import os
import json
import sys
import numpy as np
import pytetwild

def transform_point(matrix, point):
    """Transforms a 3D point using a 4x4 matrix."""
    pt_hom = np.array([point[0], point[1], point[2], 1.0])
    transformed = np.dot(matrix, pt_hom)
    return transformed[:3] / transformed[3]

def main():
    if len(sys.argv) < 3:
        print("Usage: python m2_processor.py <scene_raw_json_path> <output_dir>")
        sys.exit(1)

    scene_raw_path = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Reading raw scene data from {scene_raw_path}...")
    with open(scene_raw_path, 'r') as f:
        raw_data = json.load(f)

    # Prepare output directories
    os.makedirs(output_dir, exist_ok=True)
    meshes_dir = os.path.join(output_dir, "meshes")
    os.makedirs(meshes_dir, exist_ok=True)

    bones_config = raw_data.get("bones", {})
    raw_muscles = raw_data.get("muscles", [])
    
    scene_objects = []

    for m in raw_muscles:
        name = m["name"]
        verts = m["vertices"]
        faces = m["faces"]
        mat_world = np.array(m["matrix_world"])
        radius = m["radius"]
        material = m["material"]

        origin_lm = m["origin_landmark"]
        insertion_lm = m["insertion_landmark"]

        p_origin = np.array(origin_lm["world_position"])
        p_insertion = np.array(insertion_lm["world_position"])

        print(f"\nTetrahedralizing muscle '{name}' with {len(verts)} vertices and {len(faces)} faces...")

        # Triangulate polygon faces (e.g. split quads into triangles)
        # since pytetwild.tetrahedralize expects homogeneous 3-vertex faces.
        tri_faces = []
        for face in faces:
            if len(face) == 3:
                tri_faces.append(face)
            elif len(face) == 4:
                tri_faces.append([face[0], face[1], face[2]])
                tri_faces.append([face[0], face[2], face[3]])
            elif len(face) > 4:
                # Triangle fan triangulation
                for i in range(1, len(face) - 1):
                    tri_faces.append([face[0], face[i], face[i+1]])

        # Run pytetwild to generate tet mesh in local space
        try:
            # edge_length_fac=1.0 is relative to bbox diagonal, which is standard.
            # We can decrease it if we want a finer mesh, but 1.0 is very fast and stable on CPU.
            nodes_local, tets = pytetwild.tetrahedralize(np.array(verts), np.array(tri_faces))
        except Exception as e:
            sys.stderr.write(f"fTetWild error: Tet meshing failed for muscle '{name}'. The mesh might have self-intersections or holes. Details: {str(e)}\n")
            sys.exit(1)

        print(f"Successfully generated tet mesh: {len(nodes_local)} vertices, {len(tets)} tetrahedra.")

        # Transform local nodes to world space
        nodes_world = []
        for v_loc in nodes_local:
            v_w = transform_point(mat_world, v_loc)
            nodes_world.append(v_w)
        nodes_world = np.array(nodes_world)

        # Map attachments by projecting world nodes onto the muscle axis
        direction = p_insertion - p_origin
        len_sq = np.dot(direction, direction)
        
        origin_vertices = []
        insertion_vertices = []

        for idx, v_w in enumerate(nodes_world):
            # Compute projection factor t along muscle axis
            if len_sq > 1e-9:
                t = np.dot(v_w - p_origin, direction) / len_sq
            else:
                t = 0.0

            # Direct distances to landmarks
            dist_to_origin = np.linalg.norm(v_w - p_origin)
            dist_to_insertion = np.linalg.norm(v_w - p_insertion)

            # Assign to attachments based on projection or distance
            # Threshold of t < 0.15 is standard to capture the end cap
            if t < 0.15 or dist_to_origin < radius * 1.2:
                origin_vertices.append(idx)
            elif t > 0.85 or dist_to_insertion < radius * 1.2:
                insertion_vertices.append(idx)

        # Safety check: ensure at least some vertices are attached
        if len(origin_vertices) == 0:
            # Fall back to nearest node to origin
            dists = np.linalg.norm(nodes_world - p_origin, axis=1)
            origin_vertices = [int(np.argmin(dists))]
        if len(insertion_vertices) == 0:
            # Fall back to nearest node to insertion
            dists = np.linalg.norm(nodes_world - p_insertion, axis=1)
            insertion_vertices = [int(np.argmin(dists))]

        print(f"  Attached {len(origin_vertices)} vertices to bone '{origin_lm['bone']}'")
        print(f"  Attached {len(insertion_vertices)} vertices to bone '{insertion_lm['bone']}'")

        # Save tet mesh JSON file
        mesh_filename = f"meshes/{name}_tet.json"
        mesh_path = os.path.join(output_dir, mesh_filename)
        with open(mesh_path, 'w') as mf:
            json.dump({
                "vertices": nodes_world.tolist(),
                "tets": tets.tolist()
            }, mf, indent=2)

        # Compute constant fiber direction in world space
        if np.linalg.norm(direction) > 1e-9:
            f0 = (direction / np.linalg.norm(direction)).tolist()
        else:
            f0 = [0.0, 0.0, 1.0]

        # Build object configuration
        obj_config = {
            "name": name,
            "mesh_file": mesh_filename,
            "material": material,
            "fiber": {
                "type": "constant",
                "direction": f0
            },
            "attachments": [
                {
                    "bone": origin_lm["bone"],
                    "vertices": origin_vertices
                },
                {
                    "bone": insertion_lm["bone"],
                    "vertices": insertion_vertices
                }
            ]
        }
        scene_objects.append(obj_config)

    # Write scene.json
    scene_config = {
        "bones": bones_config,
        "objects": scene_objects
    }
    scene_path = os.path.join(output_dir, "scene.json")
    with open(scene_path, 'w') as sf:
        json.dump(scene_config, sf, indent=2)
    print(f"Saved final solver scene configuration to {scene_path}")

    # Write animation.json
    animation_config = {
        "fps": raw_data["fps"],
        "frames": raw_data["frames"]
    }
    animation_path = os.path.join(output_dir, "animation.json")
    with open(animation_path, 'w') as af:
        json.dump(animation_config, af, indent=2)
    print(f"Saved final solver animation configuration to {animation_path}")

if __name__ == "__main__":
    main()

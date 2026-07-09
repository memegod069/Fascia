import os
import json
import numpy as np
import warp as wp
import warp.examples.fem.utils as fem_example_utils

wp.init()

def make_fusiform_muscle_data(res_x=12, res_y=4, res_z=4, L=1.0, R=0.15, offset_y=0.0):
    """Generates a block grid mesh and deforms it into a spindle/fusiform shape."""
    res = wp.vec3i(res_x, res_y, res_z)
    positions_wp, tets_wp = fem_example_utils.gen_tetmesh(
        res,
        bounds_lo=wp.vec3(0.0, -1.0, -1.0),
        bounds_hi=wp.vec3(L, 1.0, 1.0)
    )
    
    pos = positions_wp.numpy()
    tets = tets_wp.numpy().tolist()
    
    # Deform positions to create the thick middle and thin ends
    for i in range(len(pos)):
        x = pos[i][0]
        y = pos[i][1]
        z = pos[i][2]
        
        # Scale radius based on position along the X-axis
        scale = np.sin(np.pi * x / L)
        scale = 0.8 * scale + 0.2  # Keep at least 20% thickness at the ends
        
        pos[i][1] = y * R * scale + offset_y
        pos[i][2] = z * R * scale
        
    return pos.tolist(), tets

def generate_data():
    os.makedirs("meshes", exist_ok=True)
    
    print("Generating mesh for Muscle A...")
    pos_a, tets_a = make_fusiform_muscle_data(offset_y=0.0)
    mesh_a_path = "meshes/muscle_a.json"
    with open(mesh_a_path, "w") as f:
        json.dump({"vertices": pos_a, "tets": tets_a}, f, indent=2)
    print(f"Saved Muscle A mesh to {mesh_a_path}")
    
    print("Generating mesh for Muscle B...")
    pos_b, tets_b = make_fusiform_muscle_data(offset_y=0.5)
    mesh_b_path = "meshes/muscle_b.json"
    with open(mesh_b_path, "w") as f:
        json.dump({"vertices": pos_b, "tets": tets_b}, f, indent=2)
    print(f"Saved Muscle B mesh to {mesh_b_path}")
    
    # Find boundary indices (X < 0.05 for origin, X > 0.95 for insertion)
    # Muscle A
    origin_indices_a = [i for i, p in enumerate(pos_a) if p[0] < 0.05]
    insertion_indices_a = [i for i, p in enumerate(pos_a) if p[0] > 0.95]
    
    # Muscle B
    origin_indices_b = [i for i, p in enumerate(pos_b) if p[0] < 0.05]
    insertion_indices_b = [i for i, p in enumerate(pos_b) if p[0] > 0.95]
    
    # Define scene.json
    scene = {
        "bones": {
            "OriginBone": {
                "bind_matrix": [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0]
                ]
            },
            "InsertionBone": {
                "bind_matrix": [
                    [1.0, 0.0, 0.0, 1.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0]
                ]
            }
        },
        "objects": [
            {
                "name": "muscle_a",
                "mesh_file": mesh_a_path,
                "material": {
                    "mu": 34.01,
                    "lam": 1500.0,
                    "sigma_max": 24.0
                },
                "fiber": {
                    "type": "constant",
                    "direction": [1.0, 0.0, 0.0]
                },
                "attachments": [
                    {
                        "bone": "OriginBone",
                        "vertices": origin_indices_a
                    },
                    {
                        "bone": "InsertionBone",
                        "vertices": insertion_indices_a
                    }
                ]
            },
            {
                "name": "muscle_b",
                "mesh_file": mesh_b_path,
                "material": {
                    "mu": 34.01,
                    "lam": 1500.0,
                    "sigma_max": 24.0
                },
                "fiber": {
                    "type": "constant",
                    "direction": [1.0, 0.0, 0.0]
                },
                "attachments": [
                    {
                        "bone": "OriginBone",
                        "vertices": origin_indices_b
                    },
                    {
                        "bone": "InsertionBone",
                        "vertices": insertion_indices_b
                    }
                ]
            }
        ]
    }
    
    with open("scene.json", "w") as f:
        json.dump(scene, f, indent=2)
    print("Saved scene.json")
    
    # Generate animation.json
    num_frames = 100
    frames = []
    
    for frame in range(num_frames + 1):
        t = frame / float(num_frames)
        # InsertionBone translates in X over time: 1.0 -> 1.1 -> 1.0
        # Ramps up to 1.1 at frame 50, then back to 1.0 at frame 100
        disp_x = 0.1 * np.sin(np.pi * t)
        
        # OriginBone matrix (remains identity)
        m_origin = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ]
        
        # InsertionBone matrix (translated along X)
        m_insertion = [
            [1.0, 0.0, 0.0, 1.0 + disp_x],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ]
        
        # Muscle A is active (ramp 0 to 1 at frame 50, then back to 0 at frame 100)
        activation_a = float(np.sin(np.pi * t))
        # Muscle B remains passive (0.0)
        activation_b = 0.0
        
        frames.append({
            "frame": frame,
            "bones": {
                "OriginBone": m_origin,
                "InsertionBone": m_insertion
            },
            "activations": {
                "muscle_a": activation_a,
                "muscle_b": activation_b
            }
        })
        
    animation = {
        "fps": 24,
        "frames": frames
    }
    
    with open("animation.json", "w") as f:
        json.dump(animation, f, indent=2)
    print("Saved animation.json")

if __name__ == "__main__":
    generate_data()

import os
import json
import numpy as np
import warp as wp
import warp.fem as fem
import warp.examples.fem.utils as fem_example_utils

wp.init()

# -------------------------------------------------------------------------
# Warp Device Functions
# -------------------------------------------------------------------------

@wp.func
def cofactor33(F: wp.mat33) -> wp.mat33:
    """Robust cofactor matrix computation in 3D using column cross products."""
    c0 = wp.vec3(F[0, 0], F[1, 0], F[2, 0])
    c1 = wp.vec3(F[0, 1], F[1, 1], F[2, 1])
    c2 = wp.vec3(F[0, 2], F[1, 2], F[2, 2])
    
    col0 = wp.cross(c1, c2)
    col1 = wp.cross(c2, c0)
    col2 = wp.cross(c0, c1)
    
    return wp.matrix_from_cols(col0, col1, col2)

@wp.func
def outer_product(a: wp.vec3, b: wp.vec3) -> wp.mat33:
    """Compute the outer product of two 3D vectors."""
    return wp.mat33(
        a[0]*b[0], a[0]*b[1], a[0]*b[2],
        a[1]*b[0], a[1]*b[1], a[1]*b[2],
        a[2]*b[0], a[2]*b[1], a[2]*b[2]
    )

# -------------------------------------------------------------------------
# FEM Integrands
# -------------------------------------------------------------------------

@fem.integrand
def muscle_gradient(
    s: fem.Sample,
    u_cur: fem.Field,
    v: fem.Field,
    mu: float,
    lam: float,
    sigma_active: float,
    f0_x: float,
    f0_y: float,
    f0_z: float,
):
    grad_v = fem.grad(v, s)
    
    # Deformation gradient F = I + grad(u_cur)
    F = wp.identity(n=3, dtype=float) + fem.grad(u_cur, s)
    
    # Volume term (J) and cofactor (H)
    J = wp.determinant(F)
    H = cofactor33(F)
    
    # Stable Neo-Hookean passive stress: P = mu * F + (lam * (J - 1.0) - mu) * H
    P_passive = mu * F + (lam * (J - 1.0) - mu) * H
    
    # Active fiber stress: P_active = sigma_active * F * (f0 * f0^T)
    f0 = wp.vec3(f0_x, f0_y, f0_z)
    f0_mat = outer_product(f0, f0)
    P_active = sigma_active * F * f0_mat
    
    P_total = P_passive + P_active
    
    return wp.ddot(grad_v, P_total)


@fem.integrand
def muscle_hessian(
    s: fem.Sample,
    u_cur: fem.Field,
    u: fem.Field,
    v: fem.Field,
    mu: float,
    lam: float,
    sigma_active: float,
    f0_x: float,
    f0_y: float,
    f0_z: float,
):
    grad_u = fem.grad(u, s)
    grad_v = fem.grad(v, s)
    
    # Deformation gradient F = I + grad(u_cur)
    F = wp.identity(n=3, dtype=float) + fem.grad(u_cur, s)
    
    # Cofactor H
    H = cofactor33(F)
    
    # Gauss-Newton approximation for passive Hessian
    dJ_du = wp.ddot(H, grad_u)
    dJ_dv = wp.ddot(H, grad_v)
    H_passive = mu * wp.ddot(grad_v, grad_u) + lam * dJ_du * dJ_dv
    
    # Active Hessian contribution
    f0 = wp.vec3(f0_x, f0_y, f0_z)
    f0_mat = outer_product(f0, f0)
    H_active = sigma_active * wp.ddot(grad_v, grad_u * f0_mat)
    
    return H_passive + H_active


@fem.integrand
def muscle_boundary_projector(
    s: fem.Sample,
    u: fem.Field,
    v: fem.Field,
    pin_weight: fem.Field,
):
    """Binds boundary conditions using a spatial pin weight field."""
    return pin_weight(s) * wp.dot(u(s), v(s))


@fem.integrand
def muscle_boundary_displacement(
    s: fem.Sample,
    v: fem.Field,
    pin_disp: fem.Field,
):
    """Sets displacement based on the spatial pin displacement field."""
    return wp.dot(pin_disp(s), v(s))

# -------------------------------------------------------------------------
# Simulation Helper Classes and Functions
# -------------------------------------------------------------------------

def get_boundary_faces(tets):
    """Finds all outer surface boundary faces (shared by exactly one tetrahedron)."""
    face_counts = {}
    for tet in tets:
        faces = [
            tuple(sorted([tet[0], tet[1], tet[2]])),
            tuple(sorted([tet[0], tet[2], tet[3]])),
            tuple(sorted([tet[0], tet[3], tet[1]])),
            tuple(sorted([tet[1], tet[2], tet[3]])),
        ]
        for f in faces:
            face_counts[f] = face_counts.get(f, 0) + 1
            
    return [f for f, count in face_counts.items() if count == 1]


def save_obj(filename, vertices, faces):
    """Saves the surface mesh to an OBJ file."""
    with open(filename, 'w') as f:
        f.write("# OBJ export from Fascia M1 Solver\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def compute_volume(positions, tets):
    """Computes the total volume of the tetrahedral mesh."""
    pos = positions.numpy() if hasattr(positions, "numpy") else np.array(positions)
    tets_np = tets.numpy() if hasattr(tets, "numpy") else np.array(tets)
    total_volume = 0.0
    for tet in tets_np:
        p0 = pos[tet[0]]
        p1 = pos[tet[1]]
        p2 = pos[tet[2]]
        p3 = pos[tet[3]]
        
        v0 = p0 - p3
        v1 = p1 - p3
        v2 = p2 - p3
        
        vol = abs(np.dot(v0, np.cross(v1, v2))) / 6.0
        total_volume += vol
    return total_volume


def transform_point(matrix, point):
    """Transforms a 3D point using a 4x4 matrix."""
    pt_hom = np.array([point[0], point[1], point[2], 1.0])
    transformed = np.dot(matrix, pt_hom)
    return transformed[:3] / transformed[3]


class DeformableObject:
    def __init__(self, obj_config, bone_configs):
        self.name = obj_config["name"]
        
        # Load mesh from json file
        mesh_path = obj_config["mesh_file"]
        print(f"Loading mesh for {self.name} from {mesh_path}...")
        with open(mesh_path, "r") as f:
            mesh_data = json.load(f)
            
        self.rest_positions_np = np.array(mesh_data["vertices"], dtype=np.float32)
        self.tets_np = np.array(mesh_data["tets"], dtype=np.int32)
        
        self.num_vertices = len(self.rest_positions_np)
        self.num_tets = len(self.tets_np)
        
        # Convert to Warp arrays
        self.rest_positions = wp.array(self.rest_positions_np, dtype=wp.vec3)
        self.tets = wp.array(self.tets_np, dtype=wp.int32)
        
        self.boundary_faces = get_boundary_faces(self.tets_np)
        print(f"Object {self.name}: {self.num_vertices} vertices, {self.num_tets} tetrahedra, {len(self.boundary_faces)} surface faces.")
        
        # Setup warp.fem geometry and spaces
        self.geo = fem.Tetmesh(tet_vertex_indices=self.tets, positions=self.rest_positions)
        self.u_space = fem.make_polynomial_space(self.geo, degree=1, dtype=wp.vec3)
        self.u_field = self.u_space.make_field()
        
        self.boundary = fem.BoundarySides(self.geo)
        self.domain = fem.Cells(geometry=self.geo)
        
        # Boundary condition spaces
        self.u_bd_test = fem.make_test(space=self.u_space, domain=self.boundary)
        self.u_bd_trial = fem.make_trial(space=self.u_space, domain=self.boundary)
        
        # Setup pin weight and pin displacement fields
        self.scalar_space = fem.make_polynomial_space(self.geo, degree=1, dtype=float)
        self.pin_weight_field = self.scalar_space.make_field()
        self.pin_disp_field = self.u_space.make_field()
        
        # Populate constant pin weights from attachments
        pin_weights = np.zeros(self.num_vertices, dtype=np.float32)
        self.attachments = obj_config.get("attachments", [])
        
        for att in self.attachments:
            bone_name = att["bone"]
            vertices = att["vertices"]
            print(f"  Attaching {len(vertices)} vertices to bone {bone_name}")
            for v_idx in vertices:
                pin_weights[v_idx] = 1.0
                
        self.pin_weight_field.dof_values.assign(wp.array(pin_weights, dtype=float))
        
        # Pre-integrate boundary projector matrix
        print("  Pre-integrating boundary projector...")
        self.u_bd_matrix = fem.integrate(
            muscle_boundary_projector,
            fields={"u": self.u_bd_trial, "v": self.u_bd_test, "pin_weight": self.pin_weight_field.trace()},
            assembly="nodal",
        )
        fem.normalize_dirichlet_projector(self.u_bd_matrix)
        
        # Setup trial/test for main domain
        self.u_test = fem.make_test(space=self.u_space, domain=self.domain)
        self.u_trial = fem.make_trial(space=self.u_space, domain=self.domain)
        
        # Material properties
        mat_config = obj_config["material"]
        self.mu = float(mat_config["mu"])
        self.lam = float(mat_config["lam"])
        self.sigma_max = float(mat_config["sigma_max"])
        
        # Fiber orientation
        fiber_config = obj_config["fiber"]
        if fiber_config["type"] == "constant":
            self.f0 = np.array(fiber_config["direction"], dtype=np.float32)
            # Normalize fiber direction
            self.f0 /= np.linalg.norm(self.f0)
        else:
            raise ValueError(f"Unsupported fiber type: {fiber_config['type']}")
            
        self.initial_volume = compute_volume(self.rest_positions_np, self.tets_np)
        print(f"  Initial volume: {self.initial_volume:.6f}")
        
    def solve_frame(self, frame_bones, activation, bone_configs):
        # Update pin displacement field for this frame
        pin_disp = np.zeros((self.num_vertices, 3), dtype=np.float32)
        
        for att in self.attachments:
            bone_name = att["bone"]
            vertices = att["vertices"]
            
            # Compute T_rel = T_pose * inv(T_bind)
            T_pose = np.array(frame_bones[bone_name], dtype=np.float32)
            T_bind = np.array(bone_configs[bone_name]["bind_matrix"], dtype=np.float32)
            T_rel = np.matmul(T_pose, np.linalg.inv(T_bind))
            
            for v_idx in vertices:
                x_rest = self.rest_positions_np[v_idx]
                x_target = transform_point(T_rel, x_rest)
                pin_disp[v_idx] = x_target - x_rest
                
        self.pin_disp_field.dof_values.assign(wp.array(pin_disp, dtype=wp.vec3))
        
        # Re-integrate boundary RHS for this frame
        u_bd_rhs = fem.integrate(
            muscle_boundary_displacement,
            fields={"v": self.u_bd_test, "pin_disp": self.pin_disp_field.trace()},
            assembly="nodal",
            output_dtype=wp.vec3,
        )
        
        sigma_active = activation * self.sigma_max
        
        # Newton-Raphson solver
        num_newton_iters = 5
        for newton_iter in range(num_newton_iters):
            # Tangent stiffness matrix K (Hessian)
            u_matrix = fem.integrate(
                muscle_hessian,
                fields={"u_cur": self.u_field, "u": self.u_trial, "v": self.u_test},
                values={
                    "mu": self.mu, 
                    "lam": self.lam, 
                    "sigma_active": sigma_active,
                    "f0_x": float(self.f0[0]),
                    "f0_y": float(self.f0[1]),
                    "f0_z": float(self.f0[2])
                },
                output_dtype=float,
            )
            
            # Residual force vector R (Gradient)
            u_rhs = fem.integrate(
                muscle_gradient,
                fields={"u_cur": self.u_field, "v": self.u_test},
                values={
                    "mu": self.mu, 
                    "lam": self.lam, 
                    "sigma_active": sigma_active,
                    "f0_x": float(self.f0[0]),
                    "f0_y": float(self.f0[1]),
                    "f0_z": float(self.f0[2])
                },
                output_dtype=wp.vec3,
            )
            
            # Project boundary conditions
            fem.project_linear_system(
                u_matrix,
                u_rhs,
                self.u_bd_matrix,
                u_bd_rhs if newton_iter == 0 else None,
                normalize_projector=False
            )
            
            # Solve using CG
            du = wp.zeros_like(self.u_field.dof_values)
            fem_example_utils.bsr_cg(u_matrix, b=u_rhs, x=du, quiet=True)
            
            # Update displacement: u = u - du
            fem.linalg.array_axpy(x=du, y=self.u_field.dof_values, alpha=-1.0, beta=1.0)
            
        # Return the deformed positions
        deformed_pos = self.rest_positions_np + self.u_field.dof_values.numpy()
        return deformed_pos


def run_solver(scene_json_path="scene.json", animation_json_path="animation.json", output_dir="m1_output", limit_frames=None):
    # Load scene setup
    print(f"Loading scene configuration from {scene_json_path}...")
    with open(scene_json_path, "r") as f:
        scene_config = json.load(f)
        
    bone_configs = scene_config["bones"]
    
    # Load animation sequence
    print(f"Loading animation sequence from {animation_json_path}...")
    with open(animation_json_path, "r") as f:
        anim_config = json.load(f)
        
    frames = anim_config["frames"]
    if limit_frames is not None:
        frames = frames[:limit_frames]
        
    # Initialize all deformable objects
    objects = []
    for obj_config in scene_config["objects"]:
        obj = DeformableObject(obj_config, bone_configs)
        objects.append(obj)
        
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    for obj in objects:
        os.makedirs(os.path.join(output_dir, obj.name), exist_ok=True)
        
    print(f"\nStarting simulation loop over {len(frames)} frames...", flush=True)
    
    results = {obj.name: [] for obj in objects}
    
    for f_idx, frame_data in enumerate(frames):
        frame_num = frame_data["frame"]
        frame_bones = frame_data["bones"]
        activations = frame_data["activations"]
        
        print(f"\n--- Frame {frame_num:03d} ---", flush=True)
        
        for obj in objects:
            activation = activations.get(obj.name, 0.0)
            
            # Solve the frame warm-started from the previous frame's displacement
            deformed_pos = obj.solve_frame(frame_bones, activation, bone_configs)
            results[obj.name].append(deformed_pos.tolist())
            
            # Calculate metrics
            current_volume = compute_volume(deformed_pos, obj.tets_np)
            vol_drift = abs(current_volume - obj.initial_volume) / obj.initial_volume * 100.0
            
            # Export to OBJ
            obj_path = os.path.join(output_dir, obj.name, f"{obj.name}_{frame_num:03d}.obj")
            save_obj(obj_path, deformed_pos, obj.boundary_faces)
            
            print(f"  Object: {obj.name:12s} | Activation: {activation:.2f} | Volume: {current_volume:.6f} | Drift: {vol_drift:.2f}%", flush=True)
            
    print("\nSimulation completed successfully!", flush=True)
    return results


if __name__ == "__main__":
    with wp.ScopedDevice("cpu"):
        run_solver()

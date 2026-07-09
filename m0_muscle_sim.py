import os
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
    # Muscle fibers are aligned with the X-axis (1.0, 0.0, 0.0)
    f0 = wp.vec3(1.0, 0.0, 0.0)
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
    f0 = wp.vec3(1.0, 0.0, 0.0)
    f0_mat = outer_product(f0, f0)
    H_active = sigma_active * wp.ddot(grad_v, grad_u * f0_mat)
    
    return H_passive + H_active


@fem.integrand
def muscle_boundary_projector(
    s: fem.Sample,
    domain: fem.Domain,
    u: fem.Field,
    v: fem.Field,
):
    """Binds boundary conditions to the ends of the muscle (X < 0.05 and X > 0.95)."""
    x = domain(s)
    # We fix the origin-end (x[0] < 0.05) and insertion-end (x[0] > 0.95)
    weight = wp.where((x[0] < 0.05) or (x[0] > 0.95), 1.0, 0.0)
    return weight * wp.dot(u(s), v(s))


@fem.integrand
def muscle_boundary_displacement(
    s: fem.Sample,
    domain: fem.Domain,
    v: fem.Field,
    disp_x: float,
    disp_y: float,
    disp_z: float,
):
    """Sets target displacements for the boundary vertices."""
    x = domain(s)
    # Origin remains at (0, 0, 0), insertion is shifted by (disp_x, disp_y, disp_z)
    target = wp.where(x[0] > 0.95, wp.vec3(disp_x, disp_y, disp_z), wp.vec3(0.0, 0.0, 0.0))
    weight = wp.where((x[0] < 0.05) or (x[0] > 0.95), 1.0, 0.0)
    return weight * wp.dot(target, v(s))

# -------------------------------------------------------------------------
# Mesh Generation and Helpers
# -------------------------------------------------------------------------

def make_fusiform_muscle(res_x=12, res_y=4, res_z=4, L=1.0, R=0.15):
    """Generates a block grid mesh and deforms it into a spindle/fusiform shape."""
    # Generate the block grid tetmesh (x: 0 to L, y: -1 to 1, z: -1 to 1)
    res = wp.vec3i(res_x, res_y, res_z)
    positions_np, tets_np = fem_example_utils.gen_tetmesh(
        res,
        bounds_lo=wp.vec3(0.0, -1.0, -1.0),
        bounds_hi=wp.vec3(L, 1.0, 1.0)
    )
    
    pos = positions_np.numpy()
    # Deform positions to create the thick middle and thin ends
    for i in range(len(pos)):
        x = pos[i][0]
        y = pos[i][1]
        z = pos[i][2]
        
        # Scale radius based on position along the X-axis
        scale = np.sin(np.pi * x / L)
        scale = 0.8 * scale + 0.2  # Keep at least 20% thickness at the ends
        
        pos[i][1] = y * R * scale
        pos[i][2] = z * R * scale
        
    return wp.array(pos, dtype=wp.vec3), tets_np

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
        f.write("# OBJ export from Fascia M0 Muscle Sim\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for face in faces:
            # OBJ uses 1-based indexing
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

# -------------------------------------------------------------------------
# Simulation Runner
# -------------------------------------------------------------------------

def run_simulation():
    # Setup directories
    os.makedirs("m0_output", exist_ok=True)
    
    # Material properties
    # E = 100.0, nu = 0.47 for better incompressibility
    mu = 34.01
    lam = 532.89
    sigma_max = 50.0  # Max active stress
    
    # Muscle dimensions
    L = 1.0
    R = 0.15
    
    print("Generating fusiform muscle mesh...")
    positions, tets = make_fusiform_muscle(res_x=12, res_y=4, res_z=4, L=L, R=R)
    tets_np = tets.numpy()
    
    # Get boundary faces for OBJ export
    boundary_faces = get_boundary_faces(tets_np)
    print(f"Mesh has {len(positions)} vertices, {len(tets_np)} tetrahedra, {len(boundary_faces)} boundary faces.")
    
    # Setup warp.fem geometry and spaces
    geo = fem.Tetmesh(tet_vertex_indices=tets, positions=positions)
    u_space = fem.make_polynomial_space(geo, degree=1, dtype=wp.vec3)
    u_field = u_space.make_field()
    
    boundary = fem.BoundarySides(geo)
    domain = fem.Cells(geometry=geo)
    
    # Boundary condition spaces
    u_bd_test = fem.make_test(space=u_space, domain=boundary)
    u_bd_trial = fem.make_trial(space=u_space, domain=boundary)
    
    print("Pre-integrating boundary projector...")
    u_bd_matrix = fem.integrate(
        muscle_boundary_projector,
        fields={"u": u_bd_trial, "v": u_bd_test},
        assembly="nodal",
    )
    fem.normalize_dirichlet_projector(u_bd_matrix)
    
    u_test = fem.make_test(space=u_space, domain=domain)
    u_trial = fem.make_trial(space=u_space, domain=domain)
    
    # Main simulation loop
    num_frames = 100
    initial_volume = compute_volume(positions, tets)
    print(f"Initial mesh volume: {initial_volume:.6f}")
    
    volumes = []
    
    for frame in range(num_frames + 1):
        # Activation value a: 0 -> 1
        a = frame / float(num_frames)
        sigma_active = a * sigma_max
        
        # Insertion target displacement: shortens along X by 15%
        disp_x = -0.15 * a * L
        
        # Integrate boundary RHS for current frame
        u_bd_rhs = fem.integrate(
            muscle_boundary_displacement,
            fields={"v": u_bd_test},
            values={"disp_x": disp_x, "disp_y": 0.0, "disp_z": 0.0},
            assembly="nodal",
            output_dtype=wp.vec3,
        )
        
        # We solve the static equilibrium from scratch at each frame.
        # This keeps the implementation robust, stable, and simple.
        u_field.dof_values.zero_()
        
        # Newton-Raphson solver
        num_newton_iters = 5
        for newton_iter in range(num_newton_iters):
            # Compute tangent stiffness matrix K (Hessian)
            u_matrix = fem.integrate(
                muscle_hessian,
                fields={"u_cur": u_field, "u": u_trial, "v": u_test},
                values={"mu": mu, "lam": lam, "sigma_active": sigma_active},
                output_dtype=float,
            )
            
            # Compute residual force vector R (Gradient)
            u_rhs = fem.integrate(
                muscle_gradient,
                fields={"u_cur": u_field, "v": u_test},
                values={"mu": mu, "lam": lam, "sigma_active": sigma_active},
                output_dtype=wp.vec3,
            )
            
            # Project Dirichlet boundary conditions
            fem.project_linear_system(
                u_matrix,
                u_rhs,
                u_bd_matrix,
                u_bd_rhs if newton_iter == 0 else None,
                normalize_projector=False
            )
            
            # Solve the linear system using CG
            du = wp.zeros_like(u_field.dof_values)
            fem_example_utils.bsr_cg(u_matrix, b=u_rhs, x=du, quiet=True)
            
            # Update the displacement field
            fem.linalg.array_axpy(x=du, y=u_field.dof_values, alpha=-1.0, beta=1.0)
            
        # Compute the deformed positions for this frame: x = X + u
        deformed_pos_np = positions.numpy() + u_field.dof_values.numpy()
        deformed_pos_wp = wp.array(deformed_pos_np, dtype=wp.vec3)
        
        # Calculate volume of deformed mesh
        current_volume = compute_volume(deformed_pos_wp, tets)
        volumes.append(current_volume)
        vol_drift = abs(current_volume - initial_volume) / initial_volume * 100.0
        
        # Save frame as OBJ
        obj_path = os.path.join("m0_output", f"muscle_{frame:03d}.obj")
        save_obj(obj_path, deformed_pos_np, boundary_faces)
        
        # Print progress
        if frame % 10 == 0 or frame == num_frames:
            print(f"Frame {frame:03d} | Activation a = {a:.2f} | Disp X = {disp_x:.3f} | Vol = {current_volume:.6f} | Drift = {vol_drift:.2f}%")
            
    # Print summary metrics
    max_drift = max(abs(v - initial_volume) / initial_volume * 100.0 for v in volumes)
    print("\n--- Simulation Complete ---")
    print(f"Max Volume Drift across animation: {max_drift:.2f}%")
    if max_drift < 2.0:
        print("[PASS] Volume drift acceptance test (< 2.0%)")
    else:
        print("[FAIL] Volume drift acceptance test (>= 2.0%)")

if __name__ == "__main__":
    with wp.ScopedDevice("cpu"):
        run_simulation()

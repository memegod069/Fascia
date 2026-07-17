# SPEC 13 — M1 Solver Core

**Target executor:** AI Coding Agent.
**Scope:** Design and implement a reusable multi-object, rig-driven soft-tissue simulation engine using `warp.fem` that runs on CPU (with CPU fallback) and is driven by `scene.json` and `animation.json` configuration files.
**Estimated size:** ~300-400 lines of python code in `m1_solver.py` + a test script `tests/test_m1.py`.

---

## 1. Why this change is needed

In Milestone M0, we proved that a single fusiform muscle could be simulated standing alone in Warp with active fiber contraction and volume preservation. However, that simulation was hardcoded:
- The mesh was generated procedurally inside the script.
- The boundary conditions (pinning the origin, moving the insertion) were defined by hardcoded spatial coordinates (`X < 0.05`).
- The muscle fiber direction was assumed to be constant along the X-axis.
- It only supported a single muscle.

To build a complete soft-tissue pipeline (Fascia), we must generalize this solver. The engine needs to:
1. Load multiple muscle/tissue meshes of arbitrary shapes.
2. Drive the boundary conditions (tendon attachments) using a skeleton rig animation exported from Blender.
3. Drive activation dynamically over time from the animation timeline.
4. Support warm-starting between frames to preserve volume accurately and converge rapidly.
5. Provide a golden-file test to prevent regression.

---

## 2. Architectural Decision

1. **File-Based Input/Output (Loose Coupling):**
   The Blender add-on and the simulation engine will communicate purely via files. This ensures the engine remains standalone, has no Blender dependency (so it can run on a Google Colab GPU instance in M3), and is easy to test.

2. **JSON Schema Formats:**
   - **`scene.json`**: Lists all simulation objects (muscles/tissues), their material parameters, their fiber fields, and their bone attachments.
   - **`animation.json`**: Describes bone transformation matrices (4x4 world space transforms) and muscle activations for every frame.
   - **Tet Mesh JSON (`.json`)**: To avoid importing complex binary formats like Medit `.mesh` or VTK `.vtk` (which require external libraries), tetrahedral meshes will be stored in a simple JSON structure containing vertices and tetrahedral vertex indices.

3. **Rig-Driven Dirichlet Boundary Conditions:**
   Instead of pinning vertices by bounding-box coordinate thresholds, vertices are explicitly bound to bones. Each bound vertex has a bone name and a weight.
   - In M1, we assume rigid attachment (weight = 1.0) to a single bone for simplicity and reliability.
   - For any boundary vertex bound to a bone, its target position at frame $t$ is calculated by applying the bone's world transform matrix to its rest-pose position.
   - The displacement $u(t) = x_{\text{target}}(t) - x_{\text{rest}}$ is applied as a Dirichlet boundary condition.

4. **Multi-Object Sequential Solver:**
   Because muscles do not interact or contact each other in M1 (contact is deferred to M3), solving them sequentially is mathematically identical to solving them in a combined system, but much faster and memory-efficient. We will solve each object one by one for all frames, or solve all objects frame by frame (which is better for future contact integration). Let's solve frame by frame so that frame state is advanced together.

5. **Warp.FEM Adaptation:**
   We will adapt the Stable Neo-Hookean material model and fiber-activation integrands from `m0_muscle_sim.py`. Since fiber directions vary across arbitrary meshes, fiber fields will be specified as per-tetrahedron vectors, falling back to a default constant vector if not specified.

---

## 3. Data Formats

### 3.1. Tet Mesh JSON File (`meshes/example_muscle.json`)
```json
{
  "vertices": [
    [0.0, 0.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.5, 0.866, 0.0],
    [0.5, 0.288, 0.816]
  ],
  "tets": [
    [0, 1, 2, 3]
  ]
}
```

### 3.3. Scene Configuration File (`scene.json`)
```json
{
  "objects": [
    {
      "name": "biceps",
      "mesh_file": "meshes/biceps_tet.json",
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
          "bone": "Scapula",
          "vertices": [0, 1, 2]
        },
        {
          "bone": "Radius",
          "vertices": [3]
        }
      ]
    }
  ]
}
```

### 3.4. Animation Configuration File (`animation.json`)
```json
{
  "fps": 24,
  "frames": [
    {
      "frame": 0,
      "bones": {
        "Scapula": [
          [1.0, 0.0, 0.0, 0.0],
          [0.0, 1.0, 0.0, 0.0],
          [0.0, 0.0, 1.0, 0.0],
          [0.0, 0.0, 0.0, 1.0]
        ],
        "Radius": [
          [1.0, 0.0, 0.0, 0.0],
          [0.0, 1.0, 0.0, 0.0],
          [0.0, 0.0, 1.0, 0.0],
          [0.0, 0.0, 0.0, 1.0]
        ]
      },
      "activations": {
        "biceps": 0.0
      }
    }
  ]
}
```

---

## 4. Implementation Details

We will write `m1_solver.py` containing:
- Mesh loader (parses Tet Mesh JSON and converts to Warp arrays).
- Scene loader (reads `scene.json` and `animation.json`).
- Boundary condition builder (pre-integrates Dirichlet matrices and RHS vectors for each object and bone transform).
- Solver loop (advances frame by frame, solves Newton iterations, warm-starts displacements, and saves output files).
- Output writer (writes simulated OBJ sequences for each object).

---

## 5. Verification & Acceptance Criteria

1. **Multi-Object Test:** Set up a scene with two separate muscles attached to a moving rig. Ensure both solve correctly across a 100-frame animation without manual intervention.
2. **Warm-Starting & Volume Preservation:** Verify that the solver maintains a volume drift of `< 2.0%` for all simulated muscles, and that it warm-starts displacements properly.
3. **Golden-File Test:** Check in a simple test scenario and its reference output. Running `python tests/test_m1.py` must assert that the solved vertex positions match the reference with relative error `< 1e-4`.

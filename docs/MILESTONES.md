# Fascia — Milestones

Each milestone has a scope, a hard acceptance test, and an explicit
"out of scope" list. Do not start a milestone until the previous one's
acceptance test has actually passed — not "looks close."

Hardware note: M0–M2 must run on the laptop CPU (Intel UHD 620, no
NVIDIA GPU) via Warp's CPU/LLVM backend. M3 onward may require bursting
to a free Google Colab GPU runtime (T4) — the engine's file-based
architecture (scene.json in, cache out) makes this a copy-paste of files
into a notebook, not a redesign.

---

## M0 — Single-Muscle FEM Proof (the kill-switch milestone)

**Scope:** One fusiform muscle mesh, tet-meshed, simulated standalone in
a Warp script. No Blender integration, no rig, no contact, no skin.

**Steps:**
1. Build or download a simple stretched-sphere muscle mesh.
2. Run it through fTetWild to get a tetrahedral mesh.
3. Write a Warp script (start from Warp's own soft-body example) that:
   - Pins the origin-end vertices in place.
   - Pins the insertion-end vertices to an animated target position.
   - Adds a fiber-direction energy term so the muscle shortens along a
     defined fiber axis as an activation value `a` goes from 0 to 1.
   - Uses the Stable Neo-Hookean material model for the bulk tissue.
4. Animate `a: 0 → 1` over 100 frames, write an OBJ sequence.
5. Import the OBJ sequence into Blender and scrub the timeline.

**Acceptance test (all must hold):**
- The muscle visibly shortens along its fiber axis by at least 15% at
  `a = 1`.
- It visibly bulges perpendicular to the fiber axis — and this bulge
  must be an emergent result of the volume/incompressibility term, NOT
  an authored scale multiplier on top.
- Volume drift across the whole animation stays under 2%.
- The solve does not crash, produce NaNs, or invert elements, across at
  least 3 separate runs with different activation curves.
- Runs to completion on the CPU backend (record the per-frame time in
  STATE.md — this is your CPU performance baseline, not a bar to hit).

**Out of scope:** rig/bones, multiple muscles, contact, skin, Blender
addon integration, Colab/GPU.

**If this milestone can't be made convincing within about a month of
real effort:** stop, report exactly what failed and why, and revisit
whether this architecture is right before investing further. This is
the entire purpose of doing M0 first and small.

---

## M1 — Solver Core (multi-object, rig-driven, repeatable)

**Scope:** Generalize M0's script into a reusable solver: multiple tet
meshes, bone-driven boundary conditions from an exported skeleton
animation, warm-starting between frames.

**Steps:**
1. Define a minimal `scene.json` format: list of tet meshes, their
   material properties, their fiber fields, their bone attachments.
2. Export a simple skeleton animation (2-3 bones) to Alembic or a plain
   JSON keyframe list from Blender.
3. Solver reads scene.json + the animation, applies bone transforms as
   Dirichlet boundary conditions on attached vertices, solves each frame
   with Newton's method (or Warp's projective/VBD equivalent), warm-
   starting from the previous frame's solution.
4. Write a golden-file test: fixed scene + fixed animation → assert
   output vertex positions match a saved reference within a stated
   numeric tolerance (e.g. relative error < 1e-4).

**Acceptance test:**
- Two muscles attached to a simple 2-3 bone rig solve correctly across
  100 frames, unattended, with no manual intervention.
- The golden-file test passes and is checked into the repo so future
  sessions can't silently regress this.
- Per-frame solve time recorded in STATE.md.

**Out of scope:** contact between the two muscles (they can overlap for
now — that's M3's job), fiber field automation (still hand-authored),
Blender addon UI (scene.json still hand-written or minimally scripted).

---

## M2 — Anatomy Pipeline (Blender integration begins)

**Scope:** Wire the existing Fascia addon (landmarks, species JSON,
muscle generation, rig binding — all of which already work) into the
new engine as an export step.

**Steps:**
1. Add an export operator: walks the addon's existing muscle objects +
   rig binding data and writes scene.json + an animation cache in the
   M1 format.
2. Automatic fiber field generation: solve a heat/geodesic flow across
   each tet mesh from its origin landmark to its insertion landmark,
   producing a per-tet fiber direction (replaces the hand-authored
   fields from M0/M1).
3. Wrap fTetWild as a callable step with validation and plain-English
   error messages (e.g. "this mesh has a hole, tet meshing failed").
4. Add a Blender-side visualization of the fiber field (arrows or lines)
   so it can be checked by eye before solving.

**Acceptance test:**
- One-click export from the existing addon produces a scene.json that
  M1's solver consumes without modification.
- Fiber directions visibly flow from origin to insertion on at least 3
  differently-shaped test muscles, viewable in Blender.
- fTetWild failures produce a clear, specific error, not a silent crash.

**Out of scope:** contact, skin sliding, fat/fascia layers.

---

## M3 — Contact and Layering (the hard one — expect this to take longest)

**Scope:** Muscle-on-muscle and muscle-on-bone non-interpenetration,
then a fascia/fat layer, then skin sliding over everything.

**Two-stage approach (do not skip stage 1):**
- **Stage 1 (interim, CPU-friendly):** simple penalty/barrier contact
  using low-poly collision proxies for each muscle. Good enough for slow
  motion and static poses; explicitly documented as an interim technique.
- **Stage 2 (target):** integrate the IPC Toolkit for guaranteed
  intersection-free, friction-aware contact. This is compute-heavy —
  expect to need the Colab GPU burst path here.

**Steps:**
1. Auto-generate a decimated collision proxy per muscle.
2. Implement Stage 1 contact; verify no interpenetration in a
   multi-muscle test scene at rest and in slow motion.
3. Add a thin fascia/fat layer (extra tet layer or thin-shell) wrapping
   the muscle group.
4. Add a skin layer that slides over the fascia/fat with friction.
5. Set up the Colab notebook: installs deps, loads scene.json + anim
   cache uploaded from the laptop, runs the Stage 2 (IPC) solve, writes
   a downloadable result cache.
6. Integrate Stage 2 once the Colab path is confirmed working.

**Acceptance test:**
- Stage 1: a 3-4 muscle test scene with bone motion shows zero visible
  interpenetration across 100 frames.
- Stage 2: the same scene, run via IPC on Colab, produces measurably
  better contact behavior (no jitter/tunneling) and the notebook path is
  documented step-by-step in the repo.
- Skin visibly slides relative to the fascia/fat layer as muscles
  contract, not just bulges radially.

**Out of scope:** production performance tuning (that's M5), full
creature-scale mesh counts.

---

## M4 — Blender Integration (full round trip)

**Scope:** Author → export → solve (local CPU or Colab) → import
cache → render, as one coherent workflow with a mode switch.

**Steps:**
1. `bpy.ops.fascia.export_scene`, `bpy.ops.fascia.run_solve` (local),
   `bpy.ops.fascia.import_cache` operators.
2. A clear "Preview mode" (fast geometric approximation, existing
   system) vs. "Solve mode" (real FEM engine) toggle in the addon UI.
3. Cache import via Alembic/MDD + Mesh Cache modifier — never shape
   keys for per-frame results.

**Acceptance test:**
- A user can go from a rigged mesh in Blender to a baked, playable FEM
  simulation using only Fascia's operators, no manual file wrangling
  beyond "upload to Colab, download the result" for Stage 2 solves.
- Preview mode and Solve mode are clearly, visibly distinguished in the
  UI so nobody mistakes one for the other.

---

## M5 — Performance Hardening

**Scope:** Make the pipeline fast enough to actually iterate with.

**Steps:**
1. Per-frame timing + memory reporting operator.
2. Warm-starting, adaptive solver tolerances, batching where Warp
   supports it.
3. Document realistic numbers for both CPU-only and Colab-GPU paths at
   a stated tet count (e.g. "50k tets: X sec/frame on CPU, Y sec/frame
   on T4").

**Acceptance test:**
- A documented, reproducible benchmark exists for at least two mesh
  complexities on both the CPU and Colab paths.
- No milestone-4 workflow silently times out or hangs without a
  progress indicator.

---

## M6 — Learned Real-Time Deformer (long-term, optional)

**Scope:** Train a small model on baked M0-M5 simulation output (bone
poses + activations → tissue displacement) to approximate the FEM
result at interactive speed. This is the honest path to "real-time,"
since true real-time volumetric FEM does not exist anywhere, including
at Weta.

**Cannot start until:** M1-M5 have produced real simulation data to
train on. No shortcuts — this is compression of real physics, not a
replacement for having done the physics.

**Acceptance test:** to be defined once M5 is complete and real
training data exists. Do not pre-specify network architecture now.

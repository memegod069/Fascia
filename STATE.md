# Fascia — Project State
(Every session reads this first, and updates it before finishing.)

## Current Milestone
M2 — Anatomy Pipeline (Blender integration begins)
See docs/MILESTONES.md → M2 for the full acceptance test.

## Last Session Summary
- **M2 Exporter and fTetWild Integration Completed:**
  - **Blender Exporter (`fascia_addon.py`):** Implemented a new `FASCIA_OT_export_scene` operator that walks the active muscles and armature rig. It suppresses `fascia_flex` to `0.0` during export to capture the clean rest pose geometry, collects landmarks/bone associations, and exports a raw JSON scene.
  - **Mesh Preprocessor (`m2_processor.py`):** Wrapped the `pytetwild` package to run as an external Python subprocess. It handles polygon triangulation (to split Blender quads), tetrahedralizes surface meshes, maps attachments dynamically via segment projection ($t < 0.15$ and $t > 0.85$), and generates clean `scene.json`, `animation.json`, and tet-mesh files.
  - **End-to-End Joint Bend Solve:** Set up a clean 2-bone linear arm/joint bend (UpperArm + Forearm) animation over 60 frames in Blender. The exporter produced output that `m1_solver.py` consumed directly without modification.
  - **Verification Metrics:**
    - Attachment mapping: **100** vertices successfully bound to `UpperArm` (origin) and **100** vertices to `Forearm` (insertion) on the generated Biceps tet mesh (441 vertices, 1384 tets).
    - Solve Stability: 60-frame joint bend simulation ran to completion with zero crashes or NaNs.
    - Volume Conservation: Maximum volume drift was extremely low at **0.09%**, well below the 2.0% acceptance threshold.

- **M1 Completed successfully:** Generalized the standalone solver into a reusable rig-driven solver (`m1_solver.py`).
  - **Repeatability:** Verified node coordinates over all frames within $10^{-4}$ tolerance via golden-file tests. (Note: This is a determinism and regression check to confirm the solver reproduces its own prior output exactly, not a validation against independently verified ground-truth physics.)

## Known Issues / Open Questions
- warp.sim does not exist in warp-lang 1.15.0 (deprecated/removed); using warp.fem instead.

## Exact Next Step
- Implement the Blender-side visualization of the fiber field (arrows or lines) so it can be checked by eye before solving.
- Implement the automatic heat/geodesic flow solver to generate per-tetrahedron fiber fields from landmark attachments.

## Environment
- Machine: Dell Latitude 7300, 16GB RAM, Intel UHD 620 (no NVIDIA GPU)
- Blender: 4.2 LTS
- Python: 3.13.2
- Warp: CPU backend (v1.15.0)
- Cloud burst: Google Colab free tier (T4 GPU) — for M3 onward only

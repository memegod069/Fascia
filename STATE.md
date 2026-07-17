# Fascia — Project State
(Every session reads this first, and updates it before finishing.)

## Current Milestone
M2 — Anatomy Pipeline (Blender integration begins)
See docs/MILESTONES.md → M2 for the full acceptance test.

## M2 Anatomy Pipeline Solver Verification
- **Pose Bug Root Cause Identified:** The Blender exporter was not resetting the scene to the rest-pose frame before capturing muscle geometry. As a result, muscles were sometimes exported mid-animation (bent) rather than at rest. The attachment threshold (15/85 vs 5/95 vs 2/98) was NOT the primary cause — that was a red herring.
- **Applied Fixes:**
  1. Updated `FASCIA_OT_export_scene` in `fascia_addon.py` to call `scene.frame_set(scene.frame_start)` before capturing geometry and restore the original frame after.
  2. Fixed a parenting offset bug in `tests/test_m2_export.py`'s scene setup where a landmark was parented while the forearm bone was posed at 90°, resulting in an incorrect parent inverse matrix.
- **Verified Results:**
  * **Peak Volume Drift:** **0.055%** (at Frame 59), replacing the earlier-reported 4.44% baseline as the actual, correct M2 drift figure.
  * **Mesh Configuration:** Verified on the original untouched `0.15`/`0.85` attachment threshold, Z-aligned rest-pose Biceps mesh (460 vertices, 1502 tetrahedra) with symmetric attachments (107 `UpperArm` / 106 `Forearm`).
  * **Simulation Completeness:** 60/60 frames simulated successfully with zero crashes and zero NaNs, verified via two independent file-read methods.

- **M1 Solver Verification:** Standalone solver generalized into a reusable rig-driven solver (`m1_solver.py`).
  - Verified node coordinates over all frames within $10^{-4}$ tolerance via golden-file tests.

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

# Fascia — Project State
(Every session reads this first, and updates it before finishing.)

## Current Milestone
M2 — Anatomy Pipeline (Blender integration begins)
See docs/MILESTONES.md → M2 for the full acceptance test.

## Last Session Summary
- **M1 Completed successfully:** Generalized the standalone solver into a reusable rig-driven solver (`m1_solver.py`).
- **Key findings and verification:**
  - **Generalized Rig Binding:** Handled Dirichlet boundary conditions dynamically by setting vertex target positions from bone transforms ($T_{\text{rel}} = T_{\text{pose}} \cdot T_{\text{bind}}^{-1}$) using Warp's `.trace()` method to project cell fields onto boundary integration domains.
  - **Multi-Object support:** Simulated active Muscle A and passive Muscle B simultaneously, verifying correct passive deformation and active fiber contraction in a single system.
  - **Volume Conservation:** Kept volume drift extremely low (under **0.06%** for active muscle, **0.00%** for passive muscle), well below the 2.0% acceptance limit.
  - **Repeatability:** Built a golden-file test (`tests/test_m1.py` + `tests/golden_m1.json`) verifying node coordinates over 10 frames within $10^{-4}$ tolerance.
  - **Performance:** Recorded solve speed of **~6.9s per muscle per frame** on a CPU-only Dell Latitude.
- **M0 Completed successfully:** Standalone 3D fusiform muscle simulated using `warp.fem`. Contraction of **15.67%** at full activation ($a=1.0$), volume drift of **0.46%**.

## Known Issues / Open Questions
- warp.sim does not exist in warp-lang 1.15.0 (deprecated/removed); using warp.fem instead.

## Exact Next Step
- Start M2 (Anatomy Pipeline): Write an exporter in the Blender add-on (`fascia_addon.py`) to output `scene.json` and bone animations in the format expected by the M1 solver.
- Implement heat/geodesic flow solver to auto-generate per-tetrahedron fiber fields from landmark attachments.

## Environment
- Machine: Dell Latitude 7300, 16GB RAM, Intel UHD 620 (no NVIDIA GPU)
- Blender: 4.2 LTS
- Python: 3.13.2
- Warp: CPU backend (v1.15.0)
- Cloud burst: Google Colab free tier (T4 GPU) — for M3 onward only

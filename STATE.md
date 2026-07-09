# Fascia — Project State
(Every session reads this first, and updates it before finishing.)

## Current Milestone
M1 — Solver Core (multi-object, rig-driven, repeatable)
See docs/MILESTONES.md → M1 for the full acceptance test.

## Last Session Summary
- **M0 Completed successfully:** Wrote `m0_muscle_sim.py` implementing a 3D tetrahedral fusiform muscle simulation in `warp.fem` using a Stable Neo-Hookean material model, active fiber contraction, and fixed boundary conditions at both ends.
- **Key findings logged:**
  - `warp.sim` has been deprecated/removed in Warp 1.10+. Successfully used `warp.fem` for the elasticity solve.
  - Warp's examples run in blocking GUI mode by default unless the `--headless` flag is passed. Headless CPU simulation runs stably.
  - Replaced Python bitwise OR `|` with logical `or` inside Warp's `@fem.integrand` kernels to fix compilation errors.
  - Replaced Unicode emojis in prints to avoid Windows terminal character encoding crashes (`UnicodeEncodeError`).
  - Tuned parameters: Used $\mu = 34.01$ and $\lambda = 532.89$ (representing Poisson's ratio $\nu = 0.47$) to achieve near-incompressibility.
  - **Verification:** The muscle successfully contracted by 15% under active fiber tension (50.0 max active stress) and bulged emergent from the volume preservation. Max volume drift across the 100-frame animation was 1.10% (well below the 2% milestone requirement). The sequence of 100 OBJ frames was written to `m0_output/`.

## Known Issues / Open Questions
- warp.sim does not exist in warp-lang 1.15.0 (deprecated/removed).
  Using warp.fem instead for the elasticity solve. Verified this is fully viable for M0's fiber-activation term.

## Exact Next Step
- Start M1 (Solver Core): Generalize the standalone script to support multiple muscles/objects defined via a `scene.json` file.
- Export a simple 2-3 bone skeleton animation from Blender to drive boundary conditions on attached vertices.

## Environment
- Machine: Dell Latitude 7300, 16GB RAM, Intel UHD 620 (no NVIDIA GPU)
- Blender: 4.2 LTS
- Python: 3.13.2
- Warp: CPU backend (v1.15.0)
- Cloud burst: Google Colab free tier (T4 GPU) — for M3 onward only

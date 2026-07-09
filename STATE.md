# Fascia — Project State
(Every session reads this first, and updates it before finishing.)

## Current Milestone
M1 — Solver Core (multi-object, rig-driven, repeatable)
See docs/MILESTONES.md → M1 for the full acceptance test.

## Last Session Summary
- **M0 Completed successfully:** Wrote `m0_muscle_sim.py` implementing a standalone 3D tetrahedral fusiform muscle simulation using `warp.fem`.
- **Key findings and verification:**
  - **Emergent Shortening:** Pinned only the origin end ($X < 0.05$) in place, leaving the insertion end free. The shortening emerged solely from active fiber tension, contracting by **15.67%** at full activation ($a=1.0$), meeting the $> 15\%$ milestone criteria.
  - **Volume Conservation:** Increased bulk modulus to $\lambda = 1500.0$ and enabled **warm-starting** (keeping previous frame's solved displacement as the initial guess) to allow the Newton solver to converge to high precision. This successfully restricted the maximum volume drift to only **0.46%** (well below the $2.0\%$ limit).
  - **Warp Compatibility:** Resolved `warp.sim` deprecation by building a displacement-based FEM solver in `warp.fem`. Resolved compiler issues by replacing bitwise operators with logical `or` inside integrands.
  - **Windows Compatibility:** Swapped emoji characters in print statements to ASCII to prevent `UnicodeEncodeError` crashes on non-UTF-8 console environments.
  - **Output:** Stored the 100-frame OBJ mesh sequence inside the ignored `m0_output/` folder.

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

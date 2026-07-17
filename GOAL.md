# Fascia — Goal

Build Fascia: an open-source Weta Tissue alternative.

Architecture: a Blender addon (authoring front-end: anatomy, landmarks,
muscles, rig binding, preview mode, cache import) + a standalone GPU
simulation engine (NVIDIA Warp: tetrahedral FEM, fiber-based muscle
activation, layered contact). They talk through files (JSON scene
description + Alembic/OBJ caches) — never physics inside Blender itself.

Hardware note: development machine is a laptop with **no NVIDIA GPU**
(CPU-only via Warp's LLVM backend). Milestones M0–M2 must run entirely on
CPU. From M3 onward, heavy solves burst to a free Google Colab GPU runtime;
the laptop stays for authoring, debugging, and small-scale test scenes.

Before doing ANYTHING:
1. Read AGENTS_ENGINE.md (the rules — these override any conflicting instinct).
2. Read STATE.md (what happened last session, what's next).
3. Read docs/MILESTONES.md (find the current milestone, read ONLY that
   milestone's section).
4. State your single micro-goal for this session before writing any code.

Before finishing:
1. Update STATE.md.
2. Leave the repo in a working, committed state.

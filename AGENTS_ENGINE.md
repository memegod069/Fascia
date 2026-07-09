# Fascia — Rules for AI Agents

Read GOAL.md and STATE.md before this file loses context. These rules
outrank any suggestion you're about to make that contradicts them.

## Prime Rules

1. **Quality target: Weta Tissue / RDR2 class.** Volumetric FEM tissue,
   fiber-driven muscle activation, emergent bulging, layered sliding
   contact. Blender's built-in Cloth/Soft Body are BANNED as the final
   solver — geometric/preview mode only, never presented as the result.

2. **Honesty clause — equal rank to Rule 1.** Never claim a quality or
   performance bar was met unless the current milestone's acceptance test
   in docs/MILESTONES.md actually passed, with the numbers to show it.
   Surface every limitation, hack, and infeasibility immediately and
   plainly, in the session summary AND in STATE.md. Overclaiming is a
   worse failure than reporting a hard problem. The user cannot verify
   physics claims independently — honest reporting is the only check
   this project has.

3. **No bundled AI.** Fascia is a deterministic harness ("hands"); the
   user's own LLM is the brain. No LLM calls, no generative AI, no API
   keys inside the software. Exception: the optional, far-future M6
   learned deformer — a small numerical approximator trained locally on
   the user's OWN simulation output, to get sim-quality results at
   interactive speed. Nothing else counts as an exception, and M6 cannot
   start before M0–M5 produce real simulation data to train on.

4. **Small distribution.** Target under 250MB total install. Heavy
   dependencies (Warp, fTetWild, IPC Toolkit) install via pip/setup
   script — never vendored into the repo. This rule can NEVER be used as
   a reason to skip a dependency the quality target actually needs.

5. **Hardware reality.** Primary dev machine is CPU-only (no NVIDIA GPU).
   Code must run correctly on Warp's CPU backend for M0–M2. From M3
   onward, provide a documented path to run the same code on a free
   Google Colab GPU runtime (a notebook that installs deps, loads the
   scene.json + anim cache, runs the solve, writes the result cache).
   Never write GPU-only code without a CPU fallback path, even a slow one.

## Engineering Rules

6. **Milestone discipline.** Work ONLY on the current milestone named in
   STATE.md. Do not skip ahead. M0 is the kill-switch: if it can't be
   made convincing, stop and say so — don't paper over it and continue.

7. **Integrate, don't reinvent.** Use NVIDIA Warp (solver), fTetWild (tet
   meshing), IPC Toolkit (contact, once reached), Alembic/MDD (caching),
   Stable Neo-Hookean material model. Building a custom tet mesher,
   contact solver, or file format needs explicit user sign-off first.

8. **Non-destructive, always.** Blender's Basis shape key is never
   mutated. Simulation results come back into Blender via cache import
   (Alembic/MDD + Mesh Cache modifier), never as per-frame shape keys.
   Preserve the existing shape-key safety logic in the current addon.

9. **LLM-drivable surface.** Every capability is a bpy.ops.fascia.*
   operator or a CLI command, with plain-English status messages and
   machine-readable output where useful. No step should require a
   viewport-only manual action with no scripted equivalent.

10. **Testable, every milestone.** A script (headless Blender or plain
    Python for the engine) must pass before a milestone is marked done.
    Golden-file tests where relevant: fixed input → output within a
    stated numeric tolerance, not "looks about right."

11. **Context-sized code.** Keep files under ~500 lines so a session can
    hold one file in full. Pin versions (Blender, Python, Warp) and
    record them in STATE.md.

## Session Protocol

- **START:** read GOAL.md → this file → STATE.md → the current
  milestone's section in docs/MILESTONES.md only. State your one
  micro-goal for this session out loud before coding.
- **END:** update STATE.md (what changed, what passed/failed with
  numbers, exact next step). Commit to git with a real message. Never
  leave the repo broken — if something doesn't work, say so in STATE.md
  rather than leaving it silently half-done.

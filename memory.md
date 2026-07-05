# Fascia Project Memory

This file is the project source of truth for future AI coding sessions.
It is public-safe: no personal names, no private paths, no API keys, no machine-specific details.

**Status: this is a v0 prototype.** Most tools are placeholders or partial. Do not overclaim it as production-quality.

---

## 1. Core Vision

Fascia is a free, open-source Blender add-on that provides the **soft-tissue layer** for creature creation — the missing piece in the open-source world.

The dream is an end-to-end creature pipeline:
- A user gives a high-level request ("make a realistic galloping Thoroughbred").
- The user's own external LLM decides which tools to call.
- Fascia provides the actual Blender tools.
- The add-on itself contains no AI model.

Fascia should be the hands, not the brain.

### The equation (the product thesis)

Think of it as **y = m · x**:
- **y** = the final result Weta/Ziva deliver (the moving, fleshy creature)
- **x** = the client's LLM (the brain — acts as the muscle TD, animator, director)
- **m** = Fascia (the hands — the Blender add-on)

So **m = y / x**: take the whole competitor deliverable, divide out everything the LLM can figure out on its own, and whatever is left is what Fascia must provide. That residual is: **soft-tissue tools + the wires that bind them to the mesh and the rig.**

In plain words: Fascia = the flesh + the wires. The LLM is the muscle TD that knows the creature's anatomy and directs the performance. Fascia is the hands that build what the LLM describes.

### Competition reality (as of 2024)

- **Ziva VFX is dead.** Unity announced April 2, 2024: no longer selling or supporting Ziva VFX, Ziva Real-Time, Ziva Face Trainer. DNEG got an exclusive perpetual license to the Ziva IP. The main buyable soft-tissue competitor no longer exists as a product.
- **Weta "Tissue" is not a product.** It is an internal tool at Weta FX. You do not buy it — you hire Weta FX the VFX house (six- to seven-figure work).
- **Neither runs in Blender.** Ziva was Maya. Weta is proprietary.
- The "free, Blender-native, LLM-driven creature soft-tissue" hole is currently unfilled.

### The competitor workflow split (who does what)

The Weta/Ziva workflow has ~7 steps. The point is to split each step into what **x** (the client's LLM) does vs what **m** (Fascia) does. Fascia does NOT rebuild Blender's existing capabilities — the LLM drives those through Blender's native operators.

| Step | Weta/Ziva human does | **x** (client LLM) | **m** (Fascia) |
|---|---|---|---|
| 1 Sculpt creature mesh | sculptor in ZBrush | picks/directs the mesh | receives the mesh, tags it as base |
| 2 Skeleton + rig | rigger | drives Blender's native rigging via Blender's own operators | **binds tissue to the rig** (landmarks follow bones) — MISSING |
| 3 Place muscles by hand | muscle TD (scarce role) | defines the creature's anatomy (landmarks, muscles, attachments) | places them + gives them volume |
| 4 Fascia/fat/skin layers | TD wraps them | directs the layers | builds the layers |
| 5 Animate the gait | animator | decides the gait | keyframes it |
| 6 FEM physics sim | sim TD, hours of compute | decides intensity | runs geometric contraction (APPROXIMATION, not FEM) |
| 7 Bake + render | sim cache | picks frames | bakes shape keys |

Step 2 is split: **building** the rig is Blender's job (LLM drives it via native operators); **binding** Fascia's tissue to that rig is Fascia's job and is currently missing. A landmark that floats when the skeleton moves is the bug this binding fixes.

### The missing thing (named, finally)

For x to be the muscle TD (step 3), x has to be able to *tell m what the creature's anatomy is* — "place a landmark called CranialRidge here, place a muscle from CranialRidge to ScapulaTop with this thickness." Today m cannot accept that input. `place_landmarks` and `generate_muscles` read hardcoded `HORSE_LANDMARKS` / `HORSE_MUSCLES` tables and take zero anatomy input. There is no front door for the LLM to hand in an alien's anatomy.

This is two layered gaps:
1. **Anatomy input** — tools must accept an anatomy definition as a parameter (the LLM as TD). Today: impossible. Missing half.
2. **Action input** — "flex this muscle by 0.6, simulate 60 frames, bake" (the LLM as animator). Today: half-works, horse-only, not callable from outside Blender.

The harness isn't only "LLM calls tools." It's "LLM defines the creature, then Fascia builds it."

### Honest physics caveat

Fascia's contraction is **geometric and volume-preserving**, not an FEM physics solve. It shortens + bulges by formula (`L·(1−c)`, `r/√(1−c)`). It looks plausible; it is not a simulation. Never claim parity with Weta/Ziva's FEM. Step 6 is the one place Fascia approximates rather than matches. Be honest about this in code, docs, and status messages.

## 2. What Fascia Is NOT

- **Not a mesh generator.** Not Rodin, not Meshy. The base mesh comes from outside (the user, the LLM, or another tool).
- **Not an LLM.** No brain inside. External LLMs may drive Fascia later, but only by calling tools.
- **Not a rigging tool.** Rigging (skeleton + joints) is Blender's job. Fascia sits on top of a rigged mesh.
- **Not the Blender AI agent.** The agent dream is real but is a separate project. Do not build agent features inside Fascia. If the user asks for agent features, remind them: that is the agent's job, not Fascia's.

## 3. Hard Design Rules

1. No AI lives inside Fascia.
2. External LLMs may drive Fascia later, but only by calling tools.
3. Each tool should do one clear job.
4. Tools should report short plain-English status messages.
5. Never return raw mesh or vertex dumps to an LLM-facing tool.
6. Do not overclaim placeholder code as real anatomy, real simulation, or production physics.
7. Keep public files free of personal/private information.
8. Fascia receives meshes, it does not generate them. Tool 1 should accept a base mesh, not create one from scratch. (A placeholder generator is fine for testing only.)
9. **Stay on target.** The goal is to build the TOOL, not to tune one specific test mesh. If you are spending tokens adjusting landmark positions on one specific horse, you are doing the wrong job. Build the tool that places landmarks correctly on ANY mesh. The horse is a test case, not the deliverable.

## 4. Current Code State

`fascia_addon.py` is a working **v0 prototype** — a single ~1700-line file. All nine tools exist and connect. The pipeline is visible end-to-end. The critical "wires" are in place: anatomy input slot (Spec 6), rig binding (Spec 7), muscle insertion tracking (Spec 8), and LLM-facing surface (Spec 9). The remaining work is tissue-math refinements (antagonist pairing, skin sliding, performance) and production hardening.

### The Nine Tools

| # | Tool | Status | Notes |
|---|------|--------|-------|
| 1 | Load Horse Base | Placeholder + "Use Selected as Base" | Old button creates a blob (two spheres). The "Use Selected as Base" button lets the user tag any mesh as the base — that is the real direction. |
| 2 | Customize Sliders | Placeholder | Age/Fat/Color affect object scale and viewport color. No operator — driven by slider callbacks. |
| 3 | Place Landmarks | Real | Positions are normalized (0-1) UVW and map to the base mesh's bounding box. Works on any mesh. Accepts anatomy from file (Spec 6), inline JSON (Spec 9), or embedded horse data. Landmarks can be bone-parented to a rig (Spec 7). Pose-dependent: correct for a standing four-square pose, off on extreme poses (grazing/rearing/galloping) — documented bounding-box limitation. |
| 4 | Generate Muscles | Real (mesh-agnostic sizing, pinned origin, insertion tracking) | Creates stretched spheres between landmarks. Radii + influence radius scale with base mesh size (Spec 2). Origin end pinned at `from` landmark (Spec 4). Contraction is volume-preserving (Spec 3). Muscle reorients toward the insertion landmark via Damped Track constraint (Spec 8). Accepts anatomy from file, inline JSON, or embedded (Spec 6/9). |
| 5 | Bind Skin to Muscles | Working, safe | Flex slider SHORTENS muscles (local Z) and BULGES thickness (local X/Y) by `1/√(1−c)`, preserving volume. Origin end stays pinned; insertion shortens toward origin along the Damped-Track-reoriented direction. Per-muscle recruitment multiplier (Spec 5). Skin-push center tracks the flexed belly. Skin-push axis follows the Damped Track rotation (Spec 7 flex fix). Pushes nearby skin vertices with distance falloff. Shape-key-safe (see section 5). |
| 6 | Simulate Motion | v0 placeholder | Keyframes flex value over 60 frames. Not real physics. Checks that muscles exist before running. |
| 7 | Bake Result | v0, fixed | Samples the flex animation into `Baked_Frame_NNN` shape keys. Capture order fixed (captures flexed pose before creating Basis). Checks that muscles exist before running. |
| 8 | Bind/Clear Rig (Spec 7) | Real | Operators `fascia.bind_landmarks_to_rig` and `fascia.clear_rig_binding`. Auto-binds each landmark to the nearest bone, or uses explicit `fascia_bone`. Clear restores mesh-parenting. The chain: bone → landmark (bone parent) → muscle (object parent) → skin bulge (depsgraph-evaluated). |
| 9 | Status Query (Spec 9) | Real | Operator `fascia.get_status` returns a short plain-English summary (base, species, landmark/muscle counts, rig, flex). LLM-facing; no mesh data (rule 5). |

### What is real vs. placeholder

**Real / working:**
- Sidebar panel, placeholder horse creation, age/fat/color sliders.
- Normalized landmark placement (mesh-agnostic, real-horse proportions).
- Mesh-agnostic muscle sizing (fractions of base bounding box).
- Volume-preserving muscle contraction (shorten + bulge, `V = π·r²·L` constant).
- Flex slider skin deformation with shape-key safety and drift-free restore.
- 60-frame test motion + shape-key baking.
- Species-definition files for any creature's anatomy (Spec 6).
- Rig binding: bone-parented landmarks + muscle-to-landmark parenting (Spec 7).
- Muscle insertion tracking: Damped Track reorients muscle toward insertion landmark (Spec 8).
- LLM-facing surface: inline `fascia_species_json` property + `fascia.get_status` operator (Spec 9).

**Placeholder / not real yet:**
- No real horse base mesh or skeleton.
- No real soft-body / FEM / SOFA physics.
- No true automatic creature generation.
- No built-in LLM or AI assistant.
- No production-ready Weta/Ziva-level tissue system.
- The Damped Track fixes the direction toward the insertion landmark, but the far end is at `rest_length·ls` — it does not stretch to exactly reach the insertion (geometric length mismatch remains, Spec 4 §2).
- Per-muscle recruitment controls exist (Spec 5) but no antagonist pairing yet.
- Radial skin push only (no tangential skin sliding).

## 5. Shape Key Safety Rules

The code uses `Basis`, `Live_Flex`, and baked frame shape keys. These rules are critical — violating them corrupts the Basis.

- Do not write flexed results into `Basis`.
- If `Live_Flex` exists, live deformation goes there.
- Baked results go into separate shape keys (`Baked_Frame_NNN`).
- When shape keys exist, NEVER write to `mesh.vertices` — that is the Basis.
- The backup system (`_original_verts`) is only used before shape keys exist. It has a topology-change guard (vertex-count check) but no shape-key topology-change guard.
- If you add shape key operations, always capture flexed data BEFORE creating or modifying Basis.

## 6. Known Limitations & Messy Code

Known scope limits (documented in code comments — these are honest boundaries, not bugs):
- **Muscle reorients toward insertion but does not stretch to reach it.** Spec 8 adds a Damped Track constraint so the muscle's local +Z points at the insertion landmark (fixing the "wrong angle" from Spec 7 §7). However the far end is at `rest_length·ls` along that direction — it does NOT stretch to exactly reach the insertion. If the insertion moves closer than `rest_length·ls`, the far end overshoots; if farther, it undershoots. This is the pre-existing Spec 4 §2 "insertion length mismatch" — Spec 8 narrowed it from "gap + wrong angle" to "length mismatch only."
- **Radial skin push only:** axial shortening does not directly deform the skin. Skin slides tangentially over tissue as a future refinement.
- **Per-muscle recruitment exists (Spec 5); antagonist pairing does not.**
- **No antagonist relaxation.**

Minor code smells (safe to leave, not urgent):
- `update_horse(None, context)` and `update_flex(None, context)` pass None as self — works but is a code smell.
- Redundant `update_flex` call in `simulate_motion`: setting `scene.fascia_flex` already triggers the property update callback.
- `scene["_fascia_flex_affected"]` is an unregistered ID property, inconsistent with the registered `fascia_*` properties.
- No topology-change detection for the shape-key path (only the no-shape-keys backup path is guarded).

## 7. Test Mesh

A real horse mesh (imported from a free Sketchfab asset) is used as a TEST CASE only. It was rotated so length is along X, scaled to ~3.6 units, joined into one object, and tagged with `fascia_role = "skin"`.

**Important:** This mesh is in a dynamic pose (head down, croup high), so 6 dorsal/head landmarks (Withers, MidBack, ScapulaTop×2, Poll, NuchalCrest) float in air on THIS mesh only. That is the documented POSE ASSUMPTION limitation — the normalized values are provably correct for any standing four-square horse. Do NOT retune the data to fix it on this dynamic-pose mesh. Full standing-pose verification is deferred (low priority).

Per rule 9: do not spend tokens tuning the tool to this specific mesh. The tool must work on ANY horse mesh.

## 8. Completed Specs

- **Spec 1 — Landmark proportions (DONE):** All `HORSE_LANDMARKS` `pos` values retuned to real-horse proportions. Verified via BVH surface-proximity. `specs/01_landmark_proportions.md`.
- **Spec 2 — Mesh-agnostic muscles (DONE):** `influence_radius`, all `HORSE_MUSCLES` radii, and stored `fascia_radius` converted to fractions of the base mesh's longest bounding-box side; scaled at runtime via `_get_base_size`. Behaviour-preserving on the 3.6-unit mesh. `specs/02_mesh_agnostic_muscles.md`.
- **Spec 3 — Volume-preserving contraction (DONE):** Flex slider now SHORTENS muscles (local Z) and BULGES thickness (local X/Y) by `1/√(1−c)`, preserving volume. Verified: at flex=1, scale=(1.1547, 1.1547, 0.75), volume product=1.0. Skin push is now the physical bulge, not a heuristic. `specs/03_volume_preserving_contraction.md`.
- **Spec 4 — Pin muscle attachments (DONE):** Muscle object origin moved from midpoint to the `from` landmark (anatomical origin); geometry offset to local Z ∈ [0, +length]. At flex=1 the origin end stays exactly on its landmark (distance 0.0); the insertion end pulls in by exactly 25% of rest length. Volume product stays 1.0. At-rest appearance identical to pre-change (both endpoints on landmarks, distance 0.0). `fascia_rest_length` stored per muscle; skin-push center tracks the flexed belly. Verified on GluteusMedius_R, Triceps_L, LongissimusDorsi. `specs/04_pin_muscle_attachments.md`.
- **Spec 5 — Per-muscle contraction controls (DONE):** Added `FasciaMuscleRecruitment` PropertyGroup + `Scene.fascia_recruitment` CollectionProperty + UIList in panel. Each muscle gets a recruitment multiplier (0.0–2.0, default 1.0): `c_i = flex * MAX_CONTRACTION * recruitment_i`. Per-muscle `ls_i`/`ts_i` feed both the scale assignment and the skin-push center/growth. Recruitment preserved across muscle regeneration (matched by name). Empty collection = uniform (backwards-compatible). Verified: r=0 → scale (1,1,1) vol 1.0; r=1 → (1.1547, 1.1547, 0.75) vol 1.0; r=2 → (1.4142, 1.4142, 0.5) vol 1.0. Architect fixed a double-registration bug (PropertyGroup was both in `classes` tuple AND explicitly `register_class`'d — removed the redundant explicit calls). `specs/05_per_muscle_contraction_controls.md`.
- **Spec 6 — Anatomy input slot (DONE):** Hardcoded `HORSE_LANDMARKS`/`HORSE_MUSCLES` extracted into loadable `species/equine_horse.json` file. New `Scene.fascia_species_path` string property (FILE_PATH subtype) selects a species file; empty = use embedded horse data. New `_load_species()` helper validates and returns landmark/muscle dicts. Both `place_landmarks` and `generate_muscles` fall back to embedded data when the path is empty or the file fails to load. `species/equine_horse.json` is an exact mirror of the embedded horse data. `specs/06_anatomy_input_slot.md`.
- **Spec 7 — Rig binding (DONE):** Landmarks bone-parent to armature bones via `parent_set(type='BONE', keep_transform=True)` with `armature.data.bones.active` set. New `fascia_armature` PointerProperty (poll: ARMATURE type), operators `fascia.bind_landmarks_to_rig` (auto-bind or explicit via `fascia_bone`) and `fascia.clear_rig_binding` (restores mesh-parenting). Muscles parented to their origin landmark at generation time via `_object_parent_object()`. Flex code fixed: reads world rotation from `matrix_world.to_quaternion()` instead of `rotation_quaternion`; `context.view_layer.update()` before reading parented transforms. Panel has a new Rig section. All 10 edits verified: 29/29 landmarks bound, world positions preserved, bone→landmark→muscle→skin chain verified, volume preservation unchanged (1.0), clear binding restores default state. `specs/07_rig_binding.md`.
- **Spec 8 — Muscle insertion tracking (DONE):** `DAMPED_TRACK` constraint added on each muscle targeting its insertion landmark at generation time. New `_add_insertion_track_constraint()` helper (rotation-only — does NOT affect `obj.scale`, so volume preservation is untouched). Two call sites in `generate_muscles` (bilateral + midline branches), one line each after the existing Spec 7 `_object_parent_object()` call. The Spec 7 flex fix (`matrix_world.to_quaternion()` + depsgraph update) already covers constraint-evaluated rotation, so `update_flex` needed zero changes. Updated KNOWN LIMITATION comment in `create_muscle_mesh` (Spec 4 §2 narrowed from "gap + wrong angle" to "length mismatch only"). All 8 verification checks passed: at-rest identical, all 29 muscles have constraint, reorients on insertion move (4.24° for 30° bone rotation), origin stays pinned (drift=0.0), volume preserved (1.0), skin-push axis aligns to insertion direction (7e-8 error), clear binding compatible, far end tracks direction (error=0.0). `specs/08_muscle_insertion_tracking.md`.
- **Spec 9 — LLM-facing surface (DONE):** New `Scene.fascia_species_json` StringProperty so an external LLM can pass anatomy inline without writing a file to disk. New `_load_species_json()` helper — same schema and return contract as `_load_species` (Spec 6), but operates on a JSON string instead of a file path. Three-tier species resolution in both `place_landmarks` and `generate_muscles`: file path (Spec 6) → inline JSON string (Spec 9) → embedded horse data. New `FASCIA_OT_get_status` operator (`fascia.get_status`) returns a short plain-English summary string via `self.report()` — no mesh data. All 8 verification checks passed: property exists, inline JSON overrides embedded (3 landmarks, 2 muscles for Alien), file beats JSON string (29 landmarks, 29 muscles), invalid JSON falls back gracefully, empty+empty=embedded horse (no-regression), status query works with and without a base mesh. `specs/09_llm_facing_surface.md`.

## 9. Agentic Engineering Workflow

Fascia development follows **Kun Chen's Agentic Engineering Workflow** (see `AGENTS.md` "Session Workflow" section for detailed agent instructions):

### Flow (Captain → Agent → Tools)

```
You (Captain) — decides WHAT, reviews, approves specs
  └── AI Agent — reads AGENTS.md, follows session workflow
        ├── Spec-driven dev (specs/ + .agents/skills/spec-driven-dev/)
        ├── treehouse get — isolated worktree for every change
        ├── git push no-mistakes — automated validation before PR
        └── gnhf "task" — overnight autonomous iteration
```

### Tools we use (all open-source by Kun Chen)
| Tool | Purpose | Install |
|------|---------|---------|
| `gh-axi` | GitHub operations (issues, PRs) | `npm install -g gh-axi` |
| `lavish-axi` | Visual HTML planning with agents | `npm install -g lavish-axi` |
| `treehouse` | Isolated git worktrees | `irm .../treehouse/install.ps1 \| iex` |
| `no-mistakes` | Automated code review pipeline | `irm .../no-mistakes/install.ps1 \| iex` |
| `gnhf` | Overnight autonomous loop | `npm install -g gnhf` |

### Session checklist (every time you start work)
1. Check `git status` and `git log --oneline -5`
2. Review any open specs in `specs/`
3. State your goal — I'll load the right skill and follow the workflow

### Missing piece: firstmate (NOW UNBLOCKED)
Kun's full stack includes `firstmate` — an orchestrator that spawns parallel crewmates in tmux panes. We now have **psmux** (native Windows tmux replacement, v3.3.6 — `winget install psmux`), which responds as `tmux` and supports 83 tmux commands. Firstmate also needs bash (we have it via WSL). Setting up firstmate is doable but needs careful config — see AGENTS.md "Session Workflow > Note on firstmate" for details.

## 10. Next Sensible Work

**The critical "wires" are complete.** The chain is fully connected: brain → anatomy → landmarks → rig → muscles → insertion → skin. The remaining work is refinements on top of a working pipeline.

### Tissue-math refinements (next priority)

1. **Antagonist muscle pairing** — when one muscle contracts, its antagonist relaxes. Now fully unblocked: per-muscle recruitment (Spec 5), rig binding (Spec 7), muscle insertion tracking (Spec 8), and LLM-facing surface (Spec 9) are all in place. The LLM can define pairing data; the flex loop auto-relaxes paired muscles. This is the highest-impact tissue-math improvement.
2. **Skin sliding** — skin moves tangentially over tissue, not just pushed radially. The real differentiator vs. Weta/Ziva. Depends on real muscle bulges (done, Spec 3), correct axial motion (done, Spec 4), and correct muscle direction (done, Spec 8). Unblocked for single-bone tests.
3. **`update_flex` performance** — the skin-push loop is pure Python and times out on the 748k-vertex test mesh at flex>0. Needs spatial acceleration (BVH or kdtree) or a GPU/geometry-nodes approach. Becoming a practical blocker for skin sliding tests on real meshes.
4. **Standing-pose test mesh** for full landmark verification.
5. **Split `fascia_addon.py` into modules** (`landmarks.py`, `muscles.py`, `flex.py`, `panel.py`, `__init__.py`) — only when parallel editing becomes a bottleneck. Not urgent.
6. **Fascia MCP bridge** — optional follow-on to Spec 9. Register dedicated MCP tools wrapping `bpy.ops.fascia.*` so they appear as first-class MCP tools rather than raw Python calls. Separate addon potential; out of scope for the core Fascia add-on.

### What the wires now enable

Any external LLM using the Blender MCP server can now:
- Define a creature's anatomy inline (`scene.fascia_species_json = '{...}'`) without writing a file.
- Place landmarks, generate muscles, bind to a rig, flex, simulate, and bake — all via `bpy.ops.fascia.*`.
- Query the current state with `bpy.ops.fascia.get_status()`.
- Pass any alien anatomy; the tools accept it without modification (rule 11).
- Trust that the bone → landmark → muscle → skin chain is complete on both ends (origin pinned, insertion tracked by Damped Track).

Do not try to do everything at once. The tissue math builds on the wires; polish the wires first when gaps appear.

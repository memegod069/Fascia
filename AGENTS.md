Note: for the standalone FEM simulation engine (separate from the
Blender addon), also read AGENTS_ENGINE.md.

# Fascia — Creature Soft-Tissue Toolbox for Blender

This file is the source of truth for AI coding agents working on Fascia.
It is safe for public repos: no personal names, no private paths, no API keys.

## Project Identity

Fascia is a Blender add-on (target: 4.0+) that provides the **soft-tissue layer** for creature creation — muscles, fascia, fat, and skin on top of a rigged mesh. It is **not** an AI model, not a mesh generator, and not a rigging tool. External LLMs may drive its tools but only by calling them. Fascia is the hands, not the brain.

### Product Thesis (the equation)

Fascia is a **harness**: the client brings their own LLM, Fascia provides the Blender tools that LLM drives to build a creature. The target deliverable is what Weta "Tissue" / Ziva VFX produce — a moving, fleshy creature — but free, Blender-native, and LLM-driven.

Think of it as **y = m · x**:
- **y** = the final result Weta/Ziva deliver (the moving, fleshy creature)
- **x** = the client's LLM (the brain — acts as the muscle TD, animator, director)
- **m** = Fascia (the hands)

So **m = y / x**: take the whole competitor deliverable, divide out everything the LLM can figure out on its own, and whatever is left is what Fascia must provide. That residual is: **soft-tissue tools + the wires that bind them to the mesh and the rig.**

Competition reality (as of 2024): Ziva VFX is dead — Unity stopped selling/supporting it (DNEG got an exclusive IP license). Weta "Tissue" is not a product — it is an internal tool at Weta FX; you hire the VFX house. Neither runs in Blender. The "free, Blender-native, LLM-driven creature soft-tissue" hole is currently unfilled.

### What Fascia owns vs what the LLM drives through Blender

The Weta/Ziva workflow has ~7 steps. Fascia does NOT rebuild Blender's existing capabilities (mesh sculpting, bone rigging). The LLM drives those through Blender's native operators. Fascia fills the one gap Blender does not have — flesh, fascia, fat, skin, contraction — and wires that flesh to the mesh and the skeleton.

- Mesh + skeleton + rig → LLM drives Blender's native tools. Not Fascia.
- Soft-tissue layers + contraction + baking → Fascia.
- **Bindings** (landmarks follow bones; tools accept anatomy as input) → Fascia. Currently missing. On the critical path.

### Honest physics caveat

Fascia's contraction is **geometric and volume-preserving**, not an FEM physics solve. It shortens + bulges by formula. It looks plausible; it is not a simulation. Never claim parity with Weta/Ziva's FEM. Step 6 of the competitor workflow (real FEM sim) is the one place Fascia approximates rather than matches.

Single-file add-on: `fascia_addon.py` (~1268 lines). The `register()` entry point (line 1172) registers all operators, panels, and Scene properties. The `unregister()` entry point (line 1246) reverses each registration in the correct order.

## Hard Design Rules

**NON-NEGOTIABLE QUALITY TARGET (Read Before Everything Else)**

We are not building approximations. We are building m such that y = m · x reaches full Weta Tissue or Red Dead Redemption 2 level quality and performance.

- Visual fidelity, believable dynamics, skin/muscle/fat behavior, and production performance are non-negotiable.
- Geometric tricks, simplified volume math, or "good enough for now" solutions are temporary only.
- Every agent must reject any proposal that compromises on matching the reference quality.

If a design cannot deliver Weta/RDR results, redesign it. Do not simplify the target.

**Read also:** `docs/project-vision-and-motivation.md` — this file contains the creator’s own words about why the project exists and the strong “no compromise on quality” stance expressed in this project’s development.

1. No AI lives inside Fascia.
2. External LLMs may drive Fascia later, but only by calling tools.
3. Each tool should do one clear job.
4. Tools should report short plain-English status messages.
5. Never return raw mesh or vertex dumps to an LLM-facing tool.
6. Do not overclaim placeholder code as real anatomy, real simulation, or production physics — but always keep the long-term target in mind (full quality).
7. Keep public files free of personal/private information.
8. Fascia receives meshes, it does not generate them. Tool 1 should accept a base mesh, not create one from scratch. The placeholder generator is for testing only.
9. **Build the tool, not the horse.** The horse is a test case, not the deliverable. But the tool must be capable of producing horse-level (Weta/RDR) results.
10. **Fascia is the flesh + the wires.** Do not rebuild what Blender already has (mesh sculpting, bone rigging, weight painting). The LLM drives those through Blender's native operators. Fascia fills the soft-tissue gap and wires it to the mesh and rig — at full quality.
11. **The LLM is the muscle TD.** Fascia's tools must accept anatomy (landmarks, muscles, attachments) as input — not read hardcoded horse tables forever. The horse is the first data file, not the only one. If a tool cannot accept an alien's anatomy, it is not done.
12. **Landmarks must bind to the rig.** A landmark that floats when the skeleton moves is a bug to fix, not a limitation to document forever. Bone moves → landmark moves → muscle follows → skin deforms. The rig binding is Fascia's job.
13. **Never settle for geometric-only solutions.** Current contraction uses volume-preserving math as a stepping stone. The direction must advance toward methods that can deliver real high-fidelity physics behavior matching Weta and RDR references.

## Commands & Testing

There is no test framework yet. Run Blender manually, enable the add-on, and test each tool:
1. **Tool 1:** Click "Make Placeholder Horse" or select a mesh + "Use Selected as Base"
2. **Tool 3:** Click "Place Landmarks" — 19 landmarks should appear as yellow sphere empties
3. **Tool 4:** Click "Generate Muscles" — 15 muscle types (29 instances with bilateral) should appear
4. **Tool 5:** Drag "Flex" slider — muscles shorten/bulge, skin deforms
5. **Tool 6:** Click "Simulate Motion" — 60-frame test animation
6. **Tool 7:** Click "Bake Result" — shape keys created for 12 sampled frames

Register/unregister: `fascia_addon.py` is loaded as a Blender add-on. Test with `bpy.ops.script.reload()` or restart Blender.

## Architecture

### File structure
```
.agents/
  skills/
    spec-driven-dev/     spec-first feature development
    skill_creator/       create new skills interactively
    roadmap_manager/     auto-update memory.md on completion
fascia_addon.py          single-file add-on
memory.md                project source of truth (for AI sessions)
species/                  species-definition JSON files (first: horse)
specs/                    completed feature specifications
  01_landmark_proportions.md
  02_mesh_agnostic_muscles.md
  03_volume_preserving_contraction.md
  04_pin_muscle_attachments.md
  05_per_muscle_contraction_controls.md
  06_anatomy_input_slot.md
```

### Add-on structure
- **`register()`** — registers all classes in the `classes` tuple, then registers Scene properties (fascia_age, fascia_fat, fascia_color, fascia_flex, fascia_recruitment, fascia_recruitment_index)
- **`unregister()`** — deletes CollectionProperty/IntProperty BEFORE unregistering PropertyGroup, then unregisters classes, then deletes remaining Scene properties
- **Classes tuple** (line 1159) — all 9 classes must be listed. Registration order matters: PropertyGroup before UIList before Operators before Panel

### Registration order rules (critical)
1. `FasciaMuscleRecruitment` (PropertyGroup) must be registered BEFORE `FASCIA_UL_recruitment` (UIList) because the UIList references the PropertyGroup type
2. `fascia_recruitment` (CollectionProperty) and `fascia_recruitment_index` (IntProperty) are registered AFTER the classes tuple — they are NOT in the classes tuple but ARE registered in register()
3. Unregistration reverses: first delete the IntProperty, then delete the CollectionProperty, then unregister classes (which unregisters the PropertyGroup). Deleting properties before the PropertyGroup avoids dangling type references

### The seven tools
| # | Tool | Operator | Key details |
|---|------|----------|-------------|
| 1 | Load Horse Base / Use Selected as Base | `fascia.make_placeholder_horse` / `fascia.use_selected_as_base` | Placeholder creates 2 UV spheres. "Use Selected" tags any mesh with `fascia_role = "skin"` |
| 2 | Customize Sliders | Callbacks on Scene properties | Age/Fat/Color change object scale and viewport color. Only affects placeholder objects |
| 3 | Place Landmarks | `fascia.place_landmarks` | 19 landmarks defined in `HORSE_LANDMARKS`. Positions are normalized UVW (0-1) mapped to bounding box. Bilateral = mirrored left/right. All parented to base mesh |
| 4 | Generate Muscles | `fascia.generate_muscles` | 15 muscle types in `HORSE_MUSCLES` (29 instances with bilateral). Radii are fractions of base mesh longest bounding-box side. Origin pinned at `from` landmark. Per-muscle recruitment preserved across regeneration |
| 5 | Bind Skin (Flex) | Callback on `fascia_flex` | Volume-preserving contraction: L*(1-c), r/sqrt(1-c). Per-muscle recruitment: c_i = flex * MAX_CONTRACTION * recruitment_i. Skin push with distance falloff. Shape-key-safe |
| 6 | Simulate Motion | `fascia.simulate_motion` | Keyframes flex at frames 1/15/30/45/60: values 0/1/0/1/0 |
| 7 | Bake Result | `fascia.bake_flex_pose` | Samples 12 frames into Baked_Frame_NNN shape keys. Must capture flexed data BEFORE creating Basis |

### Shape Key Safety (CRITICAL — violating these corrupts Basis)
- Do not write flexed results into `Basis`
- If `Live_Flex` exists, live deformation goes there
- Baked results go into separate shape keys (`Baked_Frame_NNN`)
- When shape keys exist, NEVER write to `mesh.vertices` — that is the Basis
- The backup system (`_original_verts`) is only used before shape keys exist
- Always capture flexed data BEFORE creating or modifying Basis

### Muscle contraction math
- `MAX_CONTRACTION = 0.25` (25% max shortening)
- `c_i = flex * 0.25 * recruitment_i`
- `ls_i = 1.0 - c_i` (length scale)
- `ts_i = 1.0 / sqrt(ls_i)` (thickness scale = bulge)
- Volume: `pi * r^2 * L * ls_i * ts_i^2 = pi * r^2 * L * (1-c) / (1-c) = pi * r^2 * L` (preserved)

### Key constants
- `MUSCLE_INFLUENCE_FRACTION = 0.083` — skin-bulge influence radius as fraction of base size
- `MAX_CONTRACTION = 0.25` — maximum fractional shortening

### Known limitations (documented, not bugs)
- Insertion shortens toward pinned origin, leaving a gap at insertion landmark (needs rig-driven landmarks)
- No antagonist pairing (future work)
- Radial skin push only, no tangential skin sliding
- Skin-push loop is pure Python — performance issue on high-vertex meshes
- Landmarks assume standing four-square pose; extreme poses misplace landmarks
- No recruitment animation (values are static, not keyframed)

## Session Workflow — Agentic Engineering (Kun Chen's Method)

This section defines how every coding session runs. Read it at session start and follow it step by step.

### Phase 0: Session Start
1. Read `AGENTS.md`, `captain.md`, `learnings.md` — done (you're reading this)
2. Check `specs/` for any existing specs that relate to the current task
3. Check git status: `git status`, `git log --oneline -5`

### Phase 1: Plan Before Code (spec-driven)
1. If the task needs a new feature or significant change, write a spec first
2. Load the `spec-driven-dev` skill: read `.agents/skills/spec-driven-dev/SKILL.md` and follow it
3. If the user wants to create a new reusable workflow (skill), load `skill_creator` instead: read `.agents/skills/skill_creator/SKILL.md` and follow its interview process
4. Present the spec to the captain for approval
5. For complex multi-step plans, use `lavish-axi` to create a visual HTML plan

### Phase 2: Isolated Work
1. Run `treehouse get` to enter an isolated worktree — this prevents conflicts with other work
2. Make changes inside the worktree
3. Run `exit` when done — worktree returns to pool
4. Or use `treehouse get --lease` for persistent worktrees

### Phase 3: Validate Before Merge
1. **Local validation:** Run through the spec's verification criteria. Test in Blender manually.
2. **Gate validation:** `git push no-mistakes <branch>` — automated review pipeline:
   - AI reviews code for bugs, shape-key safety, registration order
   - Runs linting and convention checks
   - Applies safe fixes automatically
   - Escalates risky findings to the captain
   - Opens a clean PR once all checks pass

### Phase 4: Compound Progress (overnight + parallel)
For repetitive or iterative tasks:
1. Use `gnhf "task description"` to run an autonomous loop overnight
2. Each iteration commits one improvement, resets on failures
3. Wake up to a branch of working code with full change log

For parallelizable work (independent specs, multiple species files, unrelated features):
4. Use the `task` tool to launch subagents — each runs in its own context, returns when done
5. Launch multiple `task` calls in a single message to run them concurrently
6. Each subagent should: `treehouse get` → implement → verify → `git push no-mistakes`
7. Example: "Implement specs 06, 07, 08 in parallel" → 3 task calls in one message

### Phase 5: Update Memory
After completing work:
1. Load the `roadmap_manager` skill: read `.agents/skills/roadmap_manager/SKILL.md` and follow it to update `memory.md`
2. Add any new gotchas or discoveries to `learnings.md` (dated entry)
3. If the work changed project conventions, update `AGENTS.md` accordingly

### Available Tools
| Tool | Command | When to use |
|------|---------|-------------|
| gh-axi | `gh-axi issue`, `gh-axi pr view`, etc. | All GitHub operations (agent-friendly output) |
| lavish-axi | `lavish-axi` | Complex planning that needs visual review |
| treehouse | `treehouse get` / `treehouse get --lease` | Isolated development in clean worktrees |
| no-mistakes | `git push no-mistakes <branch>` | Validate and gate every change before merge |
| gnhf | `gnhf "task"` | Overnight autonomous iterations |
| `task` tool | Launch subagents via opencode | Parallel execution of independent tasks (replaces firstmate on Windows) |
| spec-driven-dev | Load skill via `.agents/skills/spec-driven-dev/SKILL.md` | Feature development — spec first, implement second |
| skill_creator | Load skill via `.agents/skills/skill_creator/SKILL.md` | Create a new reusable workflow (skill) |
| roadmap_manager | Load skill via `.agents/skills/roadmap_manager/SKILL.md` | Auto-update memory.md on task completion |

### Note on parallelism (replaces firstmate)
Kun's full stack uses `firstmate` (an orchestrator that spawns crewmates in tmux panes). On Windows, we **skip firstmate** and use opencode's built-in `task` tool instead — it launches subagents within the current session, no tmux or terminal multiplexer needed. Each subagent gets its own context, runs `treehouse get` for isolation, and returns when done. Launch multiple `task` calls in a single message for true parallelism. This covers the same ground as firstmate (parallel agents, isolated worktrees, automated validation) without the Windows/tmux/bash complexity.

## Conventions
- Single-file add-on (module split deferred until parallel editing is a bottleneck)
- All imports: `bpy`, `bmesh`, `mathutils` only (no external dependencies)
- Property naming: `fascia_` prefix for all custom properties
- Object naming: `Fascia_` prefix for all add-on objects
- Custom properties used for metadata: `fascia_role`, `fascia_type`, `fascia_muscle_name`, `fascia_origin`, `fascia_insertion`, `fascia_radius`, `fascia_rest_length`, `fascia_region`, `fascia_landmark`, `fascia_side`
- When adding new operators: add to both `classes` tuple and to the panel's `draw()` method
- When adding new Scene properties: register in `register()`, unregister in `unregister()`
- When modifying landmark/muscle data: update the definitions, not the specs (specs are post-hoc documentation)
- Comment style: explanatory paragraphs, not inline annotations

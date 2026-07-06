# Fascia Repository — Comprehensive Improvement Plan

**Prepared:** 2026-07-06 | **Branch:** `issues-1-and-11` | **Target:** 3.8/10 → 7+/10

---

## MANDATORY READING BEFORE ANY WORK

Read these files IN FULL before touching a single line of code:

1. `AGENTS.md` — hard design rules, shape-key safety, registration order, session workflow
2. `captain.md` — code style, quality bar
3. `learnings.md` — hard-won Blender gotchas (PropertyGroup order, bone parenting, KDTree unpack)
4. `memory.md` — full project state, all 12 specs, known limitations
5. `issues.md` — 21 QA issues with severity, line numbers, and suggested fixes
6. `fascia_addon.py` — the full 1906-line addon

**NEVER violate these rules:**
- Shape key safety: NEVER write to `mesh.vertices` when shape keys exist. Write only to `Live_Flex` (live) or `Baked_Frame_NNN` (baked). Capture flexed data BEFORE creating/modifying Basis.
- Registration order: `FasciaMuscleRecruitment` before `FASCIA_UL_recruitment` in classes tuple. CollectionProperty + IntProperty registered AFTER classes tuple, deleted BEFORE unregistering classes.
- New operators: add to BOTH `classes` tuple AND panel `draw()`.
- New Scene properties: add to BOTH `register()` AND `unregister()`.
- Use explanatory paragraph comments, not inline annotations.

---

## ALREADY DONE (do not redo)

- `LICENSE` — MIT created
- `.gitignore` — expanded version created
- Issues 1 & 11 — already fixed in `fascia_addon.py` (commits `506e5d9`, `e9cdc4a`)

---

## PHASE 1 — OSS FOUNDATION (pure file creation, zero risk)

### 1.1 Rewrite `README.md` (overwrite entirely)

Full content:

```markdown
# Fascia

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B-orange.svg)](https://www.blender.org/)
[![Status: Work in Progress](https://img.shields.io/badge/status-work%20in%20progress-red.svg)]()

**Fascia** is a free, open-source Blender add-on that provides the **soft-tissue layer**
for creature creation — muscles, fascia, fat, and skin binding on top of a rigged mesh.

> **Honest status:** Working prototype, not production. Core pipeline works end-to-end.
> Known limitations documented below.

## What Fascia Is

- A **toolbox** — each tool does one job, reports a plain-English status message.
- A **harness for LLMs** — external AI defines any creature's anatomy as JSON and drives
  all tools via `bpy.ops.fascia.*`. Fascia is the hands; the LLM is the brain.
- **Blender-native** — no proprietary tools needed (Ziva VFX discontinued; Weta Tissue
  is an internal-only VFX house tool, not a product).

## What Fascia Is NOT

- **Not an AI model** — no LLM inside the add-on.
- **Not a mesh generator** — bring your own creature mesh.
- **Not a rigging tool** — rigging is Blender's job.
- **Not real FEM physics** — contraction is geometric and volume-preserving by formula,
  not a physics simulation. Documented honestly throughout.

---

## Installation

### Option A — Zip Install (users)

1. Download the latest release zip from [Releases](../../releases).
2. Blender: **Edit → Preferences → Add-ons → Install** → select zip.
3. Enable **Fascia**. The **Fascia** tab appears in the View3D sidebar (`N`).

### Option B — Development Symlink (contributors)

```bash
git clone https://github.com/memegod069/Fascia.git
# Windows — symlink into Blender's addons folder:
mklink "C:\Users\<You>\AppData\Roaming\Blender Foundation\Blender\4.x\scripts\addons\fascia_addon.py" ^
       "C:\path\to\Fascia\fascia_addon.py"
```

Enable in Blender Preferences. Use **Scripts → Reload Scripts** (`Alt+R`) after edits.

---

## Quick Start (Tools 1–7 + 9)

1. **Tool 1** — Select your mesh → click **"Use Selected as Base"**
   (or "Make Placeholder Horse" for a test blob)
2. **Tool 2** — Age / Fat / Color sliders (placeholder only)
3. **Tool 3** — Optionally set Species File → click **"Place Landmarks"**
4. **Tool 4** — Click **"Generate Muscles"**
5. **Tool 5** — Optionally **"Bind Landmarks to Rig"** → drag **Flex** slider
6. **Tool 6** — Click **"Simulate Motion"** (60-frame flex animation)
7. **Tool 7** — Click **"Bake Result"** (shape keys per frame)
9. **Tool 9** — `bpy.ops.fascia.get_status()` for LLM/scripting state query

---

## What Works / Known Limitations

| Feature | Status | Notes |
|---|---|---|
| Landmark placement | ✅ Real | Normalized to bounding box; any mesh |
| Muscle sizing | ✅ Real | Radii = fraction of bbox longest side |
| Volume-preserving contraction | ✅ Real | `L·(1−c)`, `r/√(1−c)`, πr²L constant |
| Origin pinning | ✅ Real | Origin fixed; insertion shortens toward it |
| Per-muscle recruitment | ✅ Real | UIList; `c_i = flex·0.25·r_i` |
| KDTree skin push | ✅ Real | O(V·log M) replaces O(V·M) |
| Skin sliding | ✅ Real | Axial slide ∝ shortening |
| Rig binding | ✅ Real | `parent_set(BONE, keep_transform=True)` |
| Insertion tracking | ✅ Real | Damped Track; rotation-only |
| Antagonist pairing | ✅ Real | Reciprocal inhibition, side-specific |
| LLM surface | ✅ Real | Inline JSON + `get_status` |
| FEM physics | ❌ Not real | Geometric approximation — honest choice |
| Automatic creature gen | ❌ Not real | LLM drives; Fascia is the hands |
| Muscle stretch to insertion | ⚠️ Gap | Damped Track fixes angle; length mismatch |
| Skin relaxation | ⚠️ Deferred | Vertices slide independently |
| Performance 700k+ verts | ⚠️ Slow | Pure Python; ~30s/update_flex |

---

## For LLM / Scripting Users

```python
import bpy

bpy.data.objects["YourMesh"]["fascia_role"] = "skin"
bpy.context.scene.fascia_species_json = '{"name":"Alien","landmarks":{...},"muscles":{...}}'
bpy.ops.fascia.place_landmarks()
bpy.ops.fascia.generate_muscles()
bpy.context.scene.fascia_flex = 0.8
bpy.ops.fascia.get_status()   # → stdout/MCP
bpy.ops.fascia.bake_flex_pose()
```

See `docs/llm-integration.md` and `docs/species-schema.md` for full guides.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
```

---

### 1.2 Create `CONTRIBUTING.md`

```markdown
# Contributing to Fascia

## Before You Start

1. Read `AGENTS.md` — source of truth for hard rules and session workflow.
2. Read `memory.md` — full project state, real vs placeholder, known limitations.
3. Read `issues.md` — open backlog with reproduction steps and suggested fixes.

## Setup

1. `git clone https://github.com/memegod069/Fascia.git`
2. Symlink or copy `fascia_addon.py` into Blender's `scripts/addons/` folder.
3. Enable **Fascia** in Blender → Preferences → Add-ons.
4. After changes: **Scripts → Reload Scripts** (`Alt+R`).

## Making Changes

**Bug fixes:** Check `issues.md` for steps + suggested fix. Make the minimal change.
Verify manually in Blender. Preserve all shape-key safety rules.

**New features:** Write a spec in `specs/` first (see existing specs for format).
Add new operators to BOTH `classes` tuple AND `panel.draw()`.
Add new Scene properties to BOTH `register()` AND `unregister()`.

## Code Style

- Explanatory paragraph comments before complex functions, not inline annotations.
- Descriptive variable names — clarity over brevity.
- `self.report({'INFO'}, "Fascia: ...")` for operator messages — NOT bare `print()`.
- `self.report({'WARNING'}, ...)` for soft failures.

## Testing

```bash
python tests/smoke_test.py          # Pure-function math tests (no Blender needed)
```

Manual: open Blender, enable add-on, run Tools 1–7 in order.

## Pull Requests

- One fix per PR. Reference the `issues.md` item (e.g. "Fixes Issue 3").
- Do NOT mix unrelated changes.

## What NOT to Do

- Do not write flexed data into Basis shape key.
- Do not add AI/LLM logic inside the add-on (rule 1, AGENTS.md).
- Do not rebuild Blender features (rigging, sculpting).
- Do not claim geometric contraction is real FEM physics.
- Do not tune values for one test mesh — build for any mesh.
```

---

### 1.3 Create `CHANGELOG.md`

```markdown
# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [Unreleased]

### Fixed
- Issue 1: Stale _original_verts cache invalidated via depsgraph handler when user sculpts skin.
- Issue 11: update_flex reads from Basis shape key, not mesh.vertices, when shape keys exist.

### Added
- LICENSE (MIT), expanded .gitignore, CONTRIBUTING.md, CHANGELOG.md
- .github/ issue templates, PR template, CI lint workflow
- docs/llm-integration.md, docs/species-schema.md
- tests/smoke_test.py (pure-function contraction + bbox math tests)
- blender_manifest.toml (Blender 4.2+ Extensions system)

---

## [0.1.0] — 2026-07-06

### Added
- Spec 1: Landmark proportions (real horse anatomy)
- Spec 2: Mesh-agnostic muscle sizing (fraction of bbox)
- Spec 3: Volume-preserving contraction (L·(1-c), r/√(1-c))
- Spec 4: Pinned muscle origin
- Spec 5: Per-muscle recruitment UIList
- Spec 6: Anatomy input slot (species JSON files)
- Spec 7: Rig binding (bone-parent landmarks)
- Spec 8: Muscle insertion tracking (Damped Track)
- Spec 9: LLM-facing surface (inline JSON + get_status)
- Spec 10: Antagonist pairing (reciprocal inhibition)
- Spec 11: KDTree spatial acceleration
- Spec 12: Skin sliding (axial tangential push)
```

---

### 1.4 Create `.github/ISSUE_TEMPLATE/bug_report.md`

```markdown
---
name: Bug report
about: Something is broken or crashing
title: "[BUG] "
labels: bug
assignees: ''
---

**Blender version:**
**Fascia addon version (bl_info):**
**OS:**

**Describe the bug**

**To reproduce**
1.
2.
3.

**Expected behavior**

**Actual behavior** (include console output)

**Does this affect meshes or shape keys?**
```

### 1.5 Create `.github/ISSUE_TEMPLATE/feature_request.md`

```markdown
---
name: Feature request
about: Propose a new tool or improvement
title: "[FEATURE] "
labels: enhancement
assignees: ''
---

**New tool or improvement to existing tool?**

**Describe the feature** (plain English)

**Why is this needed?** (which creature pipeline step does it address?)

**Does this fit Fascia's scope?**
Fascia builds soft tissue — it does not generate meshes, rig skeletons, or contain AI.

**Suggested approach** (optional)
```

### 1.6 Create `.github/PULL_REQUEST_TEMPLATE.md`

```markdown
## Summary
<!-- One sentence: what does this PR do? -->

## Issue addressed
<!-- e.g. "Fixes Issue 3 (missing poll methods)" -->

## Changes made

## Testing done (Blender version?)

## Shape-key safety check
- [ ] Did NOT write flexed data into Basis shape key
- [ ] Did NOT write to mesh.vertices when shape keys exist
- [ ] Baked data captured BEFORE creating/modifying Basis

## Registration order check (if adding operators/properties)
- [ ] New operator in BOTH classes tuple AND panel.draw()
- [ ] New Scene property in BOTH register() AND unregister()
- [ ] PropertyGroup registered BEFORE UIList referencing it
- [ ] CollectionProperty/IntProperty deleted BEFORE unregistering PropertyGroup
```

### 1.7 Create `.github/workflows/lint.yml`

```yaml
name: Lint

on:
  push:
    branches: ["**"]
  pull_request:
    branches: ["main"]

jobs:
  syntax-check:
    name: Python syntax check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Syntax check (py_compile)
        run: python -m py_compile fascia_addon.py && echo "Syntax OK"

      - name: Pure-function smoke tests
        run: python tests/smoke_test.py
```

---

## PHASE 2 — HIGH-SEVERITY CODE FIXES (all in `fascia_addon.py`)

Apply all, then do ONE commit. Run `python -m py_compile fascia_addon.py` after each fix.

---

### 2.1 — Issue 2: `//` relative path resolution in `_load_species` (~line 158)

**Find:**
```python
if not os.path.isfile(filepath):
    print("Fascia: species file not found: " + filepath)
    return None, None, None
```

**Replace with:**
```python
# Resolve Blender-relative paths (// prefix) to absolute paths.
# Python's os.path.isfile does not understand the // convention.
abs_path = bpy.path.abspath(filepath)
if not os.path.isfile(abs_path):
    print("Fascia: species file not found: " + abs_path)
    return None, None, None
filepath = abs_path
```

---

### 2.2 — Issue 3: Add `poll()` to ALL nine operators

Add this classmethod to every `FASCIA_OT_*` class (after `bl_description`, before `execute`):

```python
@classmethod
def poll(cls, context):
    # Fascia operators require Object Mode — they create, parent, and
    # deform objects via bpy.ops, which fail in other contexts.
    return context.mode == 'OBJECT'
```

Classes to update (search for each `class FASCIA_OT_` in the file):
- `FASCIA_OT_make_placeholder_horse`
- `FASCIA_OT_use_selected_as_base`
- `FASCIA_OT_place_landmarks`
- `FASCIA_OT_generate_muscles`
- `FASCIA_OT_bind_landmarks_to_rig`
- `FASCIA_OT_clear_rig_binding`
- `FASCIA_OT_simulate_motion`
- `FASCIA_OT_bake_flex_pose`
- `FASCIA_OT_get_status`

---

### 2.3 — Issue 4 + 13: Species schema validation helper

**Step A:** Insert this function after `_load_species_json`, before the rig-binding helpers section:

```python
def _validate_species_data(landmarks_data, muscles_data, context_label="species"):
    """Validate species dicts before any scene modification.

    Checks required keys, validates 'from'/'to' landmark references,
    auto-pads 3-element colors to RGBA. Returns (errors, warnings)
    where errors should abort the operation and warnings are non-fatal.
    Called at the top of place_landmarks and generate_muscles before
    any objects are created — prevents half-created scenes on bad input.
    """
    errors = []
    warnings = []

    for name, data in landmarks_data.items():
        pos = data.get("pos")
        if pos is None:
            errors.append(f"{context_label}: landmark '{name}' missing 'pos'")
        elif not isinstance(pos, (list, tuple)) or len(pos) != 3:
            errors.append(f"{context_label}: landmark '{name}' 'pos' must be 3 floats")

    known = set(landmarks_data.keys())
    for name, data in muscles_data.items():
        for key in ("from", "to", "radius"):
            if key not in data:
                errors.append(f"{context_label}: muscle '{name}' missing '{key}'")
        for ref_key in ("from", "to"):
            ref = data.get(ref_key, "")
            if ref and ref not in known:
                errors.append(
                    f"{context_label}: muscle '{name}' '{ref_key}' "
                    f"references unknown landmark '{ref}'"
                )
        color = data.get("color")
        if color is not None:
            if len(color) == 3:
                data["color"] = list(color) + [1.0]
                warnings.append(f"{context_label}: muscle '{name}' color padded to RGBA")
            elif len(color) != 4:
                errors.append(f"{context_label}: muscle '{name}' 'color' must be 3 or 4 elements")

    return errors, warnings
```

**Step B:** Add these lines at the TOP of `FASCIA_OT_place_landmarks.execute` AND `FASCIA_OT_generate_muscles.execute`, right AFTER species data is resolved but BEFORE any `bpy.data.objects` / scene modifications:

```python
errors, warnings = _validate_species_data(landmarks_data, muscles_data)
for w in warnings:
    self.report({'WARNING'}, w)
if errors:
    for e in errors:
        self.report({'ERROR'}, e)
    return {'CANCELLED'}
```

---

### 2.4 — Issue 12: Safe division floor (~line 636 in `update_flex`)

**Find:**
```python
max_c_total = flex * MAX_CONTRACTION if flex > 0.001 else 1.0
```

**Replace with:**
```python
# Safe floor prevents ZeroDivisionError in antagonist ratio.
# 1e-9 floor is correct for all flex values, not just the > 0.001 case.
max_c_total = max(flex * MAX_CONTRACTION, 1e-9)
```

---

### 2.5 — Issue 19: Save world matrix before clearing rig parent

**Where:** `FASCIA_OT_clear_rig_binding.execute`, per-landmark loop.

**Find the block that clears parent:**
```python
lm.parent = None
lm.parent_type = 'OBJECT'
lm.parent_bone = ""
```

**Replace with:**
```python
# Save world position before clearing parent. Setting lm.parent = None
# without saving causes Blender to recompute position from bone-relative
# local coords, snapping the landmark to the wrong world location when
# the rig is in a non-rest pose (Issue 19).
saved_world = lm.matrix_world.copy()
lm.parent = None
lm.parent_type = 'OBJECT'
lm.parent_bone = ""
lm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
lm.matrix_world = saved_world
```

---

### 2.6 — Issue 20: Mirror bone name for bilateral `_R` landmarks

**Where:** `FASCIA_OT_place_landmarks.execute`, bilateral creation branch, where `fascia_bone` is set on the `_R` empty.

**Find (on the _R side):**
```python
if "bone" in data:
    empty["fascia_bone"] = data["bone"]
```

**Replace (only for the _R branch):**
```python
if "bone" in data:
    bone_name = data["bone"]
    # Derive right-side bone name by swapping left-side suffixes.
    # Falls back to nearest-bone auto-binding at bind time if not found.
    bone_name = (bone_name
        .replace(".L", ".R")
        .replace("_L", "_R")
        .replace("left", "right")
        .replace("Left", "Right"))
    empty["fascia_bone"] = bone_name
```

The _L side and non-bilateral branches keep `data["bone"]` unchanged.

---

### 2.7 — Issue 21: Auto-bind fallback when explicit bone name is stale

**Where:** `FASCIA_OT_bind_landmarks_to_rig.execute`, per-landmark bind loop (~line 1092).

**Find the existing pattern:**
```python
bone_name = lm.get("fascia_bone", "")
if not bone_name:
    bone_name, _ = _find_nearest_bone(...)
ok = _bone_parent_object(lm, armature, bone_name)
if ok:
    bound += 1
else:
    skipped += 1
```

**Replace with:**
```python
bone_name = lm.get("fascia_bone", "")
used_fallback = False

# If explicit bone name is set but not in this armature (renamed rig,
# or JSON from a different creature), fall back to auto nearest-bone
# rather than silently skipping the landmark (Issue 21).
if bone_name and bone_name not in armature.data.bones:
    bone_name, _ = _find_nearest_bone(armature, lm.matrix_world.translation)
    used_fallback = True
elif not bone_name:
    bone_name, _ = _find_nearest_bone(armature, lm.matrix_world.translation)

if not bone_name:
    skipped += 1
    continue

ok = _bone_parent_object(lm, armature, bone_name)
if ok:
    bound += 1
    if used_fallback:
        self.report({'WARNING'},
            f"Fascia: '{lm.name}' used fallback binding (explicit bone not found)")
else:
    skipped += 1
```

---

## PHASE 3 — MEDIUM ISSUES + UX POLISH

### 3.1 — Issue 5: `update=update_flex` on recruitment and skin_sliding

**In `FasciaMuscleRecruitment`** — add `update=update_flex` to the `recruitment` FloatProperty:
```python
recruitment: bpy.props.FloatProperty(
    ...,
    update=update_flex   # triggers immediate redraw when slider moves
)
```

**In `register()`** — add `update=update_flex` to `fascia_skin_sliding`:
```python
bpy.types.Scene.fascia_skin_sliding = bpy.props.BoolProperty(
    ...,
    update=update_flex   # triggers immediate redraw when toggled
)
```

---

### 3.2 — Issue 6: Remove double `update_flex` in simulate/bake loops

In `FASCIA_OT_simulate_motion.execute` and `FASCIA_OT_bake_flex_pose.execute`, find and DELETE every line:
```python
update_flex(None, context)
```
that appears IMMEDIATELY AFTER `scene.fascia_flex = val` inside a loop.
The property callback fires automatically — the explicit call doubles the cost.
Do NOT delete `update_flex` itself or its `update=` registration.

---

### 3.3 — Issue 9: Save/restore selection around bind/clear operators

At the START of `FASCIA_OT_bind_landmarks_to_rig.execute` and `FASCIA_OT_clear_rig_binding.execute`:
```python
# Preserve selection so internal deselect/reselect doesn't destroy user state.
saved_active = context.view_layer.objects.active
saved_selected = list(context.selected_objects)
```

Just BEFORE `return {'FINISHED'}` in each:
```python
for obj in context.view_layer.objects:
    obj.select_set(obj in saved_selected)
context.view_layer.objects.active = saved_active
```

---

### 3.4 — Issue 15: Robust color unpack in `update_horse`

**Find (~line 423):**
```python
r, g, b = scene.fascia_color
body.color = (r, g, b, 1.0)
```

**Replace:**
```python
col = scene.fascia_color
body.color = (col[0], col[1], col[2], 1.0)
```

---

### 3.5 — Issue 10: Clear stale `Live_Flex` data when flex returns to 0

In `update_flex`, in the shape-keys branch, find:
```python
if flex < 0.001:
    live_key.value = 0.0
    mesh.update()
    continue
```

**Replace:**
```python
if flex < 0.001:
    live_key.value = 0.0
    # Write Basis coords into Live_Flex so external tools reading shape
    # key data directly see rest positions, not stale flexed positions.
    # Weight is 0.0 so no visual change occurs (Issue 10).
    basis_key = mesh.shape_keys.key_blocks.get("Basis")
    if basis_key:
        for i, bv in enumerate(basis_key.data):
            live_key.data[i].co = bv.co.copy()
    mesh.update()
    continue
```

---

### 3.6 — Issue 16: Bake reads Basis (not mesh.vertices) at flex=0 frames

In `FASCIA_OT_bake_flex_pose.execute`, find where source is set for baking.
Replace the source-selection logic with:
```python
basis = mesh.shape_keys.key_blocks.get("Basis") if mesh.shape_keys else None
if flex_val < 0.001:
    source = basis.data if basis else mesh.vertices
elif basis and "Live_Flex" in mesh.shape_keys.key_blocks:
    source = mesh.shape_keys.key_blocks["Live_Flex"].data
else:
    source = mesh.vertices
```

---

### 3.7 — Issue 17: Dynamic species label in panel

**Find in `FASCIA_PT_main_panel.draw`:**
```python
layout.label(text="Horse Settings:")
```

**Replace:**
```python
# Show loaded species name — not hardcoded "Horse" for non-horse workflows.
species_path = scene.fascia_species_path
if species_path:
    species_label = os.path.splitext(
        os.path.basename(bpy.path.abspath(species_path)))[0]
elif scene.fascia_species_json:
    species_label = "Custom Species"
else:
    species_label = "Horse"
layout.label(text=f"{species_label} Settings:")
```

---

### 3.8 — Issue 18: Cache species name to avoid re-reading file in `get_status`

At the end of `FASCIA_OT_place_landmarks.execute` and `FASCIA_OT_generate_muscles.execute`,
after `species_name` is resolved, add:
```python
context.scene["_fascia_species_name"] = species_name
```

In `FASCIA_OT_get_status.execute`, read the cache first:
```python
species_name = context.scene.get("_fascia_species_name")
if species_name is None:
    # ... existing resolution logic as fallback ...
```

---

### 3.9 — Issue 14: Mark orphan landmarks as RESERVED

In `HORSE_LANDMARKS` dict (Python code) and in `species/equine_horse.json`,
the three landmarks with no muscles are: `NuchalCrest`, `FrontKnee`, `BellyMid`.

In the Python dict, add a comment before each:
```python
# RESERVED: NuchalCrest — future neck muscle attachment (no muscle yet).
# RESERVED: FrontKnee — future cannon-bone muscle attachment (bilateral, no muscle yet).
# RESERVED: BellyMid — future abdominal muscle attachment (no muscle yet).
```

In `equine_horse.json`, add a `"note"` field to each orphan:
```json
"NuchalCrest": {"pos": [...], "bilateral": false, "region": "neck",
                "note": "RESERVED — future neck muscle attachment"},
```

---

### 3.10 — Add honest physics callout in panel UI

After the Flex slider row in `FASCIA_PT_main_panel.draw`:
```python
# Hard Design Rule 13: never claim FEM parity.
layout.label(text="Geometric contraction only (not FEM/physics)", icon='INFO')
```

---

## PHASE 4 — "AND MORE" IMPROVEMENTS

### 4.1 Create `docs/llm-integration.md`

```markdown
# LLM Integration Guide

Fascia is driven by an external LLM as the creature's "muscle TD".
This guide covers driving Fascia from Python, MCP, or any scripting env.

## The Pattern

1. Tag base mesh as skin
2. Pass anatomy inline (JSON string) or point at a species file
3. Run operators: place_landmarks → generate_muscles → [bind_to_rig] → flex → bake
4. Query state with get_status

## Minimal Example — Alien Creature

```python
import bpy, json

bpy.data.objects["AlienMesh"]["fascia_role"] = "skin"

anatomy = {
    "name": "Alien",
    "landmarks": {
        "CranialRidge": {"pos": [0.9, 0.5, 0.8], "bilateral": False, "region": "head"},
        "ThoraxTop":    {"pos": [0.5, 0.5, 0.9], "bilateral": False, "region": "torso"},
        "ThoraxSide":   {"pos": [0.5, 0.7, 0.6], "bilateral": True,  "region": "torso"}
    },
    "muscles": {
        "DorsalCord":    {"from": "CranialRidge", "to": "ThoraxTop",  "radius": 0.03, "color": [0.2, 0.8, 0.4, 0.6]},
        "LateralFascia": {"from": "ThoraxTop",    "to": "ThoraxSide", "radius": 0.025,"color": [0.3, 0.7, 0.5, 0.6]}
    }
}
bpy.context.scene.fascia_species_json = json.dumps(anatomy)

bpy.ops.fascia.place_landmarks()
bpy.ops.fascia.generate_muscles()
bpy.context.scene.fascia_flex = 0.8
bpy.ops.fascia.get_status()
# → "Fascia: base=AlienMesh, species=Alien, landmarks=4, muscles=3, rig=None, flex=0.8"
```

## Species Resolution Priority

1. `scene.fascia_species_path` — file path (wins)
2. `scene.fascia_species_json` — inline JSON string
3. Embedded `HORSE_*` data — fallback

## Rules for LLM Anatomy

- `pos` = UVW [0,1] mapped to base mesh bounding box
- `bilateral: true` → Name_L + Name_R empties mirrored on Y
- `radius` = fraction of bbox longest side (e.g. 0.02 = 2%)
- No raw vertex coordinates — Fascia maps anatomy at runtime

## What get_status Reports

```
Fascia: base=<name>, species=<name>, landmarks=<N>, muscles=<M>, rig=<name|None>, flex=<val>
```
No vertex data (rule 5, AGENTS.md).

## Known Constraints

- All operators require Object Mode
- 700k+ vertex meshes: ~30s per flex update (pure Python limitation)
- Do not read raw mesh or vertex data — use get_status only
```

---

### 4.2 Create `docs/species-schema.md`

```markdown
# Species JSON Schema Reference

Full reference for species anatomy files. See `species/equine_horse.json` as a working example.

## Top-Level

| Key | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Display name (shown in UI label + status) |
| `landmarks` | object | Yes | Dict of landmark definitions |
| `muscles` | object | Yes | Dict of muscle definitions |

## Landmark Fields

| Key | Type | Required | Description |
|---|---|---|---|
| `pos` | [f, f, f] | Yes | Normalized [0,1] UVW in bounding box |
| `bilateral` | bool | Yes | true → creates Name_L + Name_R, mirrored on Y |
| `region` | string | Yes | Anatomical region (docs only) |
| `bone` | string | No | Explicit bone for rig binding. _R gets .L→.R mirrored. Falls back to nearest-bone if not found. |
| `note` | string | No | Human note, ignored by addon |

**pos system:** u=front/back, v=left/right (0.5=center), w=bottom/top

## Muscle Fields

| Key | Type | Required | Description |
|---|---|---|---|
| `from` | string | Yes | Origin landmark name (must exist) |
| `to` | string | Yes | Insertion landmark name (must exist) |
| `radius` | float | Yes | Fraction of bbox longest side |
| `color` | [R,G,B,A] | No | 3-element auto-padded to RGBA |
| `antagonist` | string | No | Antagonist muscle name (reciprocal inhibition) |

## Validation (auto-checked before any scene modification)

- Every landmark needs `pos` (3 elements)
- Every muscle needs `from`, `to`, `radius`
- `from`/`to` must reference existing landmark names
- 3-element colors auto-padded to RGBA with a warning
- Invalid data cancels operation without touching the scene

## Example — Minimal Biped

```json
{
  "name": "Simple Biped",
  "landmarks": {
    "Head":     {"pos": [0.5, 0.5, 0.95], "bilateral": false, "region": "head"},
    "Shoulder": {"pos": [0.5, 0.7, 0.80], "bilateral": true,  "region": "shoulder"},
    "Hip":      {"pos": [0.5, 0.6, 0.50], "bilateral": true,  "region": "hip"},
    "Knee":     {"pos": [0.5, 0.6, 0.30], "bilateral": true,  "region": "leg"}
  },
  "muscles": {
    "LatTrap": {"from": "Head",     "to": "Shoulder", "radius": 0.015, "color": [0.8, 0.2, 0.1, 0.6]},
    "Glute":   {"from": "Hip",      "to": "Knee",     "radius": 0.022, "color": [0.2, 0.3, 0.8, 0.6]}
  }
}
```

Result: 7 landmarks (1+2+2+2), 3 muscles (1 LatTrap + 2 bilateral Glutes).
```

---

### 4.3 Create `tests/smoke_test.py`

```python
"""
Fascia — Pure-function smoke tests.
Covers contraction math and landmark mapping.
No bpy required — run with: python tests/smoke_test.py
"""
import math, sys

MAX_CONTRACTION = 0.25

def contraction_scales(flex, recruitment=1.0):
    """Volume-preserving contraction: ls = 1-c, ts = 1/sqrt(ls)."""
    c = flex * MAX_CONTRACTION * recruitment
    ls = 1.0 - c
    ts = 1.0 / math.sqrt(ls) if ls > 0.01 else 1.0
    return ls, ts

def volume_product(ls, ts):
    """ls * ts^2 — must equal 1.0 for volume preservation."""
    return ls * ts * ts

def map_uvw_to_bbox(uvw, bbox_min, bbox_max):
    """Map normalized UVW [0,1] to world space via bounding box."""
    u, v, w = uvw
    return (
        bbox_min[0] + u * (bbox_max[0] - bbox_min[0]),
        bbox_min[1] + v * (bbox_max[1] - bbox_min[1]),
        bbox_min[2] + w * (bbox_max[2] - bbox_min[2]),
    )

def check(a, b, tol=1e-6, label=""):
    if abs(a - b) > tol:
        print(f"  FAIL [{label}] expected {b:.8f}, got {a:.8f}")
        return False
    return True

def test_rest():
    ls, ts = contraction_scales(0.0)
    return check(ls, 1.0, label="rest ls") and check(ts, 1.0, label="rest ts")

def test_full_flex():
    ls, ts = contraction_scales(1.0)
    return (check(ls, 0.75, label="full ls") and
            check(ts, 1.0/math.sqrt(0.75), label="full ts") and
            check(volume_product(ls, ts), 1.0, label="full vol"))

def test_double_recruitment():
    ls, ts = contraction_scales(1.0, 2.0)
    return (check(ls, 0.5, label="2x ls") and
            check(volume_product(ls, ts), 1.0, label="2x vol"))

def test_zero_recruitment():
    ls, ts = contraction_scales(1.0, 0.0)
    return check(ls, 1.0, label="0x ls") and check(ts, 1.0, label="0x ts")

def test_volume_sweep():
    ok = True
    for flex in [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]:
        for r in [0.0, 0.5, 1.0, 1.5, 2.0]:
            ls, ts = contraction_scales(flex, r)
            ok &= check(volume_product(ls, ts), 1.0, tol=1e-5,
                        label=f"vol f={flex} r={r}")
    return ok

def test_bbox_corners():
    mn, mx = (0.0,0.0,0.0), (3.6,1.2,2.0)
    p0 = map_uvw_to_bbox((0,0,0), mn, mx)
    p1 = map_uvw_to_bbox((1,1,1), mn, mx)
    pc = map_uvw_to_bbox((.5,.5,.5), mn, mx)
    return (check(p0[0], 0.0, label="min x") and
            check(p1[0], 3.6, label="max x") and
            check(pc[0], 1.8, label="ctr x"))

def test_bbox_offset():
    mn, mx = (-1.0,-0.5,0.2), (1.0,0.5,1.8)
    p = map_uvw_to_bbox((.5,.5,.5), mn, mx)
    return (check(p[0], 0.0, label="off x") and
            check(p[2], 1.0, label="off z"))

def test_antagonist_divisor():
    for flex in [0.0, 0.0001, 0.001, 1.0]:
        d = max(flex * MAX_CONTRACTION, 1e-9)
        if d <= 0:
            print(f"  FAIL [div] flex={flex} d={d}")
            return False
    return True

TESTS = [
    ("rest pose", test_rest),
    ("full flex + volume", test_full_flex),
    ("double recruitment", test_double_recruitment),
    ("zero recruitment", test_zero_recruitment),
    ("volume sweep", test_volume_sweep),
    ("bbox corners", test_bbox_corners),
    ("bbox offset origin", test_bbox_offset),
    ("antagonist safe divisor", test_antagonist_divisor),
]

if __name__ == "__main__":
    print("Fascia smoke tests\n")
    passed = failed = 0
    for name, fn in TESTS:
        ok = fn()
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if ok: passed += 1
        else:  failed += 1
    print(f"\n{passed}/{passed+failed} passed")
    if failed: sys.exit(1)
```

---

### 4.4 Create `blender_manifest.toml`

```toml
schema_version = "1.0.0"

id            = "fascia"
version       = "0.1.0"
name          = "Fascia"
tagline       = "Creature soft-tissue toolbox — landmarks, muscles, skin binding, flex baking"
maintainer    = "Fascia contributors"
type          = "add-on"

blender_version_min = "4.0.0"

license = ["SPDX:MIT"]
website = "https://github.com/memegod069/Fascia"
tags    = ["Mesh", "Animation", "Rigging"]

[build]
paths = ["fascia_addon.py", "species/"]
```

---

## PHASE 5 — MEMORY + LEARNINGS UPDATE

### 5.1 Append to `memory.md`

Add section **`## 11. OSS Improvements (2026-07-06)`** with:
- List of all files added (LICENSE, .gitignore, CONTRIBUTING, CHANGELOG, .github/*, docs/*, tests/*, manifest)
- List of all issues fixed (Issues 2,3,4+13,5,6,9,10,12,14,15,16,17,18,19,20,21)
- Updated overall status: OSS scaffolding complete, code hygiene improved

### 5.2 Append to `learnings.md`

```markdown
---

## 2026-07-06: Key OSS improvement gotchas

**poll() required on all operators:** Without `context.mode == 'OBJECT'` guard, Fascia buttons crash in Edit/Sculpt/Weight Paint with a context traceback and may leave partial objects in scene.

**bpy.path.abspath() for // paths:** Blender's file picker stores paths as `//relative`. Python's `os.path.isfile` cannot resolve `//`. Always call `bpy.path.abspath(filepath)` before any file check.

**update= on PropertyGroup FloatProperty:** A `FloatProperty` inside a `PropertyGroup` supports `update=` callback — it fires on change just like Scene properties. Use this to trigger `update_flex` from recruitment slider without a separate redraw hack.

**Save matrix_world before clearing parent:** Setting `obj.parent = None` without saving `obj.matrix_world.copy()` first causes Blender to snap the object to wrong world position when the parent was a posed bone. Fix: save → clear → restore matrix_world.

**Bilateral landmark bone name mirroring:** Copying the same explicit bone name to both _L and _R landmarks causes both to bind to the left-side bone. Swap `.L→.R`, `_L→_R`, `left→right` for the _R side.
```

---

## EXECUTION CHECKLIST

### Phase 1 — OSS Foundation
- [x] `LICENSE` — done
- [x] `.gitignore` — done
- [ ] `README.md` — full rewrite (§1.1)
- [ ] `CONTRIBUTING.md` — create (§1.2)
- [ ] `CHANGELOG.md` — create (§1.3)
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md` — create (§1.4)
- [ ] `.github/ISSUE_TEMPLATE/feature_request.md` — create (§1.5)
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` — create (§1.6)
- [ ] `.github/workflows/lint.yml` — create (§1.7)

### Phase 2 — High-Severity Code Fixes
- [ ] Issue 2: `bpy.path.abspath()` in `_load_species` (§2.1)
- [ ] Issue 3: `poll()` on all 9 operators (§2.2)
- [ ] Issue 4+13: `_validate_species_data()` + call in both operators (§2.3)
- [ ] Issue 12: Safe floor `max(..., 1e-9)` (§2.4)
- [ ] Issue 19: Save world matrix before clear parent (§2.5)
- [ ] Issue 20: Mirror bone name suffix for _R landmarks (§2.6)
- [ ] Issue 21: Auto-bind fallback for stale explicit bone (§2.7)

### Phase 3 — Medium Issues + UX
- [ ] Issue 5: `update=update_flex` on recruitment + skin_sliding (§3.1)
- [ ] Issue 6: Remove double `update_flex` calls in simulate/bake (§3.2)
- [ ] Issue 9: Save/restore selection in bind/clear operators (§3.3)
- [ ] Issue 15: Robust color unpack via index access (§3.4)
- [ ] Issue 10: Clear stale Live_Flex data at flex=0 (§3.5)
- [ ] Issue 16: Bake reads Basis at flex=0 frames (§3.6)
- [ ] Issue 17: Dynamic species label in panel (§3.7)
- [ ] Issue 18: Cache `_fascia_species_name` in scene (§3.8)
- [ ] Issue 14: Mark orphan landmarks as RESERVED in code + JSON (§3.9)
- [ ] Honest physics callout in UI (§3.10)

### Phase 4 — "And More"
- [ ] `docs/llm-integration.md` (§4.1)
- [ ] `docs/species-schema.md` (§4.2)
- [ ] `tests/smoke_test.py` (§4.3)
- [ ] `blender_manifest.toml` (§4.4)

### Phase 5 — Memory + Learnings
- [ ] Append section 11 to `memory.md` (§5.1)
- [ ] Append dated entry to `learnings.md` (§5.2)

### Final Validation
- [ ] `python tests/smoke_test.py` — all 8 must pass
- [ ] `python -m py_compile fascia_addon.py` — no errors
- [ ] Commit: `chore: OSS scaffolding + Issues 2,3,4,5,6,9,10,12,13,14,15,16,17,18,19,20,21 fixes`
- [ ] Push to remote

---

## EXPECTED OUTCOME AFTER ALL PHASES

| Area | Before | After |
|---|---|---|
| OSS/contributor readiness | 1/10 | 8/10 |
| README | 3/10 | 8/10 |
| Error handling | 4/10 | 7/10 |
| Code hygiene | 5/10 | 7.5/10 |
| Testing | 1/10 | 4/10 |
| Docs/LLM surface | 4/10 | 8/10 |
| **Overall** | **3.8/10** | **7.1/10** |

---

## WHAT'S NEXT (after this plan)

1. **Module split** — `fascia_addon.py` → package (`__init__.py`, `operators/`, `ui/`, `data/`, `utils/`)
2. **Standing-pose test mesh** — verify landmarks on a four-square pose horse
3. **Blender integration tests** — `blender --background --python tests/integration_test.py`
4. **Performance** — `foreach_get`/`foreach_set` batch I/O in skin-push loop (~30s bottleneck)
5. **GitHub Release** — tag `v0.1.0`, zip `fascia_addon.py` + `species/`, publish with CHANGELOG notes

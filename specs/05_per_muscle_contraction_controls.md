# SPEC 05 — Per-Muscle Contraction Controls

**Target executor:** DeepSeek.
**Scope:** Adds a per-muscle "recruitment" multiplier on top of the global Flex slider, with a UI list in the panel. New: a `PropertyGroup`, collection property registration, population logic in `FASCIA_OT_generate_muscles`, per-muscle contraction math in `update_flex`, and a UI list + slider in `FASCIA_PT_main_panel`. Does NOT touch the volume-preserving scale formula (still `length_scale = 1-c`, `thickness_scale = 1/√(1-c)`), the skin-push falloff/influence-radius/push-direction logic, shape-key safety, the backup system, landmark/muscle data tables, `create_muscle_mesh`, or tools 6/7 (they call `update_flex` and inherit the fix).
**Estimated size:** ~80 lines added/changed across 5 locations in `fascia_addon.py`.

---

## 1. Why this change is needed

Every muscle currently contracts by the same fraction — one global Flex slider drives `c = flex * MAX_CONTRACTION` for all 29 muscles simultaneously. Real movement recruits muscles individually: a galloping horse fires its hamstrings and glutes hard while its trapezius stays nearly relaxed. Per-muscle control is the documented next layer on top of pinned attachments (Spec 4) and the prerequisite for antagonist pairing (a future spec where contracting one muscle automatically relaxes its paired antagonist).

This spec adds a **recruitment multiplier per muscle** (`0.0`–`2.0`, default `1.0`). The effective contraction for muscle *i* becomes:

```
c_i = flex * MAX_CONTRACTION * recruitment_i
```

- `recruitment = 1.0` → identical to today (uniform contraction).
- `recruitment = 0.0` → that muscle stays at rest no matter the global Flex.
- `recruitment = 2.0` → that muscle contracts twice as hard (up to the volume-preservation `length_scale > 0.01` guard).

The global Flex slider stays — it is the "how hard is the whole creature working" master. Recruitment is "how much does *this* muscle participate." This mirrors how real muscle recruitment works (central drive × per-muscle activation).

---

## 2. The per-muscle contraction model

For each muscle *i* with recruitment `r_i`:

```
c_i     = flex * MAX_CONTRACTION * r_i
ls_i    = 1.0 - c_i                         (length scale)
ts_i    = 1.0 / (ls_i ** 0.5)  if ls_i > 0.01 else 1.0   (thickness scale)
vol_i   = ts_i² * ls_i  = 1.0  (volume preserved, per muscle)
```

The global `length_scale` / `thickness_scale` variables in `update_flex` are replaced by per-muscle values. The skin-push center computation (Spec 4, section 4c) uses the **per-muscle** `ls_i` instead of the global `length_scale`.

The skin-push `growth` formula (`m_radius * (thickness_scale - 1.0)`) uses the **per-muscle** `ts_i`. This means a muscle with `recruitment=0` contributes zero growth (no bulge) even when global Flex=1 — correct, because it isn't contracting.

**Volume is still preserved per-muscle.** Each muscle's `ts_i² · ls_i = 1.0` regardless of `r_i` (within the `ls_i > 0.01` guard). The guard clamps extreme recruitment so the muscle doesn't collapse to zero length.

---

## 3. Architectural decisions (read before changing anything)

1. **Recruitment is a multiplier on global Flex, not an absolute.** `c_i = flex * MAX_CONTRACTION * r_i`. The global slider is the master intensity; recruitment is per-muscle participation. Do NOT make per-muscle values absolute (that would orphan the global slider and break tools 6/7).
2. **Range 0.0–2.0, default 1.0.** 0 = never contracts, 1 = today's behaviour, 2 = double contraction. The `ls_i > 0.01` guard from Spec 3 protects against collapse at high recruitment. Do NOT cap recruitment at 1.0 — real muscles can be recruited beyond their nominal baseline, and the guard handles the math.
3. **Store recruitment in a registered `PropertyGroup` + `CollectionProperty` on the Scene**, keyed by muscle object name. Not as `fascia_recruitment` on each muscle object — object ID properties are fine for static metadata (`fascia_type`, `fascia_radius`) but a registered collection gives a real UI list with sliders, and survives undo/reload cleanly. The collection is rebuilt when muscles are regenerated.
4. **Populate on muscle generation, clear on regeneration.** `FASCIA_OT_generate_muscles` already deletes and recreates muscles; it should also clear and repopulate the recruitment collection so names stay in sync. Preserve values for muscles that still exist after a re-generate (e.g. if the user tuned recruitment then re-ran generate) — match by muscle name.
5. **Backwards compatibility: empty collection = uniform behaviour.** If the collection is empty (e.g. a saved scene opened before this spec, or muscles deleted manually), `update_flex` falls back to `r_i = 1.0` for every muscle — identical to pre-Spec-05 behaviour. This keeps old scenes working without manual migration.
6. **UI: a UI list with a slider beside it.** The list shows each muscle name + its recruitment value; a slider below edits the selected entry. Do NOT draw 29 individual sliders in the panel — that's a wall of UI. A `UIList` + one slider is the standard Blender pattern and scales to any muscle count.
7. **Per-muscle `ls_i` feeds the skin-push center (Spec 4).** The Spec-4 center computation `center = origin + axis * (rest_length * length_scale * 0.5)` must use the per-muscle `ls_i`, not a global `length_scale`. Otherwise a non-recruited muscle (`r=0`, `ls=1`) would have its bulge center computed as if it shortened.
8. **Per-muscle `ts_i` feeds the skin-push growth.** A non-recruited muscle contributes zero growth (`ts_i = 1.0` → `growth = 0`). This is automatic if the growth formula uses `ts_i`.
9. **Legacy `fascia_rest_length` fallback (Spec 4) stays.** Muscles without `fascia_rest_length` still use the old midpoint center; they also get `r_i = 1.0` (uniform) since they pre-date this spec too.
10. **Do not overclaim.** Code comments must state what this does (per-muscle recruitment multiplier on global flex) AND what it does not do (no antagonist relaxation, no automatic recruitment curves, no UI for saving/loading recruitment presets). See section 7.

---

## 4. The exact changes

### 4a. Add the `PropertyGroup` class

Immediately before the `classes` tuple (currently ~line 1029), add:

```python
# ─────────────────────────────────────────────────────────────────
# PER-MUSCLE CONTRACTION RECRUITMENT
# ─────────────────────────────────────────────────────────────────
# A registered PropertyGroup stored in a CollectionProperty on the
# Scene. One entry per muscle, keyed by muscle object name. The
# recruitment value (0.0–2.0, default 1.0) multiplies the global Flex
# slider's contraction for that muscle:
#   c_i = flex * MAX_CONTRACTION * recruitment_i
# This lets the user make individual muscles contract harder, softer,
# or not at all, while the global Flex slider stays the master drive.
# Antagonist pairing (auto-relax reciprocal muscles) is future work.

class FasciaMuscleRecruitment(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Muscle Name",
        description="Name of the muscle object this entry controls",
    )
    recruitment: bpy.props.FloatProperty(
        name="Recruitment",
        description="How much this muscle participates in the global Flex contraction. 1.0 = normal, 0.0 = stays at rest, 2.0 = double contraction",
        default=1.0,
        min=0.0,
        max=2.0,
    )
```

### 4b. Register the `PropertyGroup` and the `CollectionProperty` + `IntProperty` for the UI list

In `register()` (currently ~line 1040), after the existing `bpy.types.Scene.fascia_*` property registrations and before the closing of the function, add:

```python
    # Per-muscle contraction recruitment collection (Spec 5).
    # One FasciaMuscleRecruitment entry per muscle, rebuilt when
    # muscles are generated. Empty collection = uniform recruitment
    # (backwards-compatible with pre-Spec-5 scenes).
    bpy.utils.register_class(FasciaMuscleRecruitment)
    bpy.types.Scene.fascia_recruitment = bpy.props.CollectionProperty(
        type=FasciaMuscleRecruitment,
        name="Per-Muscle Recruitment",
        description="Per-muscle contraction recruitment multipliers",
    )
    bpy.types.Scene.fascia_recruitment_index = bpy.props.IntProperty(
        name="Recruitment List Index",
        description="Active row in the per-muscle recruitment list",
        default=0,
        min=0,
    )
```

In `unregister()` (currently ~line 1096), before the existing `del bpy.types.Scene.fascia_*` lines, add:

```python
    del bpy.types.Scene.fascia_recruitment_index
    del bpy.types.Scene.fascia_recruitment
    bpy.utils.unregister_class(FasciaMuscleRecruitment)
```

Add `FasciaMuscleRecruitment` to the `classes` tuple so it is also registered by the `register()` class loop (Blender requires it registered for use in a `CollectionProperty`). Place it first in the tuple so it exists before the Scene properties reference it:

```python
classes = (
    FasciaMuscleRecruitment,
    FASCIA_OT_make_placeholder_horse,
    ...
)
```

### 4c. Populate the recruitment collection in `FASCIA_OT_generate_muscles`

At the start of `FASCIA_OT_generate_muscles.execute` (currently ~line 741), immediately AFTER the `has_landmarks` check and BEFORE the "Clean up any previously generated muscles" block, add a block to snapshot the current recruitment values so they can be restored after regeneration:

```python
        # Snapshot existing per-muscle recruitment values so we can
        # restore them after regeneration (by muscle name). This lets
        # the user re-run Generate Muscles without losing their
        # per-muscle recruitment tuning (Spec 5).
        old_recruitment = {}
        for entry in context.scene.fascia_recruitment:
            old_recruitment[entry.name] = entry.recruitment
        context.scene.fascia_recruitment.clear()
```

Then, at the END of `execute` (currently ~line 860, just before `update_flex(None, context)`), repopulate the collection from the muscle objects that now exist:

```python
        # Rebuild the per-muscle recruitment collection from the
        # generated muscles. Preserve recruitment values for muscles
        # that existed before regeneration (matched by name); new
        # muscles default to 1.0 (uniform contraction).
        for m in bpy.data.objects:
            if m.get("fascia_type") == "muscle":
                entry = context.scene.fascia_recruitment.add()
                entry.name = m.name
                entry.recruitment = old_recruitment.get(m.name, 1.0)
```

### 4d. Per-muscle contraction math in `update_flex`

Find the Step 1 block (currently ~lines 335–345):

```python
    muscles = [obj for obj in bpy.data.objects
               if obj.get("fascia_type") == "muscle"]

    c = flex * MAX_CONTRACTION
    length_scale = 1.0 - c
    thickness_scale = 1.0 / (length_scale ** 0.5) if length_scale > 0.01 else 1.0

    for obj in muscles:
        obj.scale[0] = thickness_scale  # local X = thickness (bulge)
        obj.scale[1] = thickness_scale  # local Y = thickness (bulge)
        obj.scale[2] = length_scale     # local Z = length (shorten)
```

Replace with:

```python
    muscles = [obj for obj in bpy.data.objects
               if obj.get("fascia_type") == "muscle"]

    # Per-muscle recruitment (Spec 5). Build a name -> recruitment map
    # from the Scene collection. Empty collection (old scene, or
    # muscles deleted manually) = uniform recruitment (r=1.0 for all),
    # which is identical to pre-Spec-5 behaviour.
    recruitment_map = {}
    for entry in scene.fascia_recruitment:
        recruitment_map[entry.name] = entry.recruitment

    # Per-muscle scale cache: also needed by Step 2 (skin push), so
    # compute it once here and reuse. Each muscle gets its own
    # length_scale_i and thickness_scale_i based on its recruitment.
    muscle_scales = {}  # name -> (length_scale_i, thickness_scale_i)

    for obj in muscles:
        r_i = recruitment_map.get(obj.name, 1.0)
        c_i = flex * MAX_CONTRACTION * r_i
        ls_i = 1.0 - c_i
        ts_i = 1.0 / (ls_i ** 0.5) if ls_i > 0.01 else 1.0
        obj.scale[0] = ts_i  # local X = thickness (bulge)
        obj.scale[1] = ts_i  # local Y = thickness (bulge)
        obj.scale[2] = ls_i  # local Z = length (shorten)
        muscle_scales[obj.name] = (ls_i, ts_i)
```

Then find the Step 2 muscle_info precompute block (currently ~lines 375–396):

```python
    muscle_info = []
    for m in muscles:
        rest_length = m.get("fascia_rest_length", None)
        if rest_length is None:
            center = m.matrix_world.translation.copy()
        else:
            origin = m.matrix_world.translation.copy()
            axis = (m.rotation_quaternion @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
            center = origin + axis * (rest_length * length_scale * 0.5)
        radius = m.get("fascia_radius", 0.04)
        muscle_info.append((center, radius))
```

Replace with:

```python
    muscle_info = []
    for m in muscles:
        ls_i, ts_i = muscle_scales.get(m.name, (1.0, 1.0))
        rest_length = m.get("fascia_rest_length", None)
        if rest_length is None:
            # Legacy muscle (pre-Spec-4): pivot at midpoint.
            center = m.matrix_world.translation.copy()
        else:
            # Pinned muscle (Spec 4): origin at from-landmark, belly
            # center computed from per-muscle length_scale (Spec 5).
            origin = m.matrix_world.translation.copy()
            axis = (m.rotation_quaternion @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
            center = origin + axis * (rest_length * ls_i * 0.5)
        radius = m.get("fascia_radius", 0.04)
        # Per-muscle thickness_scale drives the bulge growth (Spec 5):
        # a non-recruited muscle (r=0, ts=1) contributes zero growth.
        muscle_info.append((center, radius, ts_i))
```

Then find the inner skin-push loop that unpacks `muscle_info` (currently ~line 444):

```python
            for (m_center, m_radius) in muscle_info:
                delta = world_pos - m_center
                dist = delta.length

                if dist < influence_radius and dist > 0.001:
                    t = dist / influence_radius
                    falloff = (1.0 - t) * (1.0 - t)
                    growth = m_radius * (thickness_scale - 1.0)
                    push_dir = delta.normalized()
                    push += push_dir * growth * falloff
                    was_affected = True
```

Replace with:

```python
            for (m_center, m_radius, m_ts_i) in muscle_info:
                delta = world_pos - m_center
                dist = delta.length

                if dist < influence_radius and dist > 0.001:
                    t = dist / influence_radius
                    falloff = (1.0 - t) * (1.0 - t)
                    growth = m_radius * (m_ts_i - 1.0)
                    push_dir = delta.normalized()
                    push += push_dir * growth * falloff
                    was_affected = True
```

(`m_ts_i` is the per-muscle thickness scale. A muscle with `recruitment=0` has `ts_i=1.0` → `growth=0` → no skin push, even at global Flex=1. Correct: it isn't contracting.)

### 4e. Add the UI list + recruitment slider to the panel

Immediately before the `FASCIA_PT_main_panel` class definition, add a UI list class:

```python
class FASCIA_UL_recruitment(bpy.types.UIList):
    bl_idname = "FASCIA_UL_recruitment"
    bl_label = "Per-Muscle Recruitment"

    def draw_item(self, context, layout, data, item, icon_value, active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.name, icon='MESH_UVSPHERE')
            row.prop(item, "recruitment", text="", slider=True, emboss=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon_value)
```

Add `FASCIA_UL_recruitment` to the `classes` tuple (after `FasciaMuscleRecruitment`):

```python
classes = (
    FasciaMuscleRecruitment,
    FASCIA_UL_recruitment,
    FASCIA_OT_make_placeholder_horse,
    ...
)
```

In `FASCIA_PT_main_panel.draw`, find the Simulation section (currently ~lines 1042–1053):

```python
        # ── Simulation section (Tools 5-7) ───────────────────
        layout.separator()
        layout.label(text="Simulation:")

        # Flex slider — controls muscle bulge and skin deformation
        layout.prop(scene, "fascia_flex", text="Flex", slider=True)

        # Show how many skin vertices are being affected by the flex
        flex_val = scene.fascia_flex
        if flex_val > 0.001:
            affected = scene.get("_fascia_flex_affected", 0)
            layout.label(text="Skin bound: " + str(affected) + " vertices affected")
```

Replace with:

```python
        # ── Simulation section (Tools 5-7) ───────────────────
        layout.separator()
        layout.label(text="Simulation:")

        # Flex slider — the GLOBAL contraction drive. Per-muscle
        # recruitment (below) multiplies this per muscle:
        #   c_i = flex * MAX_CONTRACTION * recruitment_i
        layout.prop(scene, "fascia_flex", text="Flex", slider=True)

        # Show how many skin vertices are being affected by the flex
        flex_val = scene.fascia_flex
        if flex_val > 0.001:
            affected = scene.get("_fascia_flex_affected", 0)
            layout.label(text="Skin bound: " + str(affected) + " vertices affected")

        # ── Per-muscle recruitment (Spec 5) ──────────────────
        # A UI list of all generated muscles, each with its own
        # recruitment multiplier on the global Flex. 1.0 = normal,
        # 0.0 = stays at rest, 2.0 = double contraction.
        # Empty list = no muscles generated yet (or pre-Spec-5 scene);
        # falls back to uniform recruitment in update_flex.
        if len(scene.fascia_recruitment) > 0:
            layout.separator()
            layout.label(text="Per-Muscle Recruitment:")
            row = layout.row()
            row.template_list(
                "FASCIA_UL_recruitment", "",
                scene, "fascia_recruitment",
                scene, "fascia_recruitment_index",
                rows=6,
            )
```

---

## 5. What you must NOT change

- Do NOT change the volume-preserving scale formula (`ls = 1-c`, `ts = 1/√(1-c)`). Per-muscle recruitment feeds into `c_i`; the formula stays.
- Do NOT change the skin-push falloff (`(1.0 - t) ** 2`), the influence radius, or the push direction (`delta.normalized()`).
- Do NOT change `HORSE_MUSCLES` radii, `HORSE_LANDMARKS`, `MAX_CONTRACTION`, or `MUSCLE_INFLUENCE_FRACTION`.
- Do NOT touch shape-key logic, the backup system, `_save_original_verts` / `_restore_original_verts`, or the bake capture order.
- Do NOT touch `create_muscle_mesh` (Spec 4's pivot + geometry offset stays).
- Do NOT touch `FASCIA_OT_simulate_motion` or `FASCIA_OT_bake_flex_pose` — they call `update_flex` and inherit per-muscle contraction automatically.
- Do NOT add antagonist pairing, recruitment presets, or animation curves for recruitment. Those are future specs.
- Do NOT add new imports — `bpy` and `mathutils` are already imported.
- Do NOT change the global Flex slider's range or behaviour — it stays 0.0–1.0, the master drive.

---

## 6. Verification (architect runs in Blender)

After the edit: copy `fascia_addon.py` to the Blender addons dir, reload the add-on, regenerate muscles. Then verify (note: the test mesh has 748k vertices and `update_flex`'s Python loop times out at flex>0 — a pre-existing perf issue, not this spec's problem. Verification uses direct scale-setting to bypass the skin push, same as Spec 4 verification):

1. **Collection populated:** after Generate Muscles, `scene.fascia_recruitment` has one entry per muscle (29 entries), each with `recruitment=1.0` and `name` matching a muscle object.
2. **Default = uniform:** with all recruitment=1.0, set flex=1 by directly applying scales (bypass `update_flex`). Every muscle has `scale=(1.1547, 1.1547, 0.75)`, volume product=1.0. Identical to Spec-4 behaviour.
3. **Per-muscle recruitment works:** set one muscle's recruitment to 0.0 (e.g. `GluteusMedius_R`), another to 2.0 (e.g. `Triceps_L`), apply scales via the per-muscle formula directly:
   - `GluteusMedius_R` (r=0): `c=0`, scale=(1.0, 1.0, 1.0) — stays at rest.
   - `Triceps_L` (r=2): `c=0.5`, `ls=0.5`, `ts=1/√0.5≈1.4142`, scale=(1.4142, 1.4142, 0.5), volume product `1.4142²·0.5 = 1.0`.
   - A third muscle with default r=1: scale=(1.1547, 1.1547, 0.75), volume product 1.0.
4. **Recruitment preserved across regeneration:** change a muscle's recruitment to 0.5, re-run Generate Muscles, confirm that muscle's entry still has recruitment=0.5 (matched by name). New muscles (if any) default to 1.0.
5. **Backwards compat:** manually clear `scene.fascia_recruitment`, apply scales — all muscles get r=1.0 (uniform), identical to pre-Spec-5.
6. **UI list renders:** the panel shows the recruitment list with muscle names and sliders when muscles exist; hidden when the collection is empty.
7. **Restore:** set all recruitment back to 1.0, set scales to (1,1,1) — drift-free.

Report: the collection length after generation, the `scale` + volume product for the three muscles in check 3, whether recruitment survived regeneration (check 4), and whether the UI list rendered (check 6).

Sanity expectations:
- r=0: scale (1,1,1), vol 1.0.
- r=1: scale (1.1547, 1.1547, 0.75), vol 1.0.
- r=2: scale (1.4142, 1.4142, 0.5), vol 1.0.

---

## 7. Known limitations (must be documented in code comments, NOT hidden)

- **No antagonist pairing.** Setting one muscle's recruitment high does not automatically relax its antagonist. Antagonist pairing is a future spec.
- **No recruitment animation.** Recruitment values are static; they do not keyframe with the Simulate Motion tool. Animating recruitment per-frame is future work.
- **No presets.** There is no save/load for recruitment setups (e.g. "gallop preset", "standing preset"). Future work.
- **Uniform global Flex still contracts all muscles.** A muscle with recruitment=0 stays at rest, but there is no inverse — a muscle with recruitment>0 contracts whenever global Flex>0. Asymmetric drive (some muscles contracting while others relax below baseline) needs antagonist pairing.
- **Per-muscle UI list only.** No graph editor, no per-muscle curve view. Future work.

These are honest scope boundaries, not bugs. Do NOT silently work around them.

---

## 8. Deliverable back to the architect

- The updated `fascia_addon.py` written to `C:\Projects\Fascia\fascia_addon.py` (the source — the architect handles the addons-dir copy and Blender reload).
- A short note confirming only the 5 locations in section 4 were changed (4a PropertyGroup, 4b register/unregister + classes tuple, 4c populate-on-generate, 4d per-muscle math + skin-push unpack, 4e UI list + panel).
- No need to paste logs — the architect will read the file and run the section-6 verification independently.

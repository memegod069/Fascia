# SPEC 07 — Rig Binding (Landmarks Follow Bones)

**Target executor:** DeepSeek or implementing agent.
**Scope:** Add a rig-binding layer so landmarks attach to armature bones and muscles follow their origin landmark. New operators `fascia.bind_landmarks_to_rig` and `fascia.clear_rig_binding`, new Scene property `fascia_armature`, new per-landmark `fascia_bone` custom property, optional `bone` field in species JSON, muscle parenting to origin landmark in `generate_muscles`, and a correctness fix in `update_flex` (read world rotation from `matrix_world`, force a depsgraph update before reading parented muscle transforms). Does NOT change contraction math, shape-key safety, the bake pipeline, species loading logic, or the panel layout beyond adding a small Rig section.
**Estimated size:** ~140 lines added/changed across 6 locations in `fascia_addon.py`, plus optional extension of `species/equine_horse.json` (no `bone` fields added by default — the horse has no shipped rig).

---

## 1. Why this change is needed

Rule 12 (AGENTS.md): "Landmarks must bind to the rig. A landmark that floats when the skeleton moves is a bug to fix, not a limitation to document forever. Bone moves → landmark moves → muscle follows → skin deforms. The rig binding is Fascia's job."

Today (line 754, 778 of `fascia_addon.py`) every landmark is parented to the base mesh:

```python
empty.parent = body
empty.matrix_parent_inverse = body.matrix_world.inverted()
```

This has two failure modes:

1. **Mesh-parenting follows the object transform, not the deformed mesh surface.** If the base mesh has an Armature modifier and the skeleton moves, the mesh *surface* deforms but the mesh *object* does not translate/rotate. Mesh-parented landmarks therefore stay fixed in world space while the creature walks away underneath them. The landmarks visually detach from the anatomy they mark.
2. **The documented "insertion leaves a gap" limitation (Spec 4, §2) is a direct consequence.** Spec 4 pinned each muscle's origin to a static landmark and correctly noted that the gap at the insertion would be closed by "skeleton-driven landmarks (future rig work)". This spec is that future work.

The product thesis (AGENTS.md §"Product Thesis") requires Fascia to be **the flesh + the wires**. The wires are the bindings that connect soft tissue to the rig. Without rig binding, Fascia is a horse-shaped static sculpture add-on, not a creature harness. This is the next critical-path item after the anatomy input slot (Spec 6) — memory.md §10 priority #2.

The deliverable: when the captain rotates a bone (e.g. the horse's femur), the Stifle and HipJoint landmarks move with it, the Quadriceps muscle (parented to its HipJoint origin landmark) moves and reorients with the bone, and the skin bulge from the Quadriceps' contraction follows the moved muscle. The full chain: **bone → landmark → muscle → skin**.

---

## 2. The binding model

### 2a. Two-stage binding

```
   Armature bone  ──(bone parent)──>  Landmark empty  ──(object parent)──>  Muscle mesh
```

- **Stage 1 (landmark → bone):** each landmark empty is bone-parented to a bone in the chosen armature, with `matrix_parent_inverse` set to preserve its world position at bind time. The bone's transform (head position + rotation) becomes the landmark's parent. When the bone moves or rotates, the landmark follows, with the original offset preserved.
- **Stage 2 (muscle → landmark):** each muscle mesh is object-parented to its `from` landmark (the muscle's anatomical origin, already stored as `fascia_origin`), with `matrix_parent_inverse` preserving its world transform. When the landmark moves, the muscle moves with it. The muscle's local rotation (pointing from p1 to p2 at generation time) is preserved, so the muscle translates and reorients with its origin bone.

### 2b. What each stage costs and gives

| Stage | Mechanism | What it gives | What it does NOT give |
|-------|-----------|---------------|----------------------|
| 1 (landmark → bone) | `parent_type='BONE'` + `parent_bone` + `matrix_parent_inverse` | Landmark follows bone position AND rotation, offset preserved | Does not slide along the bone (offset is fixed at bind time) |
| 2 (muscle → landmark) | `parent=<origin empty>` + `matrix_parent_inverse` | Muscle origin tracks landmark; muscle translates + rotates with origin bone | Muscle does NOT track its insertion landmark — insertion end stays at its generated direction/length (see §7) |

### 2c. Why bone-parenting, not a Copy Transforms constraint

A Copy Transforms constraint replaces the landmark's whole transform with the bone's, which would snap the landmark to the bone head and discard the anatomical offset. Preserving the offset with a constraint requires a Child Of constraint with inverse-set, which is functionally identical to bone parenting but more complex to set up and inspect. Bone parenting via `parent_type='BONE'` is the documented Blender-native mechanism, handles the offset automatically via `matrix_parent_inverse`, and is what rule 12 describes ("landmarks attach to armature bones"). We use it.

### 2d. Auto-bind vs explicit bind

Two ways to specify which bone each landmark binds to:

- **Auto-bind (human-friendly, default):** for each landmark, find the bone whose segment (head→tail) is closest to the landmark's world position. Bind to that bone. One click, works for any rig whose bones roughly correspond to the landmark anatomy. Implemented in `fascia.bind_landmarks_to_rig`.
- **Explicit bind (LLM-facing):** the LLM sets `fascia_bone` (a per-landmark string property) to the bone name, then runs `fascia.bind_landmarks_to_rig` — the operator uses the named bone instead of auto-finding. The LLM can also author `"bone": "Femur"` per landmark in the species JSON (Spec 6 schema extension), so `place_landmarks` writes `fascia_bone` at placement time and a subsequent bind uses it.

The bind operator's logic per landmark:
1. If `fascia_bone` is set and a bone of that name exists in `fascia_armature`, bind to it.
2. Else, auto-find the nearest bone (nearest point on any bone segment) and bind to it; write the chosen bone name back to `fascia_bone`.
3. Else (no armature, or no bones), skip with an error report.

---

## 3. Architectural decisions (read before changing anything)

1. **Bone-parenting via the `parent_set` operator, not manual matrix math.** The operator `bpy.ops.object.parent_set(type='BONE', keep_transform=True)` is the documented, tested way to bone-parent an object while preserving world position. Manual `parent`/`parent_bone`/`parent_type`/`matrix_parent_inverse` assignment is fragile (the bone-world-matrix formula is easy to get wrong and varies across Blender versions). Use the operator with a `temp_override` for context. Target is Blender 4.0+, so `temp_override` is available.
2. **Muscle parenting uses the same operator** (`parent_set(type='OBJECT', keep_transform=True)`) with the origin landmark as the active object. Same reasoning — let Blender handle the inverse.
3. **`fascia_armature` is a PointerProperty, not a string path.** A pointer is type-safe (only Armature objects can be picked), survives rename of the armature object (Blender updates pointers), and gives the panel a clean search field. The LLM sets it via `scene.fascia_armature = bpy.data.objects["Rig"]`.
4. **`fascia_bone` is a per-landmark custom property (string), not a Scene property.** Bone binding is per-landmark, so the data lives on the landmark empty. The LLM sets `empty["fascia_bone"] = "Femur_R"` directly. The bind operator reads and writes it.
5. **Muscles are parented to their origin landmark at generation time**, not in a separate operator. `generate_muscles` already knows the `from_obj` (origin landmark) and creates the muscle at p1. Adding the parent there is one operator call. Regeneration is already required for Spec 4 pinning to take effect — Spec 7 piggybacks on the same regeneration requirement.
6. **The flex code must read world rotation from `matrix_world`, not `rotation_quaternion`.** Line 443-447 of `fascia_addon.py` has the comment `# rotation_quaternion is world rotation (muscles are unparented)`. Once muscles are parented to landmarks, `rotation_quaternion` is LOCAL rotation; the world rotation is `m.matrix_world.to_quaternion()` (or `m.matrix_world.decompose()[1]`). This is a correctness fix that must ship with Spec 7 — without it, the skin-push axis is wrong whenever a muscle is parented.
7. **Force a depsgraph update before reading parented muscle transforms.** Unparented muscles have `matrix_world` = local transform directly (always current). Parented muscles have `matrix_world` computed from the parent chain, which may be stale until the depsgraph evaluates. Add `context.view_layer.update()` (or `context.evaluated_depsgraph_get().update()`) at the start of the skin-push section in `update_flex`. This is the cost of parenting — paid once per flex update, not per vertex.
8. **Auto-bind uses nearest point on bone segment, not nearest bone head.** Horse bones are long (femur, humerus). A landmark like "MidBack" may be closest to the middle of a vertebral bone, not its head. The nearest-point-on-segment test (projection of landmark onto each bone's head→tail line, clamped to [0,1]) is correct for both joint and mid-shaft landmarks. It is O(landmarks × bones) — cheap for the horse (19 × ~80 bones).
9. **Landmarks without a rig stay mesh-parented.** If `fascia_armature` is None, the bind operator does nothing and landmarks keep their existing base-mesh parent (current behaviour). This keeps the no-rig workflow (placeholder horse, no armature) identical to today.
10. **Clear binding restores mesh-parenting, not "no parent".** `fascia.clear_rig_binding` unparents landmarks from bones AND re-parents them to the base mesh (with `matrix_parent_inverse` preserving world position), so the default state is restored. Otherwise cleared landmarks would float in world space.
11. **The horse species JSON does NOT gain `bone` fields.** No horse rig ships with the add-on (the placeholder horse has no armature). The `bone` field is an optional schema extension for LLM-authored species that ship with a rig. The schema tolerates a missing `bone` field (auto-bind handles it).
12. **Do not overclaim.** This spec delivers landmark→bone binding + muscle→landmark parenting + the flex correctness fix. It does NOT deliver: muscle tracking of the insertion landmark (still a gap at insertion — see §7), tangential skin sliding, antagonist pairing, or a rig autorigger. The contraction is still geometric volume-preserving, not FEM (rule 13).

---

## 4. The exact changes

### 4a. New Scene property `fascia_armature`

In `register()`, after `fascia_species_path`:

```python
    bpy.types.Scene.fascia_armature = bpy.props.PointerProperty(
        name="Rig",
        description="Armature object to bind landmarks to. None = landmarks stay parented to the base mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
    )
```

In `unregister()`, before the existing `del bpy.types.Scene.fascia_*` lines:

```python
    del bpy.types.Scene.fascia_armature
```

### 4b. New helper `_find_nearest_bone`

Insert after `_load_species` (around line 110). This finds the closest bone to a world-space point by projecting onto each bone segment.

```python
def _find_nearest_bone(armature, world_point):
    """Find the bone in armature whose segment (head→tail) is
    closest to world_point. Returns (bone_name, distance) or
    (None, inf) if the armature has no bones.

    Distance is computed by projecting world_point onto each
    bone's head→tail line segment (clamped to [0,1]) and
    measuring the distance to the projected point. Bone head
    and tail are converted to world space via the armature's
    matrix_world.

    Used by the auto-bind operator (Spec 7) to pick a bone for
    each landmark when the LLM has not set fascia_bone explicitly.
    """
    bones = armature.data.bones
    if not bones:
        return None, float('inf')

    pt = mathutils.Vector(world_point)
    best_name = None
    best_dist = float('inf')
    arm_mat = armature.matrix_world

    for bone in bones:
        # bone.head_local / bone.tail_local are in armature space
        head_w = arm_mat @ bone.head_local
        tail_w = arm_mat @ bone.tail_local
        seg = tail_w - head_w
        seg_len_sq = seg.length_squared
        if seg_len_sq < 1e-12:
            # Zero-length bone: distance to head
            d = (head_w - pt).length
        else:
            t = ((pt - head_w).dot(seg)) / seg_len_sq
            t = max(0.0, min(1.0, t))
            closest = head_w + seg * t
            d = (closest - pt).length
        if d < best_dist:
            best_dist = d
            best_name = bone.name

    return best_name, best_dist
```

### 4c. New helper `_bone_parent_object`

Wraps the bone-parenting operator with correct context. Used by both the bind operator and (not directly) by clear-binding's mesh-reparent. Lives next to `_find_nearest_bone`.

```python
def _bone_parent_object(empty, armature, bone_name):
    """Bone-parent empty to bone_name on armature, preserving
    the empty's current world position (keep_transform=True).

    Uses bpy.ops.object.parent_set(type='BONE') via temp_override,
    which is the documented Blender 4.0+ way to bone-parent with
    correct matrix_parent_inverse. Manual matrix math is fragile
    across versions; the operator is tested.

    Sets empty['fascia_bone'] = bone_name as metadata.
    Returns True on success, False on failure (e.g. bone missing).
    """
    if bone_name not in armature.data.bones:
        return False

    # Select only the empty + armature, armature active
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    empty.select_set(True)
    bpy.context.view_layer.objects.active = armature

    with bpy.context.temp_override(
        view_layer=bpy.context.view_layer,
        active_object=armature,
        selected_editable_objects=[armature, empty],
        object=armature,
    ):
        bpy.ops.object.parent_set(type='BONE', keep_transform=True)

    empty["fascia_bone"] = bone_name
    return True


def _object_parent_object(child, parent):
    """Object-parent child to parent, preserving child's world
    transform (keep_transform=True). Used to parent muscles to
    their origin landmark (Spec 7)."""
    bpy.ops.object.select_all(action='DESELECT')
    parent.select_set(True)
    child.select_set(True)
    bpy.context.view_layer.objects.active = parent

    with bpy.context.temp_override(
        view_layer=bpy.context.view_layer,
        active_object=parent,
        selected_editable_objects=[parent, child],
        object=parent,
    ):
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
```

### 4d. New operator `FASCIA_OT_bind_landmarks_to_rig`

Insert after `FASCIA_OT_place_landmarks` (around line 788). This is the main bind operator.

```python
class FASCIA_OT_bind_landmarks_to_rig(bpy.types.Operator):
    bl_idname = "fascia.bind_landmarks_to_rig"
    bl_label = "Bind Landmarks to Rig"
    bl_description = "Bone-parent every landmark to the nearest bone in the chosen armature (or to its fascia_bone if set)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        armature = context.scene.fascia_armature
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "No armature selected — set the Rig property first")
            return {"CANCELLED"}

        landmarks = [obj for obj in bpy.data.objects
                     if obj.get("fascia_type") == "landmark"]
        if not landmarks:
            self.report({'ERROR'}, "No landmarks found — place landmarks first")
            return {"CANCELLED"}

        bound = 0
        skipped = 0
        for lm in landmarks:
            # Explicit bone name wins; else auto-find nearest
            bone_name = lm.get("fascia_bone", "")
            if not bone_name:
                bone_name, _ = _find_nearest_bone(armature, lm.matrix_world.translation)
            if not bone_name:
                skipped += 1
                continue
            ok = _bone_parent_object(lm, armature, bone_name)
            if ok:
                bound += 1
            else:
                skipped += 1

        # Restore the user's active object (the operator changed it)
        context.view_layer.update()
        self.report({'INFO'},
                    str(bound) + " landmarks bound to rig (" + str(skipped) + " skipped)")
        return {"FINISHED"}
```

### 4e. New operator `FASCIA_OT_clear_rig_binding`

Insert after the bind operator. Restores the default mesh-parented state.

```python
class FASCIA_OT_clear_rig_binding(bpy.types.Operator):
    bl_idname = "fascia.clear_rig_binding"
    bl_label = "Clear Rig Binding"
    bl_description = "Unparent landmarks from bones and re-parent them to the base mesh (restores default state)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        body = _get_base_mesh()
        landmarks = [obj for obj in bpy.data.objects
                     if obj.get("fascia_type") == "landmark"]

        cleared = 0
        for lm in landmarks:
            # Unparent from bone
            lm.parent = None
            lm.parent_type = 'OBJECT'
            lm.parent_bone = ""
            lm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            # Clear the bone-name metadata
            if "fascia_bone" in lm:
                del lm["fascia_bone"]
            # Re-parent to base mesh if we have one (default state)
            if body:
                # Preserve world position via parent_set
                bpy.ops.object.select_all(action='DESELECT')
                body.select_set(True)
                lm.select_set(True)
                bpy.context.view_layer.objects.active = body
                with bpy.context.temp_override(
                    view_layer=context.view_layer,
                    active_object=body,
                    selected_editable_objects=[body, lm],
                    object=body,
                ):
                    bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
            cleared += 1

        context.view_layer.update()
        self.report({'INFO'}, str(cleared) + " landmarks unbound (re-parented to base mesh)")
        return {"FINISHED"}
```

### 4f. Modify `generate_muscles` — parent each muscle to its origin landmark

In both the bilateral branch (after line 909, after storing `fascia_rest_length`) and the midline branch (after line 939), add the parenting call. The muscle's world transform must be preserved (it was just placed at p1 with the correct rotation).

In the bilateral branch, after:
```python
                    obj["fascia_rest_length"] = (p2 - p1).length
```
add:
```python
                    # Spec 7: parent muscle to its origin landmark so it
                    # follows the landmark (which follows the rig bone).
                    # keep_transform=True preserves the just-set world transform.
                    _object_parent_object(obj, from_obj)
```

In the midline branch, after:
```python
                obj["fascia_rest_length"] = (p2 - p1).length
```
add:
```python
                # Spec 7: parent muscle to its origin landmark.
                _object_parent_object(obj, from_obj)
```

### 4g. Fix `update_flex` — world rotation + depsgraph update

Two surgical edits in the skin-push section.

**Edit 1 (line ~428, start of the muscle_info loop):** add a depsgraph update so parented muscle transforms are current:

Before:
```python
    muscle_info = []
    for m in muscles:
```
add:
```python
    # Spec 7: muscles may now be parented to landmarks (which are
    # bone-parented). matrix_world is computed from the parent chain
    # and may be stale until the depsgraph evaluates. Force an update
    # once before reading any parented muscle transforms.
    context.view_layer.update()
```

**Edit 2 (line ~447):** read world rotation from `matrix_world`, not `rotation_quaternion`:

Before:
```python
            origin = m.matrix_world.translation.copy()
            axis = (m.rotation_quaternion @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
```
after:
```python
            origin = m.matrix_world.translation.copy()
            # Spec 7: rotation_quaternion is LOCAL rotation; once muscles
            # are parented to landmarks, world rotation must come from
            # matrix_world. For unparented (legacy) muscles matrix_world
            # rotation == rotation_quaternion, so this is backward-compatible.
            world_rot = m.matrix_world.to_quaternion()
            axis = (world_rot @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
```

Also update the comment on line 443 from:
```python
            # rotation_quaternion is world rotation (muscles are unparented)
```
to:
```python
            # matrix_world.to_quaternion() gives world rotation for both
            # parented (Spec 7) and unparented (legacy) muscles.
```

### 4h. Panel — add a Rig section

In `FASCIA_PT_main_panel.draw`, after the Anatomy section (after the landmark/muscle count row, before the Simulation section), add:

```python
        # ── Rig section (Spec 7) ──────────────────────────────
        layout.separator()
        layout.label(text="Rig:")
        layout.prop(scene, "fascia_armature", text="Rig")
        if scene.fascia_armature:
            layout.operator("fascia.bind_landmarks_to_rig", icon="ARMATURE_DATA")
            layout.operator("fascia.clear_rig_binding", icon="X")
```

### 4i. Classes tuple — add the two new operators

In the `classes` tuple (around line 1159), add `FASCIA_OT_bind_landmarks_to_rig` and `FASCIA_OT_clear_rig_binding`. Place them after `FASCIA_OT_place_landmarks` and `FASCIA_OT_generate_muscles` (registration order: PropertyGroup → UIList → Operators → Panel; operator order among themselves is not load-order-sensitive, but grouping logically helps).

### 4j. Optional: species JSON schema extension

The `_load_species` helper (line 86) returns `data["landmarks"]` as-is. If a landmark entry has a `"bone"` field, it survives into `landmarks_data[name]["bone"]`. In `place_landmarks`, after setting `fascia_landmark`/`fascia_side`, add:

```python
                    if "bone" in data:
                        empty["fascia_bone"] = data["bone"]
```

in both the bilateral and midline branches. This is a 2-line addition per branch. The horse species file is NOT modified (no `bone` fields) — the extension is for LLM-authored species that ship with a rig.

---

## 5. What you must NOT change

- Do NOT change the volume-preserving scale math (`ls_i = 1.0 - c_i`, `ts_i = 1.0 / sqrt(ls_i)`, `obj.scale = (ts, ts, ls)`). Spec 7 only changes WHERE the muscle is and HOW its world transform is read, not the contraction itself.
- Do NOT change shape-key safety rules. `Live_Flex` is still the only place live flex data goes when shape keys exist; `Basis` is never written to; baked frames still capture flexed data before creating Basis.
- Do NOT change the bake pipeline (`FASCIA_OT_bake_flex_pose`) or `FASCIA_OT_simulate_motion`.
- Do NOT change `HORSE_LANDMARKS`, `HORSE_MUSCLES`, or `species/equine_horse.json`. The schema extension in 4j tolerates a missing `bone` field; the horse file does not add one.
- Do NOT change `_load_species`'s validation logic. The `bone` field is optional and passes through as-is.
- Do NOT change the landmark placement math (UVW→bounding-box mapping). Spec 7 only adds post-placement parenting.
- Do NOT change the existing `fascia_species_path` property, the `fascia_recruitment` CollectionProperty, or any Spec 5 UIList code.
- Do NOT add a rig autorigger, an armature generator, or any bone-creation logic. The rig comes from the user/LLM via Blender's native tools (rule 10).
- Do NOT add muscle insertion tracking (Track To / Stretch To constraints pointing at the insertion landmark). That is a follow-on (Spec 8 candidate). The gap at insertion remains, as documented in §7.
- Do NOT change the registration/unregistration order of existing classes or properties.
- Do NOT add new imports beyond what is already imported (`bpy`, `bmesh`, `mathutils` are all used; `json`/`os` were added by Spec 6).

---

## 6. Verification

After the edit: reload the add-on in Blender. Prepare a scene with: (a) the placeholder horse base mesh (Tool 1), (b) landmarks placed (Tool 3), (c) muscles generated (Tool 4), and (d) a simple armature in the scene (a single bone is enough for the basic checks; a 3-bone chain for the rotation check).

1. **No armature set → behaviour identical.** With `scene.fascia_armature` unset, click "Generate Muscles" → muscles appear at the same positions as before Spec 7. Drag Flex → contraction + skin bulge identical to pre-Spec-7 (the depsgraph update on line ~428 is a no-op when nothing is parented). This is the regression check.

2. **Auto-bind attaches every landmark to a bone.** Set `scene.fascia_armature` to a 3-bone armature positioned near the horse. Click "Bind Landmarks to Rig" → status reads "N landmarks bound to rig (0 skipped)" where N = landmark count. Every landmark empty now has `parent_type='BONE'` and a non-empty `fascia_bone` property. Verify via Python: `all(o.parent_type=='BONE' and o.get('fascia_bone') for o in bpy.data.objects if o.get('fascia_type')=='landmark')` → True.

3. **Bone rotation moves the bound landmark.** Rotate one bone (e.g. 45° around Z) in Pose Mode. The landmark(s) bound to that bone move with it — the world-space distance from the landmark to its bone's head changes by the rotation (it stays at the same offset, just rotated). Verify: record landmark world position before, rotate bone, record after — position changes. Rotate back — landmark returns to original position (no drift).

4. **Muscles follow their origin landmark.** After binding + generating muscles, rotate a bone that a muscle's origin landmark is bound to. The muscle moves with the landmark (its `matrix_world.translation` changes). The muscle's world rotation also changes (it rotates with the bone, because the muscle is parented to the landmark which is bone-parented). Verify via Python: `m = bpy.data.objects["Fascia_Muscle_Quadriceps_L"]; before = m.matrix_world.translation.copy(); <rotate bone>; after = m.matrix_world.translation.copy(); before != after`.

5. **Skin push follows the moved muscle.** With Flex > 0, rotate a bone. The skin bulge from the muscle on that bone moves with the muscle. Visual check: the bulge appears in the new location, not the old one. This depends on the line-428 depsgraph update — if it's missing, the bulge stays at the old position (regression).

6. **Explicit bone name overrides auto-bind.** Set `bpy.data.objects["Fascia_LM_HipJoint_L"]["fascia_bone"] = "Femur_L"` (or whatever a bone is named). Click "Bind Landmarks to Rig" → that landmark binds to "Femur_L" even if another bone is closer. Verify: `o.parent_bone == "Femur_L"` for that landmark.

7. **Clear binding restores mesh-parenting.** Click "Clear Rig Binding" → all landmarks have `parent_type='OBJECT'`, `parent` = base mesh, no `fascia_bone` property. Verify via Python: `all(o.parent_type=='OBJECT' and o.parent == body and 'fascia_bone' not in o for o in landmarks)` → True. Landmark world positions unchanged by the clear (keep_transform on the re-parent).

8. **Legacy unparented muscles still work.** Generate muscles with the OLD addon, then reload the NEW addon and drag Flex without regenerating. The legacy muscles have no parent → `matrix_world.to_quaternion()` == `rotation_quaternion` (backward-compatible), the depsgraph update is a no-op for them, skin push works as before. (This is the no-regression check for the rotation read change.)

9. **Volume preservation holds with parented muscles.** Generate muscles (Spec 7 parenting active), set Flex=1, set recruitment=1 for a muscle. Verify `m.scale == (1.1547, 1.1547, 0.75)` (within 1e-3) and the volume product `scale[0]*scale[1]*scale[2]` ≈ 1.0. Parenting does not affect local scale, so this must hold.

Report: checks 1, 8, 9 are the no-regression gates (must pass). Checks 2-7 are the new functionality (must pass). Check 5 is the visual end-to-end (bone → landmark → muscle → skin chain).

---

## 7. Known limitations (must be documented in code comments, NOT hidden)

- **Muscle does not track its insertion landmark.** The muscle is parented to its ORIGIN landmark only. When the insertion bone moves, the muscle's far end does NOT move toward the new insertion position — the muscle translates + reorients with its ORIGIN bone only. The gap at the insertion (Spec 4) becomes a "gap + wrong angle at insertion" until a follow-on adds a Track To / Stretch To constraint pointing the muscle at its insertion landmark. This is the documented v0 scope boundary, not a bug.
- **Landmark offset is fixed at bind time.** A landmark bound to the middle of a bone shaft stays at the same relative offset on the bone — it does not slide along the bone as the joint flexes. Real anatomy has sliding (e.g. the patella tracks the trochlear groove), but that requires tangential skin-sliding-tier logic, out of scope here.
- **Auto-bind picks the geometrically nearest bone, not the anatomically correct one.** If two bones are equidistant from a landmark (e.g. at a joint), auto-bind may pick the "wrong" one. The LLM/user can override with `fascia_bone`. Auto-bind is a convenience, not a guarantee.
- **Bone parenting is rigid (no stretch).** A bone-parented landmark follows the bone's full transform (position + rotation + scale). If the rig uses stretchy bones, the landmark scales too — which is probably wrong for an anatomical point. Use non-stretchy bones for the rig, or accept the limitation.
- **No rig autorigger.** The armature comes from the user/LLM (via Blender's native rigging tools, rule 10). Fascia does not create bones.
- **No Pose Mode integration in the bind operator.** The bind operator works in Object Mode (it parents empties to bones, which is an Object Mode operation). It does not read or set pose transforms. The landmark follows the bone's REST position + any pose transform applied to the armature (standard Blender bone-parenting behaviour).
- **`context.view_layer.update()` on every flex update.** The depsgraph update at line ~428 is O(scene) per flex slider drag. On a 748k-vertex mesh this is already slow due to the pure-Python skin-push loop (existing limitation); the depsgraph update adds a small constant cost. Acceptable for v0; revisit when the skin-push loop is accelerated (memory.md §10 item 6).
- **Clear binding does not unbind muscles.** `clear_rig_binding` only unbinds landmarks (restores mesh-parenting). Muscles stay parented to their origin landmark until regenerated. Re-running Generate Muscles after clear rebuilds them unparented-to-landmark? No — Generate Muscles always parents to the origin landmark (Spec 7 behaviour). To get unparented muscles, the user must clear the landmark binding AND regenerate (the new muscles parent to the now-mesh-parented landmark, which is fine — mesh-parenting is the default).

These are honest scope boundaries, not bugs. Do NOT silently work around them.

---

## 8. Deliverable back to the captain

- The updated `fascia_addon.py` written to `C:\Projects\Fascia\fascia_addon.py`.
- A short note confirming:
  - Only the 10 locations in section 4 were changed (4a property, 4b-4c helpers, 4d-4e operators, 4f muscle parenting, 4g flex fix, 4h panel, 4i classes tuple, 4j optional species extension).
  - The verification results from section 6 (especially the no-regression checks 1, 8, 9).
  - That the "muscle does not track insertion" limitation (§7 bullet 1) is documented in a code comment on the muscle-parenting line in `generate_muscles`.

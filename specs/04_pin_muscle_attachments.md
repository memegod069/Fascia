# SPEC 04 — Pin Muscle Attachments

**Target executor:** DeepSeek.
**Scope:** Surgical change to `create_muscle_mesh` (pivot + geometry offset), two one-line additions in `FASCIA_OT_generate_muscles` (store rest length), and the skin-push center computation in `update_flex`. Does NOT touch the volume-preserving scale math, the falloff/influence-radius/push-direction logic, shape-key safety, the backup system, `HORSE_MUSCLES`/`HORSE_LANDMARKS` data, or any operator registration.
**Estimated size:** ~30 lines changed across 4 locations in `fascia_addon.py`.

---

## 1. Why this change is needed

The volume-preserving contraction from Spec 03 is physically correct in *shape* (shorten + bulge, `V = π·r²·L` constant) but physically wrong in *where it shortens from*. `create_muscle_mesh` places each muscle's **object origin at the midpoint** of the two landmarks (file line ~508):

```python
    midpoint = (p1 + p2) / 2.0
    obj.location = midpoint
```

`update_flex` then scales local Z by `length_scale = (1 − c)`. Because the transform pivot is the midpoint, the muscle shortens **symmetrically toward its midpoint** — both endpoints drift inward, away from their origin/insertion landmarks. At flex=1 both ends have pulled in by 12.5% of rest length, leaving visible gaps at *both* landmarks. A real muscle anchors its origin and pulls its insertion toward that origin; it does not collapse toward its own center.

This is the documented Spec-03 known limitation ("attachments not pinned"), and it is the prerequisite blocker for per-muscle controls, antagonist pairing, and correct skin sliding — all of which assume a muscle that shortens from a fixed origin.

---

## 2. The pinned-attachment model

A muscle has a `from` landmark (anatomical **origin**, p1) and a `to` landmark (**insertion**, p2), already stored in `HORSE_MUSCLES` and recorded on each muscle object as `fascia_origin` / `fascia_insertion` (landmark object names).

**Rule: pin at the `from` landmark (origin) for every muscle.** The origin end stays exactly on p1 at all flex values. The muscle shortens by `length_scale = (1 − c)`, so the insertion end moves from p2 toward p1. The insertion landmark itself is a static marker and does not move (there is no rig yet); the muscle's far end simply no longer reaches it, leaving a gap at the insertion equal to `rest_length · c`. This is anatomically honest for a static-landmark v0: in a real creature the joint would flex and close that gap; with no rig, shortening the geometry from the insertion side is the correct approximation.

Thickness still bulges by `thickness_scale = 1/√(1−c)`, volume product stays exactly 1.0. **The scale math from Spec 03 does not change at all** — only the pivot moves, which makes the same scales pin the origin instead of collapsing the center.

**At rest (flex=0) the muscle must look IDENTICAL to before.** The geometry is offset in local space so it spans local Z ∈ [0, +length] (instead of [−length/2, +length/2]) and the object is placed at p1; at scale=(1,1,1) the two ends still sit exactly on p1 and p2. Only the transform pivot has moved from the midpoint to p1. This is an acceptance criterion (section 6).

---

## 3. Architectural decisions (read before changing anything)

1. **Pin at `from` (origin) for all muscles.** One consistent rule, uses the `from`/`to` data already in `HORSE_MUSCLES`. Per-muscle choice of which end pins is future work (per-muscle controls spec). Do NOT add a per-muscle flag now.
2. **Insertion shortens toward origin; gap at insertion is expected and correct.** Do NOT try to pin both ends — that forbids shortening and breaks volume preservation. Do NOT add non-uniform belly bowing to absorb the shortening — that is a skin-sliding-tier refinement, out of scope here.
3. **At-rest appearance is identical to pre-change.** The local-space geometry offset compensates exactly for the pivot move. Verify this (section 6, check 2). If the muscle looks different at flex=0, the offset is wrong.
4. **Volume-preserving scale math is UNTOUCHED.** `scale = (thickness_scale, thickness_scale, length_scale)` stays. The pivot relocation does the pinning for free. Volume product must remain 1.0.
5. **Skin-push center must track the moving flexed belly, not the origin.** With the pivot now at p1, `m.matrix_world.translation` is the origin end, not the belly — if left unchanged the bulge would concentrate at the attachment, visibly wrong. Compute the current center from the muscle's own transform + a stored rest length + the current `length_scale`. Derive the world axis from `rotation_quaternion` (muscles are unparented, so this is world rotation and is unaffected by object scale) — this matches the existing pattern of reading transforms without forcing a depsgraph update.
6. **Store `fascia_rest_length` at generation.** One new world-space scalar per muscle, alongside the existing `fascia_radius`. Do NOT store origin/axis vectors — re-derive them from the muscle's own transform at flex time (robust to the muscle being rotated, no redundant stale data).
7. **Legacy fallback.** Muscles generated before this change have no `fascia_rest_length` and their pivot is still at the midpoint. In `update_flex`, if `fascia_rest_length` is missing, fall back to the old center (`matrix_world.translation`) so pre-regeneration muscles don't render with a badly misplaced bulge. Regeneration is still required for pinning to actually take effect (old pivots stay at the midpoint).
8. **Regeneration required.** Existing muscle objects were built with the midpoint pivot. After this change the user (and the architect's verification) must re-run **Generate Muscles** to rebuild them with pinned origins. The operator already deletes and recreates muscles, so no new cleanup logic is needed.
9. **Do not overclaim.** Code comments must state what this does (origin pinned, insertion shortens toward origin) AND what it does not do (insertion not pinned to a moving bone — no rig; no per-muscle pin choice; no antagonist relaxation). See section 7.

---

## 4. The exact changes

### 4a. `create_muscle_mesh` — offset geometry to local Z ∈ [0, +length] and place origin at p1

Find this block (currently ~lines 484–509):

```python
    bm = bmesh.new()

    # Step 1: Make a sphere (12 segments around, 6 rings top-to-bottom)
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=1.0)

    # Step 2: Squash it in LOCAL space — thin on X/Y (thickness), long on Z (length).
    # This stays baked into the geometry so the base shape is correct.
    scale_mat = mathutils.Matrix.Diagonal((radius, radius, length / 2.0, 1.0))
    bmesh.ops.transform(bm, matrix=scale_mat, verts=bm.verts)

    # NOTE: We do NOT rotate or translate the geometry here.
    # Instead, we'll set the object's location and rotation below.
    # This is what makes flex scaling work correctly.

    # Convert bmesh into a real Blender mesh object
    mesh_data = bpy.data.meshes.new(name)
    bm.to_mesh(mesh_data)
    mesh_data.update()
    bm.free()

    obj = bpy.data.objects.new(name, mesh_data)
    bpy.context.collection.objects.link(obj)

    # Step 3: Position the muscle at the midpoint between the two landmarks
    midpoint = (p1 + p2) / 2.0
    obj.location = midpoint
```

Replace the whole block with:

```python
    bm = bmesh.new()

    # Step 1: Make a sphere (12 segments around, 6 rings top-to-bottom)
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=1.0)

    # Step 2: Squash it in LOCAL space — thin on X/Y (thickness), long on Z (length).
    # This stays baked into the geometry so the base shape is correct.
    scale_mat = mathutils.Matrix.Diagonal((radius, radius, length / 2.0, 1.0))
    bmesh.ops.transform(bm, matrix=scale_mat, verts=bm.verts)

    # Step 2b: Offset the geometry so local Z spans [0, +length] instead of
    # [-length/2, +length/2]. Combined with placing the object origin at the
    # FROM landmark (p1, the muscle's anatomical ORIGIN) below, this PINS the
    # origin end: scaling local Z by (1-c) during contraction keeps local Z=0
    # fixed at p1 and pulls the insertion end (local Z=+length) toward p1.
    # At rest (scale=1) the geometry is identical to the old midpoint-pivot
    # version — only the transform pivot has moved from the midpoint to p1.
    bmesh.ops.translate(bm, vec=(0.0, 0.0, length / 2.0), verts=bm.verts)

    # NOTE: We do NOT rotate or further translate the geometry here.
    # Instead, we'll set the object's location and rotation below.
    # This is what makes flex scaling work correctly AND pins the origin.

    # Convert bmesh into a real Blender mesh object
    mesh_data = bpy.data.meshes.new(name)
    bm.to_mesh(mesh_data)
    mesh_data.update()
    bm.free()

    obj = bpy.data.objects.new(name, mesh_data)
    bpy.context.collection.objects.link(obj)

    # Step 3: Place the muscle's OBJECT ORIGIN at the FROM landmark (p1),
    # the muscle's anatomical ORIGIN (attachment). The geometry spans local
    # Z in [0, +length], so at rest the near end sits on p1 (pinned origin)
    # and the far end sits on p2 (insertion). The Step 4 rotation orients
    # local +Z from p1 toward p2.
    obj.location = p1
```

The Step 4 rotation block immediately after (lines ~511–518) is **unchanged** — local +Z still maps to the `p2 − p1` direction. Do not touch it.

### 4b. Store `fascia_rest_length` on each muscle at generation

In `FASCIA_OT_generate_muscles`, the **bilateral branch** currently sets (around lines 786–789):

```python
                    # Store the muscle's WORLD-SPACE base thickness (fraction * base_size)
                    # so the flex slider's growth math (m_radius * (thickness_scale - 1))
                    # works in consistent world units.
                    obj["fascia_radius"] = mdata["radius"] * base_size
```

Replace with:

```python
                    # Store the muscle's WORLD-SPACE base thickness (fraction * base_size)
                    # so the flex slider's growth math (m_radius * (thickness_scale - 1))
                    # works in consistent world units.
                    obj["fascia_radius"] = mdata["radius"] * base_size
                    # Store the rest length (world units) so update_flex can locate the
                    # muscle's CURRENT belly center as the insertion end shortens toward p1.
                    obj["fascia_rest_length"] = (p2 - p1).length
```

The **midline branch** currently sets (around lines 814–818):

```python
                obj["fascia_type"] = "muscle"
                obj["fascia_muscle_name"] = muscle_name
                obj["fascia_origin"] = "Fascia_LM_" + from_key
                obj["fascia_insertion"] = "Fascia_LM_" + to_key
                obj["fascia_radius"] = mdata["radius"] * base_size
```

Replace with:

```python
                obj["fascia_type"] = "muscle"
                obj["fascia_muscle_name"] = muscle_name
                obj["fascia_origin"] = "Fascia_LM_" + from_key
                obj["fascia_insertion"] = "Fascia_LM_" + to_key
                obj["fascia_radius"] = mdata["radius"] * base_size
                obj["fascia_rest_length"] = (p2 - p1).length
```

### 4c. `update_flex` — skin-push center tracks the flexed belly, not the origin

Find this block in `update_flex` (currently ~lines 374–378):

```python
    muscle_info = []
    for m in muscles:
        center = m.matrix_world.translation.copy()
        radius = m.get("fascia_radius", 0.04)
        muscle_info.append((center, radius))
```

Replace with:

```python
    muscle_info = []
    for m in muscles:
        rest_length = m.get("fascia_rest_length", None)
        if rest_length is None:
            # Legacy muscle (generated before attachment pinning): its pivot
            # is still at the midpoint, so matrix_world.translation IS the
            # belly center. Keeps pre-regeneration muscles from rendering with
            # a misplaced bulge; regeneration is still required for pinning.
            center = m.matrix_world.translation.copy()
        else:
            # Pinned muscle: object origin is at the FROM landmark (p1), so
            # matrix_world.translation is the ORIGIN END, not the belly.
            # Compute the current (flexed) belly center from the origin + the
            # world-space local-Z axis + rest length + current length scale.
            # rotation_quaternion is world rotation (muscles are unparented)
            # and is unaffected by object scale, so the axis is always current
            # without forcing a depsgraph update.
            origin = m.matrix_world.translation.copy()
            axis = (m.rotation_quaternion @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
            center = origin + axis * (rest_length * length_scale * 0.5)
        radius = m.get("fascia_radius", 0.04)
        muscle_info.append((center, radius))
```

`length_scale` is the local variable computed earlier in `update_flex` (Spec 03, Step 1) and is in scope here. At flex=0 (`length_scale=1`) this reduces to `origin + axis · rest_length/2` = the rest midpoint, identical to the old value, so rest behaviour is unchanged.

---

## 5. What you must NOT change

- Do NOT change the volume-preserving scale assignment (`obj.scale[0/1/2] = thickness/thickness/length_scale`). The pivot relocation does the pinning; the scales stay.
- Do NOT change the skin-push falloff (`(1.0 - t) ** 2`), the influence radius, the push direction (`delta.normalized()`), or the growth formula (`m_radius * (thickness_scale - 1.0)`). Only the center point changes.
- Do NOT change `HORSE_MUSCLES` radii, `HORSE_LANDMARKS`, or `MAX_CONTRACTION` / `MUSCLE_INFLUENCE_FRACTION`.
- Do NOT touch shape-key logic, the backup system, `_save_original_verts` / `_restore_original_verts`, or the bake capture order.
- Do NOT touch `FASCIA_OT_simulate_motion` or `FASCIA_OT_bake_flex_pose` — they call `update_flex` and inherit the fix.
- Do NOT add a per-muscle pin-end flag, antagonist relaxation, or axial skin deformation.
- Do NOT add new imports — `mathutils` is already imported.
- Do NOT change any operator registration or the panel UI.

---

## 6. Verification (architect runs in Blender, one call)

After the edit: copy `fascia_addon.py` to the Blender addons dir, reload the add-on, ensure the horse is tagged as base + landmarks placed, then **re-run Generate Muscles** (required — old muscles have midpoint pivots). Then verify in a single scripted pass:

1. **Rest scale check (flex=0):** every muscle has `scale == (1.0, 1.0, 1.0)`; skin displacement = 0.
2. **Rest endpoint check (flex=0):** for 2–3 sample muscles (e.g. `GluteusMedius_R`, `Triceps_L`, `LongissimusDorsi`), the world position of the local-Z=0 end (`matrix_world @ Vector((0,0,0))`) ≈ the `fascia_origin` landmark world position, AND the local-Z=rest_length end (`matrix_world @ Vector((0,0,rest_length))`) ≈ the `fascia_insertion` landmark world position. Both distances ≈ 0. This confirms the at-rest appearance is identical to pre-change (the muscle still reaches both landmarks).
3. **Pin check (flex=1) — THE KEY CHECK:** for the same sample muscles, the local-Z=0 end still ≈ the origin landmark (distance ≈ 0, ORIGIN STAYS PINNED), and the local-Z=rest_length end has moved to `origin + axis · rest_length · 0.75`, so its distance to the insertion landmark ≈ `rest_length · 0.25` (the 25% shortening gap, on the origin side). The origin end must NOT drift.
4. **Volume check (flex=1):** sample muscles have `scale ≈ (1.1547, 1.1547, 0.75)`; product `scale[0]² · scale[2] ≈ 1.0`.
5. **Skin bulge check (flex=0.5):** displaced-vertex count and max displacement are comparable to the Spec-03 baseline (the center moved by ≤12.5% of rest length, so the bulge region shifts slightly toward the origin but stays localized).
6. **Symmetry check:** sliding flex back to 0 restores all muscles to `(1,1,1)` and skin to rest (no drift).

Report: for the 2–3 sample muscles at flex=0 and flex=1 — the origin-end→landmark distance, the insertion-end→landmark distance, the `scale` tuple, and the volume product; plus the flex=0.5 skin displacement count + max.

Sanity expectations:
- flex=0: origin-end distance ≈ 0, insertion-end distance ≈ 0 (reaches both landmarks).
- flex=1: origin-end distance ≈ 0 (PINNED), insertion-end distance ≈ `0.25 · rest_length`, scale `(1.1547, 1.1547, 0.75)`, product `1.0`.

---

## 7. Known limitations (must be documented in code comments, NOT hidden)

- **Insertion not pinned to a moving bone.** The origin is fixed at its landmark; the insertion end shortens toward the origin, leaving a gap at the insertion landmark. In a real creature the joint flexes and closes that gap; Fascia has no rig yet, so the gap is the honest static-landmark approximation. Closing it needs skeleton-driven landmarks (future work).
- **Pin end is always `from` (origin).** Every muscle pins at its `from` landmark. Per-muscle choice of which end pins is future work (per-muscle controls spec).
- **Uniform contraction.** One Flex slider still contracts every muscle by the same fraction. Per-muscle recruitment is future work.
- **Radial skin push only.** Only the radial bulge pushes the skin; the axial shortening does not directly deform the skin. Axial skin sliding near muscle ends is a future refinement (skin-sliding spec).
- **No antagonist relaxation.** All muscles contract simultaneously. Future work.

These are honest scope boundaries, not bugs. Do NOT silently work around them.

---

## 8. Deliverable back to the architect

- The updated `fascia_addon.py` written to `C:\Projects\Fascia\fascia_addon.py` (the source — the architect handles the addons-dir copy and Blender reload).
- A short note confirming only the 4 locations in section 4 were changed (4a geometry offset + pivot, 4b two rest-length stores, 4c skin-push center).
- No need to paste logs — the architect will read the file and run the section-6 verification independently.

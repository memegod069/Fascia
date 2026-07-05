# SPEC 08 — Muscle Insertion Tracking (Damped Track to Insertion Landmark)

**Target executor:** implementing agent.
**Scope:** Add a `DAMPED_TRACK` constraint on each muscle targeting its insertion landmark, so the muscle reorients toward the insertion as the rig moves. New helper `_add_insertion_track_constraint`, two call sites in `FASCIA_OT_generate_muscles` (bilateral + midline), and an updated comment on the Spec 7 muscle-parenting line. Does NOT change the volume-preserving contraction math, shape-key safety, the bake pipeline, the flex skin-push loop, species loading, rig binding, or the panel layout.
**Estimated size:** ~20 lines added/changed across 3 locations in `fascia_addon.py`.

---

## 1. Why this change is needed

Spec 7 (rig binding) wired the **bone → landmark → muscle → skin** chain on the ORIGIN side: each landmark is bone-parented, and each muscle is object-parented to its origin landmark. The documented Spec 7 §7 scope boundary (and memory.md §6 bullet 1) states:

> **Muscle tracks origin landmark only, not insertion.** The muscle is parented to its ORIGIN landmark (which is bone-parented). When the insertion bone moves independently, the muscle does not reorient toward the new insertion position — the "gap at insertion" (Spec 4) becomes a "gap + wrong angle at insertion" until a follow-on adds a Track To constraint on the muscle's far end.

This spec is that follow-on. It is memory.md §10 critical-path item #2 ("Muscle insertion tracking — closes the last remaining gap in the bone → muscle → skin chain").

The deliverable: when the captain rotates a bone that a muscle's INSERTION landmark is bound to, the muscle reorients to point at the new insertion position. The origin stays pinned (Spec 4), the direction now tracks the insertion (Spec 8), so both endpoints are correct. The full chain on BOTH ends: **bone(origin) → origin landmark → muscle origin (pinned) ... muscle direction (Damped Track) → insertion landmark → bone(insertion)**.

---

## 2. The tracking model

### 2a. Why Damped Track, not Stretch To or Track To

Three Blender constraints could "aim" a muscle at its insertion. The choice is forced by Fascia's volume-preserving contraction:

| Constraint | What it does | Compatible with Fascia's contraction? |
|------------|--------------|----------------------------------------|
| **Stretch To** | Rotates AND scales the object to reach the target. | **NO.** Stretch To overrides `obj.scale` to reach the target. Fascia's flex code sets `obj.scale = (ts, ts, ls)` for volume preservation (`ls = 1−c`, `ts = 1/√ls`). A Stretch To constraint would overwrite that scale and break `V = π·r²·L = const`. Rejected. |
| **Track To** | Rotates to point a chosen axis at the target, uses a second axis + up-target for roll. | Works, but requires choosing an up axis / up target. For a cylindrical muscle (X and Y thickness equal), roll is irrelevant — the up-axis machinery is unnecessary complexity. |
| **Damped Track** | Rotates the object the **minimal** amount to align a single chosen axis with the direction to the target. No up axis. | **YES.** Rotation only — does NOT touch `obj.scale`, so the volume-preserving `obj.scale = (ts, ts, ls)` still applies. Single axis (`TRACK_Z`) matches the muscle's length axis. Minimal rotation preserves roll where possible (irrelevant for a symmetric muscle). Cleanest fit. |

**Decision: Damped Track, `track_axis = 'TRACK_Z'`, `target = insertion landmark object`.** The muscle's local +Z is its length axis (geometry spans local Z ∈ [0, +rest_length], origin at local 0 — Spec 4). Damped Track reorients local +Z to point at the insertion. The contraction then shortens + bulges ALONG that reoriented axis. Volume preservation is untouched (constraint is rotation-only).

### 2b. What each stage of the chain now gives

```
   origin bone ──(bone parent)──> origin landmark ──(object parent)──> muscle (origin pinned at local 0)
                                                                            │
                                                                            │ DAMPED_TRACK(TRACK_Z) → insertion landmark
                                                                            ▼
                                                                     insertion bone (bone parent)
```

| End | Mechanism | What it gives | What it does NOT give |
|-----|-----------|---------------|----------------------|
| Origin (Spec 4 + 7) | Object parent to origin landmark + local-Z geometry offset | Origin end stays exactly on the origin landmark at all flex values; follows the origin bone | — |
| Insertion (Spec 8, this spec) | Damped Track on `TRACK_Z` targeting the insertion landmark | Muscle DIRECTION reorients to point at the insertion as it moves; the far end points at the (possibly moved) insertion | The far end is at `rest_length · ls` along the new direction — it does NOT stretch to exactly reach the insertion. If the insertion moved closer than `rest_length · ls`, the far end overshoots; if farther, it undershoots. This is the pre-existing Spec 4 "insertion length mismatch", NOT a new limitation (see §7). |

### 2c. Why this integrates with the existing flex code with ZERO changes to `update_flex`

Spec 7 already made two changes to `update_flex` that Spec 8 relies on, without modification:

1. **`context.view_layer.update()` at the start of the muscle_info loop** (Spec 7, §4g Edit 1) — forces the depsgraph to evaluate. Constraints evaluate during depsgraph evaluation, so the Damped Track's rotation is computed before the flex code reads `matrix_world`. No extra update needed.
2. **`world_rot = m.matrix_world.to_quaternion()`** (Spec 7, §4g Edit 2) — reads the world rotation from the evaluated `matrix_world`, which INCLUDES the Damped Track constraint's output. The skin-push axis `(world_rot @ Vector((0,0,1)))` is therefore along the muscle's CURRENT direction (toward the moved insertion), not the stale generated direction.

In other words: Spec 7's flex fix was forward-compatible with Spec 8. The skin-push axis automatically follows the Damped Track rotation. **Spec 8 touches only `generate_muscles`; it does NOT touch `update_flex`.**

### 2d. At-rest appearance is identical to pre-Spec-8

At generation, the muscle's local rotation is set so local +Z points from p1 (origin) to p2 (insertion) (`create_muscle_mesh` Step 4, line 705-712). The Damped Track constraint, when first evaluated, points local +Z at the insertion landmark — which is at p2. So the constraint's output rotation equals the generation rotation at rest. No visual change at flex=0, no bone movement. This is an acceptance criterion (§6, check 1).

---

## 3. Architectural decisions (read before changing anything)

1. **Damped Track, not Stretch To.** Stretch To overrides `obj.scale` and breaks volume preservation (§2a). This is non-negotiable — Fascia's contraction is volume-preserving geometric, not a stretch-to-target sim.
2. **`track_axis = 'TRACK_Z'`.** The muscle's local +Z is the length axis (geometry spans local Z ∈ [0, +rest_length], origin at local 0). Positive Z (not negative) because the geometry grows from local 0 (origin) toward local +rest_length (insertion). Tracking +Z at the insertion orients the muscle origin→insertion.
3. **Constraint added at generation time, always — not rig-gated.** Same pattern as Spec 7's muscle→origin parenting (`_object_parent_object` is always called in `generate_muscles`, regardless of whether a rig is bound). The muscle should ALWAYS point at its insertion, with or without a rig. At rest the constraint is a no-op visually (§2d). With no rig, if the user moves the insertion landmark manually, the muscle reorients to follow — which is strictly more correct than the pre-Spec-8 fixed-direction behaviour.
4. **No operator to toggle the constraint.** The old fixed-direction behaviour was a limitation, not a feature. There is no use case for "muscle ignores where its insertion is". If a future spec needs per-muscle opt-out, add a `fascia_track_insertion` flag then. Do NOT add a toggle now (rule 3: each tool does one clear job).
5. **No change to `clear_rig_binding`.** The Damped Track targets the insertion landmark object (by reference). After `clear_rig_binding`, the insertion landmark is re-parented to the base mesh (Spec 7 §4e) — the constraint target is still valid (it's the same object, just re-parented). The muscle continues to point at its insertion. No constraint removal on clear.
6. **No change to the flex code.** Spec 7's `context.view_layer.update()` + `matrix_world.to_quaternion()` already cover constraint-evaluated rotation (§2c). Touching `update_flex` is out of scope and unnecessary.
7. **No change to volume preservation.** Damped Track is rotation-only; `obj.scale = (ts, ts, ls)` is unaffected. Volume product stays 1.0. This is an acceptance criterion (§6, check 5).
8. **Regeneration required.** `generate_muscles` deletes and recreates all muscles (line 1023-1030). Old muscles (pre-Spec-8, no constraint) are removed on regeneration. No legacy-muscle handling needed — same as Spec 4 and Spec 7. Document this in the deliverable note.
9. **Use the data API (`obj.constraints.new`), not `bpy.ops.constraint.add`.** The operator requires constraint-context and an active object; the data API is context-free, cleaner, and matches the "precise control / avoid side effects" guidance. `obj.constraints.new(type='DAMPED_TRACK')` returns the constraint instance; set `.target` and `.track_axis` on it.
10. **Constraint named `Fascia_DampedTrack_Insertion`** so it is identifiable as Fascia-owned metadata (matches the `Fascia_` object-prefix convention; constraints don't have a `fascia_` property namespace, so the name carries the ownership).
11. **Do not overclaim.** This spec delivers muscle DIRECTION tracking of the insertion landmark. It does NOT deliver: muscle LENGTH matching the insertion distance (the far end stays at `rest_length · ls` — see §7), tangential skin sliding, antagonist pairing, or a rig autorigger. The contraction is still geometric volume-preserving, not FEM (rule 13).

---

## 4. The exact changes

### 4a. New helper `_add_insertion_track_constraint`

Insert immediately after `_object_parent_object` (around line 208, in the rig-binding helpers block). Keeps the two `generate_muscles` call sites DRY and matches the Spec 7 helper pattern.

```python
def _add_insertion_track_constraint(muscle, insertion_obj):
    """Add a Damped Track constraint on the muscle so its local +Z
    (length axis, origin→insertion) points at the insertion landmark.

    Spec 8: closes the 'wrong angle at insertion' gap from Spec 7 §7.
    Damped Track is rotation-only — it does NOT touch obj.scale, so
    the volume-preserving contraction (obj.scale = (ts, ts, ls)) is
    unaffected. Stretch To would override scale and break volume
    preservation; rejected (Spec 8 §2a).

    The constraint is added at generation time and is always on.
    At rest it is a no-op visually: the muscle already points at the
    insertion (create_muscle_mesh Step 4), so the constraint's first
    evaluation produces the same rotation. When the insertion landmark
    moves (rig pose changes), the muscle reorients to follow.

    KNOWN LIMITATION: the muscle's far end is at rest_length*ls along
    the reoriented direction — it does NOT stretch to exactly reach the
    insertion. If the insertion moved closer than rest_length*ls, the
    far end overshoots; if farther, it undershoots. This is the
    pre-existing Spec 4 insertion length-mismatch; Spec 8 fixes the
    ANGLE, not the length. Anatomically honest for a geometric
    contraction model (Fascia is not FEM, rule 13).
    """
    con = muscle.constraints.new(type='DAMPED_TRACK')
    con.name = "Fascia_DampedTrack_Insertion"
    con.target = insertion_obj
    con.track_axis = 'TRACK_Z'
    return con
```

### 4b. Modify `generate_muscles` — bilateral branch

In the bilateral branch, the Spec 7 parenting block currently reads (lines 1111-1120):

```python
                    # Spec 7: parent muscle to its origin landmark so it
                    # follows the landmark (which follows the rig bone).
                    # keep_transform=True preserves the just-set world transform.
                    # KNOWN LIMITATION: The muscle tracks its ORIGIN landmark
                    # only, not its insertion. The insertion end stays at its
                    # generated direction/length; when the insertion bone moves
                    # independently, the muscle does not reorient toward it.
                    # A Track To / Stretch To constraint follow-on would close
                    # this gap (future work).
                    _object_parent_object(obj, from_obj)
```

Replace with:

```python
                    # Spec 7: parent muscle to its origin landmark so it
                    # follows the landmark (which follows the rig bone).
                    # keep_transform=True preserves the just-set world transform.
                    _object_parent_object(obj, from_obj)

                    # Spec 8: Damped Track the muscle's local +Z (length axis)
                    # at its insertion landmark so the muscle reorients toward
                    # the insertion as the rig moves. Closes the Spec 7 §7
                    # 'wrong angle at insertion' gap. Rotation-only — volume
                    # preservation is unaffected. See _add_insertion_track_constraint.
                    _add_insertion_track_constraint(obj, to_obj)
```

`to_obj` is already in scope on line 1077 (`to_obj = bpy.data.objects.get(to_obj_name)`). No new lookup needed.

### 4c. Modify `generate_muscles` — midline branch

In the midline branch, the Spec 7 parenting line (lines 1152-1153):

```python
                # Spec 7: parent muscle to its origin landmark.
                _object_parent_object(obj, from_obj)
```

Replace with:

```python
                # Spec 7: parent muscle to its origin landmark.
                _object_parent_object(obj, from_obj)

                # Spec 8: Damped Track the muscle at its insertion landmark.
                _add_insertion_track_constraint(obj, to_obj)
```

`to_obj` is already in scope on line 1126 (`to_obj = bpy.data.objects.get("Fascia_LM_" + to_key)`). No new lookup needed.

### 4d. Update the `create_muscle_mesh` KNOWN LIMITATION comment

The comment block on lines 699-702 of `create_muscle_mesh`:

```python
    # KNOWN LIMITATION: The insertion end shortens toward the origin during
    # contraction, leaving a gap at the insertion landmark. Closing it needs
    # skeleton-driven landmarks (future rig work). Per-muscle pin-end choice
    # is also future work (per-muscle controls spec).
```

The "Closing it needs skeleton-driven landmarks (future rig work)" note is now partially resolved: Spec 7 made the landmarks skeleton-driven, and Spec 8 makes the muscle reorient toward the (now skeleton-driven) insertion. Update to reflect the remaining, narrower limitation:

```python
    # KNOWN LIMITATION: The insertion end shortens toward the origin during
    # contraction. Spec 8 adds a Damped Track constraint so the muscle
    # reorients to POINT at the (possibly moved) insertion landmark, but the
    # far end is still at rest_length*ls along that direction — it does not
    # stretch to exactly reach the insertion. The geometric length mismatch
    # (Spec 4 §2) remains; only the ANGLE is now correct. Per-muscle pin-end
    # choice is future work (per-muscle controls spec).
```

---

## 5. What you must NOT change

- Do NOT change the volume-preserving scale math (`ls_i = 1.0 - c_i`, `ts_i = 1.0 / sqrt(ls_i)`, `obj.scale = (ts, ts, ls)`). Spec 8 is rotation-only.
- Do NOT change `update_flex` — Spec 7's `context.view_layer.update()` + `matrix_world.to_quaternion()` already cover constraint-evaluated rotation (§2c).
- Do NOT change shape-key safety rules, the bake pipeline, or `FASCIA_OT_simulate_motion`.
- Do NOT change `HORSE_LANDMARKS`, `HORSE_MUSCLES`, `species/equine_horse.json`, or `_load_species`.
- Do NOT change `FASCIA_OT_bind_landmarks_to_rig` or `FASCIA_OT_clear_rig_binding`. The constraint targets the insertion landmark object, which stays valid after clear (re-parented, same object).
- Do NOT use Stretch To or Track To — Damped Track is the decision (§2a). Stretch To breaks volume; Track To needs an unnecessary up axis.
- Do NOT add a per-muscle opt-out flag, a constraint-influence slider, or a panel control for the constraint. The constraint is always on at full influence (§3, decision 4).
- Do NOT change the registration/unregistration order, the `classes` tuple (no new operators/classes in this spec), or the panel UI.
- Do NOT add new imports — `bpy` (for `obj.constraints.new`) is already imported.
- Do NOT add muscle length-stretching to reach the insertion. That is a future spec (would interact with volume preservation and is out of scope here).

---

## 6. Verification

After the edit: reload the add-on in Blender. Prepare a scene with: (a) the placeholder horse base mesh (Tool 1), (b) landmarks placed (Tool 3), (c) a simple armature in the scene (a 2-bone chain is enough: one bone for the origin landmark, one for the insertion landmark of a sample muscle). **Re-run Generate Muscles** (required — old muscles have no constraint).

1. **At-rest appearance identical (no-regression).** Generate muscles → every muscle looks the same as pre-Spec-8: origin end on origin landmark, far end on insertion landmark. Verify via Python on 2-3 sample muscles (e.g. `GluteusMedius_R`, `Triceps_L`, `LongissimusDorsi`): the local-Z=0 end (`matrix_world @ Vector((0,0,0))`) ≈ origin landmark world position (distance ≈ 0), AND the local-Z=rest_length end (`matrix_world @ Vector((0,0,rest_length))`) ≈ insertion landmark world position (distance ≈ 0). This confirms the Damped Track is a no-op at rest (§2d).

2. **Every generated muscle has the constraint.** Verify via Python: `all(any(c.type=='DAMPED_TRACK' and c.target is not None and c.track_axis=='TRACK_Z' for c in m.constraints) for m in bpy.data.objects if m.get('fascia_type')=='muscle')` → True. Constraint count per muscle == 1.

3. **Damped Track reorients the muscle when the insertion moves.** Bind landmarks to a 2-bone armature (origin landmark → bone A, insertion landmark → bone B). Rotate bone B in Pose Mode by 45°. The sample muscle's world rotation changes (its local +Z now points toward the new insertion position, not the old one). Verify: `m = bpy.data.objects["Fascia_Muscle_..."]; before = m.matrix_world.to_quaternion().copy(); <rotate bone B>; bpy.context.view_layer.update(); after = m.matrix_world.to_quaternion().copy(); before.rotation_difference(after).angle > 0.01` (the muscle reoriented).

4. **Origin stays pinned when the insertion moves (Spec 4 preserved).** After the bone-B rotation in check 3, the muscle's local-Z=0 end is STILL on the origin landmark (distance ≈ 0). The origin end did not move — only the direction changed. Verify: `origin_end = m.matrix_world @ Vector((0,0,0)); (origin_end - origin_landmark.matrix_world.translation).length < 1e-3`.

5. **Volume preservation holds (no-regression).** Generate muscles (constraint active), set Flex=1, recruitment=1 for a sample muscle. Verify `m.scale == (1.1547, 1.1547, 0.75)` (within 1e-3) and volume product `scale[0]*scale[1]*scale[2]` ≈ 1.0. The Damped Track constraint must not affect local scale. (If scale changed, the wrong constraint type was used — re-read §2a.)

6. **Skin push follows the reoriented muscle.** With Flex > 0 and bone B rotated, the skin bulge from the sample muscle appears along the muscle's NEW direction (toward the moved insertion), not the old generated direction. Visual check via the viewport, or verify the skin-push center: `origin = m.matrix_world.translation; axis = m.matrix_world.to_quaternion() @ Vector((0,0,1)); center = origin + axis * (rest_length * ls * 0.5)` — `axis` points toward the moved insertion, so `center` is along the new direction. This depends on Spec 7's `matrix_world.to_quaternion()` read (§2c); if the flex code were still reading `rotation_quaternion`, the bulge would stay along the old direction (regression — but Spec 7 already fixed this).

7. **Clear rig binding does not break the muscle.** Click "Clear Rig Binding" → landmarks re-parent to base mesh (Spec 7 behaviour). The muscle's Damped Track still targets the insertion landmark (same object, now mesh-parented). The muscle still points at its insertion. Verify: `any(c.type=='DAMPED_TRACK' for c in m.constraints)` is still True after clear; `m.matrix_world.to_quaternion()` still orients +Z at the insertion landmark position.

8. **Contraction shortens + bulges along the reoriented axis.** With bone B rotated and Flex=1, the muscle's far end (local Z = rest_length) in world space is at `origin + (reoriented axis) * rest_length * 0.75` — i.e. 75% of the way from origin toward the moved insertion direction. The muscle both reoriented (Spec 8) AND shortened (Spec 3/4) along the new direction. Verify: `far_end = m.matrix_world @ Vector((0,0,rest_length*0.75))` matches `origin + axis * rest_length * 0.75` (within 1e-3, where `axis = m.matrix_world.to_quaternion() @ Vector((0,0,1))`).

Report: checks 1, 5 are the no-regression gates (must pass). Checks 2, 3, 4, 8 are the new functionality (must pass). Check 6 is the visual end-to-end (bone → landmark → muscle → skin chain on BOTH ends). Check 7 confirms clear-binding compatibility.

---

## 7. Known limitations (must be documented in code comments, NOT hidden)

- **The muscle's far end does NOT stretch to exactly reach the insertion.** Damped Track fixes the DIRECTION (the muscle points at the insertion), not the LENGTH. The far end is at `rest_length · ls` along the reoriented direction. If the insertion moved closer than `rest_length · ls` (joint flexed), the far end overshoots past the insertion; if farther (joint extended), it undershoots. This is the pre-existing Spec 4 §2 "insertion length mismatch" — Spec 8 narrows it from "gap + wrong angle" to "length mismatch only". A future "stretch-to-insertion" spec would need to reconcile stretching with volume preservation (hard — out of scope here).
- **Damped Track singularity at 180°.** If the insertion landmark is exactly behind the origin along the muscle's -Z axis, Damped Track's minimal rotation is undefined (any 180° rotation works) and may flip unexpectedly. This is an extreme edge case (a joint folded completely back on itself). Use non-extreme poses, or accept the flip. A Track To constraint with an explicit up axis would be more robust here, but adds complexity irrelevant for cylindrical muscles (§2a).
- **Muscle roll around its long axis is not anatomically controlled.** Damped Track's minimal-rotation logic preserves the original roll as much as possible; it does not target an anatomical "up" direction. Irrelevant for Fascia's cylindrical muscles (X and Y thickness are equal, so roll is visually and mathematically a no-op). If future muscles become non-cylindrical (e.g. flat aponeuroses), a Track To with an up target would be needed.
- **The constraint is always on at full influence.** There is no per-muscle opt-out and no influence slider. The muscle always tracks its insertion, even with no rig. This is a behaviour change from pre-Spec-8 (fixed direction) but is strictly more correct (the muscle should always connect origin to insertion). A future spec can add a `fascia_track_insertion` flag if a use case appears.
- **Regeneration required.** Existing muscles (generated before this spec) have no Damped Track constraint. Re-run Generate Muscles to add it. The operator already deletes and recreates muscles, so no extra cleanup is needed.
- **Clear rig binding does NOT remove the constraint.** The Damped Track targets the insertion landmark object, which stays valid (re-parented to the base mesh) after clear. The muscle continues to point at its insertion. This is intentional (§3, decision 5).
- **No Pose Mode integration.** Same as Spec 7: the constraint evaluates against the insertion landmark's evaluated world transform, which includes any pose applied to a bone it is bone-parented to. Standard Blender constraint behaviour; no pose-reading code in Fascia.

These are honest scope boundaries, not bugs. Do NOT silently work around them.

---

## 8. Deliverable back to the captain

- The updated `fascia_addon.py` written to `C:\Projects\Fascia\fascia_addon.py`.
- A short note confirming:
  - Only the 3 locations in section 4 were changed (4a new helper, 4b-4c two call sites in `generate_muscles`, 4d updated comment in `create_muscle_mesh`).
  - `update_flex` was NOT touched (Spec 7's flex fix already covers constraint-evaluated rotation — §2c).
  - The verification results from section 6 (especially the no-regression checks 1 and 5, and the new-functionality checks 2, 3, 4, 8).
  - That the "far end does not stretch to reach the insertion" limitation (§7 bullet 1) is documented in the code comment on `_add_insertion_track_constraint` and in the updated `create_muscle_mesh` comment.

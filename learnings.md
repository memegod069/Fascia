# Fascia — Project Learnings

Dated, evidence-backed operational facts discovered during development.
Prune entries when they become common knowledge (absorbed into AGENTS.md or specs).

---

## 2026-07-05: Blender PropertyGroup registration order

`FasciaMuscleRecruitment` (PropertyGroup) must be registered BEFORE `FASCIA_UL_recruitment` (UIList) in the `classes` tuple, because the UIList draws from the PropertyGroup type. If the order is wrong, Blender crashes on registration with a type-not-found error.

Additionally, the CollectionProperty (`fascia_recruitment`) and IntProperty (`fascia_recruitment_index`) are NOT in the `classes` tuple — they are registered separately in `register()` via direct assignment to `bpy.types.Scene`. They must be deleted in `unregister()` BEFORE the classes tuple is unregistered (which unregisters the PropertyGroup). If you delete them after, Blender crashes with dangling type references.

Evidence: Spec 5 implementation (see git history for the double-registration bug fix).

---

## 2026-07-05: Shape key safety — Live_Flex vs Basis

The `Live_Flex` shape key is the ONLY place live deformation data should go when shape keys exist. Writing to `mesh.vertices` when shape keys exist corrupts the `Basis` key because Blender maps `mesh.vertices` to Basis data in that state. The `_original_verts` backup system is only safe when NO shape keys exist.

Evidence: The flex system was tested with both paths (backup-only and shape-key) and the shape-key path showed Basis corruption when `mesh.vertices` was written directly. The current code in `update_flex()` correctly branches: shape keys exist → write to Live_Flex, no shape keys → use backup system.

---

## 2026-07-05: Baked frame capture order

When baking flex results into shape keys (`FASCIA_OT_bake_flex_pose`), the flexed vertex positions must be read BEFORE creating or modifying the `Basis` shape key. Creating Basis resets `mesh.vertices` to the original undeformed positions, which would lose the flexed data. The current code correctly reads flexed positions first, then ensures Basis exists, then writes to the baked frame key.

---

## 2026-07-05: Pinned muscle geometry offset

When pinning muscle attachments (Spec 4), the geometry was offset so local Z spans [0, +length] instead of [-length/2, +length/2]. The object origin is at the FROM landmark. This means scaling local Z by (1-c) keeps local Z=0 fixed at the FROM landmark and pulls the insertion end toward it. The at-rest appearance is identical to the old midpoint-pivot approach — only the transform pivot moved.

Evidence: `create_muscle_mesh()` applies a `bmesh.ops.translate` of (`0, 0, length/2`) after scaling, and sets `obj.location = p1` instead of the midpoint.

---

## 2026-07-05: Bone parenting — operator approach is correct, manual matrix is fragile

To bone-parent an empty to an armature bone while preserving world position, the approach `bpy.ops.object.parent_set(type='BONE', keep_transform=True)` works correctly. The key prerequisite: set `armature.data.bones.active` to the target bone before calling the operator. Without this, the operator fails with "No active bone".

Attempts to compute `matrix_parent_inverse` manually for bone parenting failed because Blender's world-matrix evaluation for `parent_type='BONE'` includes the bone's rest rotation (from `bone.matrix_local`) which rotates the child's local transform relative to the bone's axis. The `parent_set` operator handles this correctly; manual matrix computation would need to account for `bone.matrix_local`'s rotation fully, which is error-prone.

Evidence: Spec 7 implementation. The first version tried manual `matrix_parent_inverse = parent_world.inverted() @ world_before` which produced wrong world positions. Switching to `armature.data.bones.active` + `parent_set(type='BONE', keep_transform=True')` produced correct world positions in all tests.

## 2026-07-05: object_parent_object works with the same operator approach

For object parenting (muscle → landmark), `bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)` with `temp_override` works without any prerequisites. Unlike bone parenting, no active bone is needed. The operator handles the `matrix_parent_inverse` computation correctly to preserve world position.

Evidence: Spec 7 tests: all 29 muscles parented to their origin landmarks with correct world positions preserved.

---

## 2026-07-05: Damped Track (not Stretch To) for muscle insertion tracking

For muscle insertion tracking (Spec 8), Stretch To constraint was considered but rejected because it overrides `obj.scale` to reach the target — this would break Fascia's volume-preserving contraction (which sets `obj.scale = (ts, ts, ls)` at every flex update). Damped Track is rotation-only, so `obj.scale` is unaffected and volume preservation holds.

Key insight: Damped Track with `track_axis='TRACK_Z'` (the muscle's length axis) fixes the "wrong angle at insertion" without touching the flex/contraction pipeline. The Spec 7 flex fix (`context.view_layer.update()` + `matrix_world.to_quaternion()` for the skin-push axis) already covers constraint-evaluated rotation, so `update_flex` needed zero changes for Spec 8. This was verified: skin-push axis aligns to the Damped Track direction with 7e-8 error.

Evidence: Spec 8 verification. At flex=1, scale=(1.1547, 1.1547, 0.75) and volume product=1.0 — identical before and after Damped Track addition.

---

## 2026-07-05: Inline JSON species resolution — priority chain

For the LLM-facing surface (Spec 9), the species resolution chain in `place_landmarks` and `generate_muscles` must use `elif` (not `if`) for the JSON string branch to enforce file-beats-string priority. If both `fascia_species_path` and `fascia_species_json` are set, the file path wins — explicit user choice overrides the inline LLM input.

The `_load_species_json` helper mirrors `_load_species` but uses `json.loads()` instead of file IO. Same return contract `(landmarks_dict, muscles_dict, species_name)` so the operators handle both identically. Error paths (invalid JSON, missing keys) return `(None, None, None)` same as `_load_species`.

Evidence: Spec 9 verification. File path with horse JSON → 29 landmarks + 29 muscles. Inline JSON with Alien species → 3 landmarks + 2 muscles. Both set → file wins (29 + 29). Invalid JSON → falls back to embedded (29 + 29).

---

## 2026-07-05: Status query operator — self.report() is the LLM channel

`FASCIA_OT_get_status` uses `self.report({'INFO'}, <string>)` rather than returning a dict from `execute()`. This is because Blender operators return `{"FINISHED"}`/`{"CANCELLED"}`, not user data. The MCP server captures `self.report()` output as stdout, which the LLM sees. This keeps the operator consistent with all other Fascia operators while being LLM-accessible.

The status string deliberately omits vertex counts, coordinates, and radii (rule 5). It reports only workflow state: base mesh name, species name, landmark/muscle counts, rig name, flex value.

Evidence: Spec 9 verification. `bpy.ops.fascia.get_status()` produces `Fascia: base=Fascia_Horse_Real, species=horse(default), landmarks=29, muscles=29, rig=TestRig, flex=0.0` via `self.report()`.

---

## 2026-07-06: KDTree.find_range return order — latent Spec 11 bug

`KDTree.find_range()` returns `list[tuple(Vector position, int index, float distance)]`, not `list[tuple(int, float, Vector)]`. The original Spec 11 code unpacked as `for (_idx, dist, _co)` which assigned the Vector to `_idx` and the index to `dist`. This caused `muscle_info[_idx]` (where `_idx` is a Vector) to throw a TypeError.

---

## 2026-07-06: Bare print() statements are harmful for user/LLM experience

Bare `print()` calls in operators or helpers pollute the console and are invisible or noisy for users running through the GUI or via MCP/LLM drivers. All user-facing messages must go through `self.report({'INFO'/'WARNING'/'ERROR'})`. This was fixed for species loading by removing prints from `_load_species*` and adding explicit WARNING reports in the calling operators (place_landmarks, generate_muscles).

Evidence: Re-audit after OSS improvements. All `print("Fascia: ...")` removed from fascia_addon.py. Operators now surface fallback behavior clearly.

The bug was latent because `MUSCLE_INFLUENCE_FRACTION = 0.083` produced `influence_radius ≈ 0.3`, and on the 748k-vertex horse mesh, no belly center was within 0.3 units of any skin vertex — so `find_range` returned empty lists and the broken unpack was never exercised.

Spec 12's axial slide required a larger search radius (`influence_radius + max_half_rest_length`), which exposed the bug. Fix: unpack as `for (_co, idx, dist)` and use `idx` as the list index. The distance check `if dist < 0.001` now correctly uses the actual distance (float) instead of the muscle index (int).

Evidence: Spec 12 verification (the first flex=1 call with skin_sliding=True errored with `TypeError: list indices must be integers or slices, not Vector`). After the fix, all 10 verification checks passed and 368k vertices were correctly displaced.

---

## 2026-07-06: Key OSS improvement gotchas

**poll() required on all operators:** Without `context.mode == 'OBJECT'` guard, Fascia buttons crash in Edit/Sculpt/Weight Paint with a context traceback and may leave partial objects in scene.

**bpy.path.abspath() for // paths:** Blender's file picker stores paths as `//relative`. Python's `os.path.isfile` cannot resolve `//`. Always call `bpy.path.abspath(filepath)` before any file check.

**update= on PropertyGroup FloatProperty:** A `FloatProperty` inside a `PropertyGroup` supports `update=` callback — it fires on change just like Scene properties. Use this to trigger `update_flex` from recruitment slider without a separate redraw hack.

**Save matrix_world before clearing parent:** Setting `obj.parent = None` without saving `obj.matrix_world.copy()` first causes Blender to snap the object to wrong world position when the parent was a posed bone. Fix: save → clear → restore matrix_world.

**Bilateral landmark bone name mirroring:** Copying the same explicit bone name to both _L and _R landmarks causes both to bind to the left-side bone. Swap `.L→.R`, `_L→_R`, `left→right` for the _R side.

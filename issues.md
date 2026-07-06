# Fascia Add-on — QA Issue Tracker

**Audit version:** 2 (2026-07-06)
**Auditor role:** Senior QA Engineer — static analysis + live test log cross-reference
**Source files reviewed:** `fascia_addon.py` (1832 lines), `species/equine_horse.json`, `testing_issues_log.md`, `learnings.md`, `memory.md`
**Test environment referenced:** Blender 5.1, 748k-vertex horse mesh

---

## Priority Summary

| ID | Issue | Severity | Category |
|---|---|---|---|
| [1](#issue-1-stale-vertex-cache-overwrites-user-sculpting-data-loss) | Stale vertex cache overwrites user sculpting | **Critical** | Data Loss | ✅ Fixed (commit `506e5d9`) |
| [11](#issue-11-source_data-reads-meshvertices-not-basis-when-shape-keys-exist) | `source_data` reads live vertices instead of Basis shape key | **Critical** | Data Corruption | ✅ Fixed (commit `e9cdc4a`) |
| [2](#issue-2-relative-file-paths-starting-with--fail-to-load) | Relative `//` paths fail to load | **High** | Functional |
| [3](#issue-3-missing-poll-methods-on-all-sidebar-operators) | No `poll` guards — crash in non-Object modes | **High** | Stability |
| [4](#issue-4-species-schema-validation-gaps-lead-to-operator-crashes) | Species schema gaps cause mid-loop crashes | **High** | Validation |
| [12](#issue-12-antagonist-relaxation-has-latent-division-by-zero) | Antagonist relaxation: latent division by zero | **High** | Logic / Crash |
| [13](#issue-13-generate_muscles-crashes-with-keyerror-on-unknown-landmark-names) | `generate_muscles` crashes on unknown landmark refs | **High** | Crash |
| [5](#issue-5-viewport-does-not-update-on-recruitment--skin-sliding-changes) | Viewport not updated on recruitment / skin-sliding changes | **Medium** | UI/UX |
| [6](#issue-6-double-evaluation-of-update_flex-in-simulation--baking) | Double `update_flex` per frame in Simulate / Bake | **Medium** | Performance |
| [7](#issue-7-rig-binding-uses-rest-pose-bones-not-current-pose) | Rig binding uses rest pose, not current pose | **Medium** | Functional |
| [8](#issue-8-bake-creates-13-identical-shape-keys-without-animation) | Bake creates 13 identical shape keys without animation | **Medium** | UI/UX |
| [14](#issue-14-4-landmarks-placed-but-never-used-by-any-muscle-orphan-anchors) | 4 orphan landmarks placed but never used | **Medium** | Data Integrity |
| [15](#issue-15-update_horse-color-unpack-is-fragile-to-property-size-changes) | `update_horse` color unpack fragile to property size | **Medium** | Compatibility |
| [16](#issue-16-bake-reads-meshvertices-not-basis-at-flex-0-frames) | Bake reads `mesh.vertices` not Basis at flex=0 frames | **Medium** | Data Integrity |
| [9](#issue-9-operators-destroy-the-users-selection-state) | Operators destroy the user's selection state | **Low** | UI/UX |
| [10](#issue-10-stale-live_flex-vertex-data-persists-when-flex-returns-to-0) | Stale `Live_Flex` data when flex returns to 0 | **Low** | Functional |
| [17](#issue-17-panel-always-shows-horse-settings-regardless-of-loaded-species) | Panel always shows "Horse Settings" for all species | **Low** | UI/UX |
| [18](#issue-18-get_status-re-reads-species-file-on-every-call-no-caching) | `get_status` re-reads species file on every call | **Low** | Performance |
| [19](#issue-19-clear-rig-binding-loses-world-transform-when-rig-is-posed) | Clear Rig Binding loses world transform when rig is posed | **High** | Functional |
| [20](#issue-20-both-mirrored-landmarks-receive-the-same-bone-name-from-species-json) | Both mirrored landmarks get the same bone name from species JSON | **High** | Functional |
| [21](#issue-21-bind-landmarks-to-rig-skips-instead-of-auto-binding-when-explicit-bone-is-stale) | Bind Rig skips landmarks with stale `fascia_bone` instead of auto-binding | **Medium** | Functional |

---

## Issues Detail

---

### Issue 1: Stale Vertex Cache Overwrites User Sculpting (Data Loss)

- **Severity:** Critical
- **Component:** Vertex backup / restore helpers
- **Affected Code:** [`_save_original_verts`](file:///C:/Projects/Fascia/fascia_addon.py#L452-L464), [`_restore_original_verts`](file:///C:/Projects/Fascia/fascia_addon.py#L466-L487)
- **Reproduction Steps:**
  1. Click **Make Placeholder Horse** (or **Use Selected as Base**).
  2. Wiggle **Flex** to `0.5` then back to `0.0` — positions cached in `_original_verts`.
  3. Enter Edit/Sculpt Mode and move several vertices.
  4. Return to Object Mode and move **Flex**.
  5. **Result:** Sculpted changes are erased — mesh reverts to the cached pre-sculpt positions.
- **Expected Behavior:** Manual edits in Edit/Sculpt Mode survive flex updates. The backup must be invalidated when the base mesh is changed outside Fascia's control.
- **Actual Behavior:** Module-level Python dictionary cache silently overwrites user sculpting.
- **Suggested Fix:** Add a `Basis` shape key the first time any mesh is registered, removing the need for `_original_verts` entirely. If keeping the dict, use a depsgraph handler to detect edit-mode changes and clear the entry.

---

### Issue 2: Relative File Paths Starting with `//` Fail to Load

- **Severity:** High
- **Component:** Anatomy JSON loader
- **Affected Code:** [`_load_species` line 104](file:///C:/Projects/Fascia/fascia_addon.py#L104)
- **Reproduction Steps:**
  1. Click the **Species File** field and browse to `species/equine_horse.json`. Blender stores this as `//species/equine_horse.json`.
  2. Click **Place Landmarks**.
  3. **Result:** Console: `Fascia: species file not found: //species/equine_horse.json`. Falls back to built-in horse.
- **Expected Behavior:** Blender-relative `//` paths resolve correctly.
- **Actual Behavior:** Python `os.path.isfile()` does not understand `//` — file check always fails.
- **Suggested Fix:**
  ```python
  abs_path = bpy.path.abspath(filepath)
  if not os.path.isfile(abs_path):
      ...
  ```

---

### Issue 3: Missing `poll` Methods on All Sidebar Operators

- **Severity:** High
- **Component:** All operator classes
- **Affected Code:** [`FASCIA_OT_place_landmarks`](file:///C:/Projects/Fascia/fascia_addon.py#L946), [`FASCIA_OT_generate_muscles`](file:///C:/Projects/Fascia/fascia_addon.py#L1158), [`FASCIA_OT_make_placeholder_horse`](file:///C:/Projects/Fascia/fascia_addon.py#L874), all other `FASCIA_OT_*`
- **Reproduction Steps:**
  1. Enter **Edit Mode**, **Sculpt Mode**, or **Weight Paint Mode**.
  2. Click any Fascia sidebar button.
  3. **Result:** Blender raises a context traceback. Scene may contain partially-created objects.
- **Expected Behavior:** Buttons greyed out in any non-Object mode.
- **Actual Behavior:** Buttons active — crash when clicked in wrong context.
- **Suggested Fix:**
  ```python
  @classmethod
  def poll(cls, context):
      return context.mode == 'OBJECT'
  ```

---

### Issue 4: Species Schema Validation Gaps Lead to Operator Crashes

- **Severity:** High
- **Component:** JSON parser and geometry generation loops
- **Affected Code:** [`_load_species`](file:///C:/Projects/Fascia/fascia_addon.py#L86-L119), [`_load_species_json`](file:///C:/Projects/Fascia/fascia_addon.py#L122-L145), [`FASCIA_OT_place_landmarks`](file:///C:/Projects/Fascia/fascia_addon.py#L992-L1056), [`FASCIA_OT_generate_muscles`](file:///C:/Projects/Fascia/fascia_addon.py#L1221-L1337)
- **Reproduction Steps:**
  1. Create a species JSON missing `"pos"` on one landmark, or `"radius"` on a muscle.
  2. Set a muscle color as 3 floats `[r, g, b]` instead of 4 `[r, g, b, a]`.
  3. Click **Place Landmarks** or **Generate Muscles**.
  4. **Result:** `KeyError` or `ValueError` mid-loop. Half-created objects left in scene.
- **Expected Behavior:** Clean warning emitted; operators roll back or skip invalid entries.
- **Actual Behavior:** Uncaught exception aborts mid-loop, polluting the scene.
- **Suggested Fix:** Validate required sub-keys before the generation loop. Auto-pad 3-float colors to RGBA.

---

### Issue 5: Viewport Does Not Update on Recruitment / Skin-Sliding Changes

- **Severity:** Medium
- **Component:** Scene properties, `FasciaMuscleRecruitment`, `fascia_skin_sliding`
- **Affected Code:** [`FasciaMuscleRecruitment.recruitment`](file:///C:/Projects/Fascia/fascia_addon.py#L1656-L1662), [`fascia_skin_sliding` registration](file:///C:/Projects/Fascia/fascia_addon.py#L1796-L1800)
- **Reproduction Steps:**
  1. Generate muscles, set **Flex** to `0.8`.
  2. Drag any muscle's recruitment slider to `0.0`, or toggle **Skin Sliding**.
  3. **Result:** Mesh does not update visually. Must manually wiggle Flex to force redraw.
- **Expected Behavior:** Any contraction-influencing property triggers `update_flex` immediately.
- **Actual Behavior:** Neither `recruitment` nor `fascia_skin_sliding` has an `update=` callback.
- **Suggested Fix:**
  ```python
  # In FasciaMuscleRecruitment:
  recruitment: bpy.props.FloatProperty(..., update=update_flex)
  # In register():
  bpy.types.Scene.fascia_skin_sliding = bpy.props.BoolProperty(..., update=update_flex)
  ```

---

### Issue 6: Double Evaluation of `update_flex` in Simulation / Baking

- **Severity:** Medium
- **Component:** `FASCIA_OT_simulate_motion`, `FASCIA_OT_bake_flex_pose`
- **Affected Code:** [`simulate_motion` L1391-L1395](file:///C:/Projects/Fascia/fascia_addon.py#L1391-L1395), [`bake_flex_pose` L1434-L1435](file:///C:/Projects/Fascia/fascia_addon.py#L1434-L1435)
- **Reproduction Steps:**
  1. Load a 700k+ vertex mesh.
  2. Run **Simulate Motion** or **Bake Result**.
  3. **Result:** Each frame runs `update_flex` twice — once via the `fascia_flex` property update callback (triggered by `scene.fascia_flex = val`), and once via the explicit `update_flex(None, context)` call. On a 748k-vertex mesh this doubles an already ~30 s per-frame cost.
- **Expected Behavior:** One `update_flex` call per frame.
- **Actual Behavior:** Two calls per frame.
- **Suggested Fix:** Remove the explicit `update_flex(None, context)` calls from both operator loops. The registered callback fires automatically.

---

### Issue 7: Rig Binding Uses Rest-Pose Bones, Not Current Pose

- **Severity:** Medium
- **Component:** Rig binding helper
- **Affected Code:** [`_find_nearest_bone` L175-L176](file:///C:/Projects/Fascia/fascia_addon.py#L175-L176)
- **Reproduction Steps:**
  1. Enter **Pose Mode** and move bones far from rest.
  2. Click **Bind Landmarks to Rig** in Object Mode.
  3. **Result:** Landmarks bound to bones based on rest geometry, not current pose.
- **Expected Behavior:** Nearest-bone distance measured against current evaluated pose.
- **Actual Behavior:** Reads `bone.head_local` / `bone.tail_local` — always rest-pose constants.
- **Suggested Fix:**
  ```python
  for pose_bone in armature.pose.bones:
      head_w = armature.matrix_world @ pose_bone.head
      tail_w = armature.matrix_world @ pose_bone.tail
  ```

---

### Issue 8: Bake Creates 13 Identical Shape Keys Without Animation

- **Severity:** Medium
- **Component:** `FASCIA_OT_bake_flex_pose`
- **Affected Code:** [`FASCIA_OT_bake_flex_pose`](file:///C:/Projects/Fascia/fascia_addon.py#L1410-L1477)
- **Reproduction Steps:**
  1. Generate muscles. Do NOT run Simulate Motion (no flex keyframes).
  2. Set **Flex** to `0.5`.
  3. Click **Bake Result**.
  4. **Result:** 13 identical shape keys created (`Baked_Frame_001` to `Baked_Frame_060`), all same positions.
- **Expected Behavior:** Operator detects missing animation and warns or procedurally sweeps flex 0→1.
- **Actual Behavior:** Silently bakes 13 clones, wasting memory and cluttering the shape key list.
- **Suggested Fix:** Verify keyframes exist on the `fascia_flex` data path before baking.

---

### Issue 9: Operators Destroy the User's Selection State

- **Severity:** Low
- **Component:** Parenting helper functions and operators
- **Affected Code:** [`_bone_parent_object`](file:///C:/Projects/Fascia/fascia_addon.py#L193-L224), [`_object_parent_object`](file:///C:/Projects/Fascia/fascia_addon.py#L227-L242), [`FASCIA_OT_clear_rig_binding`](file:///C:/Projects/Fascia/fascia_addon.py#L1111-L1146)
- **Reproduction Steps:**
  1. Select your base mesh.
  2. Click **Bind Landmarks to Rig** or **Clear Rig Binding**.
  3. **Result:** Active object and selection are lost — the last-touched landmark or armature is now active instead.
- **Expected Behavior:** Active object and selection restored after operator completes.
- **Actual Behavior:** `bpy.ops.object.select_all(action='DESELECT')` called inside loop permanently clobbers selection.
- **Suggested Fix:** Save and restore `context.view_layer.objects.active` and `context.selected_objects` around the operator body.

---

### Issue 10: Stale `Live_Flex` Vertex Data Persists When Flex Returns to 0

- **Severity:** Low
- **Component:** Deformer
- **Affected Code:** [`update_flex` L695-L698](file:///C:/Projects/Fascia/fascia_addon.py#L695-L698)
- **Reproduction Steps:**
  1. Drag **Flex** to `1.0`.
  2. Drag **Flex** back to `0.0`.
  3. Read `bpy.data.objects['BaseMesh'].data.shape_keys.key_blocks['Live_Flex'].data` via Python.
  4. **Result:** `Live_Flex.data` still contains flexed positions (weight is `0.0` so no visual effect, but raw data is stale).
- **Expected Behavior:** When flex returns to 0, `Live_Flex.data` matches Basis coordinates.
- **Actual Behavior:** Raw vertex data remains deformed — confuses exporters and external scripts reading shape key data directly.
- **Suggested Fix:** Copy Basis coords into `Live_Flex.data` via `foreach_set` when `flex < 0.001` and shape keys exist.

---

### Issue 11: `source_data` Reads `mesh.vertices` Not `Basis` When Shape Keys Exist

- **Severity:** Critical
- **Component:** Deformer — shape-key path
- **Affected Code:** [`update_flex` L700-L702](file:///C:/Projects/Fascia/fascia_addon.py#L700-L702)
- **Description:** When shape keys exist, line 702 assigns:
  ```python
  source_data = mesh.vertices   # WRONG — blended/live positions, not clean Basis
  ```
  `mesh.vertices` when shape keys are present exposes the **evaluated/blended** vertex positions, not the clean Basis. Reading from here on the second flex call will compound displacement from any already-active shape key, causing visible drift and incorrect push directions.
- **Reproduction Steps:**
  1. Run **Bake Result** (creates Basis + shape keys).
  2. Drag **Flex** to `0.5`.
  3. Drag **Flex** to `0.8`.
  4. **Result:** Skin visibly drifts or over-pushes because each flex update reads the already-displaced blended mesh as the clean source instead of Basis.
- **Expected Behavior:** Source positions always read from `Basis` shape key data when shape keys exist.
- **Actual Behavior:** Source reads blended `mesh.vertices`, corrupting the reference on every subsequent flex update.
- **Suggested Fix:**
  ```python
  basis_key = mesh.shape_keys.key_blocks.get("Basis")
  source_data = basis_key.data if basis_key else mesh.vertices
  ```

---

### Issue 12: Antagonist Relaxation Has Latent Division by Zero

- **Severity:** High
- **Component:** Antagonist relaxation math in `update_flex`
- **Affected Code:** [`update_flex` L582 and L588](file:///C:/Projects/Fascia/fascia_addon.py#L582)
- **Description:**
  ```python
  max_c_total = flex * MAX_CONTRACTION if flex > 0.001 else 1.0  # L582
  ...
  max_relax = max(max_relax, min(1.0, c_ag / max_c_total))       # L588
  ```
  The `else 1.0` guard prevents division by zero in the normal `flex=0` case. However, the guard is undocumented and fragile — if `max_c_total` is ever computed as `0.0` through a different code path (future refactor, external caller bypassing the `flex > 0.001` check), line 588 will throw `ZeroDivisionError`. The condition also doesn't cover `flex` values between 0.0 and 0.001 (exclusive) where the threshold is crossed asymmetrically.
- **Expected Behavior:** Division is safe regardless of `flex` value; guard is explicit.
- **Suggested Fix:**
  ```python
  max_c_total = max(flex * MAX_CONTRACTION, 1e-9)  # safe floor
  ```

---

### Issue 13: `generate_muscles` Crashes with `KeyError` on Unknown Landmark Names

- **Severity:** High
- **Component:** `FASCIA_OT_generate_muscles`
- **Affected Code:** [`generate_muscles` L1224](file:///C:/Projects/Fascia/fascia_addon.py#L1224)
- **Reproduction Steps:**
  1. Create a species JSON where a muscle's `"from"` or `"to"` references a landmark not in the `"landmarks"` dict (e.g. typo `"ShoulderTopLeft"` vs `"ScapulaTop"`).
  2. Load via Species File picker and click **Generate Muscles**.
  3. **Result:** `KeyError: 'ShoulderTopLeft'` at `landmarks_data[from_key]` (line 1224). No user-friendly error. Partial muscles created in scene.
- **Expected Behavior:** A clean named error identifying the problematic muscle and missing landmark. Operation aborts before modifying the scene.
- **Actual Behavior:** Unhandled exception mid-loop. Scene polluted with partial muscles.
- **Suggested Fix:** Pre-validate all `"from"` / `"to"` references against `landmarks_data` keys before the generation loop. Collect errors and report them before any scene modification.

---

### Issue 14: 4 Landmarks Placed But Never Used by Any Muscle (Orphan Anchors)

- **Severity:** Medium
- **Component:** Data consistency — `HORSE_LANDMARKS` vs `HORSE_MUSCLES`
- **Affected Code:** [`HORSE_LANDMARKS`](file:///C:/Projects/Fascia/fascia_addon.py#L315-L343), [`HORSE_MUSCLES`](file:///C:/Projects/Fascia/fascia_addon.py#L381-L402)
- **Description:** Three landmarks are defined and placed as empties but are never referenced as `"from"` or `"to"` by any muscle in `HORSE_MUSCLES`:
  - `NuchalCrest` — placed, no muscle references it
  - `FrontKnee` — placed, no muscle references it
  - `BellyMid` — placed, no muscle references it
- **Effect:** Orphan empties litter the viewport. They confuse users and LLM consumers expecting every landmark to have a muscle. `FrontKnee` is bilateral so it produces 2 extra empties; total orphan empties = 4.
- **Expected Behavior:** Every placed landmark is the origin or insertion of at least one muscle, OR it is explicitly documented as a reserved future anchor.
- **Suggested Fix:** Add muscles connecting these landmarks (e.g., a neck muscle for `NuchalCrest`, a cannon-bone muscle for `FrontKnee`) or remove them and add a `# RESERVED — future muscle attachment` comment block.

---

### Issue 15: `update_horse` Color Unpack is Fragile to Property Size Changes

- **Severity:** Medium
- **Component:** `update_horse` callback
- **Affected Code:** [`update_horse` L423-L424 and L437-L438](file:///C:/Projects/Fascia/fascia_addon.py#L423-L438)
- **Description:**
  ```python
  r, g, b = scene.fascia_color   # 3-tuple unpack
  body.color = (r, g, b, 1.0)
  ```
  `fascia_color` is registered as `size=3`. If it is ever changed to `size=4` (for RGBA consistency with `body.color`), this unpack raises `ValueError: too many values to unpack`. Additionally, the hardcoded `alpha=1.0` silently overrides any transparency the user may intend when the property moves to 4-channel.
- **Suggested Fix:**
  ```python
  col = scene.fascia_color
  body.color = (col[0], col[1], col[2], 1.0)
  ```

---

### Issue 16: Bake Reads `mesh.vertices` Not Basis at Flex=0 Frames

- **Severity:** Medium
- **Component:** `FASCIA_OT_bake_flex_pose`
- **Affected Code:** [`bake_flex_pose` L1445-L1451](file:///C:/Projects/Fascia/fascia_addon.py#L1445-L1451)
- **Description:**
  ```python
  if flex_val < 0.001:
      source = mesh.vertices   # blended live mesh, not guaranteed clean Basis
  ```
  When shape keys exist, `mesh.vertices` exposes blended positions. If `Live_Flex.value` was not zeroed in this session (stale data from Issue 10), `mesh.vertices` at flex=0 frames may carry residual deformation, baking wrong rest-pose data.
- **Expected Behavior:** At flex=0 bake frames, source always reads from the `Basis` shape key.
- **Suggested Fix:**
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

### Issue 17: Panel Always Shows "Horse Settings" Regardless of Loaded Species

- **Severity:** Low
- **Component:** Panel UI
- **Affected Code:** [`FASCIA_PT_main_panel.draw` L1557](file:///C:/Projects/Fascia/fascia_addon.py#L1557)
- **Description:** `layout.label(text="Horse Settings:")` is hardcoded. When a custom species file or inline JSON is loaded (alien, dinosaur, etc.), the label still reads "Horse Settings" — misleading for non-horse workflows and confusing for LLM consumers reading panel state.
- **Suggested Fix:**
  ```python
  species_label = scene.fascia_species_path.rsplit("/", 1)[-1] or "Horse"
  layout.label(text=f"{species_label} Settings:")
  ```

---

### Issue 18: `get_status` Re-Reads Species File on Every Call — No Caching

- **Severity:** Low
- **Component:** `FASCIA_OT_get_status`
- **Affected Code:** [`FASCIA_OT_get_status.execute` L1504-L1511](file:///C:/Projects/Fascia/fascia_addon.py#L1504-L1511)
- **Description:** Every `fascia.get_status()` call opens and JSON-parses the species file from disk. When called in a fast LLM loop this adds unnecessary repeated I/O for a read-only status query.
- **Suggested Fix:** Cache the resolved species name in `scene["_fascia_species_name"]` when `place_landmarks` or `generate_muscles` runs and read it directly in `get_status`.

---

## Performance Notes

Confirmed on a 748k-vertex horse mesh during live testing:

| Issue | Impact |
|---|---|
| Pure-Python vertex loop | ~30 s per `update_flex` call; MCP timeouts on Simulate / Bake |
| Double `update_flex` per frame (Issue 6) | 2× slowdown on Simulate and Bake |
| `view_layer.update()` inside frame loop | Compounds cost per frame in Simulate / Bake |
| KDTree rebuilt every `update_flex` call | Negligible at 29 muscles; will grow with custom species |

---

## Accessibility / UX Notes

| Area | Issue |
|---|---|
| Panel label | "Horse Settings" always shown (Issue 17) |
| No progress indicator | Bake and Simulate block UI silently for minutes on large meshes |
| Orphan landmarks | 4 unused empties litter the viewport (Issue 14) |
| Selection loss | Every bind/clear operation destroys the user's selection (Issue 9) |

---

## Audit History

| Pass | Date | Issues Found | Source Method |
|---|---|---|---|
| 1 | 2026-07-06 | 10 (Issues 1–10) | Live Blender test session (Blender 5.1, 748k mesh) |
| 2 | 2026-07-06 | 8 new (Issues 11–18) | Deep static code analysis of `fascia_addon.py` |
| 3 | 2026-07-06 | 3 new (Issues 19–21) | GitHub Codex automated review (commit `5bbfb36524`) |

*Do not implement fixes in this file — use it as the source of truth for the fix backlog.*

---

### Issue 19: Clear Rig Binding Loses World Transform When Rig Is Posed

- **Severity:** High
- **Component:** `FASCIA_OT_clear_rig_binding`
- **Source:** GitHub Codex review, commit `5bbfb36524`
- **Affected Code:** [`FASCIA_OT_clear_rig_binding` L1122-L1141](file:///C:/Projects/Fascia/fascia_addon.py#L1122-L1141)
- **Description:** When the armature is in a non-rest pose and the user clicks **Clear Rig Binding**, the code sets `lm.parent = None` (line 1124) without first saving the landmark's current world-space position. Blender recalculates the landmark's position using its local (bone-relative) coordinates before the parent is removed, which snaps it to the wrong world location. The subsequent `parent_set(type='OBJECT', keep_transform=True)` then locks in this already-wrong position when re-parenting to the base mesh.
- **Reproduction Steps:**
  1. Place landmarks and bind them to a rig.
  2. Enter **Pose Mode** on the armature, move any bones away from rest.
  3. Exit Pose Mode and click **Clear Rig Binding**.
  4. **Result:** Landmarks jump to incorrect world positions and are then parented to the base mesh at those wrong locations.
- **Expected Behavior:** After clearing, landmarks sit at exactly the same world-space position they occupied before clearing — only the parent relationship changes.
- **Actual Behavior:** Setting `lm.parent = None` without first snapping the world matrix causes the landmark to relocate before the `keep_transform` re-parent step can compensate.
- **Suggested Fix:** Capture `saved_world = lm.matrix_world.copy()` before clearing the parent, then restore it after:
  ```python
  saved_world = lm.matrix_world.copy()
  lm.parent = None
  lm.parent_type = 'OBJECT'
  lm.parent_bone = ""
  lm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
  lm.matrix_world = saved_world   # restore before re-parenting
  ```

---

### Issue 20: Both Mirrored Landmarks Receive the Same Bone Name from Species JSON

- **Severity:** High
- **Component:** `FASCIA_OT_place_landmarks` — bilateral landmark creation
- **Source:** GitHub Codex review, commit `5bbfb36524`
- **Affected Code:** [`place_landmarks` L1016-L1017](file:///C:/Projects/Fascia/fascia_addon.py#L1016-L1017)
- **Description:** When a species JSON supplies a `"bone"` key for a bilateral landmark, both the `_L` and `_R` empties are tagged with the exact same bone name:
  ```python
  if "bone" in data:
      empty["fascia_bone"] = data["bone"]   # same name copied to both sides
  ```
  On a standard left/right rig (e.g., `thigh.L` / `thigh.R`), both the left and right hip landmarks would bind to, say, `thigh.L` — meaning the right-side muscle chain follows the wrong bone entirely.
- **Reproduction Steps:**
  1. Create a species JSON with a bilateral landmark that includes `"bone": "thigh.L"`.
  2. Click **Place Landmarks**.
  3. Click **Bind Landmarks to Rig**.
  4. **Result:** Both the `_L` and `_R` landmarks are bone-parented to `thigh.L`. The `_R` landmark — and all muscles originating from it — incorrectly follow the left thigh bone.
- **Expected Behavior:** The `_L` landmark receives the explicit bone name; the `_R` landmark either receives a mirrored equivalent (e.g., swap `.L` → `.R` suffix) or falls back to auto-nearest-bone binding.
- **Actual Behavior:** Both receive the identical bone name from the JSON, binding the right-side landmark to the left-side bone.
- **Suggested Fix:** When creating the `_R` mirror, attempt to derive the right-side bone name by swapping common left-side suffixes:
  ```python
  if "bone" in data:
      bone_name = data["bone"]
      if suffix == "_R":
          # Try swapping .L → .R, _L → _R, left → right
          bone_name = (bone_name
              .replace(".L", ".R")
              .replace("_L", "_R")
              .replace("left", "right")
              .replace("Left", "Right"))
      empty["fascia_bone"] = bone_name
  ```
  If the derived name does not exist in the armature, fall back to auto-nearest-bone at bind time.

---

### Issue 21: Bind Landmarks to Rig Skips Instead of Auto-Binding When Explicit Bone Is Stale

- **Severity:** Medium
- **Component:** `FASCIA_OT_bind_landmarks_to_rig`
- **Source:** GitHub Codex review, commit `5bbfb36524`
- **Affected Code:** [`bind_landmarks_to_rig` L1092-L1103](file:///C:/Projects/Fascia/fascia_addon.py#L1092-L1103)
- **Description:** The operator reads `fascia_bone` from the landmark's custom property and passes it straight to `_bone_parent_object`. If the bone does not exist on the armature (e.g., after a rig rename or when reusing anatomy JSON from a different rig), `_bone_parent_object` returns `False` and the landmark is skipped entirely — even though auto-nearest-bone binding could still attach it:
  ```python
  bone_name = lm.get("fascia_bone", "")
  if not bone_name:
      bone_name, _ = _find_nearest_bone(...)   # auto fallback only if name is blank
  # ... no fallback when bone_name is set but doesn't exist
  ok = _bone_parent_object(lm, armature, bone_name)
  if ok:
      bound += 1
  else:
      skipped += 1   # silently skipped — landmark left unbound
  ```
- **Reproduction Steps:**
  1. Place landmarks via a species JSON that includes `"bone"` hints.
  2. Click **Bind Landmarks to Rig** with an armature that has different bone names than those in the JSON.
  3. **Result:** All landmarks with explicit `fascia_bone` properties that don't match the armature are silently skipped. Significant portions of the muscle chain are left unbound with no user warning identifying which landmarks failed or why.
- **Expected Behavior:** If the explicit bone name does not exist in the chosen armature, fall back to auto-nearest-bone and warn the user which landmarks used fallback binding.
- **Actual Behavior:** Stale explicit names cause silent skips. The operator reports only a count (`N skipped`) with no detail on which landmarks were affected.
- **Suggested Fix:**
  ```python
  bone_name = lm.get("fascia_bone", "")
  used_fallback = False
  if bone_name and bone_name not in armature.data.bones:
      # Explicit name is stale — fall back to nearest bone
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
          print(f"Fascia: '{lm.name}' used fallback binding (explicit bone not found)")
  else:
      skipped += 1
  ```

# SPEC 09 — LLM-Facing Surface (Inline Anatomy + Status Query)

**Target executor:** implementing agent.
**Scope:** Add a `fascia_species_json` Scene StringProperty so an external LLM can pass anatomy inline without writing a file to disk; extend the species-loading path to consult it; add a read-only `fascia.get_status` operator that returns a short plain-English state summary for the LLM; tighten operator `bl_description` text to be LLM-discoverable. Does NOT change contraction math, shape-key safety, the bake pipeline, rig binding, muscle insertion tracking (Spec 8), the panel layout beyond one new field, or any operator's core logic.
**Estimated size:** ~45 lines added/changed across 5 locations in `fascia_addon.py`.

---

## 1. Why this change is needed

Memory.md §10 critical-path item #1:

> **LLM-facing surface.** The anatomy input slot (Spec 6) and rig binding (Spec 7) exist but are panel-only. Expose `place_landmarks`, `generate_muscles`, `bind_landmarks_to_rig`, `clear_rig_binding`, `simulate_motion`, and `bake_flex_pose` so an external LLM can call them (MCP-style, matching the Blender MCP pattern already in use). Same tools, two doors (panel + LLM). Status returns short plain-English, never raw mesh (rule 5). Also add a `fascia_species_json` string property so the LLM can pass anatomy inline without writing a file to disk.

The product thesis (AGENTS.md §"Product Thesis") is **y = m · x**: the client's LLM (x) is the muscle TD; Fascia (m) is the hands. For x to do its job it must be able to *tell m what the creature's anatomy is* and *call m's tools*. Today x can do the second (every operator is a `bpy.ops.fascia.*` call, reachable through the Blender MCP server's `execute_blender_code` tool) but not the first without writing a JSON file to disk (Spec 6's `fascia_species_path`). A file-on-disk round-trip is a poor LLM interface: it requires filesystem access on the Blender host, a writable temp path, and a second call to point `fascia_species_path` at it. An inline JSON string property removes the round-trip — the LLM sets one Scene property and calls the operator.

The status query operator fills a second gap: an LLM driving Fascia needs to know the current scene state ("are landmarks placed? how many? is a rig bound? what species is loaded?") to decide what to do next. Today it would have to run raw Python queries against `bpy.data.objects`, which is exactly the "raw mesh dump to an LLM-facing tool" anti-pattern rule 5 forbids. A dedicated `fascia.get_status` operator returns a short plain-English summary string via `self.report()` — no mesh data, no vertex counts, just the workflow state.

The deliverable: an external LLM using the Blender MCP server can, in one Python call, set `scene.fascia_species_json = '{"name":"Alien",...}'`, call `bpy.ops.fascia.place_landmarks()`, call `bpy.ops.fascia.generate_muscles()`, optionally bind to a rig, flex, simulate, bake — and at any point call `bpy.ops.fascia.get_status()` to get a one-line state report. Two doors (panel + LLM), same tools, short plain-English status, no raw mesh.

---

## 2. The LLM-facing model

### 2a. Two doors, same tools

```
   Human (panel)  ──click──>  bpy.ops.fascia.*  ──>  same execute()  ──>  self.report()
                                                                          │
   LLM (MCP)      ─execute_blender_code──>  bpy.ops.fascia.*  ───────────┘
```

Every Fascia operator is already a `bpy.ops.fascia.*` call. The Blender MCP server's `execute_blender_code` tool runs arbitrary Python, so an LLM can already call any Fascia operator. Spec 9 does NOT add an MCP server, an RPC layer, or a new transport — it adds two affordances that make the existing operators a better LLM interface:

1. **Inline anatomy:** `fascia_species_json` lets the LLM pass anatomy without a file round-trip.
2. **Status query:** `fascia.get_status` gives the LLM a one-line state summary without raw Python queries.

The operators themselves are unchanged in behaviour — same inputs, same outputs, same `self.report()` status. This is the "same tools, two doors" principle.

### 2b. Species resolution order

When `place_landmarks` or `generate_muscles` need anatomy data, they resolve it in this priority:

1. `fascia_species_path` (Spec 6) — if non-empty and the file loads, use it. **Highest priority** (explicit file beats inline string, so a user who has a curated species file isn't surprised by a stale JSON string left in the scene).
2. `fascia_species_json` (Spec 9, this spec) — if non-empty and parses as valid species JSON, use it.
3. Embedded `HORSE_LANDMARKS` / `HORSE_MUSCLES` — fallback. **Lowest priority.**

This is a strict superset of the Spec 6 resolution order (which was: file → embedded). Adding the JSON-string tier in the middle does not change the file-first or embedded-fallback behaviour, so it is backwards-compatible.

### 2c. What `fascia_species_json` accepts

The exact same JSON schema as a species file (Spec 6):

```json
{
  "name": "Alien",
  "landmarks": {
    "HeadTop": {"pos": [0.5, 0.9, 0.95], "bilateral": false, "region": "head"},
    "Shoulder": {"pos": [0.3, 0.5, 0.7], "bilateral": true, "region": "shoulder"}
  },
  "muscles": {
    "NeckFlexor": {"from": "HeadTop", "to": "Shoulder", "radius": 0.05, "color": [0.8, 0.2, 0.2, 1.0]}
  }
}
```

Optional `"bone"` field per landmark (Spec 7 schema extension) is tolerated. The validation is identical to `_load_species` (Spec 6): required keys `landmarks` and `muscles` must be present; individual entries are not validated (bad data surfaces as key errors at the operator level, same as today).

### 2d. What `fascia.get_status` returns

A single `self.report({'INFO'}, <string>)` call with a compact plain-English summary. The string is designed to be LLM-parseable (short, structured, no mesh data). Format:

```
Fascia: base=<mesh name or "none">, species=<name or "horse(default)">, landmarks=<N>, muscles=<N>, rig=<armature name or "none">, flex=<value>
```

Examples:
- `Fascia: base=Fascia_Horse_Real, species=Equine Horse, landmarks=29, muscles=29, rig=TestRig, flex=0.0`
- `Fascia: base=none, species=horse(default), landmarks=0, muscles=0, rig=none, flex=0.0`

No vertex counts, no coordinate dumps, no muscle radii — just workflow state. Rule 5: "Never return raw mesh or vertex dumps to an LLM-facing tool."

### 2e. Why not a full MCP tool registration

The Blender MCP server (`@lab_blender_org/mcp`) defines its own tool list in its own code. Fascia cannot (and should not — rule 10: don't rebuild what already exists) modify the MCP server to advertise Fascia operators as first-class MCP tools. The `execute_blender_code` transport is the MCP surface; Fascia's job is to make its operators clean to call through that transport. A future "Fascia MCP bridge" addon could register dedicated MCP tools that wrap `bpy.ops.fascia.*`, but that is a separate project, out of scope here.

---

## 3. Architectural decisions (read before changing anything)

1. **`fascia_species_json` is a StringProperty, subtype `NONE` (not `FILE_PATH`).** It holds JSON text, not a path. `subtype='NONE'` gives a plain text field in the panel; the LLM sets it via `scene.fascia_species_json = '{"...":"..."}'`. No file IO.
2. **String length is unbounded (no `maxlen`).** A real creature's species JSON can be a few KB (the horse is ~3 KB). Blender StringProperty has no practical limit for this size. Do not set `maxlen` — it would silently truncate large species files.
3. **Resolution order: file → JSON string → embedded.** File wins because it's an explicit user choice; JSON string is the LLM's inline input; embedded is the safe default. Documented in §2b. This is backwards-compatible with Spec 6.
4. **Reuse `_load_species` for file loading; add `_load_species_json` for string parsing.** Two small helpers, each with one responsibility, instead of one fat helper with a union-type input. `_load_species(filepath)` stays unchanged (Spec 6 callers keep working). `_load_species_json(json_str)` is new — same validation, same return contract `(landmarks, muscles, name) | (None, None, None)`. The operators call them in priority order.
5. **`fascia.get_status` is an operator, not a panel callback.** Operators have `self.report()` (captured by the MCP server's stdout, visible to the LLM) and are callable via `bpy.ops.fascia.get_status()`. A panel callback would not be LLM-callable. The operator does `{'FINISHED'}` always (it is a query, it cannot fail in a way that blocks the workflow).
6. **`fascia.get_status` reports via `self.report({'INFO'}, ...)`.** The MCP server captures operator reports as stdout, which the LLM sees. Do NOT return a dict from `execute()` — operators return `{"FINISHED"}`/`{"CANCELLED"}`, not data. If a future MCP bridge wants structured data, it can call a dedicated Python function; the operator is for the human-facing + LLM-via-stdout path.
7. **No new imports.** `json` is already imported (Spec 6). `bpy` is already imported.
8. **Panel: add `fascia_species_json` as a multiline text field in the Anatomy section.** Use `layout.prop(scene, "fascia_species_json", text="Species JSON")`. The field is a single-line input in the panel by default; that's fine — the LLM sets it programmatically, the human is expected to use the file picker (`fascia_species_path`). Do NOT add a fancy multiline text editor — out of scope.
9. **Tighten three `bl_description` strings to be LLM-discoverable.** The current descriptions are human-friendly but vague for an LLM ("Place anatomical landmark points on the horse" — an LLM doesn't know it works on ANY species, not just horses). Update to mention the species source. This is a comment-quality change, zero behaviour impact.
10. **Do not overclaim.** This spec delivers inline anatomy + a status query. It does NOT deliver: a Fascia MCP server, a Python API returning dicts from operators, automatic workflow orchestration, error recovery, or a web UI. The LLM still has to call operators in the right order (place landmarks → generate muscles → bind → flex → simulate → bake). A future "run pipeline" meta-operator is possible but violates rule 3 (each tool does one clear job) until the LLM has a reason to need it.

---

## 4. The exact changes

### 4a. New helper `_load_species_json`

Insert immediately after `_load_species` (around line 119). Mirrors `_load_species` but takes a JSON string instead of a filepath.

```python
def _load_species_json(json_str):
    """Parse a species-definition JSON string and return
    (landmarks_dict, muscles_dict, species_name).

    Spec 9: the LLM-facing inline-anatomy path. Same schema and
    same return contract as _load_species (Spec 6), but the
    anatomy is passed as a string property (scene.fascia_species_json)
    instead of read from a file. No file IO - the LLM sets the
    property and calls place_landmarks / generate_muscles.

    Returns (None, None, None) on error (invalid JSON or missing
    required keys) - the caller falls back to embedded HORSE_* data.
    """
    try:
        data = json.loads(json_str)
    except Exception as e:
        print("Fascia: error parsing species JSON string: " + str(e))
        return None, None, None

    if "landmarks" not in data or "muscles" not in data:
        print("Fascia: species JSON string missing 'landmarks' or 'muscles' key")
        return None, None, None

    return data["landmarks"], data["muscles"], data.get("name", "Unknown")
```

### 4b. New Scene property `fascia_species_json`

In `register()`, immediately after the `fascia_species_path` block (around line 1576):

```python
    # Inline species JSON (Spec 9). Empty = fall back to fascia_species_path
    # or embedded horse data. Set by the LLM to pass anatomy without a file.
    bpy.types.Scene.fascia_species_json = bpy.props.StringProperty(
        name="Species JSON",
        description="Inline species-definition JSON. Empty = use Species File or built-in horse anatomy. Set by the LLM to define a creature's anatomy without writing a file",
        default="",
        subtype='NONE',
    )
```

In `unregister()`, immediately after `del bpy.types.Scene.fascia_species_path` (around line 1599):

```python
    del bpy.types.Scene.fascia_species_json
```

### 4c. Modify the species-resolution block in `place_landmarks`

Find the species-resolution block in `FASCIA_OT_place_landmarks.execute` (currently it reads `fascia_species_path` and falls back to embedded). The current pattern (verify the exact lines in the file before editing) is:

```python
        landmarks_data = HORSE_LANDMARKS
        species_name = "Horse"
        species_path = context.scene.fascia_species_path
        if species_path:
            loaded_lm, _loaded_ms, loaded_name = _load_species(species_path)
            if loaded_lm:
                landmarks_data = loaded_lm
                species_name = loaded_name or "Unknown"
```

Replace with the three-tier resolution (file → JSON string → embedded):

```python
        # Spec 9: resolve anatomy in priority order - file (Spec 6),
        # inline JSON string (Spec 9), then embedded horse data.
        landmarks_data = HORSE_LANDMARKS
        species_name = "Horse"
        species_path = context.scene.fascia_species_path
        species_json = context.scene.fascia_species_json
        if species_path:
            loaded_lm, _loaded_ms, loaded_name = _load_species(species_path)
            if loaded_lm:
                landmarks_data = loaded_lm
                species_name = loaded_name or "Unknown"
        elif species_json:
            loaded_lm, _loaded_ms, loaded_name = _load_species_json(species_json)
            if loaded_lm:
                landmarks_data = loaded_lm
                species_name = loaded_name or "Unknown"
```

**Note:** `place_landmarks` only uses `landmarks_data` (not `muscles_data`), so the resolution only needs to load landmarks. The `elif` (not `if`) enforces the file-beats-string priority (§2b, decision 3).

### 4d. Modify the species-resolution block in `generate_muscles`

Find the equivalent block in `FASCIA_OT_generate_muscles.execute` (currently around lines 1074–1084):

```python
        # Use species file if configured; fall back to embedded horse data
        landmarks_data = HORSE_LANDMARKS
        muscles_data = HORSE_MUSCLES
        species_name = "Horse"
        species_path = context.scene.fascia_species_path
        if species_path:
            loaded_lm, loaded_ms, loaded_name = _load_species(species_path)
            if loaded_lm and loaded_ms:
                landmarks_data = loaded_lm
                muscles_data = loaded_ms
                species_name = loaded_name or "Unknown"
```

Replace with the three-tier resolution:

```python
        # Spec 9: resolve anatomy in priority order - file (Spec 6),
        # inline JSON string (Spec 9), then embedded horse data.
        landmarks_data = HORSE_LANDMARKS
        muscles_data = HORSE_MUSCLES
        species_name = "Horse"
        species_path = context.scene.fascia_species_path
        species_json = context.scene.fascia_species_json
        if species_path:
            loaded_lm, loaded_ms, loaded_name = _load_species(species_path)
            if loaded_lm and loaded_ms:
                landmarks_data = loaded_lm
                muscles_data = loaded_ms
                species_name = loaded_name or "Unknown"
        elif species_json:
            loaded_lm, loaded_ms, loaded_name = _load_species_json(species_json)
            if loaded_lm and loaded_ms:
                landmarks_data = loaded_lm
                muscles_data = loaded_ms
                species_name = loaded_name or "Unknown"
```

`generate_muscles` uses both `landmarks_data` and `muscles_data`, so both must load successfully. Same `elif` priority as 4c.

### 4e. New operator `FASCIA_OT_get_status`

Insert after `FASCIA_OT_bake_flex_pose` (around line 1333). A read-only query operator.

```python
class FASCIA_OT_get_status(bpy.types.Operator):
    bl_idname = "fascia.get_status"
    bl_label = "Get Fascia Status"
    bl_description = "Report the current Fascia workflow state as a short plain-English summary (base mesh, species, landmark/muscle counts, rig, flex). LLM-facing; returns no mesh data"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        body = _get_base_mesh()
        base_name = body.name if body else "none"

        # Resolve the active species name for the report (same priority
        # as the operators: file > JSON string > embedded horse).
        species_name = "horse(default)"
        if scene.fascia_species_path:
            _lm, _ms, loaded_name = _load_species(scene.fascia_species_path)
            if _lm:
                species_name = loaded_name or "Unknown"
        elif scene.fascia_species_json:
            _lm, _ms, loaded_name = _load_species_json(scene.fascia_species_json)
            if _lm:
                species_name = loaded_name or "Unknown"

        lm_count = sum(1 for o in bpy.data.objects if o.get("fascia_type") == "landmark")
        muscle_count = sum(1 for o in bpy.data.objects if o.get("fascia_type") == "muscle")
        rig_name = scene.fascia_armature.name if scene.fascia_armature else "none"

        summary = (
            "Fascia: base=" + base_name +
            ", species=" + species_name +
            ", landmarks=" + str(lm_count) +
            ", muscles=" + str(muscle_count) +
            ", rig=" + rig_name +
            ", flex=" + str(round(scene.fascia_flex, 2))
        )
        self.report({'INFO'}, summary)
        return {"FINISHED"}
```

### 4f. Panel — add the Species JSON field in the Anatomy section

In `FASCIA_PT_main_panel.draw`, in the Anatomy section (where `fascia_species_path` is drawn), add the JSON field below the file path. Find the `layout.prop(scene, "fascia_species_path", ...)` line and add after it:

```python
        layout.prop(scene, "fascia_species_json", text="Species JSON")
```

Do NOT add a button for `fascia.get_status` to the panel — it is an LLM-facing query, not a human-facing control. (If a human wants the status, they can see it in the panel's existing landmark/muscle count row.) The operator is still registered and callable via `bpy.ops.fascia.get_status()` for the LLM.

### 4g. Classes tuple — add the new operator

In the `classes` tuple (around line 1450), add `FASCIA_OT_get_status`. Place it after `FASCIA_OT_bake_flex_pose` (operator order among themselves is not load-order-sensitive, but grouping logically helps).

### 4h. Tighten three `bl_description` strings (zero behaviour impact)

Update these three descriptions to mention the species source, so an LLM inspecting operator metadata knows the tools work on any species, not just horses:

- `FASCIA_OT_place_landmarks`: `"Place anatomical landmark points on the base mesh using the active species (file, inline JSON, or built-in horse)"`
- `FASCIA_OT_generate_muscles`: `"Generate muscle shapes between the placed landmarks using the active species (file, inline JSON, or built-in horse)"`
- `FASCIA_OT_bind_landmarks_to_rig`: unchanged (already mentions `fascia_bone`).

---

## 5. What you must NOT change

- Do NOT change the volume-preserving contraction math, shape-key safety, the bake pipeline, `FASCIA_OT_simulate_motion`, `FASCIA_OT_bake_flex_pose`, rig binding (Spec 7), or muscle insertion tracking (Spec 8).
- Do NOT change `_load_species` (Spec 6) — add `_load_species_json` alongside it. Spec 6 callers keep working.
- Do NOT change `HORSE_LANDMARKS`, `HORSE_MUSCLES`, or `species/equine_horse.json`.
- Do NOT change the operator `execute()` return contract — operators return `{"FINISHED"}`/`{"CANCELLED"}`, not dicts. The status query uses `self.report()`, the same channel every other operator uses.
- Do NOT add an MCP server, an RPC layer, a `run_pipeline` meta-operator, or any new transport. The Blender MCP server's `execute_blender_code` is the transport; Fascia's operators are the surface.
- Do NOT add a multiline text editor for `fascia_species_json` — a plain StringProperty field is enough. The LLM sets it programmatically.
- Do NOT return vertex counts, coordinate dumps, muscle radii, or any mesh data from `fascia.get_status` (rule 5). The summary is workflow state only: base, species, counts, rig, flex.
- Do NOT change the registration/unregistration order of existing classes or properties. The new property is registered after `fascia_species_path`; the new operator is added to the `classes` tuple.
- Do NOT add new imports — `json` and `bpy` are already imported.
- Do NOT gate the existing operators on `fascia_species_json` being set. The resolution order falls back to embedded horse data; the LLM can drive the horse workflow without ever setting the JSON property.

---

## 6. Verification

After the edit: reload the add-on in Blender. The scene from Spec 7/8 verification (horse base, 29 landmarks, 29 muscles, TestRig armature) is a fine starting point — clear it down to just the base mesh for the inline-anatomy test, or use it as-is for the status-query test.

1. **`fascia_species_json` property exists and defaults to empty.** Verify via Python: `bpy.types.Scene.fascia_species_json is not None` and `bpy.context.scene.fascia_species_json == ""`. No-regression: `fascia_species_path` still exists and still works.

2. **Status query reports the current state (no-regression on the Spec 7/8 scene).** With the existing scene (horse base, 29 landmarks, 29 muscles, TestRig bound), call `bpy.ops.fascia.get_status()`. The INFO report reads approximately: `Fascia: base=Fascia_Horse_Real, species=Equine Horse, landmarks=29, muscles=29, rig=TestRig, flex=0.0`. No mesh data in the string.

3. **Inline JSON overrides embedded horse data.** Set `scene.fascia_species_path = ""` (clear it) and `scene.fascia_species_json = <a minimal valid species JSON with 2 landmarks and 1 muscle>`. Clear all existing Fascia objects (landmarks + muscles). Call `bpy.ops.fascia.place_landmarks()` → the landmark count matches the JSON's landmark count (2 for a non-bilateral set, or 2*N for bilateral). Call `bpy.ops.fascia.generate_muscles()` → the muscle count matches the JSON's muscle count. The status query reports the JSON's species name. This is the key LLM-facing functionality.

4. **File path beats JSON string (priority order).** Set BOTH `fascia_species_path` (pointing at `species/equine_horse.json`) and `fascia_species_json` (pointing at a different species). Clear Fascia objects. Call `place_landmarks` + `generate_muscles`. The landmark/muscle counts match the FILE's species (horse: 29 landmarks, 29 muscles), not the JSON string's species. This confirms the file-beats-string priority (§2b).

5. **Invalid JSON string falls back gracefully.** Set `fascia_species_path = ""` and `fascia_species_json = "not valid json{"`. Clear Fascia objects. Call `place_landmarks` → it falls back to embedded horse data (29 landmarks), does not raise. The console prints `Fascia: error parsing species JSON string: ...`. This confirms the error-handling fallback.

6. **Empty JSON string + empty file path = embedded horse (no-regression).** Set both `fascia_species_path = ""` and `fascia_species_json = ""`. Call `place_landmarks` + `generate_muscles` → 29 landmarks, 29 muscles (embedded horse). Identical to pre-Spec-9 behaviour. This is the backwards-compatibility gate.

7. **Status query with no base mesh.** Delete (or temporarily hide) the base mesh. Call `get_status` → report reads `Fascia: base=none, ...`. Does not crash. Restores the base mesh after.

8. **All six existing operators still work (no-regression).** Run the full workflow once: place landmarks → generate muscles → bind to rig → set flex=0.5 → simulate motion → bake. Every step completes with its existing INFO report. The Spec 8 Damped Track constraints are still present on regenerated muscles (Spec 8 is not broken by the species-resolution change).

Report: checks 6 and 8 are the no-regression gates (must pass). Checks 3, 4, 5 are the new inline-anatomy functionality (must pass). Check 2 is the status query. Check 1 is the property registration. Check 7 is the edge case.

---

## 7. Known limitations (must be documented in code comments, NOT hidden)

- **No structured-data return from operators.** `fascia.get_status` reports via `self.report({'INFO'}, <string>)`, which the MCP server captures as stdout. An LLM that needs a machine-parsed dict must call a dedicated Python function (not provided by this spec) or parse the string. A future "Fascia MCP bridge" addon could wrap the operators and return dicts, but that is a separate project.
- **No automatic workflow orchestration.** The LLM must call operators in the right order (place landmarks → generate muscles → bind → flex → simulate → bake). `get_status` helps the LLM decide what to do next, but it does not drive the workflow. A `run_pipeline` meta-operator is possible but violates rule 3 (each tool does one clear job) until there is a clear reason to add it.
- **`fascia_species_json` is a plain text field in the panel, not a multiline editor.** A human editing a large species JSON in the panel will have a poor experience. The human-facing path is `fascia_species_path` (file picker); the JSON string is primarily for LLM use. Documented in the property description.
- **No validation of individual landmark/muscle entries.** Same as Spec 6: `_load_species_json` checks only that the top-level `landmarks` and `muscles` keys exist. Bad data (e.g. a muscle referencing a non-existent landmark) surfaces as a key error at the operator level, not a friendly validation message. Out of scope to improve here.
- **The JSON string is not persisted to disk.** If the user saves the .blend, the string is saved as a Scene property (standard Blender behaviour). But there is no "export species JSON to file" operator — if the LLM wants a reusable file, it writes one itself and uses `fascia_species_path`. Out of scope.
- **`get_status` resolves the species name by re-loading the file/JSON.** This is a cheap operation (file read + JSON parse, or JSON parse), but it runs on every status call. Acceptable for a query operator called occasionally. Do not call it in a tight loop.
- **No MCP tool registration.** Fascia operators are callable through the Blender MCP server's `execute_blender_code` transport, not as dedicated MCP tools. A future "Fascia MCP bridge" could register them; out of scope here (§2e).

These are honest scope boundaries, not bugs. Do NOT silently work around them.

---

## 8. Deliverable back to the captain

- The updated `fascia_addon.py` written to `C:\Projects\Fascia\fascia_addon.py`.
- A short note confirming:
  - Only the 5 locations in section 4 were changed (4a new helper, 4b new property + unregister, 4c-4d two species-resolution blocks, 4e new operator, 4f panel field, 4g classes tuple, 4h three description strings — count them as 5 conceptual changes across ~8 edit sites).
  - The verification results from section 6 (especially the no-regression checks 6 and 8, and the new-functionality checks 3, 4, 5).
  - That the "no structured-data return from operators" limitation (§7 bullet 1) is documented in the `get_status` operator's docstring.

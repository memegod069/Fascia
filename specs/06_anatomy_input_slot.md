# SPEC 06 — Anatomy Input Slot (Species-Definition Files)

**Target executor:** DeepSeek.
**Scope:** Extract the hardcoded `HORSE_LANDMARKS` and `HORSE_MUSCLES` data tables from `fascia_addon.py` into an external JSON species-definition file (`species/equine_horse.json`). Add a `Scene.fascia_species_path` string property so `place_landmarks` and `generate_muscles` can load any species file instead of only the horse. The embedded tables stay as fallback (backwards-compatible, single-file add-on). Does NOT change how landmarks are placed or how muscles are generated — only *where the data comes from*.
**Estimated size:** ~60 lines added/changed across 5 locations in `fascia_addon.py`, plus one new JSON file.

---

## 1. Why this change is needed

`place_landmarks` and `generate_muscles` read hardcoded `HORSE_LANDMARKS` and `HORSE_MUSCLES` Python dicts. This means Fascia today is a **horse-only add-on** — the LLM (muscle TD) cannot define a different creature's anatomy. For the product thesis to hold (`Fascia = the flesh + the wires`), the tools must accept any creature's anatomy as input. The horse is the first data file, not the only one (rule 11).

This spec does **Step 1** of the anatomy input slot: extract the horse data into a loadable file format so the architecture exists. A follow-up will add the LLM-facing `fascia_species_json` parameter for passing anatomy inline (no file I/O).

---

## 2. Design

### 2a. Species JSON schema

A species-definition JSON file has two top-level keys:

```json
{
  "name": "Equine Horse",
  "landmarks": { ... },
  "muscles": { ... }
}
```

**`landmarks`** mirrors the current `HORSE_LANDMARKS` dict exactly:
```json
"landmarks": {
  "Poll":            {"pos": [0.840, 0.500, 0.920], "bilateral": false, "region": "head"},
  "ScapulaTop":      {"pos": [0.660, 0.670, 0.920], "bilateral": true,  "region": "shoulder"},
  ...
}
```
- `pos` is `[u, v, w]` (normalized 0–1, mapped to base mesh bounding box).
- `bilateral` is `true`/`false`.
- `region` is a string grouping label.

**`muscles`** mirrors `HORSE_MUSCLES`:
```json
"muscles": {
  "Trapezius":         {"from": "Withers",         "to": "ScapulaTop",      "radius": 0.017, "color": [0.80, 0.20, 0.15, 0.60]},
  ...
}
```
- `from`, `to` match landmark keys.
- `radius` is a fraction of the base mesh's longest bounding-box side (mesh-agnostic).
- `color` is `[r, g, b, a]` in 0–1 range.

**Constants** (`MAX_CONTRACTION`, `MUSCLE_INFLUENCE_FRACTION`) stay in Python — they are add-on tuning parameters, not anatomy data.

### 2b. Species file path

A new `Scene` string property `fascia_species_path`:
- Default: `""` (empty) — means "use the embedded horse data".
- When set to a path: the tools load landmarks + muscles from that file.
- The panel gets a simple text field + a "Browse" button (file selector for `.json` files).
- The LLM can set this property directly via `bpy.context.scene.fascia_species_path = "C:/path/to/species.json"`.

### 2c. Loader helper

```python
def _load_species(filepath):
    """Load a species-definition JSON file and return
    (landmarks_dict, muscles_dict) compatible with the
    existing HORSE_LANDMARKS / HORSE_MUSCLES format.
    Returns (None, None) if the file cannot be loaded."""
```

- Opens and parses the JSON file.
- Validates minimal structure (has `landmarks` and `muscles` keys).
- Returns Python dicts identical in shape to `HORSE_LANDMARKS` / `HORSE_MUSCLES`.
- On error: reports via `print()` (Blender console) and returns `(None, None)` — the tool will fall back to embedded data.

### 2d. Tool changes

**`place_landmarks`** — change the data source from:
```python
for name, data in HORSE_LANDMARKS.items():
```
to:
```python
landmarks_data = HORSE_LANDMARKS  # default fallback
if scene.fascia_species_path:
    loaded_lm, _ = _load_species(scene.fascia_species_path)
    if loaded_lm:
        landmarks_data = loaded_lm

for name, data in landmarks_data.items():
```

**`generate_muscles`** — the same pattern, but it also reads `HORSE_LANDMARKS` for bilateral info (lines 797–798). Both must come from the same species file. Change to:
```python
landmarks_data = HORSE_LANDMARKS
muscles_data = HORSE_MUSCLES
if scene.fascia_species_path:
    loaded_lm, loaded_ms = _load_species(scene.fascia_species_path)
    if loaded_lm and loaded_ms:
        landmarks_data = loaded_lm
        muscles_data = loaded_ms

for muscle_name, mdata in muscles_data.items():
    from_bilateral = landmarks_data[from_key]["bilateral"]
    to_bilateral = landmarks_data[to_key]["bilateral"]
    ...
```

### 2e. Embedded data stay

`HORSE_LANDMARKS` and `HORSE_MUSCLES` remain in the Python file as fallback defaults. This keeps the add-on single-file, backwards-compatible, and functioning without any external files. The `species/equine_horse.json` file is a **mirror** — it is the reference species-definition that matches the embedded data exactly.

---

## 3. Architectural decisions

1. **JSON over Python dict.** External files must be non-executable (safe to load from untrusted sources) and parseable by any tool (not just Python/Blender). JSON is the standard.
2. **Species path is a Scene property, not an operator parameter.** This survives undo/redo, can be set from the panel or via script, and persists with the scene. The LLM sets `scene.fascia_species_path` and then calls the operator — standard Blender property pattern.
3. **Embedded fallback stays.** The add-on must work out of the box with zero configuration. Empty species path = use the built-in horse. This keeps the user flow identical for horse work.
4. **Both landmarks and muscles come from the same file.** A species file always defines both. They are a matched pair — the muscle `from`/`to` keys reference landmark keys. Loading them from different files would cause key errors.
5. **No UI panel changes beyond the path field.** The panel layout stays the same — just add a single row for the species file path + browse button. No new operators needed.
6. **`MAX_CONTRACTION` and `MUSCLE_INFLUENCE_FRACTION` stay in Python.** These are add-on tuning parameters, not species anatomy. They affect contraction behaviour uniformly across all species. The LLM can set them directly.
7. **No species auto-detection.** The user/LLM must explicitly set the path. No scanning directories, no guessing from mesh name. Explicit > implicit.
8. **Do not overclaim.** This spec only enables loading species from files. It does NOT add inline JSON input (`fascia_species_json`), remote loading, species validation beyond minimal structure checks, or a species library browser.

---

## 4. The exact changes

### 4a. Create `species/equine_horse.json`

Create a new directory `species/` with a single JSON file mirroring the embedded data exactly. The JSON arrays use `[ ]` syntax (Python tuples `( )` become `[ ]`; `True`/`False` become `true`/`false`).

```json
{
  "name": "Equine Horse",
  "landmarks": {
    "Poll":            {"pos": [0.840, 0.500, 0.920], "bilateral": false, "region": "head"},
    "NuchalCrest":     {"pos": [0.825, 0.500, 0.880], "bilateral": false, "region": "neck"},
    "Withers":         {"pos": [0.640, 0.500, 0.980], "bilateral": false, "region": "back"},
    "ScapulaTop":      {"pos": [0.660, 0.670, 0.920], "bilateral": true,  "region": "shoulder"},
    "PointOfShoulder": {"pos": [0.700, 0.720, 0.780], "bilateral": true,  "region": "shoulder"},
    "Elbow":           {"pos": [0.680, 0.650, 0.530], "bilateral": true,  "region": "forelimb"},
    "FrontKnee":       {"pos": [0.660, 0.630, 0.430], "bilateral": true,  "region": "forelimb"},
    "Chest":           {"pos": [0.580, 0.500, 0.420], "bilateral": false, "region": "chest"},
    "MidBack":         {"pos": [0.500, 0.500, 0.950], "bilateral": false, "region": "back"},
    "BellyMid":        {"pos": [0.450, 0.500, 0.380], "bilateral": false, "region": "belly"},
    "PointOfHip":      {"pos": [0.320, 0.750, 0.780], "bilateral": true,  "region": "hip"},
    "PointOfCroup":    {"pos": [0.240, 0.500, 0.930], "bilateral": false, "region": "hip"},
    "PointOfButtock":  {"pos": [0.080, 0.680, 0.730], "bilateral": true,  "region": "hip"},
    "HipJoint":        {"pos": [0.300, 0.620, 0.660], "bilateral": true,  "region": "hip"},
    "Stifle":          {"pos": [0.260, 0.700, 0.670], "bilateral": true,  "region": "hindlimb"},
    "Hock":            {"pos": [0.200, 0.680, 0.470], "bilateral": true,  "region": "hindlimb"},
    "SerratusAnchor":  {"pos": [0.660, 0.580, 0.500], "bilateral": true,  "region": "shoulder"},
    "LatAnchor":       {"pos": [0.650, 0.680, 0.360], "bilateral": true,  "region": "forelimb"}
  },
  "muscles": {
    "Trapezius":         {"from": "Withers",         "to": "ScapulaTop",      "radius": 0.017, "color": [0.80, 0.20, 0.15, 0.60]},
    "Deltoid":           {"from": "ScapulaTop",      "to": "PointOfShoulder", "radius": 0.014, "color": [0.90, 0.35, 0.10, 0.60]},
    "Triceps":           {"from": "ScapulaTop",      "to": "Elbow",           "radius": 0.019, "color": [0.70, 0.12, 0.12, 0.60]},
    "BicepsBrachii":     {"from": "PointOfShoulder", "to": "Elbow",           "radius": 0.014, "color": [0.85, 0.45, 0.35, 0.60]},
    "Pectorals":         {"from": "Chest",           "to": "PointOfShoulder", "radius": 0.019, "color": [0.82, 0.30, 0.30, 0.60]},
    "SerratusVentralis": {"from": "Chest",           "to": "SerratusAnchor",  "radius": 0.017, "color": [0.78, 0.35, 0.40, 0.60]},
    "LatissimusDorsi":   {"from": "MidBack",         "to": "LatAnchor",       "radius": 0.019, "color": [0.72, 0.22, 0.18, 0.60]},
    "Brachiocephalicus": {"from": "Poll",            "to": "PointOfShoulder", "radius": 0.014, "color": [0.88, 0.50, 0.30, 0.60]},
    "LongissimusDorsi":  {"from": "Withers",         "to": "PointOfCroup",    "radius": 0.017, "color": [0.65, 0.18, 0.18, 0.60]},
    "RectusAbdominis":   {"from": "Chest",           "to": "PointOfHip",      "radius": 0.014, "color": [0.75, 0.55, 0.40, 0.60]},
    "GluteusMedius":     {"from": "PointOfHip",      "to": "HipJoint",        "radius": 0.028, "color": [0.20, 0.22, 0.78, 0.60]},
    "BicepsFemoris":     {"from": "PointOfButtock",  "to": "Stifle",          "radius": 0.019, "color": [0.30, 0.30, 0.85, 0.60]},
    "Semitendinosus":    {"from": "PointOfButtock",  "to": "Hock",            "radius": 0.017, "color": [0.40, 0.38, 0.75, 0.60]},
    "Quadriceps":        {"from": "HipJoint",        "to": "Stifle",          "radius": 0.019, "color": [0.45, 0.25, 0.70, 0.60]},
    "Gastrocnemius":     {"from": "Stifle",          "to": "Hock",            "radius": 0.014, "color": [0.55, 0.42, 0.78, 0.60]}
  }
}
```

### 4b. Add the `_load_species` helper

Insert between `_get_base_size` (line 81) and `_clear_skin_tags` (line 84):

```python
import json
import os

def _load_species(filepath):
    """Load a species-definition JSON file and return
    (landmarks_dict, muscles_dict, species_name).

    The file must have 'landmarks' and 'muscles' keys.
    Returns (None, None, None) on error (file missing,
    invalid JSON, or missing required keys) — the
    caller falls back to embedded HORSE_* data.

    Species files let external LLMs define any
    creature's anatomy as the muscle TD (rule 10/11).
    The horse is the first data file, not the only one.
    """
    if not os.path.isfile(filepath):
        print("Fascia: species file not found: " + filepath)
        return None, None, None

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except Exception as e:
        print("Fascia: error reading species file: " + str(e))
        return None, None, None

    if "landmarks" not in data or "muscles" not in data:
        print("Fascia: species file missing 'landmarks' or 'muscles' key")
        return None, None, None

    return data["landmarks"], data["muscles"], data.get("name", "Unknown")
```

If `json` and `os` are not already imported, add them at the top of the file. (Check current imports first — `os` is likely used; `json` may need adding.)

### 4c. Add `Scene.fascia_species_path` property

In `register()`, after the existing Scene property registrations, add:

```python
    bpy.types.Scene.fascia_species_path = bpy.props.StringProperty(
        name="Species File",
        description="Path to a species-definition JSON file. Empty = use the built-in horse anatomy",
        default="",
        subtype='FILE_PATH',
    )
```

In `unregister()`, before the existing `del bpy.types.Scene.fascia_*` lines, add:

```python
    del bpy.types.Scene.fascia_species_path
```

### 4d. Modify `place_landmarks` to load from species file

In `FASCIA_OT_place_landmarks.execute`, at the start of the function (after the base-mesh check), add:

```python
        # Use species file if configured; fall back to embedded horse data
        landmarks_data = HORSE_LANDMARKS
        species_name = "Horse"
        species_path = context.scene.fascia_species_path
        if species_path:
            loaded_lm, _, loaded_name = _load_species(species_path)
            if loaded_lm:
                landmarks_data = loaded_lm
                species_name = loaded_name or "Unknown"
```

Then change the iteration from:
```python
        for name, data in HORSE_LANDMARKS.items():
```
to:
```python
        for name, data in landmarks_data.items():
```

Update the report message from `str(placed_count) + " landmarks placed"` to include the species name:
```python
        self.report({'INFO'}, str(placed_count) + " landmarks placed for " + species_name)
```

### 4e. Modify `generate_muscles` to load from species file

In `FASCIA_OT_generate_muscles.execute`, at the start (after the landmark existence check and before the recruitment snapshot), add:

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

Then change:
- Line 679: `for name, data in HORSE_LANDMARKS.items():` → iterate over `landmarks_data` instead (wait, that's in place_landmarks, not generate_muscles)
- Line 794: `for muscle_name, mdata in HORSE_MUSCLES.items():` → `muscles_data`
- Line 797: `HORSE_LANDMARKS[from_key]["bilateral"]` → `landmarks_data[from_key]["bilateral"]`
- Line 798: `HORSE_LANDMARKS[to_key]["bilateral"]` → `landmarks_data[to_key]["bilateral"]`

Update the report message:
```python
        self.report({'INFO'}, str(muscle_count) + " muscles generated for " + species_name)
```

### 4f. Add species path field to the panel

In `FASCIA_PT_main_panel.draw`, in the Setup section (after the "Use Selected as Base" button), add:

```python
        # Species file selector (Spec 6). Empty = use built-in horse.
        layout.prop(scene, "fascia_species_path", text="")
        row = layout.row(align=True)
        row.label(text="Species: ")
        row.prop(scene, "fascia_species_path", text="")
```

Actually, the `FILE_PATH` subtype gives a browse button automatically. A simple:
```python
        layout.prop(scene, "fascia_species_path", text="Species File")
```
is sufficient — it renders as a text field with a folder icon for browsing.

---

## 5. What you must NOT change

- Do NOT change the landmark placement math (`min_x + u * size_x`, etc.). Only the data source changes.
- Do NOT change the muscle creation logic (`create_muscle_mesh`, landmark lookup, material assignment).
- Do NOT change `HORSE_LANDMARKS` or `HORSE_MUSCLES` dicts (they stay as fallback).
- Do NOT change `MAX_CONTRACTION` or `MUSCLE_INFLUENCE_FRACTION`.
- Do NOT touch shape-key logic, the backup system, flex math, or the bake pipeline.
- Do NOT touch `FASCIA_OT_simulate_motion` or `FASCIA_OT_bake_flex_pose`.
- Do NOT add inline JSON input (`fascia_species_json`), species validation beyond minimal structure checks, remote loading, or a species browser. These are future work.
- Do NOT change the registration/unregistration order of existing classes or properties.
- Do NOT add new imports that aren't needed (`json` and `os` are the only ones — check if `os` is already imported).

---

## 6. Verification

After the edit: reload the add-on in Blender, ensure a base mesh is tagged, then:

1. **Default behaviour identical (no species path):** without setting `fascia_species_path`, click "Place Landmarks" → the same 19 landmarks appear at the same positions as before. Click "Generate Muscles" → the same 29 instances appear. Compare positions of 3 sample landmarks (e.g. Poll, PointOfHip_R, Stifle_L) — same world position as before.

2. **Species file loads correctly:** set `scene.fascia_species_path` to the absolute path of `species/equine_horse.json`. Run Place Landmarks and Generate Muscles again — identical result to check 1 (the JSON is an exact mirror of the embedded data).

3. **Species file error handling:** set `fascia_species_path` to a non-existent path → tools use embedded data, no crash, a print message appears in the Blender console.

4. **Bilateral resolution still works:** with the species file loaded, confirm that bilateral landmarks look up correctly in `landmarks_data`. Check that `ScapulaTop_R` and `ScapulaTop_L` both exist and produce correct mirroring. Check that a midline-only muscle like `LongissimusDorsi` creates exactly one instance.

5. **Report messages include species name:** after Place Landmarks, the status message reads "19 landmarks placed for Equine Horse" (or "for Horse" when using embedded data).

6. **Species path persists:** set `fascia_species_path`, save and reload the blend file → the path is still set, tools still load from it.

Report: the 3 sample landmark positions match between check 1 and check 2 (within floating-point tolerance). The error-handling check (3) produces a console message and no crash. Check 4 produces correct mirroring.

---

## 7. Known limitations (must be documented in code comments, NOT hidden)

- **File-path only, no inline input.** The LLM must write a JSON file to disk and set the path. Inline JSON string input (`fascia_species_json`) is a future step.
- **No species validation beyond structure.** The loader checks for `landmarks` and `muscles` keys but does not validate individual entries (e.g. missing `pos` keys, invalid `radius` values). Bad data will fail at the operator level (key errors on lookup).
- **No species library browser.** The user must know the file path. No "Select Species" dropdown scanning a directory.
- **No bundled species beyond horse.** Only `species/equine_horse.json` ships with the add-on. Additional species (canine, feline, alien) are user-provided.
- **Single-file add-on unchanged.** The embedded `HORSE_*` dicts are not removed — the add-on works without any external files.
- **No species auto-detection from mesh.** The user/LLM must explicitly set the path. No heuristic guessing.

These are honest scope boundaries, not bugs. Do NOT silently work around them.

---

## 8. Deliverable back to the captain

- The new `species/equine_horse.json` file.
- The updated `fascia_addon.py` written to `C:\Projects\Fascia\fascia_addon.py`.
- A short note confirming:
  - Only the 6 locations in section 4 were changed (4a new file, 4b `_load_species` helper, 4c property registration, 4d `place_landmarks` data source, 4e `generate_muscles` data source, 4f panel field).
  - The verification results from section 6.

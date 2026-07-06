# Species JSON Schema Reference

A species file defines a creature's anatomy for Fascia's landmark and muscle tools.
The file is standard JSON. The horse reference is at `species/equine_horse.json`.

## Top-Level Keys

| Key | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Display name for the species (shown in status + UI label) |
| `landmarks` | object | Yes | Dict of landmark definitions |
| `muscles` | object | Yes | Dict of muscle definitions |

## Landmark Definition

```json
"LandmarkName": {
  "pos":       [0.5, 0.5, 0.9],
  "bilateral": false,
  "region":    "back",
  "bone":      "spine.003",
  "note":      "Optional human-readable note"
}
```

| Key | Type | Required | Description |
|---|---|---|---|
| `pos` | [float, float, float] | Yes | Normalized [0,1] UVW position in bounding box |
| `bilateral` | bool | Yes | If true, two empties are created: Name_L and Name_R, mirrored on Y axis |
| `region` | string | Yes | Anatomical region label (used for documentation only) |
| `bone` | string | No | Explicit bone name for rig binding. Bilateral landmarks: _L gets this name, _R gets the .L→.R mirrored name. If bone not found, falls back to nearest-bone auto-binding. |
| `note` | string | No | Human-readable note (ignored by the addon) |

### Position (pos) System

`pos = [u, v, w]` where:
- `u = 0.0` → back of creature (negative X), `u = 1.0` → front
- `v = 0.0` → left side (negative Y), `v = 0.5` → centerline, `v = 1.0` → right side
- `w = 0.0` → bottom (negative Z), `w = 1.0` → top

The addon maps pos to the base mesh's world-space bounding box at runtime.

## Muscle Definition

```json
"MuscleName": {
  "from":       "LandmarkA",
  "to":         "LandmarkB",
  "radius":     0.02,
  "color":      [0.8, 0.2, 0.1, 0.6],
  "antagonist": "OtherMuscleName",
  "bilateral":  false
}
```

| Key | Type | Required | Description |
|---|---|---|---|
| `from` | string | Yes | Origin landmark name. Must exist in `landmarks`. |
| `to` | string | Yes | Insertion landmark name. Must exist in `landmarks`. |
| `radius` | float | Yes | Muscle radius as a fraction of the base mesh's longest bounding-box side |
| `color` | [R, G, B, A] | No | Viewport color (0.0–1.0 each). 3-element [R,G,B] is auto-padded to RGBA. Default: red. |
| `antagonist` | string | No | Name of the antagonist muscle. When this muscle contracts, the named muscle relaxes proportionally. |
| `bilateral` | bool | No | If `from` or `to` is a bilateral landmark, the muscle is automatically created for both sides. This is implicit — you do not need to set this manually. |

## Validation

The addon validates anatomy before creating any scene objects:
- Every landmark must have `pos` (3 elements).
- Every muscle must have `from`, `to`, and `radius`.
- Every `from`/`to` must reference a landmark name that exists in the same file.
- 3-element colors are auto-padded to RGBA with a warning.
- Invalid files cancel the operation and report errors without modifying the scene.

## Example — Minimal Biped

```json
{
  "name": "Simple Biped",
  "landmarks": {
    "Head":        {"pos": [0.5, 0.5, 0.95], "bilateral": false, "region": "head"},
    "Shoulder":    {"pos": [0.5, 0.7, 0.80], "bilateral": true,  "region": "shoulder"},
    "Hip":         {"pos": [0.5, 0.6, 0.50], "bilateral": true,  "region": "hip"},
    "Knee":        {"pos": [0.5, 0.6, 0.30], "bilateral": true,  "region": "leg"}
  },
  "muscles": {
    "LatTrap":     {"from": "Head",     "to": "Shoulder", "radius": 0.015, "color": [0.8, 0.2, 0.1, 0.6]},
    "Glute":       {"from": "Hip",      "to": "Knee",     "radius": 0.022, "color": [0.2, 0.3, 0.8, 0.6]}
  }
}
```

This creates 1 Head + 2 Shoulders + 2 Hips + 2 Knees = 7 landmarks, and 1 + 2 = 3 muscles (bilateral muscles are created for both sides automatically).

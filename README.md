# Fascia

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B-orange.svg)](https://www.blender.org/)
[![Status: Work in Progress](https://img.shields.io/badge/status-work%20in%20progress-red.svg)]()

**Fascia** is a free, open-source Blender add-on that provides the **soft-tissue layer** for creature creation — muscles, fascia, fat, and skin layers on top of a rigged mesh.

> **Honest status:** This is a working prototype, not a production tool. The core pipeline works end-to-end on a real horse mesh. Known limitations are documented below.

---

## What Fascia Is

- A **toolbox**: each tool does one job and reports a plain-English status message.
- A **harness for LLMs**: external AI can define any creature's anatomy as a JSON file and drive all tools via `bpy.ops.fascia.*`. Fascia is the hands; the LLM is the brain.
- A **Blender-native** alternative to proprietary tools (Ziva VFX is discontinued; Weta Tissue is internal-only and not a product).

## What Fascia Is NOT

- **Not an AI model** — no LLM inside the add-on.
- **Not a mesh generator** — bring your own creature mesh.
- **Not a rigging tool** — rigging is Blender's job.
- **Not real FEM physics** — contraction is geometric and volume-preserving (shorten + bulge by formula), not a physics simulation. This is honest and documented throughout.

---

## Installation

### Option A — Zip Install (recommended for users)

1. Download the latest release zip from [Releases](../../releases).
2. In Blender: **Edit → Preferences → Add-ons → Install** → select the zip.
3. Enable **Fascia** in the add-on list.
4. The **Fascia** tab appears in the **View3D sidebar** (press `N`).

### Option B — Development Symlink (for contributors)

```bash
# Clone the repo
git clone https://github.com/memegod069/Fascia.git

# Symlink (or copy) fascia_addon.py into Blender's scripts/addons folder
# Windows example:
mklink "C:\Users\<You>\AppData\Roaming\Blender Foundation\Blender\4.x\scripts\addons\fascia_addon.py" "C:\path\to\Fascia\fascia_addon.py"
```

Then enable in Blender Preferences as above. Use **Scripts → Reload Scripts** (`Alt+R`) to pick up changes without restarting.

---

## Quick Start (Tools 1–7 + 9)

1. **Tool 1 — Load Base Mesh**
   - Select your creature mesh → click **"Use Selected as Base"**
   - Or click **"Make Placeholder Horse"** to create a test blob.

2. **Tool 2 — Customize Sliders** (placeholder only)
   - Age / Fat / Color sliders affect the placeholder horse's scale and viewport color.

3. **Tool 3 — Place Landmarks**
   - Optionally point **Species File** at a JSON anatomy file (see `species/equine_horse.json` for format).
   - Click **"Place Landmarks"** — empty objects appear at anatomical positions, sized to your mesh's bounding box.

4. **Tool 4 — Generate Muscles**
   - Click **"Generate Muscles"** — stretched-sphere muscle objects appear between landmarks, sized proportionally.
   - Each muscle gets a Damped Track constraint so it reorients toward its insertion landmark.

5. **Tool 5 — Bind Skin (Flex Slider)**
   - Optionally set **Rig** to an armature and click **"Bind Landmarks to Rig"** so landmarks follow bones.
   - Drag the **Flex** slider — muscles shorten + bulge (volume-preserving), skin deforms.
   - Toggle **Skin Sliding** to enable tangential skin movement along muscle axes.

6. **Tool 6 — Simulate Motion**
   - Click **"Simulate Motion"** — keyframes flex 0→1→0→1→0 over 60 frames.

7. **Tool 7 — Bake Result**
   - Click **"Bake Result"** — creates `Baked_Frame_NNN` shape keys for 12 sampled frames.

9. **Tool 9 — Status Query** (for LLM / scripting)
   - `bpy.ops.fascia.get_status()` — reports base mesh name, species, landmark/muscle counts, rig, flex value.

---

## What Works / Known Limitations

| Feature | Status | Notes |
|---|---|---|
| Landmark placement | ✅ Real | Normalized to bounding box; works on any mesh |
| Mesh-agnostic muscle sizing | ✅ Real | Radii = fractions of bounding box longest side |
| Volume-preserving contraction | ✅ Real | `L·(1−c)`, `r/√(1−c)`, volume `πr²L` constant |
| Muscle origin pinning | ✅ Real | Origin end stays fixed; insertion shortens toward it |
| Per-muscle recruitment | ✅ Real | UIList slider per muscle; `c_i = flex·0.25·r_i` |
| KDTree-accelerated skin push | ✅ Real | Replaces O(V·M) loop with O(V·log M) |
| Skin sliding (axial) | ✅ Real | Tangential slide proportional to shortening |
| Rig binding (bone parenting) | ✅ Real | `parent_set(type='BONE', keep_transform=True)` |
| Muscle insertion tracking | ✅ Real | Damped Track constraint; rotation-only, no scale conflict |
| Antagonist pairing | ✅ Real | Reciprocal inhibition; side-specific suffix matching |
| LLM-facing surface | ✅ Real | Inline JSON species, `get_status` operator |
| FEM physics | ❌ Not real | Geometric approximation only — honest design choice |
| Automatic creature generation | ❌ Not real | LLM drives tools; Fascia is the hands |
| Standing-pose test mesh | ⚠️ Deferred | Current horse is in a dynamic (non-standing) pose |
| Muscle stretch to insertion | ⚠️ Known gap | Damped Track fixes angle; length mismatch remains |
| Skin relaxation solver | ⚠️ Deferred | Vertices slide independently, no surface tension |
| Performance on 700k+ meshes | ⚠️ Slow | Pure Python loop; ~30s per update_flex call |

---

## For LLM / External Tool Users

Fascia exposes a scriptable surface via Blender's Python API:

```python
import bpy

# 1. Point at your base mesh
bpy.data.objects["YourMesh"]["fascia_role"] = "skin"

# 2. Load anatomy inline (no file needed)
bpy.context.scene.fascia_species_json = '{ "name": "Alien", "landmarks": {...}, "muscles": {...} }'

# 3. Run the pipeline
bpy.ops.fascia.place_landmarks()
bpy.ops.fascia.generate_muscles()

# 4. Query state
bpy.ops.fascia.get_status()   # output captured via self.report() → stdout/MCP

# 5. Flex
bpy.context.scene.fascia_flex = 0.8

# 6. Bake
bpy.ops.fascia.bake_flex_pose()
```

See `docs/llm-integration.md` for the full integration guide and `species/equine_horse.json` for the anatomy JSON schema.

---

## Species JSON Schema (brief)

```json
{
  "name": "Species Name",
  "landmarks": {
    "LandmarkName": {
      "pos": [0.0, 0.5, 1.0],
      "bilateral": false,
      "region": "back"
    }
  },
  "muscles": {
    "MuscleName": {
      "from": "LandmarkA",
      "to":   "LandmarkB",
      "radius": 0.02,
      "color": [0.8, 0.2, 0.1, 0.6],
      "antagonist": "OtherMuscleName"
    }
  }
}
```

`pos` values are normalized [0,1] UVW — mapped to the base mesh's bounding box at runtime. `bilateral: true` mirrors the landmark left and right. `antagonist` is optional.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

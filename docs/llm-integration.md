# LLM Integration Guide

Fascia is designed to be driven by an external LLM acting as the creature's "muscle TD".
This guide explains how to drive Fascia's tools from Python, an MCP server, or any scripting environment.

## The Pattern

1. Set the base mesh (tag it as skin).
2. Pass anatomy inline (JSON string) OR point at a species file.
3. Run operators in order: place_landmarks → generate_muscles → [bind_to_rig] → flex/simulate → bake.
4. Query state with get_status.

## Minimal Example — Alien Creature

```python
import bpy, json

# Step 1: Tag base mesh
bpy.data.objects["AlienMesh"]["fascia_role"] = "skin"

# Step 2: Define anatomy inline
anatomy = {
    "name": "Alien",
    "landmarks": {
        "CranialRidge": {"pos": [0.9, 0.5, 0.8], "bilateral": False, "region": "head"},
        "ThoraxTop":    {"pos": [0.5, 0.5, 0.9], "bilateral": False, "region": "torso"},
        "ThoraxSide":   {"pos": [0.5, 0.7, 0.6], "bilateral": True,  "region": "torso"}
    },
    "muscles": {
        "DorsalCord": {
            "from": "CranialRidge",
            "to":   "ThoraxTop",
            "radius": 0.03,
            "color": [0.2, 0.8, 0.4, 0.6]
        },
        "LateralFascia": {
            "from": "ThoraxTop",
            "to":   "ThoraxSide",
            "radius": 0.025,
            "color": [0.3, 0.7, 0.5, 0.6]
        }
    }
}
bpy.context.scene.fascia_species_json = json.dumps(anatomy)

# Step 3: Run pipeline
bpy.ops.fascia.place_landmarks()
bpy.ops.fascia.generate_muscles()
bpy.context.scene.fascia_flex = 0.8
bpy.ops.fascia.simulate_motion()
bpy.ops.fascia.bake_flex_pose()

# Step 4: Query state
bpy.ops.fascia.get_status()
# Output (via self.report → stdout/MCP):
# "Fascia: base=AlienMesh, species=Alien, landmarks=4, muscles=3, rig=None, flex=0.8"
```

## Priority Chain for Species Resolution

When an operator runs, it resolves anatomy in this order:
1. `scene.fascia_species_path` — explicit file path (wins over everything)
2. `scene.fascia_species_json` — inline JSON string (wins over embedded)
3. Embedded `HORSE_*` data — the built-in fallback

## Rules for LLM-Defined Anatomy

- `pos` values are UVW in [0,1] — mapped to the base mesh's bounding box at runtime.
- `bilateral: true` automatically mirrors the landmark left and right (appends `_L` / `_R`).
- `antagonist` is optional — omit it for muscles with no paired antagonist.
- `radius` is a fraction of the base mesh's longest bounding-box side (e.g. 0.02 = 2%).
- Do NOT include raw vertex coordinates — Fascia maps anatomy to any mesh via normalized positions.

## What get_status Reports

`bpy.ops.fascia.get_status()` emits a single line via `self.report({'INFO'}, ...)`:
```
Fascia: base=<mesh_name>, species=<species_name>, landmarks=<N>, muscles=<M>, rig=<rig_name|None>, flex=<value>
```

No vertex data, no coordinates, no mesh dumps (rule 5 in AGENTS.md).

## MCP Integration

If you are using the Blender MCP server:
- Set properties via `bpy.context.scene.fascia_species_json = "..."` before calling operators.
- Operators are called as `bpy.ops.fascia.<operator_id>()`.
- `self.report()` output is captured as stdout by the MCP server.

## Known Constraints

- All operators require Object Mode (they will fail in Edit/Sculpt/Paint mode).
- Flex updates are slow on high-vertex meshes (~30s per flex update in pure Python).
- The `get_status` operator is the ONLY way to query state — do not read raw mesh or vertex data.

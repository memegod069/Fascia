# Fascia End-to-End Testing — Issues Log

Test date: 2026-07-06
Test environment: Blender 5.1 (connected via MCP), 748k-vertex horse mesh
Test scope: Full add-on tool chain (Tools 1–7, 9)

## Tool Results Summary

| # | Tool | Status | Notes |
|---|------|--------|-------|
| 1 | Load Horse / Use Selected | PASS | Existing scene already had `Fascia_Horse_Real` |
| 2 | Customize Sliders | NOT TESTED | Age/Fat/Color only affect placeholder objects |
| 3 | Place Landmarks | PASS | 29 landmarks (19 types + bilateral) present |
| 4 | Generate Muscles | PASS | 29 muscles with Damped Track constraints present |
| 5 | Flex Slider | PASS | Volume-preserving: ls=0.75, ts=1.155, product=1.0 at flex=1 |
| 6 | Simulate Motion | PASS | 60-frame animation with flex keyframes on scene |
| 7 | Bake Result | PASS | 13 baked shape keys with correct frame-by-frame variation |
| 9 | Status Query | PASS | Reports base, species, landmark/muscle counts, rig, flex |

## Issues Found

### Issue 1: `Fascia_Horse_Real` missing `fascia_role="skin"` property

**Severity:** Critical (breaks skin push and bake)

When a mesh is imported or created without running `fascia.use_selected_as_base` (which tags it with `fascia_role="skin"`), `_get_skin_objects()` returns an empty list. This causes `update_flex()` to skip the skin-push vertex loop entirely — no deformation is applied to the mesh, and the bake captures only undeformed Basis data.

**Fix applied during test:** Manually set `obj["fascia_role"] = "skin"` on the base mesh.

**Root cause:** The blend file was set up externally (or from an earlier version of the add-on) without the tag. The existing operators do not retroactively tag untagged meshes.

### Issue 2: Performance — `update_flex` is extremely slow on large meshes

**Severity:** High (causes MCP timeouts on 748k-vertex mesh)

Each `update_flex` call processes ALL skin vertices with a KDTree query per vertex in pure Python. On 748k vertices:
- Single update: ~30+ seconds
- Simulate motion (5 calls): timeouts
- Full bake (13 calls): timeouts even at 10-minute limit

The inner loop at `fascia_addon.py:721-772` iterates over every vertex and calls `kd.find_range()`. For 67% of vertices, this leads to push computation. The `mesh.update()` at line 774 also blocks.

**Suggested fix:** 
- Option A: Port vertex loop to NumPy (not available in Blender by default)
- Option B: Implement a coarse culling pass (bounding box test before KDTree query)
- Option C: Use Blender's built-in `foreach_get`/`foreach_set` for batch processing
- Option D: Add a vertex count warning / async processing indicator
- Option E: Document the performance limitation for high-vertex meshes

### Issue 3: Live_Flex shape key data is stale at flex=0

**Severity:** Low (no visual impact, but could confuse API consumers)

When `flex < 0.001`, `update_flex` sets `live_key.value = 0.0` but does NOT clear/update `Live_Flex.data`. The vertex data remains from the last flex>0 state. This means reading `Live_Flex.data` while flex=0 returns the last flexed positions, not the rest pose. The weight of 0.0 means the stale data doesn't affect the visual mesh, but code reading the data (like external tools) would get wrong values.

**Affected code:** `fascia_addon.py:695-698` — `continue` after `live_key.value = 0.0` skips the vertex data refresh.

### Issue 4: Blender 5.1 animation API changes

**Severity:** Low (documentation gap)

In Blender 5.1, `Action` uses the new layered animation system (`ActionLayer` → `ActionKeyframeStrip` → `ActionChannelbag` → `FCurve`). The old `bpy.data.actions["SceneAction"].fcurves` API no longer works. Keyframe insertion via `scene.keyframe_insert()` still works. Reading keyframes requires:
```python
layer = action.layers[0]
strip = layer.strips[0]
cb = strip.channelbag(slot)
for fc in cb.fcurves: ...
```

This affects any code that reads or inspects animation data directly.

## Verification Data

| Metric | Value |
|--------|-------|
| Base mesh vertices | 748,704 |
| Landmarks | 29 |
| Muscles | 29 (all with Damped Track) |
| Volume preservation (flex=1) | ls=0.75, ts=1.155, product=1.0 |
| Affected vertices at flex=0.5 | 479,221 (64%) |
| Affected vertices at flex=1.0 | 504,815 (67.4%) |
| Max skin displacement | 0.628 units |
| Baked shape keys | 13 frames (1–60) |
| Max baked deformation | 0.426 units (frame 45) |
| Muscle constraints | 29 × Damped Track |

# SPEC 12 — Skin Sliding

**Target executor:** implementing agent.
**Scope:** Add a tangential (axial) skin-slide component to the flex skin deformation in `update_flex`, so skin follows the muscle's shortening along its length axis. New: one module constant, one Scene BoolProperty with a panel checkbox, an expanded `muscle_info` tuple, a larger KDTree query radius, and a two-component push loop in the inner vertex iteration. Does NOT touch the radial push formula, the volume-preserving scale math, shape-key safety, the backup system, muscle generation, species loading, rig binding, antagonist pairing, or the bake pipeline.
**Estimated size:** ~45 lines changed across 4 locations in `fascia_addon.py`.

---

## 1. Why this change is needed

The current skin deformation (Spec 3) is **radial only**. When a muscle contracts, each nearby skin vertex is pushed directly away from the muscle's belly center. This produces a visible bulge, but it misses half of what real skin does: **skin also slides along the muscle's length as the muscle shortens.**

When a pinned muscle shortens by factor `ls = (1 − c)` along its axis, the muscle surface at parametric position `s` (0 at the pinned origin, `rest_length` at the insertion) moves from `O + Â·s` to `O + Â·(s·ls)`. The surface point has slid by `s·(ls − 1) = −s·c` along the axis (negative = toward origin). Real skin follows this — it is dragged tangentially toward the origin, strongest at the insertion end and zero at the pinned origin. Without it, the skin at the insertion end stays put while the muscle pulls away from it, leaving the skin visibly "stretched" rather than following the contracting tissue underneath.

This is the documented limitation in every contraction spec since Spec 3: *"Radial skin push only; axial skin sliding is a future refinement."* Spec 12 is that refinement. It is unblocked now that the prerequisites are all in place:
- Correct radial bulge (Spec 3)
- Pinned origin (Spec 4) — the slide is anchored at the origin and accumulates toward the insertion
- Per-muscle length scale `ls_i` (Spec 5) — each muscle's slide is proportional to its own contraction
- Rig-aware world rotation (Spec 7) — the slide axis follows the rig
- Insertion direction tracking (Spec 8) — the slide axis points toward the insertion

---

## 2. The skin-sliding model

A pinned muscle has (all already available, no new stored fields):
- **Origin** `O` = `m.matrix_world.translation` (the pinned `from` landmark, does not move during contraction)
- **Axis** `Â` = `m.matrix_world.to_quaternion() @ Vector((0,0,1))`, normalized (points from origin toward insertion)
- **Rest length** `L` = `m["fascia_rest_length"]` (stored at generation, Spec 4)
- **Length scale** `ls_i` = `1 − c_i` (per-muscle, Spec 5)

When the muscle contracts, a point on the muscle surface at parametric position `s ∈ [0, L]` moves from `O + Â·s` to `O + Â·(s·ls_i)`. The surface point has slid by `s·(ls_i − 1) = −s·c_i` along the axis.

Skin is not rigidly attached to muscle. We apply this slide to nearby skin vertices with a **radial falloff from the muscle axis** (not from the belly center — the axial slide is about following the muscle's length, so the natural reference is the axis line):

For a skin vertex at world position `P`:
1. **Project onto the muscle axis:** `s = (P − O) · Â`
2. **Clamp** `s` to `[0, L]` (skin past the origin end gets `s=0` → no slide; skin past the insertion end gets `s=L` → full slide, matching the skin at the insertion)
3. **Radial distance from axis:** `r = |(P − O) − Â·s_clamped|`
4. **If** `r > influence_radius` or `r < 0.001`: skip (out of range, or on the axis — degenerate)
5. **Axial falloff:** `f_axial = (1 − r / influence_radius)²` (same falloff shape as the radial push)
6. **Slide amount:** `slide = s_clamped · (ls_i − 1.0) · SKIN_SLIDE_FRACTION` (negative = toward origin)
7. **Axial push:** `push += Â · slide · f_axial`

**Sanity checks:**
- At the origin (`s = 0`): slide = 0. ✓ (Origin is pinned; skin near it does not move.)
- At the insertion (`s = L`): slide = `L · (ls_i − 1)` = the full shortening gap, scaled by the radial falloff. ✓
- At rest (`ls_i = 1`): slide = 0 everywhere. ✓ (No change to rest appearance — acceptance criterion.)

**The radial push (Spec 3) is unchanged.** The total push on a vertex is the sum of:
- The existing radial push (away from the belly center, `push_dir · growth · falloff_center`)
- The new axial slide (along the muscle axis, `Â · slide · f_axial`)

Both use the same `influence_radius` for their respective falloffs, but **different reference points**: the radial push measures distance from the belly center `m_center`; the axial slide measures distance from the muscle axis (the line from `O` to `O + Â·L`).

---

## 3. Architectural decisions (read before changing anything)

1. **Slide is fully determined by existing physics — one named multiplier, not a tuned value.** `SKIN_SLIDE_FRACTION = 1.0` (default 1.0 = full physical sliding). This mirrors `MUSCLE_INFLUENCE_FRACTION` and `MAX_CONTRACTION` as a named, tunable module constant. Do NOT tune it to a specific mesh.

2. **Same `influence_radius` for both components.** The axial slide uses the same influence radius as the radial push. This is consistent and avoids a second radius constant. A vertex within `influence_radius` of the muscle axis gets both the radial push (if also near the belly center) and the axial slide; a vertex near the axis but far from the belly center gets only the axial slide.

3. **KDTree query radius must grow.** The current KDTree is built on belly centers and queried with `find_range(world_pos, influence_radius)`. A vertex near the insertion end (up to `L·ls_i/2` from the belly center) would be missed by the old query radius. The new query radius is `influence_radius + max_half_rest_length` where `max_half_rest_length` is the maximum `L/2` across all muscles (computed once, outside the vertex loop). The KDTree itself (on belly centers) is unchanged — only the query radius grows. Inside the loop, each component does its own distance check and skips out-of-range vertices.

4. **`muscle_info` tuple expands from 3 to 7 fields.** Each entry needs the origin, axis, rest length, and per-muscle `ls_i` (in addition to the existing center, radius, `ts_i`). These are all already computed in the existing `muscle_info` loop (Spec 4/5/7/8) — we just store more of them per entry instead of discarding them. The KDTree build unpacks only `entry[0]` (the center), so the 7-field tuple does not break it.

5. **Legacy fallback: muscles without `fascia_rest_length` get no axial slide.** Pre-Spec-4 muscles have no rest length and their pivot is at the midpoint. They get the radial push only (same as today). The axial slide is silently skipped via an `m_origin is not None` guard. No special code path — the guard is the fallback.

6. **UI toggle: `Scene.fascia_skin_sliding` (BoolProperty, default True).** Lets the user turn skin sliding off to compare with the old radial-only behavior (essential for verification and debugging). A single checkbox in the existing Flex section of the panel. No new panel section. When False, the axial slide code is skipped entirely (the loop reverts to radial-only behavior, except for the larger `find_range` radius — the per-component `dist_to_center < influence_radius` check still gates the radial push, so the result is byte-identical to pre-Spec-12).

7. **Shape-key safety is unchanged.** The axial slide is just another component of the same `push` vector that gets written to `Live_Flex` (or `mesh.vertices` in the no-shape-key path). The same `target_data` / `source_data` logic applies. No new shape-key concerns.

8. **Volume preservation is unchanged.** The axial slide moves skin vertices, not muscle vertices. Muscle scale (`ts_i, ts_i, ls_i`) is set in Step 1 and is not touched by the skin-push loop. Volume product stays 1.0.

9. **No new stored fields on muscle objects.** The slide uses `fascia_rest_length` (Spec 4), `fascia_radius` (Spec 2), `matrix_world` (Spec 7/8), and `muscle_scales` (Spec 5) — all already available. No changes to `generate_muscles`, `create_muscle_mesh`, or the species data.

10. **Do not overclaim.** The code comments must state what this does (tangential skin sliding along the muscle axis, proportional to shortening) AND what it does not do (no true skin relaxation, no tissue-surface friction, no sliding between adjacent skin patches — it is a per-vertex push along the nearest muscle's axis). See section 7.

---

## 4. The exact changes

### 4a. Add `SKIN_SLIDE_FRACTION` constant

Immediately after the `MAX_CONTRACTION` constant (added in Spec 3), add:

```python
# Fraction of the muscle's axial shortening that is transmitted to nearby
# skin as tangential sliding. 1.0 = full physical sliding (the skin follows
# the muscle surface exactly). < 1.0 = damped sliding (skin lags behind the
# muscle). Tunable; do not tune to a specific mesh.
SKIN_SLIDE_FRACTION = 1.0
```

### 4b. Add `fascia_skin_sliding` Scene property + panel checkbox

In `register()`, in the same block where other Scene properties are registered (after the `fascia_recruitment_index` IntProperty assignment, before the function ends), add:

```python
    bpy.types.Scene.fascia_skin_sliding = bpy.props.BoolProperty(
        name="Skin Sliding",
        description="When enabled, skin slides tangentially along contracting muscles (in addition to radial bulging). Disable to compare with radial-only behavior.",
        default=True,
    )
```

In `unregister()`, in the same block where other Scene properties are deleted (the block that deletes `fascia_recruitment_index` and `fascia_recruitment` BEFORE the classes tuple is unregistered — see Spec 5 / AGENTS.md registration-order rules), add:

```python
    del bpy.types.Scene.fascia_skin_sliding
```

In `FASCIA_PT_main_panel.draw()`, in the existing Flex section (near the Flex slider, after the `fascia_flex` slider line), add a single checkbox:

```python
        layout.prop(scene, "fascia_skin_sliding")
```

### 4c. Expand `muscle_info` and compute `max_half_length` in `update_flex`

Find the `muscle_info` loop (currently ~lines 633–658). Each entry currently stores `(center, radius, ts_i)`. Expand to also store the origin, axis, rest length, and per-muscle `ls_i` needed by the axial slide, and track the maximum half-rest-length for the KDTree query radius:

Replace:

```python
    muscle_info = []
    for m in muscles:
        ls_i, ts_i = muscle_scales.get(m.name, (1.0, 1.0))
        rest_length = m.get("fascia_rest_length", None)
        if rest_length is None:
            center = m.matrix_world.translation.copy()
        else:
            origin = m.matrix_world.translation.copy()
            world_rot = m.matrix_world.to_quaternion()
            axis = (world_rot @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
            center = origin + axis * (rest_length * ls_i * 0.5)
        radius = m.get("fascia_radius", 0.04)
        muscle_info.append((center, radius, ts_i))
```

With:

```python
    muscle_info = []
    max_half_length = 0.0
    for m in muscles:
        ls_i, ts_i = muscle_scales.get(m.name, (1.0, 1.0))
        rest_length = m.get("fascia_rest_length", None)
        if rest_length is None:
            # Legacy muscle (pre-Spec-4): no axis data, no axial slide.
            # Radial push still works (uses the belly center as before).
            center = m.matrix_world.translation.copy()
            origin = None
            axis = None
        else:
            origin = m.matrix_world.translation.copy()
            world_rot = m.matrix_world.to_quaternion()
            axis = (world_rot @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
            center = origin + axis * (rest_length * ls_i * 0.5)
            if rest_length * 0.5 > max_half_length:
                max_half_length = rest_length * 0.5
        radius = m.get("fascia_radius", 0.04)
        # Spec 12: store origin/axis/rest_length/ls_i for the axial slide.
        # Legacy muscles get None for origin/axis, which the slide code guards on.
        muscle_info.append((center, radius, ts_i, origin, axis, rest_length, ls_i))
```

### 4d. Grow the KDTree query radius and add the axial slide in the inner loop

Find the KDTree build block (currently ~lines 660–665). The KDTree is still built on `m_center` (unchanged), but the unpacking must match the expanded 7-field tuple, and the query radius must grow.

Replace:

```python
    # Spec 11: Build KDTree for spatial acceleration
    from mathutils.kdtree import KDTree
    kd = KDTree(len(muscle_info))
    for idx, (m_center, m_radius, m_ts_i) in enumerate(muscle_info):
        kd.insert(m_center, idx)
    kd.balance()
```

With:

```python
    # Spec 11: Build KDTree for spatial acceleration
    from mathutils.kdtree import KDTree
    kd = KDTree(len(muscle_info))
    for idx, entry in enumerate(muscle_info):
        kd.insert(entry[0], idx)  # entry[0] = belly center
    kd.balance()

    # Spec 12: Query a larger radius so vertices near the muscle ends (not
    # just the belly center) are found for the axial slide. The per-component
    # distance checks inside the loop filter out out-of-range vertices.
    search_radius = influence_radius + max_half_length
    skin_sliding = scene.fascia_skin_sliding
```

Then find the inner push loop (currently ~lines 713–722):

```python
            for (_idx, dist, _co) in kd.find_range(world_pos, influence_radius):
                if dist < 0.001:
                    continue
                m_center, m_radius, m_ts_i = muscle_info[_idx]
                t = dist / influence_radius
                falloff = (1.0 - t) * (1.0 - t)
                growth = m_radius * (m_ts_i - 1.0)
                push_dir = (world_pos - m_center).normalized()
                push += push_dir * growth * falloff
                was_affected = True
```

Replace with:

```python
            for (_idx, dist_to_center, _co) in kd.find_range(world_pos, search_radius):
                if dist_to_center < 0.001:
                    continue
                m_center, m_radius, m_ts_i, m_origin, m_axis, m_rest_length, m_ls_i = muscle_info[_idx]

                # ── Radial push (Spec 3, unchanged): only if within
                # influence_radius of the belly center. ──
                if dist_to_center < influence_radius:
                    t = dist_to_center / influence_radius
                    falloff = (1.0 - t) * (1.0 - t)
                    growth = m_radius * (m_ts_i - 1.0)
                    push_dir = (world_pos - m_center).normalized()
                    push += push_dir * growth * falloff
                    was_affected = True

                # ── Axial slide (Spec 12): tangential push along the muscle
                # axis, proportional to the muscle's shortening. Only if skin
                # sliding is enabled and the muscle has axis data (pinned
                # muscles, Spec 4+). Legacy muscles get None for origin/axis
                # and are skipped here. ──
                if skin_sliding and m_origin is not None and m_axis is not None and m_rest_length and m_rest_length > 0.001:
                    rel = world_pos - m_origin
                    s = rel.dot(m_axis)
                    s_clamped = max(0.0, min(m_rest_length, s))
                    radial_vec = rel - m_axis * s_clamped
                    radial_dist = radial_vec.length
                    if radial_dist < influence_radius and radial_dist > 0.001:
                        t_axial = radial_dist / influence_radius
                        falloff_axial = (1.0 - t_axial) * (1.0 - t_axial)
                        slide = s_clamped * (m_ls_i - 1.0) * SKIN_SLIDE_FRACTION
                        push += m_axis * slide * falloff_axial
                        was_affected = True
```

---

## 5. What you must NOT change

- Do NOT change the radial push formula (`growth = m_radius * (m_ts_i - 1.0)`, `falloff = (1-t)²`, `push_dir = (world_pos - m_center).normalized()`). The radial push is gated by `dist_to_center < influence_radius` — identical to before.
- Do NOT change the volume-preserving scale assignment (`obj.scale[0/1/2] = ts_i/ts_i/ls_i`). The skin slide does not touch muscle scales.
- Do NOT change `HORSE_MUSCLES`, `HORSE_LANDMARKS`, `MAX_CONTRACTION`, `MUSCLE_INFLUENCE_FRACTION`, or any species data.
- Do NOT touch shape-key logic, the backup system, `_save_original_verts` / `_restore_original_verts`, or the bake capture order.
- Do NOT touch `FASCIA_OT_simulate_motion` or `FASCIA_OT_bake_flex_pose` — they call `update_flex` and inherit the axial slide automatically.
- Do NOT touch `create_muscle_mesh`, `FASCIA_OT_generate_muscles`, rig binding, or antagonist pairing — the axial slide uses only existing data.
- Do NOT add new imports — `mathutils` is already imported, and `KDTree` is already imported inside `update_flex` (Spec 11).
- Do NOT add a second influence radius, a second falloff shape, or a skin-relaxation solver. Those are future work (section 7).
- Do NOT change any operator registration order beyond adding the one `fascia_skin_sliding` property (register after the `fascia_recruitment_index` line; delete in the same pre-classes block in `unregister`).

---

## 6. Verification (run in Blender after implementation)

After the edit: copy `fascia_addon.py` to the Blender addons dir, reload the add-on, ensure the base mesh is tagged + landmarks placed + muscles generated (re-run Generate Muscles so `fascia_rest_length` is present). Then verify:

1. **Rest check (flex=0):** every muscle has `scale == (1.0, 1.0, 1.0)`; skin displacement = 0. The axial slide is `s · (ls_i − 1) = s · 0 = 0` at rest, so the rest appearance must be IDENTICAL to pre-Spec-12. This is the critical no-regression check.

2. **Toggle-off = radial-only (no regression):** set `scene.fascia_skin_sliding = False`. At flex=1, the skin deformation must be IDENTICAL to pre-Spec-12: same affected vertex count, same max displacement, same vertex positions. This proves the axial slide is purely additive and the toggle works. (The larger `find_range` radius returns more candidates, but the `dist_to_center < influence_radius` gate on the radial push skips any that are out of range — so the radial result is byte-identical.)

3. **Toggle-on = radial + axial:** set `scene.fascia_skin_sliding = True`. At flex=1, the affected vertex count is ≥ the toggle-off count (the axial slide may affect vertices near the axis but far from the belly center, which the old radial-only code missed). Skin vertices near the insertion end of a contracting muscle are displaced TOWARD the origin along the muscle axis, in addition to the radial bulge.

4. **Origin-end skin does not slide:** for a sample muscle (e.g. `GluteusMedius_R`), pick a skin vertex near the origin end (`s ≈ 0` — compute `s = (world_pos - origin) · axis`). At flex=1, its axial displacement is ≈ 0. The slide is `s · (ls_i − 1)`, and `s ≈ 0 → slide ≈ 0`. ✓

5. **Insertion-end skin slides toward origin:** for the same muscle, pick a skin vertex near the insertion end (`s ≈ rest_length`). At flex=1 with recruitment=1 (`ls_i = 0.75`), its axial displacement along `Â` is ≈ `rest_length · (0.75 − 1.0) · falloff_axial = rest_length · (−0.25) · falloff_axial` — up to 25% of rest length toward the origin (scaled by the radial falloff). The displacement direction is `−Â` (toward origin). ✓

6. **Volume preservation unchanged:** sample muscles at flex=1 still have `scale ≈ (1.1547, 1.1547, 0.75)`, volume product `scale[0]² · scale[2] ≈ 1.0`. The skin slide does not touch muscle scales.

7. **Shape-key safety:** with shape keys present, all deformation (radial + axial) goes into `Live_Flex` only. `Basis` is never written to. Verify: read `Basis.data[0].co` before and after a flex=1 → flex=0 cycle — identical (no Basis corruption).

8. **Symmetry check:** sliding flex back to 0 restores all muscles to `(1,1,1)` and skin to rest (no drift). The axial slide is 0 at rest, so there is no accumulated drift.

9. **Legacy muscles (no-regression for pre-Spec-4 scenes):** generate muscles with a pre-Spec-4 addon version, then reload the Spec-12 addon and drag Flex. No crash. Legacy muscles (no `fascia_rest_length`) get radial push only — no axial slide (the `m_origin is not None` guard skips them). The radial push works as before.

10. **Antagonist pairing (Spec 10) compatibility:** with an antagonist pair (e.g. Triceps/Biceps), the relaxed antagonist (`ls_i ≈ 1.0` due to relaxation) gets ≈ 0 axial slide, while the contracting agonist (`ls_i < 1.0`) gets a real slide. Verify: the relaxed muscle's nearby skin does not slide, the contracting muscle's nearby skin does. This is automatic from the per-muscle `ls_i` — no special code.

Report: for the sample muscle at flex=0 and flex=1 — the origin-end axial displacement (≈0), the insertion-end axial displacement (≈ `rest_length · (ls_i−1) · falloff`), the `scale` tuple, and the volume product; plus the toggle-off vs toggle-on affected-vertex counts at flex=1.

---

## 7. Known limitations (must be documented in code comments, NOT hidden)

- **Per-vertex, not per-patch.** Each skin vertex slides independently along the nearest muscle's axis. There is no coupling between adjacent skin vertices (no skin relaxation, no surface tension). This can produce stretching in the skin near the insertion end if the axial slide is strong relative to the skin's local stiffness. A proper skin relaxation solver (e.g. Laplacian smoothing on the displaced vertices) is future work.

- **No inter-muscle sliding coherence.** If two muscles' influence regions overlap and push the same skin vertex in different axial directions, the slides simply sum. This is the same superposition model as the radial push (Spec 3) — not physically correct for overlapping muscles, but simple and stable.

- **Same `influence_radius` for radial and axial.** The axial slide uses the same falloff radius as the radial bulge. A separate, larger "sliding radius" could be more accurate (real skin slides farther than it bulges radially), but that adds a second constant and a second distance check. Deferred.

- **No sliding between skin and underlying fascia/fat layers.** Fascia has only one skin layer today. When fascia/fat layers are added (future work), the sliding between layers will need its own model.

- **Geometric, not physical.** The slide is a geometric projection of the muscle's shortening onto nearby skin. It is not a physics solve (no friction, no tissue compliance, no contact mechanics). This is the same honest caveat as the contraction itself (Spec 3) — never claim FEM parity.

- **KDTree query radius is wider, so more candidates per vertex.** With `search_radius = influence_radius + max_half_length`, each vertex iterates over more muscle candidates than before. The per-component distance checks skip out-of-range ones, but the iteration cost is higher. On the 748k-vertex test mesh this may be noticeably slower than Spec-11 radial-only. Acceptable for the current work-in-progress (correctness over speed); revisit if interactive performance is lost.

These are honest scope boundaries, not bugs. Do NOT silently work around them.

---

## 8. Deliverable back to the architect

- The updated `fascia_addon.py` written to `C:\Projects\Fascia\fascia_addon.py` (the source — the architect handles the addons-dir copy and Blender reload).
- A short note confirming only the 4 locations in section 4 were changed (4a constant, 4b property + panel, 4c muscle_info expansion, 4d KDTree radius + inner loop).
- No need to paste logs — the architect will read the file and run the section-6 verification independently.

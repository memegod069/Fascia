# SPEC 02 — Make Muscle Generation Mesh-Agnostic

**Target executor:** DeepSeek.
**Scope:** Small code change + small data change. Touches `_get_base_bounds` region (add a helper), `HORSE_MUSCLES` radii (convert to fractions), `FASCIA_OT_generate_muscles.execute` (scale radii at generation), and `update_flex` (scale influence_radius at runtime). Does NOT touch `create_muscle_mesh` internals, landmarks, shape-key logic, or any operator's registration.
**Estimated size:** ~20 lines changed across 4 locations in `fascia_addon.py`.

---

## 1. Why this change is needed

Three values are hardcoded in Blender units and assume a ~3.6-unit-long mesh:

1. `influence_radius = 0.3` (line ~326, inside `update_flex`). This is how far (in Blender units) a muscle's bulge reaches into the surrounding skin. On a 36-unit horse it would be invisibly small; on a 0.36-unit horse it would swamp the whole body.
2. The `radius` values in `HORSE_MUSCLES` (lines ~158–176): `0.04` to `0.10`. These are the muscle thicknesses passed to `create_muscle_mesh`. Same scaling problem.
3. `obj["fascia_radius"] = mdata["radius"]` (lines ~746, ~775): stores the radius per muscle, reused by `update_flex` line ~394 (`growth = flex * m_radius * 0.5`).

**Goal:** make every size a fraction of the base mesh's characteristic size, so muscles look right on a horse of any absolute scale.

---

## 2. Architectural decisions (read before changing anything)

1. **Characteristic size = the longest side of the base mesh's world-space bounding box.** Call it `base_size`. For the test meshes this is the body length (~3.6 units). It is simple, orientation-stable enough, and easy to explain. Do NOT use the diagonal — use the single longest axis. Implement via a new helper `_get_base_size(obj)`.
2. **Preserve current look on a 3.6-unit mesh.** Convert each hardcoded radius by dividing by 3.6 (the reference length both test meshes share). At runtime, multiply the fraction by the actual `base_size`. Net effect on the existing test meshes: identical output.
3. **Store the WORLD-SPACE (scaled) radius on each muscle** in `obj["fascia_radius"]`, not the fraction. This keeps `update_flex`'s growth math (`flex * m_radius * 0.5`) working in consistent world units with no extra change.
4. **Compute `influence_radius` from the base mesh inside `update_flex`** (not a global constant in Blender units). Use a named module-level fraction constant so it is self-documenting and tunable.
5. **Do NOT change `create_muscle_mesh`.** It already takes a world-space radius and uses it correctly. The scaling happens in its callers.
6. **Do NOT introduce per-muscle influence radii.** That is a behavioural change for a future spec. Keep a single global influence fraction.
7. **Do NOT scale landmark empty display sizes.** That is cosmetic and out of scope for this spec.

---

## 3. The exact changes

### 3a. Add `_get_base_size` helper

Add this function immediately after `_get_base_bounds` (currently ending ~line 72):

```python
def _get_base_size(obj):
    """Return a single characteristic size for the base mesh:
    the longest side of its world-space bounding box.
    Used to scale muscle radii and influence radius so they are
    proportional on a mesh of any absolute scale."""
    (min_x, min_y, min_z), (max_x, max_y, max_z) = _get_base_bounds(obj)
    return max(max_x - min_x, max_y - min_y, max_z - min_z)
```

### 3b. Add influence-radius fraction constant

Add this module-level constant just above `HORSE_MUSCLES` (after the `HORSE_LANDMARKS` dict closes):

```python
# Fraction of the base mesh's longest bounding-box side that a muscle's
# skin-bulge influence reaches. ~8.3% reproduces the old 0.3-unit radius
# on a 3.6-unit-long mesh. Tunable.
MUSCLE_INFLUENCE_FRACTION = 0.083
```

### 3c. Convert `HORSE_MUSCLES` radii to fractions of body length

Replace the `radius` value in every `HORSE_MUSCLES` entry. Each old absolute radius is divided by 3.6 (the reference length) and rounded to 3 decimals. The `from`, `to`, and `color` fields are unchanged. The new dict (full replacement):

```python
HORSE_MUSCLES = {
    # Front body (warm colours)
    "Trapezius":         {"from": "Withers",         "to": "ScapulaTop",      "radius": 0.017, "color": (0.80, 0.20, 0.15, 0.60)},
    "Deltoid":           {"from": "ScapulaTop",      "to": "PointOfShoulder", "radius": 0.014, "color": (0.90, 0.35, 0.10, 0.60)},
    "Triceps":           {"from": "ScapulaTop",      "to": "Elbow",           "radius": 0.019, "color": (0.70, 0.12, 0.12, 0.60)},
    "BicepsBrachii":     {"from": "PointOfShoulder", "to": "Elbow",           "radius": 0.014, "color": (0.85, 0.45, 0.35, 0.60)},
    "Pectorals":         {"from": "Chest",           "to": "PointOfShoulder", "radius": 0.019, "color": (0.82, 0.30, 0.30, 0.60)},
    "SerratusVentralis": {"from": "Chest",           "to": "SerratusAnchor",  "radius": 0.017, "color": (0.78, 0.35, 0.40, 0.60)},
    "LatissimusDorsi":   {"from": "MidBack",         "to": "LatAnchor",       "radius": 0.019, "color": (0.72, 0.22, 0.18, 0.60)},
    "Brachiocephalicus": {"from": "Poll",            "to": "PointOfShoulder", "radius": 0.014, "color": (0.88, 0.50, 0.30, 0.60)},

    # Spine & torso
    "LongissimusDorsi":  {"from": "Withers",         "to": "PointOfCroup",    "radius": 0.017, "color": (0.65, 0.18, 0.18, 0.60)},
    "RectusAbdominis":   {"from": "Chest",           "to": "PointOfHip",      "radius": 0.014, "color": (0.75, 0.55, 0.40, 0.60)},

    # Rear body (cool colours)
    "GluteusMedius":     {"from": "PointOfHip",      "to": "HipJoint",        "radius": 0.028, "color": (0.20, 0.22, 0.78, 0.60)},
    "BicepsFemoris":     {"from": "PointOfButtock",  "to": "Stifle",          "radius": 0.019, "color": (0.30, 0.30, 0.85, 0.60)},
    "Semitendinosus":    {"from": "PointOfButtock",  "to": "Hock",            "radius": 0.017, "color": (0.40, 0.38, 0.75, 0.60)},
    "Quadriceps":        {"from": "HipJoint",        "to": "Stifle",          "radius": 0.019, "color": (0.45, 0.25, 0.70, 0.60)},
    "Gastrocnemius":     {"from": "Stifle",          "to": "Hock",            "radius": 0.014, "color": (0.55, 0.42, 0.78, 0.60)},
}
```

### 3d. Scale radii at generation time in `FASCIA_OT_generate_muscles.execute`

At the start of `execute` (after the base/landmark checks, before the muscle loop), compute the base size once:

```python
        body = _get_base_mesh()
        base_size = _get_base_size(body) if body else 3.6
```

(Use 3.6 as a safe fallback if no base mesh is tagged — should not normally happen because the landmark check above would have caught it, but be defensive.)

Then everywhere a muscle radius is passed to `create_muscle_mesh` and stored, multiply the fraction by `base_size`. There are two call sites (bilateral branch ~line 726, midline branch ~line 761):

- `obj = create_muscle_mesh(obj_name, p1, p2, mdata["radius"])` →
  `obj = create_muscle_mesh(obj_name, p1, p2, mdata["radius"] * base_size)`
- `obj = create_muscle_mesh(obj_name, p1, p2, mdata["radius"])` (midline) →
  `obj = create_muscle_mesh(obj_name, p1, p2, mdata["radius"] * base_size)`

And the stored radius (two sites, ~lines 746 and 775):

- `obj["fascia_radius"] = mdata["radius"]` →
  `obj["fascia_radius"] = mdata["radius"] * base_size`

### 3e. Scale influence radius at runtime in `update_flex`

Replace the hardcoded line (~326):

```python
        influence_radius = 0.3   # How far (in Blender units) a muscle's effect reaches
```

with computation from the base mesh:

```python
        body = _get_base_mesh()
        base_size = _get_base_size(body) if body else 3.6
        influence_radius = MUSCLE_INFLUENCE_FRACTION * base_size
```

(Place this before the `skin_objects` loop, near where the current line 326 sits. `update_flex` already calls `_get_skin_objects` below, so adding a `_get_base_mesh` call here is consistent.)

---

## 4. What you must NOT change

- Do NOT modify `create_muscle_mesh` (it already takes a world-space radius).
- Do NOT change any `from`/`to`/`color` in `HORSE_MUSCLES`, only `radius`.
- Do NOT change `HORSE_LANDMARKS`.
- Do NOT touch shape-key logic, the backup system, or `_save_original_verts`/`_restore_original_verts`.
- Do NOT introduce per-muscle influence radii or falloff changes.
- Do NOT scale landmark empty display sizes.
- Do NOT change the flex growth formula (`flex * m_radius * 0.5`) — it stays correct because `m_radius` is now the stored world-space radius.

---

## 5. Verification (executor runs in Blender, or hands to architect)

With the real horse mesh tagged as base (`fascia_role = "skin"`):

1. Reload the add-on (copy `fascia_addon.py` to the addons dir, disable + re-enable the add-on).
2. Click **Place Landmarks** (if not already placed).
3. Click **Generate Muscles**.
4. Confirm muscles appear between the correct landmark pairs and are visibly proportional to the body (not tiny dots, not swamping the body).
5. Set the **Flex** slider to 0.5. Confirm the skin bulges near muscles (the bulge should be visible and localised, not affecting the whole body).
6. Report back: the `base_size` value computed, the world-space radius of 2–3 representative muscles (e.g. Trapezius, GluteusMedius), and the computed `influence_radius`. The architect will sanity-check these against the bounding box.

Sanity expectations for the real horse mesh (bbox longest side ≈ 3.6):
- `base_size` ≈ 3.6
- Trapezius world radius ≈ 0.017 × 3.6 ≈ 0.061 (matches the old hardcoded 0.06 — look preserved)
- GluteusMedius world radius ≈ 0.028 × 3.6 ≈ 0.101 (matches the old 0.10)
- `influence_radius` ≈ 0.083 × 3.6 ≈ 0.299 (matches the old 0.3)

If those three match the old hardcoded values, the change is behaviour-preserving on the existing mesh and now scales correctly on any other size.

---

## 6. Deliverable back to the architect

- The updated `fascia_addon.py` (or a unified diff).
- A short note confirming only the 4 locations in section 3 were changed.
- The verification numbers from section 5, step 6.

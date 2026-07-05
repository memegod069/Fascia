# SPEC 01 — Fix Landmark Proportions for Real Horses

**Target executor:** DeepSeek (code change is mechanical).
**Scope:** DATA fix only. Do NOT rewrite the placement operator, the bounds helper, or any other code. Only the `HORSE_LANDMARKS` dictionary and its surrounding comment block change.
**Estimated size:** ~30 lines replaced in `fascia_addon.py`.

---

## 1. Why this change is needed

`HORSE_LANDMARKS` stores each landmark as a normalized `(U, V, W)` triple in `[0,1]`:
- `U` = position along X (length). `0.0` = rearmost point of the mesh; `1.0` = frontmost point.
- `V` = position along Y (width). `0.5` = midline; bilateral landmarks store the LEFT-side value, the right side is auto-created as `1.0 - V`.
- `W` = position along Z (height). `0.0` = lowest point of the mesh; `1.0` = highest point.

At placement time (`FASCIA_OT_place_landmarks.execute`), each triple is mapped to world space via the base mesh's world-space bounding box (`_get_base_bounds`). So `W=0.0` lands on the mesh's lowest vertex and `W=1.0` lands on its highest vertex.

The current values were derived from a placeholder blob that had **no legs** and a **separate head sphere outside the body bounding box**. On that blob:
- the bounding-box bottom was the **belly** (no legs), so leg/belly landmarks got `W` values near 0 or negative;
- the bounding-box top was the **withers only** (head sphere was separate), so head landmarks needed `U > 1.0` to escape the body box and reach the head sphere.

On a real horse mesh (head and legs are part of the mesh, bounding box spans nose→tail and hooves→withers), those same values misplace:
- `FrontKnee` and `Hock` (`W = -0.111`) land below the hooves.
- `BellyMid` and `Chest` (`W ≈ 0.01–0.03`) land on the hooves instead of the belly/chest floor.
- `Poll` (`U = 1.111`) and `NuchalCrest` (`U = 1.014`) overshoot past the nose.

This is a **data problem, not a code problem.** The mapping code is correct; the stored proportions are wrong for a real horse body plan.

---

## 2. Architectural decision (read before changing anything)

1. **Keep the bounding-box-normalized approach.** Do not add surface-detection, skeleton-detection, or any new code path in this spec. That is a future, larger work item.
2. **Retune the `(U, V, W)` values to be anatomically correct for a real horse** standing in a neutral four-square pose. The values must be dimensionless fractions, so they apply to any horse mesh regardless of absolute size.
3. **Document the pose assumption in the comment block above the dict.** Bounding-box landmarking is pose-dependent. The values below are correct for a horse standing square with the head carried at roughly wither height. Extreme poses (grazing head-down, rearing, galloping) will misplace the head and limb landmarks — this is a **known limitation**, not a bug. State this explicitly in the comment.
4. **Do not touch any other landmark's bilateral flag, region, name, or dict key.** Only `pos` values and the comment block change.
5. **Do not change the orientation convention.** Low `U` = rear (tail/buttock), high `U` = front (head). Low `W` = ground/hooves, high `W` = withers/top.

---

## 3. The exact change

In `fascia_addon.py`, replace the entire `HORSE_LANDMARKS` dictionary (currently lines ~102–130) **and** the comment block immediately above it (currently lines ~82–100) with the block below.

```python
# ─────────────────────────────────────────────────────────────────
# HORSE LANDMARK DEFINITIONS
# ─────────────────────────────────────────────────────────────────
# Each entry has:
#   pos       – normalized (U, V, W) coordinate where each axis is 0.0–1.0
#               (U = X, V = Y, W = Z), mapped to the base mesh's
#               world-space bounding box at placement time.
#                 U = 0.0  rearmost point of the mesh (tail/buttock)
#                 U = 1.0  frontmost point of the mesh (nose tip)
#                 V = 0.5  midline (bilateral entries store LEFT-side V;
#                           right side is auto-created as 1.0 - V)
#                 W = 0.0  lowest point of the mesh (ground / bottom of hooves)
#                 W = 1.0  highest point of the mesh (top of withers / poll)
#   bilateral – True if it exists on both left and right sides of the horse
#   region    – which body area it belongs to (for organisation)
#
# POSE ASSUMPTION (KNOWN LIMITATION):
#   Values are calibrated for a horse standing four-square (neutral
#   reference pose) with the head carried at roughly wither height.
#   They are dimensionless fractions and apply to any horse mesh of
#   any absolute size, AS LONG AS the mesh is in or near this pose.
#   Extreme poses will misplace landmarks:
#     - Grazing (head down): head landmarks (Poll, NuchalCrest) land
#       too high; front-vs-rear U values still hold.
#     - Rearing / head well above withers: head landmarks land too low.
#     - Galloping / extended limbs: limb landmarks (Knee, Hock, Fetlock
#       if added later) no longer line up with the bounding-box edges.
#   This is a fundamental limit of bounding-box landmarking and is
#   expected to be addressed by surface- or skeleton-driven placement
#   in a future work item. Do NOT per-mesh-tune these values to mask it.
# ─────────────────────────────────────────────────────────────────

HORSE_LANDMARKS = {
    # Head & Neck (midline)
    "Poll":            {"pos": (0.840, 0.500, 0.920), "bilateral": False, "region": "head"},
    "NuchalCrest":     {"pos": (0.825, 0.500, 0.880), "bilateral": False, "region": "neck"},

    # Shoulder & Forelimb
    "Withers":         {"pos": (0.640, 0.500, 0.980), "bilateral": False, "region": "back"},
    "ScapulaTop":      {"pos": (0.660, 0.670, 0.920), "bilateral": True,  "region": "shoulder"},
    "PointOfShoulder": {"pos": (0.700, 0.720, 0.780), "bilateral": True,  "region": "shoulder"},
    "Elbow":           {"pos": (0.680, 0.650, 0.530), "bilateral": True,  "region": "forelimb"},
    "FrontKnee":       {"pos": (0.660, 0.630, 0.430), "bilateral": True,  "region": "forelimb"},

    # Trunk / Torso (midline)
    "Chest":           {"pos": (0.580, 0.500, 0.420), "bilateral": False, "region": "chest"},
    "MidBack":         {"pos": (0.500, 0.500, 0.950), "bilateral": False, "region": "back"},
    "BellyMid":        {"pos": (0.450, 0.500, 0.380), "bilateral": False, "region": "belly"},

    # Hip & Hindlimb
    "PointOfHip":      {"pos": (0.320, 0.750, 0.780), "bilateral": True,  "region": "hip"},
    "PointOfCroup":    {"pos": (0.240, 0.500, 0.930), "bilateral": False, "region": "hip"},
    "PointOfButtock":  {"pos": (0.080, 0.680, 0.730), "bilateral": True,  "region": "hip"},
    "HipJoint":        {"pos": (0.300, 0.620, 0.660), "bilateral": True,  "region": "hip"},
    "Stifle":          {"pos": (0.260, 0.700, 0.670), "bilateral": True,  "region": "hindlimb"},
    "Hock":            {"pos": (0.200, 0.680, 0.470), "bilateral": True,  "region": "hindlimb"},

    # Internal anchor points (hidden attachment sites inside the body)
    "SerratusAnchor":  {"pos": (0.660, 0.580, 0.500), "bilateral": True,  "region": "shoulder"},
    "LatAnchor":       {"pos": (0.650, 0.680, 0.360), "bilateral": True,  "region": "forelimb"},
}
```

---

## 4. Anatomical reasoning (for review — do not put this in the code)

All `W` values are fractions of wither height (withers ≈ 1.0, hooves/ground = 0.0) for a ~1.6 m horse. All `U` values are fractions of nose-to-rear total length (nose = 1.0, rearmost = 0.0). Numbers are rounded to 2 decimals.

| Landmark | U | W | Anatomical basis |
|---|---|---|---|
| Poll | 0.84 | 0.92 | Back of skull between ears; ~0.5 m behind nose tip; head-up poll ≈ wither height. |
| NuchalCrest | 0.83 | 0.88 | Base of skull dorsal, just below/behind poll. |
| Withers | 0.64 | 0.98 | Dorsal scapular spines (T4–T9); highest point of the back; near bbox top so W≈0.98 not 1.0. |
| ScapulaTop | 0.66 | 0.92 | Dorsal end of scapular spine, lateral to withers; slightly below wither peak and lateral (V=0.67). |
| PointOfShoulder | 0.70 | 0.78 | Cranial greater tubercle of humerus; lateral (V=0.72); ~75–80% wither height. |
| Elbow | 0.68 | 0.53 | Olecranon of ulna; ~50–55% wither height; caudal-lateral (V=0.65). |
| FrontKnee | 0.66 | 0.43 | Carpus; ~40–45% wither height; under the shoulder. |
| Chest | 0.58 | 0.42 | Pectoral floor between front legs; ~elbow/knee height; midline. |
| MidBack | 0.50 | 0.95 | Saddle region (T12–T15), just behind withers; dorsal midline. |
| BellyMid | 0.45 | 0.38 | Ventral abdomen lowest point; between fore and hind limbs; midline. |
| PointOfHip | 0.32 | 0.78 | Tuber coxae; very lateral (V=0.75); ~75–80% wither height. |
| PointOfCroup | 0.24 | 0.93 | Tuber sacrale; dorsal midline near rump; just below withers. |
| PointOfButtock | 0.08 | 0.73 | Tuber ischiadicum; rearmost bony point; lateral-caudal (V=0.68). |
| HipJoint | 0.30 | 0.66 | Coxo-femoral joint center, DEEP inside (not surface); less lateral than PointOfHip (V=0.62). |
| Stifle | 0.26 | 0.67 | Patella; lateral-cranial thigh; ~65–70% wither height. |
| Hock | 0.20 | 0.47 | Tuber calcanei (point of hock); ~45–50% wither height; lateral-caudal (V=0.68). |
| SerratusAnchor | 0.66 | 0.50 | Medial scapula/rib interface; deep; near-midline (V=0.58). |
| LatAnchor | 0.65 | 0.36 | Latissimus insertion on humerus; lateral chest; ~elbow height. |

Key fixes vs. the old data:
- **Head landmarks** moved from `U > 1.0` to `U ≈ 0.83–0.84` (head is inside the mesh's bbox now).
- **Leg landmarks** moved from `W < 0` to positive `W` (Knee 0.43, Hock 0.47) because the bbox bottom is now the hooves.
- **Belly/Chest** moved from `W ≈ 0.01–0.03` to `W ≈ 0.38–0.42` (belly floor is well above the hooves).
- **HipJoint** moved from `V = 0.722` (too lateral) to `V = 0.620` (it is a deep joint, not a surface point).

---

## 5. What you must NOT change

- Do not modify `_get_base_bounds`, `_get_base_mesh`, `FASCIA_OT_place_landmarks`, or any operator.
- Do not change any landmark's `bilateral` flag or `region` string.
- Do not rename any landmark key (muscles in `HORSE_MUSCLES` reference these names by string).
- Do not add new landmarks. (Fetlock, pastern, etc. are out of scope.)
- Do not "improve" the placement code with pose detection, surface sampling, or ray-casting. That is a separate future spec.
- Do not change `HORSE_MUSCLES`.

---

## 6. Verification (executor should run, or hand back to architect to run in Blender)

After the change, in Blender with the real horse mesh tagged as base (`fascia_role = "skin"`):

1. Reload the add-on script (`Fascia` panel → reload, or restart Blender).
2. Click **Place Landmarks**.
3. Read the world-space location of each placed `Fascia_LM_*` empty and confirm it sits on or near the corresponding anatomical region of the mesh — not floating in empty space and not below the hooves.
4. Specific checks that MUST pass:
   - `Fascia_LM_FrontKnee_L` world Z is between the hoof and the elbow, roughly mid-forelimb.
   - `Fascia_LM_Hock_L` world Z is between the hoof and the stifle, roughly mid-hindlimb.
   - `Fascia_LM_BellyMid` world Z is above the hooves and below the withers, around the belly floor.
   - `Fascia_LM_Poll` world X is in front of the withers but behind the nose tip (inside the head region, not past it).
   - `Fascia_LM_Withers` world Z is at or near the top of the bounding box.
5. Report back: the world-space coordinates of all placed landmarks, plus the base mesh's bounding-box min/max, so the architect can sanity-check the proportions.

If the test mesh is in a dynamic pose (rearing, galloping, grazing), limb/head landmarks will be visibly off **on that mesh only**. This is expected (see the POSE ASSUMPTION comment). Do not adjust the values to fix it for that mesh — instead report the pose so the architect can decide whether the test mesh is suitable for verification.

---

## 7. Deliverable back to the architect

- The updated `fascia_addon.py` (or a unified diff).
- A short note confirming only the `HORSE_LANDMARKS` dict + comment block were changed.
- The verification coordinates from section 6, step 5.

# SPEC 10 — Antagonist Muscle Pairing (Auto-Relaxation)

**Target executor:** implementing agent.
**Scope:** Extend the species definition schema to support reciprocal "antagonist" muscle relationships. At generation time, store the antagonist name as a custom property on the muscle objects. During flex evaluation, build an antagonist mapping (with side-specific resolution) and reduce the contraction of any muscle whose antagonist partner is active.
**Estimated size:** ~40 lines added/changed in `fascia_addon.py`.

---

## 1. Why this change is needed

In biology, skeletal muscles operate in antagonistic pairs (reciprocal inhibition). When an agonist muscle (e.g., Biceps) contracts, the nervous system signals the antagonist muscle (e.g., Triceps) to relax. 

Without this behavior:
1. Opposing muscles would contract simultaneously when the global flex slider is increased, leading to unrealistic bulging of both sides of a limb.
2. The animator/LLM would have to manually compute and set negative recruitment values for opposite muscles to achieve natural flexion, increasing the API friction and complexity (violating the goal of a low-friction TD harness).

By building antagonist pairing directly into the tissue flex loop, the user or LLM can define the anatomical pairings once in the species JSON, and Fascia will automatically handle the relaxation of opposing muscles during movement.

---

## 2. Design

### 2a. Schema and Property Storage
In the species definition JSON (e.g., `equine_horse.json`), muscles can optionally define an `"antagonist"` key:
```json
"BicepsBrachii": {"from": "PointOfShoulder", "to": "Elbow", "radius": 0.014, "color": [0.85, 0.45, 0.35, 0.60], "antagonist": "Triceps"}
```

During muscle generation (`FASCIA_OT_generate_muscles`), if a muscle template has an `"antagonist"` key, it is saved on the muscle object as a custom ID property:
```python
obj["fascia_antagonist"] = mdata["antagonist"]
```

### 2b. Antagonist Map Construction with Side Matching
Since muscles can be generated bilaterally (adding `_L` and `_R` suffixes to their object names), we must ensure that a left-side muscle only relaxes the corresponding left-side antagonist (e.g., `BicepsBrachii_L` relaxes `Triceps_L` but does not affect `Triceps_R`).

In `update_flex()`, we build an antagonist lookup map (`antagonist_map`):
1. Loop through all muscles. If a muscle has a `fascia_antagonist` property, find the target muscle(s) matching that antagonist name.
2. Resolve side suffixes. If the active muscle has a side suffix (`_L` or `_R`), we first look for the antagonist with the same side suffix. If not found, we fall back to a substring match.
3. The map associates `antagonist_muscle_name -> list of aggressor muscle objects`.

### 2c. Relaxation Formula
Let $c_{ag}$ be the contraction of an active agonist muscle (the "aggressor"), and $r_{ag}$ be its recruitment multiplier. The agonist's contraction is:
$$c_{ag} = \text{flex} \cdot \text{MAX\_CONTRACTION} \cdot r_{ag}$$

Let the maximum possible contraction at the current flex level be:
$$c_{max} = \text{flex} \cdot \text{MAX\_CONTRACTION}$$

For a given muscle $M$ which is named as an antagonist by one or more aggressors, we calculate the relaxation factor $relax_M$ as the maximum normalized contraction of its aggressors:
$$relax_M = \max_{ag} \left( \min\left(1.0, \frac{c_{ag}}{c_{max}}\right) \right)$$

Finally, the contraction of the antagonist muscle $c_M$ is scaled down by the relaxation factor:
$$c_{M,\text{final}} = c_M \cdot (1.0 - relax_M)$$

This ensures:
- If an agonist is fully active ($c_{ag} = c_{max}$), its antagonist is completely relaxed ($relax_M = 1.0 \implies c_{M,\text{final}} = 0.0$).
- The relaxation is proportional to the agonist's recruitment factor, independent of the global `flex` level (avoiding sudden popping when sliding `flex`).

---

## 3. Verification Criteria

1. **Schema support:** The embedded horse definition and the external `species/equine_horse.json` file both include antagonist definitions (e.g., `BicepsBrachii` pointing to `Triceps`, `Quadriceps` pointing to `BicepsFemoris`).
2. **Property persistence:** Regenerating muscles creates the custom property `fascia_antagonist` on the generated objects (verified via `obj.get("fascia_antagonist")`).
3. **Symmetric isolation:** Flexing the model relaxes the left antagonist but leaves the right antagonist unaffected if only the left agonist is active.
4. **Volume Preservation:** The relaxed antagonist maintains a volume product of $1.0$ (scale $1.0, 1.0, 1.0$) because its final contraction is scaled to $0.0$.

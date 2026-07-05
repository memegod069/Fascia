# SPEC 03 — Volume-Preserving Muscle Contraction

**Target executor:** DeepSeek.
**Scope:** Small, surgical change to `update_flex` only, plus one new module constant. Does NOT touch `create_muscle_mesh`, muscle generation, landmarks, shape-key logic, the backup system, or any operator registration.
**Estimated size:** ~25 lines changed across 3 locations in `fascia_addon.py`.

---

## 1. Why this change is needed

The Flex slider currently drives a **non-physical** contraction (file lines ~310–327, ~415):

```python
muscle_scale = 1.0 + flex * 0.5      # thickness grows
obj.scale[0] = muscle_scale          # X = thickness
obj.scale[1] = muscle_scale          # Y = thickness
# scale[2] stays at 1.0              # length UNCHANGED ← wrong
...
growth = flex * m_radius * 0.5       # skin push
```

Two things are wrong:
1. **The muscle never shortens.** A real muscle's defining behavior is shortening along its length when it contracts. The current code leaves length fixed and only inflates thickness — that's a balloon, not a muscle.
2. **Volume is not preserved.** Thickness scales by `(1+flex*0.5)` on two axes, so volume grows as `(1+flex*0.5)²`. At flex=1, volume is 2.25× the rest volume. Real muscles preserve volume (they're roughly incompressible).

The skin push is also decoupled from the actual muscle surface movement (`flex * m_radius * 0.5` is an arbitrary heuristic, not the physical bulge).

---

## 2. The volume-preserving model

A muscle at rest has length `L` (local Z, baked into geometry) and radius `r` (thickness, local X/Y). Volume `V = π · r² · L`.

When it contracts by fraction `c` (0 ≤ c ≤ MAX_CONTRACTION):
- New length: `L' = L · (1 − c)`  (shorten)
- To preserve volume: `r'² · L' = r² · L`  →  `r' = r / √(1 − c)`  (bulge)
- So: `length_scale = (1 − c)`, `thickness_scale = 1 / √(1 − c)`
- Check: `thickness_scale² · length_scale = (1/(1−c)) · (1−c) = 1.0`  ✓ volume preserved.

The Flex slider (0..1) maps to contraction: `c = flex · MAX_CONTRACTION`.

With `MAX_CONTRACTION = 0.25`:
- flex=0 → c=0 → length_scale=1.0, thickness_scale=1.0 (rest)
- flex=1 → c=0.25 → length_scale=0.75, thickness_scale≈1.1547 (15.5% thicker, 25% shorter)

The skin push becomes the **actual radial bulge**: `growth = base_radius · (thickness_scale − 1)`. At flex=1 this is `0.06 · 0.1547 ≈ 0.0093` for a muscle of base radius 0.06. This is smaller than the old heuristic (`0.03`) — because the old value over-pushed. The new value is physically grounded: the skin moves by exactly the amount the muscle surface grew.

---

## 3. Architectural decisions (read before changing anything)

1. **Scope: the muscle scale + skin growth formula only.** Do NOT restructure `create_muscle_mesh`, do NOT add attachment pinning, do NOT add per-muscle controls. This spec makes ONE thing real: the contraction physics.
2. **Uniform contraction across all muscles.** A single Flex slider contracts every muscle by the same fraction. Per-muscle recruitment is a future work item (needs individual controls).
3. **Attachments are NOT pinned.** The muscle shortens toward its midpoint, so both endpoints drift inward from their origin/insertion landmarks during contraction. This produces small visible gaps at the landmarks at high flex. Document this as a known limitation; do NOT try to pin attachments in this spec.
4. **Skin push stays radial.** Only the radial bulge pushes the skin. The axial shortening does not directly deform the skin. This is a pre-existing simplification; do NOT add axial skin deformation in this spec.
5. **Use `** 0.5` for the square root** so no new `import` is needed (the file currently imports only `bpy`, `bmesh`, `mathutils`).
6. **Do not overclaim.** The code comments must state what this does (volume-preserving shorten+bulge) AND what it does not do (no attachment pinning, no per-muscle control, no antagonist relaxation). See section 7.

---

## 4. The exact changes

### 4a. Add `MAX_CONTRACTION` constant

Immediately after the `MUSCLE_INFLUENCE_FRACTION` line (currently ~line 175), add:

```python
# Maximum fractional shortening of a muscle at full flex (flex=1).
# Real muscles shorten ~20-30% at peak contraction. Volume is preserved:
# if length drops by (1-c), thickness grows by 1/sqrt(1-c) so that
# pi * r^2 * L stays constant. Tunable.
MAX_CONTRACTION = 0.25
```

### 4b. Replace Step 1 (muscle scaling) in `update_flex`

Find this block (currently ~lines 310–327):

```python
    # ── Step 1: Scale muscles radially (fatter, not longer) ───
    #
    # Each muscle was built so its local Z axis runs along its
    # length, and local X/Y are its thickness (see create_muscle_mesh).
    # So scaling X and Y makes it fatter without making it longer.
    #
    #   flex = 0  →  scale = 1.0  (normal size)
    #   flex = 1  →  scale = 1.5  (50% fatter)

    muscles = [obj for obj in bpy.data.objects
               if obj.get("fascia_type") == "muscle"]

    muscle_scale = 1.0 + flex * 0.5

    for obj in muscles:
        obj.scale[0] = muscle_scale  # local X = thickness
        obj.scale[1] = muscle_scale  # local Y = thickness
        # scale[2] stays at 1.0 — length doesn't change
```

Replace the whole block with:

```python
    # ── Step 1: Volume-preserving muscle contraction ──────────
    #
    # Each muscle was built so its local Z axis runs along its length
    # and local X/Y are its thickness (see create_muscle_mesh).
    # A real muscle SHORTENS along its length and BULGES outward when
    # it contracts, keeping its volume constant (muscle tissue is
    # roughly incompressible).
    #   V = pi * r^2 * L  →  if L -> L*(1-c), then r -> r/sqrt(1-c)
    # so volume is preserved. c = flex * MAX_CONTRACTION.
    #
    #   flex = 0  →  length_scale=1.0,  thickness_scale=1.0     (rest)
    #   flex = 1  →  length_scale=0.75, thickness_scale≈1.155   (15.5% thicker, 25% shorter)
    #
    # KNOWN LIMITATION: attachments are NOT pinned. The muscle shortens
    # toward its midpoint, so both endpoints drift inward from their
    # origin/insertion landmarks during contraction. Visible as small
    # gaps at the landmarks at high flex. Pinning is future work.

    muscles = [obj for obj in bpy.data.objects
               if obj.get("fascia_type") == "muscle"]

    c = flex * MAX_CONTRACTION
    length_scale = 1.0 - c
    thickness_scale = 1.0 / (length_scale ** 0.5) if length_scale > 0.01 else 1.0

    for obj in muscles:
        obj.scale[0] = thickness_scale  # local X = thickness (bulge)
        obj.scale[1] = thickness_scale  # local Y = thickness (bulge)
        obj.scale[2] = length_scale     # local Z = length (shorten)
```

### 4c. Update the Step 2 comment and the growth formula

Find this comment (currently ~lines 338–340):

```python
    # The push amount depends on:
    #   • How much the muscle grew (flex * muscle_radius * 0.5)
    #   • How close the vertex is (closer = more push, smooth falloff)
```

Replace with:

```python
    # The push amount depends on:
    #   • How much the muscle surface bulged outward
    #     (= base_radius * (thickness_scale - 1), from Step 1)
    #   • How close the vertex is (closer = more push, smooth falloff)
```

And find the growth line (currently ~line 415):

```python
                    growth = flex * m_radius * 0.5
```

Replace with:

```python
                    growth = m_radius * (thickness_scale - 1.0)
```

(`thickness_scale` is a local variable of `update_flex`, computed in Step 1, so it is in scope here. `m_radius` is the muscle's stored BASE radius; `(thickness_scale - 1.0)` is the fractional bulge, so the product is the actual outward surface movement in world units.)

---

## 5. What you must NOT change

- Do NOT modify `create_muscle_mesh` (the rest geometry and local-axis convention are correct).
- Do NOT change `HORSE_MUSCLES` radii or `HORSE_LANDMARKS`.
- Do NOT touch shape-key logic, the backup system, or `_save_original_verts`/`_restore_original_verts`.
- Do NOT add attachment pinning, per-muscle controls, or axial skin deformation.
- Do NOT add an `import math` — use `** 0.5`.
- Do NOT change the influence radius, the falloff formula, or the push direction.
- Do NOT change any operator's registration or the panel UI.

---

## 6. Verification (architect runs in Blender)

After the edit, copy `fascia_addon.py` to the Blender addons dir, reload the add-on, ensure the horse is tagged as base + landmarks placed + muscles generated, then:

1. **Rest check (flex=0):** all muscle objects have `scale = (1.0, 1.0, 1.0)`. Skin displacement = 0.
2. **Contraction check (flex=1):** read `scale` on 2–3 muscles (e.g. Trapezius, GluteusMedius). Expect `scale = (≈1.1547, ≈1.1547, 0.75)`. Verify the product `scale[0]² · scale[2] ≈ 1.0` (volume preserved).
3. **Skin bulge check (flex=0.5):** count displaced skin vertices and max displacement. Expect a localized bulge (similar vertex count to before, smaller max displacement than the old heuristic since the push is now physically grounded).
4. **Symmetry check (flex=0):** sliding flex back to 0 restores muscles to (1,1,1) and skin to rest (no drift).

Report: the `scale` tuples of 2–3 muscles at flex=1, the product `scale[0]²·scale[2]` for each, and the flex=0.5 skin displacement count + max.

Sanity expectations:
- At flex=1: `length_scale=0.75`, `thickness_scale≈1.1547`, product `1.1547²·0.75 = 1.3333·0.75 = 1.0` ✓
- At flex=0.5: `c=0.125`, `length_scale=0.875`, `thickness_scale≈1.0690`, product `1.0690²·0.875 ≈ 1.0` ✓

---

## 7. Known limitations (must be documented in code comments, NOT hidden)

- **Attachments not pinned:** muscles shorten toward their midpoint; endpoints drift inward from landmarks during contraction. Pinning origin/insertion is future work.
- **Uniform contraction:** one Flex slider contracts every muscle by the same fraction. Per-muscle recruitment is future work.
- **Radial skin push only:** the axial shortening does not directly deform the skin; only the radial bulge does. Axial skin deformation near muscle ends is a future refinement.
- **No antagonist relaxation:** when a muscle contracts, its antagonist should relax/lengthen. This model contracts all muscles simultaneously. Future work.

These are honest scope boundaries, not bugs. Do NOT silently work around them.

---

## 8. Deliverable back to the architect

- The updated `fascia_addon.py` written to `C:\Projects\Fascia\fascia_addon.py` (the source — the architect handles the addons-dir copy and Blender reload).
- A short note confirming only the 3 locations in section 4 were changed.
- No need to paste logs — the architect will read the file and run verification independently.

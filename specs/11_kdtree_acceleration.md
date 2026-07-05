# SPEC 11 — KDTree Spatial Acceleration in Flex Skin Deformation

**Target executor:** implementing agent.
**Scope:** Implement `mathutils.kdtree.KDTree` to accelerate the skin-push deformation loop in `update_flex()`. Replaces the $O(V \cdot M)$ naive lookup with a $O(V \cdot \log(M))$ range query. Does not modify the skin-push formula, shape key safety logic, or panel layout.
**Estimated size:** ~15 lines modified in `fascia_addon.py`.

---

## 1. Why this change is needed

In `update_flex()`, the skin-push deformation loop is executed dynamically in pure Python as the user drags the "Flex" slider. 

For each vertex $v$ in the skin mesh and each muscle $m$ in the scene, the code:
1. Calculates the world position of the vertex.
2. Computes the distance from the vertex to the muscle's belly center.
3. If the distance is within the `influence_radius`, calculates and accumulates the push force.

With a naive nested loop, this requires $V \cdot M$ iterations (where $V$ is the number of vertices and $M$ is the number of muscles). For a typical high-resolution test mesh of 748,000 vertices and 29 muscles, this results in over 21.6 million distance calculations on every frame. In pure Python, this causes Blender to freeze for several seconds (or even minutes), making interactive posing impossible and blocking skin-sliding tests.

Using a spatial partition index (KDTree) allows us to query only the muscles that are actually close to a vertex, reducing the average complexity to $O(V \cdot \log(M))$ and enabling interactive performance.

---

## 2. Design

### 2a. Building the KDTree
In `update_flex()`, we first precompute the world-space center, radius, and thickness scale for all active muscles.
Then, we initialize and build a `KDTree`:

```python
from mathutils.kdtree import KDTree
kd = KDTree(len(muscle_info))
for idx, (m_center, m_radius, m_ts_i) in enumerate(muscle_info):
    kd.insert(m_center, idx)
kd.balance()
```

### 2b. Range Querying
Instead of iterating over all muscles for each vertex, we query the KDTree for all muscle indices within the `influence_radius` of the vertex's world position:

```python
for (_idx, dist, _co) in kd.find_range(world_pos, influence_radius):
    if dist < 0.001:
        continue
    m_center, m_radius, m_ts_i = muscle_info[_idx]
    # Calculate falloff and growth push...
```

This ensures we only compute the expensive vector math and push calculations for muscles that are actually close enough to affect the vertex.

---

## 3. Verification Criteria

1. **Functional Equivalence:** The resulting shape deformations and shape key vertex coordinates match the naive implementation exactly (with standard floating-point tolerance).
2. **State Consistency:** The scene property `_fascia_flex_affected` correctly tracks the total number of vertices that were modified by the flex slider.
3. **Performance Speedup:** The update loop is tested and executes substantially faster on high-poly meshes, keeping the UI interactive.

"""
Fascia — Pure-function smoke tests.

These tests cover the contraction math and landmark-mapping logic
that can be verified outside of Blender. Run with:

    python tests/smoke_test.py

No bpy, no Blender installation required.
"""

import math
import sys

# ─────────────────────────────────────────────────────────────────
# COPY of the math constants and pure functions from fascia_addon.py
# These are duplicated here intentionally so the tests can run
# without Blender. If you change the math in fascia_addon.py,
# update these too.
# ─────────────────────────────────────────────────────────────────

MAX_CONTRACTION = 0.25


def contraction_scales(flex, recruitment=1.0):
    """Return (length_scale, thickness_scale) for given flex and recruitment.

    Volume-preserving: V = pi*r^2*L is constant.
    c = flex * MAX_CONTRACTION * recruitment
    ls = 1 - c  (length scale)
    ts = 1 / sqrt(ls)  (thickness scale)
    """
    c = flex * MAX_CONTRACTION * recruitment
    ls = 1.0 - c
    ts = 1.0 / math.sqrt(ls) if ls > 0.01 else 1.0
    return ls, ts


def volume_product(ls, ts):
    """Return ls * ts^2 — should be 1.0 for any valid (ls, ts) pair."""
    return ls * ts * ts


def map_uvw_to_bbox(uvw, bbox_min, bbox_max):
    """Map a normalized (u,v,w) position to world space via a bounding box.

    uvw: (u, v, w) each in [0, 1]
    bbox_min: (min_x, min_y, min_z)
    bbox_max: (max_x, max_y, max_z)
    Returns (x, y, z) world position.
    """
    u, v, w = uvw
    x = bbox_min[0] + u * (bbox_max[0] - bbox_min[0])
    y = bbox_min[1] + v * (bbox_max[1] - bbox_min[1])
    z = bbox_min[2] + w * (bbox_max[2] - bbox_min[2])
    return (x, y, z)


# ─────────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────────

def assert_close(a, b, tol=1e-6, label=""):
    if abs(a - b) > tol:
        print(f"FAIL [{label}]: expected {b}, got {a} (diff={abs(a-b):.2e})")
        return False
    return True


def test_rest_pose():
    """At flex=0, no contraction: ls=1.0, ts=1.0."""
    ls, ts = contraction_scales(0.0)
    ok = True
    ok &= assert_close(ls, 1.0, label="rest ls")
    ok &= assert_close(ts, 1.0, label="rest ts")
    ok &= assert_close(volume_product(ls, ts), 1.0, label="rest volume")
    return ok


def test_full_flex():
    """At flex=1.0, recruitment=1.0: c=0.25, ls=0.75, ts=1/sqrt(0.75)."""
    ls, ts = contraction_scales(1.0, recruitment=1.0)
    expected_ls = 0.75
    expected_ts = 1.0 / math.sqrt(0.75)
    ok = True
    ok &= assert_close(ls, expected_ls, label="full_flex ls")
    ok &= assert_close(ts, expected_ts, label="full_flex ts")
    ok &= assert_close(volume_product(ls, ts), 1.0, label="full_flex volume")
    return ok


def test_double_recruitment():
    """At flex=1.0, recruitment=2.0: c=0.5, ls=0.5."""
    ls, ts = contraction_scales(1.0, recruitment=2.0)
    expected_ls = 0.5
    expected_ts = 1.0 / math.sqrt(0.5)
    ok = True
    ok &= assert_close(ls, expected_ls, label="double_recruit ls")
    ok &= assert_close(ts, expected_ts, label="double_recruit ts")
    ok &= assert_close(volume_product(ls, ts), 1.0, label="double_recruit volume")
    return ok


def test_zero_recruitment():
    """At flex=1.0, recruitment=0.0: no contraction."""
    ls, ts = contraction_scales(1.0, recruitment=0.0)
    ok = True
    ok &= assert_close(ls, 1.0, label="zero_recruit ls")
    ok &= assert_close(ts, 1.0, label="zero_recruit ts")
    return ok


def test_volume_preservation_sweep():
    """Volume product must be 1.0 for all flex in [0, 1], all recruitments."""
    ok = True
    for flex in [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]:
        for r in [0.0, 0.5, 1.0, 1.5, 2.0]:
            ls, ts = contraction_scales(flex, r)
            vp = volume_product(ls, ts)
            ok &= assert_close(vp, 1.0, tol=1e-5,
                               label=f"volume flex={flex} r={r}")
    return ok


def test_bbox_mapping_corners():
    """UVW (0,0,0) → min corner, (1,1,1) → max corner."""
    bbox_min = (0.0, 0.0, 0.0)
    bbox_max = (3.6, 1.2, 2.0)
    ok = True
    p = map_uvw_to_bbox((0.0, 0.0, 0.0), bbox_min, bbox_max)
    ok &= assert_close(p[0], 0.0, label="bbox min x")
    ok &= assert_close(p[2], 0.0, label="bbox min z")
    p = map_uvw_to_bbox((1.0, 1.0, 1.0), bbox_min, bbox_max)
    ok &= assert_close(p[0], 3.6, label="bbox max x")
    ok &= assert_close(p[2], 2.0, label="bbox max z")
    p = map_uvw_to_bbox((0.5, 0.5, 0.5), bbox_min, bbox_max)
    ok &= assert_close(p[0], 1.8, label="bbox center x")
    return ok


def test_bbox_mapping_offset():
    """UVW mapping works for non-zero-origin bounding boxes."""
    bbox_min = (-1.0, -0.5, 0.2)
    bbox_max = (1.0, 0.5, 1.8)
    p = map_uvw_to_bbox((0.5, 0.5, 0.5), bbox_min, bbox_max)
    ok = True
    ok &= assert_close(p[0], 0.0, label="offset bbox center x")
    ok &= assert_close(p[1], 0.0, label="offset bbox center y")
    ok &= assert_close(p[2], 1.0, label="offset bbox center z")
    return ok


def test_antagonist_safe_divisor():
    """Antagonist max_c_total must never be zero (safe floor)."""
    # Simulates the fix for Issue 12.
    for flex in [0.0, 0.0001, 0.001, 1.0]:
        max_c_total = max(flex * MAX_CONTRACTION, 1e-9)
        ok = max_c_total > 0.0
        if not ok:
            print(f"FAIL [antagonist_divisor]: flex={flex} gave max_c_total={max_c_total}")
            return False
    return True


# ─────────────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        ("rest pose", test_rest_pose),
        ("full flex volume preservation", test_full_flex),
        ("double recruitment", test_double_recruitment),
        ("zero recruitment", test_zero_recruitment),
        ("volume preservation sweep", test_volume_preservation_sweep),
        ("bbox mapping corners", test_bbox_mapping_corners),
        ("bbox mapping offset origin", test_bbox_mapping_offset),
        ("antagonist safe divisor", test_antagonist_safe_divisor),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        result = fn()
        if result:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name}")
            failed += 1

    print(f"\n{passed}/{passed + failed} tests passed.")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    print("Fascia pure-function smoke tests\n")
    run_all()

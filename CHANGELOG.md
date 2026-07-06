# Changelog

All notable changes to Fascia will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.2.0] — 2026-07-06

### Fixed
- Removed bare `print()` calls from species loading helpers (now clean fallbacks with operator warnings).
- Improved error paths in `_load_species` and `_load_species_json`.

### Added
- `poll()` methods on all major operators (addresses stability when not in Object Mode).
- `_validate_species_data()` with proper ERROR/WARNING reporting in operators.
- `tests/blender_smoke.py` (background Blender smoke test).
- Moved `IMPROVEMENT_PLAN.md` into `docs/`.
- Updated CI workflow with better documentation.
- `bl_info` and manifest bumped to 0.2.0.

### Changed
- LICENSE (MIT), expanded .gitignore, CONTRIBUTING.md, CHANGELOG.md (from previous scaffolding work).
- .github/ issue templates, PR template (with shape-key + registration safety checklists), basic CI.
- docs/llm-integration.md, docs/species-schema.md.
- tests/smoke_test.py (pure-function tests).
- blender_manifest.toml.
- README.md significantly expanded with installation, limitations table, and LLM usage guide.

### Previous
- Issue 1 and Issue 11 core fixes (see earlier commits).

---

## [0.1.0] — 2026-07-06

### Added
- Spec 1: Landmark proportions (real horse anatomy)
- Spec 2: Mesh-agnostic muscle sizing (fraction of bbox)
- Spec 3: Volume-preserving contraction (L·(1-c), r/√(1-c))
- Spec 4: Pinned muscle origin
- Spec 5: Per-muscle recruitment UIList
- Spec 6: Anatomy input slot (species JSON files)
- Spec 7: Rig binding (bone-parent landmarks)
- Spec 8: Muscle insertion tracking (Damped Track)
- Spec 9: LLM-facing surface (inline JSON + get_status)
- Spec 10: Antagonist pairing (reciprocal inhibition)
- Spec 11: KDTree spatial acceleration
- Spec 12: Skin sliding (axial tangential push)

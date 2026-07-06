# Changelog

All notable changes to Fascia will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed
- Issue 1: Stale _original_verts cache invalidated via depsgraph handler when user sculpts skin.
- Issue 11: update_flex reads from Basis shape key, not mesh.vertices, when shape keys exist.

### Added
- LICENSE (MIT), expanded .gitignore, CONTRIBUTING.md, CHANGELOG.md
- .github/ issue templates, PR template, CI lint workflow
- docs/llm-integration.md, docs/species-schema.md
- tests/smoke_test.py (pure-function contraction + bbox math tests)
- blender_manifest.toml (Blender 4.2+ Extensions system)

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

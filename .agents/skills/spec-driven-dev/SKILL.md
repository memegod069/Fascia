# Spec-Driven Development for Fascia

A skill for AI coding agents working on Fascia: always spec first, implement second.

## When to use

Use this skill when the captain asks you to implement a new feature or make a significant change to Fascia. "Significant" means any change that involves new operators, new properties, new landmark/muscle definitions, or changes to the flex/bake pipeline.

## Process

### Phase 1: Spec creation

1. Read the existing specs in `specs/` to understand the format and level of detail expected
2. Write a new spec following the established pattern: numbered file (e.g. `06_antagonist_pairing.md`)
3. Each spec must include:
   - **Title and summary** — what this feature does
   - **Problem statement** — what gap or limitation it addresses
   - **Design** — how it works, including key formulas, data structures, and control flow
   - **Verification criteria** — specific, measurable checks that prove it works (e.g. "with recruitment=0, muscle scale=(1,1,1) and volume product=1.0")
   - **Changes required** — which files and functions need modification
   - **Known limitations** — what this feature does NOT solve
4. Present the spec to the captain for review

### Phase 2: Implementation

Only start coding after the spec is approved. Follow the spec exactly — if you discover something during implementation that contradicts the spec, stop and ask.

Implementation must:
- Respect all Shape Key Safety rules in AGENTS.md (section "Shape Key Safety")
- Maintain correct registration/unregistration order
- Add new operators to both the `classes` tuple and the panel's `draw()` method
- Add new Scene properties in both `register()` and `unregister()`
- Label all new code with the spec number in comments

### Phase 3: Verification

Run through the verification criteria from the spec and report results. If verification fails, fix before declaring done.

## Example

```
captain: "Add antagonist pairing for muscles"

agent loads spec-driven-dev skill:
1. Reads specs/03_volume_preserving_contraction.md and specs/05_per_muscle_contraction_controls.md for context
2. Writes specs/06_antagonist_pairing.md
3. Shows it to captain
4. Captain approves
5. Implements following the spec
6. Verifies with the criteria in the spec
```

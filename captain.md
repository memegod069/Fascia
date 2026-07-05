# Captain's Preferences — Fascia Project

This file captures my personal preferences for how I want agents to work on this project.
It is local/personal (gitignored in principle) but kept in the repo for agent onboarding.

## Code Style

- Clean, readable code over clever optimizations
- Explanatory paragraph comments before complex functions, not inline annotations
- Descriptive variable names — prioritize clarity over brevity
- Keep functions focused on one thing
- No type annotations unless they add real value (Blender's bpy is dynamically typed anyway)

## Quality Bar

- Placeholder code must be clearly labeled as placeholder
- Known limitations must be documented in the code, not hidden
- Never claim something is "real" or "production" when it's a prototype
- Safety-critical code (shape keys, vertex deformation) needs explicit guards

## Development Approach

- Spec-driven: write the spec first, then implement
- Build the tool, not the horse — the horse mesh is a test case, not the deliverable
- One layer at a time, inside-out: muscles → fascia → fat → skin → motion
- When stuck on a problem, look at how Weta's Tissue or Ziva VFX approached it
- Prefer non-destructive workflows (shape keys, modifiers) over direct mesh editing

## Communication

- Be direct and honest about what's placeholder vs real
- If something will break existing functionality, say so before implementing
- Report limitations as part of the feature, not as an afterthought

## What I Value Most

1. Correctness — the math must be right (volume preservation, pinning, etc.)
2. Safety — never corrupt the user's mesh or shape keys
3. Honest labeling — call placeholders placeholders
4. Tool quality over mesh quality — make tools that work on ANY mesh
5. Documented limitations over silent failures

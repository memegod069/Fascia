# Fascia

Fascia is an early Blender add-on for creature soft-tissue workflows — the muscle, fascia, fat, and skin layers that sit on top of a rigged mesh.

It is inspired by high-end proprietary tissue systems, but this repository is **not** there yet. The current add-on is a **work in progress** that proves a basic tool flow inside Blender. It is not production-quality.

## What Fascia Is

- A Blender add-on that provides creature soft-tissue tools.
- A toolbox: each tool does one clear job and reports a short status message.
- A layer that sits on top of a base mesh and rig that come from elsewhere.

## What Fascia Is Not

- **Not an AI model.** There is no LLM or AI inside the add-on.
- **Not a mesh generator.** The base mesh comes from the user or another tool.
- **Not a rigging tool.** Rigging is Blender's job.
- **Not a real soft-body simulator.** No FEM/SOFA/physics backend yet.
- **Not a Weta/Ziva-level tissue system.**

External LLMs may drive Fascia's tools later, but only by calling them — Fascia is the hands, not the brain.

## Current Prototype

The add-on includes rough versions of seven tools:

1. Load Horse Base (placeholder blob, or tag any mesh as the base)
2. Customize Sliders (age, fat, color)
3. Place Landmarks (normalized to the base mesh's bounding box)
4. Generate Muscles (stretched spheres between landmarks)
5. Bind Skin to Muscles (flex slider — volume-preserving contraction + skin bulge)
6. Simulate Motion (60-frame flex test animation)
7. Bake Result (bake the flex animation into shape keys)

## What Works Right Now

- A Blender sidebar panel appears.
- A placeholder horse can be created, or any mesh can be tagged as the base.
- Age, fat, and color sliders work.
- Landmark markers can be placed on any base mesh.
- Simple muscle shapes can be generated, sized to the base mesh.
- A flex slider shortens and bulges muscles (volume-preserving) and pushes nearby skin vertices, with drift-free restore.
- A 60-frame test motion can be created and baked into shape keys.

These are a visible test pipeline, not final anatomy or real physics.

## Direction

The next goal is to keep the project honest and clean: improve the toolbox one small piece at a time, label placeholders clearly, and avoid pretending rough prototypes are final features.

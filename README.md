# Fascia

Fascia is an early Blender add-on experiment for creature creation and soft-tissue tools.

The long-term idea is simple:

- Blender provides the scene and meshes.
- Fascia provides useful creature-building tools.
- A user or an external LLM can drive those tools later.
- Fascia itself does not contain an AI model.

The project is inspired by high-end creature tissue systems, but this repository is not there yet. The current add-on is a v0 placeholder prototype that proves the basic tool flow inside Blender.

## Current Prototype

The add-on currently includes rough versions of seven tools:

1. Load Horse Base
2. Customize Sliders
3. Place Landmarks
4. Generate Muscles
5. Bind Skin to Muscles
6. Simulate Motion
7. Bake Result

These tools are useful as a visible test pipeline, not as final anatomy or real physics.

## What Is Real Right Now

- A Blender sidebar panel appears.
- A placeholder horse can be created.
- Basic age, fat, and color sliders work.
- Landmark markers can be placed.
- Simple muscle shapes can be generated.
- A flex slider can push nearby skin vertices.
- A 60-frame test motion can be created.
- The test motion can be baked into shape keys.

## What Is Not Real Yet

- No real horse base mesh or skeleton.
- No real soft-body physics.
- No FEM/SOFA simulation backend.
- No true automatic creature generation.
- No built-in LLM or AI assistant.
- No production-ready Weta/Ziva-level tissue system.

## Direction

The next goal is to keep the project honest and clean: improve the toolbox one small piece at a time, label placeholders clearly, and avoid pretending rough prototypes are final features.

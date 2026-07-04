# Fascia Project Memory

This file is the project source of truth for future AI coding sessions.
It is public-safe: do not include personal names, private details, API keys, or machine-specific secrets.

## 1. Core Vision

Fascia is a Blender add-on toolbox for creature creation and future soft-tissue workflows.

The long-term dream is an end-to-end Blender assistant experience:

- A user gives a high-level request, such as making a realistic horse.
- The user's own external LLM decides which tools to call.
- Fascia provides the actual Blender tools.
- The add-on itself contains no AI model.

Fascia should be the hands, not the brain.

## 2. Product Direction

Fascia has two connected ambitions:

1. Make Blender easier for non-experts by exposing clear, useful tools.
2. Grow toward accessible creature soft-tissue tools: muscles, fat, sliding skin, motion, and baked results.

The project is inspired by high-end systems such as Weta Tissue and Ziva-style workflows, but it must not claim that level yet.

## 3. Hard Design Rules

1. No AI lives inside Fascia.
2. External LLMs may drive Fascia later, but only by calling tools.
3. Each tool should do one clear job.
4. Tools should report short plain-English status messages.
5. Never return raw mesh or vertex dumps to an LLM-facing tool.
6. Do not overclaim placeholder code as real anatomy, real simulation, or production physics.
7. Keep public files free of personal/private information.

## 4. Current State

`fascia_addon.py` is a working v0 prototype with the full seven-tool flow implemented and functioning safely.

The seven planned tools are:

1. Load Horse Base
2. Customize Sliders
3. Place Landmarks
4. Generate Muscles
5. Bind Skin to Muscles
6. Simulate Motion
7. Bake Result

## 5. Tool Status

### 1. Load Horse Base

Status: placeholder implemented.

It creates a simple placeholder horse using basic mesh shapes. It is not a real horse mesh and does not include a skeleton.

### 2. Customize Sliders

Status: placeholder implemented.

Age, fat, and color controls affect the placeholder horse. These are simple object-level changes, not real anatomy-aware customization.

### 3. Place Landmarks

Status: placeholder implemented.

The add-on places hardcoded landmark empties tuned to the placeholder horse. This is not yet automatic landmark fitting for arbitrary meshes.

### 4. Generate Muscles

Status: placeholder implemented.

The add-on creates simple stretched muscle shapes between landmarks. These are visual/prototype muscles, not accurate anatomical muscle volumes.

### 5. Bind Skin to Muscles

Status: working, safe deformation system.

The flex slider scales muscle objects and pushes nearby skin vertices outward using a smooth distance-based falloff. It utilizes a clean vertex backup and restore system (`_original_verts`) to ensure deformation is calculated fresh each time, preventing drift or stacking. The original geometry is protected in a `Basis` shape key, while live previews are written safely to a `Live_Flex` shape key. While it provides robust mathematical deformation, it is not a true physics-based tissue simulation.

### 6. Simulate Motion

Status: v0 implemented.

The add-on creates a deterministic 60-frame test animation by keyframing the flex value with a specific relaxation-flexion curve. This proves the pipeline can make motion over time, but it is not real physical simulation.

### 7. Bake Result

Status: v0 implemented.

The add-on samples the 60-frame flex animation and stores the result as shape keys named like `Baked_Frame_001`. This is a basic reusable bake, not a final simulation cache/export system.

## 6. Shape Key Safety Notes

The code uses `Basis`, `Live_Flex`, and baked frame shape keys.

Important rules for future edits:

- Do not write flexed results into `Basis`.
- If `Live_Flex` exists, live deformation should go there.
- Baked results should be written into separate shape keys.
- Be careful with raw `mesh.vertices` edits because they can affect the base mesh.
- Add guards before relying on saved vertex backups if mesh topology changes.

## 7. What Fascia Is Not Yet

Fascia is not yet:

- A real AAA horse generator.
- A true Blender LLM assistant.
- A real Weta/Ziva replacement.
- A SOFA/FEM simulation tool.
- A full creature rigging system.
- A production-ready add-on.

It is currently a working prototype shell with a visible seven-step placeholder pipeline.

## 8. Next Sensible Work

Before adding major new features, do a cleanup and reality pass:

- Test the full seven-tool flow in Blender.
- Fix confusing labels or comments.
- Keep README and memory honest.
- Decide what counts as "v0 complete."

After that, the next larger direction should be choosing a real foundation for future growth: better data/templates, real meshes, stronger binding logic, or a future simulation backend.

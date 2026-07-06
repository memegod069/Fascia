# Contributing to Fascia

Thank you for your interest. This is a small project and contributions are welcome.

## Before You Start

1. Read `AGENTS.md` — it is the source of truth for how the project works and what the hard rules are.
2. Read `memory.md` — full project state, what is real vs placeholder, known limitations.
3. Read `issues.md` — the open issue backlog with reproduction steps and suggested fixes.

## Setting Up for Development

1. Clone the repo:
   ```bash
   git clone https://github.com/memegod069/Fascia.git
   ```
2. Symlink or copy `fascia_addon.py` into Blender's `scripts/addons/` folder.
3. Enable **Fascia** in Blender → Edit → Preferences → Add-ons.
4. After changes, use **Scripts → Reload Scripts** (`Alt+R`) in Blender to reload without restarting.

## Making Changes

### For bug fixes
- Check `issues.md` for the reproduction steps and suggested fix.
- Make the minimal change that fixes the described bug.
- Verify the fix manually in Blender using the reproduction steps.
- Preserve all shape-key safety rules (see `AGENTS.md` § Shape Key Safety).

### For new features
- Follow the spec-driven process: write a spec in `specs/` first (see existing specs for format).
- Present the spec before implementing.
- Add new operators to BOTH the `classes` tuple AND the panel `draw()` method.
- Add new Scene properties in BOTH `register()` AND `unregister()`.
- Respect registration order rules (see `AGENTS.md` § Registration order rules).

## Code Style

- Explanatory paragraph comments before complex functions, not inline annotations.
- Descriptive variable names — clarity over brevity.
- Keep functions focused on one thing.
- No type annotations (Blender's bpy is dynamically typed).
- Use `self.report({'INFO'}, "Fascia: ...")` for user-visible messages in operators.
- Use `self.report({'WARNING'}, "Fascia: ...")` for soft failures.
- Do NOT use bare `print()` for user-facing messages in operators.

## Testing

There is no automated test suite yet. Test manually:
1. Open Blender (4.0+).
2. Enable the add-on.
3. Run each tool in order (Tools 1–7, then Tool 9).
4. Check the `issues.md` reproduction steps for any issues you are fixing.

A basic smoke-test script (pure Python, no Blender required) is in `tests/smoke_test.py`.

A Blender-specific smoke test is in `tests/blender_smoke.py` — run with:
```bash
blender --background --python tests/blender_smoke.py
```

For full end-to-end verification (including shape keys, flex, bake, and rig binding), always test manually inside the Blender GUI.

## Pull Requests

- One fix or feature per PR.
- Describe what you changed and why.
- List which `issues.md` item you addressed (e.g., "Fixes Issue 3").
- Do not mix unrelated changes.

## What NOT to Do

- Do not write flexed vertex data into the Basis shape key.
- Do not add AI or LLM logic inside the add-on (rule 1 in AGENTS.md).
- Do not rebuild Blender features that already exist (rigging, sculpting).
- Do not claim geometric contraction is real FEM physics.
- Do not tune values for one specific test mesh — build the tool for any mesh.

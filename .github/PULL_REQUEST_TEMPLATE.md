## Summary
<!-- One sentence: what does this PR do? -->

## Issue addressed
<!-- e.g. "Fixes Issue 3 (missing poll methods)" -->

## Changes made
<!-- List the files changed and why. -->

## Testing done (Blender version?)
<!-- Describe manual testing in Blender. Include Blender version. -->

## Shape-key safety check
- [ ] Did NOT write flexed data into Basis shape key
- [ ] Did NOT write to mesh.vertices when shape keys exist
- [ ] Baked data captured BEFORE creating/modifying Basis

## Registration order check (if adding operators/properties)
- [ ] New operator in BOTH classes tuple AND panel.draw()
- [ ] New Scene property in BOTH register() AND unregister()
- [ ] PropertyGroup registered BEFORE UIList referencing it
- [ ] CollectionProperty/IntProperty deleted BEFORE unregistering PropertyGroup

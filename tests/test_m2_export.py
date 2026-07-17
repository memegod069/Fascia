import os
import sys
import json
import numpy as np
import importlib

# Prefer the project-local fascia_addon over any older copy already enabled
# from Blender's user addons folder (AppData may not have export_scene).
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import bpy

# Drop a pre-loaded (possibly outdated) fascia_addon module if present.
if "fascia_addon" in sys.modules:
    try:
        sys.modules["fascia_addon"].unregister()
    except Exception:
        pass
    del sys.modules["fascia_addon"]

import fascia_addon
importlib.reload(fascia_addon)

def setup_test_scene():
    print("Setting up M2 test scene...")
    # Clear existing mesh and armature objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # 1. Create Armature
    bpy.ops.object.armature_add(enter_editmode=True, align='WORLD', location=(0, 0, 0))
    arm_obj = bpy.context.active_object
    arm_obj.name = "TestRig"
    
    ebones = arm_obj.data.edit_bones
    if ebones:
        ebones.remove(ebones[0])
        
    upper_arm = ebones.new("UpperArm")
    upper_arm.head = (0, 0, 0)
    upper_arm.tail = (0, 0, 1.0)
    
    forearm = ebones.new("Forearm")
    forearm.head = (0, 0, 1.0)
    forearm.tail = (0, 0, 2.0)
    forearm.parent = upper_arm
    
    # Go to Pose mode to animate
    bpy.ops.object.mode_set(mode='POSE')
    
    p_forearm = arm_obj.pose.bones["Forearm"]
    p_forearm.rotation_mode = 'XYZ'
    
    # Force linear interpolation via user preferences
    pref = bpy.context.preferences.edit
    old_interp = pref.keyframe_new_interpolation_type
    pref.keyframe_new_interpolation_type = 'LINEAR'
    
    try:
        # Frame 1: 0 degrees
        p_forearm.rotation_euler = (0, 0, 0)
        p_forearm.keyframe_insert(data_path="rotation_euler", frame=1)
        
        # Frame 60: 90 degrees around X-axis (1.570796 radians)
        p_forearm.rotation_euler = (1.5707963, 0, 0)
        p_forearm.keyframe_insert(data_path="rotation_euler", frame=60)
    finally:
        # Restore preference
        pref.keyframe_new_interpolation_type = old_interp
                
    # Go back to Object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    
    # 2. Create a base skin object (just a tagged cube)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 1))
    skin_obj = bpy.context.active_object
    skin_obj.name = "TestSkin"
    skin_obj["fascia_role"] = "skin"
    
    # 3. Create Landmark Empty objects
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0.1, 0.2))
    lm_origin = bpy.context.active_object
    lm_origin.name = "Fascia_LM_Shoulder"
    lm_origin["fascia_type"] = "landmark"
    lm_origin["fascia_landmark"] = "Shoulder"
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0.1, 1.8))
    lm_insertion = bpy.context.active_object
    lm_insertion.name = "Fascia_LM_Hand"
    lm_insertion["fascia_type"] = "landmark"
    lm_insertion["fascia_landmark"] = "Hand"
    
    # Parent landmarks to bones using parent_set operator
    # Shoulder to UpperArm
    arm_obj.data.bones.active = arm_obj.data.bones["UpperArm"]
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.select_set(True)
    lm_origin.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type='BONE', keep_transform=True)
    lm_origin["fascia_bone"] = "UpperArm"
    
    # Hand to Forearm
    arm_obj.data.bones.active = arm_obj.data.bones["Forearm"]
    bpy.ops.object.select_all(action='DESELECT')
    arm_obj.select_set(True)
    lm_insertion.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type='BONE', keep_transform=True)
    lm_insertion["fascia_bone"] = "Forearm"
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 4. Create Muscle
    muscle_obj = fascia_addon.create_muscle_mesh("Biceps", (0, 0.1, 0.2), (0, 0.1, 1.8), radius=0.1)
    muscle_obj["fascia_type"] = "muscle"
    muscle_obj["fascia_muscle_name"] = "Biceps"
    muscle_obj["fascia_origin"] = "Fascia_LM_Shoulder"
    muscle_obj["fascia_insertion"] = "Fascia_LM_Hand"
    muscle_obj["fascia_radius"] = 0.1
    muscle_obj["fascia_rest_length"] = 1.6
    
    # Assign scene properties
    scene = bpy.context.scene
    scene.fascia_armature = arm_obj
    scene.frame_start = 1
    scene.frame_end = 60

    # Ramp fascia_flex 0 → 1 across the 60-frame timeline (M0-style activation
    # ramp, scaled to 60 frames: a = (frame - 1) / 59). Export samples this
    # per frame into activations.Biceps. Do NOT leave flex stuck at 1.0 —
    # that made every frame full activation and hid the contraction ramp.
    pref = bpy.context.preferences.edit
    old_interp = pref.keyframe_new_interpolation_type
    pref.keyframe_new_interpolation_type = 'LINEAR'
    try:
        scene.frame_set(1)
        scene.fascia_flex = 0.0
        scene.keyframe_insert(data_path="fascia_flex", frame=1)

        scene.frame_set(60)
        scene.fascia_flex = 1.0
        scene.keyframe_insert(data_path="fascia_flex", frame=60)
    finally:
        pref.keyframe_new_interpolation_type = old_interp

    scene.frame_set(1)
    
    # Setup per-muscle recruitment
    scene.fascia_recruitment.clear()
    entry = scene.fascia_recruitment.add()
    entry.name = "Biceps"
    entry.recruitment = 1.0
    
    # Damped Track constraint for muscle targeting
    bpy.ops.object.select_all(action='DESELECT')
    muscle_obj.select_set(True)
    bpy.context.view_layer.objects.active = muscle_obj
    constraint = muscle_obj.constraints.new(type='DAMPED_TRACK')
    constraint.target = lm_insertion
    constraint.track_axis = 'TRACK_Z'
    
    print("Scene setup completed.")
    return arm_obj, muscle_obj

def run_test():
    # Register the project-local addon (may already be enabled as a user addon).
    try:
        fascia_addon.unregister()
    except Exception:
        pass
    fascia_addon.register()
    
    setup_test_scene()
    
    print("\nRunning export operator...")
    res = bpy.ops.fascia.export_scene()
    if res != {'FINISHED'}:
        print(f"Export operator failed with result: {res}")
        sys.exit(1)
        
    print("\nVerifying exported files...")
    scene_json = "scene.json"
    animation_json = "animation.json"
    muscle_tet_json = "meshes/Biceps_tet.json"
    
    assert os.path.exists(scene_json), "scene.json missing"
    assert os.path.exists(animation_json), "animation.json missing"
    assert os.path.exists(muscle_tet_json), "muscle tet mesh missing"
    
    # Read and print summaries
    with open(scene_json, 'r') as f:
        scene_data = json.load(f)
    print(f"scene.json has {len(scene_data['bones'])} bones and {len(scene_data['objects'])} simulated objects.")
    
    with open(animation_json, 'r') as f:
        anim_data = json.load(f)
    n_frames = len(anim_data['frames'])
    print(f"animation.json has {n_frames} frames.")

    # Confirm flex ramp made it into activations (not a flat 1.0 constant).
    acts = []
    for fr in anim_data["frames"]:
        act = fr["activations"].get("Biceps")
        if act is None:
            # Fallback: muscle object name may differ; take first activation
            act = next(iter(fr["activations"].values()))
        acts.append(float(act))

    print("Activation samples:")
    for idx in (0, n_frames // 2, n_frames - 1):
        print(f"  frame {anim_data['frames'][idx]['frame']:02d}: Biceps a={acts[idx]:.4f}")

    assert abs(acts[0] - 0.0) < 1e-4, f"Expected activation ~0 at start, got {acts[0]}"
    assert abs(acts[-1] - 1.0) < 1e-4, f"Expected activation ~1 at end, got {acts[-1]}"
    mid = acts[n_frames // 2]
    assert 0.35 < mid < 0.65, f"Expected mid activation ~0.5, got {mid}"
    assert len(set(round(a, 4) for a in acts)) > 2, "Activation must ramp (not constant)"
    print(f"Activation ramp OK: {acts[0]:.3f} → {mid:.3f} → {acts[-1]:.3f}")
    
    with open(muscle_tet_json, 'r') as f:
        mesh_data = json.load(f)
    print(f"Biceps tet mesh has {len(mesh_data['vertices'])} vertices and {len(mesh_data['tets'])} tetrahedra.")
    
    # Unregister addon
    fascia_addon.unregister()
    
    print("\n[PASS] M2 Export pipeline verification successful!")
    
if __name__ == "__main__":
    run_test()

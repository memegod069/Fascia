import bpy
import os

# Set the path to the OBJ sequence directory
directory = r"C:\Projects\Fascia\m1_output\Biceps"

# Get all OBJ files sorted
files = sorted([f for f in os.listdir(directory) if f.endswith(".obj")])

if not files:
    print("No OBJ files found in the directory.")
else:
    print(f"Found {len(files)} OBJ files. Starting import...")
    
    # Clear selection first
    bpy.ops.object.select_all(action='DESELECT')
    
    # Import the first frame as the base mesh
    bpy.ops.wm.obj_import(filepath=os.path.join(directory, files[0]))
    base_obj = bpy.context.active_object
    base_obj.name = "Biceps_Simulated"
    
    # Ensure Basis shape key exists
    if not base_obj.data.shape_keys:
        base_obj.shape_key_add(name="Basis")

    # Loop through the rest of the frames
    for i, filename in enumerate(files[1:], start=1):
        filepath = os.path.join(directory, filename)
        
        # Import target frame
        bpy.ops.wm.obj_import(filepath=filepath)
        temp_obj = bpy.context.active_object
        
        # Select base and temp objects, making base active
        bpy.ops.object.select_all(action='DESELECT')
        base_obj.select_set(True)
        temp_obj.select_set(True)
        bpy.context.view_layer.objects.active = base_obj
        
        # Join as shape key
        bpy.ops.object.join_as_shapes()
        
        # Rename the new shape key
        key_block = base_obj.data.shape_keys.key_blocks[-1]
        key_block.name = f"Frame_{i:03d}"
        
        # Delete temp object
        bpy.ops.object.select_all(action='DESELECT')
        temp_obj.select_set(True)
        bpy.ops.object.delete()
        
    # Re-select the base object
    bpy.ops.object.select_all(action='DESELECT')
    base_obj.select_set(True)
    bpy.context.view_layer.objects.active = base_obj
    
    # Animate shape keys over the timeline
    # Frame i should have shape key Frame_i set to 1.0, and others at 0.0
    for i in range(1, len(files)):
        key_name = f"Frame_{i:03d}"
        key_block = base_obj.data.shape_keys.key_blocks.get(key_name)
        if key_block:
            # Keyframe 0.0 at frame i
            key_block.value = 0.0
            key_block.keyframe_insert(data_path="value", frame=i)
            # Keyframe 1.0 at frame i + 1
            key_block.value = 1.0
            key_block.keyframe_insert(data_path="value", frame=i + 1)
            # Keyframe 0.0 at frame i + 2
            key_block.value = 0.0
            key_block.keyframe_insert(data_path="value", frame=i + 2)
            
    # Set timeline frame start/end
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = len(files)
    bpy.context.scene.frame_set(1)
    
    # Define and show popup dialog for direct user feedback in the UI
    message_text = f"Import Successful! Loaded {len(files)} frames into 'Biceps_Simulated'."
    def draw_popup(self, context):
        self.layout.label(text=message_text)
        self.layout.label(text="Please: 1. Switch to Object Mode. 2. Hide other objects. 3. Press Play.")

    bpy.context.window_manager.popup_menu(draw_popup, title="Fascia Importer", icon='CHECKMARK')
    print("OBJ sequence successfully imported and animated!")

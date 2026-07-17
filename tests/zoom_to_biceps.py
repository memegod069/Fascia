import bpy

# Find the simulated biceps object
biceps = bpy.data.objects.get("Biceps_Simulated")

if not biceps:
    print("Could not find Biceps_Simulated object. Make sure you ran the import script first.")
else:
    # Delete all other objects in the scene to avoid confusion
    for obj in list(bpy.data.objects):
        if obj.name != "Biceps_Simulated":
            bpy.data.objects.remove(obj, do_unlink=True)
            
    # Select the biceps and make it active
    bpy.ops.object.select_all(action='DESELECT')
    biceps.select_set(True)
    bpy.context.view_layer.objects.active = biceps
    
    # Zoom the viewport camera to fit the biceps object
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    with bpy.context.temp_override(area=area, region=region, active_object=biceps, selected_objects=[biceps]):
                        bpy.ops.view3d.view_selected()
                        
    # Show popup in the viewport
    def draw_popup(self, context):
        self.layout.label(text="Viewport Centered! Focused on 'Biceps_Simulated'.")
        self.layout.label(text="Other helper shapes have been hidden. Press Play (Spacebar) to watch the bend.")

    bpy.context.window_manager.popup_menu(draw_popup, title="Fascia Viewport Focus", icon='ZOOM_IN')
    print("Viewport successfully zoomed and focused on the Biceps simulation!")

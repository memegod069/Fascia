bl_info = {
    "name": "Fascia",
    "author": "You",
    "version": (0, 0, 3),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Fascia",
    "description": "Fascia creature soft-tissue toolbox — landmarks, muscles, skin binding",
    "category": "Add Mesh",
}

import bpy
import bmesh
import mathutils


# ─────────────────────────────────────────────────────────────────
# BACKUP STORAGE FOR ORIGINAL SKIN VERTEX POSITIONS
# ─────────────────────────────────────────────────────────────────
# When the Flex slider moves for the first time, we save the
# original vertex positions of the horse body and head meshes here.
# This lets us always calculate deformation from the clean,
# unflexed shape — so sliding Flex back to 0 restores the skin
# perfectly with zero drift.
#
# It's a dictionary: key = object name, value = list of (x, y, z).
# It lives at the module level so it persists while the add-on
# is active, but resets when Blender restarts (which is fine,
# because the meshes start undeformed on restart anyway).
# ─────────────────────────────────────────────────────────────────

_original_verts = {}


# ─────────────────────────────────────────────────────────────────
# HORSE LANDMARK DEFINITIONS
# ─────────────────────────────────────────────────────────────────
# Each entry has:
#   pos       – default (X, Y, Z) world position, tuned for the placeholder horse
#   bilateral – True if it exists on both left and right sides of the horse
#   region    – which body area it belongs to (for organisation)
#
# Bilateral landmarks store the LEFT-side Y position.
# The right side is created automatically by flipping Y to negative.
# ─────────────────────────────────────────────────────────────────

HORSE_LANDMARKS = {
    # Head & Neck (midline)
    "Poll":            {"pos": (2.20, 0.00, 1.75), "bilateral": False, "region": "head"},
    "NuchalCrest":     {"pos": (1.85, 0.00, 1.55), "bilateral": False, "region": "neck"},

    # Shoulder & Forelimb
    "Withers":         {"pos": (0.80, 0.00, 1.88), "bilateral": False, "region": "back"},
    "ScapulaTop":      {"pos": (0.70, 0.30, 1.60), "bilateral": True,  "region": "shoulder"},
    "PointOfShoulder": {"pos": (1.00, 0.35, 0.55), "bilateral": True,  "region": "shoulder"},
    "Elbow":           {"pos": (0.50, 0.30, 0.25), "bilateral": True,  "region": "forelimb"},
    "FrontKnee":       {"pos": (0.85, 0.25,-0.10), "bilateral": True,  "region": "forelimb"},

    # Trunk / Torso (midline)
    "Chest":           {"pos": (1.00, 0.00, 0.15), "bilateral": False, "region": "chest"},
    "MidBack":         {"pos": (0.00, 0.00, 1.88), "bilateral": False, "region": "back"},
    "BellyMid":        {"pos": (0.00, 0.00, 0.12), "bilateral": False, "region": "belly"},

    # Hip & Hindlimb
    "PointOfHip":      {"pos": (-0.70, 0.35, 1.70), "bilateral": True,  "region": "hip"},
    "PointOfCroup":    {"pos": (-0.80, 0.00, 1.82), "bilateral": False, "region": "hip"},
    "PointOfButtock":  {"pos": (-1.50, 0.20, 1.15), "bilateral": True,  "region": "hip"},
    "HipJoint":        {"pos": (-0.90, 0.40, 1.05), "bilateral": True,  "region": "hip"},
    "Stifle":          {"pos": (-1.00, 0.35, 0.35), "bilateral": True,  "region": "hindlimb"},
    "Hock":            {"pos": (-1.10, 0.28,-0.10), "bilateral": True,  "region": "hindlimb"},

    # Internal anchor points (hidden attachment sites inside the body)
    "SerratusAnchor":  {"pos": (0.60, 0.15, 1.00), "bilateral": True,  "region": "shoulder"},
    "LatAnchor":       {"pos": (0.55, 0.32, 0.75), "bilateral": True,  "region": "forelimb"},
}


# ─────────────────────────────────────────────────────────────────
# HORSE MUSCLE DEFINITIONS
# ─────────────────────────────────────────────────────────────────
# Each muscle stretches between two landmark points.
#   from   – the origin landmark name (must match a key in HORSE_LANDMARKS)
#   to     – the insertion landmark name
#   radius – how thick the muscle shape is
#   color  – viewport display colour (Red, Green, Blue, Alpha)
#
# Front-body muscles use warm reds/oranges.
# Rear-body muscles use cool blues/purples.
# ─────────────────────────────────────────────────────────────────

HORSE_MUSCLES = {
    # Front body (warm colours)
    "Trapezius":         {"from": "Withers",         "to": "ScapulaTop",      "radius": 0.06, "color": (0.80, 0.20, 0.15, 0.60)},
    "Deltoid":           {"from": "ScapulaTop",      "to": "PointOfShoulder", "radius": 0.05, "color": (0.90, 0.35, 0.10, 0.60)},
    "Triceps":           {"from": "ScapulaTop",      "to": "Elbow",           "radius": 0.07, "color": (0.70, 0.12, 0.12, 0.60)},
    "BicepsBrachii":     {"from": "PointOfShoulder", "to": "Elbow",           "radius": 0.05, "color": (0.85, 0.45, 0.35, 0.60)},
    "Pectorals":         {"from": "Chest",           "to": "PointOfShoulder", "radius": 0.07, "color": (0.82, 0.30, 0.30, 0.60)},
    "SerratusVentralis": {"from": "Chest",           "to": "SerratusAnchor",  "radius": 0.06, "color": (0.78, 0.35, 0.40, 0.60)},
    "LatissimusDorsi":   {"from": "MidBack",         "to": "LatAnchor",       "radius": 0.07, "color": (0.72, 0.22, 0.18, 0.60)},
    "Brachiocephalicus": {"from": "Poll",            "to": "PointOfShoulder", "radius": 0.05, "color": (0.88, 0.50, 0.30, 0.60)},

    # Spine & torso
    "LongissimusDorsi":  {"from": "Withers",         "to": "PointOfCroup",    "radius": 0.06, "color": (0.65, 0.18, 0.18, 0.60)},
    "RectusAbdominis":   {"from": "Chest",           "to": "PointOfHip",      "radius": 0.05, "color": (0.75, 0.55, 0.40, 0.60)},

    # Rear body (cool colours)
    "GluteusMedius":     {"from": "PointOfHip",      "to": "HipJoint",        "radius": 0.10, "color": (0.20, 0.22, 0.78, 0.60)},
    "BicepsFemoris":     {"from": "PointOfButtock",  "to": "Stifle",          "radius": 0.07, "color": (0.30, 0.30, 0.85, 0.60)},
    "Semitendinosus":    {"from": "PointOfButtock",  "to": "Hock",            "radius": 0.06, "color": (0.40, 0.38, 0.75, 0.60)},
    "Quadriceps":        {"from": "HipJoint",        "to": "Stifle",          "radius": 0.07, "color": (0.45, 0.25, 0.70, 0.60)},
    "Gastrocnemius":     {"from": "Stifle",          "to": "Hock",            "radius": 0.05, "color": (0.55, 0.42, 0.78, 0.60)},
}


# This is a helper function that runs automatically whenever you slide the Age, Fat, or Color controls.
# It finds the horse objects and updates their scale and viewport display color instantly.
def update_horse(self, context):
    scene = context.scene

    # 1. Update the body of the horse
    body = bpy.data.objects.get("Fascia_Horse_Body")
    if body:
        # Fat scales the body along Y (width) and Z (height), but NOT X (length).
        # We start with a base thickness of 0.4 and add the Fat value (0.0 to 1.0).
        # This makes the fatness range from 0.4 (very skinny) to 1.4 (very fat).
        fat_scale = 0.4 + scene.fascia_fat
        body.scale[1] = fat_scale  # Y scale (width)
        body.scale[2] = fat_scale  # Z scale (height)

        # Apply the RGB color picker value to the body's viewport color.
        # Blender expects 4 values (Red, Green, Blue, Alpha/Opacity).
        # We set Alpha to 1.0 so it is solid (not see-through).
        r, g, b = scene.fascia_color
        body.color = (r, g, b, 1.0)

    # 2. Update the head of the horse
    head = bpy.data.objects.get("Fascia_Horse_Head")
    if head:
        # Age changes the head-to-body size ratio.
        # Younger horses (Age = 0) have relatively larger heads.
        # Older horses (Age = 1) have relatively smaller heads.
        # We calculate this: 1.3 when age is 0, down to 0.7 when age is 1.
        age_scale = 1.3 - (0.6 * scene.fascia_age)
        head.scale = (age_scale, age_scale, age_scale)

        # Apply the same viewport color to the head.
        r, g, b = scene.fascia_color
        head.color = (r, g, b, 1.0)


# ─────────────────────────────────────────────────────────────────
# HELPERS: Save and restore original skin vertex positions
# ─────────────────────────────────────────────────────────────────
# These two little functions are the safety net for the Flex slider.
# Before we deform the skin, we save a snapshot of every vertex.
# Every time the slider moves, we restore to the clean snapshot
# first, THEN apply the new deformation from scratch. This means
# the deformation never "stacks" or drifts — it's always a fresh
# calculation from the original, unflexed shape.
# ─────────────────────────────────────────────────────────────────

def _save_original_verts(obj):
    """
    Remember the current vertex positions of a mesh object.
    Only saves once per object — if positions are already saved,
    this does nothing. That prevents accidentally overwriting
    the clean originals with already-deformed positions.
    """
    if obj.name not in _original_verts:
        mesh = obj.data
        _original_verts[obj.name] = [
            (v.co.x, v.co.y, v.co.z) for v in mesh.vertices
        ]


def _restore_original_verts(obj):
    """
    Put all vertices back to their saved original positions.
    Called at the start of every flex update so we always deform
    from the clean shape, never from previously deformed positions.
    """
    if obj.name in _original_verts:
        mesh = obj.data
        saved = _original_verts[obj.name]
        for i, (x, y, z) in enumerate(saved):
            mesh.vertices[i].co.x = x
            mesh.vertices[i].co.y = y
            mesh.vertices[i].co.z = z


# ─────────────────────────────────────────────────────────────────
# TOOL 5: FLEX UPDATE (Bind Skin to Muscles)
# ─────────────────────────────────────────────────────────────────
# This function runs automatically every time the Flex slider moves.
# It does two things:
#
#   1. FATTEN THE MUSCLES — each muscle gets wider (but not longer)
#      to simulate flexing/contracting.
#
#   2. BULGE THE SKIN — for every vertex on the horse body and head,
#      check if it's near a muscle center. If it is, push that
#      vertex outward (away from the muscle), so the skin "bulges"
#      over the swelling muscle — like real flesh pressing against
#      skin from underneath.
#
# The closer a vertex is to a muscle, the more it gets pushed.
# The effect fades smoothly to zero at the edge of the influence
# radius (no hard cutoff). Bigger muscles push the skin more
# than smaller ones, which looks natural.
# ─────────────────────────────────────────────────────────────────

def update_flex(self, context):
    scene = context.scene
    flex = scene.fascia_flex

    # ── Step 1: Scale muscles radially (fatter, not longer) ───
    #
    # Each muscle was built so its local Z axis runs along its
    # length, and local X/Y are its thickness (see create_muscle_mesh).
    # So scaling X and Y makes it fatter without making it longer.
    #
    #   flex = 0  →  scale = 1.0  (normal size)
    #   flex = 1  →  scale = 1.5  (50% fatter)

    muscles = [obj for obj in bpy.data.objects
               if obj.get("fascia_type") == "muscle"]

    muscle_scale = 1.0 + flex * 0.5

    for obj in muscles:
        obj.scale[0] = muscle_scale  # local X = thickness
        obj.scale[1] = muscle_scale  # local Y = thickness
        # scale[2] stays at 1.0 — length doesn't change

    # ── Step 2: Push skin vertices outward near muscles ───────
    #
    # For each vertex on the horse's skin (body + head mesh),
    # we check how close it is to each muscle's center point.
    #
    # If it's within the "influence_radius" (0.3 Blender units),
    # we push that vertex outward — away from the muscle center —
    # so the skin appears to bulge over the swelling muscle.
    #
    # The push amount depends on:
    #   • How much the muscle grew (flex * muscle_radius * 0.5)
    #   • How close the vertex is (closer = more push, smooth falloff)
    #
    # We always start from the ORIGINAL vertex positions (not the
    # already-pushed ones) so the deformation never drifts.

    influence_radius = 0.3   # How far (in Blender units) a muscle's effect reaches
    total_affected = 0

    # Find the skin mesh objects (the horse body and head)
    skin_objects = []
    body = bpy.data.objects.get("Fascia_Horse_Body")
    head = bpy.data.objects.get("Fascia_Horse_Head")
    if body and body.data:
        skin_objects.append(body)
    if head and head.data:
        skin_objects.append(head)

    # Precompute muscle info so we don't recalculate it for every vertex.
    # For each muscle, we need its center (world position) and its radius
    # (how thick it is — stored when the muscle was generated).
    muscle_info = []
    for m in muscles:
        center = m.matrix_world.translation.copy()
        radius = m.get("fascia_radius", 0.04)
        muscle_info.append((center, radius))

    for obj in skin_objects:
        mesh = obj.data

        # Save the original vertex positions (only happens once per object)
        _save_original_verts(obj)

        # Restore all vertices back to the original, unflexed positions.
        # If shape keys exist, this correctly keeps the Basis key perfectly clean!
        _restore_original_verts(obj)

        if flex < 0.001:
            # Slider is at zero — skin is restored.
            # Turn off Live_Flex if it exists so we just see the clean Basis.
            if mesh.shape_keys and "Live_Flex" in mesh.shape_keys.key_blocks:
                mesh.shape_keys.key_blocks["Live_Flex"].value = 0.0
            mesh.update()
            continue

        # Determine where to write the flexed positions.
        # If shape keys exist, we MUST NOT write to mesh.vertices (which is Basis).
        # We write to a temporary "Live_Flex" shape key instead.
        if mesh.shape_keys:
            live_key = mesh.shape_keys.key_blocks.get("Live_Flex")
            if not live_key:
                live_key = obj.shape_key_add(name="Live_Flex")
            live_key.value = 1.0
            target_data = live_key.data
        else:
            # No shape keys exist, deform the base mesh directly
            target_data = mesh.vertices

        # Get the transform matrices for this skin object.
        world_mat = obj.matrix_world.copy()
        world_inv = world_mat.inverted()

        for i, vert in enumerate(mesh.vertices):
            # NOTE: We read from mesh.vertices (which is always clean),
            # but we write to target_data (which might be Live_Flex).
            world_pos = world_mat @ vert.co

            # Accumulate push from all nearby muscles
            push = mathutils.Vector((0.0, 0.0, 0.0))
            was_affected = False

            for (m_center, m_radius) in muscle_info:
                delta = world_pos - m_center
                dist = delta.length

                if dist < influence_radius and dist > 0.001:
                    t = dist / influence_radius
                    falloff = (1.0 - t) * (1.0 - t)
                    growth = flex * m_radius * 0.5
                    push_dir = delta.normalized()
                    push += push_dir * growth * falloff
                    was_affected = True

            if was_affected:
                new_world_pos = world_pos + push
                target_data[i].co = world_inv @ new_world_pos
                total_affected += 1
            else:
                # If using a shape key, copy the clean coordinate over 
                # so unaffected vertices don't inherit old garbage data.
                if mesh.shape_keys:
                    target_data[i].co = vert.co.copy()

        # Tell Blender the mesh data changed so it redraws
        mesh.update()

    # Store the count so the panel can display it as a status line
    scene["_fascia_flex_affected"] = total_affected


# ─────────────────────────────────────────────────────────────────
# HELPER: Create a muscle-shaped mesh between two 3D points
# ─────────────────────────────────────────────────────────────────
# How it works:
#   1. Creates a small sphere
#   2. Stretches it into a long, thin ellipsoid in LOCAL space
#      (Z axis = muscle length, X/Y = muscle thickness)
#   3. Uses OBJECT transforms (location + rotation) to position
#      and orient the muscle in the scene
#
# Why object transforms instead of baking into geometry?
#   Because the Flex slider needs to scale muscles fatter (X/Y)
#   without making them longer (Z). If the rotation were baked
#   into the vertices, Blender's object.scale couldn't tell
#   which direction is "fat" vs "long". With object rotation,
#   scale[0] and scale[1] always mean "thickness" and scale[2]
#   always means "length", regardless of how the muscle is
#   oriented in the scene.
# ─────────────────────────────────────────────────────────────────

def create_muscle_mesh(name, point1, point2, radius=0.04):
    """Build a muscle-shaped mesh (stretched sphere) between two 3D points."""
    p1 = mathutils.Vector(point1)
    p2 = mathutils.Vector(point2)
    direction = p2 - p1
    length = direction.length

    # If the two points are basically on top of each other, skip
    if length < 0.001:
        return None

    bm = bmesh.new()

    # Step 1: Make a sphere (12 segments around, 6 rings top-to-bottom)
    bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=6, radius=1.0)

    # Step 2: Squash it in LOCAL space — thin on X/Y (thickness), long on Z (length).
    # This stays baked into the geometry so the base shape is correct.
    scale_mat = mathutils.Matrix.Diagonal((radius, radius, length / 2.0, 1.0))
    bmesh.ops.transform(bm, matrix=scale_mat, verts=bm.verts)

    # NOTE: We do NOT rotate or translate the geometry here.
    # Instead, we'll set the object's location and rotation below.
    # This is what makes flex scaling work correctly.

    # Convert bmesh into a real Blender mesh object
    mesh_data = bpy.data.meshes.new(name)
    bm.to_mesh(mesh_data)
    mesh_data.update()
    bm.free()

    obj = bpy.data.objects.new(name, mesh_data)
    bpy.context.collection.objects.link(obj)

    # Step 3: Position the muscle at the midpoint between the two landmarks
    midpoint = (p1 + p2) / 2.0
    obj.location = midpoint

    # Step 4: Rotate the muscle so its local Z axis (the long axis)
    # points along the line between the two landmarks.
    # We use quaternion rotation because it handles all orientations
    # without the "gimbal lock" problem that Euler angles can have.
    z_up = mathutils.Vector((0, 0, 1))
    rotation = z_up.rotation_difference(direction.normalized())
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rotation

    # Smooth shading so muscles look rounded, not faceted
    for poly in mesh_data.polygons:
        poly.use_smooth = True

    return obj


# This class defines WHAT HAPPENS when the "Make Placeholder Horse" button is clicked.
class FASCIA_OT_make_placeholder_horse(bpy.types.Operator):
    bl_idname = "fascia.make_placeholder_horse"
    bl_label = "Make Placeholder Horse"
    bl_description = "Adds a rough placeholder shape where a real horse will go later"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Clear any saved vertex backups from a previous horse,
        # since the old mesh data is no longer valid.
        _original_verts.clear()

        # Create the Body: a stretched sphere
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 1))
        body = context.active_object
        body.name = "Fascia_Horse_Body"
        body.scale = (1.8, 0.9, 0.9)

        # Create the Head: a smaller sphere out front
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(2.2, 0, 1.3))
        head = context.active_object
        head.name = "Fascia_Horse_Head"

        # Apply the current slider values to the horse objects we just created
        # so they match the sliders immediately.
        update_horse(None, context)

        self.report({'INFO'}, "Placeholder horse created")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────
# TOOL 3: PLACE LANDMARKS
# ─────────────────────────────────────────────────────────────────
# Places small yellow marker spheres (Blender "Empties") at key
# anatomical points on the horse. These mark where muscles will
# attach. Bilateral landmarks are placed on both left and right.
# ─────────────────────────────────────────────────────────────────

class FASCIA_OT_place_landmarks(bpy.types.Operator):
    bl_idname = "fascia.place_landmarks"
    bl_label = "Place Landmarks"
    bl_description = "Place anatomical landmark points on the horse"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Check that the placeholder horse exists
        body = bpy.data.objects.get("Fascia_Horse_Body")
        if not body:
            self.report({'ERROR'}, "No horse found — create one first")
            return {"CANCELLED"}

        # Clean up any previously placed landmarks so we don't get duplicates
        old_landmarks = [obj for obj in bpy.data.objects
                         if obj.get("fascia_type") == "landmark"]
        for obj in old_landmarks:
            bpy.data.objects.remove(obj, do_unlink=True)

        placed_count = 0

        for name, data in HORSE_LANDMARKS.items():
            x, y, z = data["pos"]
            is_bilateral = data["bilateral"]
            region = data["region"]

            if is_bilateral:
                # Create left side (_L) and right side (_R, with Y flipped)
                for suffix, y_mult in (("_L", 1.0), ("_R", -1.0)):
                    empty_name = "Fascia_LM_" + name + suffix
                    empty = bpy.data.objects.new(empty_name, None)
                    empty.location = (x, y * y_mult, z)
                    empty.empty_display_size = 0.05
                    empty.empty_display_type = 'SPHERE'
                    empty.color = (1.0, 1.0, 0.0, 1.0)  # Yellow
                    empty.show_in_front = True
                    empty["fascia_type"] = "landmark"
                    empty["fascia_region"] = region
                    empty["fascia_landmark"] = name
                    empty["fascia_side"] = suffix.strip("_")
                    bpy.context.collection.objects.link(empty)

                    # Parent to horse body so everything moves together
                    empty.parent = body
                    empty.matrix_parent_inverse = body.matrix_world.inverted()

                    placed_count += 1
            else:
                # Single midline landmark (centre of the body)
                empty_name = "Fascia_LM_" + name
                empty = bpy.data.objects.new(empty_name, None)
                empty.location = (x, y, z)
                empty.empty_display_size = 0.05
                empty.empty_display_type = 'SPHERE'
                empty.color = (1.0, 1.0, 0.0, 1.0)  # Yellow
                empty.show_in_front = True
                empty["fascia_type"] = "landmark"
                empty["fascia_region"] = region
                empty["fascia_landmark"] = name
                empty["fascia_side"] = "mid"
                bpy.context.collection.objects.link(empty)

                # Parent to horse body so everything moves together
                empty.parent = body
                empty.matrix_parent_inverse = body.matrix_world.inverted()

                placed_count += 1

        # Make sure Blender recalculates all object positions
        context.view_layer.update()

        self.report({'INFO'}, str(placed_count) + " landmarks placed")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────
# TOOL 4: GENERATE MUSCLES
# ─────────────────────────────────────────────────────────────────
# Reads the placed landmark positions and creates coloured,
# elongated muscle shapes stretched between them.
# If either end of a muscle is a bilateral landmark, the muscle
# is created on both left and right sides automatically.
# ─────────────────────────────────────────────────────────────────

class FASCIA_OT_generate_muscles(bpy.types.Operator):
    bl_idname = "fascia.generate_muscles"
    bl_label = "Generate Muscles"
    bl_description = "Generate muscle shapes between the placed landmarks"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Check that landmarks exist first
        has_landmarks = any(obj.get("fascia_type") == "landmark"
                           for obj in bpy.data.objects)
        if not has_landmarks:
            self.report({'ERROR'}, "No landmarks found — place landmarks first")
            return {"CANCELLED"}

        # Clean up any previously generated muscles so we don't get duplicates
        old_muscles = [obj for obj in bpy.data.objects
                       if obj.get("fascia_type") == "muscle"]
        for obj in old_muscles:
            mesh_data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            # Also remove the mesh data if nothing else uses it
            if mesh_data and mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data)

        # Clean up leftover muscle materials
        for mat in list(bpy.data.materials):
            if mat.name.startswith("Fascia_Mat_") and mat.users == 0:
                bpy.data.materials.remove(mat)

        muscle_count = 0

        for muscle_name, mdata in HORSE_MUSCLES.items():
            from_key = mdata["from"]
            to_key = mdata["to"]
            from_bilateral = HORSE_LANDMARKS[from_key]["bilateral"]
            to_bilateral = HORSE_LANDMARKS[to_key]["bilateral"]

            needs_mirror = from_bilateral or to_bilateral

            if needs_mirror:
                # Create left (_L) and right (_R) versions of this muscle
                for suffix in ("_L", "_R"):
                    # Build the landmark names for this side
                    if from_bilateral:
                        from_obj_name = "Fascia_LM_" + from_key + suffix
                    else:
                        from_obj_name = "Fascia_LM_" + from_key

                    if to_bilateral:
                        to_obj_name = "Fascia_LM_" + to_key + suffix
                    else:
                        to_obj_name = "Fascia_LM_" + to_key

                    from_obj = bpy.data.objects.get(from_obj_name)
                    to_obj = bpy.data.objects.get(to_obj_name)

                    if not from_obj or not to_obj:
                        continue  # Landmark is missing, skip

                    # Read the landmark world positions
                    p1 = from_obj.matrix_world.translation.copy()
                    p2 = to_obj.matrix_world.translation.copy()

                    obj_name = "Fascia_Muscle_" + muscle_name + suffix
                    obj = create_muscle_mesh(obj_name, p1, p2, mdata["radius"])

                    if obj is None:
                        continue

                    # Apply colour via a material
                    mat = bpy.data.materials.new(
                        name="Fascia_Mat_" + muscle_name + suffix
                    )
                    mat.use_nodes = False
                    mat.diffuse_color = mdata["color"]
                    obj.data.materials.append(mat)

                    # Store metadata for later identification
                    obj["fascia_type"] = "muscle"
                    obj["fascia_muscle_name"] = muscle_name
                    obj["fascia_origin"] = from_obj_name
                    obj["fascia_insertion"] = to_obj_name
                    # Store the muscle's base thickness so the flex
                    # slider knows how much each muscle should push the skin
                    obj["fascia_radius"] = mdata["radius"]

                    muscle_count += 1
            else:
                # Both landmarks are midline — create one muscle, no mirroring
                from_obj = bpy.data.objects.get("Fascia_LM_" + from_key)
                to_obj = bpy.data.objects.get("Fascia_LM_" + to_key)

                if not from_obj or not to_obj:
                    continue

                p1 = from_obj.matrix_world.translation.copy()
                p2 = to_obj.matrix_world.translation.copy()

                obj_name = "Fascia_Muscle_" + muscle_name
                obj = create_muscle_mesh(obj_name, p1, p2, mdata["radius"])

                if obj is None:
                    continue

                mat = bpy.data.materials.new(name="Fascia_Mat_" + muscle_name)
                mat.use_nodes = False
                mat.diffuse_color = mdata["color"]
                obj.data.materials.append(mat)

                obj["fascia_type"] = "muscle"
                obj["fascia_muscle_name"] = muscle_name
                obj["fascia_origin"] = "Fascia_LM_" + from_key
                obj["fascia_insertion"] = "Fascia_LM_" + to_key
                obj["fascia_radius"] = mdata["radius"]

                muscle_count += 1

        # If the Flex slider is currently above zero, recalculate
        # the skin deformation with the newly generated muscles
        update_flex(None, context)

        self.report({'INFO'}, str(muscle_count) + " muscles generated")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────
# TOOL 6: SIMULATE MOTION
# ─────────────────────────────────────────────────────────────────
# Creates a simple deterministic test animation over frames 1 to 60.
# Animates scene.fascia_flex using keyframes.
# ─────────────────────────────────────────────────────────────────

class FASCIA_OT_simulate_motion(bpy.types.Operator):
    bl_idname = "fascia.simulate_motion"
    bl_label = "Simulate Motion"
    bl_description = "Create a 60-frame flex test animation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene

        scene.frame_start = 1
        scene.frame_end = 60

        keyframes = [
            (1, 0.0),
            (15, 1.0),
            (30, 0.0),
            (45, 1.0),
            (60, 0.0)
        ]

        for frame, val in keyframes:
            scene.frame_set(frame)
            scene.fascia_flex = val
            scene.keyframe_insert(data_path="fascia_flex", frame=frame)
            update_flex(None, context)

        scene.frame_set(1)

        self.report({'INFO'}, "Motion simulation created: 60 frames")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────
# TOOL 7: BAKE RESULT
# ─────────────────────────────────────────────────────────────────
# Bakes the 60-frame simulated flex animation into reusable shape keys.
# Ensures the original unflexed shape is preserved as the "Basis" key.
# ─────────────────────────────────────────────────────────────────

class FASCIA_OT_bake_flex_pose(bpy.types.Operator):
    bl_idname = "fascia.bake_flex_pose"
    bl_label = "Bake Result"
    bl_description = "Bake the simulated flex animation into reusable shape keys"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        skin_objects = []
        body = bpy.data.objects.get("Fascia_Horse_Body")
        head = bpy.data.objects.get("Fascia_Horse_Head")
        if body and body.data:
            skin_objects.append(body)
        if head and head.data:
            skin_objects.append(head)

        if not skin_objects:
            self.report({'ERROR'}, "No horse meshes found to bake.")
            return {"CANCELLED"}

        frames_to_bake = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
        frames_saved = 0

        for frame in frames_to_bake:
            context.scene.frame_set(frame)
            update_flex(None, context)
            flex_val = context.scene.fascia_flex

            for obj in skin_objects:
                mesh = obj.data

                # Ensure "Basis" exists and is perfectly clean
                if not mesh.shape_keys:
                    _restore_original_verts(obj)
                    obj.shape_key_add(name="Basis")

                # Read current flexed positions
                if flex_val < 0.001:
                    flexed_verts = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]
                elif mesh.shape_keys and "Live_Flex" in mesh.shape_keys.key_blocks:
                    flexed_verts = [(v.co.x, v.co.y, v.co.z) for v in mesh.shape_keys.key_blocks["Live_Flex"].data]
                else:
                    flexed_verts = [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices]

                # Create or get shape key for this frame
                pose_name = f"Baked_Frame_{frame:03d}"
                if pose_name in mesh.shape_keys.key_blocks:
                    new_key = mesh.shape_keys.key_blocks[pose_name]
                else:
                    new_key = obj.shape_key_add(name=pose_name)
                
                # Write the flexed positions DIRECTLY into the shape key's data
                for i, (x, y, z) in enumerate(flexed_verts):
                    new_key.data[i].co.x = x
                    new_key.data[i].co.y = y
                    new_key.data[i].co.z = z
            
            frames_saved += 1

        # Return to start frame
        context.scene.frame_set(1)

        self.report({'INFO'}, f"Bake complete: {frames_saved} frames saved")
        return {"FINISHED"}


# This class defines the PANEL - the sidebar panel in Blender where the buttons and sliders live.
class FASCIA_PT_main_panel(bpy.types.Panel):
    bl_label = "Fascia"
    bl_idname = "FASCIA_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fascia"  # This is the name of the tab in the sidebar

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Fascia - Creature Generator")
        
        # Draw the button to create the horse
        layout.operator("fascia.make_placeholder_horse", icon="MESH_MONKEY")
        
        # Add a visual separator line
        layout.separator()
        
        # Draw the settings label and sliders
        layout.label(text="Horse Settings:")
        
        # Age slider (0.0 to 1.0)
        layout.prop(scene, "fascia_age", text="Age", slider=True)
        
        # Fat slider (0.0 to 1.0)
        layout.prop(scene, "fascia_fat", text="Fat", slider=True)
        
        # Color picker
        layout.prop(scene, "fascia_color", text="Color")

        # ── Anatomy section (Tool 3 & Tool 4) ────────────────
        layout.separator()
        layout.label(text="Anatomy:")

        # Buttons to place landmarks and generate muscles
        layout.operator("fascia.place_landmarks", icon="EMPTY_DATA")
        layout.operator("fascia.generate_muscles", icon="MESH_UVSPHERE")

        # Show a count of how many landmarks and muscles currently exist
        lm_count = sum(1 for obj in bpy.data.objects
                       if obj.get("fascia_type") == "landmark")
        muscle_count = sum(1 for obj in bpy.data.objects
                          if obj.get("fascia_type") == "muscle")
        if lm_count > 0 or muscle_count > 0:
            row = layout.row()
            row.label(text="Landmarks: " + str(lm_count))
            row.label(text="Muscles: " + str(muscle_count))

        # ── Simulation section (Tool 5) ───────────────────────
        layout.separator()
        layout.label(text="Simulation:")

        # Flex slider — controls muscle bulge and skin deformation
        layout.prop(scene, "fascia_flex", text="Flex", slider=True)

        # Show how many skin vertices are being affected by the flex
        flex_val = scene.fascia_flex
        if flex_val > 0.001:
            affected = scene.get("_fascia_flex_affected", 0)
            layout.label(text="Skin bound: " + str(affected) + " vertices affected")

        layout.separator()
        
        # Button to create a 60-frame flex test animation
        layout.operator("fascia.simulate_motion", icon="ACTION")

        # Button to bake the flex animation into Shape Keys
        layout.operator("fascia.bake_flex_pose", text="Bake Result", icon="SHAPEKEY_DATA")


# A list of classes that Blender needs to register/load when enabling this add-on
classes = (
    FASCIA_OT_make_placeholder_horse,
    FASCIA_OT_place_landmarks,
    FASCIA_OT_generate_muscles,
    FASCIA_OT_simulate_motion,
    FASCIA_OT_bake_flex_pose,
    FASCIA_PT_main_panel,
)


def register():
    # Register all our panel and operator classes
    for cls in classes:
        bpy.utils.register_class(cls)

    # Register our custom Scene properties so Blender knows they exist
    # These properties store the slider values.
    
    # Age Property: goes from 0.0 to 1.0. When changed, it runs 'update_horse'
    bpy.types.Scene.fascia_age = bpy.props.FloatProperty(
        name="Age",
        description="Older = slightly different proportions (smaller head)",
        default=0.5,
        min=0.0,
        max=1.0,
        update=update_horse
    )

    # Fat Property: goes from 0.0 to 1.0. When changed, it runs 'update_horse'
    bpy.types.Scene.fascia_fat = bpy.props.FloatProperty(
        name="Fat",
        description="Fatter = wider and taller, not longer",
        default=0.5,
        min=0.0,
        max=1.0,
        update=update_horse
    )

    # Color Property: holds 3 numbers (Red, Green, Blue) for the color picker
    bpy.types.Scene.fascia_color = bpy.props.FloatVectorProperty(
        name="Color",
        description="Viewport display color of the horse",
        subtype='COLOR',
        default=(0.8, 0.8, 0.8),
        min=0.0,
        max=1.0,
        size=3,
        update=update_horse
    )

    # Flex Property: controls how much the muscles bulge and the skin deforms.
    # At 0.0 = relaxed (no deformation).
    # At 1.0 = fully flexed (muscles are 50% fatter, skin bulges over them).
    # When this slider changes, it runs 'update_flex' which does all the
    # muscle scaling and skin vertex pushing automatically.
    bpy.types.Scene.fascia_flex = bpy.props.FloatProperty(
        name="Flex",
        description="How much the muscles flex — higher = bigger muscles and more skin bulge",
        default=0.0,
        min=0.0,
        max=1.0,
        update=update_flex
    )


def unregister():
    # Unregister our panel and operator classes
    for cls in classes:
        bpy.utils.unregister_class(cls)

    # Remove the custom Scene properties so we don't leave clutter behind
    del bpy.types.Scene.fascia_age
    del bpy.types.Scene.fascia_fat
    del bpy.types.Scene.fascia_color
    del bpy.types.Scene.fascia_flex

    # Clear the saved vertex backups
    _original_verts.clear()


if __name__ == "__main__":
    register()
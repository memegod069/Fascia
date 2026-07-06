bl_info = {
    "name": "Fascia",
    "author": "Fascia contributors",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Fascia",
    "description": "Fascia creature soft-tissue toolbox — landmarks, muscles, skin binding, flex baking",
    "category": "Add Mesh",
}

import bpy
import bmesh
import mathutils
import json
import os


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


# Issue 1 fix: invalidate the vertex cache when the user edits or
# sculpts a skin mesh, so manual sculpting survives subsequent flex
# updates. Without this, _original_verts silently holds the
# pre-sculpt positions and _restore_original_verts writes them back,
# erasing the user's work the next time Flex moves.
#
# A single depsgraph_update_post handler covers both Edit mode and
# Sculpt/Texture/Vertex/Weight paint modes. Blender fires
# is_updated_geometry on the active object when entering Edit mode
# and on every sculpt stroke, with bpy.context.object.mode reporting
# the current non-OBJECT mode at that moment. Flex updates always
# run in OBJECT mode, so they never trigger invalidation — no flag
# or timing guard is needed.
#
# (Note: bpy.app.handlers.edit_mode_update does not exist in
# Blender 5.1, so we rely on depsgraph_update_post alone.)

@bpy.app.handlers.persistent
def _fascia_invalidate_on_depsgraph(scene, depsgraph):
    if not _original_verts:
        return
    active = bpy.context.object
    # Skip in OBJECT mode — that is where flex updates run, and they
    # must not invalidate the cache they just wrote.
    if active is None or active.mode == 'OBJECT':
        return
    # Map mesh NAME → cached object names that use it. Keying by name
    # (a stable string) instead of by the Mesh datablock reference is
    # required because update.id inside a depsgraph callback is a
    # different Python wrapper than bpy.data.objects[*].data and does
    # not hash-match the persistent reference.
    cached_mesh_name_to_obj_names = {}
    for obj in bpy.data.objects:
        if obj.name in _original_verts and obj.type == 'MESH' and obj.data:
            cached_mesh_name_to_obj_names.setdefault(obj.data.name, []).append(obj.name)
    if not cached_mesh_name_to_obj_names:
        return
    for update in depsgraph.updates:
        if not update.is_updated_geometry:
            continue
        uid = update.id
        # update.id may be the Mesh datablock or an Object referencing it.
        if isinstance(uid, bpy.types.Mesh):
            mesh_name = uid.name
        elif isinstance(uid, bpy.types.Object) and uid.type == 'MESH' and uid.data:
            mesh_name = uid.data.name
        else:
            continue
        names = cached_mesh_name_to_obj_names.get(mesh_name)
        if names:
            for name in names:
                _original_verts.pop(name, None)


# ─────────────────────────────────────────────────────────────────
# HELPERS: Find the base skin mesh(es)
# ─────────────────────────────────────────────────────────────────
# The pipeline needs to know which object(s) are the creature's skin.
# A user can tag ANY mesh as the base by clicking "Use Selected as Base".
# If nothing is tagged, we fall back to the default placeholder names.
# ─────────────────────────────────────────────────────────────────

def _get_skin_objects():
    """Return all mesh objects tagged as Fascia skin, or fall back to defaults."""
    tagged = [obj for obj in bpy.data.objects
              if obj.get("fascia_role") == "skin" and obj.type == 'MESH']
    if tagged:
        return tagged
    # Fallback to default placeholder names
    result = []
    for name in ("Fascia_Horse_Body", "Fascia_Horse_Head"):
        obj = bpy.data.objects.get(name)
        if obj and obj.data:
            result.append(obj)
    return result


def _get_base_mesh():
    """Return the primary base mesh, or None."""
    skins = _get_skin_objects()
    return skins[0] if skins else None


def _get_base_bounds(obj):
    """Return ((min_x, min_y, min_z), (max_x, max_y, max_z)) in world space."""
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    min_x = min(c.x for c in corners)
    min_y = min(c.y for c in corners)
    min_z = min(c.z for c in corners)
    max_x = max(c.x for c in corners)
    max_y = max(c.y for c in corners)
    max_z = max(c.z for c in corners)
    return ((min_x, min_y, min_z), (max_x, max_y, max_z))


def _get_base_size(obj):
    """Return a single characteristic size for the base mesh:
    the longest side of its world-space bounding box.
    Used to scale muscle radii and influence radius so they are
    proportional on a mesh of any absolute scale."""
    (min_x, min_y, min_z), (max_x, max_y, max_z) = _get_base_bounds(obj)
    return max(max_x - min_x, max_y - min_y, max_z - min_z)


def _load_species(filepath):
    """Load a species-definition JSON file and return
    (landmarks_dict, muscles_dict, species_name).

    The file must have 'landmarks' and 'muscles' keys.
    Returns (None, None, None) on error (file missing,
    invalid JSON, or missing required keys) — the
    caller falls back to embedded HORSE_* data.

    Species files let external LLMs define any
    creature's anatomy as the muscle TD (rule 10/11).
    The horse is the first data file, not the only one.

    KNOWN LIMITATION: Only structural validation
    (required keys exist). Individual entries are
    not validated — bad data surfaces as key errors
    at the operator level.
    """
    # Resolve Blender-relative paths (starting with //) to absolute paths.
    # bpy.path.abspath handles // correctly; os.path.isfile does not.
    abs_path = bpy.path.abspath(filepath)
    if not os.path.isfile(abs_path):
        print("Fascia: species file not found: " + abs_path)
        return None, None, None
    filepath = abs_path

    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except Exception as e:
        print("Fascia: error reading species file: " + str(e))
        return None, None, None

    if "landmarks" not in data or "muscles" not in data:
        print("Fascia: species file missing 'landmarks' or 'muscles' key")
        return None, None, None

    return data["landmarks"], data["muscles"], data.get("name", "Unknown")


def _load_species_json(json_str):
    """Parse a species-definition JSON string and return
    (landmarks_dict, muscles_dict, species_name).

    Spec 9: the LLM-facing inline-anatomy path. Same schema and
    same return contract as _load_species (Spec 6), but the
    anatomy is passed as a string property (scene.fascia_species_json)
    instead of read from a file. No file IO - the LLM sets the
    property and calls place_landmarks / generate_muscles.

    Returns (None, None, None) on error (invalid JSON or missing
    required keys) - the caller falls back to embedded HORSE_* data.
    """
    try:
        data = json.loads(json_str)
    except Exception as e:
        print("Fascia: error parsing species JSON string: " + str(e))
        return None, None, None

    if "landmarks" not in data or "muscles" not in data:
        print("Fascia: species JSON string missing 'landmarks' or 'muscles' key")
        return None, None, None

    return data["landmarks"], data["muscles"], data.get("name", "Unknown")


def _validate_species_data(landmarks_data, muscles_data, context_label="species"):
    """Validate species landmark and muscle dicts before any scene modification.

    Checks that:
    - Every landmark has a 'pos' key with a 3-element list.
    - Every muscle has 'from', 'to', and 'radius' keys.
    - Every muscle's 'from' and 'to' reference a known landmark name.
    - Colors (if present) have 3 or 4 elements (auto-pads 3-element colors to RGBA).

    Returns (errors, warnings) where each is a list of strings.
    errors = problems that should abort the operation.
    warnings = problems that are auto-corrected or non-fatal.
    """
    errors = []
    warnings = []

    # Validate landmarks
    for name, data in landmarks_data.items():
        pos = data.get("pos")
        if pos is None:
            errors.append(f"{context_label}: landmark '{name}' missing 'pos' key")
        elif not isinstance(pos, (list, tuple)) or len(pos) != 3:
            errors.append(f"{context_label}: landmark '{name}' 'pos' must be a 3-element list")

    # Validate muscles
    known_landmarks = set(landmarks_data.keys())
    for name, data in muscles_data.items():
        for key in ("from", "to", "radius"):
            if key not in data:
                errors.append(f"{context_label}: muscle '{name}' missing '{key}' key")
        from_key = data.get("from", "")
        to_key = data.get("to", "")
        if from_key and from_key not in known_landmarks:
            errors.append(f"{context_label}: muscle '{name}' 'from' references unknown landmark '{from_key}'")
        if to_key and to_key not in known_landmarks:
            errors.append(f"{context_label}: muscle '{name}' 'to' references unknown landmark '{to_key}'")
        color = data.get("color")
        if color is not None:
            if len(color) == 3:
                data["color"] = list(color) + [1.0]
                warnings.append(f"{context_label}: muscle '{name}' color auto-padded to RGBA")
            elif len(color) != 4:
                errors.append(f"{context_label}: muscle '{name}' 'color' must be 3 or 4 elements")

    return errors, warnings


# ─────────────────────────────────────────────────────────────────
# RIG-BINDING HELPERS (Spec 7)
# ─────────────────────────────────────────────────────────────────
# These helpers wire landmarks to armature bones and muscles to
# landmarks, so the whole soft-tissue stack follows the skeleton.
# The chain: bone → landmark (bone parent) → muscle (object parent)
# → skin bulge (world-transform read via depsgraph).
# ─────────────────────────────────────────────────────────────────

def _find_nearest_bone(armature, world_point):
    """Find the bone in armature whose segment (head→tail) is
    closest to world_point. Returns (bone_name, distance) or
    (None, inf) if the armature has no bones.

    Used by the auto-bind operator (Spec 7) to pick a bone for
    each landmark when the LLM has not set fascia_bone explicitly.
    """
    bones = armature.data.bones
    if not bones:
        return None, float('inf')

    pt = mathutils.Vector(world_point)
    best_name = None
    best_dist = float('inf')
    arm_mat = armature.matrix_world

    for bone in bones:
        head_w = arm_mat @ bone.head_local
        tail_w = arm_mat @ bone.tail_local
        seg = tail_w - head_w
        seg_len_sq = seg.length_squared
        if seg_len_sq < 1e-12:
            d = (head_w - pt).length
        else:
            t = ((pt - head_w).dot(seg)) / seg_len_sq
            t = max(0.0, min(1.0, t))
            closest = head_w + seg * t
            d = (closest - pt).length
        if d < best_dist:
            best_dist = d
            best_name = bone.name

    return best_name, best_dist


def _bone_parent_object(empty, armature, bone_name):
    """Bone-parent empty to bone_name on armature, preserving
    the empty's current world position (keep_transform=True).

    Sets armature.data.bones.active before calling parent_set
    so the operator knows which bone to parent to, then restores
    the original active bone.

    Sets empty['fascia_bone'] = bone_name as metadata.
    Returns True on success, False on failure.
    """
    if bone_name not in armature.data.bones:
        return False

    old_active = armature.data.bones.active
    armature.data.bones.active = armature.data.bones[bone_name]

    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    empty.select_set(True)
    bpy.context.view_layer.objects.active = armature

    with bpy.context.temp_override(
        active_object=armature,
        selected_editable_objects=[armature, empty],
        object=armature,
    ):
        bpy.ops.object.parent_set(type='BONE', keep_transform=True)

    armature.data.bones.active = old_active
    empty["fascia_bone"] = bone_name
    return True


def _object_parent_object(child, parent):
    """Object-parent child to parent, preserving child's world
    transform (keep_transform=True). Used to parent muscles to
    their origin landmark (Spec 7)."""
    bpy.ops.object.select_all(action='DESELECT')
    parent.select_set(True)
    child.select_set(True)
    bpy.context.view_layer.objects.active = parent

    with bpy.context.temp_override(
        view_layer=bpy.context.view_layer,
        active_object=parent,
        selected_editable_objects=[parent, child],
        object=parent,
    ):
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)


def _add_insertion_track_constraint(muscle, insertion_obj):
    """Add a Damped Track constraint on the muscle so its local +Z
    (length axis, origin->insertion) points at the insertion landmark.

    Spec 8: closes the 'wrong angle at insertion' gap from Spec 7 section 7.
    Damped Track is rotation-only - it does not touch obj.scale, so
    the volume-preserving contraction (obj.scale = (ts, ts, ls)) is
    unaffected. Stretch To would override scale and break volume
    preservation; rejected (Spec 8 section 2a).

    The constraint is added at generation time and is always on.
    At rest it is a no-op visually: the muscle already points at the
    insertion (create_muscle_mesh Step 4), so the constraint's first
    evaluation produces the same rotation. When the insertion landmark
    moves (rig pose changes), the muscle reorients to follow.

    KNOWN LIMITATION: The muscle's far end is at rest_length*ls along
    the reoriented direction - it does NOT stretch to exactly reach the
    insertion. If the insertion moved closer than rest_length*ls, the
    far end overshoots; if farther, it undershoots. This is the
    pre-existing Spec 4 insertion length-mismatch; Spec 8 fixes the
    ANGLE, not the length. Anatomically honest for a geometric
    contraction model (Fascia is not FEM, rule 13).
    """
    con = muscle.constraints.new(type='DAMPED_TRACK')
    con.name = "Fascia_DampedTrack_Insertion"
    con.target = insertion_obj
    con.track_axis = 'TRACK_Z'
    return con


def _clear_skin_tags():
    """Remove the skin role tag from all objects."""
    for obj in bpy.data.objects:
        if obj.get("fascia_role") == "skin":
            del obj["fascia_role"]


# ─────────────────────────────────────────────────────────────────
# HORSE LANDMARK DEFINITIONS
# ─────────────────────────────────────────────────────────────────
# Each entry has:
#   pos       – normalized (U, V, W) coordinate where each axis is 0.0–1.0
#               (U = X, V = Y, W = Z), mapped to the base mesh's
#               world-space bounding box at placement time.
#                 U = 0.0  rearmost point of the mesh (tail/buttock)
#                 U = 1.0  frontmost point of the mesh (nose tip)
#                 V = 0.5  midline (bilateral entries store LEFT-side V;
#                           right side is auto-created as 1.0 - V)
#                 W = 0.0  lowest point of the mesh (ground / bottom of hooves)
#                 W = 1.0  highest point of the mesh (top of withers / poll)
#   bilateral – True if it exists on both left and right sides of the horse
#   region    – which body area it belongs to (for organisation)
#
# POSE ASSUMPTION (KNOWN LIMITATION):
#   Values are calibrated for a horse standing four-square (neutral
#   reference pose) with the head carried at roughly wither height.
#   They are dimensionless fractions and apply to any horse mesh of
#   any absolute size, AS LONG AS the mesh is in or near this pose.
#   Extreme poses will misplace landmarks:
#     - Grazing (head down): head landmarks (Poll, NuchalCrest) land
#       too high; front-vs-rear U values still hold.
#     - Rearing / head well above withers: head landmarks land too low.
#     - Galloping / extended limbs: limb landmarks (Knee, Hock, Fetlock
#       if added later) no longer line up with the bounding-box edges.
#   This is a fundamental limit of bounding-box landmarking and is
#   expected to be addressed by surface- or skeleton-driven placement
#   in a future work item. Do NOT per-mesh-tune these values to mask it.
# ─────────────────────────────────────────────────────────────────

HORSE_LANDMARKS = {
    # Head & Neck (midline)
    "Poll":            {"pos": (0.840, 0.500, 0.920), "bilateral": False, "region": "head"},
    # RESERVED: NuchalCrest — future neck muscle attachment (no muscle assigned yet).
    "NuchalCrest":     {"pos": (0.825, 0.500, 0.880), "bilateral": False, "region": "neck"},

    # Shoulder & Forelimb
    "Withers":         {"pos": (0.640, 0.500, 0.980), "bilateral": False, "region": "back"},
    "ScapulaTop":      {"pos": (0.660, 0.670, 0.920), "bilateral": True,  "region": "shoulder"},
    "PointOfShoulder": {"pos": (0.700, 0.720, 0.780), "bilateral": True,  "region": "shoulder"},
    "Elbow":           {"pos": (0.680, 0.650, 0.530), "bilateral": True,  "region": "forelimb"},
    # RESERVED: FrontKnee — future cannon-bone muscle attachment (bilateral; no muscle yet).
    "FrontKnee":       {"pos": (0.660, 0.630, 0.430), "bilateral": True,  "region": "forelimb"},

    # Trunk / Torso (midline)
    "Chest":           {"pos": (0.580, 0.500, 0.420), "bilateral": False, "region": "chest"},
    "MidBack":         {"pos": (0.500, 0.500, 0.950), "bilateral": False, "region": "back"},
    # RESERVED: BellyMid — future abdominal muscle attachment (no muscle assigned yet).
    "BellyMid":        {"pos": (0.450, 0.500, 0.380), "bilateral": False, "region": "belly"},

    # Hip & Hindlimb
    "PointOfHip":      {"pos": (0.320, 0.750, 0.780), "bilateral": True,  "region": "hip"},
    "PointOfCroup":    {"pos": (0.240, 0.500, 0.930), "bilateral": False, "region": "hip"},
    "PointOfButtock":  {"pos": (0.080, 0.680, 0.730), "bilateral": True,  "region": "hip"},
    "HipJoint":        {"pos": (0.300, 0.620, 0.660), "bilateral": True,  "region": "hip"},
    "Stifle":          {"pos": (0.260, 0.700, 0.670), "bilateral": True,  "region": "hindlimb"},
    "Hock":            {"pos": (0.200, 0.680, 0.470), "bilateral": True,  "region": "hindlimb"},

    # Internal anchor points (hidden attachment sites inside the body)
    "SerratusAnchor":  {"pos": (0.660, 0.580, 0.500), "bilateral": True,  "region": "shoulder"},
    "LatAnchor":       {"pos": (0.650, 0.680, 0.360), "bilateral": True,  "region": "forelimb"},
}


# ─────────────────────────────────────────────────────────────────
# HORSE MUSCLE DEFINITIONS
# ─────────────────────────────────────────────────────────────────
# Each muscle stretches between two landmark points.
#   from   – the origin landmark name (must match a key in HORSE_LANDMARKS)
#   to     – the insertion landmark name
#   radius – how thick the muscle shape is, as a FRACTION of the base
#            mesh's longest bounding-box side (mesh-agnostic scaling)
#   color  – viewport display colour (Red, Green, Blue, Alpha)
#
# Front-body muscles use warm reds/oranges.
# Rear-body muscles use cool blues/purples.
#
# Fractions computed from the previous hardcoded Blender-unit values
# (divided by the reference length 3.6 and rounded to 3 decimals).
# On a 3.6-unit mesh they produce identical output.
# ─────────────────────────────────────────────────────────────────

# Fraction of the base mesh's longest bounding-box side that a muscle's
# skin-bulge influence reaches. ~8.3% reproduces the old 0.3-unit radius
# on a 3.6-unit-long mesh. Tunable.
MUSCLE_INFLUENCE_FRACTION = 0.083

# Maximum fractional shortening of a muscle at full flex (flex=1).
# Real muscles shorten ~20-30% at peak contraction. Volume is preserved:
# if length drops by (1-c), thickness grows by 1/sqrt(1-c) so that
# pi * r^2 * L stays constant. Tunable.
MAX_CONTRACTION = 0.25

# Fraction of the muscle's axial shortening that is transmitted to nearby
# skin as tangential sliding (Spec 12). 1.0 = full physical sliding (the
# skin follows the muscle surface exactly). < 1.0 = damped sliding (skin
# lags behind the muscle). Tunable; do not tune to a specific mesh.
SKIN_SLIDE_FRACTION = 1.0

HORSE_MUSCLES = {
    # Front body (warm colours)
    "Trapezius":         {"from": "Withers",         "to": "ScapulaTop",      "radius": 0.017, "color": (0.80, 0.20, 0.15, 0.60)},
    "Deltoid":           {"from": "ScapulaTop",      "to": "PointOfShoulder", "radius": 0.014, "color": (0.90, 0.35, 0.10, 0.60), "antagonist": "Pectorals"},
    "Triceps":           {"from": "ScapulaTop",      "to": "Elbow",           "radius": 0.019, "color": (0.70, 0.12, 0.12, 0.60)},
    "BicepsBrachii":     {"from": "PointOfShoulder", "to": "Elbow",           "radius": 0.014, "color": (0.85, 0.45, 0.35, 0.60), "antagonist": "Triceps"},
    "Pectorals":         {"from": "Chest",           "to": "PointOfShoulder", "radius": 0.019, "color": (0.82, 0.30, 0.30, 0.60), "antagonist": "LatissimusDorsi"},
    "SerratusVentralis": {"from": "Chest",           "to": "SerratusAnchor",  "radius": 0.017, "color": (0.78, 0.35, 0.40, 0.60)},
    "LatissimusDorsi":   {"from": "MidBack",         "to": "LatAnchor",       "radius": 0.019, "color": (0.72, 0.22, 0.18, 0.60)},
    "Brachiocephalicus": {"from": "Poll",            "to": "PointOfShoulder", "radius": 0.014, "color": (0.88, 0.50, 0.30, 0.60), "antagonist": "SerratusVentralis"},

    # Spine & torso
    "LongissimusDorsi":  {"from": "Withers",         "to": "PointOfCroup",    "radius": 0.017, "color": (0.65, 0.18, 0.18, 0.60)},
    "RectusAbdominis":   {"from": "Chest",           "to": "PointOfHip",      "radius": 0.014, "color": (0.75, 0.55, 0.40, 0.60), "antagonist": "LongissimusDorsi"},

    # Rear body (cool colours)
    "GluteusMedius":     {"from": "PointOfHip",      "to": "HipJoint",        "radius": 0.028, "color": (0.20, 0.22, 0.78, 0.60)},
    "BicepsFemoris":     {"from": "PointOfButtock",  "to": "Stifle",          "radius": 0.019, "color": (0.30, 0.30, 0.85, 0.60)},
    "Semitendinosus":    {"from": "PointOfButtock",  "to": "Hock",            "radius": 0.017, "color": (0.40, 0.38, 0.75, 0.60), "antagonist": "Quadriceps"},
    "Quadriceps":        {"from": "HipJoint",        "to": "Stifle",          "radius": 0.019, "color": (0.45, 0.25, 0.70, 0.60), "antagonist": "BicepsFemoris"},
    "Gastrocnemius":     {"from": "Stifle",          "to": "Hock",            "radius": 0.014, "color": (0.55, 0.42, 0.78, 0.60)},
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
        col = scene.fascia_color
        body.color = (col[0], col[1], col[2], 1.0)

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
        col = scene.fascia_color
        head.color = (col[0], col[1], col[2], 1.0)


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
    Returns True if restore succeeded, False if the backup is stale.
    """
    if obj.name not in _original_verts:
        return False
    mesh = obj.data
    saved = _original_verts[obj.name]
    if len(saved) != len(mesh.vertices):
        # Topology changed since the backup was made — backup is stale.
        # Discard it so a fresh one gets saved next time.
        del _original_verts[obj.name]
        return False
    for i, (x, y, z) in enumerate(saved):
        mesh.vertices[i].co.x = x
        mesh.vertices[i].co.y = y
        mesh.vertices[i].co.z = z
    return True


# ─────────────────────────────────────────────────────────────────
# TOOL 5: FLEX UPDATE (Bind Skin to Muscles)
# ─────────────────────────────────────────────────────────────────
# This function runs automatically every time the Flex slider moves.
# It does two things:
#
#   1. CONTRACT THE MUSCLES — each muscle shortens along its length
#      and bulges outward (volume-preserving) to simulate contracting.
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

    # ── Step 1: Volume-preserving muscle contraction ──────────
    #
    # Each muscle was built so its local Z axis runs along its length
    # and local X/Y are its thickness (see create_muscle_mesh).
    # A real muscle SHORTENS along its length and BULGES outward when
    # it contracts, keeping its volume constant (muscle tissue is
    # roughly incompressible).
    #   V = pi * r^2 * L  →  if L -> L*(1-c), then r -> r/sqrt(1-c)
    # so volume is preserved. c = flex * MAX_CONTRACTION.
    #
    #   flex = 0  →  length_scale=1.0,  thickness_scale=1.0     (rest)
    #   flex = 1  →  length_scale=0.75, thickness_scale≈1.155   (15.5% thicker, 25% shorter)
    #
    # KNOWN LIMITATION: The insertion end shortens toward the pinned origin
    # during contraction, leaving a gap at the insertion landmark. A real
    # joint would flex and close this gap; Fascia has no rig yet so the gap
    # is the honest static-landmark approximation. Closing it needs skeleton-
    # driven landmarks (future rig work).

    muscles = [obj for obj in bpy.data.objects
               if obj.get("fascia_type") == "muscle"]

    # Per-muscle recruitment (Spec 5). Build a name -> recruitment map
    # from the Scene collection. Empty collection (old scene, or
    # muscles deleted manually) = uniform recruitment (r=1.0 for all),
    # which is identical to pre-Spec-5 behaviour.
    recruitment_map = {}
    for entry in scene.fascia_recruitment:
        recruitment_map[entry.name] = entry.recruitment

    # Per-muscle scale cache: also needed by Step 2 (skin push), so
    # compute it once here and reuse. Each muscle gets its own
    # length_scale_i and thickness_scale_i based on its recruitment.
    muscle_scales = {}  # name -> (length_scale_i, thickness_scale_i)

    # Spec 10: Antagonist relaxation
    # Build a map: muscle_name -> list of muscles that name it as antagonist
    # (the "aggressors"). When an aggressor contracts, the named antagonist
    # gets its contraction reduced proportionally.
    antagonist_map = {}
    for obj in muscles:
        ant = obj.get("fascia_antagonist", "")
        if ant:
            # Side suffix resolution: left muscle relaxes left antagonist, etc.
            side_suffix = ""
            if obj.name.endswith("_L"):
                side_suffix = "_L"
            elif obj.name.endswith("_R"):
                side_suffix = "_R"

            if side_suffix:
                # First try matching with the same side suffix (e.g. Triceps_L)
                ant_objs = [m for m in muscles if (ant + side_suffix) in m.name]
                if not ant_objs:
                    # Fallback to general substring match
                    ant_objs = [m for m in muscles if ant in m.name]
            else:
                ant_objs = [m for m in muscles if ant in m.name]

            for ant_obj in ant_objs:
                antagonist_map.setdefault(ant_obj.name, []).append(obj)

    # Compute the relaxation fraction for each muscle that is named
    # as an antagonist. The relaxation is the maximum contraction
    # of all aggressors that name this muscle, normalised so that
    # full antagonist contraction = full relaxation (c_B * 0.0).
    # Saturated at 1.0 so relaxation never exceeds the muscle's
    # own contraction.
    # Safe floor prevents ZeroDivisionError in antagonist ratio.
    # 1e-9 floor is correct for all flex values, not just the > 0.001 case.
    max_c_total = max(flex * MAX_CONTRACTION, 1e-9)
    relaxation_map = {}
    for m_name, aggressors in antagonist_map.items():
        max_relax = 0.0
        for ag in aggressors:
            c_ag = flex * MAX_CONTRACTION * recruitment_map.get(ag.name, 1.0)
            max_relax = max(max_relax, min(1.0, c_ag / max_c_total))
        relaxation_map[m_name] = max_relax

    for obj in muscles:
        r_i = recruitment_map.get(obj.name, 1.0)
        c_i = flex * MAX_CONTRACTION * r_i
        # Spec 10: apply antagonist relaxation
        relax = relaxation_map.get(obj.name, 0.0)
        c_i = c_i * (1.0 - relax)
        ls_i = 1.0 - c_i
        ts_i = 1.0 / (ls_i ** 0.5) if ls_i > 0.01 else 1.0
        obj.scale[0] = ts_i  # local X = thickness (bulge)
        obj.scale[1] = ts_i  # local Y = thickness (bulge)
        obj.scale[2] = ls_i  # local Z = length (shorten)
        muscle_scales[obj.name] = (ls_i, ts_i)

    # ── Step 2: Push skin vertices outward near muscles ───────
    #
    # For each vertex on the horse's skin (body + head mesh),
    # we check how close it is to each muscle's center point.
    #
    # If it's within the "influence_radius" (scaled to base mesh size),
    # we push that vertex outward — away from the muscle center —
    # so the skin appears to bulge over the swelling muscle.
    #
    # The push amount depends on:
    #   • How much the muscle surface bulged outward
    #     (= base_radius * (thickness_scale - 1), from Step 1)
    #   • How close the vertex is (closer = more push, smooth falloff)
    #
    # We always start from the ORIGINAL vertex positions (not the
    # already-pushed ones) so the deformation never drifts.

    body = _get_base_mesh()
    base_size = _get_base_size(body) if body else 3.6
    influence_radius = MUSCLE_INFLUENCE_FRACTION * base_size
    total_affected = 0

    # Find the skin mesh objects (tagged by the user, or default placeholder)
    skin_objects = _get_skin_objects()

    # Spec 7: muscles may now be parented to landmarks (which are
    # bone-parented). matrix_world is computed from the parent chain
    # and may be stale until the depsgraph evaluates. Force an update
    # once before reading any parented muscle transforms.
    context.view_layer.update()

    # Precompute muscle info so we don't recalculate it for every vertex.
    # For each muscle, we need its center (world position), its radius
    # (how thick it is), and its per-muscle thickness scale for the skin
    # push growth calculation (Spec 5).
    muscle_info = []
    max_half_length = 0.0
    for m in muscles:
        ls_i, ts_i = muscle_scales.get(m.name, (1.0, 1.0))
        rest_length = m.get("fascia_rest_length", None)
        if rest_length is None:
            # Legacy muscle (pre-Spec-4): no axis data, no axial slide.
            # Radial push still works (uses the belly center as before).
            center = m.matrix_world.translation.copy()
            origin = None
            axis = None
        else:
            # Pinned muscle: object origin is at the FROM landmark (p1), so
            # matrix_world.translation is the ORIGIN END, not the belly.
            # Compute the current (flexed) belly center from the origin + the
            # world-space local-Z axis + rest length + current length scale.
            # matrix_world.to_quaternion() gives world rotation for both
            # parented (Spec 7) and unparented (legacy) muscles.
            # For unparented muscles it equals rotation_quaternion, so this
            # is backward-compatible. The depsgraph update above ensures
            # matrix_world is current for parented muscles.
            origin = m.matrix_world.translation.copy()
            world_rot = m.matrix_world.to_quaternion()
            axis = (world_rot @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
            center = origin + axis * (rest_length * ls_i * 0.5)
            if rest_length * 0.5 > max_half_length:
                max_half_length = rest_length * 0.5
        radius = m.get("fascia_radius", 0.04)
        # Spec 12: store origin/axis/rest_length/ls_i for the axial slide.
        # Legacy muscles get None for origin/axis, which the slide code guards on.
        muscle_info.append((center, radius, ts_i, origin, axis, rest_length, ls_i))

    # Spec 11: Build KDTree for spatial acceleration
    from mathutils.kdtree import KDTree
    kd = KDTree(len(muscle_info))
    for idx, entry in enumerate(muscle_info):
        kd.insert(entry[0], idx)  # entry[0] = belly center
    kd.balance()

    # Spec 12: Query a larger radius so vertices near the muscle ends (not
    # just the belly center) are found for the axial slide. The per-component
    # distance checks inside the loop filter out out-of-range vertices.
    search_radius = influence_radius + max_half_length
    skin_sliding = scene.fascia_skin_sliding

    for obj in skin_objects:
        mesh = obj.data

        if mesh.shape_keys:
            # ── Shape keys exist: Basis is the clean reference ──
            # NEVER write to mesh.vertices (that would corrupt Basis).
            # Read from Basis, write flex to Live_Flex only.
            #
            # Issue 11 fix: source_data MUST be the Basis shape key's
            # vertex data, NOT mesh.vertices. When shape keys exist,
            # mesh.vertices exposes the evaluated/blended positions
            # (Basis + active shape key offsets), not the clean Basis.
            # Reading from mesh.vertices compounds displacement on
            # every subsequent flex call, causing visible skin drift
            # and incorrect push directions.
            live_key = mesh.shape_keys.key_blocks.get("Live_Flex")
            if not live_key:
                live_key = obj.shape_key_add(name="Live_Flex")

            if flex < 0.001:
                live_key.value = 0.0
                # Write Basis coordinates into Live_Flex so external tools reading
                # shape key data directly see rest-pose positions, not stale flexed
                # positions (Issue 10). Weight is 0.0 so no visual change.
                basis_key = mesh.shape_keys.key_blocks.get("Basis")
                if basis_key:
                    for i, bv in enumerate(basis_key.data):
                        live_key.data[i].co = bv.co.copy()
                mesh.update()
                continue

            live_key.value = 1.0
            target_data = live_key.data
            basis_key = mesh.shape_keys.key_blocks.get("Basis")
            source_data = basis_key.data if basis_key else mesh.vertices
        else:
            # ── No shape keys yet: use the backup system ──
            # Save original verts (only once), then restore so we
            # always deform from the clean shape.
            _save_original_verts(obj)
            _restore_original_verts(obj)

            if flex < 0.001:
                mesh.update()
                continue

            target_data = mesh.vertices
            source_data = mesh.vertices

        # Get the transform matrices for this skin object.
        world_mat = obj.matrix_world.copy()
        world_inv = world_mat.inverted()

        for i, vert in enumerate(source_data):
            # Read from the clean source (Basis or restored base mesh).
            # Write to target_data (Live_Flex or base mesh).
            world_pos = world_mat @ vert.co

            # Accumulate push from all nearby muscles
            push = mathutils.Vector((0.0, 0.0, 0.0))
            was_affected = False

            # find_range returns (position, index, distance). Unpack by
            # position to match the return order, not the variable names.
            for (_co, idx, dist) in kd.find_range(world_pos, search_radius):
                if dist < 0.001:
                    continue
                m_center, m_radius, m_ts_i, m_origin, m_axis, m_rest_length, m_ls_i = muscle_info[idx]

                # ── Radial push (Spec 3, unchanged): only if within
                # influence_radius of the belly center. ──
                if dist < influence_radius:
                    t = dist / influence_radius
                    falloff = (1.0 - t) * (1.0 - t)
                    growth = m_radius * (m_ts_i - 1.0)
                    push_dir = (world_pos - m_center).normalized()
                    push += push_dir * growth * falloff
                    was_affected = True

                # ── Axial slide (Spec 12): tangential push along the muscle
                # axis, proportional to the muscle's shortening. Only if skin
                # sliding is enabled and the muscle has axis data (pinned
                # muscles, Spec 4+). Legacy muscles get None for origin/axis
                # and are skipped here. ──
                if skin_sliding and m_origin is not None and m_axis is not None and m_rest_length and m_rest_length > 0.001:
                    rel = world_pos - m_origin
                    s = rel.dot(m_axis)
                    s_clamped = max(0.0, min(m_rest_length, s))
                    radial_vec = rel - m_axis * s_clamped
                    radial_dist = radial_vec.length
                    if radial_dist < influence_radius and radial_dist > 0.001:
                        t_axial = radial_dist / influence_radius
                        falloff_axial = (1.0 - t_axial) * (1.0 - t_axial)
                        slide = s_clamped * (m_ls_i - 1.0) * SKIN_SLIDE_FRACTION
                        push += m_axis * slide * falloff_axial
                        was_affected = True

            if was_affected:
                new_world_pos = world_pos + push
                target_data[i].co = world_inv @ new_world_pos
                total_affected += 1
            elif target_data is not source_data:
                # Writing to a separate shape key — copy clean co over
                # so unaffected vertices don't keep stale flex data.
                target_data[i].co = vert.co.copy()

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

    # Step 2b: Offset the geometry so local Z spans [0, +length] instead of
    # [-length/2, +length/2]. Combined with placing the object origin at the
    # FROM landmark (p1, the muscle's anatomical ORIGIN) below, this PINS the
    # origin end: scaling local Z by (1-c) during contraction keeps local Z=0
    # fixed at p1 and pulls the insertion end (local Z=+length) toward p1.
    # At rest (scale=1) the geometry is identical to the old midpoint-pivot
    # version — only the transform pivot has moved from the midpoint to p1.
    bmesh.ops.translate(bm, vec=(0.0, 0.0, length / 2.0), verts=bm.verts)

    # NOTE: We do NOT rotate or further translate the geometry here.
    # Instead, we'll set the object's location and rotation below.
    # This is what makes flex scaling work correctly AND pins the origin.

    # Convert bmesh into a real Blender mesh object
    mesh_data = bpy.data.meshes.new(name)
    bm.to_mesh(mesh_data)
    mesh_data.update()
    bm.free()

    obj = bpy.data.objects.new(name, mesh_data)
    bpy.context.collection.objects.link(obj)

    # Step 3: Place the muscle's OBJECT ORIGIN at the FROM landmark (p1),
    # the muscle's anatomical ORIGIN (attachment). The geometry spans local
    # Z in [0, +length], so at rest the near end sits on p1 (pinned origin)
    # and the far end sits on p2 (insertion). The Step 4 rotation orients
    # local +Z from p1 toward p2.
    # KNOWN LIMITATION: The insertion end shortens toward the origin during
    # contraction. Spec 8 adds a Damped Track constraint so the muscle
    # reorients to POINT at the (possibly moved) insertion landmark, but the
    # far end is still at rest_length*ls along that direction - it does not
    # stretch to exactly reach the insertion. The geometric length mismatch
    # (Spec 4 section 2) remains; only the ANGLE is now correct. Per-muscle
    # pin-end choice is future work (per-muscle controls spec).
    obj.location = p1

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

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        # Clear any saved vertex backups and skin tags from a previous base,
        # since the old mesh data is no longer valid.
        _original_verts.clear()
        _clear_skin_tags()

        # Create the Body: a stretched sphere
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 1))
        body = context.active_object
        body.name = "Fascia_Horse_Body"
        body.scale = (1.8, 0.9, 0.9)
        body["fascia_role"] = "skin"

        # Create the Head: a smaller sphere out front
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(2.2, 0, 1.3))
        head = context.active_object
        head.name = "Fascia_Horse_Head"
        head["fascia_role"] = "skin"

        # Apply the current slider values to the horse objects we just created
        # so they match the sliders immediately.
        update_horse(None, context)

        self.report({'INFO'}, "Placeholder horse created")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────
# TOOL 1B: USE SELECTED AS BASE
# ─────────────────────────────────────────────────────────────────
# Lets the user bring their own mesh into the Fascia pipeline.
# Select any mesh in Blender, click this button, and Fascia treats
# it as the creature's skin from that point on.
# ─────────────────────────────────────────────────────────────────

class FASCIA_OT_use_selected_as_base(bpy.types.Operator):
    bl_idname = "fascia.use_selected_as_base"
    bl_label = "Use Selected as Base"
    bl_description = "Tag the selected mesh as the Fascia base creature mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object first")
            return {"CANCELLED"}

        # Clear old skin tags and vertex backups
        _clear_skin_tags()
        _original_verts.clear()

        # Tag the selected mesh as the Fascia base skin
        obj["fascia_role"] = "skin"

        self.report({'INFO'}, "Using '" + obj.name + "' as base mesh")
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
    bl_description = "Place anatomical landmark points on the base mesh using the active species (file, inline JSON, or built-in horse)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        # Check that a base mesh exists
        body = _get_base_mesh()
        if not body:
            self.report({'ERROR'}, "No base mesh found — create or load one first")
            return {"CANCELLED"}

        # Compute the base mesh's world-space bounding box
        bounds_min, bounds_max = _get_base_bounds(body)
        min_x, min_y, min_z = bounds_min
        max_x, max_y, max_z = bounds_max
        size_x = max_x - min_x
        size_y = max_y - min_y
        size_z = max_z - min_z

        # Spec 9: resolve anatomy in priority order - file (Spec 6),
        # inline JSON string (Spec 9), then embedded horse data.
        landmarks_data = HORSE_LANDMARKS
        muscles_data = HORSE_MUSCLES
        species_name = "Horse"
        species_path = context.scene.fascia_species_path
        species_json = context.scene.fascia_species_json
        if species_path:
            loaded_lm, loaded_ms, loaded_name = _load_species(species_path)
            if loaded_lm:
                landmarks_data = loaded_lm
                muscles_data = loaded_ms
                species_name = loaded_name or "Unknown"
        elif species_json:
            loaded_lm, loaded_ms, loaded_name = _load_species_json(species_json)
            if loaded_lm:
                landmarks_data = loaded_lm
                muscles_data = loaded_ms
                species_name = loaded_name or "Unknown"

        errors, warnings = _validate_species_data(landmarks_data, muscles_data, context_label=species_name)
        for w in warnings:
            self.report({'WARNING'}, w)
        if errors:
            for e in errors:
                self.report({'ERROR'}, e)
            return {'CANCELLED'}

        # Clean up any previously placed landmarks so we don't get duplicates
        old_landmarks = [obj for obj in bpy.data.objects
                         if obj.get("fascia_type") == "landmark"]
        for obj in old_landmarks:
            bpy.data.objects.remove(obj, do_unlink=True)

        placed_count = 0

        for name, data in landmarks_data.items():
            u, v, w = data["pos"]
            is_bilateral = data["bilateral"]
            region = data["region"]

            if is_bilateral:
                # Create left side (_L) and right side (_R, with V flipped)
                for suffix in ("_L", "_R"):
                    empty_name = "Fascia_LM_" + name + suffix
                    empty = bpy.data.objects.new(empty_name, None)
                    v_side = v if suffix == "_L" else (1.0 - v)
                    empty.location = (
                        min_x + u * size_x,
                        min_y + v_side * size_y,
                        min_z + w * size_z,
                    )
                    empty.empty_display_size = 0.05
                    empty.empty_display_type = 'SPHERE'
                    empty.color = (1.0, 1.0, 0.0, 1.0)  # Yellow
                    empty.show_in_front = True
                    empty["fascia_type"] = "landmark"
                    empty["fascia_region"] = region
                    empty["fascia_landmark"] = name
                    empty["fascia_side"] = suffix.strip("_")
                    if "bone" in data:
                        bone_name = data["bone"]
                        if suffix == "_R":
                            # Derive the right-side bone name by swapping common left-side
                            # suffixes. If the derived name doesn't exist in the armature at
                            # bind time, FASCIA_OT_bind_landmarks_to_rig will fall back to
                            # nearest-bone auto-binding (Issue 21 fix).
                            bone_name = (bone_name
                                .replace(".L", ".R")
                                .replace("_L", "_R")
                                .replace("left", "right")
                                .replace("Left", "Right"))
                        empty["fascia_bone"] = bone_name
                    bpy.context.collection.objects.link(empty)

                    # Parent to horse body so everything moves together
                    empty.parent = body
                    empty.matrix_parent_inverse = body.matrix_world.inverted()

                    placed_count += 1
            else:
                # Single midline landmark (centre of the body)
                empty_name = "Fascia_LM_" + name
                empty = bpy.data.objects.new(empty_name, None)
                empty.location = (
                    min_x + u * size_x,
                    min_y + v * size_y,
                    min_z + w * size_z,
                )
                empty.empty_display_size = 0.05
                empty.empty_display_type = 'SPHERE'
                empty.color = (1.0, 1.0, 0.0, 1.0)  # Yellow
                empty.show_in_front = True
                empty["fascia_type"] = "landmark"
                empty["fascia_region"] = region
                empty["fascia_landmark"] = name
                empty["fascia_side"] = "mid"
                if "bone" in data:
                    empty["fascia_bone"] = data["bone"]
                bpy.context.collection.objects.link(empty)

                # Parent to horse body so everything moves together
                empty.parent = body
                empty.matrix_parent_inverse = body.matrix_world.inverted()

                placed_count += 1

        # Make sure Blender recalculates all object positions
        context.view_layer.update()

        # Cache the resolved species name so get_status can read it without
        # re-parsing the species file on every call (Issue 18).
        context.scene["_fascia_species_name"] = species_name

        self.report({'INFO'}, str(placed_count) + " landmarks placed for " + species_name)
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────
# TOOL 7 (Spec 7): BIND / CLEAR RIG
# ─────────────────────────────────────────────────────────────────
# These operators wire landmarks to armature bones and optionally
# restore the default mesh-parenting. The chain:
#   bone → landmark (bone parent) → muscle (object parent) → skin
#
# Each landmark is bone-parented to the nearest bone (or to the
# bone named in its fascia_bone custom property, if set). Muscles
# already parented to their origin landmark at generation time
# (see generate_muscles) then follow the bones via the landmarks.
# ─────────────────────────────────────────────────────────────────

class FASCIA_OT_bind_landmarks_to_rig(bpy.types.Operator):
    bl_idname = "fascia.bind_landmarks_to_rig"
    bl_label = "Bind Landmarks to Rig"
    bl_description = "Bone-parent every landmark to the nearest bone in the chosen armature (or to its fascia_bone if set)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        # Preserve selection so internal deselect/reselect doesn't destroy user state (Issue 9).
        saved_active = context.view_layer.objects.active
        saved_selected = list(context.selected_objects)

        armature = context.scene.fascia_armature
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "No armature selected — set the Rig property first")
            return {"CANCELLED"}

        landmarks = [obj for obj in bpy.data.objects
                     if obj.get("fascia_type") == "landmark"]
        if not landmarks:
            self.report({'ERROR'}, "No landmarks found — place landmarks first")
            return {"CANCELLED"}

        bound = 0
        skipped = 0
        for lm in landmarks:
            bone_name = lm.get("fascia_bone", "")
            used_fallback = False

            # If explicit bone name is set but not in this armature (renamed rig,
            # or JSON from a different creature), fall back to auto nearest-bone
            # rather than silently skipping the landmark (Issue 21).
            if bone_name and bone_name not in armature.data.bones:
                bone_name, _ = _find_nearest_bone(armature, lm.matrix_world.translation)
                used_fallback = True
            elif not bone_name:
                bone_name, _ = _find_nearest_bone(armature, lm.matrix_world.translation)

            if not bone_name:
                skipped += 1
                continue

            ok = _bone_parent_object(lm, armature, bone_name)
            if ok:
                bound += 1
                if used_fallback:
                    self.report({'WARNING'}, f"Fascia: '{lm.name}' used fallback binding (explicit bone not found)")
            else:
                skipped += 1

        context.view_layer.update()
        self.report({'INFO'},
                    str(bound) + " landmarks bound to rig (" + str(skipped) + " skipped)")

        # Restore user's selection state.
        for obj in context.view_layer.objects:
            obj.select_set(obj in saved_selected)
        context.view_layer.objects.active = saved_active

        return {"FINISHED"}


class FASCIA_OT_clear_rig_binding(bpy.types.Operator):
    bl_idname = "fascia.clear_rig_binding"
    bl_label = "Clear Rig Binding"
    bl_description = "Unparent landmarks from bones and re-parent them to the base mesh (restores default state)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        # Preserve selection so internal deselect/reselect doesn't destroy user state (Issue 9).
        saved_active = context.view_layer.objects.active
        saved_selected = list(context.selected_objects)

        body = _get_base_mesh()
        landmarks = [obj for obj in bpy.data.objects
                     if obj.get("fascia_type") == "landmark"]

        cleared = 0
        for lm in landmarks:
            # Capture world position BEFORE clearing the parent relationship.
            # Setting lm.parent = None without first saving the world matrix
            # causes Blender to recompute position from local (bone-relative)
            # coordinates, snapping the landmark to the wrong world location
            # when the rig is in a non-rest pose (Issue 19).
            saved_world = lm.matrix_world.copy()
            lm.parent = None
            lm.parent_type = 'OBJECT'
            lm.parent_bone = ""
            lm.matrix_parent_inverse = mathutils.Matrix.Identity(4)
            lm.matrix_world = saved_world
            if "fascia_bone" in lm:
                del lm["fascia_bone"]
            if body:
                bpy.ops.object.select_all(action='DESELECT')
                body.select_set(True)
                lm.select_set(True)
                bpy.context.view_layer.objects.active = body
                with bpy.context.temp_override(
                    view_layer=context.view_layer,
                    active_object=body,
                    selected_editable_objects=[body, lm],
                    object=body,
                ):
                    bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
            cleared += 1

        context.view_layer.update()
        self.report({'INFO'}, str(cleared) + " landmarks unbound (re-parented to base mesh)")

        # Restore user's selection state.
        for obj in context.view_layer.objects:
            obj.select_set(obj in saved_selected)
        context.view_layer.objects.active = saved_active

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
    bl_description = "Generate muscle shapes between the placed landmarks using the active species (file, inline JSON, or built-in horse)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        # Check that landmarks exist first
        has_landmarks = any(obj.get("fascia_type") == "landmark"
                           for obj in bpy.data.objects)
        if not has_landmarks:
            self.report({'ERROR'}, "No landmarks found — place landmarks first")
            return {"CANCELLED"}

        # Snapshot existing per-muscle recruitment values so we can
        # restore them after regeneration (by muscle name). This lets
        # the user re-run Generate Muscles without losing their
        # per-muscle recruitment tuning (Spec 5).
        old_recruitment = {}
        for entry in context.scene.fascia_recruitment:
            old_recruitment[entry.name] = entry.recruitment
        context.scene.fascia_recruitment.clear()

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

        body = _get_base_mesh()
        base_size = _get_base_size(body) if body else 3.6

        # Spec 9: resolve anatomy in priority order - file (Spec 6),
        # inline JSON string (Spec 9), then embedded horse data.
        landmarks_data = HORSE_LANDMARKS
        muscles_data = HORSE_MUSCLES
        species_name = "Horse"
        species_path = context.scene.fascia_species_path
        species_json = context.scene.fascia_species_json
        if species_path:
            loaded_lm, loaded_ms, loaded_name = _load_species(species_path)
            if loaded_lm and loaded_ms:
                landmarks_data = loaded_lm
                muscles_data = loaded_ms
                species_name = loaded_name or "Unknown"
        elif species_json:
            loaded_lm, loaded_ms, loaded_name = _load_species_json(species_json)
            if loaded_lm and loaded_ms:
                landmarks_data = loaded_lm
                muscles_data = loaded_ms
                species_name = loaded_name or "Unknown"

        errors, warnings = _validate_species_data(landmarks_data, muscles_data, context_label=species_name)
        for w in warnings:
            self.report({'WARNING'}, w)
        if errors:
            for e in errors:
                self.report({'ERROR'}, e)
            return {'CANCELLED'}

        muscle_count = 0

        for muscle_name, mdata in muscles_data.items():
            from_key = mdata["from"]
            to_key = mdata["to"]
            from_bilateral = landmarks_data[from_key]["bilateral"]
            to_bilateral = landmarks_data[to_key]["bilateral"]

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
                    obj = create_muscle_mesh(obj_name, p1, p2, mdata["radius"] * base_size)

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
                    # Store the muscle's WORLD-SPACE base thickness (fraction * base_size)
                    # so the flex slider's growth math (m_radius * (thickness_scale - 1))
                    # works in consistent world units.
                    obj["fascia_radius"] = mdata["radius"] * base_size
                    obj["fascia_rest_length"] = (p2 - p1).length

                    # Spec 10: Antagonist pairing — store the
                    # antagonist muscle name so update_flex can
                    # auto-relax this muscle when its antagonist
                    # contracts.
                    if "antagonist" in mdata:
                        obj["fascia_antagonist"] = mdata["antagonist"]

                    # Spec 7: parent muscle to its origin landmark so it
                    # follows the landmark (which follows the rig bone).
                    # keep_transform=True preserves the just-set world transform.
                    _object_parent_object(obj, from_obj)

                    # Spec 8: Damped Track the muscle's local +Z (length axis)
                    # at its insertion landmark so the muscle reorients toward
                    # the insertion as the rig moves. Closes the Spec 7 section 7
                    # 'wrong angle at insertion' gap. Rotation-only - volume
                    # preservation unaffected. See _add_insertion_track_constraint.
                    _add_insertion_track_constraint(obj, to_obj)

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
                obj = create_muscle_mesh(obj_name, p1, p2, mdata["radius"] * base_size)

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
                obj["fascia_radius"] = mdata["radius"] * base_size
                obj["fascia_rest_length"] = (p2 - p1).length

                # Spec 10: Antagonist pairing.
                if "antagonist" in mdata:
                    obj["fascia_antagonist"] = mdata["antagonist"]

                # Spec 7: parent muscle to its origin landmark.
                _object_parent_object(obj, from_obj)

                # Spec 8: Damped Track the muscle at its insertion landmark.
                _add_insertion_track_constraint(obj, to_obj)

                muscle_count += 1

        # Rebuild the per-muscle recruitment collection from the
        # generated muscles. Preserve recruitment values for muscles
        # that existed before regeneration (matched by name); new
        # muscles default to 1.0 (uniform contraction).
        for m in bpy.data.objects:
            if m.get("fascia_type") == "muscle":
                entry = context.scene.fascia_recruitment.add()
                entry.name = m.name
                entry.recruitment = old_recruitment.get(m.name, 1.0)

        # If the Flex slider is currently above zero, recalculate
        # the skin deformation with the newly generated muscles
        update_flex(None, context)

        # Cache the resolved species name so get_status can read it without
        # re-parsing the species file on every call (Issue 18).
        context.scene["_fascia_species_name"] = species_name

        self.report({'INFO'}, str(muscle_count) + " muscles generated for " + species_name)
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

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene

        # Without muscles, the flex animation has nothing to deform.
        has_muscles = any(obj.get("fascia_type") == "muscle"
                          for obj in bpy.data.objects)
        if not has_muscles:
            self.report({'ERROR'}, "No muscles found — generate muscles first")
            return {"CANCELLED"}

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

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        skin_objects = _get_skin_objects()

        if not skin_objects:
            self.report({'ERROR'}, "No horse meshes found to bake.")
            return {"CANCELLED"}

        # Without muscles, baking just captures the rest pose on every frame.
        has_muscles = any(obj.get("fascia_type") == "muscle"
                          for obj in bpy.data.objects)
        if not has_muscles:
            self.report({'ERROR'}, "No muscles found — generate muscles and run Simulate Motion first")
            return {"CANCELLED"}

        frames_to_bake = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
        frames_saved = 0

        for frame in frames_to_bake:
            context.scene.frame_set(frame)
            flex_val = context.scene.fascia_flex

            for obj in skin_objects:
                mesh = obj.data

                # Read current flexed positions from wherever update_flex wrote them.
                # This MUST happen before we create Basis, because creating Basis
                # restores mesh.vertices to the original (clean) state — which would
                # erase the flexed data we need to capture.
                basis = mesh.shape_keys.key_blocks.get("Basis") if mesh.shape_keys else None
                if flex_val < 0.001:
                    source = basis.data if basis else mesh.vertices
                elif basis and "Live_Flex" in mesh.shape_keys.key_blocks:
                    source = mesh.shape_keys.key_blocks["Live_Flex"].data
                else:
                    source = mesh.vertices
                flexed_verts = [(v.co.x, v.co.y, v.co.z) for v in source]

                # Ensure Basis exists and is clean
                if not mesh.shape_keys:
                    _restore_original_verts(obj)
                    obj.shape_key_add(name="Basis")

                # Create or get shape key for this frame
                pose_name = f"Baked_Frame_{frame:03d}"
                if pose_name in mesh.shape_keys.key_blocks:
                    new_key = mesh.shape_keys.key_blocks[pose_name]
                else:
                    new_key = obj.shape_key_add(name=pose_name)
                
                # Write the flexed positions into this frame's shape key
                for i, (x, y, z) in enumerate(flexed_verts):
                    new_key.data[i].co.x = x
                    new_key.data[i].co.y = y
                    new_key.data[i].co.z = z
            
            frames_saved += 1

        # Return to start frame
        context.scene.frame_set(1)

        self.report({'INFO'}, f"Bake complete: {frames_saved} frames saved")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────
# TOOL 9 (Spec 9): STATUS QUERY (LLM-facing)
# ─────────────────────────────────────────────────────────────────
# Reports the current Fascia workflow state as a short plain-English
# summary (base mesh, species, landmark/muscle counts, rig, flex).
# Returns no mesh data (rule 5). Callable via bpy.ops.fascia.get_status()
# by an external LLM through the Blender MCP server.
# ─────────────────────────────────────────────────────────────────

class FASCIA_OT_get_status(bpy.types.Operator):
    bl_idname = "fascia.get_status"
    bl_label = "Get Fascia Status"
    bl_description = "Report the current Fascia workflow state — base, species, landmark/muscle counts, rig, flex. LLM-facing; returns no mesh data"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Fascia operators require Object Mode — they create, parent, and
        # deform objects via bpy.ops, which fail in other contexts.
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        body = _get_base_mesh()
        base_name = body.name if body else "none"

        # Resolve the active species name (same priority as operators)
        species_name = context.scene.get("_fascia_species_name", None)
        if species_name is None:
            species_name = "horse(default)"
            species_path = scene.fascia_species_path
            species_json = scene.fascia_species_json
            if species_path:
                _lm, _ms, loaded_name = _load_species(species_path)
                if _lm:
                    species_name = loaded_name or "Unknown"
            elif species_json:
                _lm, _ms, loaded_name = _load_species_json(species_json)
                if _lm:
                    species_name = loaded_name or "Unknown"

        lm_count = sum(1 for o in bpy.data.objects if o.get("fascia_type") == "landmark")
        muscle_count = sum(1 for o in bpy.data.objects if o.get("fascia_type") == "muscle")
        rig_name = scene.fascia_armature.name if scene.fascia_armature else "none"

        summary = (
            "Fascia: base=" + base_name +
            ", species=" + species_name +
            ", landmarks=" + str(lm_count) +
            ", muscles=" + str(muscle_count) +
            ", rig=" + rig_name +
            ", flex=" + str(round(scene.fascia_flex, 2))
        )
        self.report({'INFO'}, summary)
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
        
        # Draw the button to create the placeholder horse
        layout.operator("fascia.make_placeholder_horse", icon="MESH_MONKEY")

        # Draw the button to use a selected mesh as the base
        layout.operator("fascia.use_selected_as_base", icon="MESH_DATA")

        # Species file selector (Spec 6). Empty = use built-in horse.
        layout.prop(scene, "fascia_species_path", text="Species File")
        layout.prop(scene, "fascia_species_json", text="Species JSON")
        
        # Add a visual separator line
        layout.separator()
        
        # Draw the settings label and sliders
        # Show loaded species name — not hardcoded "Horse" for non-horse workflows.
        species_path = scene.fascia_species_path
        if species_path:
            species_label = os.path.splitext(
                os.path.basename(bpy.path.abspath(species_path)))[0]
        elif scene.fascia_species_json:
            species_label = "Custom Species"
        else:
            species_label = "Horse"
        layout.label(text=f"{species_label} Settings:")
        
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

        # ── Rig section (Spec 7) ─────────────────────────────
        layout.separator()
        layout.label(text="Rig:")
        layout.prop(scene, "fascia_armature", text="Rig")
        if scene.fascia_armature:
            layout.operator("fascia.bind_landmarks_to_rig", icon="ARMATURE_DATA")
            layout.operator("fascia.clear_rig_binding", icon="X")

        # ── Simulation section (Tools 5-7) ───────────────────
        layout.separator()
        layout.label(text="Simulation:")

        # Flex slider — the GLOBAL contraction drive. Per-muscle
        # recruitment (below) multiplies this per muscle:
        #   c_i = flex * MAX_CONTRACTION * recruitment_i
        layout.prop(scene, "fascia_flex", text="Flex", slider=True)

        # Skin sliding toggle (Spec 12). On by default; turn off to
        # compare with radial-only deformation.
        layout.prop(scene, "fascia_skin_sliding")

        # Hard Design Rule 13: never claim FEM parity.
        layout.label(text="Geometric contraction only (not FEM/physics)", icon='INFO')

        # Show how many skin vertices are being affected by the flex
        flex_val = scene.fascia_flex
        if flex_val > 0.001:
            affected = scene.get("_fascia_flex_affected", 0)
            layout.label(text="Skin bound: " + str(affected) + " vertices affected")

        # ── Per-muscle recruitment (Spec 5) ──────────────────
        # A UI list of all generated muscles, each with its own
        # recruitment multiplier on the global Flex. 1.0 = normal,
        # 0.0 = stays at rest, 2.0 = double contraction.
        # Empty list = no muscles generated yet (or pre-Spec-5 scene);
        # falls back to uniform recruitment in update_flex.
        if len(scene.fascia_recruitment) > 0:
            layout.separator()
            layout.label(text="Per-Muscle Recruitment:")
            row = layout.row()
            row.template_list(
                "FASCIA_UL_recruitment", "",
                scene, "fascia_recruitment",
                scene, "fascia_recruitment_index",
                rows=6,
            )

        layout.separator()
        
        # Button to create a 60-frame flex test animation
        layout.operator("fascia.simulate_motion", icon="ACTION")

        # Button to bake the flex animation into Shape Keys
        layout.operator("fascia.bake_flex_pose", text="Bake Result", icon="SHAPEKEY_DATA")


# ─────────────────────────────────────────────────────────────────
# PER-MUSCLE CONTRACTION RECRUITMENT
# ─────────────────────────────────────────────────────────────────
# A registered PropertyGroup stored in a CollectionProperty on the
# Scene. One entry per muscle, keyed by muscle object name. The
# recruitment value (0.0–2.0, default 1.0) multiplies the global Flex
# slider's contraction for that muscle:
#   c_i = flex * MAX_CONTRACTION * recruitment_i
# This lets the user make individual muscles contract harder, softer,
# or not at all, while the global Flex slider stays the master drive.
# Antagonist pairing (auto-relax reciprocal muscles) is supported (Spec 10).

class FasciaMuscleRecruitment(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Muscle Name",
        description="Name of the muscle object this entry controls",
    )
    recruitment: bpy.props.FloatProperty(
        name="Recruitment",
        description="How much this muscle participates in the global Flex contraction. 1.0 = normal, 0.0 = stays at rest, 2.0 = double contraction",
        default=1.0,
        min=0.0,
        max=2.0,
        update=update_flex
    )


class FASCIA_UL_recruitment(bpy.types.UIList):
    bl_idname = "FASCIA_UL_recruitment"
    bl_label = "Per-Muscle Recruitment"

    def draw_item(self, context, layout, data, item, icon_value, active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.name, icon='MESH_UVSPHERE')
            row.prop(item, "recruitment", text="", slider=True, emboss=False)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon_value)


# A list of classes that Blender needs to register/load when enabling this add-on
classes = (
    FasciaMuscleRecruitment,
    FASCIA_UL_recruitment,
    FASCIA_OT_make_placeholder_horse,
    FASCIA_OT_use_selected_as_base,
    FASCIA_OT_place_landmarks,
    FASCIA_OT_generate_muscles,
    FASCIA_OT_bind_landmarks_to_rig,
    FASCIA_OT_clear_rig_binding,
    FASCIA_OT_simulate_motion,
    FASCIA_OT_bake_flex_pose,
    FASCIA_OT_get_status,
    FASCIA_PT_main_panel,
)


def register():
    # Register all our panel and operator classes
    for cls in classes:
        bpy.utils.register_class(cls)

    # Issue 1: register the handler that invalidates the vertex
    # cache when the user sculpts/edits a skin mesh. Guard against
    # double-registration on reload.
    if _fascia_invalidate_on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_fascia_invalidate_on_depsgraph)

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
    # At 1.0 = fully flexed (muscles are 25% shorter and ~15.5% thicker,
    # volume preserved; skin bulges over them).
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

    # Per-muscle contraction recruitment collection (Spec 5).
    # One FasciaMuscleRecruitment entry per muscle, rebuilt when
    # muscles are generated. Empty collection = uniform recruitment
    # (backwards-compatible with pre-Spec-5 scenes).
    # FasciaMuscleRecruitment is already registered via the classes
    # tuple loop above; no explicit register_class call here.
    bpy.types.Scene.fascia_recruitment = bpy.props.CollectionProperty(
        type=FasciaMuscleRecruitment,
        name="Per-Muscle Recruitment",
        description="Per-muscle contraction recruitment multipliers",
    )
    bpy.types.Scene.fascia_recruitment_index = bpy.props.IntProperty(
        name="Recruitment List Index",
        description="Active row in the per-muscle recruitment list",
        default=0,
        min=0,
    )

    # Species definition file path (Spec 6). Empty = use embedded horse data.
    bpy.types.Scene.fascia_species_path = bpy.props.StringProperty(
        name="Species File",
        description="Path to a species-definition JSON file. Empty = use the built-in horse anatomy",
        default="",
        subtype='FILE_PATH',
    )

    # Inline species JSON (Spec 9). Empty = fall back to fascia_species_path
    # or embedded horse data. Set by the LLM to pass anatomy without a file.
    bpy.types.Scene.fascia_species_json = bpy.props.StringProperty(
        name="Species JSON",
        description="Inline species-definition JSON string. Empty = use Species File or built-in horse anatomy",
        default="",
        subtype='NONE',
    )

    # Armature for rig binding (Spec 7). None = landmarks stay parented to base mesh.
    bpy.types.Scene.fascia_armature = bpy.props.PointerProperty(
        name="Rig",
        description="Armature object to bind landmarks to. None = landmarks stay parented to the base mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
    )

    # Skin sliding toggle (Spec 12). When enabled, skin slides tangentially
    # along contracting muscles in addition to radial bulging.
    bpy.types.Scene.fascia_skin_sliding = bpy.props.BoolProperty(
        name="Skin Sliding",
        description="When enabled, skin slides tangentially along contracting muscles (in addition to radial bulging). Disable to compare with radial-only behavior.",
        default=True,
        update=update_flex,
    )


def unregister():
    # Remove the CollectionProperty and IntProperty BEFORE unregistering
    # the PropertyGroup type, so there are no dangling type references.
    del bpy.types.Scene.fascia_recruitment_index
    del bpy.types.Scene.fascia_recruitment

    # Skin sliding toggle (Spec 12) — no type dependency, but keep it in
    # the pre-class block for consistency with other Scene properties.
    del bpy.types.Scene.fascia_skin_sliding

    # Unregister our panel and operator classes (includes
    # FasciaMuscleRecruitment and FASCIA_UL_recruitment via the tuple).
    for cls in classes:
        bpy.utils.unregister_class(cls)

    # Remove the custom Scene properties so we don't leave clutter behind
    del bpy.types.Scene.fascia_species_path
    del bpy.types.Scene.fascia_species_json
    del bpy.types.Scene.fascia_armature
    del bpy.types.Scene.fascia_age
    del bpy.types.Scene.fascia_fat
    del bpy.types.Scene.fascia_color
    del bpy.types.Scene.fascia_flex

    # Clear the saved vertex backups
    _original_verts.clear()

    # Issue 1: remove the cache-invalidation handler so a disabled
    # add-on does not keep reacting to scene edits.
    if _fascia_invalidate_on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_fascia_invalidate_on_depsgraph)


if __name__ == "__main__":
    register()
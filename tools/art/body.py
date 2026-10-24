"""
The Helldiver body, built procedurally on Commando's rig (rig.py) so it can be regenerated and tuned from this file.
Design: art/DESIGN.md and art/concept/final_turnaround.png. Run inside Blender:

    import sys; sys.path.insert(0, r"<repo>/tools/art"); import body; body.build()

Blender space: z up, the character faces -y, its left side is +x (rig.py). Each part is a simple bevelled shape weighted rigidly to one
bone; parts listed for the left side are mirrored to the right (x -> -x, ".l" -> ".r"). Colours come from a palette texture: every part
points its UVs at one flat swatch (PALETTE), the way Commando's own 64x8 palette texture works.
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

COLLECTION = "Body"
RIG = "HelldiverRig"

# palette swatches: name -> (column, row) in an 8 x 8 grid of flat colours, and the sRGB colour
PALETTE = {
    "armor":  ((0, 0), (0.205, 0.215, 0.235)),
    "suit":   ((1, 0), (0.560, 0.570, 0.590)),
    "trim":   ((2, 0), (0.960, 0.760, 0.160)),
    "visor":  ((3, 0), (1.000, 0.620, 0.170)),
    "dark":   ((4, 0), (0.115, 0.118, 0.128)),
    "belt":   ((5, 0), (0.360, 0.370, 0.390)),
    "boot":   ((6, 0), (0.420, 0.430, 0.450)),
    "sole":   ((7, 0), (0.090, 0.090, 0.095)),
}
GRID = 8


def swatch_uv(name):
    (c, r), _ = PALETTE[name]
    return ((c + 0.5) / GRID, 1.0 - (r + 0.5) / GRID)


# ------------------------------------------------------------------------------------------------ primitives (bmesh)
def _finish(bm, geom_verts, colour):
    uv = bm.loops.layers.uv.verify()
    u = swatch_uv(colour)
    vs = set(geom_verts)
    for f in bm.faces:
        if all(v in vs for v in f.verts):
            for l in f.loops: l[uv].uv = u
    return geom_verts


def box(bm, center, size, colour, rot=None, bevel=0.0):
    m = Matrix.LocRotScale(Vector(center), rot, Vector(size))
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    verts = r["verts"]
    if bevel > 0:
        edges = list({e for v in verts for e in v.link_edges})
        res = bmesh.ops.bevel(bm, geom=edges + verts, offset=bevel, segments=1, affect="EDGES", profile=0.5)
        verts = list({v for v in verts if v.is_valid} | set(res["verts"]))
    return _finish(bm, verts, colour)


def ellipsoid(bm, center, radii, colour, segs=10, rings=6):
    r = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0,
                                  matrix=Matrix.LocRotScale(Vector(center), None, Vector(radii)))
    return _finish(bm, r["verts"], colour)


def cylinder(bm, a, b, ra, rb, colour, sides=8):
    a, b = Vector(a), Vector(b)
    axis = b - a
    r = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=sides, radius1=ra, radius2=rb, depth=axis.length,
                              matrix=Matrix.Translation((a + b) / 2) @ axis.to_track_quat("Z", "Y").to_matrix().to_4x4())
    return _finish(bm, r["verts"], colour)


def seg_box(bm, a, b, width, depth, colour, bevel=0.0, forward_offset=0.0):
    """A box running from a to b; width along world x, depth along world y (forward is -y), pushed forward by forward_offset."""
    a, b = Vector(a), Vector(b)
    yaxis = (b - a).normalized()
    fwd = Vector((0, -1, 0)); fwd = (fwd - yaxis * fwd.dot(yaxis)).normalized()
    xaxis = yaxis.cross(fwd)
    rot = Matrix((xaxis, yaxis, -fwd)).transposed()            # columns: x, along, back
    c = (a + b) / 2 + fwd * forward_offset
    return box(bm, c, (width, (b - a).length, depth), colour, rot.to_quaternion(), bevel)


# ------------------------------------------------------------------------------------------------ the parts (left side + centre)
def parts(B):
    """(object name, bone, builder(bm) -> verts). B: rest-pose bone heads/tails in Blender space."""
    h = lambda n: B[n].head_local.copy()
    t = lambda n: B[n].tail_local.copy()
    P = []
    def add(name, bone, fn): P.append((name, bone, fn))

    # --- hips, belt, pouches
    add("Hips", "pelvis", lambda bm: box(bm, (0, -0.005, 0.975), (0.32, 0.21, 0.16), "suit", bevel=0.02))
    add("Belt", "pelvis", lambda bm: box(bm, (0, -0.01, 1.035), (0.36, 0.25, 0.065), "belt", bevel=0.01))
    add("Buckle", "pelvis", lambda bm: box(bm, (0, -0.138, 1.035), (0.075, 0.02, 0.055), "trim", bevel=0.005))
    add("PouchA.l", "pelvis", lambda bm: box(bm, (0.075, -0.14, 1.005), (0.07, 0.05, 0.085), "belt", bevel=0.01))
    add("PouchB.l", "pelvis", lambda bm: box(bm, (0.155, -0.11, 1.005), (0.065, 0.05, 0.085), "belt", bevel=0.01))
    # --- abdomen, chest, back, collar
    add("Abdomen", "stomach", lambda bm: box(bm, (0, -0.02, 1.13), (0.28, 0.21, 0.14), "suit", bevel=0.02))
    add("AbPlate", "stomach", lambda bm: box(bm, (0, -0.125, 1.15), (0.20, 0.03, 0.09), "armor", bevel=0.01))
    add("Chest", "chest", lambda bm: box(bm, (0, 0.0, 1.355), (0.42, 0.27, 0.30), "armor", bevel=0.04))
    add("ChestTrim", "chest", lambda bm: box(bm, (0, -0.138, 1.30), (0.30, 0.012, 0.16), "trim", bevel=0.004))
    add("ChestPlate", "chest", lambda bm: box(bm, (0, -0.142, 1.30), (0.27, 0.02, 0.135), "armor", bevel=0.006))
    add("Collar", "chest", lambda bm: cylinder(bm, (0, 0.05, 1.49), (0, 0.06, 1.575), 0.135, 0.12, "armor", sides=10))
    add("CollarTrim", "chest", lambda bm: cylinder(bm, (0, 0.06, 1.575), (0, 0.062, 1.585), 0.123, 0.12, "trim", sides=10))
    # --- helmet (head)
    add("Helmet", "head", lambda bm: ellipsoid(bm, (0, 0.045, 1.735), (0.150, 0.165, 0.160), "armor", segs=12, rings=8))
    add("HelmetStripe", "head", lambda bm: ellipsoid(bm, (0, 0.045, 1.737), (0.022, 0.168, 0.162), "trim", segs=8, rings=8))
    add("Brow", "head", lambda bm: box(bm, (0, -0.105, 1.775), (0.27, 0.07, 0.035), "armor", bevel=0.01))
    add("Visor", "head", lambda bm: box(bm, (0, -0.108, 1.725), (0.235, 0.05, 0.06), "visor", bevel=0.008))
    add("Jaw", "head", lambda bm: box(bm, (0, -0.10, 1.645), (0.17, 0.08, 0.11), "armor", bevel=0.02))
    add("Vent.l", "head", lambda bm: box(bm, (0.065, -0.135, 1.645), (0.035, 0.02, 0.06), "dark", bevel=0.004))
    add("Ear.l", "head", lambda bm: box(bm, (0.145, 0.03, 1.70), (0.05, 0.13, 0.13), "armor", bevel=0.02))
    # --- arms
    add("Shoulder.l", "upper_arm.l", lambda bm: ellipsoid(bm, h("upper_arm.l") + Vector((0.05, -0.005, -0.005)), (0.115, 0.125, 0.095), "armor"))
    add("ShoulderTrim.l", "upper_arm.l", lambda bm: ellipsoid(bm, h("upper_arm.l") + Vector((0.05, -0.005, -0.03)), (0.118, 0.128, 0.06), "trim"))
    add("UpperArm.l", "upper_arm.l", lambda bm: cylinder(bm, h("upper_arm.l") + Vector((0, 0, -0.04)), t("upper_arm.l"), 0.06, 0.055, "suit"))
    add("Forearm.l", "lower_arm.l", lambda bm: cylinder(bm, h("lower_arm.l"), t("lower_arm.l") + Vector((0, 0, 0.03)), 0.072, 0.064, "armor"))
    add("Glove.l", "hand.l", lambda bm: seg_box(bm, h("hand.l") + Vector((0, 0, 0.02)), h("hand.l").lerp(t("hand.l"), 0.75), 0.07, 0.11, "dark", bevel=0.02))
    # --- legs
    add("Thigh.l", "thigh.l", lambda bm: cylinder(bm, h("thigh.l") + Vector((0, 0, 0.03)), h("calf.l"), 0.092, 0.074, "suit"))
    add("ThighPlate.l", "thigh.l", lambda bm: seg_box(bm, h("thigh.l").lerp(h("calf.l"), 0.12), h("thigh.l").lerp(h("calf.l"), 0.62), 0.135, 0.03, "armor", bevel=0.01, forward_offset=0.085))
    add("Knee.l", "calf.l", lambda bm: ellipsoid(bm, h("calf.l") + Vector((0.0, -0.07, 0.0)), (0.07, 0.05, 0.075), "boot"))
    add("Shin.l", "calf.l", lambda bm: cylinder(bm, h("calf.l"), Vector((0.188, 0.045, 0.16)), 0.07, 0.06, "suit"))
    add("ShinGuard.l", "calf.l", lambda bm: seg_box(bm, h("calf.l").lerp(Vector((0.19, 0.04, 0.16)), 0.18), h("calf.l").lerp(Vector((0.19, 0.04, 0.16)), 0.9), 0.11, 0.03, "armor", bevel=0.01, forward_offset=0.065))
    add("BootShaft.l", "calf.l", lambda bm: box(bm, (0.192, 0.035, 0.165), (0.135, 0.16, 0.12), "boot", bevel=0.02))
    add("Boot.l", "foot.l", lambda bm: box(bm, (0.193, 0.03, 0.06), (0.14, 0.19, 0.10), "boot", bevel=0.02))
    add("Toe.l", "toe.l", lambda bm: box(bm, (0.193, -0.075, 0.05), (0.135, 0.09, 0.085), "boot", bevel=0.025))
    add("Sole.l", "foot.l", lambda bm: box(bm, (0.193, -0.0, 0.012), (0.145, 0.27, 0.024), "sole", bevel=0.006))
    return P


def _mirror_name(n):
    return n[:-2] + ".r" if n.endswith(".l") else n


def build(rig_name=RIG):
    rig = bpy.data.objects[rig_name]
    col = bpy.data.collections.get(COLLECTION)
    if col:
        for o in list(col.objects): bpy.data.objects.remove(o, do_unlink=True)
    else:
        col = bpy.data.collections.new(COLLECTION); bpy.context.scene.collection.children.link(col)
    mats = {}
    for name, (_, c) in PALETTE.items():
        m = bpy.data.materials.get("hd_" + name) or bpy.data.materials.new("hd_" + name)
        m.diffuse_color = (*[x ** 2.2 for x in c], 1.0)
        mats[name] = m
    made = []
    for name, bone, fn in parts(rig.data.bones):
        for side in ((False, True) if name.endswith(".l") else (False,)):
            bm = bmesh.new()
            fn(bm)
            if side:
                bmesh.ops.scale(bm, vec=(-1, 1, 1), verts=bm.verts)
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
            nm = _mirror_name(name) if side else name
            bn = _mirror_name(bone) if side else bone
            me = bpy.data.meshes.new(nm); bm.to_mesh(me); bm.free()
            ob = bpy.data.objects.new(nm, me); col.objects.link(ob)
            # viewport colour from the swatch the part uses
            u = me.uv_layers[0].data[0].uv
            sw = min(PALETTE, key=lambda k: (Vector(swatch_uv(k)) - Vector(u)).length)
            me.materials.append(mats[sw])
            vg = ob.vertex_groups.new(name=bn); vg.add(range(len(me.vertices)), 1.0, "REPLACE")
            ob.parent = rig
            mod = ob.modifiers.new("Armature", "ARMATURE"); mod.object = rig
            for p in me.polygons: p.use_smooth = False
            made.append(ob)
    return made


def palette_png(path, size=64):
    """The palette texture the UVs point into (flat swatches)."""
    import numpy as np
    img = np.zeros((size, size, 4), np.float32); img[..., 3] = 1.0
    cell = size // GRID
    for _, ((c, r), col) in PALETTE.items():
        img[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell, :3] = col
    # Blender images are stored bottom row first; byte images keep the sRGB values as given
    im = bpy.data.images.new("hd_palette_tmp", size, size, alpha=False)
    im.pixels.foreach_set(np.ascontiguousarray(img[::-1]).ravel())
    im.filepath_raw = path; im.file_format = "PNG"; im.save()
    bpy.data.images.remove(im)


def stats():
    col = bpy.data.collections[COLLECTION]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in col.objects)
    return {"objects": len(col.objects), "triangles": tris}

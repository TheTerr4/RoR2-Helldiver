"""
The Helldiver body, built procedurally on Commando's rig (rig.py) so it can be regenerated and tuned from this file.
Design: art/DESIGN.md and art/concept/final_turnaround.png (gate renders in art/review/). Run inside Blender:

    import sys; sys.path.insert(0, r"<repo>/tools/art"); import body; body.build()

Blender space: z up, the character faces -y, its left side is +x (rig.py). The joint positions are Commando's and can't move; the
shapes around them carry the concept's proportions. Parts listed for the left side are mirrored to the right (x -> -x, ".l" -> ".r").
Each part is weighted rigidly to one bone, except the joint fillers (elbow, knee), which are split between the two bones.
Colours come from a palette texture: every part points its UVs at one flat swatch (PALETTE), the way Commando's own 64x8 palette
texture works. Yellow trim is a slightly larger yellow plate behind an armour plate, so it shows as a rim.
Shading: smooth, with sharp edges where faces meet at more than SHARP_DEG, so bevels read as clean facets.
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

COLLECTION = "Body"
RIG = "HelldiverRig"
SHARP_DEG = 35.0

# palette swatches: name -> (column, row) in an 8 x 8 grid of flat colours, and the sRGB colour
PALETTE = {
    "armor":  ((0, 0), (0.205, 0.215, 0.235)),
    "suit":   ((1, 0), (0.470, 0.475, 0.480)),
    "trim":   ((2, 0), (0.960, 0.760, 0.160)),
    "visor":  ((3, 0), (1.000, 0.620, 0.170)),
    "dark":   ((4, 0), (0.115, 0.118, 0.128)),
    "belt":   ((5, 0), (0.360, 0.370, 0.390)),
    "boot":   ((6, 0), (0.250, 0.255, 0.265)),
    "sole":   ((7, 0), (0.090, 0.090, 0.095)),
}
GRID = 8
FWD = Vector((0, -1, 0))
OUT = Vector((1, 0, 0))        # the character's left (outward for .l parts)


def swatch_uv(name):
    (c, r), _ = PALETTE[name]
    return ((c + 0.5) / GRID, 1.0 - (r + 0.5) / GRID)


# ------------------------------------------------------------------------------------------------ primitives (bmesh)
def _finish(bm, verts, colour):
    uv = bm.loops.layers.uv.verify()
    u = swatch_uv(colour)
    vs = set(verts)
    for f in bm.faces:
        if all(v in vs for v in f.verts):
            for l in f.loops: l[uv].uv = u
    return verts


def _bevel(bm, verts, bevel, segments=1):
    if bevel <= 0: return verts
    edges = list({e for v in verts for e in v.link_edges})
    res = bmesh.ops.bevel(bm, geom=edges + verts, offset=bevel, segments=segments, affect="EDGES", profile=0.5, clamp_overlap=True)
    return list({v for v in verts if v.is_valid} | set(res["verts"]))


def box(bm, center, size, colour, rot=None, bevel=0.0, segments=1):
    bevel = min(bevel, 0.45 * min(size))
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.LocRotScale(Vector(center), rot, Vector(size)))
    return _finish(bm, _bevel(bm, r["verts"], bevel, segments), colour)


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


def frustum(bm, a, b, size_a, size_b, colour, face=FWD, offset=0.0, bevel=0.0, segments=1):
    """A box running from a to b that tapers from size_a to size_b ((width, depth) each). `face` is the direction its front looks
    (depth is measured along it, width across), and the whole box is pushed `offset` metres that way."""
    a, b = Vector(a), Vector(b)
    bevel = min(bevel, 0.45 * min(size_a[0], size_a[1], size_b[0], size_b[1], (b - a).length))
    along = (b - a).normalized()
    f = Vector(face); f = (f - along * f.dot(along)).normalized()
    side = along.cross(f)
    a = a + f * offset; b = b + f * offset
    vs = []
    for c, (w, d) in ((a, size_a), (b, size_b)):
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vs.append(bm.verts.new(c + side * (sx * w / 2) + f * (sy * d / 2)))
    q = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    faces = [bm.faces.new([vs[i] for i in fq]) for fq in q]
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return _finish(bm, _bevel(bm, vs, bevel, segments), colour)


def plate(bm, a, b, size_a, size_b, colour, face=FWD, offset=0.0, bevel=0.0, trim=0.0, trim_colour="trim"):
    """An armour plate plus, when trim > 0, a yellow plate `trim` metres larger on every side right behind it (the rim)."""
    vs = frustum(bm, a, b, size_a, size_b, colour, face, offset, bevel)
    if trim > 0:
        ext = (Vector(b) - Vector(a)).normalized() * trim
        # thinner and set further back than the plate, so no bevel facet of the trim lies in the plate's plane
        vs += frustum(bm, Vector(a) - ext, Vector(b) + ext, (size_a[0] + 2 * trim, size_a[1] * 0.7), (size_b[0] + 2 * trim, size_b[1] * 0.7),
                      trim_colour, face, offset - size_a[1] * 0.31, bevel * 0.4)
    return vs


def shell(bm, center, radii, z0, z1, a0, a1, s_in, s_out, colour, segs=10):
    """A curved slab lying on an ellipsoid (center, radii): between heights z0..z1 and angles a0..a1 (degrees around z, 0 = front
    (-y), positive toward +x), from s_in to s_out times the ellipsoid's size. Visor, brow and other parts that follow the helmet."""
    import math as _m
    c = Vector(center); rx, ry, rz = radii
    def pt(a, z, s):
        k = max(0.0, 1.0 - ((z - c.z) / (rz * s)) ** 2) ** 0.5
        return Vector((c.x + _m.sin(_m.radians(a)) * rx * s * k, c.y - _m.cos(_m.radians(a)) * ry * s * k, z))
    angs = [a0 + (a1 - a0) * i / segs for i in range(segs + 1)]
    grid = {}
    for i, a in enumerate(angs):
        for j, z in enumerate((z0, z1)):
            for k, s in enumerate((s_in, s_out)):
                grid[i, j, k] = bm.verts.new(pt(a, z, s))
    faces = []
    for i in range(segs):
        faces.append(bm.faces.new([grid[i, 0, 1], grid[i + 1, 0, 1], grid[i + 1, 1, 1], grid[i, 1, 1]]))   # outer
        faces.append(bm.faces.new([grid[i, 1, 0], grid[i + 1, 1, 0], grid[i + 1, 0, 0], grid[i, 0, 0]]))   # inner
        faces.append(bm.faces.new([grid[i, 1, 1], grid[i + 1, 1, 1], grid[i + 1, 1, 0], grid[i, 1, 0]]))   # top
        faces.append(bm.faces.new([grid[i, 0, 0], grid[i + 1, 0, 0], grid[i + 1, 0, 1], grid[i, 0, 1]]))   # bottom
    for i in (0, segs):
        faces.append(bm.faces.new([grid[i, 0, 0], grid[i, 0, 1], grid[i, 1, 1], grid[i, 1, 0]]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return _finish(bm, list(grid.values()), colour)


# ------------------------------------------------------------------------------------------------ the parts (left side + centre)
def parts(B):
    """(object name, {bone: weight}, builder(bm)). B: rest-pose bones (Blender space)."""
    h = lambda n: B[n].head_local.copy()
    t = lambda n: B[n].tail_local.copy()
    P = []
    def add(name, bones, fn): P.append((name, bones if isinstance(bones, dict) else {bones: 1.0}, fn))
    V = Vector

    # --- hips, belt, pouches (pelvis)
    add("Hips", "pelvis", lambda bm: frustum(bm, (0, 0.0, 0.89), (0, 0.0, 1.02), (0.30, 0.22), (0.36, 0.25), "suit", bevel=0.025))
    add("Belt", "pelvis", lambda bm: box(bm, (0, 0.005, 1.035), (0.40, 0.28, 0.065), "belt", bevel=0.012))
    add("Buckle", "pelvis", lambda bm: box(bm, (0, -0.142, 1.035), (0.08, 0.02, 0.055), "trim", bevel=0.006))
    add("PouchA.l", "pelvis", lambda bm: box(bm, (0.085, -0.15, 1.005), (0.075, 0.055, 0.085), "belt", bevel=0.012))
    add("PouchB.l", "pelvis", lambda bm: box(bm, (0.158, -0.118, 1.005), (0.07, 0.055, 0.085), "belt", bevel=0.012))
    add("PouchFlapA.l", "pelvis", lambda bm: box(bm, (0.085, -0.157, 1.042), (0.087, 0.06, 0.024), "belt", bevel=0.006))
    add("PouchFlapB.l", "pelvis", lambda bm: box(bm, (0.158, -0.122, 1.042), (0.082, 0.06, 0.024), "belt", bevel=0.006))
    # --- abdomen and torso armour
    add("Abdomen", "stomach", lambda bm: frustum(bm, (0, 0.0, 1.05), (0, 0.01, 1.22), (0.30, 0.22), (0.33, 0.24), "suit", bevel=0.025))
    add("Chest", "chest", lambda bm: frustum(bm, (0, 0.0, 1.19), (0, 0.03, 1.52), (0.36, 0.26), (0.46, 0.31), "armor", bevel=0.04, segments=1))
    add("ChestPlate", "chest", lambda bm: plate(bm, (0, 0, 1.23), (0, 0.02, 1.46), (0.30, 0.03), (0.38, 0.03), "armor", offset=0.145, bevel=0.012, trim=0.012))
    add("BackPlate", "chest", lambda bm: frustum(bm, (0, 0.03, 1.24), (0, 0.06, 1.48), (0.32, 0.04), (0.38, 0.04), "armor", face=V((0, 1, 0)), offset=0.13, bevel=0.012))
    add("Collar", "chest", lambda bm: cylinder(bm, (0, 0.06, 1.49), (0, 0.07, 1.585), 0.16, 0.13, "armor", sides=12))
    add("CollarTrim", "chest", lambda bm: cylinder(bm, (0, 0.07, 1.578), (0, 0.071, 1.597), 0.134, 0.126, "trim", sides=12))
    # --- helmet (head), 10% smaller than block-out 1
    add("Helmet", "head", lambda bm: ellipsoid(bm, (0, 0.04, 1.722), (0.136, 0.150, 0.145), "armor", segs=14, rings=9))
    add("HelmetStripe", "head", lambda bm: ellipsoid(bm, (0, 0.04, 1.724), (0.02, 0.152, 0.147), "trim", segs=8, rings=9))
    add("Brow", "head", lambda bm: shell(bm, (0, 0.04, 1.722), (0.136, 0.150, 0.145), 1.738, 1.770, -64, 64, 0.97, 1.075, "armor", segs=12))
    add("Visor", "head", lambda bm: shell(bm, (0, 0.04, 1.722), (0.136, 0.150, 0.145), 1.686, 1.735, -56, 56, 0.95, 1.015, "visor", segs=12))
    # jaw guard: a shell wrapping the lower face, a raised centre plate, two vent slots on each side (Terr4's note)
    add("Jaw", "head", lambda bm: shell(bm, (0, 0.04, 1.722), (0.136, 0.150, 0.145), 1.600, 1.690, -72, 72, 0.93, 1.07, "armor", segs=12))
    add("JawPlate", "head", lambda bm: shell(bm, (0, 0.04, 1.722), (0.136, 0.150, 0.145), 1.595, 1.675, -18, 18, 1.0, 1.13, "armor", segs=4))
    add("Vent1.l", "head", lambda bm: shell(bm, (0, 0.04, 1.722), (0.136, 0.150, 0.145), 1.648, 1.660, 30, 48, 1.0, 1.085, "dark", segs=3))
    add("Vent2.l", "head", lambda bm: shell(bm, (0, 0.04, 1.722), (0.136, 0.150, 0.145), 1.625, 1.637, 30, 48, 1.0, 1.085, "dark", segs=3))
    add("Ear.l", "head", lambda bm: shell(bm, (0, 0.04, 1.722), (0.136, 0.150, 0.145), 1.645, 1.765, 69, 112, 0.97, 1.065, "armor", segs=4))
    # --- arms
    # pauldron: a thick plate sloping from the collar down and out over the shoulder, its front facing up and out
    slope_in = lambda: h("upper_arm.l") + V((-0.055, 0.0, 0.075)); slope_out = lambda: h("upper_arm.l") + V((0.115, 0.0, -0.045))
    add("Pauldron.l", "upper_arm.l", lambda bm: plate(bm, slope_in(), slope_out(), (0.25, 0.075), (0.27, 0.08), "armor",
                                                         face=V((0.5, 0.0, 1.0)).normalized(), offset=0.0, bevel=0.03, trim=0.012))
    add("PauldronSkirt.l", "upper_arm.l", lambda bm: plate(bm, h("upper_arm.l") + V((0.115, 0.0, -0.03)), h("upper_arm.l") + V((0.105, 0.0, -0.16)),
                                                              (0.24, 0.05), (0.21, 0.045), "armor", face=OUT, offset=0.0, bevel=0.025, trim=0.01))
    add("UpperArm.l", "upper_arm.l", lambda bm: cylinder(bm, h("upper_arm.l") + V((0, 0, -0.02)), t("upper_arm.l") + (t("upper_arm.l") - h("upper_arm.l")).normalized() * 0.03, 0.072, 0.062, "suit", sides=10))
    add("Elbow.l", {"upper_arm.l": 0.5, "lower_arm.l": 0.5}, lambda bm: ellipsoid(bm, h("lower_arm.l"), (0.07, 0.07, 0.07), "suit", segs=10, rings=6))
    add("Gauntlet.l", "lower_arm.l", lambda bm: plate(bm, h("lower_arm.l").lerp(t("lower_arm.l"), 0.1), h("lower_arm.l").lerp(t("lower_arm.l"), 0.92),
                                                        (0.13, 0.135), (0.115, 0.12), "armor", face=FWD, bevel=0.022))
    add("GauntletTrim.l", "lower_arm.l", lambda bm: frustum(bm, h("lower_arm.l").lerp(t("lower_arm.l"), 0.06), h("lower_arm.l").lerp(t("lower_arm.l"), 0.13),
                                                             (0.137, 0.142), (0.135, 0.14), "trim", bevel=0.01))
    add("Cuff.l", "hand.l", lambda bm: frustum(bm, h("hand.l") + V((0, 0, 0.025)), h("hand.l") + V((0.005, -0.005, -0.035)), (0.10, 0.12), (0.095, 0.115), "dark", bevel=0.015))
    add("Palm.l", "hand.l", lambda bm: frustum(bm, h("hand.l") + V((0.004, -0.004, -0.02)), B["finger2.1.l"].head_local + V((0, 0, 0.0)),
                                                 (0.065, 0.115), (0.06, 0.12), "dark", face=FWD, bevel=0.015))
    for f in ("finger1", "finger2", "finger3", "finger4"):
        for s, (w, d) in (("1", (0.034, 0.03)), ("2", (0.031, 0.028)), ("3", (0.028, 0.026))):
            bn = "%s.%s.l" % (f, s)
            add("%s%s.l" % (f.capitalize(), s), bn, lambda bm, bn=bn, w=w, d=d: frustum(bm, h(bn) - (t(bn) - h(bn)).normalized() * 0.006, t(bn), (w, d), (w * 0.95, d * 0.95), "dark", bevel=0.006))
    for s, (w, d) in (("1", (0.034, 0.032)), ("2", (0.03, 0.028))):
        bn = "thumb.%s.l" % s
        add("Thumb%s.l" % s, bn, lambda bm, bn=bn, w=w, d=d: frustum(bm, h(bn), t(bn) + (t(bn) - h(bn)).normalized() * 0.012, (w, d), (w * 0.9, d * 0.9), "dark", bevel=0.006))
    # --- legs
    knee = lambda: h("calf.l"); ankle = V((0.188, 0.045, 0.16))
    add("Thigh.l", "thigh.l", lambda bm: cylinder(bm, h("thigh.l") + V((0, 0, 0.04)), knee(), 0.105, 0.082, "suit", sides=10))
    add("ThighPlate.l", "thigh.l", lambda bm: plate(bm, h("thigh.l").lerp(knee(), 0.08), h("thigh.l").lerp(knee(), 0.66), (0.15, 0.035), (0.13, 0.035),
                                                       "armor", face=(OUT + FWD * 0.7).normalized(), offset=0.072, bevel=0.015, trim=0.012))
    add("Knee.l", {"thigh.l": 0.5, "calf.l": 0.5}, lambda bm: ellipsoid(bm, knee(), (0.07, 0.072, 0.072), "suit", segs=10, rings=6))
    add("KneePad.l", "calf.l", lambda bm: ellipsoid(bm, knee() + V((0.0, -0.07, 0.005)), (0.076, 0.045, 0.082), "boot", segs=10, rings=6))
    add("Shin.l", "calf.l", lambda bm: cylinder(bm, knee(), ankle, 0.078, 0.066, "suit", sides=10))
    add("ShinGuard.l", "calf.l", lambda bm: plate(bm, knee().lerp(ankle, 0.16), knee().lerp(ankle, 0.82), (0.135, 0.045), (0.12, 0.045),
                                                     "armor", face=FWD, offset=0.068, bevel=0.015))
    add("ShinStrap.l", "calf.l", lambda bm: frustum(bm, knee().lerp(ankle, 0.55), knee().lerp(ankle, 0.62), (0.165, 0.165), (0.16, 0.16), "belt", bevel=0.01))
    add("BootShaft.l", "calf.l", lambda bm: frustum(bm, V((0.192, 0.035, 0.10)), V((0.19, 0.04, 0.27)), (0.16, 0.19), (0.15, 0.17), "boot", bevel=0.022))
    add("Boot.l", "foot.l", lambda bm: box(bm, (0.193, 0.02, 0.065), (0.16, 0.22, 0.11), "boot", bevel=0.025))
    add("Toe.l", "toe.l", lambda bm: frustum(bm, V((0.193, -0.05, 0.055)), V((0.193, -0.135, 0.045)), (0.155, 0.11), (0.145, 0.08), "boot", face=V((0, 0, 1)), bevel=0.025))
    add("Sole.l", "foot.l", lambda bm: box(bm, (0.193, -0.01, 0.015), (0.165, 0.31, 0.03), "sole", bevel=0.008))
    return P


def _mirror_name(n):
    return n[:-2] + ".r" if n.endswith(".l") else n


def _shade(me):
    bm = bmesh.new(); bm.from_mesh(me)
    lim = math.radians(SHARP_DEG)
    for f in bm.faces: f.smooth = True
    for e in bm.edges:
        e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim) and len(e.link_faces) == 2
    bm.to_mesh(me); bm.free()


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
    for name, bones, fn in parts(rig.data.bones):
        for side in ((False, True) if name.endswith(".l") else (False,)):
            bm = bmesh.new()
            fn(bm)
            if side:
                bmesh.ops.scale(bm, vec=(-1, 1, 1), verts=bm.verts)
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
            nm = _mirror_name(name) if side else name
            me = bpy.data.meshes.new(nm); bm.to_mesh(me); bm.free()
            _shade(me)
            ob = bpy.data.objects.new(nm, me); col.objects.link(ob)
            u = me.uv_layers[0].data[0].uv
            sw = min(PALETTE, key=lambda k: (Vector(swatch_uv(k)) - Vector(u)).length)
            me.materials.append(mats[sw])
            for bn, w in bones.items():
                vg = ob.vertex_groups.new(name=_mirror_name(bn) if side else bn)
                vg.add(range(len(me.vertices)), w, "REPLACE")
            ob.parent = rig
            mod = ob.modifiers.new("Armature", "ARMATURE"); mod.object = rig
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

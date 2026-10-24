"""
The Helldiver, built from scratch on Commando's rig (rig.py), following art/concept/final_turnaround.png and art/DESIGN.md.

    import sys; sys.path.insert(0, r"<repo>/tools/art"); import character; character.build_body()

Body: one continuous mesh. A vertex skeleton through Commando's joints (NODES, EDGES) gets a Skin modifier (quad tubes with an edge
loop at every node, so every joint can bend) and a Subdivision level, then the result is applied into the mesh "Body" and bound to
the rig with heat weights (blender-character-rigging bind_mesh.py). Armour, helmet, belt and boots' hard parts are separate meshes
fitted to this body (fitted later in this file).

Blender space: z up, the character faces -y, its left side is +x. Radii are (x, y) in metres before subdivision (Catmull-Clark
shrinks a skin tube by roughly a quarter, so they are larger than the finished body).
"""
import bpy
import bmesh
from mathutils import Vector

RIG = "HelldiverRig"
COLLECTION = "Helldiver"
SKIN_SCALE = 1.0
BODY_CUT_Z = 0.14         # the body ends here, inside the boot shafts
NO_DEFORM = {"base"}       # behind the hips; Commando's mesh doesn't use it either
RIGGING_SKILL = r"C:\Users\Terr4\.claude\skills\blender-character-rigging\scripts"


def _bones():
    B = bpy.data.objects[RIG].data.bones
    return (lambda n: B[n].head_local.copy()), (lambda n: B[n].tail_local.copy())


def skeleton():
    """(nodes {name: (pos, (rx, ry))}, edges [(a, b)], root name)."""
    H, T = _bones()
    N, E = {}, []
    def node(n, p, r): N[n] = (Vector(p), r)
    def chain(*ns):
        for a, b in zip(ns, ns[1:]): E.append((a, b))
    # torso: wide ribcage and shoulders, narrow waist (concept), neck ends inside the helmet
    node("pelvis", (0, 0.005, 0.95), (0.218, 0.16))
    node("waist", (0, 0.005, 1.07), (0.215, 0.158))
    node("belly", (0, 0.01, 1.19), (0.225, 0.162))
    node("chest", (0, 0.03, 1.33), (0.24, 0.17))
    node("upchest", (0, 0.05, 1.46), (0.24, 0.165))
    node("neck0", (0, 0.07, 1.56), (0.095, 0.09))
    node("neck1", (0, 0.072, 1.66), (0.08, 0.078))
    chain("pelvis", "waist", "belly", "chest", "upchest", "neck0", "neck1")
    for s, sx in (("l", 1), ("r", -1)):
        P = lambda v, sx=sx: Vector((v[0] * sx, v[1], v[2]))
        sh, el, wr = H("upper_arm.l"), H("lower_arm.l"), H("hand.l")
        node("shoulder." + s, P(sh + Vector((-0.012, -0.004, -0.012))), (0.098, 0.1))
        node("bicep." + s, P(sh.lerp(el, 0.5)), (0.085, 0.085))
        node("elbow." + s, P(el), (0.075, 0.075))
        node("forearm." + s, P(el.lerp(wr, 0.45)), (0.08, 0.077))
        node("wrist." + s, P(wr + Vector((0, 0, 0.012))), (0.06, 0.055))
        node("palm." + s, P(H("hand.l").lerp(H("finger2.1.l"), 0.55)), (0.056, 0.08))
        chain("upchest", "shoulder." + s, "bicep." + s, "elbow." + s, "forearm." + s, "wrist." + s, "palm." + s)
        for f in ("finger1", "finger2", "finger3", "finger4"):
            ns = ["palm." + s]
            for k, r in (("1", 0.025), ("2", 0.023), ("3", 0.021)):
                n = "%s.%s.%s" % (f, k, s); node(n, P(H("%s.%s.l" % (f, k))), (r, r)); ns.append(n)
            n = "%s.tip.%s" % (f, s); node(n, P(T("%s.3.l" % f)), (0.017, 0.017)); ns.append(n)
            chain(*ns)
        ns = ["palm." + s]
        for k in ("1", "2"):
            n = "thumb.%s.%s" % (k, s); node(n, P(H("thumb.%s.l" % k)), (0.023, 0.023)); ns.append(n)
        n = "thumb.tip." + s; node(n, P(T("thumb.2.l")), (0.018, 0.018)); ns.append(n)
        chain(*ns)
        hip, kn = H("thigh.l"), H("calf.l")
        ankle = Vector((0.189, 0.062, 0.12))
        node("hip." + s, P((hip.x, hip.y, hip.z - 0.02)), (0.13, 0.13))
        node("thigh." + s, P(hip.lerp(kn, 0.5)), (0.115, 0.115))
        node("knee." + s, P(kn), (0.092, 0.095))
        node("calf." + s, P(kn.lerp(ankle, 0.42) + Vector((0, 0.012, 0))), (0.09, 0.095))
        node("ankle." + s, P(ankle), (0.088, 0.092))
        node("instep." + s, P((0.191, -0.035, 0.05)), (0.1, 0.085))
        node("toe." + s, P((0.193, -0.145, 0.034)), (0.096, 0.06))
        chain("pelvis", "hip." + s, "thigh." + s, "knee." + s, "calf." + s, "ankle." + s, "instep." + s, "toe." + s)
    return N, E, "pelvis"


def base_skin(name="BaseSkin", subdiv=1):
    """The skin-chain object (modifiers live, for tuning). Returns the object."""
    N, E, root = skeleton()
    names = list(N)
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(N[n][0]) for n in names], [(names.index(a), names.index(b)) for a, b in E], [])
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    sk = ob.modifiers.new("Skin", "SKIN"); sk.use_smooth_shade = True; sk.branch_smoothing = 1.0
    for i, n in enumerate(names):
        r = N[n][1]; me.skin_vertices[0].data[i].radius = (r[0] * SKIN_SCALE, r[1] * SKIN_SCALE)
    me.skin_vertices[0].data[names.index(root)].use_root = True
    sub = ob.modifiers.new("Subdiv", "SUBSURF"); sub.levels = subdiv; sub.render_levels = subdiv
    return ob


def tris(ob):
    dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); m = ev.to_mesh()
    n = sum(len(p.vertices) - 2 for p in m.polygons); ev.to_mesh_clear(); return n


# ------------------------------------------------------------------------------------------------ helmet
import math

HELMET_C = Vector((0.0, 0.035, 1.70))      # centre of the dome
HELMET_R = (0.126, 0.138, 0.148)           # half sizes x, y, z (smaller than block-out 1, per Terr4)
HELMET_P = 3.0                             # horizontal squareness (2 = round, higher = flatter sides)
HELMET_Q = 2.1 
HELMET_SHARP_DEG = 20.0                     # crease angle on the helmet's faceted parts
HELMET_FLARE = 0.16                         # how much the lower half flares outward                            # vertical squareness


def _se(t, e):
    return math.copysign(abs(t) ** e, t)


def helmet_point(az, el, s=1.0):
    """Point on the helmet surface: az = degrees around z from the front (-y) toward +x, el = degrees above the centre."""
    a, e = math.radians(az), math.radians(el)
    ce, se_ = math.cos(e), math.sin(e)
    flare = 1.0 + HELMET_FLARE * max(0.0, -se_)          # the lower half widens into the jaw guards (concept front view)
    x = HELMET_R[0] * s * flare * _se(ce, 2 / HELMET_Q) * _se(math.sin(a), 2 / HELMET_P)
    y = -HELMET_R[1] * s * flare * _se(ce, 2 / HELMET_Q) * _se(math.cos(a), 2 / HELMET_P)
    z = HELMET_R[2] * s * _se(se_, 2 / HELMET_Q)
    return HELMET_C + Vector((x, y, z))


def el_at(z):
    """Elevation (degrees) whose helmet height is z (at any azimuth)."""
    t = max(-1.0, min(1.0, (z - HELMET_C.z) / HELMET_R[2]))
    return math.degrees(math.asin(_se(t, HELMET_Q / 2)))


def surface_patch(bm, az0, az1, z0, z1, s_in, s_out, segs=12, rows=3):
    """A slab lying on the helmet: azimuth az0..az1, height z0..z1, from s_in to s_out times the helmet size. s_out may be a
    function (az, z) -> scale, for shaped plates (the jaw guard's raised centre)."""
    so = s_out if callable(s_out) else (lambda a, z: s_out)
    si = s_in if callable(s_in) else (lambda a, z: s_in)
    G = {}
    for i in range(segs + 1):
        a = az0 + (az1 - az0) * i / segs
        for j in range(rows + 1):
            z = z0 + (z1 - z0) * j / rows
            G[i, j, 0] = bm.verts.new(helmet_point(a, el_at(z), si(a, z)))
            G[i, j, 1] = bm.verts.new(helmet_point(a, el_at(z), so(a, z)))
    F = []
    for i in range(segs):
        for j in range(rows):
            F.append(bm.faces.new([G[i, j, 1], G[i + 1, j, 1], G[i + 1, j + 1, 1], G[i, j + 1, 1]]))
            F.append(bm.faces.new([G[i, j + 1, 0], G[i + 1, j + 1, 0], G[i + 1, j, 0], G[i, j, 0]]))
    for i in range(segs):
        for j, (k0, k1) in ((0, (0, 1)), (rows, (1, 0))):
            F.append(bm.faces.new([G[i, j, k0], G[i + 1, j, k0], G[i + 1, j, k1], G[i, j, k1]]))
    for i, d in ((0, 1), (segs, -1)):
        for j in range(rows):
            F.append(bm.faces.new([G[i, j, 0], G[i, j + 1, 0], G[i, j + 1, 1], G[i, j, 1]]))
    bmesh.ops.recalc_face_normals(bm, faces=F)
    return list(G.values())


def helmet_dome(bm, segs=20, rings=9, bottom_z=1.585):
    """The dome: a superellipsoid cap from bottom_z up, closed at the top, open below."""
    el0 = el_at(bottom_z)
    rows = []
    for j in range(rings):
        el = el0 + (89.0 - el0) * j / (rings - 1)
        rows.append([bm.verts.new(helmet_point(360.0 * i / segs, el)) for i in range(segs)])
    top = bm.verts.new(helmet_point(0, 90))
    F = []
    for j in range(rings - 1):
        for i in range(segs):
            F.append(bm.faces.new([rows[j][i], rows[j][(i + 1) % segs], rows[j + 1][(i + 1) % segs], rows[j + 1][i]]))
    for i in range(segs):
        F.append(bm.faces.new([rows[-1][i], rows[-1][(i + 1) % segs], top]))
    bmesh.ops.recalc_face_normals(bm, faces=F)
    # a thin inner wall so the open bottom isn't see-through: extrude the rim inward
    rim = [e for e in bm.edges if e.is_boundary]
    r = bmesh.ops.extrude_edge_only(bm, edges=rim)
    for v in [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]:
        v.co = HELMET_C + (v.co - HELMET_C) * 0.9 + Vector((0, 0, 0.012))
    return list(bm.verts)


def hp(az, z, s):
    """Helmet-space point from (azimuth, height, scale)."""
    return helmet_point(az, el_at(z), s)


def quad_slab(bm, corners, thickness, colour, uvl=None, inward=True):
    """A flat-faced slab from 4 corner points (counter-clockwise seen from outside): the front face is the quad, the back face
    sits `thickness` toward the helmet centre. Faceted on purpose (the concept's angular mask plates)."""
    uvl = uvl or bm.loops.layers.uv.verify()
    front = [bm.verts.new(c) for c in corners]
    back = [bm.verts.new(c + (HELMET_C - c).normalized() * thickness) for c in corners]
    F = [bm.faces.new(front), bm.faces.new(list(reversed(back)))]
    for i in range(4):
        j = (i + 1) % 4
        F.append(bm.faces.new([front[j], front[i], back[i], back[j]]))
    bmesh.ops.recalc_face_normals(bm, faces=F)
    for f in F: _uv_face(f, uvl, colour)
    return front + back


def _bilerp(q, u, v):
    """Point at (u, v) in a quad (p00, p10, p11, p01)."""
    p00, p10, p11, p01 = q
    return (p00 * (1 - u) + p10 * u) * (1 - v) + (p01 * (1 - u) + p11 * u) * v


def _cheek(sx):
    """Left (sx = 1) or right (sx = -1) cheek plate corners: from beside the centre plate back toward the ear, its lower edge
    rising diagonally toward the jaw corner (concept side view)."""
    return [hp(sx * 15, 1.596, 1.135), hp(sx * 58, 1.626, 1.035), hp(sx * 56, 1.694, 1.05), hp(sx * 18.5, 1.696, 1.098)]


# goggle opening (Terr4: "snowboard goggles", slightly lower than the surrounding shell): bottom edge with a nose notch in the
# middle and ends curving up, top edge drooping at the ends; columns every 10 degrees, the opening spans -60..60
GOG_HALF = 60.0
def gog_bottom(az):
    t = abs(az) / GOG_HALF
    return 1.684 + 0.017 * math.exp(-(az / 10.0) ** 2) + 0.02 * t ** 3
def gog_top(az):
    t = abs(az) / GOG_HALF
    return 1.738 - 0.012 * t ** 3


def _shell_scale(az, z):
    """How far the helmet shell sits from the dome (1 = dome). Piecewise linear on purpose, so the face reads as flat planes:
    a centre front plane (|az| <= 20) and two cheek planes falling back to the sides, a horizontal crease under the goggles and a
    chamfered chin; a brow bulge over the goggles; and the lower flange: a crisp ledge at z 1.64, then straight down."""
    a = abs(((az + 180) % 360) - 180)
    front = max(0.0, min(1.0, (75.0 - a) / 55.0))
    face = 0.15 * front * max(0.0, min(1.0, (1.70 - z) / 0.035))
    chin = 0.04 * front * max(0.0, min(1.0, (1.612 - z) / 0.022))
    brow = 0.055 * front * max(0.0, 1.0 - abs(z - 1.748) / 0.016)
    flare = 0.07 * max(0.0, min(1.0, (1.6405 - z) / 0.004)) + 0.022 * max(0.0, min(1.0, (1.62 - z) / 0.04))
    return 1.0 + face - chin + brow + flare


SHELL_COLS = 36
SHELL_ROWS_Z = [1.574, 1.590, 1.606, 1.612, 1.622, 1.6365, 1.6405, 1.656, 1.665, 1.672, None, None, 1.756, 1.772]   # None = goggle bottom / top rows


def _shell_rows():
    rows = []
    for z in SHELL_ROWS_Z: rows.append(z)
    top_el = el_at(1.79)
    for k in range(6): rows.append(("el", top_el + (88.0 - top_el) * k / 5))
    return rows


def _shell_point(az, row, s_extra=0.0):
    if row is None: raise ValueError
    if isinstance(row, tuple):
        el = row[1]; p = helmet_point(az, el, 1.0)
        return HELMET_C + (p - HELMET_C) * (_shell_scale(az, p.z) + s_extra)
    z = row
    return HELMET_C + (helmet_point(az, el_at(z), 1.0) - HELMET_C) * (_shell_scale(az, z) + s_extra)


def helmet_shell(bm, part="shell"):
    """part "shell": the helmet in one piece (dome, face, brow, lower flare) with the goggle opening cut out and its inner walls
    stepping 15 mm in; part "glass": the recessed goggle glass filling the opening."""
    uvl = bm.loops.layers.uv.verify()
    azs = [-180.0 + 360.0 * i / SHELL_COLS for i in range(SHELL_COLS)]
    rows = _shell_rows()
    ib, it = SHELL_ROWS_Z.index(None), SHELL_ROWS_Z.index(None) + 1
    def row_z(j, az):
        if j == ib: return gog_bottom(max(-GOG_HALF, min(GOG_HALF, az)))
        if j == it: return gog_top(max(-GOG_HALF, min(GOG_HALF, az)))
        return rows[j]
    def inside(az): return -GOG_HALF - 1e-6 <= az <= GOG_HALF + 1e-6
    if part == "glass":
        cols = [a for a in azs if inside(a)]
        G = {}
        for i, az in enumerate(cols):
            for j in (ib, it):
                G[i, j] = bm.verts.new(_shell_point(az, row_z(j, az), -0.015 / 0.13))
        F = [bm.faces.new([G[i, ib], G[i + 1, ib], G[i + 1, it], G[i, it]]) for i in range(len(cols) - 1)]
        for f in F: _uv_face(f, uvl, "visor")
        bmesh.ops.recalc_face_normals(bm, faces=F)
        for f in F:
            if f.normal.dot(f.calc_center_median() - HELMET_C) < 0: f.normal_flip()
        return list(bm.verts)
    G = {}
    for j in range(len(rows)):
        for i, az in enumerate(azs):
            G[i, j] = bm.verts.new(_shell_point(az, row_z(j, az)))
    top = bm.verts.new(helmet_point(0, 90, 1.0))
    F = []
    for j in range(len(rows) - 1):
        for i in range(SHELL_COLS):
            k = (i + 1) % SHELL_COLS
            a0, a1 = azs[i], azs[k] if k else 180.0
            if j == ib and inside(a0) and inside(a1 if k else 180.0) and a1 > a0: continue      # the goggle opening
            F.append(bm.faces.new([G[i, j], G[k, j], G[k, j + 1], G[i, j + 1]]))
    for i in range(SHELL_COLS):
        F.append(bm.faces.new([G[i, len(rows) - 1], G[(i + 1) % SHELL_COLS, len(rows) - 1], top]))
    # goggle walls: from the opening's edge 15 mm inward to the glass
    gcols = [i for i, a in enumerate(azs) if inside(a)]
    inner = {}
    for i in gcols:
        for j in (ib, it):
            inner[i, j] = bm.verts.new(_shell_point(azs[i], row_z(j, azs[i]), -0.015 / 0.13))
    for i, i2 in zip(gcols, gcols[1:]):
        F.append(bm.faces.new([G[i, ib], inner[i, ib], inner[i2, ib], G[i2, ib]]))
        F.append(bm.faces.new([G[i2, it], inner[i2, it], inner[i, it], G[i, it]]))
    for i in (gcols[0], gcols[-1]):
        F.append(bm.faces.new([G[i, ib], G[i, it], inner[i, it], inner[i, ib]]))
    # a thin inner wall at the open bottom (the neck)
    rim = [G[i, 0] for i in range(SHELL_COLS)]
    rim_in = [bm.verts.new(HELMET_C + (v.co - HELMET_C) * 0.88 + Vector((0, 0, 0.01))) for v in rim]
    for i in range(SHELL_COLS):
        k = (i + 1) % SHELL_COLS
        F.append(bm.faces.new([rim[k], rim[i], rim_in[i], rim_in[k]]))
    bmesh.ops.recalc_face_normals(bm, faces=F)
    for f in F: _uv_face(f, uvl, "armor")
    return list(bm.verts)


def _vent(bm, sx, z, az0, az1):
    """A dark slot sunk into the lower flare at the front of the face (where the flare ends)."""
    e = 0.035                                   # ~4 mm proud of the shell
    c = [_shell_point(sx * az0, z - 0.005, e), _shell_point(sx * az1, z - 0.002, e),
         _shell_point(sx * az1, z + 0.006, e), _shell_point(sx * az0, z + 0.003, e)]
    return quad_slab(bm, c if sx > 0 else list(reversed(c)), 0.012, "dark")


def helmet_parts():
    """(name, colour, builder(bm), subdiv). All weighted 100% to the head bone.
    Concept (helmet sheet + Terr4's notes): one smooth shell whose face pushes forward below the goggles, a lower flare all the way
    round that ends at the front in the vents, recessed snowboard-goggle visor, raised centre strip with two yellow lines."""
    P = []
    P.append(("Helmet", "armor", lambda bm: helmet_shell(bm, "shell"), 0))
    P.append(("Visor", "visor", lambda bm: helmet_shell(bm, "glass"), 0))
    P.append(("HelmetRidge", "armor", lambda bm: (surface_patch(bm, -8, 8, 1.776, 1.842, 0.96, 1.025, segs=2, rows=4),
                                                  surface_patch(bm, 172, 188, 1.66, 1.842, 0.96, 1.025, segs=2, rows=6)), 0))
    for side, sx in (("l", 1), ("r", -1)):
        P.append(("HelmetLine." + side, "trim", lambda bm, sx=sx: (surface_patch(bm, sx * 8.5, sx * 11, 1.773, 1.842, 0.99, 1.02, segs=1, rows=4),
                                                                   surface_patch(bm, 180 - sx * 8.5, 180 - sx * 11, 1.66, 1.842, 0.99, 1.02, segs=1, rows=6)), 0))
        for k, z in enumerate((1.598, 1.612, 1.626)):
            P.append(("Vent%d.%s" % (k + 1, side), "dark", lambda bm, sx=sx, z=z: _vent(bm, sx, z, 36, 52), 0))
    return P


def build_helmet():
    import body as palette          # palette swatches and shading helpers live in body.py
    col = _collection()
    made = []
    for name, colour, fn, subdiv in helmet_parts():
        old = bpy.data.objects.get(name)
        if old: bpy.data.objects.remove(old, do_unlink=True)
        bm = bmesh.new(); fn(bm)
        palette._finish(bm, list(bm.verts), colour)
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me); col.objects.link(ob)
        me.materials.append(palette_material())
        if subdiv:
            m = ob.modifiers.new("Subdiv", "SUBSURF"); m.levels = subdiv; m.render_levels = subdiv
        if subdiv: 
            for p in me.polygons: p.use_smooth = True
        else:
            palette._shade(me, HELMET_SHARP_DEG)
        ob.vertex_groups.new(name="head").add(range(len(me.vertices)), 1.0, "REPLACE")
        ob.parent = bpy.data.objects[RIG]
        a = ob.modifiers.new("Armature", "ARMATURE"); a.object = bpy.data.objects[RIG]
        if subdiv: ob.modifiers.move(len(ob.modifiers) - 1, 0)      # armature first, then subdivision
        made.append(ob.name)
    return made


# ------------------------------------------------------------------------------------------------ armour fitted to the body
from mathutils.bvhtree import BVHTree


def body_bvh():
    """BVH of the body in its rest pose (world space), for projecting plates onto it."""
    ob = bpy.data.objects["Body"]
    rig = bpy.data.objects[RIG]; old = rig.data.pose_position; rig.data.pose_position = "REST"
    try:
        dg = bpy.context.evaluated_depsgraph_get(); dg.update()
        ev = ob.evaluated_get(dg); me = ev.to_mesh()
        verts = [ob.matrix_world @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
    finally:
        rig.data.pose_position = old
    return BVHTree.FromPolygons(verts, polys)


def _uv_face(f, uvl, colour):
    import body as palette
    u = palette.swatch_uv(colour)
    for l in f.loops: l[uvl].uv = u


def projected_plate(bm, bvh, center, normal, up, w, h, colour="armor", trim=None, squareness=4.0, thickness=0.02, gap=0.004,
                    taper=0.0, n=20, rings=(1.0, 0.86, 0.45), band=1, bulge=0.0, axis=None, poly=None, max_dist=1.0):
    """An armour plate whose outline (a superellipse w x h, optionally tapered toward the bottom) is drawn in the plane
    (center, normal, up), projected onto the body along -normal, lifted by gap and given a thickness. The outer `band` ring of
    the front face and the rim take the `trim` colour (the concept's yellow outlines). Returns the new verts."""
    uvl = bm.loops.layers.uv.verify()
    nrm = Vector(normal).normalized(); upv = Vector(up); upv = (upv - nrm * upv.dot(nrm)).normalized(); rgt = upv.cross(nrm)
    c = Vector(center)
    if poly is not None:
        pts = _poly_samples(poly, n)
        n = len(pts)
    def outline(t):
        if poly is not None:
            px, py = pts[int(round(t / (2 * math.pi) * n)) % n]
            return px * w, py * h
        x = 0.5 * w * math.copysign(abs(math.cos(t)) ** (2 / squareness), math.cos(t))
        y = 0.5 * h * math.copysign(abs(math.sin(t)) ** (2 / squareness), math.sin(t))
        if taper and y < 0: x *= 1.0 - taper * (-y / (0.5 * h))
        return x, y
    def place(x, y, k):
        o = c + rgt * x + upv * y + nrm * 0.5
        d_ray = -nrm
        if axis is not None:
            # cylindrical projection: from the body's axis line outward through the plate point, so the outline wraps a curved
            # torso by angle (the first hit from inside is the body's surface)
            a0, a1 = Vector(axis[0]), Vector(axis[1]); ad = (a1 - a0).normalized()
            pp = c + rgt * x + upv * y
            q = a0 + ad * (pp - a0).dot(ad)
            o, d_ray = q, (pp - q).normalized()
        hit, hn, _, _ = bvh.ray_cast(o, d_ray, max_dist)
        if hit is None: hit, hn = c + rgt * x + upv * y, nrm
        d = (hn * 0.5 + nrm * 0.5).normalized()
        back = hit + hn * gap
        return back, back + d * (thickness + bulge * k)
    R = []
    for k in rings:
        ring = []
        for i in range(n):
            x, y = outline(2 * math.pi * i / n)
            b, f = place(x * k, y * k, k)
            ring.append((bm.verts.new(b), bm.verts.new(f)))
        R.append(ring)
    cb, cf = place(0.0, 0.0, 1.0)
    cb, cf = bm.verts.new(cb), bm.verts.new(cf)
    tc = trim or colour
    for j in range(len(R) - 1):
        for i in range(n):
            a, b = R[j][i], R[j][(i + 1) % n]; a2, b2 = R[j + 1][i], R[j + 1][(i + 1) % n]
            ff = bm.faces.new([a[1], b[1], b2[1], a2[1]]); _uv_face(ff, uvl, tc if j < band else colour)
            fb = bm.faces.new([a2[0], b2[0], b[0], a[0]]); _uv_face(fb, uvl, colour)
    last = R[-1]
    for i in range(n):
        a, b = last[i], last[(i + 1) % n]
        _uv_face(bm.faces.new([a[1], b[1], cf]), uvl, colour)
        _uv_face(bm.faces.new([cb, b[0], a[0]]), uvl, colour)
    for i in range(n):
        a, b = R[0][i], R[0][(i + 1) % n]
        _uv_face(bm.faces.new([a[0], b[0], b[1], a[1]]), uvl, tc)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return list(bm.verts)


def _poly_samples(poly, n):
    """n points around a closed polygon (unit-size coordinates, counter-clockwise), every corner included, the rest spread by
    edge length, starting at the corner nearest angle 0 so the ring indexing matches the superellipse outline's."""
    import math as _m
    P = [Vector((x, y, 0)) for x, y in poly]
    start = min(range(len(P)), key=lambda i: abs(_m.atan2(P[i].y, P[i].x)))
    P = P[start:] + P[:start]
    L = [(P[(i + 1) % len(P)] - P[i]).length for i in range(len(P))]
    total = sum(L); extra = n - len(P)
    counts = [1 + int(round(extra * l / total)) for l in L]
    out = []
    for i, c in enumerate(counts):
        a, b = P[i], P[(i + 1) % len(P)]
        for k in range(c): out.append(tuple(a.lerp(b, k / c))[:2])
    return out


# concept outlines (unit size, counter-clockwise from the right): chamfered, straight-edged plates
POLY_CHEST = [(0.5, 0.32), (0.42, 0.5), (-0.42, 0.5), (-0.5, 0.32), (-0.42, -0.15), (-0.2, -0.5), (0.2, -0.5), (0.42, -0.15)]
POLY_BACK = [(0.5, 0.38), (0.42, 0.5), (-0.42, 0.5), (-0.5, 0.38), (-0.5, -0.38), (-0.4, -0.5), (0.4, -0.5), (0.5, -0.38)]
POLY_THIGH = [(0.5, 0.3), (0.28, 0.5), (-0.28, 0.5), (-0.5, 0.3), (-0.42, -0.28), (0.0, -0.5), (0.42, -0.28)]
POLY_SHIN = [(0.5, 0.42), (0.38, 0.5), (-0.38, 0.5), (-0.5, 0.42), (-0.5, -0.25), (-0.25, -0.5), (0.25, -0.5), (0.5, -0.25)]

POLY_SOLE = [(0.5, 0.2), (0.42, 0.42), (0.2, 0.5), (-0.2, 0.5), (-0.42, 0.42), (-0.5, 0.2), (-0.46, -0.32), (-0.3, -0.5), (0.3, -0.5), (0.46, -0.32)]
POLY_BUCKLE = [(0.5, 0.32), (0.38, 0.5), (-0.38, 0.5), (-0.5, 0.32), (-0.5, -0.32), (-0.38, -0.5), (0.38, -0.5), (0.5, -0.32)]


def oriented_box(bm, center, out, up, size, colour, chamfer=0.004):
    """A box at `center` whose depth (size[2]) runs along `out`, height (size[1]) along `up`; edges chamfered (hard-surface)."""
    from mathutils import Matrix
    z = Vector(out).normalized(); y = Vector(up); y = (y - z * y.dot(z)).normalized(); x = y.cross(z)
    rot = Matrix((x, y, z)).transposed().to_4x4()
    m = Matrix.Translation(Vector(center)) @ rot @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    vs = r["verts"]
    if chamfer > 0:
        edges = list({e for v in vs for e in v.link_edges})
        res = bmesh.ops.bevel(bm, geom=edges + vs, offset=min(chamfer, 0.45 * min(size)), segments=1, affect="EDGES", clamp_overlap=True)
        vs = list({v for v in vs if v.is_valid} | set(res["verts"]))
    uvl = bm.loops.layers.uv.verify()
    for f in {f for v in vs for f in v.link_faces}: _uv_face(f, uvl, colour)
    return vs


def surface_at(bvh, origin, direction):
    hit, hn, _, dist = bvh.ray_cast(Vector(origin), Vector(direction).normalized(), 1.0)
    return hit, hn


def region_shell(bm, faces_filter, offset, thickness, colour, trim_loops=None):
    """A sleeve or band: the body faces passing faces_filter(center, weights), pushed out by `offset` along their normals and
    given a thickness. Returns {new vert: body vert index} so the body's weights can be copied onto it."""
    body = bpy.data.objects["Body"]; me = body.data
    groups = {g.index: g.name for g in body.vertex_groups}
    uvl = bm.loops.layers.uv.verify()
    sel = []
    for p in me.polygons:
        w = {}
        for vi in p.vertices:
            for g in me.vertices[vi].groups: w[groups[g.group]] = w.get(groups[g.group], 0) + g.weight / len(p.vertices)
        if faces_filter(p.center, w): sel.append(p)
    vmap, back, front = {}, {}, {}
    for p in sel:
        for vi in p.vertices:
            if vi in back: continue
            v = me.vertices[vi]
            b = bm.verts.new(v.co + v.normal * offset); f = bm.verts.new(v.co + v.normal * (offset + thickness))
            back[vi], front[vi] = b, f; vmap[b] = vi; vmap[f] = vi
    edges = {}
    for p in sel:
        vs = list(p.vertices)
        _uv_face(bm.faces.new([front[i] for i in vs]), uvl, colour)
        _uv_face(bm.faces.new([back[i] for i in reversed(vs)]), uvl, colour)
        for a, b in zip(vs, vs[1:] + vs[:1]):
            k = (min(a, b), max(a, b)); edges[k] = edges.get(k, 0) + 1; edges.setdefault(("dir", k), (a, b))
    for k, cnt in list(edges.items()):
        if k[0] == "dir" or cnt != 1: continue
        a, b = edges[("dir", k)]
        _uv_face(bm.faces.new([back[a], back[b], front[b], front[a]]), uvl, trim_loops or colour)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return vmap


def cap_patch(bm, center, frame, radii, az0, az1, el0, el1, s_in, s_out, colour="armor", trim=None, trim_rows=0,
              segs=12, rows=6, p=2.4, q=2.2, bvh=None, gap=0.006, thickness=None):
    """A slab on a superellipsoid cap (pauldrons, knee pads): `frame` is a 3x3 matrix whose columns are the cap's local x, y, z
    (az = 0 looks along local -y). Rows from el0 (bottom) to el1; the lowest `trim_rows` rows and the rim take the trim colour."""
    from mathutils import Matrix
    uvl = bm.loops.layers.uv.verify()
    c = Vector(center); M = Matrix(frame) if not isinstance(frame, Matrix) else frame
    def pt(az, el, s):
        a, e = math.radians(az), math.radians(el)
        ce, se_ = math.cos(e), math.sin(e)
        loc = Vector((radii[0] * s * _se(ce, 2 / q) * _se(math.sin(a), 2 / p),
                      -radii[1] * s * _se(ce, 2 / q) * _se(math.cos(a), 2 / p),
                      radii[2] * s * _se(se_, 2 / q)))
        return c + M @ loc
    G = {}
    for i in range(segs + 1):
        az = az0 + (az1 - az0) * i / segs
        for j in range(rows + 1):
            el = el0 + (el1 - el0) * j / rows
            pi, po = pt(az, el, s_in), pt(az, el, s_out)
            if thickness is not None: po = pi + (pi - c).normalized() * thickness
            if bvh is not None:
                # keep the inner surface clear of the body: push it out to gap above the nearest body point
                hit, hn, _, _ = bvh.find_nearest(pi)
                if hit is not None and (pi - hit).dot(hn) < gap:
                    d = hit + hn * gap - pi; pi = pi + d; po = po + d
            G[i, j, 0] = bm.verts.new(pi); G[i, j, 1] = bm.verts.new(po)
    tc = trim or colour
    for i in range(segs):
        for j in range(rows):
            col = tc if j < trim_rows else colour
            _uv_face(bm.faces.new([G[i, j, 1], G[i + 1, j, 1], G[i + 1, j + 1, 1], G[i, j + 1, 1]]), uvl, col)
            _uv_face(bm.faces.new([G[i, j + 1, 0], G[i + 1, j + 1, 0], G[i + 1, j, 0], G[i, j, 0]]), uvl, colour)
    for i in range(segs):
        _uv_face(bm.faces.new([G[i, 0, 0], G[i + 1, 0, 0], G[i + 1, 0, 1], G[i, 0, 1]]), uvl, tc)
        _uv_face(bm.faces.new([G[i, rows, 1], G[i + 1, rows, 1], G[i + 1, rows, 0], G[i, rows, 0]]), uvl, colour)
    for i in (0, segs):
        for j in range(rows):
            _uv_face(bm.faces.new([G[i, j, 0], G[i, j + 1, 0], G[i, j + 1, 1], G[i, j, 1]]), uvl, tc)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return list(bm.verts)


def palette_material():
    """One material showing the palette texture (for previews in Material view; the game uses its own material)."""
    import os, body as palette
    path = os.path.join(os.path.dirname(bpy.data.filepath), "palette.png")
    palette.palette_png(path, 512)
    mat = bpy.data.materials.get("hd_palette") or bpy.data.materials.new("hd_palette")
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None) or nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.get("palette.png")
    if img: img.reload()
    else: img = bpy.data.images.load(path)
    tex.image = img; tex.interpolation = "Closest"
    if not tex.outputs["Color"].links: nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def _finish_object(name, bm, weights, subdiv=0, sharp=True, colour_for_material="armor"):
    """Mesh object in the character collection, parented to the rig with an Armature modifier. weights: {bone: w} for every vertex,
    or a callable(vert index) -> {bone: w}."""
    import body as palette
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); _collection().objects.link(ob)
    me.materials.append(palette_material())
    if sharp: palette._shade(me)
    else:
        for p in me.polygons: p.use_smooth = True
    if callable(weights):
        for v in me.vertices:
            for bn, w in weights(v.index).items():
                (ob.vertex_groups.get(bn) or ob.vertex_groups.new(name=bn)).add([v.index], w, "REPLACE")
    else:
        for bn, w in weights.items():
            ob.vertex_groups.new(name=bn).add(range(len(me.vertices)), w, "REPLACE")
    rig = bpy.data.objects[RIG]; ob.parent = rig
    a = ob.modifiers.new("Armature", "ARMATURE"); a.object = rig
    if subdiv:
        m = ob.modifiers.new("Subdiv", "SUBSURF"); m.levels = subdiv; m.render_levels = subdiv
    return ob


def _body_weights(vmap):
    """weights(new vert index) -> the body's weights at the vertex it was copied from."""
    body = bpy.data.objects["Body"]; me = body.data
    groups = {g.index: g.name for g in body.vertex_groups}
    order = list(vmap.values())          # bm vertex creation order == new mesh vertex order
    def w(i):
        vi = order[i]
        return {groups[g.group]: g.weight for g in me.vertices[vi].groups if g.weight > 1e-4}
    return w


def _collection():
    col = bpy.data.collections.get(COLLECTION)
    if not col:
        col = bpy.data.collections.new(COLLECTION); bpy.context.scene.collection.children.link(col)
    return col


def bind(names):
    """Heat weights to the rig's deform bones (blender-character-rigging bind_mesh.py: proxy fallback, 4 influences, normalised)."""
    import sys, importlib
    if RIGGING_SKILL not in sys.path: sys.path.insert(0, RIGGING_SKILL)
    import bind_mesh; importlib.reload(bind_mesh)
    return bind_mesh.run(armature=RIG, meshes=list(names))


def build_body(subdiv=2, target_tris=5500, do_bind=True):
    """Apply the skin chain into the mesh "Body" (collection COLLECTION) and bind it to the rig with heat weights."""
    rig = bpy.data.objects[RIG]
    for n in NO_DEFORM:
        if n in rig.data.bones: rig.data.bones[n].use_deform = False
    src = base_skin(subdiv=subdiv)
    # subdividing twice rounds off the skin's branch hulls (shoulders, crotch); decimate brings it back to the budget
    if target_tris:
        full = tris(src)
        dec = src.modifiers.new("Decimate", "DECIMATE"); dec.decimate_type = "COLLAPSE"; dec.ratio = min(1.0, target_tris / full)
        dec.use_symmetry = True; dec.symmetry_axis = "X"
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(src.evaluated_get(dg))
    old = bpy.data.objects.get("Body")
    if old: bpy.data.objects.remove(old, do_unlink=True)
    me.name = "Body"
    # decimation can leave loose verts and mixed winding: clean before binding
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # the boots (separate hard-surface meshes) cover the feet: drop the body below the ankles (hidden, and it poked through)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < BODY_CUT_Z and abs(v.co.x) > 0.06], context="VERTS")
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("Body", me); _collection().objects.link(ob)
    for p in me.polygons: p.use_smooth = True
    src.hide_set(True); src.hide_render = True
    out = {"tris": sum(len(p.vertices) - 2 for p in me.polygons), "verts": len(me.vertices)}
    if do_bind:
        out["bind"] = bind(["Body"])
        colour_body(ob)
    me.materials.clear(); me.materials.append(palette_material())
    return out


def colour_body(ob):
    """Palette UVs by region: gloves dark (faces weighted to the hands), boots grey with a dark sole, the rest suit grey."""
    import body as palette
    me = ob.data
    if not me.uv_layers: me.uv_layers.new(name="UVMap")
    uvl = me.uv_layers[0]
    groups = {g.index: g.name for g in ob.vertex_groups}
    for p in me.polygons:
        w = {}
        for vi in p.vertices:
            for g in me.vertices[vi].groups: w[groups[g.group]] = w.get(groups[g.group], 0) + g.weight
        hand = sum(v for k, v in w.items() if k.startswith(("hand", "finger", "thumb")))
        z = p.center.z
        col = "dark" if hand > 0.5 * len(p.vertices) else ("boot" if z < 0.185 else "suit")
        u = palette.swatch_uv(col)
        for li in p.loop_indices: uvl.data[li].uv = u



def wrap_band(bm, bvh, a, b, t0, t1, offset, thickness, colour="armor", segs=16, rings=3, trim=None, trim_top=False, trim_bottom=False,
              flare=0.0):
    """A band wrapped around the body along the axis a -> b, from t0 to t1 (fractions of the axis): each ring point is found by a
    ray cast from the axis outward to the body surface, then lifted by `offset`; the band has `thickness`. Clean parametric
    edges (belts, collars, gauntlets, cuffs). The top/bottom rim and outermost ring take the trim colour when asked. flare widens
    the band toward t1 (cuffs)."""
    uvl = bm.loops.layers.uv.verify()
    a, b = Vector(a), Vector(b)
    ax = (b - a).normalized()
    ref = Vector((0, -1, 0)) if abs(ax.dot(Vector((0, -1, 0)))) < 0.9 else Vector((1, 0, 0))
    u = (ref - ax * ref.dot(ax)).normalized(); v = ax.cross(u)
    G = {}
    for j in range(rings + 1):
        t = t0 + (t1 - t0) * j / rings
        o = a.lerp(b, t)
        for i in range(segs):
            ang = 2 * math.pi * i / segs
            d = (u * math.cos(ang) + v * math.sin(ang)).normalized()
            hit, hn, _, dist = bvh.ray_cast(o, d, 1.0)
            r = dist if hit is not None else 0.1
            extra = flare * (j / rings)
            pin = o + d * (r + offset + extra); pout = o + d * (r + offset + extra + thickness)
            G[i, j, 0] = bm.verts.new(pin); G[i, j, 1] = bm.verts.new(pout)
    tc = trim or colour
    for j in range(rings):
        for i in range(segs):
            i2 = (i + 1) % segs
            col = tc if ((trim_top and j == rings - 1) or (trim_bottom and j == 0)) else colour
            _uv_face(bm.faces.new([G[i, j, 1], G[i2, j, 1], G[i2, j + 1, 1], G[i, j + 1, 1]]), uvl, col)
            _uv_face(bm.faces.new([G[i, j + 1, 0], G[i2, j + 1, 0], G[i2, j, 0], G[i, j, 0]]), uvl, colour)
    for i in range(segs):
        i2 = (i + 1) % segs
        _uv_face(bm.faces.new([G[i, 0, 0], G[i2, 0, 0], G[i2, 0, 1], G[i, 0, 1]]), uvl, tc if trim_bottom else colour)
        _uv_face(bm.faces.new([G[i, rings, 1], G[i2, rings, 1], G[i2, rings, 0], G[i, rings, 0]]), uvl, tc if trim_top else colour)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return list(bm.verts)


def radial_shell(bm, bvh, center, frame, az0, az1, el0, el1, gap, thickness, colour="armor", trim=None, trim_rows=0,
                 segs=10, rows=5, bulge=0.0):
    """Armour that hugs the body: rays from `center` (a joint inside the body) along the directions (az, el) of `frame` find the
    body's surface; the inner face sits `gap` outside it and the outer face `thickness` (+ bulge in the middle) further out.
    az = 0 looks along the frame's local -y; the lowest `trim_rows` rows and the rim take the trim colour."""
    from mathutils import Matrix
    uvl = bm.loops.layers.uv.verify()
    c = Vector(center); M = frame
    G = {}
    for i in range(segs + 1):
        az = az0 + (az1 - az0) * i / segs
        for j in range(rows + 1):
            el = el0 + (el1 - el0) * j / rows
            a, e = math.radians(az), math.radians(el)
            d = (M @ Vector((math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e)))).normalized()
            hit, hn, _, dist = bvh.ray_cast(c, d, 1.0)
            r = dist if hit is not None else 0.08
            mid = math.sin(math.pi * i / segs) * math.sin(math.pi * j / rows)
            G[i, j, 0] = bm.verts.new(c + d * (r + gap)); G[i, j, 1] = bm.verts.new(c + d * (r + gap + thickness + bulge * mid))
    tc = trim or colour
    for i in range(segs):
        for j in range(rows):
            col = tc if j < trim_rows else colour
            _uv_face(bm.faces.new([G[i, j, 1], G[i + 1, j, 1], G[i + 1, j + 1, 1], G[i, j + 1, 1]]), uvl, col)
            _uv_face(bm.faces.new([G[i, j + 1, 0], G[i + 1, j + 1, 0], G[i + 1, j, 0], G[i, j, 0]]), uvl, colour)
    for i in range(segs):
        _uv_face(bm.faces.new([G[i, 0, 0], G[i + 1, 0, 0], G[i + 1, 0, 1], G[i, 0, 1]]), uvl, tc)
        _uv_face(bm.faces.new([G[i, rows, 1], G[i + 1, rows, 1], G[i + 1, rows, 0], G[i, rows, 0]]), uvl, colour)
    for i in (0, segs):
        for j in range(rows):
            _uv_face(bm.faces.new([G[i, j, 0], G[i, j + 1, 0], G[i, j + 1, 1], G[i, j, 1]]), uvl, tc)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return list(bm.verts)


# ------------------------------------------------------------------------------------------------ the armour set
def _frame(outward, up):
    """Cap frame whose az = 0 looks along `outward` and whose top is `up` (columns x, y, z)."""
    from mathutils import Matrix
    zl = Vector(up).normalized(); yl = -Vector(outward); yl = (yl - zl * yl.dot(zl)).normalized(); xl = yl.cross(zl)
    return Matrix((xl, yl, zl)).transposed()


def _mirror_bm(bm):
    bmesh.ops.scale(bm, vec=(-1, 1, 1), verts=bm.verts)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)


def build_armor():
    """Every armour piece, fitted to the current body. Left-side pieces are built, then mirrored for the right."""
    import body as palette
    rig = bpy.data.objects[RIG]; B = rig.data.bones
    H = lambda n: B[n].head_local.copy()
    bvh = body_bvh()
    made = []
    def obj(name, build, weights, subdiv=0, sharp=True, mirror=False):
        for side in (("l", False), ("r", True)) if mirror else ((None, False),):
            bm = bmesh.new()
            res = build(bm)
            nm = name if side[0] is None else "%s.%s" % (name, side[0])
            w = weights
            if side[1]:
                _mirror_bm(bm)
                if isinstance(w, dict): w = {k[:-2] + ".r" if k.endswith(".l") else k: v for k, v in w.items()}
            if callable(w) and getattr(w, "needs_vmap", False): w = w(res, side[1])
            made.append(_finish_object(nm, bm, w, subdiv=subdiv, sharp=sharp).name)
    # --- torso
    obj("ChestPlate", lambda bm: projected_plate(bm, bvh, (0, -0.15, 1.395), (0, -1, 0.1), (0, 0, 1), 0.95, 0.32, trim="trim",
                                                 thickness=0.024, bulge=0.004, n=40, poly=POLY_CHEST,
                                                 axis=((0, 0.03, 1.0), (0, 0.06, 1.6))), {"chest": 1.0})
    obj("BackPlate", lambda bm: projected_plate(bm, bvh, (0, 0.17, 1.38), (0, 1, 0.08), (0, 0, 1), 0.9, 0.28, poly=POLY_BACK, n=36,
                                                thickness=0.02, bulge=0.003, axis=((0, 0.03, 1.0), (0, 0.06, 1.6))), {"chest": 1.0})
    def shell_w(filter_fn, offset, thickness, colour, trim=None):
        def build(bm):
            return region_shell(bm, filter_fn, offset, thickness, colour, trim_loops=trim)
        return build
    def copy_weights(vmap, mirrored):
        w = _body_weights(vmap)
        if not mirrored: return w
        return lambda i: {k[:-2] + ".r" if k.endswith(".l") else (k[:-2] + ".l" if k.endswith(".r") else k): v for k, v in w(i).items()}
    copy_weights.needs_vmap = True
    obj("Collar", lambda bm: wrap_band(bm, bvh, (0, 0.07, 1.46), (0, 0.075, 1.62), 0.47, 0.86, 0.008, 0.02, "armor", segs=18, rings=3,
                                       trim="trim", trim_top=True, flare=-0.01), {"chest": 1.0}, sharp=True)
    obj("Belt", lambda bm: wrap_band(bm, bvh, (0, 0.005, 0.95), (0, 0.005, 1.15), 0.24, 0.58, 0.006, 0.022, "belt", segs=20, rings=2),
        {"pelvis": 1.0}, sharp=True)
    obj("Buckle", lambda bm: projected_plate(bm, bvh, (0, -0.15, 1.025), (0, -1, 0), (0, 0, 1), 0.08, 0.056, colour="trim", poly=POLY_BUCKLE,
                                             n=16, rings=(1.0, 0.5), thickness=0.014, gap=0.025), {"pelvis": 1.0})
    def pouches(bm):
        axis_o = Vector((0, 0.005, 1.02))
        for ang in (22, 52):
            d = Vector((math.sin(math.radians(ang)), -math.cos(math.radians(ang)), 0))
            hit, hn = surface_at(bvh, axis_o, d)
            base = hit + d * 0.026
            oriented_box(bm, base + d * 0.026 + Vector((0, 0, -0.012)), d, (0, 0, 1), (0.068, 0.082, 0.05), "belt", chamfer=0.006)
            oriented_box(bm, base + d * 0.03 + Vector((0, 0, 0.03)), d, (0, 0, 1), (0.074, 0.024, 0.06), "belt", chamfer=0.004)
            oriented_box(bm, base + d * 0.058 + Vector((0, 0, 0.012)), d, (0, 0, 1), (0.012, 0.016, 0.006), "trim", chamfer=0.0)
        return list(bm.verts)
    obj("Pouches", pouches, {"pelvis": 1.0}, mirror=True)
    # --- arms (left built, right mirrored)
    sh = H("upper_arm.l"); el = H("lower_arm.l"); wr = H("hand.l")
    # pauldron: hugs the shoulder; rays from the shoulder joint over the top and outer side of the deltoid
    obj("Pauldron", lambda bm: radial_shell(bm, bvh, sh + Vector((-0.02, 0.0, -0.02)), _frame((1, 0, 0), (0.35, 0, 1)), -60, 48, -20, 62,
                                            0.004, 0.022, "armor", trim="trim", trim_rows=1, segs=6, rows=3, bulge=0.006),
        {"upper_arm.l": 1.0}, sharp=True, mirror=True)
    obj("Gauntlet", lambda bm: wrap_band(bm, bvh, el, wr, 0.14, 0.97, 0.003, 0.013, "armor", segs=8, rings=2, flare=0.006),
        {"lower_arm.l": 1.0}, sharp=True, mirror=True)
    obj("GauntletRing", lambda bm: wrap_band(bm, bvh, el, wr, 0.06, 0.13, 0.012, 0.014, "trim", segs=12, rings=1),
        {"lower_arm.l": 1.0}, sharp=True, mirror=True)
    # --- legs
    hip = H("thigh.l"); kn = H("calf.l"); ank = Vector((0.189, 0.05, 0.13))
    tm = hip.lerp(kn, 0.42)
    obj("ThighPlate", lambda bm: projected_plate(bm, bvh, tm + Vector((0.07, -0.07, 0)), (0.72, -0.69, 0), (kn - hip).normalized() * -1, 0.13, 0.23,
                                                 trim="trim", poly=POLY_THIGH, n=28, thickness=0.02, bulge=0.003, gap=0.002), {"thigh.l": 1.0}, mirror=True)
    obj("KneePad", lambda bm: radial_shell(bm, bvh, kn + Vector((0, 0.01, 0.0)), _frame((0, -1, 0), (0, 0, 1)), -48, 48, -38, 42,
                                           0.009, 0.018, "boot", segs=8, rows=5, bulge=0.014),
        {"calf.l": 1.0}, sharp=False, mirror=True)
    made += build_boots()
    return made


def _thicken_cap(bm, thickness):
    """cap_patch built with s_in == s_out: move each outer vertex out along the cap's normal by `thickness`."""
    bm.normal_update()
    n = len(bm.verts) // 2
    vs = list(bm.verts)
    for k in range(0, len(vs), 2):
        vin, vout = vs[k], vs[k + 1]
        d = vout.normal if vout.normal.length > 0 else Vector((0, 0, 1))
        vout.co = vin.co + d * thickness
    bm.normal_update()
    return vs



def _clear_scale(bvh, center, frame, radii, az0, az1, el0, el1, clearance, p=2.4, q=2.2):
    """Smallest scale (>= 1) of a cap whose inner surface stays `clearance` outside the body (checked at the cap's sample points)."""
    k = 1.0
    for _ in range(40):
        bm = bmesh.new()
        cap_patch(bm, center, frame, tuple(r * k for r in radii), az0, az1, el0, el1, 1.0, 1.0, segs=10, rows=5, p=p, q=q)
        worst = 1.0
        for v in bm.verts:
            hit, hn, _, _ = bvh.find_nearest(v.co)
            if hit is not None: worst = min(worst, (v.co - hit).dot(hn))
        bm.free()
        if worst >= clearance: return k
        k *= 1.03
    return k



def sole_prism(bm, z0, z1, grow, n=20, colour="sole"):
    """A boot sole: the left foot's outline (convex hull of the body's vertices below the ankle, x > 0.1) grown by `grow`,
    extruded from z0 to z1 with straight sides. Clean and flat, with no projection."""
    body = bpy.data.objects["Body"]
    pts = [(v.co.x, v.co.y) for v in body.data.vertices if v.co.x > 0.1 and v.co.z < 0.1]
    import numpy as np
    P = np.array(pts)
    # convex hull (monotone chain)
    P = P[np.lexsort((P[:, 1], P[:, 0]))]
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in P:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0: lower.pop()
        lower.append(tuple(p))
    for p in P[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0: upper.pop()
        upper.append(tuple(p))
    hull = np.array(lower[:-1] + upper[:-1])
    c = hull.mean(0)
    # resample by angle around the centre, grown outward
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n; d = np.array([math.cos(a), math.sin(a)])
        best = 0.0
        for j in range(len(hull)):
            p, q = hull[j] - c, hull[(j + 1) % len(hull)] - c
            M = np.array([[d[0], p[0] - q[0]], [d[1], p[1] - q[1]]])
            if abs(np.linalg.det(M)) < 1e-9: continue
            t, u = np.linalg.solve(M, p)
            if t > 0 and 0 <= u <= 1: best = max(best, t)
        out.append(c + d * (best + grow))
    uvl = bm.loops.layers.uv.verify()
    top = [bm.verts.new((p[0], p[1], z1)) for p in out]; bot = [bm.verts.new((p[0], p[1], z0)) for p in out]
    F = [bm.faces.new(top), bm.faces.new(list(reversed(bot)))]
    for i in range(n):
        j = (i + 1) % n
        F.append(bm.faces.new([bot[i], bot[j], top[j], top[i]]))
    bmesh.ops.recalc_face_normals(bm, faces=F)
    bmesh.ops.triangulate(bm, faces=[F[0], F[1]])
    for f in bm.faces: _uv_face(f, uvl, colour)
    return list(bm.verts)



# ------------------------------------------------------------------------------------------------ boots
def _boot_chain(sx):
    """Skin-chain nodes of one tall boot (concept: up to just under the knee pad, chunky foot, angled toe)."""
    H, T = _bones()
    kn, ank = H("calf.l"), Vector((0.189, 0.062, 0.12))
    P = lambda v: Vector((v[0] * sx, v[1], v[2]))
    return [("top", P(kn.lerp(ank, 0.2)), (0.118, 0.122)),
            ("shin", P(kn.lerp(ank, 0.55)), (0.118, 0.124)),
            ("ankle", P((0.189, 0.058, 0.13)), (0.112, 0.118)),
            ("instep", P((0.191, -0.04, 0.075)), (0.118, 0.1)),
            ("toe", P((0.193, -0.165, 0.062)), (0.108, 0.072))]


def _skin_mesh(name, nodes, subdiv=2, target_tris=1100):
    """Closed smooth mesh from a chain of (name, pos, radii) nodes (Skin + Subdivision + Decimate, applied)."""
    old = bpy.data.objects.get(name + "_src")
    if old: bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name + "_src")
    me.from_pydata([tuple(p) for _, p, _ in nodes], [(i, i + 1) for i in range(len(nodes) - 1)], [])
    src = bpy.data.objects.new(name + "_src", me); bpy.context.scene.collection.objects.link(src)
    sk = src.modifiers.new("Skin", "SKIN"); sk.use_smooth_shade = True
    for i, (_, _, r) in enumerate(nodes): me.skin_vertices[0].data[i].radius = r
    me.skin_vertices[0].data[0].use_root = True
    sub = src.modifiers.new("Subdiv", "SUBSURF"); sub.levels = subdiv
    full = tris(src)
    dec = src.modifiers.new("Decimate", "DECIMATE"); dec.decimate_type = "COLLAPSE"; dec.ratio = min(1.0, target_tris / full)
    dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(src.evaluated_get(dg))
    bpy.data.objects.remove(src, do_unlink=True); bpy.data.meshes.remove(me)
    return out


SOLE_Z = (0.0, 0.045)         # the boots' sole: bottom and top


def _prism_from_points(bm, pts, z0, z1, grow, colour, n=20):
    """Straight-sided prism from the convex hull of 2D points, grown outward, between z0 and z1."""
    import numpy as np
    P = np.array(pts); P = P[np.lexsort((P[:, 1], P[:, 0]))]
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(tuple(p))
    for p in P[::-1]:
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(tuple(p))
    hull = np.array(lo[:-1] + up[:-1]); c = hull.mean(0)
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n; d = np.array([math.cos(a), math.sin(a)]); best = 0.0
        for j in range(len(hull)):
            p, q = hull[j] - c, hull[(j + 1) % len(hull)] - c
            M = np.array([[d[0], p[0] - q[0]], [d[1], p[1] - q[1]]])
            if abs(np.linalg.det(M)) < 1e-9: continue
            t, u = np.linalg.solve(M, p)
            if t > 0 and 0 <= u <= 1: best = max(best, t)
        out.append(c + d * (best + grow))
    uvl = bm.loops.layers.uv.verify()
    top = [bm.verts.new((p[0], p[1], z1)) for p in out]; bot = [bm.verts.new((p[0], p[1], z0)) for p in out]
    F = [bm.faces.new(top), bm.faces.new(list(reversed(bot)))]
    for i in range(n):
        j = (i + 1) % n; F.append(bm.faces.new([bot[i], bot[j], top[j], top[i]]))
    bmesh.ops.recalc_face_normals(bm, faces=F)
    bmesh.ops.triangulate(bm, faces=[F[0], F[1]])
    for f in bm.faces: _uv_face(f, uvl, colour)
    return list(bm.verts)


# boot foot: cross-sections from heel to toe (y, half width, height above the sole top, top chamfer); concept: blocky, rising at
# the back to the ankle, chamfered down toward the toe
BOOT_FOOT = [(0.142, 0.074, 0.150, 0.03), (0.10, 0.084, 0.168, 0.03), (0.05, 0.085, 0.165, 0.03), (0.0, 0.083, 0.140, 0.03), (-0.06, 0.081, 0.112, 0.03),
             (-0.12, 0.076, 0.092, 0.03), (-0.165, 0.066, 0.075, 0.028), (-0.192, 0.052, 0.058, 0.02)]
BOOT_TOP_Z = 0.44             # shaft top, just under the knee pad


def _foot_loft(bm, sx, colour="boot"):
    """The boot's foot block: chamfered rounded-rectangle cross-sections lofted from heel to toe, capped at both ends."""
    uvl = bm.loops.layers.uv.verify()
    x0 = 0.192 * sx
    rings = []
    for y, hw, h, ch in BOOT_FOOT:
        z0, z1 = SOLE_Z[1], SOLE_Z[1] + h
        c = min(ch, 0.45 * hw)
        pts = [(hw, z0), (hw, z1 - c), (hw - c, z1), (-hw + c, z1), (-hw, z1 - c), (-hw, z0)]
        rings.append([bm.verts.new((x0 + px, y, pz)) for px, pz in pts])
    F = []
    n = len(rings[0])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            F.append(bm.faces.new([r0[i], r0[j], r1[j], r1[i]]))
    F.append(bm.faces.new(list(reversed(rings[0])))); F.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=F)
    for f in F: _uv_face(f, uvl, colour)
    return list(bm.verts)


def _shaft_loft(bm, bvh, sx, z0, z1, rows=4, segs=10, extra=0.014, colour="boot"):
    """The boot shaft: rings fitted around the leg (ray casts from the leg axis) plus `extra`, `segs`-sided so it reads faceted,
    lofted from z0 to z1 and closed at the bottom; open at the top (the leg goes in)."""
    uvl = bm.loops.layers.uv.verify()
    H, T = _bones()
    kn = H("calf.l"); kn = Vector((kn.x * sx, kn.y, kn.z)); ank = Vector((0.189 * sx, 0.055, 0.12))
    rings = []
    for j in range(rows + 1):
        z = z0 + (z1 - z0) * j / rows
        t = (z - ank.z) / (kn.z - ank.z); o = ank.lerp(kn, t)
        ring = []
        for i in range(segs):
            a = 2 * math.pi * (i + 0.5) / segs
            d = Vector((math.sin(a), -math.cos(a), 0))
            hit, hn, _, dist = bvh.ray_cast(o, d, 0.4)
            r = (dist if hit is not None else 0.07) + extra + 0.004 * (1 - j / rows)
            ring.append(bm.verts.new(o + d * r))
        rings.append(ring)
    F = []
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(segs):
            k = (i + 1) % segs
            F.append(bm.faces.new([r0[i], r0[k], r1[k], r1[i]]))
    # a thin rim at the top (inner wall) so the open top has thickness
    inner = [bm.verts.new(v.co + (Vector((rings[-1][0].co.x * 0 + (o.x), o.y, v.co.z)) - v.co).normalized() * 0.012) for v in rings[-1]]
    for i in range(segs):
        k = (i + 1) % segs
        F.append(bm.faces.new([rings[-1][i], rings[-1][k], inner[k], inner[i]]))
    F.append(bm.faces.new(list(reversed(rings[0]))))
    bmesh.ops.recalc_face_normals(bm, faces=F)
    for f in F: _uv_face(f, uvl, colour)
    return list(bm.verts)


def build_boots():
    """Tall hard-surface boots (concept): a faceted shaft to just under the knee pad with two straps and a front plate, a blocky
    foot rising at the back and chamfered to the toe, an ankle strap over the seam, a thick sole and a heel block."""
    made = []
    body_bvh_ = body_bvh()
    for side, sx in (("l", 1), ("r", -1)):
        old = bpy.data.objects.get("Boot." + side)
        if old: bpy.data.objects.remove(old, do_unlink=True)
        calf = {"calf." + side: 1.0}
        bm = bmesh.new(); _shaft_loft(bm, body_bvh_, sx, 0.1, BOOT_TOP_Z)
        made.append(_finish_object("BootShaft." + side, bm, calf, sharp=True).name)
        bm = bmesh.new(); res = _foot_loft(bm, sx)
        ys = [v.co.y for v in res]
        def fw(i, ys=ys, side=side):
            y = ys[i]
            if y < -0.11: return {"toe." + side: 1.0}
            if y < -0.05: t = (-0.05 - y) / 0.06; return {"foot." + side: 1 - t, "toe." + side: t}
            return {"foot." + side: 1.0}
        made.append(_finish_object("BootFoot." + side, bm, fw, sharp=True).name)
        # boot surfaces for the details: shaft + foot
        shaft = bpy.data.objects["BootShaft." + side]; foot = bpy.data.objects["BootFoot." + side]
        V, Pp = [], []
        for ob in (shaft, foot):
            off = len(V); V += [v.co.copy() for v in ob.data.vertices]; Pp += [tuple(i + off for i in p.vertices) for p in ob.data.polygons]
        bvh = BVHTree.FromPolygons(V, Pp)
        H, T = _bones()
        kn = H("calf.l"); kn = Vector((kn.x * sx, kn.y, kn.z)); ank = Vector((0.189 * sx, 0.055, 0.12))
        for k, z in enumerate((0.26, 0.37)):
            t0 = (z - ank.z) / (kn.z - ank.z); t1 = (z + 0.026 - ank.z) / (kn.z - ank.z)
            bm = bmesh.new(); wrap_band(bm, bvh, ank, kn, t0, t1, 0.001, 0.01, "belt", segs=10, rings=1)
            made.append(_finish_object("BootStrap%d.%s" % (k + 1, side), bm, calf, sharp=True).name)
        ta, tb = (0.135 - ank.z) / (kn.z - ank.z), (0.175 - ank.z) / (kn.z - ank.z)
        bm = bmesh.new(); wrap_band(bm, bvh, ank, kn, ta, tb, 0.002, 0.012, "belt", segs=10, rings=1)
        made.append(_finish_object("BootAnkle." + side, bm, calf, sharp=True).name)
        mid = ank.lerp(kn, 0.56)
        bm = bmesh.new()
        projected_plate(bm, bvh, mid + Vector((0, -0.12, 0)), (0, -1, 0), (kn - ank).normalized(), 0.1, 0.15, colour="armor",
                        poly=POLY_SHIN, n=24, thickness=0.012, bulge=0.0, gap=0.001, rings=(1.0, 0.5))
        made.append(_finish_object("BootShin." + side, bm, calf).name)
        # sole and heel from the foot's exact outline
        outline = [(v.co.x, v.co.y) for v in foot.data.vertices]
        bm = bmesh.new(); res = _prism_from_points(bm, outline, SOLE_Z[0] + 0.012, SOLE_Z[1] + 0.002, 0.008, "sole")
        ys2 = [v.co.y for v in res]
        made.append(_finish_object("Sole." + side, bm, (lambda i, ys=ys2, side=side: {("toe." + side): 1.0} if ys[i] < -0.09 else {("foot." + side): 1.0}),
                                   sharp=True).name)
        bm = bmesh.new(); _prism_from_points(bm, [p for p in outline if p[1] >= 0.03], SOLE_Z[0], SOLE_Z[0] + 0.014, 0.012, "dark")
        made.append(_finish_object("Heel." + side, bm, {"foot." + side: 1.0}, sharp=True).name)
    return made

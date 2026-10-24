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
    node("pelvis", (0, 0.005, 0.95), (0.205, 0.155))
    node("waist", (0, 0.005, 1.07), (0.185, 0.14))
    node("belly", (0, 0.01, 1.19), (0.205, 0.15))
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
        ankle = Vector((0.189, 0.05, 0.13))
        node("hip." + s, P((hip.x, hip.y, hip.z - 0.02)), (0.13, 0.13))
        node("thigh." + s, P(hip.lerp(kn, 0.5)), (0.115, 0.115))
        node("knee." + s, P(kn), (0.092, 0.095))
        node("calf." + s, P(kn.lerp(ankle, 0.42) + Vector((0, 0.012, 0))), (0.09, 0.095))
        node("ankle." + s, P(ankle), (0.078, 0.085))
        node("instep." + s, P((0.191, -0.035, 0.05)), (0.09, 0.078))
        node("toe." + s, P((0.193, -0.14, 0.032)), (0.085, 0.056))
        node("heel." + s, P((0.192, 0.095, 0.036)), (0.075, 0.058))
        chain("pelvis", "hip." + s, "thigh." + s, "knee." + s, "calf." + s, "ankle." + s, "instep." + s, "toe." + s)
        chain("ankle." + s, "heel." + s)
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

HELMET_C = Vector((0.0, 0.035, 1.712))     # centre of the dome
HELMET_R = (0.124, 0.133, 0.152)           # half sizes x, y, z (smaller than block-out 1, per Terr4)
HELMET_P = 3.4                             # horizontal squareness (2 = round, higher = flatter sides)
HELMET_Q = 2.15                            # vertical squareness


def _se(t, e):
    return math.copysign(abs(t) ** e, t)


def helmet_point(az, el, s=1.0):
    """Point on the helmet surface: az = degrees around z from the front (-y) toward +x, el = degrees above the centre."""
    a, e = math.radians(az), math.radians(el)
    ce, se_ = math.cos(e), math.sin(e)
    x = HELMET_R[0] * s * _se(ce, 2 / HELMET_Q) * _se(math.sin(a), 2 / HELMET_P)
    y = -HELMET_R[1] * s * _se(ce, 2 / HELMET_Q) * _se(math.cos(a), 2 / HELMET_P)
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


JAW_Z = (1.582, 1.686)


def _jaw_scale(a, z):
    """The jaw guard is a faceted prow: a ridge down the centre, flat cheek planes falling back toward the ears, jutting forward
    and down toward the chin (concept side view)."""
    ridge = max(0.0, 1.0 - abs(a) / 70.0)
    low = max(0.0, min(1.0, (1.686 - z) / 0.10))
    return 1.015 + 0.07 * ridge + 0.05 * ridge * low


def helmet_parts():
    """(name, colour, builder(bm), subdiv). All weighted 100% to the head bone. subdiv 0 parts are faceted on purpose."""
    P = []
    P.append(("Helmet", "armor", lambda bm: helmet_dome(bm), 1))
    P.append(("HelmetStripe", "trim", lambda bm: surface_patch(bm, -3.5, 3.5, 1.762, 1.862, 0.99, 1.012, segs=1, rows=8), 0))
    P.append(("Brow", "armor", lambda bm: surface_patch(bm, -76, 76, 1.734, 1.764, 0.975, 1.07, segs=12, rows=1), 1))
    P.append(("Visor", "visor", lambda bm: surface_patch(bm, -66, 66, 1.683, 1.736, 0.96, 1.02, segs=12, rows=1), 1))
    P.append(("Jaw", "armor", lambda bm: surface_patch(bm, -72, 72, JAW_Z[0], JAW_Z[1], 0.95, _jaw_scale, segs=6, rows=2), 0))
    for side, sx in (("l", 1), ("r", -1)):
        for k, z in ((1, 1.650), (2, 1.630)):
            # dark slots lying 3-6 mm proud of the jaw's cheek plane
            P.append(("Vent%d.%s" % (k, side), "dark",
                      lambda bm, sx=sx, z=z: surface_patch(bm, sx * 30, sx * 46, z - 0.0055, z + 0.0055,
                                                           lambda a, zz: _jaw_scale(a, zz) - 0.01, lambda a, zz: _jaw_scale(a, zz) + 0.006, segs=2, rows=1), 0))
        P.append(("Ear." + side, "armor", lambda bm, sx=sx: surface_patch(bm, sx * 78, sx * 104, 1.635, 1.75, 0.985, 1.035, segs=4, rows=3), 1))
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
            palette._shade(me)
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
                    taper=0.0, n=20, rings=(1.0, 0.86, 0.45), band=1, bulge=0.0, axis=None):
    """An armour plate whose outline (a superellipse w x h, optionally tapered toward the bottom) is drawn in the plane
    (center, normal, up), projected onto the body along -normal, lifted by gap and given a thickness. The outer `band` ring of
    the front face and the rim take the `trim` colour (the concept's yellow outlines). Returns the new verts."""
    uvl = bm.loops.layers.uv.verify()
    nrm = Vector(normal).normalized(); upv = Vector(up); upv = (upv - nrm * upv.dot(nrm)).normalized(); rgt = upv.cross(nrm)
    c = Vector(center)
    def outline(t):
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
        hit, hn, _, _ = bvh.ray_cast(o, d_ray, 1.0)
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
        col = "dark" if hand > 0.5 * len(p.vertices) else ("sole" if z < 0.035 else ("boot" if z < 0.19 else "suit"))
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
    obj("ChestPlate", lambda bm: projected_plate(bm, bvh, (0, -0.15, 1.395), (0, -1, 0.1), (0, 0, 1), 1.0, 0.31, trim="trim",
                                                 squareness=3.6, thickness=0.022, taper=0.32, bulge=0.008,
                                                 axis=((0, 0.03, 1.0), (0, 0.06, 1.6))), {"chest": 1.0})
    obj("BackPlate", lambda bm: projected_plate(bm, bvh, (0, 0.17, 1.38), (0, 1, 0.08), (0, 0, 1), 0.9, 0.28, squareness=3.2,
                                                thickness=0.018, bulge=0.004, axis=((0, 0.03, 1.0), (0, 0.06, 1.6))), {"chest": 1.0})
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
    obj("Buckle", lambda bm: projected_plate(bm, bvh, (0, -0.15, 1.025), (0, -1, 0), (0, 0, 1), 0.075, 0.05, colour="trim", squareness=4,
                                             thickness=0.012, gap=0.025, n=12, rings=(1.0, 0.5)), {"pelvis": 1.0})
    # --- arms (left built, right mirrored)
    sh = H("upper_arm.l"); el = H("lower_arm.l"); wr = H("hand.l")
    # pauldron: hugs the shoulder; rays from the shoulder joint over the top and outer side of the deltoid
    obj("Pauldron", lambda bm: radial_shell(bm, bvh, sh + Vector((-0.02, 0.0, -0.02)), _frame((1, 0, 0), (0.35, 0, 1)), -60, 60, -20, 62,
                                            0.004, 0.022, "armor", trim="trim", trim_rows=1, segs=10, rows=5, bulge=0.012),
        {"upper_arm.l": 1.0}, sharp=True, mirror=True)
    obj("Gauntlet", lambda bm: wrap_band(bm, bvh, el, wr, 0.14, 0.97, 0.003, 0.013, "armor", segs=8, rings=2, flare=0.006),
        {"lower_arm.l": 1.0}, sharp=True, mirror=True)
    obj("GauntletRing", lambda bm: wrap_band(bm, bvh, el, wr, 0.06, 0.13, 0.012, 0.014, "trim", segs=12, rings=1),
        {"lower_arm.l": 1.0}, sharp=True, mirror=True)
    # --- legs
    hip = H("thigh.l"); kn = H("calf.l"); ank = Vector((0.189, 0.05, 0.13))
    tm = hip.lerp(kn, 0.42)
    obj("ThighPlate", lambda bm: projected_plate(bm, bvh, tm + Vector((0.07, -0.07, 0)), (0.72, -0.69, 0), (kn - hip).normalized() * -1, 0.12, 0.22,
                                                 trim="trim", squareness=2.6, thickness=0.018, bulge=0.004, gap=0.002), {"thigh.l": 1.0}, mirror=True)
    obj("KneePad", lambda bm: radial_shell(bm, bvh, kn + Vector((0, 0.01, 0.0)), _frame((0, -1, 0), (0, 0, 1)), -48, 48, -38, 42,
                                           0.009, 0.018, "boot", segs=8, rows=5, bulge=0.014),
        {"calf.l": 1.0}, sharp=False, mirror=True)
    sm = kn.lerp(ank, 0.6)
    obj("ShinGuard", lambda bm: projected_plate(bm, bvh, sm + Vector((0, -0.08, 0)), (0, -1, 0), (kn - ank).normalized(), 0.11, 0.26,
                                                squareness=2.8, thickness=0.016, taper=0.15, bulge=0.004), {"calf.l": 1.0}, mirror=True)
    obj("BootCuff", lambda bm: wrap_band(bm, bvh, ank + Vector((0, 0, -0.1)), kn, 0.29, 0.39, 0.008, 0.02, "boot", segs=14, rings=1),
        {"calf.l": 1.0}, sharp=True, mirror=True)
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

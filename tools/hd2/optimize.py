"""
Make a game-ready low-poly model out of one of the high-poly sources (HDM1 body, HDW1 weapon, HDP1 jump pack, made by fit/paint/fixhands, weapon.py, pack.py):
decimate it, give it a proper UV atlas, bake its colour and a tangent-space normal map from the high-poly, and write the HDX1 file the mod loads.
Runs inside Blender 4.0 (it does the decimation, the unwrap and the Cycles bake):

  blender -b --factory-startup --python-exit-code 1 -P optimize.py -- <src.bin> <src_tex.png> <out_prefix>
      [--tris 12000] [--size 2048] [--nrm-size <size>] [--angle 60] [--extrude 0.01] [--detail <src>_detail.npz] [--preview <png prefix>]

Writes <out_prefix>.hdx, <out_prefix>_tex.png (colour) and <out_prefix>_nrm.png (normal map, +Y up, Unity/OpenGL convention).
--detail: HD2's own normal maps (from weapon.py / pack.py --detail) are applied to the high-poly first, so their panel lines and screws end up in the bake.
--preview: renders the high-poly and the result side by side (Eevee) for a quick check.

The source files are in Unity space (y up, the character faces +z, Unity's winding). Loaded as-is into Blender every face normal still points the same way,
and the tangents Blender writes (MikkTSpace, bitangent = cross(normal, tangent) * sign) are what Unity's shaders expect, so nothing is converted.

HDX1 (little endian):
  "HDX1", u32 version (1), u32 flags (1 = skinned), u32 vertex count, u32 triangle count, u32 key count, u32 bone count
  keys:  per key  u8 name length, name (utf-8), 3 x f32
  bones: per bone u8 name length, name (utf-8)
  positions 3 x f32, normals 3 x f32, tangents 4 x f32, uvs 2 x f32 (per vertex)
  skinned only: bone indices 4 x u8, weights 4 x f32 (per vertex)
  triangles: 3 x u16 per triangle (u32 when there are more than 65535 vertices)
"""
import bpy, sys, os, struct, math, time
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
def opt(name, default=None, cast=str):
    return cast(argv[argv.index(name) + 1]) if name in argv else default
SRC, SRC_TEX, OUT = pos[0], pos[1], pos[2]
TRIS = opt("--tris", 12000, int)
SIZE = opt("--size", 2048, int)
NRM_SIZE = opt("--nrm-size", SIZE, int)       # the normal map can be smaller than the colour map when it only carries the shape
ANGLE = opt("--angle", 60.0, float)
EXTRUDE = opt("--extrude", 0.01, float)
DETAIL = opt("--detail")
PREVIEW = opt("--preview")
PAD = 4                                   # texels of empty space around every UV island
t_start = time.time()
def log(*a): print("[optimize]", *a, flush=True)


# ---------------------------------------------------------------- source
def read_src(path):
    f = open(path, "rb").read()
    magic = f[:4]
    d = {"keys": [], "bones": [], "BI": None, "BW": None}
    def arr(dt, n, o): return np.frombuffer(f, dt, n, o)
    if magic == b"HDM1":
        nV, nT, nB = struct.unpack("<III", f[4:16]); o = 16
        for _ in range(nB):
            l = f[o]; d["bones"].append(f[o + 1:o + 1 + l].decode()); o += 1 + l
    elif magic in (b"HDW1", b"HDP1"):
        nV, nT = struct.unpack("<II", f[4:12]); o = 12
        names = ["trigger", "muzzle", "underbarrel"] if magic == b"HDW1" else ["thrusterL", "thrusterR", "light", "flameDir"]
        kp = arr("<f4", len(names) * 3, o).reshape(-1, 3); o += len(names) * 12
        d["keys"] = [(n, kp[i].astype(np.float64)) for i, n in enumerate(names)]
    else:
        raise SystemExit("unknown source format " + repr(magic))
    d["P"] = arr("<f4", nV * 3, o).reshape(nV, 3).astype(np.float64); o += nV * 12
    d["N"] = arr("<f4", nV * 3, o).reshape(nV, 3).astype(np.float64); o += nV * 12
    d["UV"] = arr("<f4", nV * 2, o).reshape(nV, 2).astype(np.float64); o += nV * 8
    if magic == b"HDM1":
        d["BI"] = arr("<u1", nV * 4, o).reshape(nV, 4).astype(np.int64); o += nV * 4
        d["BW"] = arr("<f4", nV * 4, o).reshape(nV, 4).astype(np.float64); o += nV * 16
    d["T"] = arr("<u4", nT * 3, o).reshape(nT, 3).astype(np.int64)
    d["magic"] = magic
    return d

src = read_src(SRC)
P, N, UV, T = src["P"], src["N"], src["UV"], src["T"]
skinned = src["BI"] is not None
log(os.path.basename(SRC), src["magic"].decode(), len(P), "vertices", len(T), "triangles", "skinned" if skinned else "static")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def mesh_object(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob

def load_image(path, colorspace):
    im = bpy.data.images.load(os.path.abspath(path))
    im.colorspace_settings.name = colorspace
    return im


# ---------------------------------------------------------------- high-poly (the bake source)
high = mesh_object("high", P, T)
hm = high.data
hm.uv_layers.new(name="cells").data.foreach_set("uv", UV[T].ravel())
hm.use_auto_smooth = True
hm.normals_split_custom_set_from_vertices(N.tolist())
hm.polygons.foreach_set("use_smooth", np.ones(len(T), bool))

colour_src = load_image(SRC_TEX, "sRGB")
detail_maps, slots = [], None
if DETAIL:
    dz = np.load(DETAIL)
    hm.uv_layers.new(name="hd2").data.foreach_set("uv", dz["uv"].astype(np.float64).ravel())
    slots = dz["slot"].astype(np.int64)
    for m in dz["maps"]:
        p = str(m)
        if not os.path.isabs(p) or not os.path.exists(p): p = os.path.join(os.path.dirname(os.path.abspath(DETAIL)), os.path.basename(p))
        detail_maps.append(load_image(p, "Non-Color"))
    log("detail:", len(detail_maps), "HD2 normal maps")

def high_material(name, detail):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    uv = nodes.new("ShaderNodeUVMap"); uv.uv_map = "cells"
    tex = nodes.new("ShaderNodeTexImage"); tex.image = colour_src; tex.interpolation = "Linear"
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])     # the colour bake reads the emission
    bsdf.inputs["Emission Strength"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.6
    if detail is not None:
        uvd = nodes.new("ShaderNodeUVMap"); uvd.uv_map = "hd2"
        dt = nodes.new("ShaderNodeTexImage"); dt.image = detail; dt.interpolation = "Linear"
        nm = nodes.new("ShaderNodeNormalMap"); nm.space = "TANGENT"; nm.uv_map = "hd2"
        links.new(uvd.outputs["UV"], dt.inputs["Vector"])
        links.new(dt.outputs["Color"], nm.inputs["Color"])
        links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m

high.data.materials.append(high_material("high_plain", None))
for i, im in enumerate(detail_maps): high.data.materials.append(high_material("high_detail%d" % i, im))
if slots is not None:
    hm.polygons.foreach_set("material_index", np.where(slots >= 0, slots + 1, 0).astype(np.int32))


# ---------------------------------------------------------------- low-poly: weld, decimate
# weld the triangle soup by position (the sources store three vertices per triangle), drop collapsed and duplicate triangles
Pq = np.round(P / 1e-5).astype(np.int64)
_, first, inv = np.unique(Pq, axis=0, return_index=True, return_inverse=True)
inv = inv.ravel()
Tw = inv[T]
ok = (Tw[:, 0] != Tw[:, 1]) & (Tw[:, 1] != Tw[:, 2]) & (Tw[:, 0] != Tw[:, 2])
Tw = Tw[ok]
_, keep = np.unique(np.sort(Tw, 1), axis=0, return_index=True)
Tw = Tw[np.sort(keep)]
Pw = P[first]
low = mesh_object("low", Pw, Tw)
lm = low.data
log("welded:", len(Pw), "vertices", len(Tw), "triangles")

if skinned:
    groups = [low.vertex_groups.new(name=b) for b in src["bones"]]
    BI, BW = src["BI"][first], src["BW"][first]
    for k in range(4):
        for b in np.unique(BI[:, k]):
            sel = np.nonzero((BI[:, k] == b) & (BW[:, k] > 0))[0]
            for w in np.unique(BW[sel, k]):                         # vertex_groups.add takes one weight per call
                groups[b].add(sel[BW[sel, k] == w].tolist(), float(w), "ADD")

bpy.context.view_layer.objects.active = low
for o in scene.objects: o.select_set(o == low)
if TRIS < len(Tw):
    dec = low.modifiers.new("decimate", "DECIMATE")
    dec.decimate_type = "COLLAPSE"; dec.ratio = TRIS / len(Tw); dec.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=dec.name)
tri = low.modifiers.new("triangulate", "TRIANGULATE"); bpy.ops.object.modifier_apply(modifier=tri.name)
log("decimated:", len(lm.vertices), "vertices", len(lm.polygons), "triangles")

lm.use_auto_smooth = True
lm.auto_smooth_angle = math.radians(ANGLE)
lm.polygons.foreach_set("use_smooth", np.ones(len(lm.polygons), bool))

# ---------------------------------------------------------------- UV atlas
lm.uv_layers.new(name="atlas")
lm.uv_layers.active = lm.uv_layers["atlas"]
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(min(ANGLE, 89.0)), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
try:
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", scale=True, merge_overlap=False, margin_method="FRACTION", margin=2 * PAD / SIZE, shape_method="CONCAVE")
except TypeError:
    bpy.ops.uv.pack_islands(rotate=True, margin=2 * PAD / SIZE)
bpy.ops.object.mode_set(mode="OBJECT")
uvs = np.zeros(len(lm.loops) * 2); lm.uv_layers["atlas"].data.foreach_get("uv", uvs); uvs = uvs.reshape(-1, 2)
log("atlas: uv range", uvs.min(0).round(3), uvs.max(0).round(3))


# ---------------------------------------------------------------- bake colour + normal map from the high-poly
scene.render.engine = "CYCLES"
try:
    cp = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            cp.compute_device_type = dev; cp.get_devices()
            if any(d.type == dev for d in cp.devices):
                for d in cp.devices: d.use = d.type == dev
                scene.cycles.device = "GPU"; log("cycles device", dev); break
        except TypeError: pass
except Exception as e: log("gpu setup failed, using the cpu:", e)
scene.cycles.samples = 16
scene.cycles.use_denoising = False
scene.view_settings.view_transform = "Standard"
bk = scene.render.bake
bk.use_selected_to_active = True; bk.cage_extrusion = EXTRUDE; bk.max_ray_distance = EXTRUDE * 3
bk.margin = 2 * PAD; bk.margin_type = "EXTEND"; bk.use_clear = False

img_c = bpy.data.images.new("bake_colour", SIZE, SIZE, alpha=False)
img_c.generated_color = (0.1, 0.1, 0.11, 1.0)
img_n = bpy.data.images.new("bake_normal", NRM_SIZE, NRM_SIZE, alpha=False)
img_n.generated_color = (0.5, 0.5, 1.0, 1.0)
img_n.colorspace_settings.name = "Non-Color"

lowmat = bpy.data.materials.new("low"); lowmat.use_nodes = True
lnodes, llinks = lowmat.node_tree.nodes, lowmat.node_tree.links
target = lnodes.new("ShaderNodeTexImage"); lnodes.active = target
lm.materials.append(lowmat)

for o in scene.objects: o.select_set(o in (low, high))
bpy.context.view_layer.objects.active = low
target.image = img_c
t0 = time.time()
bpy.ops.object.bake(type="EMIT")
log("colour baked in %.1fs" % (time.time() - t0))
target.image = img_n
t0 = time.time()
bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z")
log("normal map baked in %.1fs" % (time.time() - t0))

for im, suffix in ((img_c, "_tex.png"), (img_n, "_nrm.png")):
    im.filepath_raw = os.path.abspath(OUT + suffix); im.file_format = "PNG"; im.save()


# ---------------------------------------------------------------- export HDX1
lm.calc_normals_split()
lm.calc_tangents(uvmap="atlas")
nL = len(lm.loops)
vi = np.zeros(nL, np.int64); lm.loops.foreach_get("vertex_index", vi)
ln = np.zeros(nL * 3); lm.loops.foreach_get("normal", ln); ln = ln.reshape(-1, 3)
lt = np.zeros(nL * 3); lm.loops.foreach_get("tangent", lt); lt = lt.reshape(-1, 3)
ls = np.zeros(nL); lm.loops.foreach_get("bitangent_sign", ls)
vco = np.zeros(len(lm.vertices) * 3); lm.vertices.foreach_get("co", vco); vco = vco.reshape(-1, 3)
key = np.concatenate([vi[:, None], np.round(ln * 1e4), np.round(uvs * 1e6), np.round(lt * 1e3), ls[:, None]], 1).astype(np.int64)
_, lfirst, linv = np.unique(key, axis=0, return_index=True, return_inverse=True)
linv = linv.ravel()
nV = len(lfirst)
loop_start = np.zeros(len(lm.polygons), np.int64); lm.polygons.foreach_get("loop_start", loop_start)
tris = linv[loop_start[:, None] + np.arange(3)[None, :]]
outP, outN, outUV = vco[vi[lfirst]], ln[lfirst], uvs[lfirst]
outT = np.concatenate([lt[lfirst], ls[lfirst, None]], 1)

bone_idx = bone_w = None
if skinned:
    bone_idx = np.zeros((nV, 4), np.uint8); bone_w = np.zeros((nV, 4), np.float32)
    gi = {g.index: src["bones"].index(g.name) for g in low.vertex_groups}
    empty = 0
    for k, v in enumerate(vi[lfirst]):
        ws = sorted(((g.weight, gi[g.group]) for g in lm.vertices[v].groups if g.weight > 1e-4), reverse=True)[:4]
        s = sum(w for w, _ in ws)
        if s <= 0: empty += 1; ws, s = [(1.0, 0)], 1.0
        for j, (w, b) in enumerate(ws): bone_idx[k, j] = b; bone_w[k, j] = w / s
    log("weights: %d vertices without weights" % empty)

with open(OUT + ".hdx", "wb") as f:
    f.write(b"HDX1"); f.write(struct.pack("<IIIIII", 1, 1 if skinned else 0, nV, len(tris), len(src["keys"]), len(src["bones"])))
    for name, v in src["keys"]:
        e = name.encode(); f.write(struct.pack("<B", len(e))); f.write(e); f.write(np.asarray(v, "<f4").tobytes())
    for name in src["bones"]:
        e = name.encode(); f.write(struct.pack("<B", len(e))); f.write(e)
    for a in (outP, outN, outT, outUV): f.write(a.astype("<f4").tobytes())
    if skinned: f.write(bone_idx.astype("<u1").tobytes()); f.write(bone_w.astype("<f4").tobytes())
    f.write(tris.astype("<u2" if nV <= 65535 else "<u4").tobytes())
log("wrote %s.hdx: %d vertices, %d triangles (%d bytes) in %.0fs" % (OUT, nV, len(tris), os.path.getsize(OUT + ".hdx"), time.time() - t_start))


# ---------------------------------------------------------------- preview: high-poly (left) and the result (right)
if PREVIEW:
    nodes = lowmat.node_tree.nodes; links = lowmat.node_tree.links
    bsdf = nodes["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = 0.6
    tc = nodes.new("ShaderNodeTexImage"); tc.image = img_c
    tn = nodes.new("ShaderNodeTexImage"); tn.image = img_n
    nmap = nodes.new("ShaderNodeNormalMap"); nmap.uv_map = "atlas"
    links.new(tc.outputs["Color"], bsdf.inputs["Base Color"]); links.new(tn.outputs["Color"], nmap.inputs["Color"]); links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    for m in high.data.materials: m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
    if not "--preview-detail" in argv:     # the high-poly as the game showed it until now: no normal maps
        for m in high.data.materials:
            b = m.node_tree.nodes["Principled BSDF"]
            for l in list(b.inputs["Normal"].links): m.node_tree.links.remove(l)
    import mathutils
    lo, hi = vco.min(0), vco.max(0); size = (hi - lo).max(); c = (lo + hi) / 2
    for ob in (high, low):
        ob.rotation_euler = (math.radians(90), 0, 0)
        ob.location = (-c[0], c[2], -c[1])                       # unity y up -> blender z up, the front (+z) faces the camera at -y
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 900
    scene.world = bpy.data.worlds.new("w"); scene.world.color = (0.08, 0.08, 0.09)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); scene.collection.objects.link(sun)
    sun.data.energy = 3.5; sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); scene.collection.objects.link(cam); scene.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = size * 1.1
    # one image per view and model (high = what the game showed until now, low = the optimized model); tools/hd2/sheet.py puts them side by side
    for view, rot in (("front", (90, 0, 0)), ("back", (90, 0, 180)), ("left", (90, 0, -90)), ("right", (90, 0, 90))):
        r = [math.radians(a) for a in rot]
        cam.rotation_euler = r
        cam.location = (mathutils.Euler(r).to_matrix() @ mathutils.Vector((0, 0, 1))) * size * 4
        for name, ob in (("high", high), ("low", low)):
            high.hide_render, low.hide_render = ob is not high, ob is not low
            scene.render.filepath = os.path.abspath("%s_%s_%s.png" % (PREVIEW, view, name))
            bpy.ops.render.render(write_still=True)
    log("previews written", PREVIEW + "_*.png")

"""
Convert the Helldivers 2 LIFT-850 Jump Pack (content/fac_helldivers/equipment/backpacks/jumppack_backpack) into a static mesh in the same space as helldiver_mesh.bin
(the Commando bind pose), plus a baked colour texture, so the mod can hang it off the chest bone.

  uv run --with numpy --with pillow python pack.py <jumppack_backpack.unit.glb> <avatar_helldiver.unit.glb> <commando_skel.json> <out_prefix> [preview_prefix] [--detail]

Steps: skinned GLB -> rest pose (inverse bind matrices); pack space -> the diver's world via the avatar's `backpack` node (the pack's +Y/forward is the node's +Y = the
diver's back); mirror z (the body convention: the diver faces +Z); fit with the same chest transform fit.py / cape.py use. HD2 only stores a normal map and material ids
for its gear, so colours are baked per triangle by region (tanks, plate, nozzles, straps), with worn convex edges.
Output HDP1: "HDP1", nV u32, nT u32, then 4 key points (thruster L, thruster R, indicator light, flame direction: 3 x f32 each), positions, normals, uvs, triangles.
The key points are the nozzle exit centres (flame origins), the status light and the unit flame direction, all in the same space as the vertices.
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
import glb, detail

args = [a for a in sys.argv[1:] if not a.startswith("--")]
want_detail = "--detail" in sys.argv          # also write the HD2 UVs and normal map for optimize.py (see detail.py)
packp, avatarp, skelp, outp = args[0:4]
prev = args[4] if len(args) > 4 else None
maps = detail.Maps(outp)
ALPHA = 0.65

def hexc(h): return np.array([int(h[i:i+2], 16) for i in (1, 3, 5)], dtype=np.float64)

# ---- the chest transform (same as cape.py)
aj, ab = glb.load(avatarp)
AW = glb.node_world(aj)
skin = aj["skins"][0]
jnode = {aj["nodes"][i]["name"]: i for i in skin["joints"]}
def hp(name):
    p = AW[jnode[name]][:3, 3].copy(); p[2] = -p[2]; return p
cname = {bn["name"]: bn for bn in json.load(open(skelp))["renderers"][0]["bones"]}
def cp(name): return np.array(cname[name]["pos"], dtype=np.float64)
def rot_between(a, bv):
    a = a / np.linalg.norm(a); bv = bv / np.linalg.norm(bv)
    v = np.cross(a, bv); c = float(np.dot(a, bv)); s = np.linalg.norm(v)
    if s < 1e-8: return np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * ((1 - c) / (s * s))
def seg(cb, hs, he, ce):
    ps = hp(hs); pt = cp(cb)
    s = hp(he) - ps; t = cp(ce) - pt
    R = rot_between(s, t); d = t / np.linalg.norm(t)
    k = 1 + ALPHA * (np.linalg.norm(t) / np.linalg.norm(s) - 1)
    S = np.eye(3) + (k - 1) * np.outer(d, d)
    M = np.eye(4); M[:3, :3] = S @ R; M[:3, 3] = pt - S @ R @ ps
    return M
Gchest = seg("chest", "spine2", "neck", "head")

# ---- pack -> diver glb world (y up, diver faces -z)
bp_node = [i for i, n in enumerate(aj["nodes"]) if n.get("name") == "backpack"][0]
U2S = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)   # unit (glb, y up) -> Stingray node frame (z up, y forward)
M = AW[bp_node] @ U2S

def to_diver(P):            # unit-space points -> diver world -> z mirrored -> chest fit
    W = (np.concatenate([P, np.ones((len(P), 1))], 1) @ M.T)[:, :3]
    W[:, 2] *= -1
    return (np.concatenate([W, np.ones((len(W), 1))], 1) @ Gchest.T)[:, :3]
def dir_to_diver(d):
    W = M[:3, :3] @ d; W[2] *= -1
    r = Gchest[:3, :3] @ W; return r / np.linalg.norm(r)

j, b = glb.load(packp)
Wn = glb.node_world(j)
jn = {nd.get("name"): i for i, nd in enumerate(j["nodes"])}
parts = []
for i, nd in enumerate(j["nodes"]):
    if "mesh" not in nd: continue
    sk = j["skins"][nd["skin"]]
    ibm = glb.accessor(j, b, sk["inverseBindMatrices"]).reshape(-1, 4, 4).astype(np.float64).transpose(0, 2, 1)
    jm = np.array([Wn[x] for x in sk["joints"]]) @ ibm
    for pr in j["meshes"][nd["mesh"]]["primitives"]:
        mat = j["materials"][pr["material"]]["name"] if pr.get("material") is not None else "none"
        if "collision" in mat or "shadow" in mat or pr.get("material") is None: continue
        P = glb.accessor(j, b, pr["attributes"]["POSITION"]).astype(np.float64)
        N = glb.accessor(j, b, pr["attributes"]["NORMAL"]).astype(np.float64)
        J = glb.accessor(j, b, pr["attributes"]["JOINTS_0"]).astype(np.int64); Wt = glb.accessor(j, b, pr["attributes"]["WEIGHTS_0"]).astype(np.float64)
        Ph = np.concatenate([P, np.ones((len(P), 1))], 1); Pn = np.zeros_like(P); Nn = np.zeros_like(N)
        for k in range(4):
            Mk = jm[J[:, k]]
            Pn += Wt[:, k:k+1] * np.einsum("nij,nj->ni", Mk, Ph)[:, :3]
            Nn += Wt[:, k:k+1] * np.einsum("nij,nj->ni", Mk[:, :3, :3], N)
        T = glb.accessor(j, b, pr["indices"]).astype(np.int64).reshape(-1, 3)
        kind = "light" if "m_jump_backpack" not in mat else "body"
        UV0 = glb.accessor(j, b, pr["attributes"]["TEXCOORD_0"]).astype(np.float64) if want_detail else None
        parts.append((kind, Pn, Nn, T, UV0, maps.slot(j, b, packp, pr["material"]) if want_detail else -1))
        print("part", kind, mat, "verts", len(Pn), "tris", len(T))

# diver-world pack-frame coordinates, kept for the region classification (y up from the pack bottom, z outward = +)
def unit_xyz(P):             # unit-space -> (x across, y up, depth outward) with outward positive
    return np.stack([P[:, 0], P[:, 1], -P[:, 2]], 1)

Pu = np.concatenate([p[1] for p in parts]); Nu = np.concatenate([p[2] for p in parts])
kinds = np.concatenate([[p[0]] * len(p[1]) for p in parts])
base = 0; Ts = []
for p in parts:
    Ts.append(p[3] + base); base += len(p[1])
T = np.concatenate(Ts)
slots = np.concatenate([[p[5]] * len(p[3]) for p in parts])
X = unit_xyz(Pu)
P = to_diver(Pu)
Nw = (Nu @ M[:3, :3].T); Nw[:, 2] *= -1; N = Nw @ Gchest[:3, :3].T
N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
T = T[:, ::-1]                                    # z mirror flips the winding

# key points
def node_pos(name): return np.array(Wn[jn[name]][:3, 3])
exitL = node_pos("fx_thruster_l"); exitR = node_pos("fx_thruster_r"); light = node_pos("fx_top_light")
low = Pu[:, 1].min()
def rim(centre):
    sel = (Pu[:, 1] < low + 0.012) & (np.abs(Pu[:, 0] - centre[0]) < 0.08)
    return Pu[sel].mean(0) if sel.any() else centre
exitL, exitR = rim(exitL), rim(exitR)
keys = np.array([to_diver(exitL[None])[0], to_diver(exitR[None])[0], to_diver(light[None])[0], dir_to_diver(np.array([0.0, -1.0, 0.0]))])
print("verts", len(P), "tris", len(T), "bbox", P.min(0).round(3), P.max(0).round(3))
print("key points (thruster L, R, light, flame dir):", keys.round(3).tolist())

# ---- colours by region (pack frame: h = height above the pack bottom, d = depth outward from the pack's plate)
PAL = {"tank": hexc("#35383f"), "plate": hexc("#25272c"), "nozzle": hexc("#202226"), "rim": hexc("#8a6a3e"), "panel": hexc("#2d3036"),
       "strap": hexc("#1a1b1f"), "light": hexc("#8fd8ff")}
WEAR = hexc("#7b7f88")
h = X[:, 1] - X[:, 1].min()
d = X[:, 2]
region = np.full(len(P), "plate", dtype=object)
region[d > 0.03] = "tank"                                       # the two cylinders, outward of the plate (d in the pack's frame: plate ~ -0.09..0.03)
region[(d > 0.03) & (np.abs(X[:, 0]) < 0.047)] = "panel"        # centre panel with the status window
region[(h < 0.165) & (d > 0.0) & (np.abs(X[:, 0]) > 0.035)] = "nozzle"
region[(h < 0.022) & (d > 0.0) & (np.abs(X[:, 0]) > 0.035)] = "rim"
region[d < -0.09] = "strap"                                     # straps and the side pods, on the diver's side of the plate
region[kinds == "light"] = "light"
for k in sorted(set(region)): print("region", k, int((region == k).sum()))

nV = len(P)
key = np.round(P * 4000).astype(np.int64)
_, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel(); nU = inv.max() + 1
A, B_, C_ = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
fn = np.cross(B_ - A, C_ - A); fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12); fc = (A + B_ + C_) / 3
edges = {}
for fi, t in enumerate(T):
    u = inv[t]
    for a, c in ((u[0], u[1]), (u[1], u[2]), (u[2], u[0])):
        edges.setdefault((a, c) if a < c else (c, a), []).append(fi)
wear = np.zeros(nU); groove = np.zeros(nU)
for (a, c), fs in edges.items():
    if len(fs) != 2: continue
    f0, f1 = fs
    ang = np.degrees(np.arccos(np.clip(np.dot(fn[f0], fn[f1]), -1, 1)))
    if ang < 45: continue
    if np.dot(fc[f1] - fc[f0], fn[f0]) < 0: wear[a] = wear[c] = 1
    else: groove[a] = groove[c] = 1
col = np.zeros((nV, 3))
for v in range(nV):
    c = PAL[region[v]].copy()
    if region[v] != "light":
        if wear[inv[v]] > 0: c = c * 0.5 + WEAR * 0.5
        elif groove[inv[v]] > 0: c = c * 0.6
        c = c * (0.88 + 0.24 * (0.5 + 0.5 * N[v, 1]))
        if region[v] == "nozzle":                       # soot toward the exit
            c = c * (0.65 + 0.35 * min(1.0, h[v] / 0.185))
    col[v] = c

# ---- per-triangle texture cells (as weapon.py)
CELL = 8; SZ = 1024
perrow = SZ // CELL
nF = len(T); assert nF <= perrow * perrow, nF
newP = P[T].reshape(-1, 3); newN = N[T].reshape(-1, 3); newUV = np.zeros((nF * 3, 2)); img = np.zeros((SZ, SZ, 3))
ys, xs = np.mgrid[0:CELL, 0:CELL]
b1 = np.clip(xs / (CELL - 1.0), 0, 1); b2 = np.clip(ys / (CELL - 1.0), 0, 1)
s_ = np.maximum(b1 + b2, 1e-9); over = s_ > 1
b1 = np.where(over, b1 / s_, b1); b2 = np.where(over, b2 / s_, b2); b0 = 1 - b1 - b2
for fi, t in enumerate(T):
    cx, cy = (fi % perrow) * CELL, (fi // perrow) * CELL
    img[cy:cy + CELL, cx:cx + CELL] = b0[..., None] * col[t[0]] + b1[..., None] * col[t[1]] + b2[..., None] * col[t[2]]
    newUV[fi * 3] = ((cx + 0.5) / SZ, 1 - (cy + 0.5) / SZ)
    newUV[fi * 3 + 1] = ((cx + CELL - 0.5) / SZ, 1 - (cy + 0.5) / SZ)
    newUV[fi * 3 + 2] = ((cx + 0.5) / SZ, 1 - (cy + CELL - 0.5) / SZ)
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(outp + "_tex.png")
with open(outp + ".bin", "wb") as f:
    f.write(b"HDP1"); f.write(struct.pack("<II", nF * 3, nF))
    f.write(keys.astype("<f4").tobytes())
    f.write(newP.astype("<f4").tobytes()); f.write(newN.astype("<f4").tobytes()); f.write(newUV.astype("<f4").tobytes())
    f.write(np.arange(nF * 3, dtype="<u4").tobytes())
print("wrote", outp, os.path.getsize(outp + ".bin"))
if want_detail:
    UV0 = np.concatenate([p[4] for p in parts]); UV0[:, 1] = 1 - UV0[:, 1]     # glTF v runs down the image
    detail.write(outp, UV0[T].reshape(-1, 2), slots, maps.paths)

if prev:
    import render
    f2 = open(os.environ.get("HD_BODY_SRC", os.path.join(os.path.dirname(os.path.abspath(outp)), "helldiver_mesh.bin")), "rb").read()   # the high-poly body source (HDM1), next to the output by default
    nVb, nTb, nB = struct.unpack("<III", f2[4:16]); o = 16
    for _ in range(nB): o += 1 + f2[o]
    BP = np.frombuffer(f2, "<f4", nVb * 3, o).reshape(nVb, 3).astype(np.float64); o += nVb * 12
    BN = np.frombuffer(f2, "<f4", nVb * 3, o).reshape(nVb, 3).astype(np.float64); o += nVb * 12 + nVb * 8 + nVb * 4 + nVb * 16
    BT = np.frombuffer(f2, "<u4", nTb * 3, o).reshape(nTb, 3).astype(np.int64)
    meshes = [(0, BP, BN, BT, 0), (1, newP, newN, np.arange(nF * 3).reshape(-1, 3), 0)]
    render.render(meshes, prev + "_side.png", view="side")
    render.render(meshes, prev + "_front.png", view="front")

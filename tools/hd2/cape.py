"""
Extract the Helldivers 2 cape (`g_cape_standard_display`, mesh 1 of the avatar GLB) and fit it onto the Commando rest pose the same way fit.py fits the body.

  uv run --with numpy --with pillow python cape.py <avatar.glb> <skel.json> <out.bin> [preview_prefix]

The cape is simulated at runtime (Cape.cs), so only its rest shape is needed: positions/normals/uvs/triangles in the same space as helldiver_mesh.bin
(z mirrored so the character faces +Z, winding flipped). Output HDC1: "HDC1", nV u32, nT u32, positions f32x3, normals f32x3, uvs f32x2, triangles u32x3.
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import glb

avatar, skelpath, outpath = sys.argv[1], sys.argv[2], sys.argv[3]
prev = sys.argv[4] if len(sys.argv) > 4 else None
ALPHA = 0.65

j, b = glb.load(avatar)
Wn = glb.node_world(j)
skin = j["skins"][0]
jnode = {j["nodes"][i]["name"]: i for i in skin["joints"]}
def hp(name):
    p = Wn[jnode[name]][:3, 3].copy(); p[2] = -p[2]; return p
cname = {bn["name"]: bn for bn in json.load(open(skelpath))["renderers"][0]["bones"]}
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
Gchest = seg("chest", "spine2", "neck", "head")        # same transform fit.py uses for the chest (the cape joints map to "chest" there)

mesh_idx = [i for i, nd in enumerate(j["nodes"]) if "mesh" in nd and "cape" in (nd.get("name") or "")][0]
pr = j["meshes"][j["nodes"][mesh_idx]["mesh"]]["primitives"][0]
P = glb.accessor(j, b, pr["attributes"]["POSITION"]).astype(np.float64); P[:, 2] *= -1
N = glb.accessor(j, b, pr["attributes"]["NORMAL"]).astype(np.float64); N[:, 2] *= -1
UV = glb.accessor(j, b, pr["attributes"]["TEXCOORD_0"]).astype(np.float64)
T = glb.accessor(j, b, pr["indices"]).astype(np.int64).reshape(-1, 3)[:, ::-1]
Pn = (np.concatenate([P, np.ones((len(P), 1))], 1) @ Gchest.T)[:, :3]
Nn = N @ Gchest[:3, :3].T; Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
print("cape verts", len(Pn), "tris", len(T), "fitted bbox", Pn.min(0).round(3), Pn.max(0).round(3))

# topology stats
edges = set()
for t in T:
    for a, c in ((0, 1), (1, 2), (2, 0)):
        u, v = int(t[a]), int(t[c]); edges.add((u, v) if u < v else (v, u))
E = np.array(sorted(edges)); el = np.linalg.norm(Pn[E[:, 0]] - Pn[E[:, 1]], axis=1)
print("edges", len(E), "length min/mean/max", el.min().round(4), el.mean().round(4), el.max().round(4))
# distinct positions (UV seams duplicate vertices)
key = np.round(Pn * 5000).astype(np.int64)
print("distinct positions", len(np.unique(key, axis=0)))

with open(outpath, "wb") as f:
    f.write(b"HDC1"); f.write(struct.pack("<II", len(Pn), len(T)))
    f.write(Pn.astype("<f4").tobytes()); f.write(Nn.astype("<f4").tobytes())
    uv = UV.copy(); uv[:, 1] = 1 - uv[:, 1]
    f.write(uv.astype("<f4").tobytes()); f.write(T.astype("<u4").tobytes())
print("wrote", outpath, os.path.getsize(outpath))

if prev:
    import render
    body = [(0, *[None] * 0)]
    # body (the fitted Helldiver) + cape side/back views
    f2 = open(os.path.join(os.path.dirname(__file__), "..", "..", "Model", "helldiver_mesh.bin"), "rb").read()
    nV, nT, nB = struct.unpack("<III", f2[4:16]); o = 16
    for _ in range(nB): o += 1 + f2[o]
    BP = np.frombuffer(f2, "<f4", nV * 3, o).reshape(nV, 3).astype(np.float64); o += nV * 12
    BN = np.frombuffer(f2, "<f4", nV * 3, o).reshape(nV, 3).astype(np.float64); o += nV * 12 + nV * 8 + nV * 4 + nV * 16
    BT = np.frombuffer(f2, "<u4", nT * 3, o).reshape(nT, 3).astype(np.int64)
    meshes = [(0, BP, BN, BT, 0), (1, Pn, Nn, T, 0)]
    render.render(meshes, prev + "_side.png", view="side")
    render.render(meshes, prev + "_front.png", view="front")

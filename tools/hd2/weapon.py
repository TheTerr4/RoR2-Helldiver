"""
Convert a Helldivers 2 weapon GLB (skinned, rest pose) into the mod's static weapon format (HDW1) plus a baked colour texture.

  uv run --with numpy --with pillow python tools/weapon.py <name> <out_prefix> <glb> [<extra_glb>:<attach_node> ...] [--detail]

Output: <out_prefix>.bin  (HDW1: header, key points, positions, normals, uvs, triangles) and <out_prefix>_tex.png
--detail also writes the HD2 UVs and normal maps for optimize.py (see detail.py).
Coordinates: metres, z mirrored so the barrel points +Z and up is +Y (same convention as the body).
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from PIL import Image
import glb, detail

args = [a for a in sys.argv[1:] if not a.startswith("--")]
want_detail = "--detail" in sys.argv
name, outp, main = args[0], args[1], args[2]
extras = [a.split(":") for a in args[3:]]
maps = detail.Maps(outp)

def hexc(h): return np.array([int(h[i:i+2], 16) for i in (1, 3, 5)], dtype=np.float64)
PAL = {"weapon": hexc("#33353c"), "rail": hexc("#1b1c20"), "ammo": hexc("#8a3026"), "mag": hexc("#2a2c31"), "other": hexc("#2b2d33")}
WEAR = hexc("#7b7f88"); BRASS = hexc("#b48a3a")

def load_parts(path, offset=None):
    j, b = glb.load(path)
    Wn = glb.node_world(j)
    jn = {nd.get("name"): i for i, nd in enumerate(j["nodes"])}
    parts = []
    for i, nd in enumerate(j["nodes"]):
        if "mesh" not in nd: continue
        skin = j["skins"][nd["skin"]] if "skin" in nd else None
        if skin is not None:
            ibm = glb.accessor(j, b, skin["inverseBindMatrices"]).reshape(-1, 4, 4).astype(np.float64).transpose(0, 2, 1)
            jm = np.array([Wn[x] for x in skin["joints"]]) @ ibm
        for pr in j["meshes"][nd["mesh"]]["primitives"]:
            mat = j["materials"][pr["material"]]["name"] if pr.get("material") is not None else "none"
            if "collision" in mat or "shadow" in mat or pr.get("material") is None: continue
            P = glb.accessor(j, b, pr["attributes"]["POSITION"]).astype(np.float64)
            N = glb.accessor(j, b, pr["attributes"]["NORMAL"]).astype(np.float64)
            if skin is not None and "JOINTS_0" in pr["attributes"]:
                J = glb.accessor(j, b, pr["attributes"]["JOINTS_0"]).astype(np.int64); Wt = glb.accessor(j, b, pr["attributes"]["WEIGHTS_0"]).astype(np.float64)
                Ph = np.concatenate([P, np.ones((len(P), 1))], 1); Pn = np.zeros_like(P); Nn = np.zeros_like(N)
                for k in range(4):
                    M = jm[J[:, k]]                                   # (n,4,4)
                    Pn += Wt[:, k:k+1] * np.einsum("nij,nj->ni", M, Ph)[:, :3]
                    Nn += Wt[:, k:k+1] * np.einsum("nij,nj->ni", M[:, :3, :3], N)
                P, N = Pn, Nn
            else:
                P = (np.concatenate([P, np.ones((len(P), 1))], 1) @ Wn[i].T)[:, :3]
            if offset is not None: P = P + offset
            T = glb.accessor(j, b, pr["indices"]).astype(np.int64).reshape(-1, 3)
            kind = "ammo" if "ammo" in mat else ("rail" if "rail" in mat else ("mag" if "magazine" in mat else "weapon"))
            if kind == "ammo":   # keep the centred shell row, drop the stray alternate-feed shells
                keep = (np.abs(P[T][:, :, 0]) < 0.04).all(1); T = T[keep]
            UV0 = glb.accessor(j, b, pr["attributes"]["TEXCOORD_0"]).astype(np.float64) if want_detail else None
            parts.append((kind, P, N, T, UV0, maps.slot(j, b, path, pr["material"]) if want_detail else -1))
    pts = {k: Wn[v][:3, 3].copy() for k, v in jn.items() if k in ("attach_mag", "attach_muzzle", "trigger", "attach_underbarrel", "sight", "attach_optic")}
    return parts, pts

parts, pts = load_parts(main)
for path, node in extras:
    p2, _ = load_parts(path, offset=pts[node])
    parts += p2

P = np.concatenate([p[1] for p in parts]); N = np.concatenate([p[2] for p in parts])
kinds = np.concatenate([[p[0]] * len(p[1]) for p in parts])
base = 0; Ts = []
for p in parts:
    Ts.append(p[3] + base); base += len(p[1])
T = np.concatenate(Ts)
slots = np.concatenate([[p[5]] * len(p[3]) for p in parts])
# mirror z so the barrel points +Z, fix winding
P[:, 2] *= -1; N[:, 2] *= -1; T = T[:, ::-1]
N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
for k in pts: pts[k][2] *= -1
print(name, "verts", len(P), "tris", len(T), "bbox", P.min(0).round(3), P.max(0).round(3), "keypoints", {k: v.round(3).tolist() for k, v in pts.items()})

# --- colour: base by part kind, wear on hard convex edges, dark in grooves
nV = len(P)
key = np.round(P * 4000).astype(np.int64)
_, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel(); nU = inv.max() + 1
A, B_, C_ = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
fn = np.cross(B_ - A, C_ - A); fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12); fc = (A + B_ + C_) / 3
edges = {}
for fi, t in enumerate(T):
    u = inv[t]
    for a, b in ((u[0], u[1]), (u[1], u[2]), (u[2], u[0])):
        edges.setdefault((a, b) if a < b else (b, a), []).append(fi)
wear = np.zeros(nU); groove = np.zeros(nU)
for (a, b), fs in edges.items():
    if len(fs) != 2: continue
    f0, f1 = fs
    ang = np.degrees(np.arccos(np.clip(np.dot(fn[f0], fn[f1]), -1, 1)))
    if ang < 50: continue
    if np.dot(fc[f1] - fc[f0], fn[f0]) < 0: wear[a] = wear[b] = 1
    else: groove[a] = groove[b] = 1
col = np.zeros((nV, 3))
for v in range(nV):
    c = PAL[kinds[v]].copy()
    if kinds[v] == "ammo" and P[v, 2] > 0.0 and False: c = BRASS
    if wear[inv[v]] > 0: c = c * 0.45 + WEAR * 0.55
    elif groove[inv[v]] > 0: c = c * 0.6
    col[v] = c * (0.9 + 0.2 * (0.5 + 0.5 * N[v, 1]))

# --- per-triangle unique texture cells
CELL = 8; SZ = 1024
perrow = SZ // CELL
nF = len(T); assert nF <= perrow * perrow
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
kp = [pts.get(k, np.zeros(3)) for k in ("trigger", "attach_muzzle", "attach_underbarrel")]
with open(outp + ".bin", "wb") as f:
    f.write(b"HDW1"); f.write(struct.pack("<II", nF * 3, nF))
    f.write(np.array(kp, dtype="<f4").tobytes())   # trigger, muzzle, underbarrel
    f.write(newP.astype("<f4").tobytes()); f.write(newN.astype("<f4").tobytes()); f.write(newUV.astype("<f4").tobytes())
    f.write(np.arange(nF * 3, dtype="<u4").tobytes())
print("wrote", outp, os.path.getsize(outp + ".bin"))
if want_detail:
    UV0 = np.concatenate([p[4] for p in parts]); UV0[:, 1] = 1 - UV0[:, 1]     # glTF v runs down the image
    detail.write(outp, UV0[T].reshape(-1, 2), slots, maps.paths)

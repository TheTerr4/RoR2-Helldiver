"""
Paint the fitted Helldiver mesh in the colours of the default (B-01 style) armour: charcoal suit, dark-grey plates with gold trim on the
hard convex edges, silver-grey top plates, black helmet/boots/gloves. The real HD2 armour is a layered material whose albedo can't be
extracted as one texture, so this bakes per-vertex colours into the mesh's own UV atlas.

  uv run --with numpy --with pillow python tools/paint.py fitted.bin out_tex.png [size]
"""
import sys, os, struct
import numpy as np
from PIL import Image, ImageFilter

src, out = sys.argv[1], sys.argv[2]
SZ = int(sys.argv[3]) if len(sys.argv) > 3 else 2048

f = open(src, "rb").read()
nV, nT, nB = struct.unpack("<III", f[4:16]); o = 16
names = []
for _ in range(nB):
    l = f[o]; names.append(f[o+1:o+1+l].decode()); o += 1 + l
P = np.frombuffer(f, "<f4", nV*3, o).reshape(nV, 3).astype(np.float64); o += nV*12
N = np.frombuffer(f, "<f4", nV*3, o).reshape(nV, 3).astype(np.float64); o += nV*12
UV = np.frombuffer(f, "<f4", nV*2, o).reshape(nV, 2).astype(np.float64); o += nV*8
BI = np.frombuffer(f, "<u1", nV*4, o).reshape(nV, 4); o += nV*4
BW = np.frombuffer(f, "<f4", nV*4, o).reshape(nV, 4); o += nV*16
T = np.frombuffer(f, "<u4", nT*3, o).reshape(nT, 3).astype(np.int64)

def hexc(h): return np.array([int(h[i:i+2], 16) for i in (1, 3, 5)], dtype=np.float64)
SUIT = hexc("#34323c"); PLATE = hexc("#4a4b56"); PLATE_HI = hexc("#9a9da6"); HELM = hexc("#2a2a31"); VISOR = hexc("#101216")
GOLD = hexc("#d9aa22"); GLOVE = hexc("#26262b"); BOOT = hexc("#222226"); STRAP = hexc("#2f2d33")

# --- topology on merged positions
key = np.round(P * 2000).astype(np.int64)
_, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel()
nU = inv.max() + 1
parent = np.arange(nU)
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
for t in T:
    a, b, c = inv[t]
    for u, v in ((a, b), (b, c)):
        ru, rv = find(u), find(v)
        if ru != rv: parent[ru] = rv
cu = np.array([find(i) for i in range(nU)])
_, comp = np.unique(cu, return_inverse=True)
vc = comp[inv]
sizes = np.bincount(vc)

# face normals / centres
A, B_, C_ = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
fn = np.cross(B_ - A, C_ - A); fl = np.linalg.norm(fn, axis=1, keepdims=True); fn = fn / np.maximum(fl, 1e-12)
fc = (A + B_ + C_) / 3

# edge adjacency over merged positions
edges = {}
for fi, t in enumerate(T):
    u = inv[t]
    for ia, ib in ((0, 1), (1, 2), (2, 0)):
        a, b = u[ia], u[ib]
        k = (a, b) if a < b else (b, a)
        edges.setdefault(k, []).append((fi, ia, ib))
convex_edges = []; concave_edges = []
for (a, b), fs in edges.items():
    if len(fs) != 2: continue
    (f0, ia0, ib0), (f1, _, _) = fs
    ang = np.degrees(np.arccos(np.clip(np.dot(fn[f0], fn[f1]), -1, 1)))
    if ang < 42: continue
    sgn = np.dot(fc[f1] - fc[f0], fn[f0])
    (convex_edges if sgn < 0 else concave_edges).append((f0, ia0, ib0, ang))

# per-component class
bone_of = np.array(names)[BI[:, 0]]
col = np.zeros((nV, 3)); plate_flag = np.zeros(nV, bool); gold_ok = np.zeros(nV, bool)
for v in range(nV):
    c = vc[v]; bn = bone_of[v]; y = P[v, 1]; big = sizes[c]
    if bn == "head":
        if y < 1.60: base = hexc("#34363e")             # neck scarf
        elif big < 500 and 1.70 < y < 1.80: base = VISOR
        else: base = HELM
        plate = y >= 1.60
    elif bn.startswith("hand"): base, plate = GLOVE, False
    elif bn.startswith("foot") or (bn.startswith("calf") and y < 0.30): base, plate = BOOT, True
    elif big >= 250 and bn in ("upper_arm.l", "upper_arm.r", "chest", "lower_arm.l", "lower_arm.r", "thigh.l", "thigh.r", "calf.l", "calf.r"):
        # large shells: undersuit unless they are the plate shells (heuristic: components far from the body centre line or on the torso front)
        base, plate = PLATE, True
    else: base, plate = STRAP, False
    # big smooth cloth shells (torso 75/29, arms, thighs) read as suit: darken the very large ones
    if big > 1300 or (bn.startswith("thigh") and big > 800): base, plate = SUIT, False
    c3 = base.copy()
    if plate and bn.startswith(("upper_arm", "chest")) and N[v, 1] > 0.6 and y > 1.3 and 120 < big < 1300: c3 = PLATE_HI
    plate_flag[v] = plate
    gold_ok[v] = (bn in ('head',) and y >= 1.62) or (bn.startswith('foot') and y > 0.07) or (bn.startswith('calf') and y < 0.30) or (bn.startswith('upper_arm') and 120 < big < 1300) or (bn.startswith('lower_arm') and 120 < big < 900)
    col[v] = c3


def elen(t, ia, ib): return float(np.linalg.norm(P[t[ia]] - P[t[ib]]))
gold_v = np.zeros(nV); dark_v = np.zeros(nV)
for (fi, ia, ib, ang) in convex_edges:
    t = T[fi]
    if ang > 70 and elen(t, ia, ib) < 0.035 and gold_ok[t[ia]] and gold_ok[t[ib]]:
        gold_v[t[ia]] = gold_v[t[ib]] = 1
for (fi, ia, ib, ang) in concave_edges:
    t = T[fi]
    if elen(t, ia, ib) < 0.045 and ang > 55:
        dark_v[t[ia]] = dark_v[t[ib]] = 1
# merged-position propagation so both sides of a seam agree
gm = np.zeros(nU); dm = np.zeros(nU)
np.maximum.at(gm, inv, gold_v); np.maximum.at(dm, inv, dark_v)
gold_v = gm[inv]; dark_v = dm[inv]
rng = np.random.default_rng(7)
for v in range(nV):
    c3 = col[v]
    if gold_v[v] > 0: c3 = GOLD * 0.9 + c3 * 0.1
    elif dark_v[v] > 0: c3 = c3 * 0.62
    shade = 0.92 + 0.16 * (0.5 + 0.5 * N[v, 1]) + rng.normal(0, 0.015)
    col[v] = c3 * shade

# --- unique per-triangle UV cells (the HD2 atlas overlaps/mirrors, so painting it would smear colours between parts)
CELL = 8
perrow = SZ // CELL
nF = len(T)
assert nF <= perrow * perrow, "atlas too small"
newP = P[T].reshape(-1, 3); newN = N[T].reshape(-1, 3)
newBI = BI[T].reshape(-1, 4); newBW = BW[T].reshape(-1, 4)
newUV = np.zeros((nF * 3, 2)); img = np.zeros((SZ, SZ, 3))
ys, xs = np.mgrid[0:CELL, 0:CELL]
lx = (xs + 0.5 - 0.5) / (CELL - 1.0); ly = (ys + 0.5 - 0.5) / (CELL - 1.0)  # 0..1 inside the cell
b1 = np.clip(lx, 0, 1); b2 = np.clip(ly, 0, 1)
tot = np.maximum(1, b1 + b2); b1 = b1 / tot if False else np.clip(b1, 0, 1); b2 = np.clip(b2, 0, 1)
s_ = b1 + b2
over = s_ > 1
b1 = np.where(over, b1 / s_, b1); b2 = np.where(over, b2 / s_, b2)
b0 = 1 - b1 - b2
for fi, t in enumerate(T):
    cx, cy = (fi % perrow) * CELL, (fi // perrow) * CELL
    img[cy:cy + CELL, cx:cx + CELL] = b0[..., None] * col[t[0]] + b1[..., None] * col[t[1]] + b2[..., None] * col[t[2]]
    # corners sit at texel centres of the cell's first/last texels
    p0 = ((cx + 0.5) / SZ, 1 - (cy + 0.5) / SZ)
    p1 = ((cx + CELL - 0.5) / SZ, 1 - (cy + 0.5) / SZ)
    p2 = ((cx + 0.5) / SZ, 1 - (cy + CELL - 0.5) / SZ)
    newUV[fi * 3] = p0; newUV[fi * 3 + 1] = p1; newUV[fi * 3 + 2] = p2
tex = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
tex.save(out)
newT = np.arange(nF * 3, dtype=np.uint32).reshape(-1, 3)
binout = os.path.splitext(out)[0] + ".bin"
with open(binout, "wb") as fo:
    fo.write(b"HDM1"); fo.write(struct.pack("<III", nF * 3, nF, nB))
    for n in names:
        e = n.encode(); fo.write(struct.pack("<B", len(e))); fo.write(e)
    fo.write(newP.astype("<f4").tobytes()); fo.write(newN.astype("<f4").tobytes()); fo.write(newUV.astype("<f4").tobytes())
    fo.write(newBI.astype("<u1").tobytes()); fo.write(newBW.astype("<f4").tobytes()); fo.write(newT.astype("<u4").tobytes())
print("wrote", out, tex.size, binout, os.path.getsize(binout))

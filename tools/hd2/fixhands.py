"""
Reflect the glove geometry of a Helldiver HDM1 mesh across the hand bone local Z=0 plane.

The HD2 body was fitted with a mirrored Z axis, which left the hands with the wrong chirality (the glove on `hand.r` is a left-hand shape,
thumb on local +X, palm = inside of the finger curl facing local +Z) and, because the glove is bound to the Commando rest pose with its palm
facing outward, any natural grip needs 110-160 degrees of wrist twist, which collapses a linear-blend wrist. Reflecting every vertex that is mostly
weighted to a hand bone across the bone's local Z=0 plane fixes both at once: the glove becomes the correct handedness and its palm now faces
the body at the rest pose (thumb forward, palm -Z). Triangles that are mostly hand get their winding reversed.

Optional --flip: afterwards roll the glove 180 degrees about the wrist axis (palm <-> back of hand) with a smooth twist ramp across the wrist
(angle 0 below WRIST0, 180 above WRIST1, in hand-local Y metres), so a posed hand can show its other side without any forearm twist at runtime.

  uv run --with numpy python fixhands.py in.bin out.bin [--flip] [skel.json]
"""
import sys, os, json, struct
import numpy as np

args = [a for a in sys.argv[1:] if not a.startswith("--")]
FLIP = "--flip" in sys.argv
src, dst = args[0], args[1]
skel = args[2] if len(args) > 2 else os.path.join(os.path.dirname(__file__), "commando_skel.json")
WRIST0, WRIST1 = -0.07, 0.04
B = {b["name"]: b for b in json.load(open(skel))["renderers"][0]["bones"]}

f = open(src, "rb").read()
nV, nT, nB = struct.unpack("<III", f[4:16]); o = 16
names = []
for _ in range(nB):
    l = f[o]; names.append(f[o + 1:o + 1 + l].decode()); o += 1 + l
head = f[:o]
P = np.frombuffer(f, "<f4", nV * 3, o).reshape(nV, 3).astype(np.float64); oP = o; o += nV * 12
N = np.frombuffer(f, "<f4", nV * 3, o).reshape(nV, 3).astype(np.float64); oN = o; o += nV * 12
UV = f[o:o + nV * 8]; o += nV * 8
BI = np.frombuffer(f, "<u1", nV * 4, o).reshape(nV, 4); o += nV * 4
BW = np.frombuffer(f, "<f4", nV * 4, o).reshape(nV, 4); o += nV * 16
T = np.frombuffer(f, "<u4", nT * 3, o).reshape(nT, 3).astype(np.int64)
assert o + nT * 12 == len(f), "unexpected file layout"

P2 = P.copy(); N2 = N.copy(); wh = np.zeros(nV)
for side in "rl":
    nm = "hand." + side
    idx = names.index(nm)
    w = (BW * (BI == idx)).sum(1)
    b = B[nm]; pos = np.array(b["pos"]); fwd = np.array(b["fwd"]); up = np.array(b["up"]); right = np.cross(up, fwd)
    R = np.stack([right, up, fwd], 1)           # columns: local x, y, z in mesh space
    sel = w > 0.5                               # hard cut at 50% hand weight: blending produced twisted triangles at the wrist
    lp = (P[sel] - pos) @ R; ln = N[sel] @ R
    wr = (lp[:, 1] > -0.06) & (lp[:, 1] < -0.02)
    cx, cz = lp[wr, 0].mean(), lp[wr, 2].mean()   # centre of the wrist cuff: reflect and roll about it so the cuff ring stays put
    lp[:, 2] = 2 * cz - lp[:, 2]; ln[:, 2] = -ln[:, 2]          # reflection across the local Z plane through the wrist centre
    if FLIP:
        t = np.clip((lp[:, 1] - WRIST0) / (WRIST1 - WRIST0), 0, 1); t = t * t * (3 - 2 * t)
        ang = np.pi * t; ca, sa = np.cos(ang), np.sin(ang)
        dx, dz = lp[:, 0] - cx, lp[:, 2] - cz
        lp[:, 0] = cx + dx * ca + dz * sa; lp[:, 2] = cz - dx * sa + dz * ca
        nx, nz = ln[:, 0].copy(), ln[:, 2].copy()
        ln[:, 0] = nx * ca + nz * sa; ln[:, 2] = -nx * sa + nz * ca
    P2[sel] = lp @ R.T + pos; N2[sel] = ln @ R.T
    wh[sel] = 1.0
    print(nm, "wrist centre (x,z)=(%.3f, %.3f)" % (cx, cz), "palm-region centroid after fix (hand-local):", np.round(lp[lp[:, 1] > 0.0].mean(0), 3))
N2 /= np.maximum(np.linalg.norm(N2, axis=1, keepdims=True), 1e-9)

flip = (wh[T] > 0.5).sum(1) >= 2        # triangles that are mostly hand: mirrored, so reverse their winding
T2 = T.copy(); T2[flip] = T[flip][:, [0, 2, 1]]
print("hand-weighted verts", int((wh > 0).sum()), "triangles flipped", int(flip.sum()), "of", nT)

with open(dst, "wb") as out:
    out.write(head)
    out.write(P2.astype("<f4").tobytes()); out.write(N2.astype("<f4").tobytes()); out.write(UV)
    out.write(BI.astype("<u1").tobytes()); out.write(BW.astype("<f4").tobytes()); out.write(T2.astype("<u4").tobytes())
print("wrote", dst, os.path.getsize(dst))

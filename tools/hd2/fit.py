"""
Fit the Helldivers 2 avatar mesh onto Risk of Rain 2's Commando skeleton (rest pose) and write a compact binary the mod loads at runtime.

  uv run --with numpy python tools/fit.py <avatar.glb> <skel.json> <out.bin> [preview_prefix]

Idea: pose the HD2 body (T-pose, its own proportions) so each limb segment lies on the matching Commando segment, using linear blend
skinning with one rigid(+axial scale) transform per Commando bone, then store the posed vertices with weights on Commando bones.
At runtime the Commando skeleton + its original bind poses animate it.
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import glb

ALPHA = float(os.environ.get("FIT_ALPHA", "0.65"))  # how much of the axial length ratio is applied (1 = joints coincide exactly)

avatar, skelpath, outpath = sys.argv[1], sys.argv[2], sys.argv[3]
prev = sys.argv[4] if len(sys.argv) > 4 else None

j, b = glb.load(avatar)
Wn = glb.node_world(j)
skin = j["skins"][0]
jnames = [j["nodes"][i]["name"] for i in skin["joints"]]
jnode = {j["nodes"][i]["name"]: i for i in skin["joints"]}
def hp(name):  # HD2 rest joint position in "Unity-like" space (z flipped so the character faces +Z)
    p = Wn[jnode[name]][:3, 3].copy(); p[2] = -p[2]; return p

cmd = json.load(open(skelpath))["renderers"][0]["bones"]
cname = {bn["name"]: bn for bn in cmd}
def cp(name): return np.array(cname[name]["pos"], dtype=np.float64)

# (commando bone) -> (hd2 start joint, hd2 end joint or None, commando end bone or None)
SEG = {
    "pelvis":      ("hips", None, None),
    "stomach":     ("spine1", "spine2", "chest"),
    "chest":       ("spine2", "neck", "head"),
    "head":        ("neck", None, None),
    "upper_arm.l": ("l_shoulder", "l_elbow", "lower_arm.l"),
    "lower_arm.l": ("l_elbow", "l_hand", "hand.l"),
    "hand.l":      ("l_hand", None, None),
    "upper_arm.r": ("r_shoulder", "r_elbow", "lower_arm.r"),
    "lower_arm.r": ("r_elbow", "r_hand", "hand.r"),
    "hand.r":      ("r_hand", None, None),
    "thigh.l":     ("l_thigh", "l_knee", "calf.l"),
    "calf.l":      ("l_knee", "l_foot", "foot.l"),
    "foot.l":      ("l_foot", "l_toe", "toe.l"),
    "thigh.r":     ("r_thigh", "r_knee", "calf.r"),
    "calf.r":      ("r_knee", "r_foot", "foot.r"),
    "foot.r":      ("r_foot", "r_toe", "toe.r"),
}

def rot_between(a, bv):
    a = a / np.linalg.norm(a); bv = bv / np.linalg.norm(bv)
    v = np.cross(a, bv); c = float(np.dot(a, bv)); s = np.linalg.norm(v)
    if s < 1e-8: return np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx * ((1 - c) / (s * s))

G = {}  # commando bone -> 4x4 transform in the shared (Unity-like) space
for cb, (hs, he, ce) in SEG.items():
    ps = hp(hs); pt = cp(cb)
    R = np.eye(3); k = 1.0; d = np.array([0, 1.0, 0])
    if he is not None:
        s = hp(he) - ps; t = cp(ce) - pt
        R = rot_between(s, t)
        d = t / np.linalg.norm(t)
        k = 1 + ALPHA * (np.linalg.norm(t) / np.linalg.norm(s) - 1)
        if cb.startswith(('foot', 'hand')): k = 1.0
    # axial scale along d (after rotation), pivot at the segment start
    S = np.eye(3) + (k - 1) * np.outer(d, d)
    M = np.eye(4); M[:3, :3] = S @ R; M[:3, 3] = pt - S @ R @ ps
    G[cb] = M
    print(f"{cb:12s} <- {hs:11s} k={k:.2f} shift={np.round(pt - ps, 3)}")

# HD2 joint -> commando bone
def bone_for(jn):
    n = jn
    side = "l" if n.startswith("l_") else ("r" if n.startswith("r_") else "")
    base = n[2:] if side else n
    sfx = ".l" if side == "l" else (".r" if side == "r" else "")
    if base in ("hips", "boss", "root", "boss_aim", "climb_ref"): return "pelvis"
    if base in ("spine1",): return "stomach"
    if base in ("spine2", "chest", "clavicle", "backpack", "support", "support_mg", "sling", "attach_weapon", "aim_weapon") or base.startswith("clavicle"): return "chest"
    if base in ("neck", "head", "head_aim") or base.startswith("head"): return "head"
    if base.startswith("shoulder") and "armour" not in base: return "upper_arm" + sfx if base == "shoulder" or base == "shoulder_twist" else "upper_arm" + sfx
    if "shoulderarmour" in base or "shoulder_armour" in base: return "upper_arm" + sfx
    if base.startswith("elbow") or "forearm" in base: return "lower_arm" + sfx
    if base.startswith("hand") or "finger" in base or base.startswith("thumb"): return "hand" + sfx
    if base.startswith("thigh"): return "thigh" + sfx
    if base.startswith("knee"): return "calf" + sfx
    if base in ("foot",): return "foot" + sfx
    if base.startswith("ball"): return "foot" + sfx
    if base.startswith("toe"): return "foot" + sfx
    if base.startswith("cape"): return "chest"
    return None

unmapped = sorted({n for n in jnames if bone_for(n) is None})
print("unmapped joints (-> pelvis):", unmapped[:40])
jbone = [bone_for(n) or "pelvis" for n in jnames]
for jb in set(jbone):
    if jb not in G: print("MISSING transform for", jb, [n for n, x in zip(jnames, jbone) if x == jb][:6]); G[jb] = np.eye(4)

# body mesh only (mesh 0); the cape (mesh 1) is skipped for now
pr = j["meshes"][0]["primitives"][0]
P = glb.accessor(j, b, pr["attributes"]["POSITION"]).astype(np.float64); P[:, 2] *= -1
N = glb.accessor(j, b, pr["attributes"]["NORMAL"]).astype(np.float64); N[:, 2] *= -1
UV = glb.accessor(j, b, pr["attributes"]["TEXCOORD_0"]).astype(np.float64)
J = glb.accessor(j, b, pr["attributes"]["JOINTS_0"]).astype(np.int64)
Wt = glb.accessor(j, b, pr["attributes"]["WEIGHTS_0"]).astype(np.float64)
T = glb.accessor(j, b, pr["indices"]).astype(np.int64).reshape(-1, 3)[:, ::-1]  # flip winding for the mirrored axis

used = sorted(set(jbone))
bidx = {n: i for i, n in enumerate(used)}
nV = len(P)
agg = np.zeros((nV, len(used)))
for k in range(J.shape[1]):
    for v in range(nV):
        if Wt[v, k] > 0: agg[v, bidx[jbone[J[v, k]]]] += Wt[v, k]
# keep the 4 strongest bone influences per vertex
top = np.argsort(-agg, axis=1)[:, :4]
bw = np.take_along_axis(agg, top, 1)
bw /= np.maximum(bw.sum(1, keepdims=True), 1e-9)

Pn = np.zeros_like(P); Nn = np.zeros_like(N)
Ph = np.concatenate([P, np.ones((nV, 1))], 1)
for slot in range(4):
    for bi, name in enumerate(used):
        m = (top[:, slot] == bi) & (bw[:, slot] > 0)
        if not m.any(): continue
        M = G[name]
        Pn[m] += bw[m, slot, None] * (Ph[m] @ M.T)[:, :3]
        Nn[m] += bw[m, slot, None] * (N[m] @ M[:3, :3].T)
Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
print("fitted bounds", Pn.min(0).round(3), Pn.max(0).round(3), "commando body ~ y 0..1.95")

# --- write binary
with open(outpath, "wb") as f:
    f.write(b"HDM1")
    f.write(struct.pack("<III", nV, len(T), len(used)))
    for n in used:
        e = n.encode(); f.write(struct.pack("<B", len(e))); f.write(e)
    f.write(Pn.astype("<f4").tobytes())
    f.write(Nn.astype("<f4").tobytes())
    uv = UV.copy(); uv[:, 1] = 1 - uv[:, 1]
    f.write(uv.astype("<f4").tobytes())
    f.write(top.astype("<u1").tobytes())
    f.write(bw.astype("<f4").tobytes())
    f.write(T.astype("<u4").tobytes())
print("wrote", outpath, os.path.getsize(outpath))

if prev:
    import render
    from PIL import Image
    meshes = [(0, Pn, Nn, T, 0)]
    # commando reference points
    render.render(meshes, prev + "_front.png", view="front")
    render.render(meshes, prev + "_side.png", view="side")
    a = Image.open(prev + "_front.png"); s = Image.open(prev + "_side.png")
    c = Image.new("RGB", (1200, 900)); c.paste(a, (0, 0)); c.paste(s, (600, 0)); c.save(prev + "_both.png")

# --- bake a stylised colour texture from per-vertex region colours (the HD2 armour textures live in unnamed packages)
from PIL import Image
def hexc(h): return np.array([int(h[i:i+2], 16) for i in (1, 3, 5)], dtype=np.float64)
ARMOR = hexc("#5d6552"); ARMOR_HI = hexc("#737b64"); SUIT = hexc("#3b4036"); HELM = hexc("#434a43"); GLOVE = hexc("#26292a")
BOOT = hexc("#2b2d2e"); SCARF = hexc("#8c7b55"); STRAP = hexc("#6b5d3e")
bone_of = np.array(used)[top[:, 0]]
col = np.zeros((nV, 3))
for v in range(nV):
    y = Pn[v, 1]; bn = bone_of[v]
    if bn == "head":
        c = HELM if y > 1.64 else SCARF
    elif bn.startswith("hand"): c = GLOVE
    elif bn.startswith(("foot",)) or (bn.startswith("calf") and y < 0.28): c = BOOT
    elif bn.startswith(("thigh", "calf")): c = SUIT if abs(Nn[v, 0]) < 0.5 else ARMOR
    elif bn.startswith(("upper_arm",)): c = ARMOR_HI if Nn[v, 1] > 0.3 else ARMOR
    elif bn.startswith("lower_arm"): c = ARMOR
    elif bn in ("chest",): c = ARMOR_HI if Nn[v, 1] > 0.4 else ARMOR
    else: c = SUIT
    col[v] = c * (0.9 + 0.2 * (0.5 + 0.5 * Nn[v, 1]))
SZ = 1024
img = np.zeros((SZ, SZ, 3)); cov = np.zeros((SZ, SZ), bool)
for t in T:
    uv = UV[t] * SZ; uv[:, 1] = SZ - uv[:, 1]
    x0, x1 = int(max(0, np.floor(uv[:, 0].min()))), int(min(SZ - 1, np.ceil(uv[:, 0].max())))
    y0, y1 = int(max(0, np.floor(uv[:, 1].min()))), int(min(SZ - 1, np.ceil(uv[:, 1].max())))
    if x1 < x0 or y1 < y0: continue
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    d = (uv[1, 1] - uv[2, 1]) * (uv[0, 0] - uv[2, 0]) + (uv[2, 0] - uv[1, 0]) * (uv[0, 1] - uv[2, 1])
    if abs(d) < 1e-9: continue
    w0 = ((uv[1, 1] - uv[2, 1]) * (gx - uv[2, 0]) + (uv[2, 0] - uv[1, 0]) * (gy - uv[2, 1])) / d
    w1 = ((uv[2, 1] - uv[0, 1]) * (gx - uv[2, 0]) + (uv[0, 0] - uv[2, 0]) * (gy - uv[2, 1])) / d
    w2 = 1 - w0 - w1
    m = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
    cc = w0[..., None] * col[t[0]] + w1[..., None] * col[t[1]] + w2[..., None] * col[t[2]]
    sub = img[y0:y1 + 1, x0:x1 + 1]; sc = cov[y0:y1 + 1, x0:x1 + 1]
    sub[m] = cc[m]; sc[m] = True
# fill uncovered texels with a neutral suit colour and dilate a little so filtering never shows black
img[~cov] = SUIT
tex = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
texpath = os.path.splitext(outpath)[0] + "_tex.png"
tex.save(texpath); print("wrote", texpath)

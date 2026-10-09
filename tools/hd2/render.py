import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import glb, numpy as np
from PIL import Image

def mesh_data(path):
    j, b = glb.load(path)
    out = []
    for mi, m in enumerate(j["meshes"]):
        for pr in m["primitives"]:
            P = glb.accessor(j, b, pr["attributes"]["POSITION"]).astype(np.float64)
            N = glb.accessor(j, b, pr["attributes"]["NORMAL"]).astype(np.float64)
            idx = glb.accessor(j, b, pr["indices"]).astype(np.int64) if "indices" in pr else np.arange(len(P))
            out.append((mi, P, N, idx.reshape(-1, 3), pr.get("material")))
    return out

def render(meshes, out, W=600, H=900, view="front", colors=None):
    # orthographic z-buffer rasterizer with normal shading
    allP = np.concatenate([m[1] for m in meshes])
    lo, hi = allP.min(0), allP.max(0)
    ctr = (lo + hi) / 2
    if view == "front": ax = (0, 1); depth = 2; sign = 1
    else: ax = (2, 1); depth = 0; sign = 1
    scale = min(W / (hi[ax[0]] - lo[ax[0]]), H / (hi[ax[1]] - lo[ax[1]])) * 0.92
    img = np.zeros((H, W, 3), np.uint8) + 30
    zb = np.full((H, W), -1e9)
    cols = colors or [(230, 200, 80), (120, 180, 230), (200, 120, 120), (120, 220, 140)]
    for k, (mi, P, N, T, mat) in enumerate(meshes):
        col = np.array(cols[k % len(cols)], dtype=np.float64)
        X = (P[:, ax[0]] - ctr[ax[0]]) * scale + W / 2
        Y = H / 2 - (P[:, ax[1]] - ctr[ax[1]]) * scale
        Z = P[:, depth] * sign
        for t in T:
            xs, ys, zs = X[t], Y[t], Z[t]
            n = N[t].mean(0); ln = np.linalg.norm(n)
            sh = 0.35 + 0.65 * max(0, (n[depth] * sign) / ln if ln else 0)
            x0, x1 = int(max(0, np.floor(xs.min()))), int(min(W - 1, np.ceil(xs.max())))
            y0, y1 = int(max(0, np.floor(ys.min()))), int(min(H - 1, np.ceil(ys.max())))
            if x1 < x0 or y1 < y0: continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
            if abs(d) < 1e-9: continue
            w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
            w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
            w2 = 1 - w0 - w1
            m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            z = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
            sub = zb[y0:y1 + 1, x0:x1 + 1]
            upd = m & (z > sub)
            sub[upd] = z[upd]
            img[y0:y1 + 1, x0:x1 + 1][upd] = (col * sh).astype(np.uint8)
    Image.fromarray(img).save(out)

if __name__ == "__main__":
    md = mesh_data(sys.argv[1])
    print([(m[0], len(m[1]), len(m[3]), m[4]) for m in md])
    render(md, sys.argv[2] + "_front.png", view="front")
    render(md, sys.argv[2] + "_side.png", view="side")

import sys, os, struct
import numpy as np
from PIL import Image
f = open(sys.argv[1], "rb").read(); tex = np.asarray(Image.open(sys.argv[2]).convert("RGB")); out = sys.argv[3]
nV, nT, nB = struct.unpack("<III", f[4:16]); o = 16
for _ in range(nB):
    l = f[o]; o += 1 + l
P = np.frombuffer(f, "<f4", nV*3, o).reshape(nV, 3).astype(np.float64); o += nV*12
N = np.frombuffer(f, "<f4", nV*3, o).reshape(nV, 3).astype(np.float64); o += nV*12
UV = np.frombuffer(f, "<f4", nV*2, o).reshape(nV, 2).astype(np.float64); o += nV*8 + nV*4 + nV*16
T = np.frombuffer(f, "<u4", nT*3, o).reshape(nT, 3).astype(np.int64)
TH, TW = tex.shape[:2]
W, H = 520, 760
lo, hi = P.min(0), P.max(0); ctr = (lo + hi) / 2
scale = min(W / (hi[0] - lo[0]), H / (hi[1] - lo[1])) * 0.9
views = []
for ang in (0, 50, 130, 180):
    a = np.radians(ang); R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    Pr = (P - ctr) @ R.T; Nr = N @ R.T
    X = Pr[:, 0] * scale + W / 2; Y = H / 2 - Pr[:, 1] * scale; Z = Pr[:, 2]
    img = np.zeros((H, W, 3), np.uint8) + 35; zb = np.full((H, W), -1e9)
    L = np.array([0.35, 0.6, 0.72]); L /= np.linalg.norm(L)
    for t in T:
        xs, ys, zs = X[t], Y[t], Z[t]
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
        sub = zb[y0:y1 + 1, x0:x1 + 1]; upd = m & (z > sub)
        if not upd.any(): continue
        sub[upd] = z[upd]
        u = w0 * UV[t[0], 0] + w1 * UV[t[1], 0] + w2 * UV[t[2], 0]; v = w0 * UV[t[0], 1] + w1 * UV[t[1], 1] + w2 * UV[t[2], 1]
        tx = np.clip((u * TW).astype(int), 0, TW - 1); ty = np.clip(((1 - v) * TH).astype(int), 0, TH - 1)
        c = tex[ty, tx].astype(np.float64)
        n = w0[..., None] * Nr[t[0]] + w1[..., None] * Nr[t[1]] + w2[..., None] * Nr[t[2]]
        n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-9)
        sh = 0.30 + 0.85 * np.clip((n * L).sum(2), 0, 1)
        img[y0:y1 + 1, x0:x1 + 1][upd] = np.clip(c * sh[..., None], 0, 255).astype(np.uint8)[upd]
    views.append(Image.fromarray(img))
s = Image.new("RGB", (W * 4, H))
for i, v in enumerate(views): s.paste(v, (i * W, 0))
s.save(out)

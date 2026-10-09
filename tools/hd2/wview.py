import sys, struct
import numpy as np
from PIL import Image
def load(binp, texp):
    f = open(binp, "rb").read(); nV, nT = struct.unpack("<II", f[4:12]); o = 12 + 36
    P = np.frombuffer(f, "<f4", nV*3, o).reshape(nV, 3).astype(np.float64); o += nV*12
    N = np.frombuffer(f, "<f4", nV*3, o).reshape(nV, 3).astype(np.float64); o += nV*12
    UV = np.frombuffer(f, "<f4", nV*2, o).reshape(nV, 2).astype(np.float64); o += nV*8
    T = np.frombuffer(f, "<u4", nT*3, o).reshape(nT, 3).astype(np.int64)
    return P, N, UV, T, np.asarray(Image.open(texp).convert("RGB"))
def render(P, N, UV, T, tex, ang, W=700, H=380):
    TH, TW = tex.shape[:2]
    a = np.radians(ang); R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    lo, hi = P.min(0), P.max(0); ctr = (lo + hi) / 2
    Pr = (P - ctr) @ R.T; Nr = N @ R.T
    sc = min(W / (np.ptp(Pr[:, 0]) + 1e-6), H / (np.ptp(Pr[:, 1]) + 1e-6)) * 0.9
    X = Pr[:, 0] * sc + W / 2; Y = H / 2 - Pr[:, 1] * sc; Z = Pr[:, 2]
    img = np.zeros((H, W, 3), np.uint8) + 45; zb = np.full((H, W), -1e9)
    L = np.array([0.4, 0.6, 0.7]); L /= np.linalg.norm(L)
    for t in T:
        xs, ys, zs = X[t], Y[t], Z[t]
        x0, x1 = int(max(0, np.floor(xs.min()))), int(min(W - 1, np.ceil(xs.max()))); y0, y1 = int(max(0, np.floor(ys.min()))), int(min(H - 1, np.ceil(ys.max())))
        if x1 < x0 or y1 < y0: continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(d) < 1e-9: continue
        w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d; w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d; w2 = 1 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0); z = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]; upd = m & (z > sub)
        if not upd.any(): continue
        sub[upd] = z[upd]
        u = w0 * UV[t[0], 0] + w1 * UV[t[1], 0] + w2 * UV[t[2], 0]; v = w0 * UV[t[0], 1] + w1 * UV[t[1], 1] + w2 * UV[t[2], 1]
        c = tex[np.clip(((1 - v) * TH).astype(int), 0, TH - 1), np.clip((u * TW).astype(int), 0, TW - 1)].astype(np.float64)
        n = w0[..., None] * Nr[t[0]] + w1[..., None] * Nr[t[1]] + w2[..., None] * Nr[t[2]]; n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-9)
        sh = 0.3 + 0.9 * np.clip((n * L).sum(2), 0, 1)
        img[y0:y1 + 1, x0:x1 + 1][upd] = np.clip(c * sh[..., None], 0, 255).astype(np.uint8)[upd]
    return Image.fromarray(img)
out = Image.new("RGB", (1400, 760))
for r, (b, t) in enumerate([("wl.bin", "wl_tex.png"), ("wb.bin", "wb_tex.png")]):
    d = load(b, t)
    for i, ang in enumerate((90, 0)):  # side (barrel left->right) and from the muzzle
        out.paste(render(*d, ang), (i * 700, r * 380))
out.save("wview.png")

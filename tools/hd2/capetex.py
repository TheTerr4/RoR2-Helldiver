"""
Bake the cape textures from the HD2 standard cape's own maps (extracted with filediver from content/fac_helldivers/capes/textures):

  uv run --with numpy --with pillow python capetex.py <standard_medium_cape_cfd.png> <standard_medium_cape_tear.png> <out_dir> [logo.png cape.bin]

HD2 only stores a normal map ("cfd": folds, hemmed side strips, V neckline) and a tear mask for the cape, the colour comes from a procedural material,
so the colour layer here is our own: dark cloth, a slightly lighter hemmed border with a stitch line, and fraying toward the hem. The tear mask drives the alpha
(the ragged lower edge, used as a cutout in game) and a darkening toward the hem.
With a logo (white on transparent, e.g. Assets/Helldivers_2_Logo_white.png) and the cape grid (HDC2, for its UVs) the logo is printed across the upper back the way the HD2
standard cape has it: centred, ~17 cm under the shoulder line, ~43 cm wide. It is placed in world metres and mapped through the grid's UVs, so it keeps its proportions.
Writes cape_tex.png (RGBA 1024, alpha = cutout) and cape_nrm.png (RGB 1024 tangent-space normal map).
"""
import sys, os
import numpy as np
from PIL import Image, ImageFilter

nrm_p, tear_p, out = sys.argv[1], sys.argv[2], sys.argv[3]
S = 1024
nrm = Image.open(nrm_p).convert("RGB")
tear = Image.open(tear_p).convert("L")
n = np.asarray(nrm).astype(np.float32)

# island = where the normal map differs from the flat colour
flat = np.array([128, 128, 255], np.float32)
dev = np.abs(n - np.median(n.reshape(-1, 3), axis=0)).sum(2)
mask = Image.fromarray(((dev > 10) * 255).astype(np.uint8))
mask = mask.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MinFilter(15)).filter(ImageFilter.MaxFilter(15))   # close gaps, then drop specks
mk = np.asarray(mask) > 0
for r in range(mk.shape[0]):                               # the island is convex across each row: fill flat pixels inside it
    xs = np.nonzero(mk[r])[0]
    if len(xs) > 8 and xs[-1] - xs[0] > 20: mk[r, xs[0]:xs[-1] + 1] = True
mask = Image.fromarray((mk * 255).astype(np.uint8))
inner = mask.filter(ImageFilter.MinFilter(33))            # ~16 px in from the edge at 1024
trim = np.asarray(mask).astype(np.float32) / 255 - np.asarray(inner).astype(np.float32) / 255
inner2 = mask.filter(ImageFilter.MinFilter(45))           # stitch line just inside the border
stitch = np.asarray(inner).astype(np.float32) / 255 - np.asarray(inner2).astype(np.float32) / 255

rng = np.random.RandomState(7)
H = 1024
yy, xx = np.mgrid[0:H, 0:H]
weave = 1.0 + 0.07 * (((xx // 2 + yy // 2) % 4) == 0)     # faint twill
grain = 0.9 + 0.2 * rng.rand(H, H).astype(np.float32)
base = np.array([0.105, 0.108, 0.120], np.float32)       # dark charcoal with a hint of blue
col = base[None, None, :] * (weave * grain)[:, :, None]

t = np.asarray(tear.resize((H, H), Image.BILINEAR)).astype(np.float32) / 255
col *= (0.55 + 0.45 * np.clip(t * 1.1, 0, 1))[:, :, None]                       # fraying darkens the hem
col = np.where(trim[:, :, None] > 0.5, col * np.array([1.55, 1.55, 1.5], np.float32), col)   # lighter hemmed border
dash = (((xx + yy) // 6) % 2 == 0).astype(np.float32)
col = np.where((stitch * dash)[:, :, None] > 0.5, col * 0.55, col)                  # dashed stitch line

# logo print
if len(sys.argv) > 5:
    import struct
    LOGO_Y, LOGO_W = 1.43, 0.43                 # centre height (grid row 0 is y=1.60) and width in metres
    g = open(sys.argv[5], "rb").read()
    gc, gr = struct.unpack("<ii", g[4:12]); nv = gc * gr
    gp = np.frombuffer(g, "<f4", nv * 3, 12).reshape(gr, gc, 3).astype(np.float64)
    gu = np.frombuffer(g, "<f4", nv * 2, 12 + nv * 12).reshape(gr, gc, 2).astype(np.float64)
    logo = Image.open(sys.argv[4]).convert("RGBA"); logo = logo.crop(logo.getchannel("A").getbbox())
    lw, lh = logo.size; LOGO_H = LOGO_W * lh / lw
    la = np.asarray(logo).astype(np.float32) / 255
    acc = np.zeros((H, H, 4), np.float32); cnt = np.zeros((H, H), np.float32)
    ys0, ys1 = gp[0, 0, 1], gp[-1, 0, 1]
    jj, ii = np.mgrid[0:lh, 0:lw]
    wx = (ii + 0.5) / lw * LOGO_W - LOGO_W / 2
    wy = LOGO_Y + LOGO_H / 2 - (jj + 0.5) / lh * LOGO_H
    fr = np.clip((wy - ys0) / (ys1 - ys0) * (gr - 1), 0, gr - 1 - 1e-6); r0 = fr.astype(int); ft = fr - r0
    def at(r, x):                                   # uv of world (x, row r) by interpolating across the row
        hw = gp[r, -1, 0]
        fc = np.clip((x + hw) / (2 * hw) * (gc - 1), 0, gc - 1 - 1e-6); c0 = fc.astype(int); fcf = fc - c0
        return gu[r, c0] * (1 - fcf)[..., None] + gu[r, c0 + 1] * fcf[..., None]
    uv = at(r0, wx) * (1 - ft)[..., None] + at(np.minimum(r0 + 1, gr - 1), wx) * ft[..., None]
    px = np.clip((uv[..., 0] * H).astype(int), 0, H - 1); py = np.clip(((1 - uv[..., 1]) * H).astype(int), 0, H - 1)
    np.add.at(acc, (py, px), la * la[..., 3:4]); np.add.at(cnt, (py, px), la[..., 3])
    cov = np.minimum(cnt, 1.0)                                   # many logo pixels land in one texel: the average alpha is the coverage
    n_px = np.zeros((H, H), np.float32); np.add.at(n_px, (py, px), 1.0)
    cover = np.where(n_px > 0, cnt / np.maximum(n_px, 1), 0)
    cover = np.asarray(Image.fromarray((cover * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255   # close texel gaps
    ink = np.array([0.80, 0.80, 0.78], np.float32)               # slightly worn white print
    worn = (0.82 + 0.18 * rng.rand(H, H).astype(np.float32)) * weave
    col = col * (1 - cover[:, :, None]) + (ink[None, None, :] * worn[:, :, None]) * cover[:, :, None]
    print("logo %.2f x %.3f m, texel box" % (LOGO_W, LOGO_H), px.min(), px.max(), py.min(), py.max())

# alpha: torn hem
noise = np.asarray(Image.fromarray((rng.rand(64, 64) * 255).astype(np.uint8)).resize((H, H), Image.BICUBIC)).astype(np.float32) / 255
a = np.clip((t + (noise - 0.5) * 0.25 - 0.28) / 0.25, 0, 1)
a[t > 0.98] = 1.0

rgba = np.dstack([np.clip(col, 0, 1), a])
Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").resize((S, S), Image.LANCZOS).save(os.path.join(out, "cape_tex.png"))
nrm.resize((S, S), Image.LANCZOS).save(os.path.join(out, "cape_nrm.png"))
print("wrote", out, "island px", int((np.asarray(mask) > 0).sum()), "trim px", int((trim > 0.5).sum()))

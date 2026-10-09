"""
Resample the full HD2 cape (HDC1 from cape.py, ~1000 vertices) into a coarse grid for the runtime cloth.

  uv run --with numpy python capegrid.py <cape_hdc1.bin> <out.bin> [cols rows]

Per grid row: x spans the cape's width at that height, z follows a quadratic fit of the original surface across x (the cloak wraps around the back),
then z is smoothed over the rows so the sculpted folds are gone. Output HDC2: "HDC2", cols i32, rows i32, positions f32x3, uvs f32x2 (row-major, row 0 = shoulders; uvs follow the original cape UV layout so Model/cape_tex.png / cape_nrm.png line up).
The runtime (Cape.cs) simulates every second row/column and renders the full grid by bilinear interpolation.
"""
import sys, struct
import numpy as np

src, out = sys.argv[1], sys.argv[2]
COLS = int(sys.argv[3]) if len(sys.argv) > 3 else 9
ROWS = int(sys.argv[4]) if len(sys.argv) > 4 else 13
Y_TOP, Y_HEM = 1.60, 0.27

f = open(src, "rb").read()
assert f[:4] == b"HDC1"
nV, nT = struct.unpack("<II", f[4:12])
P = np.frombuffer(f, "<f4", nV * 3, 12).reshape(nV, 3).astype(np.float64)
UV = np.frombuffer(f, "<f4", nV * 2, 12 + nV * 24).reshape(nV, 2).astype(np.float64)   # after positions and normals

grid = np.zeros((ROWS, COLS, 3)); guv = np.zeros((ROWS, COLS, 2))
for r in range(ROWS):
    y = Y_TOP + (Y_HEM - Y_TOP) * r / (ROWS - 1)
    band = 0.045
    m = np.abs(P[:, 1] - y) < band
    while m.sum() < 12:
        band *= 1.5; m = np.abs(P[:, 1] - y) < band
    q = P[m]
    x0, x1 = np.percentile(q[:, 0], 2), np.percentile(q[:, 0], 98)
    hw = (x1 - x0) / 2; xs = np.linspace(-hw, hw, COLS)   # symmetric about the spine
    c = np.polyfit(q[:, 0] - (x0 + x1) / 2, q[:, 2], 2)
    grid[r, :, 0] = xs; grid[r, :, 1] = y; grid[r, :, 2] = np.polyval(c, xs)
    cu = np.polyfit(q[:, 0] - (x0 + x1) / 2, UV[m][:, 0], 2); cv = np.polyfit(q[:, 0] - (x0 + x1) / 2, UV[m][:, 1], 1)
    guv[r, :, 0] = np.polyval(cu, xs); guv[r, :, 1] = np.polyval(cv, xs)

# smooth z over the rows (keep the top row, it is hidden under the pack anyway)
z = grid[:, :, 2].copy()
for _ in range(2):
    zs = z.copy()
    zs[1:-1] = (z[:-2] + 2 * z[1:-1] + z[2:]) / 4
    z = zs
grid[:, :, 2] = z

# the hood and collar of the body stick out behind the shoulders: move the top rows back so the cape starts clear of them (fades out by row 5)
for r in range(min(5, ROWS)):
    grid[r, :, 2] -= 0.05 * (1 - r / 5)

with open(out, "wb") as o:
    o.write(b"HDC2"); o.write(struct.pack("<ii", COLS, ROWS)); o.write(grid.astype("<f4").tobytes()); o.write(guv.astype("<f4").tobytes())
print("wrote", out, "cols", COLS, "rows", ROWS)
for r in (0, 2, 4, 8, 12 if ROWS > 12 else ROWS - 1):
    print("row %2d y=%.2f x[%.2f..%.2f] z[centre %.2f edge %.2f]" % (r, grid[r, 0, 1], grid[r, 0, 0], grid[r, -1, 0], grid[r, COLS // 2, 2], grid[r, 0, 2]))
for r in (0, 4, 8, ROWS - 1):
    print("uv row %2d: u[%.3f..%.3f] v[%.3f..%.3f]" % (r, guv[r, 0, 0], guv[r, -1, 0], guv[r, 0, 1], guv[r, -1, 1]))

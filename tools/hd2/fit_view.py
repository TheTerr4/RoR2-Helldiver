import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, render
from PIL import Image
f = open(sys.argv[1], "rb").read()
nV, nT, nB = struct.unpack("<III", f[4:16]); o = 16
for _ in range(nB):
    l = f[o]; o += 1 + l
P = np.frombuffer(f, "<f4", nV * 3, o).reshape(nV, 3).astype(np.float64); o += nV * 12
N = np.frombuffer(f, "<f4", nV * 3, o).reshape(nV, 3).astype(np.float64); o += nV * 12 + nV * 8 + nV * 4 + nV * 16
T = np.frombuffer(f, "<u4", nT * 3, o).reshape(nT, 3).astype(np.int64)
imgs = []
for ang in (0, 40, 90, 180):
    a = np.radians(ang); R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    render.render([(0, P @ R.T, N @ R.T, T, 0)], "_tmp.png", W=450, H=700, view="front")
    imgs.append(Image.open("_tmp.png"))
s = Image.new("RGB", (1800, 700))
for i, im in enumerate(imgs): s.paste(im, (i * 450, 0))
s.save(sys.argv[2])

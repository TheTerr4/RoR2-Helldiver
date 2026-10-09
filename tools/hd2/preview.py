import sys, glob, os
sys.path.insert(0, os.path.dirname(__file__))
import glb, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
files = sys.argv[2:]
fig, axes = plt.subplots(1, len(files), figsize=(4 * len(files), 6))
if len(files) == 1: axes = [axes]
for ax, p in zip(axes, files):
    j, b = glb.load(p)
    pts = []
    for mi, m in enumerate(j["meshes"]):
        for pr in m["primitives"]:
            pts.append(glb.accessor(j, b, pr["attributes"]["POSITION"]))
    P = np.concatenate(pts)
    ax.scatter(P[:, 0], P[:, 1], s=0.2, c=P[:, 2], cmap="viridis")
    ax.set_aspect("equal"); ax.set_title(os.path.basename(p)[:28] + f"\n{len(P)} v  y:[{P[:,1].min():.2f},{P[:,1].max():.2f}]", fontsize=8)
plt.savefig(sys.argv[1], dpi=80)

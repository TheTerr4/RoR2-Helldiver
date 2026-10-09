"""
HD2 normal maps as bake sources for optimize.py: weapon.py and pack.py call write() when run with --detail, so the low-poly bake picks up the
panel lines, screws and vents that HD2 keeps in its normal maps rather than in the geometry.

Output: <out_prefix>_detail.npz with
  uv    (nTris*3, 2) float32  the HD2 UV of every triangle corner, in the same corner order as the .bin file, v up (Blender/Unity convention)
  slot  (nTris,)     int16    index into maps (-1 = no normal map)
  maps  list of PNG paths (written next to the npz): plain RGB tangent-space normal maps, +Y = up in the image
HD2 stores X/Y in R/G (the green channel already points up in the image), a height map in A and other data in B, so Z is rebuilt from X/Y.
"""
import io, os
import numpy as np
from PIL import Image


def normal_map(j, b, material_index, out_png):
    """Save the material's normal map as a plain RGB normal map; returns the path, or None when the material has none."""
    m = j["materials"][material_index]
    nt = m.get("normalTexture")
    if not nt or nt.get("texCoord", 0) != 0: return None
    im = j["images"][j["textures"][nt["index"]]["source"]]
    bv = j["bufferViews"][im["bufferView"]]
    a = np.asarray(Image.open(io.BytesIO(b[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]])).convert("RGBA")).astype(np.float64)
    x = a[..., 0] / 255.0 * 2 - 1; y = a[..., 1] / 255.0 * 2 - 1
    l = np.sqrt(x * x + y * y); s = np.where(l > 0.999, 0.999 / np.maximum(l, 1e-9), 1.0)
    x, y = x * s, y * s
    z = np.sqrt(np.maximum(0.0, 1 - x * x - y * y))
    rgb = np.stack([x, y, z], -1) * 0.5 + 0.5
    Image.fromarray(np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8)).save(out_png)
    return out_png


def write(out_prefix, uv_corners, slots, maps):
    np.savez_compressed(out_prefix + "_detail.npz", uv=np.asarray(uv_corners, np.float32), slot=np.asarray(slots, np.int16), maps=np.array(maps))
    print("detail:", len(slots), "triangles,", len(maps), "normal maps ->", out_prefix + "_detail.npz")


class Maps:
    """Collects one normal map per (glb, material), named <out_prefix>_detail<k>.png."""
    def __init__(self, out_prefix): self.prefix, self.paths, self.index = out_prefix, [], {}

    def slot(self, j, b, glb_path, material_index):
        key = (glb_path, material_index)
        if key not in self.index:
            p = normal_map(j, b, material_index, self.prefix + "_detail%d.png" % len(self.paths))
            self.index[key] = -1 if p is None else len(self.paths)
            if p is not None: self.paths.append(p)
        return self.index[key]

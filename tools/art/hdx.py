"""
HDX1 / HDC2 files (the formats Visuals/ModelFiles.cs and Visuals/Cape.cs read), in plain numpy so they can be tested outside Blender.

HDX1 (little endian):
  "HDX1", u32 version (1), u32 flags (1 = skinned), u32 vertex count, u32 triangle count, u32 key count, u32 bone count
  keys:  per key  u8 name length, name (utf-8), 3 x f32
  bones: per bone u8 name length, name (utf-8)
  positions 3 x f32, normals 3 x f32, tangents 4 x f32 (w = bitangent sign), uvs 2 x f32   (each a block over all vertices)
  skinned only: bone indices 4 x u8, weights 4 x f32 (per vertex; normalised, largest first)
  triangles: 3 x u16 per triangle (u32 when there are more than 65535 vertices)
HDC2 (cape grid): "HDC2", i32 cols, i32 rows, cols*rows x 3 f32 positions (row-major, row 0 = shoulders), then cols*rows x 2 f32 uvs.

Everything is in Unity space: y up, the character faces +z, metres, Unity's winding (the triangle's cross product points outward).
Blender (z up, facing -y) maps to it with unity = (-x, z, -y); that map is a reflection, so triangle order and tangent w flip too
(unity_from_blender below does all three).
"""
import struct
import numpy as np


def unity_from_blender(p):
    """Blender position/direction array (..., 3) -> Unity space."""
    p = np.asarray(p, np.float64)
    return np.stack([-p[..., 0], p[..., 2], -p[..., 1]], -1)


def blender_from_unity(p):
    p = np.asarray(p, np.float64)
    return np.stack([-p[..., 0], -p[..., 2], p[..., 1]], -1)


def write_hdx(path, pos, nrm, tan, uv, tris, keys=None, bones=None, bone_idx=None, bone_w=None):
    """pos/nrm (n,3), tan (n,4), uv (n,2), tris (m,3), keys {name: (x,y,z)}, bones [names], bone_idx (n,4) u8, bone_w (n,4) f32."""
    keys = keys or {}
    bones = bones or []
    skinned = bone_idx is not None
    pos, nrm, tan, uv = (np.ascontiguousarray(a, "<f4") for a in (pos, nrm, tan, uv))
    tris = np.asarray(tris)
    n = len(pos)
    assert nrm.shape == (n, 3) and tan.shape == (n, 4) and uv.shape == (n, 2) and tris.ndim == 2 and tris.shape[1] == 3
    assert tris.min() >= 0 and tris.max() < n
    assert len(bones) < 256 and all(len(b.encode()) < 256 for b in bones)
    with open(path, "wb") as f:
        f.write(b"HDX1")
        f.write(struct.pack("<IIIIII", 1, 1 if skinned else 0, n, len(tris), len(keys), len(bones)))
        for name, v in keys.items():
            e = name.encode(); f.write(struct.pack("<B", len(e))); f.write(e); f.write(np.asarray(v, "<f4").tobytes())
        for name in bones:
            e = name.encode(); f.write(struct.pack("<B", len(e))); f.write(e)
        for a in (pos, nrm, tan, uv): f.write(a.tobytes())
        if skinned:
            assert bone_idx.shape == (n, 4) and bone_w.shape == (n, 4) and int(np.max(bone_idx)) < max(len(bones), 1)
            f.write(np.ascontiguousarray(bone_idx, "<u1").tobytes()); f.write(np.ascontiguousarray(bone_w, "<f4").tobytes())
        f.write(np.ascontiguousarray(tris, "<u2" if n <= 65535 else "<u4").tobytes())


def read_hdx(path):
    """The same structure back, as numpy arrays (mirrors ModelFiles.Read)."""
    with open(path, "rb") as f:
        b = f.read()
    assert b[:4] == b"HDX1", "not an HDX1 file"
    ver, flags, n, nt, nk, nb = struct.unpack_from("<IIIIII", b, 4)
    assert ver == 1
    o = 28
    def name():
        nonlocal o
        l = b[o]; s = b[o + 1:o + 1 + l].decode(); o += 1 + l; return s
    keys = {}
    for _ in range(nk):
        k = name(); keys[k] = np.frombuffer(b, "<f4", 3, o).copy(); o += 12
    bones = [name() for _ in range(nb)]
    def block(cols, dt="<f4", size=4):
        nonlocal o
        a = np.frombuffer(b, dt, n * cols, o).reshape(n, cols).copy(); o += n * cols * size; return a
    out = {"keys": keys, "bones": bones, "pos": block(3), "nrm": block(3), "tan": block(4), "uv": block(2), "skinned": bool(flags & 1)}
    if flags & 1:
        out["bone_idx"] = block(4, "<u1", 1); out["bone_w"] = block(4)
    dt, sz = ("<u2", 2) if n <= 65535 else ("<u4", 4)
    out["tris"] = np.frombuffer(b, dt, nt * 3, o).reshape(nt, 3).astype(np.int64); o += nt * 3 * sz
    assert o == len(b), "trailing bytes"
    return out


def write_hdc2(path, grid_pos, grid_uv=None):
    """grid_pos (rows, cols, 3) in Unity bind space, row 0 = shoulders; grid_uv (rows, cols, 2) or None."""
    grid_pos = np.asarray(grid_pos, "<f4")
    rows, cols, _ = grid_pos.shape
    assert rows >= 3 and cols >= 3 and rows % 2 == 1 and cols % 2 == 1, "Cape.cs needs odd rows and cols, at least 3"
    with open(path, "wb") as f:
        f.write(b"HDC2"); f.write(struct.pack("<ii", cols, rows)); f.write(grid_pos.tobytes())
        if grid_uv is not None: f.write(np.asarray(grid_uv, "<f4").tobytes())

import struct, json
import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

def load(path):
    f = open(path, "rb").read()
    off = 12; j = None; binchunk = None
    while off < len(f):
        cl, ct = struct.unpack("<II", f[off:off+8]); data = f[off+8:off+8+cl]
        if ct == 0x4E4F534A: j = json.loads(data)
        elif ct == 0x004E4942: binchunk = data
        off += 8 + cl
    return j, binchunk

def accessor(j, b, idx):
    a = j["accessors"][idx]; bv = j["bufferViews"][a["bufferView"]]
    dt = CT[a["componentType"]]; nc = NC[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0)
    cnt = a["count"]
    isz = np.dtype(dt).itemsize * nc
    if stride and stride != isz:
        arr = np.frombuffer(b, dtype=np.uint8, count=stride * cnt, offset=start).reshape(cnt, stride)[:, :isz].copy().view(dt)
    else:
        arr = np.frombuffer(b, dtype=dt, count=cnt * nc, offset=start)
    return arr.reshape(cnt, nc) if nc > 1 else arr

def node_world(j):
    nodes = j["nodes"]; n = len(nodes)
    parent = [-1] * n
    for i, nd in enumerate(nodes):
        for c in nd.get("children", []): parent[c] = i
    mats = [None] * n
    def local(nd):
        if "matrix" in nd: return np.array(nd["matrix"], dtype=np.float64).reshape(4, 4).T
        t = np.array(nd.get("translation", [0, 0, 0]), dtype=np.float64)
        q = np.array(nd.get("rotation", [0, 0, 0, 1]), dtype=np.float64)
        s = np.array(nd.get("scale", [1, 1, 1]), dtype=np.float64)
        x, y, z, w = q
        R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        M = np.eye(4); M[:3, :3] = R * s; M[:3, 3] = t
        return M
    def world(i):
        if mats[i] is not None: return mats[i]
        m = local(nodes[i])
        mats[i] = (world(parent[i]) @ m) if parent[i] >= 0 else m
        return mats[i]
    return [world(i) for i in range(n)]

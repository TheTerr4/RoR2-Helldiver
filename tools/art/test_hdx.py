"""Round trip of the HDX1 writer/reader and the axis map.  uv run --with numpy --with pytest pytest -q tools/art/test_hdx.py"""
import os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import hdx


def test_round_trip_skinned():
    rng = np.random.default_rng(1)
    n = 7
    pos = rng.normal(size=(n, 3)); nrm = rng.normal(size=(n, 3)); tan = rng.normal(size=(n, 4)); uv = rng.random((n, 2))
    tris = np.array([[0, 1, 2], [2, 3, 4], [4, 5, 6]])
    bi = rng.integers(0, 3, (n, 4)).astype(np.uint8); bw = rng.random((n, 4)).astype(np.float32)
    keys = {"muzzle": (0.1, 0.2, 0.3), "grip": (1, 2, 3)}
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.hdx")
        hdx.write_hdx(p, pos, nrm, tan, uv, tris, keys, ["hand.r", "chest", "head"], bi, bw)
        r = hdx.read_hdx(p)
    assert r["skinned"] and r["bones"] == ["hand.r", "chest", "head"]
    assert np.allclose(r["pos"], pos, atol=1e-6) and np.allclose(r["tan"], tan, atol=1e-6) and np.allclose(r["uv"], uv, atol=1e-6)
    assert (r["tris"] == tris).all() and (r["bone_idx"] == bi).all() and np.allclose(r["bone_w"], bw)
    assert np.allclose(r["keys"]["muzzle"], (0.1, 0.2, 0.3))


def test_round_trip_static_wide():
    n = 70000
    z = np.zeros((n, 3)); t = np.zeros((n, 4)); uv = np.zeros((n, 2))
    tris = np.array([[0, 1, n - 1]])
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "w.hdx")
        hdx.write_hdx(p, z, z, t, uv, tris)
        r = hdx.read_hdx(p)
    assert not r["skinned"] and (r["tris"] == tris).all()


def test_axis_map():
    b = np.array([[1.0, 2.0, 3.0]])
    u = hdx.unity_from_blender(b)
    assert np.allclose(u, [[-1, 3, -2]])
    assert np.allclose(hdx.blender_from_unity(u), b)
    # the map is a reflection: a counter-clockwise triangle's cross product flips relative to the mapped one
    a, c, e = np.eye(3)
    nb = np.cross(c - a, e - a)
    ua, uc, ue = hdx.unity_from_blender(np.array([a, c, e]))
    assert np.allclose(np.cross(uc - ua, ue - ua), -hdx.unity_from_blender(nb))

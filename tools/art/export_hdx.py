"""
Blender mesh objects -> one HDX1 file in Unity space (see hdx.py). Run inside Blender:

    import sys; sys.path.insert(0, r"<repo>/tools/art"); import export_hdx
    export_hdx.export(["Body"], r"<lab>/BepInEx/plugins/HelldiverMod/Model/body.hdx", skeleton=r"<repo>/tools/hd2/commando_skel.json")

- Modifiers are applied (mirror, bevel...) except Armature ones: the armature is put in its rest pose while exporting.
- Vertex groups named after Commando's bones become the skin weights (top 4, normalised, largest first). A group name that is not a
  deform bone of the skeleton is an error, so a typo can't silently bind to the root.
- The UV map used is each object's active render UV map; tangents are Blender's MikkTSpace ones.
- Key points: empties passed in `keys` (name "kp_<key>" -> key "<key>"), at their world position.
- Static meshes (weapons, pack): skeleton=None.
"""
import json
import numpy as np
import bpy
import bmesh

try:
    from . import hdx
except ImportError:
    import hdx


def _deform_bones(skeleton):
    if not skeleton: return None
    bones = json.load(open(skeleton, encoding="utf-8"))["renderers"][0]["bones"]
    return [b["name"] for b in bones if not ("IK" in b["name"] or b["name"].startswith("gun.") or b["name"] == "ROOT")]


def _mesh_arrays(ob, depsgraph):
    """World-space triangulated arrays of one object, per corner (loop)."""
    ev = ob.evaluated_get(depsgraph)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.to_mesh(me); bm.free()
        me.transform(ob.matrix_world)
        if ob.matrix_world.determinant() < 0: me.flip_normals()
        if not me.uv_layers: raise RuntimeError(ob.name + " has no UV map")
        uvl = next((u for u in me.uv_layers if u.active_render), me.uv_layers[0])
        me.calc_tangents(uvmap=uvl.name)
        nL = len(me.loops)
        vi = np.zeros(nL, np.int64); me.loops.foreach_get("vertex_index", vi)
        ln = np.zeros(nL * 3); me.corner_normals.foreach_get("vector", ln); ln = ln.reshape(-1, 3)
        lt = np.zeros(nL * 3); me.loops.foreach_get("tangent", lt); lt = lt.reshape(-1, 3)
        ls = np.zeros(nL); me.loops.foreach_get("bitangent_sign", ls)
        uv = np.zeros(nL * 2); uvl.data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
        co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        ls0 = np.zeros(len(me.polygons), np.int64); me.polygons.foreach_get("loop_start", ls0)
        tri_loops = ls0[:, None] + np.arange(3)[None, :]
        groups = [[(ob.vertex_groups[g.group].name, g.weight) for g in v.groups if g.weight > 1e-4] for v in me.vertices]
        return dict(vi=vi, n=ln, t=lt, s=ls, uv=uv, co=co, tri=tri_loops, groups=groups)
    finally:
        bpy.data.meshes.remove(me)


def export(objects, path, skeleton=None, keys=()):
    obs = [bpy.data.objects[o] if isinstance(o, str) else o for o in objects]
    deform = _deform_bones(skeleton)
    rigs = {m.object for o in obs for m in o.modifiers if m.type == "ARMATURE" and m.object}
    saved = {r: r.data.pose_position for r in rigs}
    for r in rigs: r.data.pose_position = "REST"
    try:
        dg = bpy.context.evaluated_depsgraph_get(); dg.update()
        parts = [_mesh_arrays(o, dg) for o in obs]
    finally:
        for r, p in saved.items(): r.data.pose_position = p

    P, N, T, UV, IDX, TRI = [], [], [], [], [], []
    base = 0
    for a in parts:
        # one output vertex per distinct (vertex, normal, uv, tangent, sign)
        key = np.concatenate([a["vi"][:, None], np.round(a["n"] * 1e4), np.round(a["uv"] * 1e6), np.round(a["t"] * 1e3), a["s"][:, None]], 1).astype(np.int64)
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        inv = inv.ravel()
        tri = inv[a["tri"]] + base
        P.append(a["co"][a["vi"][first]]); N.append(a["n"][first]); UV.append(a["uv"][first])
        T.append(np.concatenate([a["t"][first], a["s"][first, None]], 1))
        TRI.append(tri[:, [0, 2, 1]])                                   # the axis map is a reflection: reverse the winding
        if deform is not None:
            unknown = sorted({g for gs in a["groups"] for g, _ in gs} - set(deform))
            if unknown: raise RuntimeError("vertex groups that are not deform bones of the skeleton: " + ", ".join(unknown))
            for v in a["vi"][first]:
                IDX.append(sorted(((w, g) for g, w in a["groups"][v]), reverse=True)[:4])
        base += len(first)

    pos = hdx.unity_from_blender(np.concatenate(P)); nrm = hdx.unity_from_blender(np.concatenate(N))
    t = np.concatenate(T); tan = np.concatenate([hdx.unity_from_blender(t[:, :3]), -t[:, 3:4]], 1)   # reflection: bitangent sign flips
    uv = np.concatenate(UV); tris = np.concatenate(TRI)
    bones = bone_idx = bone_w = None
    empty = 0
    if deform is not None:
        names = sorted({g for ws in IDX for _, g in ws}, key=deform.index)
        bones = names or [deform[0]]
        bone_idx = np.zeros((len(pos), 4), np.uint8); bone_w = np.zeros((len(pos), 4), np.float32)
        for k, ws in enumerate(IDX):
            s = sum(w for w, _ in ws)
            if s <= 0: empty += 1; bone_w[k, 0] = 1.0; continue
            for j, (w, g) in enumerate(ws): bone_idx[k, j] = bones.index(g); bone_w[k, j] = w / s
    kp = {}
    for e in keys:
        e = bpy.data.objects[e] if isinstance(e, str) else e
        kp[e.name[3:] if e.name.startswith("kp_") else e.name] = hdx.unity_from_blender(np.array(e.matrix_world.translation))
    hdx.write_hdx(path, pos, nrm, tan, uv, tris, kp, bones, bone_idx, bone_w)
    return {"vertices": len(pos), "triangles": len(tris), "bones": bones, "keys": list(kp), "unweighted_vertices": empty,
            "bounds_unity": [pos.min(0).round(3).tolist(), pos.max(0).round(3).tolist()]}

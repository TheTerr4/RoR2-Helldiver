"""
Commando's skeleton as a Blender armature, built from tools/hd2/commando_skel.json (dumped from the game by the lab bridge's
`dumpskel`; git-ignored, never shipped). Run inside Blender (Blender MCP or `blender -P`):

    import sys; sys.path.insert(0, r"<repo>/tools/art"); import rig; rig.build(r"<repo>/tools/hd2/commando_skel.json")

The json holds each bone's bind frame in Commando's mesh space (Unity: y up, facing +z): pos, fwd (local +z) and up (local +y, which
points down the bone, as in Blender). The armature is built in Blender space (z up, facing -y) through hdx.blender_from_unity. That map
is a reflection, so local x is negated to keep each bone frame a proper rotation. The rest pose is Commando's bind pose; the mesh is
modelled on it, and the game supplies Commando's own bind poses at runtime, so only bone names leave Blender.
"""
import json
import numpy as np
import bpy
from mathutils import Matrix, Vector

try:
    from . import hdx
except ImportError:
    import hdx

RIG_NAME = "HelldiverRig"


def load(json_path):
    r = json.load(open(json_path, encoding="utf-8"))["renderers"][0]
    return r["bones"]


def frame(b):
    """Blender-space 4x4 bind frame of one json bone."""
    pos = hdx.blender_from_unity(b["pos"])
    y = hdx.blender_from_unity(b["up"]); z = hdx.blender_from_unity(b["fwd"])
    y /= np.linalg.norm(y); z -= y * np.dot(z, y); z /= np.linalg.norm(z)
    x = np.cross(y, z)
    m = Matrix(((x[0], y[0], z[0], pos[0]), (x[1], y[1], z[1], pos[1]), (x[2], y[2], z[2], pos[2]), (0, 0, 0, 1)))
    return m


def build(json_path, name=RIG_NAME):
    bones = load(json_path)
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old, do_unlink=True)
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    by = {b["name"]: b for b in bones}
    children = {}
    for b in bones: children.setdefault(b["parent"], []).append(b["name"])
    eb = {}
    for b in bones:
        e = arm.edit_bones.new(b["name"])
        m = frame(b)
        # length: to the first child along the bone, else 6 cm (hands, toes, IK helpers)
        head = m.translation
        ln = 0.06
        for c in children.get(b["name"], []):
            d = Vector(hdx.blender_from_unity(by[c]["pos"])) - head
            if d.length > 0.02 and d.normalized().dot(m.col[1].xyz) > 0.9: ln = d.length; break
        e.length = ln
        e.matrix = m
        eb[b["name"]] = e
    for b in bones:
        if b["parent"] in eb: eb[b["name"]].parent = eb[b["parent"]]
    # IK helpers and the gun bones carry no mesh weight
    for n, e in eb.items():
        e.use_deform = not ("IK" in n or n.startswith("gun.") or n == "ROOT")
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.show_in_front = True
    arm.display_type = "STICK"
    return ob


def self_test(json_path, ob=None):
    """Max position / axis error between the armature's rest frames and the json, in metres and radians (expect ~0)."""
    ob = ob or bpy.data.objects[RIG_NAME]
    worst_p = worst_a = 0.0
    for b in load(json_path):
        m = ob.data.bones[b["name"]].matrix_local
        pu = hdx.unity_from_blender(np.array(m.translation))
        yu = hdx.unity_from_blender(np.array(m.col[1].xyz)); zu = hdx.unity_from_blender(np.array(m.col[2].xyz))
        worst_p = max(worst_p, float(np.linalg.norm(pu - b["pos"])))
        worst_a = max(worst_a, float(np.arccos(np.clip(np.dot(yu, b["up"]) / np.linalg.norm(b["up"]), -1, 1))),
                      float(np.arccos(np.clip(np.dot(zu, b["fwd"]) / np.linalg.norm(b["fwd"]), -1, 1))))
    return worst_p, worst_a

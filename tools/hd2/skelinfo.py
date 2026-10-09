import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import glb, numpy as np
j, b = glb.load("model/content/fac_helldivers/cha_avatar/avatar_helldiver.unit.glb")
W = glb.node_world(j)
sk = j["skins"][0]
names = [j["nodes"][i]["name"] for i in sk["joints"]]
print(len(names))
want = ["hips","spine1","spine2","chest","neck","head","l_clavicle","l_shoulder","l_elbow","l_hand","r_shoulder","r_elbow","r_hand","l_thigh","l_knee","l_foot","l_ball","l_toe","r_thigh","r_knee","r_foot"]
for i, nd in enumerate(j["nodes"]):
    if nd.get("name") in want:
        p = W[i][:3, 3]; print(nd["name"], np.round(p, 3))
# which joint names have weight
pr = j["meshes"][0]["primitives"][0]
J = glb.accessor(j, b, pr["attributes"]["JOINTS_0"]); Wt = glb.accessor(j, b, pr["attributes"]["WEIGHTS_0"])
print(J.dtype, Wt.dtype, Wt[:3], J[:3])
cnt = {}
for k in range(J.shape[1]):
    for jj, ww in zip(J[:, k], Wt[:, k]):
        cnt[jj] = cnt.get(jj, 0) + float(ww)
for jj, v in sorted(cnt.items(), key=lambda x: -x[1])[:40]: print(names[jj], round(v, 1))
C = glb.accessor(j, b, pr["attributes"]["COLOR_0"]); print("color", C.dtype, C[:3], C.min(0), C.max(0))

#if LAB
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using BepInEx;
using RoR2;
using UnityEngine;
using UnityEngine.Rendering;

namespace HelldiverMod
{
    /// <summary>
    /// Lab-only art research tools: a line-up of survivor display models (for style reference screenshots) and a dump of their
    /// meshes and materials (shader, keywords, every property value, texture sizes and formats).
    /// </summary>
    public partial class DevBridge
    {
        readonly List<GameObject> lineup = new List<GameObject>();
        GameObject lineupCam;

        static SurvivorDef[] LineupDefs() => SurvivorCatalog.orderedSurvivorDefs.Where(s => s && s.displayPrefab).ToArray();

        /// <summary>lineup [page] [angle] [perPage]: display models of survivors page*perPage.., side by side in front of the player, turned by angle.</summary>
        void Lineup(string arg)
        {
            var a = arg.Split(new[] { ' ' }, System.StringSplitOptions.RemoveEmptyEntries);
            if (a.Length > 0 && a[0] == "off") { ClearLineup(); Say("lineup off"); return; }
            int page = a.Length > 0 ? int.Parse(a[0]) : 0;
            float angle = a.Length > 1 ? float.Parse(a[1], CultureInfo.InvariantCulture) : 0f;
            int per = a.Length > 2 ? int.Parse(a[2]) : 5;
            ClearLineup();
            var defs = LineupDefs();
            var pick = defs.Skip(page * per).Take(per).ToArray();
            var body = LocalBody();
            var fwd = body.inputBank.aimDirection; fwd.y = 0f; fwd.Normalize();
            var right = Vector3.Cross(Vector3.up, fwd);
            const float spacing = 1.9f;
            float width = pick.Length * spacing + 0.6f;
            float dist = Mathf.Max(width * 0.5f / Mathf.Tan(Mathf.Deg2Rad * 30f * 0.5f * 16f / 9f), 2.6f / Mathf.Tan(Mathf.Deg2Rad * 15f));
            var center = body.footPosition + fwd * (dist + 3f);    // the camera stands 3 m in front of the player, so the player is not in the shot
            for (int i = 0; i < pick.Length; i++)
            {
                var pos = center + right * ((i - (pick.Length - 1) * 0.5f) * spacing);
                var go = Instantiate(pick[i].displayPrefab, pos, Quaternion.LookRotation(-fwd) * Quaternion.Euler(0f, angle, 0f));
                go.name = "HD_Lineup_" + pick[i].cachedName;
                ApplyDefaultSkin(go);
                lineup.Add(go);
            }
            // a fixed camera that frames the row at chest height (FOV 30 to keep perspective low)
            lineupCam = new GameObject("HD_LineupCam");
            var cam = lineupCam.AddComponent<Camera>();
            cam.depth = 100; cam.fieldOfView = 30f; cam.nearClipPlane = 0.05f;
            lineupCam.transform.position = center - fwd * dist + Vector3.up * 1.05f;
            lineupCam.transform.LookAt(center + Vector3.up * 1.0f);
            Say("lineup page " + page + " angle " + angle + ": " + string.Join(", ", pick.Select(d => d.cachedName)) + " (of " + defs.Length + ")");
        }

        static ModelSkinController ApplyDefaultSkin(GameObject go)
        {
            var msc = go.GetComponentInChildren<ModelSkinController>();
            if (msc && msc.skins.Length > 0) msc.StartCoroutine(msc.ApplySkinAsync(0, RoR2.ContentManagement.AsyncReferenceHandleUnloadType.OnSceneUnload));
            return msc;
        }

        void ClearLineup()
        {
            foreach (var g in lineup) if (g) Destroy(g);
            lineup.Clear();
            if (lineupCam) Destroy(lineupCam);
        }

        /// <summary>matdump: every survivor's display model (instantiated off to the side for a moment): meshes, bones, bounds and full material properties.</summary>
        System.Collections.IEnumerator MatDump()
        {
            var sb = new StringBuilder();
            var body = LocalBody();
            var basePos = body.footPosition + Vector3.down * 200f;    // out of sight
            foreach (var def in LineupDefs())
            {
                var go = Instantiate(def.displayPrefab, basePos, Quaternion.identity);
                // a display model gets its skin from the character select; apply the default one and wait for its meshes and materials to load
                var msc = ApplyDefaultSkin(go);
                for (float t = 0f; msc && msc.currentSkinIndex != 0 && t < 5f; t += Time.unscaledDeltaTime) yield return null;
                yield return new WaitForSeconds(0.3f);
                var rends = go.GetComponentsInChildren<Renderer>(true).Where(r => !(r is ParticleSystemRenderer) && !(r is TrailRenderer) && !(r is LineRenderer)).ToArray();
                var b = new Bounds(); bool any = false;
                int tris = 0, verts = 0;
                foreach (var r in rends)
                {
                    if (!r.enabled || !r.gameObject.activeInHierarchy) continue;
                    var mesh = r is SkinnedMeshRenderer s ? s.sharedMesh : r.GetComponent<MeshFilter>()?.sharedMesh;
                    if (!mesh) continue;
                    if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
                    verts += mesh.vertexCount;
                    for (int k = 0; k < mesh.subMeshCount; k++) tris += (int)mesh.GetIndexCount(k) / 3;
                }
                var sk = go.GetComponentInChildren<SkinnedMeshRenderer>(true);
                sb.AppendLine("=== " + def.cachedName + " height=" + b.size.y.ToString("F2") + " size=" + b.size.ToString("F2") + " visibleTris=" + tris + " visibleVerts=" + verts + " mainBones=" + (sk ? sk.bones.Length : 0));
                foreach (var r in rends)
                {
                    string path = r.name; for (var q = r.transform.parent; q && q != go.transform; q = q.parent) path = q.name + "/" + path;
                    var mesh = r is SkinnedMeshRenderer s2 ? s2.sharedMesh : r.GetComponent<MeshFilter>()?.sharedMesh;
                    int mt = 0; if (mesh) for (int k = 0; k < mesh.subMeshCount; k++) mt += (int)mesh.GetIndexCount(k) / 3;
                    sb.AppendLine("  R " + r.GetType().Name + " " + path + " on=" + (r.enabled && r.gameObject.activeInHierarchy) + " mesh=" + (mesh ? mesh.name + " v=" + mesh.vertexCount + " t=" + mt + " sub=" + mesh.subMeshCount : "none") + (r is SkinnedMeshRenderer s3 ? " bones=" + s3.bones.Length : ""));
                    foreach (var m in r.sharedMaterials)
                    {
                        if (!m) continue;
                        sb.AppendLine("    M " + m.name + " shader=" + m.shader.name + " keywords=[" + string.Join(" ", m.shaderKeywords) + "] queue=" + m.renderQueue);
                        var sh = m.shader;
                        for (int p = 0; p < sh.GetPropertyCount(); p++)
                        {
                            string n = sh.GetPropertyName(p);
                            var t = sh.GetPropertyType(p);
                            string v;
                            if (t == ShaderPropertyType.Texture)
                            {
                                var tex = m.GetTexture(n);
                                if (!tex) continue;
                                v = tex.name + " " + tex.width + "x" + tex.height + (tex is Texture2D t2 ? " " + t2.format : " " + tex.GetType().Name) + " st=" + m.GetTextureScale(n).ToString("F2") + "/" + m.GetTextureOffset(n).ToString("F2");
                            }
                            else if (t == ShaderPropertyType.Color) v = m.GetColor(n).ToString("F3");
                            else if (t == ShaderPropertyType.Vector) v = m.GetVector(n).ToString("F3");
                            else v = m.GetFloat(n).ToString("0.###", CultureInfo.InvariantCulture);
                            sb.AppendLine("      " + n + " = " + v);
                        }
                    }
                }
                Destroy(go);
                yield return null;
            }
            System.IO.File.WriteAllText(System.IO.Path.Combine(Paths.BepInExRootPath, "matdump.txt"), sb.ToString());
            Say("matdump done (" + LineupDefs().Length + " survivors)");
        }
    }
}
#endif

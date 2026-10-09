using System;
using System.Collections.Generic;
using System.IO;
using RoR2;
using UnityEngine;
using UnityEngine.Rendering;

namespace HelldiverMod
{
    /// <summary>
    /// Coarse cape grid (Model/cape.bin, HDC2, resampled from the HD2 cape by tools/hd2/capegrid.py): cols x rows render points, row 0 at the shoulders.
    /// The cloth simulates every second row and column (sc x sr particles); the render mesh is the full grid, interpolated from the particles.
    /// </summary>
    internal class CapeData
    {
        public int cols, rows;          // render grid
        public int sc, sr, nP;          // simulated grid
        public Vector3[] rest;          // particle rest positions (mesh/bind space)
        public Vector3[] renderRest;
        public Vector2[] uv;            // render points; null = file without UVs
        public float[] t;               // 0 at the shoulders .. 1 at the hem
        public float[] wChest;          // 1 = anchored to the chest bone, 0 = to the pelvis
        public int[] conA, conB; public float[] conL, conK;   // all distance constraints: structural, shear and bend
        public int[] tris;              // render triangles (front side)
        public int nV => cols * rows;

        public static CapeData Load(string path)
        {
            var f = File.ReadAllBytes(path);
            if (f.Length < 12 || f[0] != 'H' || f[1] != 'D' || f[2] != 'C' || f[3] != '2') return null;
            var d = new CapeData { cols = BitConverter.ToInt32(f, 4), rows = BitConverter.ToInt32(f, 8) };
            if (d.cols < 3 || d.rows < 3 || (d.cols & 1) == 0 || (d.rows & 1) == 0) return null;   // odd sizes so every second point is a particle
            d.renderRest = new Vector3[d.nV];
            for (int i = 0, o = 12; i < d.nV; i++, o += 12) d.renderRest[i] = new Vector3(BitConverter.ToSingle(f, o), BitConverter.ToSingle(f, o + 4), BitConverter.ToSingle(f, o + 8));

            int uvAt = 12 + d.nV * 12;
            if (f.Length >= uvAt + d.nV * 8)
            {
                d.uv = new Vector2[d.nV];
                for (int i = 0, o = uvAt; i < d.nV; i++, o += 8) d.uv[i] = new Vector2(BitConverter.ToSingle(f, o), BitConverter.ToSingle(f, o + 4));
            }

            d.sc = (d.cols + 1) / 2; d.sr = (d.rows + 1) / 2; d.nP = d.sc * d.sr;
            d.rest = new Vector3[d.nP]; d.t = new float[d.nP]; d.wChest = new float[d.nP];
            for (int r = 0; r < d.sr; r++)
                for (int c = 0; c < d.sc; c++)
                {
                    int i = r * d.sc + c;
                    d.rest[i] = d.renderRest[(2 * r) * d.cols + 2 * c];
                    d.t[i] = (float)r / (d.sr - 1);
                    d.wChest[i] = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((d.rest[i].y - 0.85f) / 0.45f));
                }

            var a = new List<int>(); var b = new List<int>(); var k = new List<float>();
            void Link(int p, int q, float stiff) { a.Add(p); b.Add(q); k.Add(stiff); }
            for (int r = 0; r < d.sr; r++)
                for (int c = 0; c < d.sc; c++)
                {
                    int i = r * d.sc + c;
                    if (c + 1 < d.sc) Link(i, i + 1, 1f);                                   // across
                    if (r + 1 < d.sr) Link(i, i + d.sc, 1f);                                // down
                    if (c + 1 < d.sc && r + 1 < d.sr) { Link(i, i + d.sc + 1, 0.5f); Link(i + 1, i + d.sc, 0.5f); }   // shear
                    if (c + 2 < d.sc) Link(i, i + 2, 0.15f);                                // bend
                    if (r + 2 < d.sr) Link(i, i + 2 * d.sc, 0.3f);
                }
            d.conA = a.ToArray(); d.conB = b.ToArray(); d.conK = k.ToArray();
            d.conL = new float[d.conA.Length];
            for (int e = 0; e < d.conA.Length; e++) d.conL[e] = Vector3.Distance(d.rest[d.conA[e]], d.rest[d.conB[e]]);

            var tr = new List<int>();
            for (int r = 0; r + 1 < d.rows; r++)
                for (int c = 0; c + 1 < d.cols; c++)
                {
                    int p = r * d.cols + c, q = p + 1, s = p + d.cols, u = s + 1;
                    tr.Add(p); tr.Add(q); tr.Add(s);
                    tr.Add(q); tr.Add(u); tr.Add(s);
                }
            d.tris = tr.ToArray();
            return d;
        }
    }

    /// <summary>
    /// Small cloth cape: a 5 x 7 grid of Verlet particles, top row fixed to the chest bone (hidden under the pack on the back). Every particle is pulled toward its skinned rest position
    /// and kept within a short distance of it, so the cape follows the body closely and only swings a bit; the body's own movement is mostly passed on to the particles (Inert) so it never trails far behind.
    /// Capsules on the pelvis, torso and legs keep it out of the body, including when walking backwards. Rendered as a 9 x 13 double-sided world-space mesh.
    /// Runs after everything else in LateUpdate (the ModelLocator moves the model in its own LateUpdate; reading bones earlier made the cape lag one frame).
    /// The inner loops are written out in floats: Unity's Mono runs Vector3 operators as calls, and this is the mod's busiest per-frame code.
    /// While the body is off screen the cloth sleeps (its last shape moves rigidly with the chest), and snaps back to its rest shape when it is seen again.
    /// </summary>
    [DefaultExecutionOrder(32000)]
    public class HelldiverCape : MonoBehaviour
    {
        // --- tuning (lab bridge: "gripset <name> <value>" also reaches these)
        public static float Gravity = 9.8f, Damping = 0.985f, PullTop = 30f, PullHem = 8f, MaxDistTop = 0.02f, MaxDistHem = 0.30f;   // pull = rate (1/s) toward the rest shape
        public static float Inert = 0.5f;          // share of the body's own movement handed to the cloth each step (1 = rigid, 0 = pure world-space inertia)
        public static float AirDrag = 2.5f, Gust = 1.2f;   // drag on the velocity along the cape normal (1/s); gust = flutter acceleration (m/s^2) at full running speed
        public static float Margin = 0.03f, SubstepHz = 90f, Friction = 0.8f;
        public static int Iterations = 4, MaxSubsteps = 3;
        public static float NormalStrength = 0.7f;
        public static bool HideCape;   // lab

        static CapeData data;
        static bool dataTried;
        static Material material;

        public CharacterModel model;

        Transform chest, pelvis, thighL, thighR, calfL, calfR, footL, footR;
        Matrix4x4 bindChest = Matrix4x4.identity, bindPelvis = Matrix4x4.identity;
        SkinnedMeshRenderer bodySmr;
        bool initialised, found, asleep;
        Matrix4x4 sleepInv;     // the chest's world-to-local matrix when the cloth went to sleep

        // particles (float arrays: position, previous position, anchor this frame and last frame)
        float[] px, py, pz, qx, qy, qz, a0x, a0y, a0z, a1x, a1y, a1z, maxDist;
        // capsules: torso, pelvis, 2 thighs, 2 calves, crotch filler (end points last frame / this frame, sub-step values, radius + margin)
        const int NCol = 7;
        readonly Vector3[] colPrevA = new Vector3[NCol], colPrevB = new Vector3[NCol], colCurA = new Vector3[NCol], colCurB = new Vector3[NCol];
        readonly float[] cr = new float[NCol], cax = new float[NCol], cay = new float[NCol], caz = new float[NCol], cbx = new float[NCol], cby = new float[NCol], cbz = new float[NCol];
        readonly float[] cmx = new float[NCol], cmy = new float[NCol], cmz = new float[NCol], cm2 = new float[NCol];   // bounding sphere of each capsule (centre, squared radius): most particles are far from most capsules
        Vector3 lastChest, velSmooth;

        GameObject go; Mesh mesh; Vector3[] rpos, verts, norms; Vector4[] tang;

        public static bool Available
        {
            get
            {
                if (!dataTried)
                {
                    dataTried = true;
                    try
                    {
                        if (ModelFiles.Exists("cape.bin")) data = CapeData.Load(ModelFiles.PathOf("cape.bin"));
                        if (data != null) Plugin.Log.LogInfo("Helldiver cape: " + data.cols + "x" + data.rows + " render points, " + data.nP + " particles, " + data.conA.Length + " links");
                    }
                    catch (Exception e) { Plugin.Log.LogWarning("Helldiver cape failed to load: " + e.Message); }
                }
                return data != null;
            }
        }

        // cloth texture baked from the HD2 standard cape's maps (tools/hd2/capetex.py): cape_tex.png (alpha = torn hem) + cape_nrm.png; a plain charcoal cloth when they are missing
        static Material GetMaterial()
        {
            if (material) return material;
            var src = HelldiverModel.BodyMaterial;
            if (!src) return null;
            var tex = ModelFiles.Texture("cape_tex.png", ModelFiles.Kind.Cutout);
            bool cutout = tex;
            if (!tex)
            {
                tex = new Texture2D(4, 4, TextureFormat.RGBA32, false) { name = "tex_cape" };
                var px = new Color32[16];
                for (int i = 0; i < px.Length; i++) px[i] = new Color32(29, 29, 32, 255);
                tex.SetPixels32(px); tex.Apply(false, true);
            }
            material = ModelFiles.MakeMaterial(src, "mat_cape", tex, cutout ? ModelFiles.Texture("cape_nrm.png", ModelFiles.Kind.Normal) : null, 0.12f, NormalStrength);
            if (cutout)     // alpha cutout: the torn hem
            {
                if (material.HasProperty("_EnableCutout")) material.SetFloat("_EnableCutout", 1f);
                material.EnableKeyword("CUTOUT");
            }
            return material;
        }

        bool Find()
        {
            if (!model) return false;
            var b = ModelFiles.Find(model.transform, "chest", "pelvis", "thigh.l", "thigh.r", "calf.l", "calf.r", "foot.l", "foot.r");
            chest = b[0]; pelvis = b[1]; thighL = b[2]; thighR = b[3]; calfL = b[4]; calfR = b[5]; footL = b[6]; footR = b[7];
            if (!(chest && pelvis && thighL && thighR && calfL && calfR && footL && footR)) return false;
            bodySmr = ModelFiles.BodyRenderer(model);
            return ModelFiles.BindPose(bodySmr, chest, out bindChest) && ModelFiles.BindPose(bodySmr, pelvis, out bindPelvis);
        }

        void Setup()
        {
            int n = data.nP;
            px = new float[n]; py = new float[n]; pz = new float[n]; qx = new float[n]; qy = new float[n]; qz = new float[n];
            a0x = new float[n]; a0y = new float[n]; a0z = new float[n]; a1x = new float[n]; a1y = new float[n]; a1z = new float[n];
            maxDist = new float[n];
            for (int i = 0; i < n; i++) maxDist[i] = Mathf.Lerp(MaxDistTop, MaxDistHem, data.t[i]);

            // double-sided: the back copy has reversed winding and flipped normals
            int nV = data.nV;
            rpos = new Vector3[nV]; verts = new Vector3[nV * 2]; norms = new Vector3[nV * 2]; tang = new Vector4[nV * 2];
            var uv = new Vector2[nV * 2]; var tris = new int[data.tris.Length * 2];
            for (int r = 0; r < data.rows; r++)
                for (int c = 0; c < data.cols; c++)
                {
                    int i = r * data.cols + c;
                    var u = data.uv != null ? data.uv[i] : new Vector2((float)c / (data.cols - 1), 1f - (float)r / (data.rows - 1));
                    uv[i] = u; uv[nV + i] = u;
                }
            int nt = data.tris.Length;
            for (int i = 0; i < nt; i += 3)
            {
                tris[i] = data.tris[i]; tris[i + 1] = data.tris[i + 1]; tris[i + 2] = data.tris[i + 2];
                tris[nt + i] = data.tris[i] + nV; tris[nt + i + 1] = data.tris[i + 2] + nV; tris[nt + i + 2] = data.tris[i + 1] + nV;
            }
            mesh = new Mesh { name = "HelldiverCape", indexFormat = IndexFormat.UInt16 };
            mesh.MarkDynamic();
            mesh.vertices = verts; mesh.uv = uv; mesh.triangles = tris;
            go = new GameObject("HD_Cape") { layer = model.gameObject.layer };
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = GetMaterial();
            mr.shadowCastingMode = ShadowCastingMode.On;
            mr.receiveShadows = true;
            var visuals = model.GetComponent<HelldiverVisuals>();
            if (visuals) visuals.Track(mr);
        }

        // capsules in world space: torso, pelvis, 2 thighs, 2 calves, crotch filler
        void Colliders(Vector3[] a, Vector3[] b)
        {
            Vector3 cp = chest.position, pp = pelvis.position;
            Vector3 up = (cp - pp).normalized;
            a[0] = pp + up * 0.02f; b[0] = pp + up * 0.30f; cr[0] = 0.19f;                  // torso (stops under the pack plate)
            a[1] = pp - up * 0.03f; b[1] = pp + up * 0.02f; cr[1] = 0.17f;                  // pelvis / butt
            a[2] = thighL.position; b[2] = calfL.position; cr[2] = 0.125f;
            a[3] = thighR.position; b[3] = calfR.position; cr[3] = 0.125f;
            a[4] = calfL.position; b[4] = footL.position + Vector3.up * 0.06f; cr[4] = 0.10f;
            a[5] = calfR.position; b[5] = footR.position + Vector3.up * 0.06f; cr[5] = 0.10f;
            a[6] = Vector3.Lerp(thighL.position, thighR.position, 0.5f); b[6] = a[6] + Vector3.down * 0.15f; cr[6] = 0.11f;   // crotch filler between the thighs
        }

        void OnDisable() { if (go) go.SetActive(false); }
        void OnEnable() { if (go) go.SetActive(true); }
        void OnDestroy() { if (go) Destroy(go); if (mesh) Destroy(mesh); }

        void LateUpdate()
        {
            if (data == null || !model) return;
            if (!found) { found = Find(); if (!found) return; }
            if (go == null) { if (!GetMaterial()) return; Setup(); }

            bool visible = !HideCape && bodySmr && bodySmr.enabled && bodySmr.gameObject.activeInHierarchy;
            if (go.activeSelf != visible) go.SetActive(visible);
            if (!visible || !bodySmr.isVisible)     // hidden, or nobody sees the diver (e.g. another player off screen): skip the cloth
            {
                // The mesh is in world space and can be in view while the body is not: carry the last shape along with the chest,
                // so it never stays hanging where the diver was last seen.
                if (!asleep) { asleep = true; sleepInv = chest.worldToLocalMatrix; }
                var m = chest.localToWorldMatrix * sleepInv;
                go.transform.SetPositionAndRotation(m.GetColumn(3), m.rotation);
                return;
            }
            if (asleep) { asleep = false; initialised = false; go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity); }     // seen again: start from the rest shape

            float dt = Mathf.Clamp(Time.deltaTime, 0f, 0.05f);
            int n = data.nP;
            Array.Copy(a1x, a0x, n); Array.Copy(a1y, a0y, n); Array.Copy(a1z, a0z, n);
            Array.Copy(colCurA, colPrevA, NCol); Array.Copy(colCurB, colPrevB, NCol);
            Matrix4x4 mc = chest.localToWorldMatrix * bindChest, mp = pelvis.localToWorldMatrix * bindPelvis;
            for (int i = 0; i < n; i++)
            {
                var a = Vector3.Lerp(mp.MultiplyPoint3x4(data.rest[i]), mc.MultiplyPoint3x4(data.rest[i]), data.wChest[i]);
                a1x[i] = a.x; a1y[i] = a.y; a1z[i] = a.z;
            }
            Colliders(colCurA, colCurB);
            float jx = a1x[0] - a0x[0], jy = a1y[0] - a0y[0], jz = a1z[0] - a0z[0];
            if (!initialised || jx * jx + jy * jy + jz * jz > 2.25f)      // first frame, teleport or respawn
            {
                for (int i = 0; i < n; i++) { px[i] = qx[i] = a0x[i] = a1x[i]; py[i] = qy[i] = a0y[i] = a1y[i]; pz[i] = qz[i] = a0z[i] = a1z[i]; }
                Array.Copy(colCurA, colPrevA, NCol); Array.Copy(colCurB, colPrevB, NCol);
                lastChest = chest.position; velSmooth = Vector3.zero;
                initialised = true; dt = 0f;
            }

            if (dt > 0f)
            {
                velSmooth = Vector3.Lerp(velSmooth, (chest.position - lastChest) / dt, 1f - Mathf.Exp(-12f * dt));
                int steps = Mathf.Clamp(Mathf.CeilToInt(dt * SubstepHz), 1, MaxSubsteps);
                float h = dt / steps;
                for (int s = 1; s <= steps; s++) Step(h, (float)(s - 1) / steps, (float)s / steps);
            }
            lastChest = chest.position;
            BuildMesh();
        }

        void SetCapsule(int c, Vector3 a, Vector3 b)
        {
            cax[c] = a.x; cay[c] = a.y; caz[c] = a.z; cbx[c] = b.x; cby[c] = b.y; cbz[c] = b.z;
            cmx[c] = (a.x + b.x) * 0.5f; cmy[c] = (a.y + b.y) * 0.5f; cmz[c] = (a.z + b.z) * 0.5f;
            float r = (b - a).magnitude * 0.5f + cr[c] + Margin;
            cm2[c] = r * r;
        }

        bool Near(int c, float x, float y, float z)
        {
            float dx = x - cmx[c], dy = y - cmy[c], dz = z - cmz[c];
            return dx * dx + dy * dy + dz * dz < cm2[c];
        }

        void Step(float h, float s0, float s1)
        {
            int n = data.nP, sc = data.sc;
            for (int c = 0; c < NCol; c++) SetCapsule(c, Vector3.Lerp(colPrevA[c], colCurA[c], s1), Vector3.Lerp(colPrevB[c], colCurB[c], s1));
            Vector3 fwd = model.transform.forward;
            float fx = fwd.x, fy = fwd.y, fz = fwd.z;
            float speedK = Mathf.Clamp01(velSmooth.magnitude / 7f);
            float dragK = 1f - Mathf.Exp(-AirDrag * h);
            float damp = Mathf.Pow(Damping, h * 120f);
            float time = Time.time, hh = h * h, gy = -Gravity * hh;
            float t0 = s0, t1 = s1;

            for (int i = 0; i < n; i++)
            {
                // anchors at the start and end of this sub-step
                float b0x = a0x[i] + (a1x[i] - a0x[i]) * t0, b0y = a0y[i] + (a1y[i] - a0y[i]) * t0, b0z = a0z[i] + (a1z[i] - a0z[i]) * t0;
                float b1x = a0x[i] + (a1x[i] - a0x[i]) * t1, b1y = a0y[i] + (a1y[i] - a0y[i]) * t1, b1z = a0z[i] + (a1z[i] - a0z[i]) * t1;
                if (i < sc) { qx[i] = px[i]; qy[i] = py[i]; qz[i] = pz[i]; px[i] = b1x; py[i] = b1y; pz[i] = b1z; continue; }   // top row is fixed to the chest
                float tt = data.t[i];
                float vx = (px[i] - qx[i]) * damp, vy = (py[i] - qy[i]) * damp, vz = (pz[i] - qz[i]) * damp;
                float along = (vx * fx + vy * fy + vz * fz) * dragK;                  // air resistance on the broad side of the cloth
                vx -= fx * along; vy -= fy * along; vz -= fz * along;
                float gust = Mathf.Sin(time * 7.3f + py[i] * 9f + px[i] * 6f) * Gust * speedK * tt * hh;
                float x = px[i] + (b1x - b0x) * Inert, y = py[i] + (b1y - b0y) * Inert, z = pz[i] + (b1z - b0z) * Inert;   // the body's own movement, passed on to the cloth
                qx[i] = x - vx; qy[i] = y - vy; qz[i] = z - vz;
                x += fx * gust; y += gy + fy * gust; z += fz * gust;
                float pull = 1f - Mathf.Exp(-(PullTop + (PullHem - PullTop) * tt) * h);
                px[i] = x + (b1x - x) * pull; py[i] = y + (b1y - y) * pull; pz[i] = z + (b1z - z) * pull;
            }

            var ca = data.conA; var cb = data.conB; var cl = data.conL; var ck = data.conK;
            for (int it = 0; it < Iterations; it++)
            {
                for (int i = sc; i < n; i++)       // stay within a growing distance of the rest shape
                {
                    float bx = a0x[i] + (a1x[i] - a0x[i]) * t1, by = a0y[i] + (a1y[i] - a0y[i]) * t1, bz = a0z[i] + (a1z[i] - a0z[i]) * t1;
                    float dx = px[i] - bx, dy = py[i] - by, dz = pz[i] - bz, d2 = dx * dx + dy * dy + dz * dz, md = maxDist[i];
                    if (d2 > md * md) { float k = md / Mathf.Sqrt(d2); px[i] = bx + dx * k; py[i] = by + dy * k; pz[i] = bz + dz * k; }
                }
                for (int e = 0; e < ca.Length; e++)
                {
                    int a = ca[e], b = cb[e];
                    float dx = px[b] - px[a], dy = py[b] - py[a], dz = pz[b] - pz[a];
                    float l = Mathf.Sqrt(dx * dx + dy * dy + dz * dz);
                    if (l < 1e-6f) continue;
                    float wa = a < sc ? 0f : 1f, wb = b < sc ? 0f : 1f, w = wa + wb;
                    if (w == 0f) continue;
                    float k = (l - cl[e]) / l * ck[e] / w;
                    dx *= k; dy *= k; dz *= k;
                    px[a] += dx * wa; py[a] += dy * wa; pz[a] += dz * wa;
                    px[b] -= dx * wb; py[b] -= dy * wb; pz[b] -= dz * wb;
                }
                for (int i = sc; i < n; i++)
                    for (int c = 0; c < NCol; c++) if (Near(c, px[i], py[i], pz[i])) Push(i, c, fx, fy, fz);
            }
        }

        // keep a particle out of a capsule; on contact drop the velocity into the surface and damp the sliding part
        void Push(int i, int c, float fx, float fy, float fz)
        {
            float abx = cbx[c] - cax[c], aby = cby[c] - cay[c], abz = cbz[c] - caz[c];
            float len2 = abx * abx + aby * aby + abz * abz;
            float t = len2 > 1e-8f ? ((px[i] - cax[c]) * abx + (py[i] - cay[c]) * aby + (pz[i] - caz[c]) * abz) / len2 : 0f;
            t = t < 0f ? 0f : t > 1f ? 1f : t;
            float ccx = cax[c] + abx * t, ccy = cay[c] + aby * t, ccz = caz[c] + abz * t;
            float dx = px[i] - ccx, dy = py[i] - ccy, dz = pz[i] - ccz, d2 = dx * dx + dy * dy + dz * dz;
            float r = cr[c] + Margin;
            if (d2 >= r * r) return;
            float dl = Mathf.Sqrt(d2), nx, ny, nz;
            if (dl > 1e-5f) { nx = dx / dl; ny = dy / dl; nz = dz / dl; } else { nx = -fx; ny = -fy; nz = -fz; }     // degenerate: push backwards
            float x = ccx + nx * r, y = ccy + ny * r, z = ccz + nz * r;
            float vx = x - qx[i], vy = y - qy[i], vz = z - qz[i];
            float vn = vx * nx + vy * ny + vz * nz;
            float tx = vx - vn * nx, ty = vy - vn * ny, tz = vz - vn * nz;
            float keep = vn > 0f ? vn : 0f;
            qx[i] = x - (tx * Friction + keep * nx); qy[i] = y - (ty * Friction + keep * ny); qz[i] = z - (tz * Friction + keep * nz);
            px[i] = x; py[i] = y; pz[i] = z;
        }

        // render grid = bilinear interpolation of the particle grid, then a last push out of the body capsules so the in-between points never clip either;
        // normals and tangents come straight from the grid (central differences), front and back
        void BuildMesh()
        {
            int cols = data.cols, rows = data.rows, sc = data.sc, sr = data.sr, nV = data.nV;
            for (int c = 0; c < NCol; c++) SetCapsule(c, colCurA[c], colCurB[c]);
            Vector3 back = -model.transform.forward;
            float minX = float.MaxValue, minY = float.MaxValue, minZ = float.MaxValue, maxX = float.MinValue, maxY = float.MinValue, maxZ = float.MinValue;
            for (int R = 0; R < rows; R++)
            {
                int r0 = R >> 1, r1 = Mathf.Min(r0 + 1, sr - 1); float fr = (R & 1) * 0.5f;
                for (int C = 0; C < cols; C++)
                {
                    int c0 = C >> 1, c1 = Mathf.Min(c0 + 1, sc - 1); float fc = (C & 1) * 0.5f;
                    int i00 = r0 * sc + c0, i01 = r0 * sc + c1, i10 = r1 * sc + c0, i11 = r1 * sc + c1;
                    float w00 = (1 - fr) * (1 - fc), w01 = (1 - fr) * fc, w10 = fr * (1 - fc), w11 = fr * fc;
                    float x = px[i00] * w00 + px[i01] * w01 + px[i10] * w10 + px[i11] * w11;
                    float y = py[i00] * w00 + py[i01] * w01 + py[i10] * w10 + py[i11] * w11;
                    float z = pz[i00] * w00 + pz[i01] * w01 + pz[i10] * w10 + pz[i11] * w11;
                    if (R > 0)
                        for (int c = 0; c < NCol; c++)
                        {
                            if (!Near(c, x, y, z)) continue;
                            float abx = cbx[c] - cax[c], aby = cby[c] - cay[c], abz = cbz[c] - caz[c], len2 = abx * abx + aby * aby + abz * abz;
                            float t = len2 > 1e-8f ? ((x - cax[c]) * abx + (y - cay[c]) * aby + (z - caz[c]) * abz) / len2 : 0f;
                            t = t < 0f ? 0f : t > 1f ? 1f : t;
                            float ccx = cax[c] + abx * t, ccy = cay[c] + aby * t, ccz = caz[c] + abz * t;
                            float dx = x - ccx, dy = y - ccy, dz = z - ccz, d2 = dx * dx + dy * dy + dz * dz, r = cr[c] + Margin;
                            if (d2 >= r * r) continue;
                            float dl = Mathf.Sqrt(d2);
                            if (dl > 1e-5f) { x = ccx + dx / dl * r; y = ccy + dy / dl * r; z = ccz + dz / dl * r; }
                            else { x = ccx + back.x * r; y = ccy + back.y * r; z = ccz + back.z * r; }
                        }
                    rpos[R * cols + C] = new Vector3(x, y, z);
                    if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y; if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
                }
            }
            for (int R = 0; R < rows; R++)
            {
                int rUp = R > 0 ? R - 1 : 0, rDn = R < rows - 1 ? R + 1 : R;
                for (int C = 0; C < cols; C++)
                {
                    int i = R * cols + C;
                    Vector3 du = rpos[R * cols + (C < cols - 1 ? C + 1 : C)] - rpos[R * cols + (C > 0 ? C - 1 : 0)];
                    Vector3 dv = rpos[rDn * cols + C] - rpos[rUp * cols + C];
                    Vector3 nrm = Vector3.Cross(du, dv).normalized;      // the front faces' winding (across, then down)
                    Vector3 tu = du.normalized;
                    verts[i] = verts[nV + i] = rpos[i];
                    norms[i] = nrm; norms[nV + i] = -nrm;
                    tang[i] = new Vector4(tu.x, tu.y, tu.z, 1f); tang[nV + i] = new Vector4(tu.x, tu.y, tu.z, -1f);   // the back copy's normal is flipped, so its handedness flips too
                }
            }
            mesh.vertices = verts;
            mesh.normals = norms;
            mesh.tangents = tang;
            mesh.bounds = new Bounds(new Vector3((minX + maxX) * 0.5f, (minY + maxY) * 0.5f, (minZ + maxZ) * 0.5f), new Vector3(maxX - minX, maxY - minY, maxZ - minZ));
        }

#if LAB
        public Renderer LabRenderer => go ? go.GetComponent<MeshRenderer>() : null;
        public SkinnedMeshRenderer LabBody => bodySmr;
        /// <summary>Lab diagnostics: worst stretch of the structural links, hem centre relative to the pelvis, smallest gap of any render point to a body capsule.</summary>
        public string Diagnostics()
        {
            if (rpos == null) return "cape not built";
            float worst = 0f;
            for (int e = 0; e < data.conA.Length; e++)
            {
                if (data.conK[e] < 1f) continue;
                int a = data.conA[e], b = data.conB[e];
                worst = Mathf.Max(worst, new Vector3(px[b] - px[a], py[b] - py[a], pz[b] - pz[a]).magnitude / data.conL[e]);
            }
            int cols = data.cols, rows = data.rows;
            Vector3 hc = Vector3.zero; float minGap = 9f;
            for (int c = 0; c < cols; c++) hc += rpos[(rows - 1) * cols + c];
            hc = hc / cols - pelvis.position;
            for (int i = cols; i < data.nV; i++)
                for (int c = 0; c < NCol; c++)
                {
                    Vector3 ab = colCurB[c] - colCurA[c]; float l2 = ab.sqrMagnitude;
                    float tt = l2 > 1e-8f ? Mathf.Clamp01(Vector3.Dot(rpos[i] - colCurA[c], ab) / l2) : 0f;
                    minGap = Mathf.Min(minGap, Vector3.Distance(rpos[i], colCurA[c] + ab * tt) - cr[c]);
                }
            return "maxStretch=" + worst.ToString("F3") + " hemSide=" + Vector3.Dot(hc, model.transform.right).ToString("F2") + " hemBack=" + (-Vector3.Dot(hc, model.transform.forward)).ToString("F2") + " minGapToBody=" + minGap.ToString("F3") + " asleep=" + asleep;
        }
#endif
    }
}

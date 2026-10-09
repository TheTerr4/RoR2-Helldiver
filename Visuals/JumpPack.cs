using System.Collections.Generic;
using RoR2;
using UnityEngine;
using UnityEngine.Rendering;

namespace HelldiverMod
{
    /// <summary>
    /// The LIFT-850 Jump Pack on the diver's back (Model/jumppack.hdx, tools/hd2: pack.py --detail then optimize.py), shown while the Jump Pack utility is
    /// selected, in the run and on the character select screen, with a flame out of each nozzle while <see cref="States.JumpPackBurst"/> thrusts.
    /// The file is in the body's bind space; it is baked once into the chest bone's space and hung off the chest bone. The cape hangs from underneath it.
    /// </summary>
    public class HelldiverPack : MonoBehaviour
    {
        public CharacterModel model;
        public bool equipped;                       // set by HelldiverVisuals: the Jump Pack is the selected utility

        // shared by every pack: the mesh baked into chest space, the nozzle frames, the material
        static bool loaded;
        static Mesh chestMesh;
        static Material material;
        static Vector3 nozzleL, nozzleR; static Quaternion nozzleRot;

        public static bool Available => ModelFiles.Exists("jumppack.hdx");

        Transform chest, flameL, flameR;
        SkinnedMeshRenderer bodySmr;
        GameObject go;
        bool found;

        static bool Load(SkinnedMeshRenderer body, Transform chest)
        {
            loaded = true;
            var h = ModelFiles.ReadHdx("jumppack.hdx");
            if (h == null || !HelldiverModel.BodyMaterial || !ModelFiles.BindPose(body, chest, out var bind)) return false;
            var m = h.mesh;
            var v = m.vertices; var n = m.normals; var t = m.tangents; var tris = m.triangles;
            var nrmMat = bind.inverse.transpose;
            bool mirrored = bind.determinant < 0f;      // a mirroring bind pose flips the winding and the tangent handedness
            for (int i = 0; i < v.Length; i++)
            {
                v[i] = bind.MultiplyPoint3x4(v[i]);
                n[i] = nrmMat.MultiplyVector(n[i]).normalized;
                var tv = bind.MultiplyVector(t[i]).normalized;
                t[i] = new Vector4(tv.x, tv.y, tv.z, mirrored ? -t[i].w : t[i].w);
            }
            if (mirrored) for (int i = 0; i < tris.Length; i += 3) { int k = tris[i + 1]; tris[i + 1] = tris[i + 2]; tris[i + 2] = k; }
            m.vertices = v; m.normals = n; m.tangents = t; m.triangles = tris;
            m.RecalculateBounds();
            m.name = "HelldiverJumpPack";
            chestMesh = m;
            nozzleL = bind.MultiplyPoint3x4(h.Key("thrusterL"));
            nozzleR = bind.MultiplyPoint3x4(h.Key("thrusterR"));
            nozzleRot = Quaternion.LookRotation(bind.MultiplyVector(h.Key("flameDir")).normalized, Vector3.up);
            material = ModelFiles.MakeMaterial(HelldiverModel.BodyMaterial, "mat_jumppack", ModelFiles.Texture("jumppack_tex.png"), ModelFiles.Texture("jumppack_nrm.png", ModelFiles.Kind.Normal), 0.3f);
            return true;
        }

        bool Find()
        {
            if (!model) return false;
            chest = ModelFiles.Find(model.transform, "chest")[0];
            bodySmr = ModelFiles.BodyRenderer(model);
            return chest && bodySmr;
        }

        Transform Nozzle(string name, Vector3 at)
        {
            var t = new GameObject(name) { layer = go.layer }.transform;
            t.SetParent(go.transform, false);
            t.localPosition = at; t.localRotation = nozzleRot;
            return t;
        }

        void Build()
        {
            go = new GameObject("HD_JumpPack") { layer = model.gameObject.layer };
            go.transform.SetParent(chest, false);
            go.AddComponent<MeshFilter>().sharedMesh = chestMesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = material;
            mr.shadowCastingMode = ShadowCastingMode.On;
            mr.receiveShadows = true;
            var visuals = model.GetComponent<HelldiverVisuals>();
            if (visuals) visuals.Track(mr);
            flameL = Nozzle("HD_ThrusterL", nozzleL);
            flameR = Nozzle("HD_ThrusterR", nozzleR);
        }

        // --- flames: the vanilla dash-jet effect (the one the Commando dodge uses), made continuous and placed at each nozzle exit
        public static float FlameScale = 0.7f, SparkRate = 14f, JetRate = 60f, FlareRate = 10f, GlowIntensity = 6f;
        readonly GameObject[] flames = new GameObject[2];
        readonly Light[] flameLights = new Light[2];
        readonly List<ParticleSystem>[] flameSystems = { new List<ParticleSystem>(), new List<ParticleSystem>() };
        float level;

        /// <summary>The pack is on the diver's back (so the flames have somewhere to come from).</summary>
        public bool Ready => go && go.activeInHierarchy;

        static float RateFor(string name, float level)
        {
            switch (name)
            {
                case "Jet": return JetRate * level;
                case "Flare": return FlareRate * level;
                case "Sparks": return SparkRate * level;
                case "Distortion": return 6f * level;
                default: return 0f;                 // the ring is a one-off pulse
            }
        }

        void MakeFlame(int i)
        {
            var f = Instantiate(Assets.DashJets, i == 0 ? flameL : flameR);
            f.transform.localPosition = Vector3.zero; f.transform.localRotation = Quaternion.identity; f.transform.localScale = Vector3.one * FlameScale;
            foreach (var c in f.GetComponents<MonoBehaviour>())
                if (c is DestroyOnTimer || c is ShakeEmitter || c is LightIntensityCurve) Destroy(c);     // a one-shot puff with a camera shake: ours lasts as long as the thrust
            flameSystems[i].Clear();
            foreach (var ps in f.GetComponentsInChildren<ParticleSystem>(true))
            {
                ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);     // duration can only change while stopped
                var main = ps.main; main.loop = true; main.duration = 1f; main.playOnAwake = false;
                if (ps.name == "Flare") main.startSizeMultiplier *= 0.3f;           // the vanilla flash is a big disc: here only a hot spot at the nozzle
                else if (ps.name == "Distortion") main.startSizeMultiplier *= 0.6f;
                var em = ps.emission; em.SetBursts(new ParticleSystem.Burst[0]);
                flameSystems[i].Add(ps);
            }
            flameLights[i] = f.GetComponent<Light>();
            if (flameLights[i]) flameLights[i].intensity = 0f;
            flames[i] = f;
        }

        /// <summary>Thrust level: 0 = off, 1 = full burst, in between = hover. Called by the Jump Pack state.</summary>
        public void Thrust(float newLevel)
        {
            level = newLevel;
            for (int i = 0; i < 2; i++)
            {
                if (level <= 0f)
                {
                    if (flames[i]) { Destroy(flames[i]); flames[i] = null; flameLights[i] = null; }
                    continue;
                }
                if (!flames[i]) { if (!Assets.DashJets || !flameL) return; MakeFlame(i); }
                foreach (var ps in flameSystems[i])
                {
                    var em = ps.emission; em.rateOverTime = RateFor(ps.name, level);
                    if (!ps.isPlaying && em.rateOverTime.constant > 0f) ps.Play(false);
                }
            }
        }

        void OnDestroy() { if (go) Destroy(go); }
        void OnDisable() { if (go) go.SetActive(false); Thrust(0f); }

        void LateUpdate()
        {
            if (!model) return;
            if (!found) { found = Find(); if (!found) return; }
            if (!go)
            {
                if (!equipped) return;                      // nothing to show yet: build on first use
                if (!loaded && !Load(bodySmr, chest)) { enabled = false; return; }
                if (!chestMesh) { enabled = false; return; }
                Build();
            }
            bool visible = equipped && bodySmr.enabled && bodySmr.gameObject.activeInHierarchy;
            if (go.activeSelf != visible) go.SetActive(visible);
            if (level > 0f && !visible) Thrust(0f);
            for (int i = 0; i < 2; i++)      // the flame light flickers with the thrust
                if (flameLights[i]) flameLights[i].intensity = GlowIntensity * level * (0.7f + 0.6f * Mathf.PerlinNoise(Time.time * 28f, i * 7.3f));
        }
    }
}

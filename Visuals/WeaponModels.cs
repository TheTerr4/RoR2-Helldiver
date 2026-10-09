using RoR2;
using UnityEngine;
using UnityEngine.Rendering;

namespace HelldiverMod
{
    /// <summary>One weapon model (Model/[file].hdx + _tex/_nrm.png), in weapon space: barrel along +Z, up +Y.</summary>
    internal class WeaponModel
    {
        public string file;
        public Vector3 grip;                  // the point the right palm holds
        public Mesh mesh; public Material material;
        public Vector3 muzzle, under;         // key points from the file: barrel exit, foregrip (the left palm)
    }

    /// <summary>
    /// The AR-23 Liberator and SG-225 Breaker models (tools/hd2: weapon.py --detail, then optimize.py). They hang off a free weapon root under the model
    /// that <see cref="HelldiverGrip"/> poses every frame. Indices follow the primary skill variants (<see cref="Survivor.Primaries"/>).
    /// </summary>
    internal static class WeaponModels
    {
        static readonly WeaponModel[] all =
        {
            new WeaponModel { file = "liberator", grip = new Vector3(0f, -0.055f, 0.03f) },
            new WeaponModel { file = "breaker", grip = new Vector3(0f, -0.04f, -0.007f) },
        };
        static bool loaded;

        public static int Count => all.Length;
        public static WeaponModel Get(int index) => index >= 0 && index < all.Length ? all[index] : null;

        static void Load(Material template)
        {
            loaded = true;
            foreach (var w in all)
            {
                var h = ModelFiles.ReadHdx(w.file + ".hdx");
                if (h == null) continue;
                w.mesh = h.mesh; w.muzzle = h.Key("muzzle"); w.under = h.Key("underbarrel");
                w.material = ModelFiles.MakeMaterial(template, "mat_" + w.file, ModelFiles.Texture(w.file + "_tex.png"), ModelFiles.Texture(w.file + "_nrm.png", ModelFiles.Kind.Normal), 0.35f);
            }
        }

        /// <summary>Create the weapon root under the model with one (inactive) child per weapon, null where a model is missing; null when there are none.</summary>
        public static GameObject[] Attach(CharacterModel model, Material template, out Transform root)
        {
            root = null;
            if (!model || !template) return null;
            if (!loaded) Load(template);
            var rootGo = new GameObject("HD_WeaponRoot") { layer = model.gameObject.layer };
            rootGo.transform.SetParent(model.transform, false);
            var objs = new GameObject[all.Length];
            bool any = false;
            for (int i = 0; i < all.Length; i++)
            {
                if (!all[i].mesh) continue;
                var go = new GameObject("HD_" + all[i].file) { layer = rootGo.layer };
                go.transform.SetParent(rootGo.transform, false);
                go.AddComponent<MeshFilter>().sharedMesh = all[i].mesh;
                var mr = go.AddComponent<MeshRenderer>();
                mr.sharedMaterial = all[i].material;
                mr.shadowCastingMode = ShadowCastingMode.On;
                go.SetActive(false);
                objs[i] = go; any = true;
            }
            if (!any) { Object.Destroy(rootGo); return null; }
            root = rootGo.transform;
            return objs;
        }

        /// <summary>Move the muzzle effect transforms to the active weapon's muzzle so tracers and flashes come out of the barrel.</summary>
        public static void PlaceMuzzles(Transform root, Transform muzzleR, Transform muzzleL, int index)
        {
            var w = Get(index);
            if (w == null || !w.mesh || !root) return;
            foreach (var m in new[] { muzzleR, muzzleL })
            {
                if (!m) continue;
                m.SetParent(root, false);
                m.localPosition = w.muzzle; m.localRotation = Quaternion.identity; m.localScale = Vector3.one;
            }
        }
    }
}

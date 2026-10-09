using System;
using RoR2;
using UnityEngine;

namespace HelldiverMod
{
    /// <summary>
    /// The Helldiver body: Model/body.hdx, a mesh fitted offline onto the Commando skeleton and rest pose (tools/hd2: fit.py, paint.py, fixhands.py --flip,
    /// then optimize.py), skinned to Commando's bones by name and drawn with Commando's bind poses. Without the file the survivor keeps the recoloured Commando.
    /// </summary>
    internal static class HelldiverModel
    {
        static Mesh mesh;
        static Material material;
        static bool built;

        public static Material BodyMaterial => material;
        public static Mesh Mesh => mesh;

        /// <summary>Swap the body renderer's mesh and material (again, when the skin system has put Commando's back).</summary>
        public static void Apply(CharacterModel model)
        {
            if (!model || !ModelFiles.Available) return;
            try
            {
                var body = ModelFiles.BodyRenderer(model);
                if (!body || !body.sharedMesh) return;
                if (!built) Build(body);
                if (!mesh) return;

                body.sharedMesh = mesh;
                body.sharedMaterial = material;
                body.updateWhenOffscreen = true;
                var infos = model.baseRendererInfos;
                for (int i = 0; i < infos.Length; i++)
                    if (infos[i].renderer == body) infos[i].defaultMaterial = material;

                foreach (var t in model.GetComponentsInChildren<Transform>(true))
                    if (t.name.StartsWith("GunMesh")) t.gameObject.SetActive(false);       // Commando's pistols: the Helldiver carries its own weapons
            }
            catch (Exception e) { Plugin.Log.LogError("Helldiver model failed: " + e); }
        }

        static void Build(SkinnedMeshRenderer body)
        {
            built = true;
            var h = ModelFiles.ReadHdx("body.hdx");
            if (h == null || h.weights == null) return;

            // the file names its bones; find each among the Commando renderer's bones
            var rbones = body.bones;
            var map = new int[h.bones.Length];
            for (int i = 0; i < map.Length; i++)
            {
                map[i] = Array.FindIndex(rbones, t => t && t.name == h.bones[i]);
                if (map[i] < 0) { Plugin.Log.LogWarning("Helldiver model: bone '" + h.bones[i] + "' missing on the Commando rig, using the root"); map[i] = 0; }
            }
            var w = h.weights;
            for (int i = 0; i < w.Length; i++)
            {
                w[i].boneIndex0 = map[w[i].boneIndex0]; w[i].boneIndex1 = map[w[i].boneIndex1];
                w[i].boneIndex2 = map[w[i].boneIndex2]; w[i].boneIndex3 = map[w[i].boneIndex3];
            }
            h.mesh.boneWeights = w;
            h.mesh.bindposes = body.sharedMesh.bindposes;      // the mesh was fitted to the Commando rest pose
            h.mesh.name = "HelldiverBody";
            mesh = h.mesh;

            material = ModelFiles.MakeMaterial(body.sharedMaterial, "matHelldiverArmor", ModelFiles.Texture("body_tex.png"), ModelFiles.Texture("body_nrm.png", ModelFiles.Kind.Normal), 0.25f);
            if (material.HasProperty("_SpecularStrength")) material.SetFloat("_SpecularStrength", 0.15f);
            if (material.HasProperty("_SpecularExponent")) material.SetFloat("_SpecularExponent", 4f);
        }
    }
}

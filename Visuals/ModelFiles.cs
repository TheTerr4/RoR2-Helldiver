using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using RoR2;
using UnityEngine;
using UnityEngine.Rendering;
using Path = System.IO.Path;

namespace HelldiverMod
{
    /// <summary>
    /// The optional Model folder (the full package only): meshes and textures made offline from the player's own Helldivers 2 install by tools/hd2.
    /// Without it the survivor is a recoloured Commando and every visual below quietly does nothing.
    /// </summary>
    internal static class ModelFiles
    {
        static string dir;
        static bool searched;

        /// <summary>The folder holding body.hdx, or null. Mod managers sometimes flatten or move package folders, so it looks around the plugins folder too.</summary>
        public static string Dir
        {
            get
            {
                if (searched) return dir;
                searched = true;
                foreach (var c in new[] { Path.Combine(Plugin.Dir, "Model"), Plugin.Dir })
                    if (File.Exists(Path.Combine(c, "body.hdx"))) { dir = c; break; }
                if (dir == null)
                {
                    try
                    {
                        var hits = Directory.GetFiles(BepInEx.Paths.PluginPath, "body.hdx", SearchOption.AllDirectories);
                        if (hits.Length > 0) dir = Path.GetDirectoryName(hits[0]);
                    }
                    catch (Exception e) { Plugin.Log.LogWarning("Helldiver model search failed: " + e.Message); }
                }
                Plugin.Log.LogInfo(dir != null ? "Helldiver model files found in " + dir : "Helldiver model files not found: using the recoloured Commando");
                return dir;
            }
        }

        public static bool Available => Dir != null;
        public static string PathOf(string file) => Dir == null ? null : Path.Combine(Dir, file);
        public static bool Exists(string file) => Dir != null && File.Exists(Path.Combine(Dir, file));

        /// <summary>A mesh from an HDX1 file (tools/hd2/optimize.py documents the layout) plus its named key points and bone names.</summary>
        internal class HdxMesh
        {
            public Mesh mesh;
            public string[] bones = new string[0];
            public BoneWeight[] weights;            // skinned meshes only; bone indices refer to bones[]
            public readonly Dictionary<string, Vector3> keys = new Dictionary<string, Vector3>();
            public Vector3 Key(string name) => keys.TryGetValue(name, out var v) ? v : Vector3.zero;
        }

        static readonly Dictionary<string, HdxMesh> meshes = new Dictionary<string, HdxMesh>();

        /// <summary>The mesh of an HDX1 file, read once (callers that change it do so once, on first use).</summary>
        public static HdxMesh ReadHdx(string file)
        {
            if (!meshes.TryGetValue(file, out var h)) meshes[file] = h = Read(file);
            return h;
        }

        static HdxMesh Read(string file)
        {
            var path = PathOf(file);
            if (path == null || !File.Exists(path)) return null;
            try
            {
                using (var r = new BinaryReader(File.OpenRead(path)))
                {
                    if (Encoding.ASCII.GetString(r.ReadBytes(4)) != "HDX1" || r.ReadUInt32() != 1) { Plugin.Log.LogError("Helldiver model: " + file + " is not an HDX1 file"); return null; }
                    bool skinned = (r.ReadUInt32() & 1) != 0;
                    int nV = r.ReadInt32(), nT = r.ReadInt32(), nK = r.ReadInt32(), nB = r.ReadInt32();
                    string Name() => Encoding.UTF8.GetString(r.ReadBytes(r.ReadByte()));
                    Vector3 V3() => new Vector3(r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                    var h = new HdxMesh { bones = new string[nB] };
                    for (int i = 0; i < nK; i++) { var n = Name(); h.keys[n] = V3(); }
                    for (int i = 0; i < nB; i++) h.bones[i] = Name();
                    var pos = new Vector3[nV]; var nrm = new Vector3[nV]; var tan = new Vector4[nV]; var uv = new Vector2[nV];
                    for (int i = 0; i < nV; i++) pos[i] = V3();
                    for (int i = 0; i < nV; i++) nrm[i] = V3();
                    for (int i = 0; i < nV; i++) tan[i] = new Vector4(r.ReadSingle(), r.ReadSingle(), r.ReadSingle(), r.ReadSingle());
                    for (int i = 0; i < nV; i++) uv[i] = new Vector2(r.ReadSingle(), r.ReadSingle());
                    if (skinned)
                    {
                        var idx = r.ReadBytes(nV * 4);
                        h.weights = new BoneWeight[nV];
                        for (int i = 0; i < nV; i++)
                            h.weights[i] = new BoneWeight
                            {
                                boneIndex0 = idx[i * 4], boneIndex1 = idx[i * 4 + 1], boneIndex2 = idx[i * 4 + 2], boneIndex3 = idx[i * 4 + 3],
                                weight0 = r.ReadSingle(), weight1 = r.ReadSingle(), weight2 = r.ReadSingle(), weight3 = r.ReadSingle(),
                            };
                    }
                    var tris = new int[nT * 3];
                    bool wide = nV > 65535;
                    for (int i = 0; i < tris.Length; i++) tris[i] = wide ? (int)r.ReadUInt32() : r.ReadUInt16();
                    var m = new Mesh { name = Path.GetFileNameWithoutExtension(file), indexFormat = wide ? IndexFormat.UInt32 : IndexFormat.UInt16 };
                    m.vertices = pos; m.normals = nrm; m.tangents = tan; m.uv = uv; m.triangles = tris;
                    m.RecalculateBounds();
                    h.mesh = m;
                    Plugin.Log.LogInfo("Helldiver model: " + file + " " + nV + " vertices, " + nT + " triangles");
                    return h;
                }
            }
            catch (Exception e) { Plugin.Log.LogError("Helldiver model: " + file + " failed to load: " + e.Message); return null; }
        }

        static readonly Dictionary<string, Texture2D> textures = new Dictionary<string, Texture2D>();

        public enum Kind { Opaque, Cutout, Normal }

        /// <summary>
        /// A texture from the Model folder, block-compressed for the GPU with mipmaps and its CPU copy released: opaque colour maps become DXT1
        /// (an eighth of plain RGBA), cutouts DXT5 (a quarter). Normal maps are stored as ordinary RGB images and moved to the DXT5nm layout
        /// (X in alpha, Y in green), which the game's shaders unpack; they are compressed without dithering, which would only add noise to the lighting.
        /// </summary>
        public static Texture2D Texture(string file, Kind kind = Kind.Opaque)
        {
            if (textures.TryGetValue(file, out var cached)) return cached;
            var path = PathOf(file);
            Texture2D t = null;
            if (path != null && File.Exists(path))
            {
                bool normal = kind == Kind.Normal;
                t = new Texture2D(2, 2, TextureFormat.RGBA32, true, normal);
                t.LoadImage(File.ReadAllBytes(path));       // PNGs always load as 32-bit
                var px = kind == Kind.Cutout ? null : t.GetPixels32();
                if (normal)
                {
                    for (int i = 0; i < px.Length; i++) { var c = px[i]; px[i] = new Color32(255, c.g, c.g, c.r); }
                    t.SetPixels32(px);
                }
                else if (kind == Kind.Opaque)               // no alpha: a 24-bit copy compresses to DXT1
                {
                    var rgb = new Texture2D(t.width, t.height, TextureFormat.RGB24, true);
                    rgb.SetPixels32(px);
                    UnityEngine.Object.Destroy(t);
                    t = rgb;
                }
                t.name = Path.GetFileNameWithoutExtension(file); t.wrapMode = TextureWrapMode.Clamp; t.filterMode = FilterMode.Trilinear;
                if (px != null) t.Apply(true);
                t.Compress(!normal);
                t.Apply(false, true);
            }
            return textures[file] = t;
        }

        /// <summary>
        /// Read every model file and compress every texture now, while the game is loading, instead of on the character select screen
        /// (decoding and compressing about 30 MB of images takes most of a second).
        /// </summary>
        public static void Preload()
        {
            if (!Available) return;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            foreach (var m in new[] { "body", "liberator", "breaker", "jumppack" })
            {
                ReadHdx(m + ".hdx");
                Texture(m + "_tex.png");
                Texture(m + "_nrm.png", Kind.Normal);
            }
            if (Settings.Cape.Value) { Texture("cape_tex.png", Kind.Cutout); Texture("cape_nrm.png", Kind.Normal); }
            Plugin.Log.LogInfo("Helldiver model files loaded in " + sw.ElapsedMilliseconds + " ms");
        }

        /// <summary>A copy of the body's (Hopoo deferred standard) material with our own colour map and, when given, normal map.</summary>
        public static Material MakeMaterial(Material template, string name, Texture2D colour, Texture2D normal, float smoothness, float normalStrength = 1f)
        {
            var m = new Material(template) { name = name };
            m.SetTexture("_MainTex", colour);
            m.SetColor("_Color", Color.white);
            if (m.HasProperty("_EmPower")) m.SetFloat("_EmPower", 0f);
            if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", smoothness);
            if (normal && m.HasProperty("_NormalTex")) m.SetTexture("_NormalTex", normal);
            if (m.HasProperty("_NormalStrength")) m.SetFloat("_NormalStrength", normal ? normalStrength : 0f);
            return m;
        }

        /// <summary>The CharacterModel's main skinned renderer (the body; Commando's has 50+ bones, its other renderers none).</summary>
        public static SkinnedMeshRenderer BodyRenderer(CharacterModel model)
        {
            if (!model) return null;
            foreach (var r in model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                if (r.bones != null && r.bones.Length > 40) return r;
            return null;
        }

        /// <summary>Bind pose of one of the body renderer's bones (mesh space -> bone space), or false when it isn't one of its bones.</summary>
        public static bool BindPose(SkinnedMeshRenderer body, Transform bone, out Matrix4x4 bind)
        {
            bind = Matrix4x4.identity;
            if (!body || !body.sharedMesh || !bone) return false;
            int i = Array.IndexOf(body.bones, bone);
            var bp = body.sharedMesh.bindposes;
            if (i < 0 || i >= bp.Length) return false;
            bind = bp[i];
            return true;
        }

        /// <summary>Transforms under root with the given names (null where missing), in the order asked.</summary>
        public static Transform[] Find(Transform root, params string[] names)
        {
            var found = new Transform[names.Length];
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                int i = Array.IndexOf(names, t.name);
                if (i >= 0 && !found[i]) found[i] = t;
            }
            return found;
        }
    }
}

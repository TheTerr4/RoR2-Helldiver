using System;
using System.Collections.Generic;
using System.IO;
using R2API;
using RoR2.Projectile;
using UnityEngine;
using UnityEngine.AddressableAssets;

namespace HelldiverMod
{
    /// <summary>Vanilla assets (addressables) the Helldiver reuses, its own projectiles, and the skill icons embedded in the dll (Assets/*.png).</summary>
    internal static class Assets
    {
        static readonly Dictionary<string, Sprite> sprites = new Dictionary<string, Sprite>();

        public static T Load<T>(string key) where T : UnityEngine.Object
        {
            try { return Addressables.LoadAssetAsync<T>(key).WaitForCompletion(); }
            catch (Exception e) { Plugin.Log.LogWarning("asset '" + key + "' failed: " + e.Message); return null; }
        }

        // effects
        public static GameObject MuzzleFlash, Tracer, HitSpark, ShotgunTracer, ShotgunHitSpark, StrikeIndicator, DashJets, ThrowArc;
        // supply drops (vanilla prefabs, reused as they are)
        public static GameObject EmsDrop, ResupplyDrop;
        // grenades (cloned vanilla projectiles)
        public static GameObject HeGrenade, StunGrenade;

        public static void LoadVanilla()
        {
            MuzzleFlash = Load<GameObject>("RoR2/Base/Common/VFX/Muzzleflash1.prefab");
            Tracer = Load<GameObject>("RoR2/Base/Commando/TracerCommandoDefault.prefab");
            HitSpark = Load<GameObject>("RoR2/Base/Commando/HitsparkCommando.prefab");
            ShotgunTracer = Load<GameObject>("RoR2/Base/Commando/TracerCommandoShotgun.prefab");
            ShotgunHitSpark = Load<GameObject>("RoR2/Base/Commando/HitsparkCommandoShotgun.prefab");
            StrikeIndicator = Load<GameObject>("RoR2/Base/Treebot/TreebotMortarAreaIndicator.prefab");
            DashJets = Load<GameObject>("RoR2/Base/Commando/CommandoDashJets.prefab");
            ThrowArc = Load<GameObject>("RoR2/Base/Common/VFX/BasicThrowableVisualizer.prefab");
            EmsDrop = Load<GameObject>("RoR2/Base/Captain/CaptainSupplyDrop, Shocking.prefab");
            ResupplyDrop = Load<GameObject>("RoR2/Base/Captain/CaptainSupplyDrop, Healing.prefab");

            const string grenade = "RoR2/Base/Commando/CommandoGrenadeProjectile.prefab";
            HeGrenade = CloneProjectile(grenade, "HelldiverHeGrenade", Settings.HeRadius.Value, 10f);
            StunGrenade = CloneProjectile(grenade, "HelldiverStunGrenade", Settings.StunRadius.Value, 10f);
        }

        /// <summary>A networked copy of a vanilla exploding projectile with its own blast radius and fuse.</summary>
        public static GameObject CloneProjectile(string key, string name, float radius, float fuse)
        {
            var p = PrefabAPI.InstantiateClone(Load<GameObject>(key), name, true);
            var ie = p.GetComponent<ProjectileImpactExplosion>();
            ie.blastRadius = radius;
            ie.lifetime = fuse;
            ContentAddition.AddProjectile(p);
            return p;
        }

        static byte[] Embedded(string name)
        {
            using (var st = typeof(Assets).Assembly.GetManifestResourceStream("HelldiverMod.Assets." + name + ".png"))
            {
                if (st == null) return null;
                var buf = new byte[st.Length];
                int read = 0;
                while (read < buf.Length) { int n = st.Read(buf, read, buf.Length - read); if (n <= 0) break; read += n; }
                return buf;
            }
        }

        /// <summary>An icon embedded in the dll (falls back to Assets/[name].png next to it).</summary>
        public static Texture2D Icon(string name)
        {
            var bytes = Embedded(name);
            if (bytes == null)
            {
                var path = Path.Combine(Plugin.Dir, "Assets", name + ".png");
                if (File.Exists(path)) bytes = File.ReadAllBytes(path);
            }
            if (bytes == null) { Plugin.Log.LogWarning("missing icon " + name); return null; }
            var t = new Texture2D(2, 2, TextureFormat.RGBA32, false) { filterMode = FilterMode.Bilinear, name = "hd_" + name };
            t.LoadImage(bytes, true);
            return t;
        }

        public static Sprite Sprite(string name)
        {
            if (sprites.TryGetValue(name, out var s)) return s;
            var t = Icon(name);
            if (!t) return null;
            s = UnityEngine.Sprite.Create(t, new Rect(0, 0, t.width, t.height), new Vector2(0.5f, 0.5f), 100f, 0, SpriteMeshType.FullRect);
            s.name = "hd_" + name;
            return sprites[name] = s;
        }
    }
}

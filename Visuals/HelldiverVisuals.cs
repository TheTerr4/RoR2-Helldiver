using System.Collections;
using System.Collections.Generic;
using RoR2;
using RoR2.Skills;
using RoR2.SurvivorMannequins;
using UnityEngine;
using UnityEngine.Rendering;

namespace HelldiverMod
{
    /// <summary>
    /// Sits on the Helldiver's model (in a run and on the character select screen) and dresses it: the Helldiver body over Commando's, the weapon of the
    /// selected primary, the cape, and the Jump Pack while that utility is selected. Without the Model folder it only recolours the Commando.
    /// </summary>
    public class HelldiverVisuals : MonoBehaviour
    {
        public static readonly Color Tint = new Color(0.58f, 0.64f, 0.56f, 1f);     // recolour of the Commando when there is no Helldiver model
        static readonly Dictionary<Material, Material> tinted = new Dictionary<Material, Material>();

        CharacterModel model;
        SkinnedMeshRenderer bodySmr;
        bool applied;
        GameObject[] weapons;
        Transform weaponRoot, muzzleR, muzzleL;
        HelldiverGrip grip;
        HelldiverPack pack;
        int shownWeapon = -1;
        readonly List<Renderer> extras = new List<Renderer>();

        /// <summary>
        /// Hand one of our own renderers (weapon, pack, cape) to the CharacterModel, which then treats it like the body: camera-proximity fade, cloaking,
        /// hit flash and elite / buff overlays. The skin system replaces the model's renderer list when it applies a skin, so it is checked every frame.
        /// </summary>
        public void Track(Renderer r) { if (r && !extras.Contains(r)) extras.Add(r); }

        void KeepTracked()
        {
            var infos = model.baseRendererInfos;
            int missing = 0;
            foreach (var r in extras) if (r && IndexOf(infos, r) < 0) missing++;
            if (missing == 0) return;
            var list = new List<CharacterModel.RendererInfo>(infos);
            foreach (var r in extras)
                if (r && IndexOf(infos, r) < 0)
                    list.Add(new CharacterModel.RendererInfo { renderer = r, defaultMaterial = r.sharedMaterial, defaultShadowCastingMode = ShadowCastingMode.On, ignoreOverlays = false, hideOnDeath = false });
            model.baseRendererInfos = list.ToArray();
        }

        static int IndexOf(CharacterModel.RendererInfo[] infos, Renderer r)
        {
            for (int i = 0; i < infos.Length; i++) if (infos[i].renderer == r) return i;
            return -1;
        }

        // The skin system puts Commando's mesh back whenever the loadout, skin or model changes (all the time on the character select screen):
        // check every frame, after it ran and before rendering, so the Commando never shows for even one frame.
        void LateUpdate()
        {
            if (!ModelFiles.Available) return;
            if (!model) { model = GetComponentInChildren<CharacterModel>(); if (!model) return; }
            if (!bodySmr) { bodySmr = ModelFiles.BodyRenderer(model); if (!bodySmr) return; }
            var m = HelldiverModel.Mesh;
            if (!m && applied) return;     // the model file could not be read: keep the recoloured Commando
            if (bodySmr.sharedMesh && (bodySmr.sharedMesh != m || bodySmr.sharedMaterial != HelldiverModel.BodyMaterial))
            {
                applied = true;
                HelldiverModel.Apply(model);
            }
            if (extras.Count > 0) KeepTracked();
        }

        // the weapon of the selected primary, and the pack while the Jump Pack is the selected utility
        void Update()
        {
            if (!model) return;
            var body = model.body;
            var sl = body ? body.skillLocator : null;
            if (pack) pack.equipped = Selected(sl, Survivor.UtilitySlot) == Survivor.JumpPack;
            if (weapons == null) return;
            int want = System.Array.IndexOf(Survivor.Primaries, Selected(sl, Survivor.PrimarySlot));
            if (want < 0) want = 0;
            if (want == shownWeapon) return;
            shownWeapon = want;
            for (int i = 0; i < weapons.Length; i++) if (weapons[i]) weapons[i].SetActive(i == want);
            WeaponModels.PlaceMuzzles(weaponRoot, muzzleR, muzzleL, want);
            if (grip) grip.index = want;
        }

        static BodyIndex bodyIndex = BodyIndex.None;
        bool loadoutDirty = true;
        NetworkUser loadoutUser;
        Loadout userLoadout;

        void OnEnable() { NetworkUser.onLoadoutChangedGlobal += OnLoadoutChanged; loadoutDirty = true; }
        void OnDisable() { NetworkUser.onLoadoutChangedGlobal -= OnLoadoutChanged; }
        void OnLoadoutChanged(NetworkUser user) { if (user == loadoutUser) loadoutDirty = true; }

        // in a run the body's skill; on the character select screen (a display model: no body, no skills) the variant picked by the player it stands for
        SkillDef Selected(SkillLocator sl, int slot)
        {
            if (sl)
            {
                var gs = slot == Survivor.PrimarySlot ? sl.primary : sl.utility;
                return gs ? gs.skillDef : null;
            }
            if (!Survivor.Body) return null;
            if (bodyIndex == BodyIndex.None) bodyIndex = BodyCatalog.FindBodyIndex(Survivor.Body);
            var loadout = DisplayLoadout();
            if (bodyIndex == BodyIndex.None || loadout == null) return null;
            var variants = Survivor.Families[slot].variants;
            uint v = loadout.bodyLoadoutManager.GetSkillVariant(bodyIndex, slot);
            return v < variants.Length ? variants[v].skillDef : null;
        }

        // In a lobby every player's Helldiver is a display model of its own, in that player's mannequin slot: read that player's loadout
        // (copied only when it changes), not the local profile's. The local profile is the fallback for a display without a player.
        Loadout DisplayLoadout()
        {
            var slot = GetComponentInParent<SurvivorMannequinSlotController>();      // looked up each time: the lobby swaps models between slots
            var user = slot ? slot.networkUser : null;
            if (user)
            {
                if (user != loadoutUser) { loadoutUser = user; loadoutDirty = true; }
                if (userLoadout == null) userLoadout = new Loadout();
                if (loadoutDirty) { loadoutDirty = false; user.networkLoadout.CopyLoadout(userLoadout); }
                return userLoadout;
            }
            var lu = LocalUserManager.GetFirstLocalUser();
            return lu != null && lu.userProfile != null ? lu.userProfile.loadout : null;
        }

        IEnumerator Start()
        {
            yield return null;          // the skin system applies its materials in the first frames
            yield return null;
            if (!model) model = GetComponentInChildren<CharacterModel>();
            if (!model || model.baseRendererInfos == null) yield break;
            var infos = model.baseRendererInfos;
            for (int i = 0; i < infos.Length; i++)
            {
                var mat = infos[i].defaultMaterial;
                if (!mat) continue;
                if (!tinted.TryGetValue(mat, out var t))
                {
                    t = new Material(mat) { name = mat.name + "_hd" };
                    if (t.HasProperty("_Color")) t.SetColor("_Color", mat.GetColor("_Color") * Tint);
                    tinted[mat] = t;
                }
                infos[i].defaultMaterial = t;
                if (infos[i].renderer) infos[i].renderer.sharedMaterial = t;
            }
            HelldiverModel.Apply(model);
            var bodyMat = HelldiverModel.BodyMaterial;
            if (!bodyMat) yield break;

            weapons = WeaponModels.Attach(model, bodyMat, out weaponRoot);
            if (weapons != null) foreach (var w in weapons) if (w) Track(w.GetComponent<Renderer>());
            var muzzles = ModelFiles.Find(model.transform, "MuzzleRight", "MuzzleLeft");
            muzzleR = muzzles[0]; muzzleL = muzzles[1];
            if (weaponRoot)
            {
                grip = model.gameObject.AddComponent<HelldiverGrip>();
                grip.model = model; grip.root = weaponRoot;
            }
            if (Settings.Cape.Value && HelldiverCape.Available)
                model.gameObject.AddComponent<HelldiverCape>().model = model;
            if (HelldiverPack.Available)
            {
                pack = model.gameObject.AddComponent<HelldiverPack>();
                pack.model = model;
            }
        }

#if LAB
        /// <summary>Lab diagnostics: whose loadout a display model follows and what it shows.</summary>
        public string Diagnostics() => name + " body=" + (model && model.body ? model.body.name : "none (display)") + " user=" + (loadoutUser ? loadoutUser.userName : "-")
            + " slot=" + (transform.parent ? transform.parent.name : "-")
            + " weapon=" + shownWeapon + " pack=" + (pack ? pack.equipped.ToString() : "-");
#endif
    }
}

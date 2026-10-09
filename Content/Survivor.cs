using System;
using System.Reflection;
using EntityStates;
using HelldiverMod.States;
using R2API;
using RoR2;
using RoR2.Skills;
using UnityEngine;

namespace HelldiverMod
{
    /// <summary>The Helldiver survivor: a clone of the Commando body with its own stats, skills, passive and character select display.</summary>
    internal static class Survivor
    {
        public static GameObject Body, Display;
        public const int PrimarySlot = 0, SecondarySlot = 1, UtilitySlot = 2, SpecialSlot = 3;    // order of the body's GenericSkill components
        public static readonly SkillFamily[] Families = new SkillFamily[4];
        public static SkillDef[] Primaries;           // in WeaponModels order
        public static SkillDef JumpPack;
        public static readonly Color Yellow = new Color(0.96f, 0.77f, 0.1f);

        static SkillDef Skill(string id, Type state, string machine, float cooldown, string icon, InterruptPriority priority,
            int maxStock = 1, int stockToConsume = 1, bool mustKeyPress = true, bool combat = true, bool cancelSprint = true)
        {
            var sd = ScriptableObject.CreateInstance<SkillDef>();
            ((ScriptableObject)sd).name = "Helldiver" + id;
            sd.skillName = "Helldiver" + id;
            sd.skillNameToken = "HELLDIVER_" + id.ToUpperInvariant() + "_NAME";
            sd.skillDescriptionToken = "HELLDIVER_" + id.ToUpperInvariant() + "_DESC";
            sd.icon = Assets.Sprite(icon);
            sd.activationState = new SerializableEntityStateType(state);
            sd.activationStateMachineName = machine;
            sd.baseMaxStock = maxStock;
            sd.baseRechargeInterval = cooldown;
            sd.rechargeStock = 1;
            sd.requiredStock = 1;
            sd.stockToConsume = stockToConsume;
            sd.interruptPriority = priority;
            sd.mustKeyPress = mustKeyPress;
            sd.isCombatSkill = combat;
            sd.cancelSprintingOnActivation = cancelSprint;
            sd.canceledFromSprinting = false;
            sd.fullRestockOnAssign = true;
            ContentAddition.AddSkillDef(sd);
            ContentAddition.AddEntityState(state, out _);
            return sd;
        }

        static void Family(int slot, GenericSkill gs, string name, params SkillDef[] defs)
        {
            var fam = ScriptableObject.CreateInstance<SkillFamily>();
            ((ScriptableObject)fam).name = "Helldiver" + name + "Family";
            fam.variants = new SkillFamily.Variant[defs.Length];
            for (int i = 0; i < defs.Length; i++)
                fam.variants[i] = new SkillFamily.Variant { skillDef = defs[i], unlockableDef = null, viewableNode = new ViewablesCatalog.Node(defs[i].skillNameToken, false, null) };
            ContentAddition.AddSkillFamily(fam);
            typeof(GenericSkill).GetField("_skillFamily", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(gs, fam);
            gs.skillName = "Helldiver" + name;
            Families[slot] = fam;
        }

        public static void Create()
        {
            Assets.LoadVanilla();
            Stratagems.Create();

            Body = PrefabAPI.InstantiateClone(Assets.Load<GameObject>("RoR2/Base/Commando/CommandoBody.prefab"), "HelldiverBody", true);
            var cb = Body.GetComponent<CharacterBody>();
            cb.baseNameToken = "HELLDIVER_BODY_NAME";
            cb.subtitleNameToken = "HELLDIVER_BODY_SUBTITLE";
            cb.portraitIcon = Assets.Icon("portrait");
            cb.bodyColor = Yellow;
            cb.baseMaxHealth = Settings.BaseHealth.Value; cb.levelMaxHealth = Settings.HealthPerLevel.Value;
            cb.baseRegen = Settings.BaseRegen.Value; cb.levelRegen = Settings.RegenPerLevel.Value;
            cb.baseArmor = Settings.BaseArmor.Value;
            cb.baseDamage = Settings.BaseDamage.Value; cb.levelDamage = Settings.DamagePerLevel.Value;
            cb.baseMoveSpeed = Settings.MoveSpeed.Value;
            cb.baseJumpCount = 1;
            Body.AddComponent<DemocracyProtects>();
            Body.AddComponent<HelldiverAmmo>();
            Body.GetComponentInChildren<CharacterModel>().gameObject.AddComponent<HelldiverVisuals>();

            // skills (variant order matters: player profiles store the selected variant by index)
            var slots = Body.GetComponents<GenericSkill>();
            Primaries = new[]
            {
                Skill("Liberator", typeof(FireLiberator), "Weapon", 0f, "rifle", InterruptPriority.Any, stockToConsume: 0, mustKeyPress: false),
                Skill("Breaker", typeof(FireBreaker), "Weapon", 0f, "shotgun", InterruptPriority.Any, stockToConsume: 0, mustKeyPress: false),
            };
            Family(PrimarySlot, slots[PrimarySlot], "Primary", Primaries);
            Family(SecondarySlot, slots[SecondarySlot], "Secondary",
                Skill("HeGrenade", typeof(ThrowHeGrenade), "Weapon", Settings.HeCooldown.Value, "grenade_he", InterruptPriority.Skill, Settings.HeCharges.Value),
                Skill("StunGrenade", typeof(ThrowStunGrenade), "Weapon", Settings.StunCooldown.Value, "grenade_stun", InterruptPriority.Skill, Settings.StunCharges.Value));
            JumpPack = Skill("JumpPack", typeof(JumpPackBurst), "Body", Settings.JumpPackCooldown.Value, "jump", InterruptPriority.PrioritySkill, combat: false, cancelSprint: false);
            Family(UtilitySlot, slots[UtilitySlot], "Utility",
                Skill("Dive", typeof(HelldiverDive), "Body", Settings.DiveCooldown.Value, "dive", InterruptPriority.PrioritySkill, combat: false, cancelSprint: false),
                JumpPack);
            // stratagems: the stock is spent when the beacon is thrown (stockToConsume 0), so cancelling is free
            var specials = new SkillDef[Stratagems.All.Length];
            for (int i = 0; i < specials.Length; i++)
            {
                var d = Stratagems.All[i];
                specials[i] = Skill(d.id, d.input, "Weapon", d.cooldown.Value, d.icon, InterruptPriority.Skill, stockToConsume: 0);
                ContentAddition.AddEntityState(d.armed, out _);
            }
            Family(SpecialSlot, slots[SpecialSlot], "Stratagem", specials);
            ContentAddition.AddEntityState(typeof(StratagemThrown), out _);
            ContentAddition.AddEntityState(typeof(ReloadLiberator), out _);
            ContentAddition.AddEntityState(typeof(ReloadBreaker), out _);

            Body.GetComponent<SkillLocator>().passiveSkill = new SkillLocator.PassiveSkill
            {
                enabled = true,
                skillNameToken = "HELLDIVER_PASSIVE_NAME",
                skillDescriptionToken = "HELLDIVER_PASSIVE_DESC",
                keywordToken = "",
                icon = Assets.Sprite("passive_democracy"),
            };
            ContentAddition.AddBody(Body);

            // character select
            Display = PrefabAPI.InstantiateClone(Assets.Load<GameObject>("RoR2/Base/Commando/CommandoDisplay.prefab"), "HelldiverDisplay", false);
            Display.GetComponentInChildren<CharacterModel>().gameObject.AddComponent<HelldiverVisuals>();

            var sd = ScriptableObject.CreateInstance<SurvivorDef>();
            sd.cachedName = "Helldiver";
            sd.bodyPrefab = Body;
            sd.displayPrefab = Display;
            sd.primaryColor = Yellow;
            sd.displayNameToken = "HELLDIVER_BODY_NAME";
            sd.descriptionToken = "HELLDIVER_DESCRIPTION";
            sd.outroFlavorToken = "HELLDIVER_OUTRO";
            sd.mainEndingEscapeFailureFlavorToken = "HELLDIVER_FAIL";
            sd.desiredSortPosition = 100f;
            ContentAddition.AddSurvivorDef(sd);

            Tokens.Add();
        }
    }
}

using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using BepInEx.Configuration;

namespace HelldiverMod
{
    /// <summary>
    /// Everything players can tune, bound to BepInEx/config/terr4.helldiver.cfg (written with the defaults on the first launch).
    /// Damage values are percentages of the Helldiver's damage stat, as in the skill descriptions (70 = 70%). Sections are numbered so the file
    /// reads in loadout order. Entries marked "Restart" are read once at startup (body stats, skill definitions, projectile prefabs); the rest are read on use.
    /// </summary>
    internal static class Settings
    {
        // 1. Character
        public static ConfigEntry<float> BaseHealth, HealthPerLevel, BaseRegen, RegenPerLevel, BaseArmor, BaseDamage, DamagePerLevel, MoveSpeed;
        // 2. Passive
        public static ConfigEntry<float> PassiveChance, PassiveCooldown, PassiveHeal, PassiveInvulnerability;
        // 3-4. Primaries
        public static ConfigEntry<float> LiberatorDamage, LiberatorFireRate, LiberatorReload, LiberatorAutoReload;
        public static ConfigEntry<int> LiberatorMagazine;
        public static ConfigEntry<float> BreakerDamage, BreakerFireRate, BreakerReload, BreakerAutoReload;
        public static ConfigEntry<int> BreakerMagazine, BreakerPellets;
        // 5-6. Secondaries
        public static ConfigEntry<float> HeDamage, HeRadius, HeCooldown, StunDamage, StunRadius, StunCooldown;
        public static ConfigEntry<int> HeCharges, StunCharges;
        // 7-8. Utilities
        public static ConfigEntry<float> DiveCooldown, JumpPackCooldown, JumpPackHover, JumpPackLift, JumpPackForward;
        // 9-14. Stratagems
        public static ConfigEntry<float> StrikeDamage, StrikeRadius, StrikeDelay, StrikeCooldown;
        public static ConfigEntry<float> EagleDamage, EagleRadius, EagleCooldown;
        public static ConfigEntry<float> BombDamage, BombRadius, BombDelay, BombCooldown;
        public static ConfigEntry<float> EmsDamage, EmsCooldown, ResupplyDamage, ResupplyCooldown;
        public static ConfigEntry<float> CodeTime, BeaconDelay, ThrowRange;
        // 15. Visuals
        public static ConfigEntry<bool> Cape, AmmoCounter, AmmoOnSkillIcon;

        const string Restart = " Restart the game after changing it.";
        const string Mp = " In multiplayer every player should use the same values.";

        static ConfigEntry<float> F(ConfigFile c, string section, string key, float value, string desc, float min, float max) =>
            c.Bind(section, key, value, new ConfigDescription(desc, new AcceptableValueRange<float>(min, max)));
        static ConfigEntry<int> I(ConfigFile c, string section, string key, int value, string desc, int min, int max) =>
            c.Bind(section, key, value, new ConfigDescription(desc, new AcceptableValueRange<int>(min, max)));

        public static void Bind(ConfigFile c)
        {
            const string ch = "01. Character";
            BaseHealth = F(c, ch, "Base Health", 110f, "Health at level 1." + Restart, 1f, 10000f);
            HealthPerLevel = F(c, ch, "Health Per Level", 33f, "Health gained per level." + Restart, 0f, 1000f);
            BaseRegen = F(c, ch, "Base Regen", 1f, "Health regenerated per second at level 1." + Restart, 0f, 100f);
            RegenPerLevel = F(c, ch, "Regen Per Level", 0.2f, "Regeneration gained per level." + Restart, 0f, 10f);
            BaseArmor = F(c, ch, "Armor", 8f, "Armor (each point is about 1% less damage taken at low values)." + Restart, -100f, 1000f);
            BaseDamage = F(c, ch, "Base Damage", 12f, "Damage stat at level 1. Every skill's damage % is a share of this." + Restart, 1f, 1000f);
            DamagePerLevel = F(c, ch, "Damage Per Level", 2.4f, "Damage stat gained per level." + Restart, 0f, 100f);
            MoveSpeed = F(c, ch, "Move Speed", 7f, "Movement speed in m/s (Commando: 7)." + Restart, 1f, 30f);

            const string pa = "02. Passive - Democracy Protects";
            PassiveChance = F(c, pa, "Chance", 50f, "Chance (%) that a lethal hit is survived.", 0f, 100f);
            PassiveCooldown = F(c, pa, "Cooldown", 40f, "Seconds before the passive can be checked again after a lethal hit.", 0f, 600f);
            PassiveHeal = F(c, pa, "Heal", 25f, "Health restored when it triggers, in % of maximum health.", 0f, 100f);
            PassiveInvulnerability = F(c, pa, "Invulnerability", 1.5f, "Seconds of invulnerability when it triggers.", 0f, 10f);

            const string li = "03. Primary - AR-23 Liberator";
            LiberatorDamage = F(c, li, "Damage", 70f, "Damage per bullet (%).", 0f, 10000f);
            LiberatorFireRate = F(c, li, "Fire Rate", 640f, "Rounds per minute (attack speed raises it).", 30f, 3000f);
            LiberatorMagazine = I(c, li, "Magazine", 30, "Rounds per magazine.", 1, 1000);
            LiberatorReload = F(c, li, "Reload Time", 1.9f, "Seconds to reload (attack speed shortens it).", 0.1f, 10f);
            LiberatorAutoReload = F(c, li, "Auto Reload Delay", 2.5f, "Seconds without firing before a partly empty magazine reloads by itself (0 = only when empty).", 0f, 30f);

            const string br = "04. Primary - SG-225 Breaker";
            BreakerDamage = F(c, br, "Damage", 55f, "Damage per pellet (%).", 0f, 10000f);
            BreakerPellets = I(c, br, "Pellets", 9, "Pellets per shot.", 1, 50);
            BreakerFireRate = F(c, br, "Fire Rate", 300f, "Shots per minute (attack speed raises it).", 10f, 1200f);
            BreakerMagazine = I(c, br, "Magazine", 6, "Shells per magazine.", 1, 100);
            BreakerReload = F(c, br, "Reload Time", 2.4f, "Seconds to reload (attack speed shortens it).", 0.1f, 10f);
            BreakerAutoReload = F(c, br, "Auto Reload Delay", 2.5f, "Seconds without firing before a partly empty magazine reloads by itself (0 = only when empty).", 0f, 30f);

            const string he = "05. Secondary - G-12 High Explosive";
            HeDamage = F(c, he, "Damage", 700f, "Explosion damage (%).", 0f, 100000f);
            HeRadius = F(c, he, "Blast Radius", 10f, "Explosion radius in metres." + Mp, 1f, 50f);
            HeCooldown = F(c, he, "Cooldown", 12f, "Seconds to recharge one grenade." + Restart, 0f, 120f);
            HeCharges = I(c, he, "Charges", 1, "Grenades held." + Restart, 1, 10);

            const string st = "06. Secondary - G-23 Stun";
            StunDamage = F(c, st, "Damage", 300f, "Explosion damage (%). The blast stuns.", 0f, 100000f);
            StunRadius = F(c, st, "Blast Radius", 15f, "Explosion radius in metres." + Mp, 1f, 50f);
            StunCooldown = F(c, st, "Cooldown", 15f, "Seconds to recharge one grenade." + Restart, 0f, 120f);
            StunCharges = I(c, st, "Charges", 2, "Grenades held." + Restart, 1, 10);

            const string dv = "07. Utility - Dive";
            DiveCooldown = F(c, dv, "Cooldown", 4f, "Seconds between dives." + Restart, 0f, 60f);

            const string jp = "08. Utility - LIFT-850 Jump Pack";
            JumpPackCooldown = F(c, jp, "Cooldown", 9f, "Seconds between uses." + Restart, 0f, 120f);
            JumpPackLift = F(c, jp, "Launch Speed", 24f, "Upward speed of the launch from the ground (m/s).", 1f, 100f);
            JumpPackForward = F(c, jp, "Forward Speed", 14f, "Forward speed of the launch (m/s).", 0f, 100f);
            JumpPackHover = F(c, jp, "Hover Time", 2.6f, "Seconds of hover when used in mid air.", 0.1f, 20f);

            const string os = "09. Stratagem - Orbital Precision Strike";
            StrikeDamage = F(c, os, "Damage", 8000f, "Damage of the shot (%). Stuns.", 0f, 1000000f);
            StrikeRadius = F(c, os, "Blast Radius", 8f, "Explosion radius in metres." + Mp, 1f, 100f);
            StrikeDelay = F(c, os, "Impact Delay", 2.2f, "Seconds from the call-in to the impact." + Mp, 0.1f, 20f);
            StrikeCooldown = F(c, os, "Cooldown", 45f, "Seconds to recharge." + Restart, 0f, 600f);

            const string ea = "10. Stratagem - Eagle Airstrike";
            EagleDamage = F(c, ea, "Damage", 1200f, "Damage of each of the 6 bombs (%). Stuns.", 0f, 1000000f);
            EagleRadius = F(c, ea, "Blast Radius", 8.5f, "Explosion radius of each bomb in metres." + Mp, 1f, 100f);
            EagleCooldown = F(c, ea, "Cooldown", 50f, "Seconds to recharge." + Restart, 0f, 600f);

            const string eb = "11. Stratagem - Eagle 500kg Bomb";
            BombDamage = F(c, eb, "Damage", 5000f, "Damage of the bomb (%). Stuns.", 0f, 1000000f);
            BombRadius = F(c, eb, "Blast Radius", 24f, "Explosion radius in metres." + Mp, 1f, 100f);
            BombDelay = F(c, eb, "Impact Delay", 3.2f, "Seconds from the call-in to the impact." + Mp, 0.1f, 20f);
            BombCooldown = F(c, eb, "Cooldown", 65f, "Seconds to recharge." + Restart, 0f, 600f);

            const string em = "12. Stratagem - Orbital EMS Strike";
            EmsDamage = F(c, em, "Damage", 2000f, "Damage of the beacon's landing (%); the beacon then keeps shocking and stunning enemies near it.", 0f, 1000000f);
            EmsCooldown = F(c, em, "Cooldown", 60f, "Seconds to recharge." + Restart, 0f, 600f);

            const string rs = "13. Stratagem - Resupply";
            ResupplyDamage = F(c, rs, "Damage", 2000f, "Damage of the beacon's landing (%); the beacon then heals allies near it.", 0f, 1000000f);
            ResupplyCooldown = F(c, rs, "Cooldown", 50f, "Seconds to recharge." + Restart, 0f, 600f);

            const string sg = "14. Stratagems - All";
            CodeTime = F(c, sg, "Code Time", 6f, "Seconds to type a stratagem code before the input closes.", 1f, 60f);
            BeaconDelay = F(c, sg, "Beacon Delay", 0.8f, "Seconds between the beacon sticking and the stratagem being called in." + Mp, 0f, 10f);
            ThrowRange = F(c, sg, "Throw Range", 95f, "Maximum throw distance of the beacon in metres.", 10f, 300f);

            const string vi = "15. Visuals";
            Cape = c.Bind(vi, "Cape", true, "Show the simulated cape (full package only)." + Restart);
            AmmoCounter = c.Bind(vi, "Ammo Counter", true, "Show the rounds left next to the crosshair while firing and reloading.");
            AmmoOnSkillIcon = c.Bind(vi, "Ammo On Skill Icon", true, "Always show the rounds left on the primary skill icon (bottom right).");
            MigrateOldEntries(c);
        }

        // Up to 0.9 the file had [Model] Cape and FlipPalms: keep the player's cape choice and drop the old section (BepInEx keeps unknown entries otherwise).
        static void MigrateOldEntries(ConfigFile c)
        {
            var orphans = typeof(ConfigFile).GetProperty("OrphanedEntries", BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance)?.GetValue(c) as Dictionary<ConfigDefinition, string>;
            if (orphans == null) return;
            var old = orphans.Keys.Where(k => k.Section == "Model").ToList();
            if (old.Count == 0) return;
            if (orphans.TryGetValue(new ConfigDefinition("Model", "Cape"), out var v) && bool.TryParse(v, out var on)) Cape.Value = on;
            foreach (var k in old) orphans.Remove(k);
            c.Save();
        }

        /// <summary>Damage % from the config as a damage coefficient (70 -> 0.7).</summary>
        public static float Coef(this ConfigEntry<float> percent) => percent.Value / 100f;
    }
}

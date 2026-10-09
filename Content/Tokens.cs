using System.Globalization;
using System.Linq;
using BepInEx.Configuration;
using R2API;

namespace HelldiverMod
{
    /// <summary>English text for the survivor and its skills. The numbers come from the config, so the descriptions always match the tuning.</summary>
    internal static class Tokens
    {
        static string N(float v) => v.ToString("0.##", CultureInfo.InvariantCulture);
        static string Dmg(ConfigEntry<float> percent) => "<style=cIsDamage>" + N(percent.Value) + "% damage</style>";
        static string Sec(float s) => N(s) + (s == 1f ? " second" : " seconds");
        static string Reload(ConfigEntry<float> time, ConfigEntry<float> auto) => Sec(time.Value) + " to reload (faster with <style=cIsDamage>attack speed</style>)."
            + (auto.Value > 0f ? " Reloads by itself after " + Sec(auto.Value) + " without firing." : "");
        static string Code(BeaconKind k) => "<style=cKeywordName>" + string.Join(" ", Stratagems.Get(k).code.Select(a => a == Arrow.Up ? "↑" : a == Arrow.Right ? "→" : a == Arrow.Down ? "↓" : "←")) + "</style> ";

        public static void Add()
        {
            void L(string k, string v) => LanguageAPI.Add(k, v);
            L("HELLDIVER_BODY_NAME", "Helldiver");
            L("HELLDIVER_BODY_SUBTITLE", "Soldier of Super Earth");
            L("HELLDIVER_DESCRIPTION",
                "The Helldiver is a self-reliant soldier who calls the planet's finest firepower down on the enemy.<color=#CCD3E0>\r\n\r\n" +
                "< ! > Pick a rifle for sustained fire or a shotgun for close quarters.\r\n\r\n" +
                "< ! > Grenades clear crowds. Stun grenades buy you breathing room.\r\n\r\n" +
                "< ! > Dive or jump-pack out of trouble.\r\n\r\n" +
                "< ! > Choose your stratagem before you deploy. Type the code with the arrow keys, aim, then fire to throw the beacon.\r\n\r\n</color>");
            L("HELLDIVER_OUTRO", "..and so they left, with a medal for Super Earth.");
            L("HELLDIVER_FAIL", "..and so they vanished, for Democracy.");

            L("HELLDIVER_PASSIVE_NAME", "Democracy Protects");
            L("HELLDIVER_PASSIVE_DESC", "A lethal hit has a <style=cIsHealing>" + N(Settings.PassiveChance.Value) + "%</style> chance to be <style=cIsHealing>survived</style>: the damage is negated, you recover <style=cIsHealing>"
                + N(Settings.PassiveHeal.Value) + "% health</style> and are invulnerable for <style=cIsUtility>" + Sec(Settings.PassiveInvulnerability.Value) + "</style>. Checked at most once every <style=cIsUtility>" + Sec(Settings.PassiveCooldown.Value) + "</style>.");

            L("HELLDIVER_LIBERATOR_NAME", "AR-23 Liberator");
            L("HELLDIVER_LIBERATOR_DESC", "Fire an automatic rifle for " + Dmg(Settings.LiberatorDamage) + " per bullet at " + N(Settings.LiberatorFireRate.Value) + " rounds per minute. "
                + Settings.LiberatorMagazine.Value + "-round magazine, " + Reload(Settings.LiberatorReload, Settings.LiberatorAutoReload) + " Spread builds as you hold the trigger.");
            L("HELLDIVER_BREAKER_NAME", "SG-225 Breaker");
            L("HELLDIVER_BREAKER_DESC", "Fire a shotgun blast of " + Settings.BreakerPellets.Value + " pellets for <style=cIsDamage>" + Settings.BreakerPellets.Value + "x" + N(Settings.BreakerDamage.Value) + "% damage</style>. "
                + Settings.BreakerMagazine.Value + " shells, " + Reload(Settings.BreakerReload, Settings.BreakerAutoReload) + " Damage falls off with range.");

            L("HELLDIVER_HEGRENADE_NAME", "G-12 High Explosive");
            L("HELLDIVER_HEGRENADE_DESC", "Throw a grenade that bounces and explodes a second after it lands, for " + Dmg(Settings.HeDamage) + "." + (Settings.HeCharges.Value > 1 ? " Holds " + Settings.HeCharges.Value + " charges." : ""));
            L("HELLDIVER_STUNGRENADE_NAME", "G-23 Stun");
            L("HELLDIVER_STUNGRENADE_DESC", "Throw a stun grenade that explodes a second after it lands, for " + Dmg(Settings.StunDamage) + " in a wide radius that <style=cIsUtility>stuns</style>." + (Settings.StunCharges.Value > 1 ? " Holds " + Settings.StunCharges.Value + " charges." : ""));

            L("HELLDIVER_DIVE_NAME", "Dive");
            L("HELLDIVER_DIVE_DESC", "Dive a short distance in the direction you are moving.");
            L("HELLDIVER_JUMPPACK_NAME", "LIFT-850 Jump Pack");
            L("HELLDIVER_JUMPPACK_DESC", "On the ground, <style=cIsUtility>launch up and forward</style>. In mid air, <style=cIsUtility>hover</style> for up to " + Sec(Settings.JumpPackHover.Value) + " to stop a fall.");

            string how = " Type the code with the <style=cIsUtility>arrow keys</style>, aim, then <style=cIsUtility>fire</style> to throw the beacon ball. It <style=cIsUtility>sticks</style> to the ground or to enemies and calls the stratagem in on that spot after a moment. Cancel with the Special key. Only costs a charge when thrown.";
            L("HELLDIVER_ORBITALSTRIKE_NAME", "Orbital Precision Strike");
            L("HELLDIVER_ORBITALSTRIKE_DESC", Code(BeaconKind.OrbitalStrike) + "A single orbital shot lands after " + Sec(Settings.StrikeDelay.Value) + " for " + Dmg(Settings.StrikeDamage) + " and <style=cIsUtility>stuns</style>." + how);
            L("HELLDIVER_EAGLEAIRSTRIKE_NAME", "Eagle Airstrike");
            L("HELLDIVER_EAGLEAIRSTRIKE_DESC", Code(BeaconKind.EagleAirstrike) + "An Eagle drops <style=cIsDamage>" + 2 * Stratagems.EagleBombsPerLane + " bombs</style> in two parallel lines of " + Stratagems.EagleBombsPerLane + " toward the target, each for " + Dmg(Settings.EagleDamage) + "." + how);
            L("HELLDIVER_EAGLEBOMB_NAME", "Eagle 500kg Bomb");
            L("HELLDIVER_EAGLEBOMB_DESC", Code(BeaconKind.EagleBomb) + "One enormous bomb lands after " + Sec(Settings.BombDelay.Value) + " for " + Dmg(Settings.BombDamage) + " in a huge radius (" + N(Settings.BombRadius.Value) + " m)." + how);
            L("HELLDIVER_ORBITALEMS_NAME", "Orbital EMS Strike");
            L("HELLDIVER_ORBITALEMS_DESC", Code(BeaconKind.Ems) + "A beacon that repeatedly <style=cIsUtility>shocks and stuns</style> every enemy near it." + how);
            L("HELLDIVER_RESUPPLY_NAME", "Resupply");
            L("HELLDIVER_RESUPPLY_DESC", Code(BeaconKind.Resupply) + "A supply beacon that <style=cIsHealing>heals</style> nearby allies, and <style=cIsUtility>instantly resets your Secondary and Utility cooldowns</style>." + how);
        }
    }
}

using RoR2;
using UnityEngine;

namespace HelldiverMod
{
    /// <summary>Passive "Democracy Protects": a lethal hit is survived (server side) with a chance, at most once per cooldown.</summary>
    public class DemocracyProtects : MonoBehaviour, IOnIncomingDamageServerReceiver
    {
        float nextReady;
        CharacterBody body;
        HealthComponent health;

        void Awake() { body = GetComponent<CharacterBody>(); health = GetComponent<HealthComponent>(); }

        public void OnIncomingDamageServer(DamageInfo damageInfo)
        {
            if (damageInfo.rejected || !body || !health || Time.time < nextReady) return;
            if ((damageInfo.damageType.damageType & DamageType.BypassOneShotProtection) != 0) return;
            float armor = body.armor;
            float dealt = damageInfo.damage * (armor >= 0f ? 100f / (100f + armor) : 2f - 100f / (100f - armor));
            if (dealt < health.combinedHealth) return;
            nextReady = Time.time + Settings.PassiveCooldown.Value;
            if (Random.value * 100f >= Settings.PassiveChance.Value) return;
            damageInfo.rejected = true;
            body.AddTimedBuff(RoR2Content.Buffs.Immune, Settings.PassiveInvulnerability.Value);
            health.HealFraction(Settings.PassiveHeal.Value / 100f, default);
            Util.PlaySound("Play_item_proc_extraLife", gameObject);
            Chat.AddMessage("<style=cShrine>For Super Earth! Democracy protected the Helldiver.</style>");
        }
    }
}

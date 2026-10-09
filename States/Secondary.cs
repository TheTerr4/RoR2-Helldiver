using EntityStates;
using RoR2;
using RoR2.Projectile;
using UnityEngine;

namespace HelldiverMod.States
{
    /// <summary>Grenade throw: Commando's grenade toss animation, our projectile (blast radius set when the projectile is registered).</summary>
    public abstract class ThrowGrenadeBase : GenericProjectileBaseState
    {
        protected abstract GameObject Prefab { get; }
        protected abstract float Damage { get; }
        protected abstract DamageTypeCombo Type { get; }

        public override void OnEnter()
        {
            projectilePrefab = Prefab;
            damageCoefficient = Damage;
            force = 1000f;
            baseDuration = 0.45f;
            baseDelayBeforeFiringProjectile = 0.05f;
            attackSoundString = "Play_commando_M2_grenade_throw";
            targetMuzzle = "";
            base.OnEnter();
        }

        protected override void PlayAnimation(float duration)
        {
            if (!GetModelAnimator()) return;
            int hash = Animator.StringToHash("ThrowGrenade"), rate = Animator.StringToHash("FireFMJ.playbackRate");
            PlayAnimation("Gesture, Additive", hash, rate, duration * 2f);
            PlayAnimation("Gesture, Override", hash, rate, duration * 2f);
        }

        protected override void ModifyProjectileInfo(ref FireProjectileInfo info)
        {
            base.ModifyProjectileInfo(ref info);
            info.damageTypeOverride = Type;
        }

        public override InterruptPriority GetMinimumInterruptPriority() => InterruptPriority.PrioritySkill;
    }

    /// <summary>G-12 High Explosive: bounces, explodes a second after it lands (Commando's grenade fuse).</summary>
    public class ThrowHeGrenade : ThrowGrenadeBase
    {
        protected override GameObject Prefab => Assets.HeGrenade;
        protected override float Damage => Settings.HeDamage.Coef();
        protected override DamageTypeCombo Type => new DamageTypeCombo(DamageType.Generic, DamageTypeExtended.Generic, DamageSource.Secondary);
    }

    /// <summary>G-23 Stun: big radius, light damage, stuns.</summary>
    public class ThrowStunGrenade : ThrowGrenadeBase
    {
        protected override GameObject Prefab => Assets.StunGrenade;
        protected override float Damage => Settings.StunDamage.Coef();
        protected override DamageTypeCombo Type => new DamageTypeCombo(DamageType.Stun1s, DamageTypeExtended.Generic, DamageSource.Secondary);
    }
}

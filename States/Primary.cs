using EntityStates;
using RoR2;
using UnityEngine;

namespace HelldiverMod.States
{
    /// <summary>
    /// Per-body magazines (authority side: bullets are fired on the authority). A partly empty magazine reloads by itself once the gun has been
    /// left alone for the weapon's Auto Reload Delay (the weapon slot idle that long after the last shot).
    /// </summary>
    public class HelldiverAmmo : MonoBehaviour
    {
        public int liberator, breaker;
        public float nextFire, lastShot;
        CharacterBody body;
        EntityStateMachine weapon;

        void Awake()
        {
            liberator = Settings.LiberatorMagazine.Value; breaker = Settings.BreakerMagazine.Value;
            body = GetComponent<CharacterBody>();
        }

        /// <summary>Rounds left and magazine size of the selected primary; false when the primary is not one of ours.</summary>
        public bool Current(out int rounds, out int magazine, out bool isLiberator)
        {
            var sl = body ? body.skillLocator : null;
            var def = sl && sl.primary ? sl.primary.skillDef : null;
            isLiberator = def && def == Survivor.Primaries[0];
            if (isLiberator) { rounds = liberator; magazine = Settings.LiberatorMagazine.Value; return true; }
            rounds = breaker; magazine = Settings.BreakerMagazine.Value;
            return def && def == Survivor.Primaries[1];
        }

        void FixedUpdate()
        {
            if (!body || !body.hasEffectiveAuthority || !Current(out int rounds, out int magazine, out bool lib) || rounds >= magazine) return;
            float delay = (lib ? Settings.LiberatorAutoReload : Settings.BreakerAutoReload).Value;
            if (delay <= 0f || Time.fixedTime - lastShot < delay) return;
            if (!weapon) weapon = EntityStateMachine.FindByCustomName(gameObject, "Weapon");
            if (weapon && weapon.IsInMainState()) weapon.SetInterruptState(lib ? new ReloadLiberator() : (EntityState)new ReloadBreaker(), InterruptPriority.Any);
        }
    }

    public abstract class ReloadBase : BaseState
    {
        protected abstract float BaseDuration { get; }
        protected abstract void Refill(HelldiverAmmo ammo);
        protected abstract string Label { get; }
        float duration;

        public override void OnEnter()
        {
            base.OnEnter();
            duration = BaseDuration / attackSpeedStat;
#if LAB
            Plugin.Log.LogInfo("[bridge] reload " + Label + " " + duration.ToString("0.00") + " s at attack speed " + attackSpeedStat.ToString("0.00") + " t=" + Time.time.ToString("0.00"));
#endif
            Util.PlaySound("Play_loader_m2_launch", gameObject);
            PlayAnimation("Gesture, Override", Animator.StringToHash("ReloadPistols"), Animator.StringToHash("ReloadPistols.playbackRate"), duration);
            if (isAuthority && HelldiverHud.Instance) HelldiverHud.Instance.ShowAmmo(Label + " RELOADING", 99f, true);
        }

        public override void FixedUpdate()
        {
            base.FixedUpdate();
            if (isAuthority && fixedAge >= duration)
            {
                var ammo = GetComponent<HelldiverAmmo>();
                if (ammo) Refill(ammo);
                outer.SetNextStateToMain();
            }
        }

        public override void OnExit()
        {
            PlayAnimation("Gesture, Override", Animator.StringToHash("ReloadPistolsExit"));
            if (isAuthority && HelldiverHud.Instance) HelldiverHud.Instance.ShowAmmo("", 0f);
            base.OnExit();
        }

        public override InterruptPriority GetMinimumInterruptPriority() => InterruptPriority.Skill;
    }

    public class ReloadLiberator : ReloadBase
    {
        protected override float BaseDuration => Settings.LiberatorReload.Value;
        protected override string Label => "AR-23";
        protected override void Refill(HelldiverAmmo a) { a.liberator = Settings.LiberatorMagazine.Value; }
    }

    public class ReloadBreaker : ReloadBase
    {
        protected override float BaseDuration => Settings.BreakerReload.Value;
        protected override string Label => "SG-225";
        protected override void Refill(HelldiverAmmo a) { a.breaker = Settings.BreakerMagazine.Value; }
    }

    /// <summary>
    /// Automatic weapon: fires at an exact rate (rounds per minute, raised by attack speed) for as long as the button is held, in one long-lived state
    /// (a one-bullet state with priority Any would re-trigger every physics frame). Reloads by itself when the magazine runs dry.
    /// </summary>
    public abstract class AutoFireBase : BaseSkillState
    {
        protected abstract float Rpm { get; }
        protected abstract string Label { get; }
        protected abstract ref int Rounds(HelldiverAmmo ammo);
        protected abstract int Magazine { get; }
        protected abstract EntityState CreateReload();
        protected abstract void Shoot(Ray aim);

        float nextShot;
        bool firedAny;
        HelldiverAmmo ammo;

        public override void OnEnter()
        {
            base.OnEnter();
            ammo = GetComponent<HelldiverAmmo>();
            nextShot = Mathf.Max(Time.fixedTime, ammo ? ammo.nextFire : 0f);
        }

        public override void FixedUpdate()
        {
            base.FixedUpdate();
            if (!isAuthority) return;
            var aim = GetAimRay();
            StartAimMode(aim, 2.5f);
            if (Time.fixedTime < nextShot) return;
            if (firedAny && !IsKeyDownAuthority()) { outer.SetNextStateToMain(); return; }
            if (ammo)
            {
                ref int left = ref Rounds(ammo);
                if (left <= 0) { outer.SetNextState(CreateReload()); return; }
                left--;
                ammo.lastShot = Time.fixedTime;
                if (HelldiverHud.Instance) HelldiverHud.Instance.ShowAmmo(Label + "  " + left + " / " + Magazine, 2.5f);
            }
            firedAny = true;
            nextShot = Mathf.Max(nextShot + 60f / Mathf.Max(Rpm, 1f) / Mathf.Max(attackSpeedStat, 0.1f), Time.fixedTime);
            Shoot(aim);
            if (ammo && Rounds(ammo) <= 0) outer.SetNextState(CreateReload());     // reload as soon as the magazine runs dry
        }

        public override void OnExit()
        {
            if (ammo) ammo.nextFire = nextShot;
            base.OnExit();
        }

        public override InterruptPriority GetMinimumInterruptPriority() => InterruptPriority.Skill;
    }

    /// <summary>AR-23 Liberator: automatic rifle, alternating muzzles, spread builds while the trigger is held.</summary>
    public class FireLiberator : AutoFireBase
    {
        const float Force = 150f, Bloom = 0.3f;
        static bool rightHand;

        protected override float Rpm => Settings.LiberatorFireRate.Value;
        protected override string Label => "AR-23";
        protected override ref int Rounds(HelldiverAmmo ammo) => ref ammo.liberator;
        protected override int Magazine => Settings.LiberatorMagazine.Value;
        protected override EntityState CreateReload() => new ReloadLiberator();

        protected override void Shoot(Ray aim)
        {
            rightHand = !rightHand;
            string muzzle = rightHand ? "MuzzleRight" : "MuzzleLeft";
            Util.PlaySound("Play_commando_R", gameObject);
            if (Assets.MuzzleFlash) EffectManager.SimpleMuzzleFlash(Assets.MuzzleFlash, gameObject, muzzle, false);
            PlayAnimation(rightHand ? "Gesture Additive, Right" : "Gesture Additive, Left", Animator.StringToHash(rightHand ? "FirePistol, Right" : "FirePistol, Left"));
            AddRecoil(-0.3f, -0.6f, -0.25f, 0.25f);
            new BulletAttack
            {
                owner = gameObject, weapon = gameObject,
                origin = aim.origin, aimVector = aim.direction,
                minSpread = 0f, maxSpread = characterBody.spreadBloomAngle,
                damage = Settings.LiberatorDamage.Coef() * damageStat, force = Force,
                tracerEffectPrefab = Assets.Tracer, muzzleName = muzzle, hitEffectPrefab = Assets.HitSpark,
                isCrit = RollCrit(), radius = 0.1f, smartCollision = true,
                trajectoryAimAssistMultiplier = 0.75f,
                damageType = new DamageTypeCombo(DamageType.Generic, DamageTypeExtended.Generic, DamageSource.Primary),
            }.Fire();
            characterBody.AddSpreadBloom(Bloom);
        }
    }

    /// <summary>SG-225 Breaker: automatic shotgun, strong up close, damage falls off with range.</summary>
    public class FireBreaker : AutoFireBase
    {
        const float Force = 250f;

        protected override float Rpm => Settings.BreakerFireRate.Value;
        protected override string Label => "SG-225";
        protected override ref int Rounds(HelldiverAmmo ammo) => ref ammo.breaker;
        protected override int Magazine => Settings.BreakerMagazine.Value;
        protected override EntityState CreateReload() => new ReloadBreaker();

        protected override void Shoot(Ray aim)
        {
            Util.PlaySound("Play_commando_M2", gameObject);
            if (Assets.MuzzleFlash) EffectManager.SimpleMuzzleFlash(Assets.MuzzleFlash, gameObject, "MuzzleRight", false);
            PlayAnimation("Gesture Additive, Right", Animator.StringToHash("FirePistol, Right"));
            AddRecoil(-1.2f, -2f, -0.6f, 0.6f);
            new BulletAttack
            {
                owner = gameObject, weapon = gameObject,
                origin = aim.origin, aimVector = aim.direction,
                minSpread = 0.5f, maxSpread = 4.5f + characterBody.spreadBloomAngle,
                bulletCount = (uint)Mathf.Max(1, Settings.BreakerPellets.Value),
                damage = Settings.BreakerDamage.Coef() * damageStat, force = Force,
                falloffModel = BulletAttack.FalloffModel.DefaultBullet,
                tracerEffectPrefab = Assets.ShotgunTracer, muzzleName = "MuzzleRight", hitEffectPrefab = Assets.ShotgunHitSpark,
                isCrit = RollCrit(), radius = 0.15f, smartCollision = true,
                damageType = new DamageTypeCombo(DamageType.Generic, DamageTypeExtended.Generic, DamageSource.Primary),
            }.Fire();
            characterBody.AddSpreadBloom(1.2f);
        }
    }
}

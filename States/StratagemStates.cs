using System;
using EntityStates;
using RoR2;
using UnityEngine;

namespace HelldiverMod.States
{
    /// <summary>
    /// First half of every stratagem: type the HD2 arrow code, then the beacon is armed. Stock is only spent when the beacon is really thrown,
    /// so cancelling or running out of time is free. Each stratagem needs its own state types (a remote copy of a state is built from its type alone).
    /// </summary>
    public abstract class StratagemInputBase : BaseSkillState
    {
        protected abstract BeaconKind Kind { get; }
        static bool legacyInputBroken;
        int progress;
        bool handedOver;

        public override void OnEnter()
        {
            base.OnEnter();
            Util.PlaySound("Play_captain_shift_start", gameObject);
            if (isAuthority && HelldiverHud.Instance) { var d = Stratagems.Get(Kind); HelldiverHud.Instance.ShowCode(d.name, d.code); }
        }

        static readonly KeyCode[] keys = { KeyCode.UpArrow, KeyCode.RightArrow, KeyCode.DownArrow, KeyCode.LeftArrow };   // in Arrow order

        static bool Pressed(Arrow d)
        {
#if LAB
            if (DevBridge.Pending(keys[(int)d])) return true;
#endif
            if (legacyInputBroken) return false;
            try { return Input.GetKeyDown(keys[(int)d]); }
            catch (InvalidOperationException) { legacyInputBroken = true; Plugin.Log.LogError("Legacy Input is disabled in this build; stratagem codes cannot be read."); return false; }
        }

        public override void Update()
        {
            base.Update();
            if (!isAuthority) return;
            var code = Stratagems.Get(Kind).code;
            for (int i = 0; i < 4; i++)
            {
                var d = (Arrow)i;
                if (!Pressed(d)) continue;
                if (d == code[progress])
                {
                    progress++;
                    Util.PlaySound("Play_UI_menuClick", gameObject);
                    if (HelldiverHud.Instance) HelldiverHud.Instance.progress = progress;
                    if (progress >= code.Length)
                    {
                        var armed = (ArmedBase)Activator.CreateInstance(Stratagems.Get(Kind).armed);
                        armed.activatorSkillSlot = activatorSkillSlot;
                        handedOver = true;
                        outer.SetNextState(armed);
                        return;
                    }
                }
                else
                {
                    progress = 0;
                    if (HelldiverHud.Instance) HelldiverHud.Instance.MarkWrong();
                }
            }
        }

        public override void FixedUpdate()
        {
            base.FixedUpdate();
            if (!isAuthority) return;
            bool cancel = fixedAge > 0.3f && ClaimCancel(inputBank);
            if (cancel || fixedAge > Settings.CodeTime.Value) outer.SetNextStateToMain();
        }

        /// <summary>
        /// Special pressed again: cancel. The press is claimed, as a skill activation claims it: otherwise the character's main state sees the same,
        /// still unclaimed press as soon as the weapon slot is free again and starts the stratagem anew (which then sat there until it timed out).
        /// </summary>
        public static bool ClaimCancel(InputBankTest bank)
        {
            if (!bank || !bank.skill4.justPressed || bank.skill4.hasPressBeenClaimed) return false;
            bank.skill4.hasPressBeenClaimed = true;
            return true;
        }

        public override void OnExit()
        {
            if (HelldiverHud.Instance && !handedOver) HelldiverHud.Instance.Hide();   // the armed state shows its own prompt
            base.OnExit();
        }

        public override InterruptPriority GetMinimumInterruptPriority() => InterruptPriority.Pain;
    }

    /// <summary>Second half: aim (arc preview), then fire (primary) to throw the beacon ball, which carries the stratagem's damage.</summary>
    public abstract class ArmedBase : AimThrowableBase
    {
        protected abstract BeaconKind Kind { get; }
        protected bool cancelled, fireRequested;
        const float Timeout = 15f;

        public override void OnEnter()
        {
            var d = Stratagems.Get(Kind);
            maxDistance = Settings.ThrowRange.Value;
            rayRadius = 0.2f;
            baseMinimumDuration = 0.25f;
            projectilePrefab = d.beacon;
            damageCoefficient = d.damage.Coef();
            endpointVisualizerPrefab = Assets.StrikeIndicator;
            endpointVisualizerRadiusScale = d.indicatorRadius;
            arcVisualizerPrefab = Assets.ThrowArc;
            base.OnEnter();
            Util.PlaySound("Play_captain_shift_active_loop", gameObject);
            if (isAuthority && HelldiverHud.Instance) HelldiverHud.Instance.ShowArmed(d.name);
        }

        protected override bool KeyIsDown()
        {
            if (!inputBank) return false;
            if ((fixedAge > 0.3f && StratagemInputBase.ClaimCancel(inputBank)) || fixedAge > Timeout) { cancelled = true; return false; }
            if (fixedAge > 0.15f && inputBank.skill1.justPressed) fireRequested = true;
            return !fireRequested;
        }

        protected override EntityState PickNextState() => cancelled ? null : new StratagemThrown();

        // Aiming straight at something right in front of the face (or at a point straight below) makes the arc maths divide by zero; throw plainly forward instead.
        protected override void UpdateTrajectoryInfo(out TrajectoryInfo dest)
        {
            base.UpdateTrajectoryInfo(out dest);
            var d = dest.finalRay.direction;
            if (float.IsNaN(dest.speedOverride) || float.IsInfinity(dest.speedOverride) || float.IsNaN(d.x) || float.IsNaN(d.y) || float.IsNaN(d.z))
            {
                var aim = GetAimRay();
                dest.finalRay = aim;
                dest.speedOverride = Stratagems.BeaconSpeed;
                dest.hitPoint = aim.GetPoint(6f);
                dest.hitNormal = -aim.direction;
                dest.travelTime = 0.2f;
            }
        }

        protected override void FireProjectile()
        {
            if (cancelled) return;
            if (activatorSkillSlot) activatorSkillSlot.DeductStock(1);
            Util.PlaySound("Play_captain_shift_confirm", gameObject);
            OnThrown();
            base.FireProjectile();
        }

        protected virtual void OnThrown() { }

        public override void OnExit()
        {
            Util.PlaySound("Stop_captain_shift_active_loop", gameObject);
            if (HelldiverHud.Instance) HelldiverHud.Instance.Hide();
            base.OnExit();
        }

        public override InterruptPriority GetMinimumInterruptPriority() => InterruptPriority.Pain;
    }

    /// <summary>After the throw: hold the weapon until the fire button is let go, so the click that threw the beacon does not also fire the gun.</summary>
    public class StratagemThrown : BaseState
    {
        public override void FixedUpdate()
        {
            base.FixedUpdate();
            if (isAuthority && (fixedAge > 1f || !inputBank || !inputBank.skill1.down)) outer.SetNextStateToMain();
        }

        public override InterruptPriority GetMinimumInterruptPriority() => InterruptPriority.Skill;
    }

    public class InputOrbitalStrike : StratagemInputBase { protected override BeaconKind Kind => BeaconKind.OrbitalStrike; }
    public class InputEagleAirstrike : StratagemInputBase { protected override BeaconKind Kind => BeaconKind.EagleAirstrike; }
    public class InputEagleBomb : StratagemInputBase { protected override BeaconKind Kind => BeaconKind.EagleBomb; }
    public class InputOrbitalEms : StratagemInputBase { protected override BeaconKind Kind => BeaconKind.Ems; }
    public class InputResupply : StratagemInputBase { protected override BeaconKind Kind => BeaconKind.Resupply; }

    public class ArmedOrbitalStrike : ArmedBase { protected override BeaconKind Kind => BeaconKind.OrbitalStrike; }
    public class ArmedEagleAirstrike : ArmedBase { protected override BeaconKind Kind => BeaconKind.EagleAirstrike; }
    public class ArmedEagleBomb : ArmedBase { protected override BeaconKind Kind => BeaconKind.EagleBomb; }
    public class ArmedEms : ArmedBase { protected override BeaconKind Kind => BeaconKind.Ems; }

    public class ArmedResupply : ArmedBase
    {
        protected override BeaconKind Kind => BeaconKind.Resupply;

        // Resupply restocks the Helldiver's own secondary and utility the moment the beacon leaves their hand
        protected override void OnThrown()
        {
            if (!skillLocator) return;
            if (skillLocator.secondary) skillLocator.secondary.Reset();
            if (skillLocator.utility) skillLocator.utility.Reset();
        }
    }
}

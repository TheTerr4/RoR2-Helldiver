using EntityStates;
using RoR2;
using UnityEngine;

namespace HelldiverMod.States
{
    /// <summary>
    /// Dive: the vanilla Commando dodge, minus the fire. DodgeState spawns Commando's boot jets (jetEffect, a static shared by every user of the state)
    /// on the model's LeftJet / RightJet points; the Helldiver dives without them, and only the Jump Pack has flames. The vanilla configuration (duration,
    /// speed curve) only reaches the exact DodgeState type, so it is copied from a plain instance.
    /// </summary>
    public class HelldiverDive : EntityStates.Commando.DodgeState
    {
        static bool read; static float dur = 0.4f, speed0 = 5f, speed1 = 2.5f;

        public override void OnEnter()
        {
            if (!read)
            {
                read = true;
                var vanilla = new EntityStates.Commando.DodgeState();
                if (vanilla.duration > 0f) { dur = vanilla.duration; speed0 = vanilla.initialSpeedCoefficient; speed1 = vanilla.finalSpeedCoefficient; }
            }
            duration = dur; initialSpeedCoefficient = speed0; finalSpeedCoefficient = speed1;
            var jets = jetEffect;
            jetEffect = null;
            try { base.OnEnter(); } finally { jetEffect = jets; }
        }
    }

    /// <summary>LIFT-850 Jump Pack: a burst up and forward from the ground, a hover in mid air. Flames come out of the pack's nozzles (or generic jets without the pack model).</summary>
    public class JumpPackBurst : BaseState
    {
        const float BurstDuration = 0.55f, HoverLevel = 0.6f;
        Vector3 forward;
        bool hover;
        float duration;
        GameObject jets;
        HelldiverPack pack;

        public override void OnEnter()
        {
            base.OnEnter();
            Util.PlaySound("Play_commando_shift", gameObject);
            hover = characterMotor && !characterMotor.isGrounded;
            duration = hover ? Settings.JumpPackHover.Value : BurstDuration;
            var model = GetModelTransform();
            pack = model ? model.GetComponent<HelldiverPack>() : null;
            if (pack && pack.Ready) pack.Thrust(hover ? HoverLevel : 1f);
            else { pack = null; if (Assets.DashJets) jets = Object.Instantiate(Assets.DashJets, transform); }
            forward = inputBank ? inputBank.moveVector : Vector3.zero;
            if (forward == Vector3.zero) forward = GetAimRay().direction;
            forward.y = 0f;
            forward.Normalize();
            if (characterMotor && !hover) { characterMotor.Motor.ForceUnground(); characterMotor.velocity.y = Settings.JumpPackLift.Value; }
        }

        public override void FixedUpdate()
        {
            base.FixedUpdate();
            if (characterMotor && isAuthority)
            {
                var v = characterMotor.velocity;
                if (hover)
                {
                    // cancel the fall, keep a gentle float, and let the player steer in the air
                    v.y = Mathf.Lerp(v.y, 0.8f, 0.25f);
                    characterMotor.velocity = v;
                    if (inputBank)
                    {
                        characterMotor.moveDirection = inputBank.moveVector;
                        if (characterDirection) characterDirection.moveVector = inputBank.aimDirection;
                    }
                    if (characterMotor.isGrounded) { outer.SetNextStateToMain(); return; }
                }
                else
                {
                    v.y = Mathf.Max(v.y, Mathf.Lerp(Settings.JumpPackLift.Value, 6f, fixedAge / duration));
                    v.x = forward.x * Settings.JumpPackForward.Value; v.z = forward.z * Settings.JumpPackForward.Value;
                    characterMotor.velocity = v;
                }
            }
            if (fixedAge >= duration && isAuthority) outer.SetNextStateToMain();
        }

        public override void OnExit()
        {
            if (jets) Object.Destroy(jets);
            if (pack) pack.Thrust(0f);
            if (characterMotor && !hover && characterMotor.velocity.y > 8f) { var v = characterMotor.velocity; v.y = 8f; characterMotor.velocity = v; }
            base.OnExit();
        }

        public override InterruptPriority GetMinimumInterruptPriority() => hover ? InterruptPriority.Skill : InterruptPriority.PrioritySkill;
    }
}

using HelldiverMod.States;
using RoR2;
using UnityEngine;

namespace HelldiverMod
{
    /// <summary>
    /// Two-handed weapon hold. The weapon root is posed in world space every frame (shouldered along the aim direction while fighting,
    /// carried across the chest when idle / sprinting / reloading) and both arms are solved with two-bone IK so the gloves close on the grip and the foregrip.
    /// Runs in LateUpdate, after the animator has written the arm bones.
    /// </summary>
    public class HelldiverGrip : MonoBehaviour
    {
        // --- tuning (lab bridge: "gripset <name> <value>")
        public static float RaiseTime = 0.2f, HoldTime = 1.6f;
        // raised pose: weapon origin relative to the right shoulder, in the aim frame
        public static float RaisedX = -0.02f, RaisedY = -0.10f, RaisedZ = 0.32f;
        // low-ready pose (rifle carried horizontally across the chest, muzzle to the left):
        // origin relative to the right shoulder in the yaw frame, plus pitch (positive = muzzle down), yaw (negative = toward the left) and roll
        public static float LowX = -0.25f, LowY = -0.30f, LowZ = 0.28f, LowPitch = 10f, LowYaw = -90f, LowRoll = 0f;
        public static float TwistShare = 0.6f, TwistMax = 70f, SwingMax = 90f;   // share of the hand-vs-forearm twist handed to the forearm so the wrist does not shear
        public static float AimYawLimit = 60f, AimPitchLimit = 75f;             // how far the weapon may swing away from the body's facing
        public static float DebugYaw = 0f;                                      // lab: pretend the camera is turned this many degrees away from the body
        public static float ReachFrac = 0.97f;                                  // fraction of the full arm length the hands may be asked to stretch
        public static float ForeDrop = 0.03f;                                   // left palm sits this far below the foregrip key point
        public static float RPalmRoll = 0f, LPalmRoll = 0f;                     // glove roll about the finger axis (degrees)
        public static float FingerTilt = 0.25f;                                 // the fingers lean toward the thumb side
        public static float PalmY = 0.08f;                                      // palm centre along the hand bone's finger axis
        public static float RFingerPitch = -0.25f, LFingerPitch = 0.05f;
        public static float LNormalX = 0.3f, LFingerSide = 0.5f;                // left fingers angle toward the body across the forend (less wrist bend)
        public static float Display = 0f;                                       // 0 = low-ready on the character select screen, 1 = shouldered

        public CharacterModel model;
        public Transform root;
        public int index = 0;

        Transform upR, loR, handR, upL, loL, handL;
        Quaternion restR = Quaternion.identity, restL = Quaternion.identity;
        float raise, lastFire = -99f;
        public float twistR, swingR, twistL, swingL;   // lab diagnostics: hand deviation from the bind pose before the correction (degrees)
        public float errR, errL;                       // lab diagnostics: distance of each palm from its target

        public static void Solve(Transform up, Transform lo, Transform hand, Vector3 target, Vector3 pole)
        {
            Vector3 a = up.position, b = lo.position, c = hand.position;
            float l1 = (b - a).magnitude, l2 = (c - b).magnitude;
            Vector3 to = target - a;
            float d = Mathf.Clamp(to.magnitude, Mathf.Abs(l1 - l2) + 0.01f, (l1 + l2) * 0.999f);
            Vector3 dir = to.sqrMagnitude > 1e-8f ? to.normalized : Vector3.down;
            float x = (d * d + l1 * l1 - l2 * l2) / (2f * d);
            float h = Mathf.Sqrt(Mathf.Max(0f, l1 * l1 - x * x));
            Vector3 side = pole - dir * Vector3.Dot(pole, dir);
            side = side.sqrMagnitude > 1e-8f ? side.normalized : Vector3.Cross(dir, Vector3.right).normalized;
            Vector3 elbow = a + dir * x + side * h;
            up.rotation = Quaternion.FromToRotation(b - a, elbow - a) * up.rotation;
            Vector3 reach = a + dir * d;
            lo.rotation = Quaternion.FromToRotation(hand.position - lo.position, reach - lo.position) * lo.rotation;
        }

        // Where the hand ends up is dictated by the weapon, where the forearm ends up by the IK. The skinning is neutral only at the bind pose, so what matters
        // is the hand's deviation from the bind-pose relation to the forearm (delta: hand = forearm * rest * delta). The roll part of it is partly handed to the
        // forearm, the rest is clamped (twist about the bone's Y axis, swing = wrist bend), so the wrist can neither wring out nor fold over.
        static void TwistSwing(Quaternion q, out Quaternion swing, out float twistDeg)
        {
            if (q.w < 0f) q = new Quaternion(-q.x, -q.y, -q.z, -q.w);
            twistDeg = Mathf.DeltaAngle(0f, 2f * Mathf.Atan2(q.y, q.w) * Mathf.Rad2Deg);
            swing = q * Quaternion.Inverse(Quaternion.AngleAxis(twistDeg, Vector3.up));
        }

        static void FinishHand(Transform lo, Transform hand, Quaternion handRot, Quaternion rest, out float twistBefore, out float swingBefore)
        {
            Quaternion delta = Quaternion.Inverse(lo.rotation * rest) * handRot;
            TwistSwing(delta, out Quaternion sw, out float tw);
            twistBefore = tw; sw.ToAngleAxis(out swingBefore, out _); swingBefore = Mathf.Abs(Mathf.DeltaAngle(0f, swingBefore));
            Vector3 axisW = hand.position - lo.position;
            if (axisW.sqrMagnitude > 1e-8f && TwistShare > 0f)
                lo.rotation = Quaternion.AngleAxis(tw * TwistShare, axisW.normalized) * lo.rotation;
            delta = Quaternion.Inverse(lo.rotation * rest) * handRot;
            TwistSwing(delta, out sw, out tw);
            tw = Mathf.Clamp(tw, -TwistMax, TwistMax);
            sw.ToAngleAxis(out float sa, out Vector3 sax);
            sa = Mathf.DeltaAngle(0f, sa);
            if (Mathf.Abs(sa) > SwingMax) sa = Mathf.Sign(sa) * SwingMax;
            hand.rotation = lo.rotation * rest * (Quaternion.AngleAxis(sa, sax) * Quaternion.AngleAxis(tw, Vector3.up));
        }

        static Quaternion BindRot(Matrix4x4 bind)
        {
            var m = bind.inverse;
            return Quaternion.LookRotation(m.GetColumn(2), m.GetColumn(1));
        }

        static Quaternion RestRelation(SkinnedMeshRenderer body, Transform lo, Transform hand) =>
            ModelFiles.BindPose(body, lo, out var a) && ModelFiles.BindPose(body, hand, out var b) ? Quaternion.Inverse(BindRot(a)) * BindRot(b) : Quaternion.identity;

        // Glove frame (measured from the glove mesh after tools/hd2/fixhands.py --flip): fingers along local +Y leaning toward the thumb side, palm facing local -Z.
        static void PlaceHand(Vector3 fingers, Vector3 normal, float roll, float tilt, out Quaternion rotation)
        {
            Vector3 nl = Quaternion.AngleAxis(roll, Vector3.up) * new Vector3(0f, 0f, -1f);
            var local = Quaternion.LookRotation(new Vector3(tilt, 1f, 0f), nl);
            var want = Quaternion.LookRotation(fingers.normalized, normal.normalized);
            rotation = want * Quaternion.Inverse(local);
        }

        bool Find()
        {
            if (!model) return false;
            var b = ModelFiles.Find(model.transform, "upper_arm.r", "lower_arm.r", "hand.r", "upper_arm.l", "lower_arm.l", "hand.l");
            upR = b[0]; loR = b[1]; handR = b[2]; upL = b[3]; loL = b[4]; handL = b[5];
            if (!(upR && loR && handR && upL && loL && handL)) return false;
            var body = ModelFiles.BodyRenderer(model);
            restR = RestRelation(body, loR, handR);
            restL = RestRelation(body, loL, handL);
            return true;
        }

        void LateUpdate()
        {
            if (!root || !root.gameObject.activeInHierarchy) return;
            if (!upR && !Find()) return;
            var weapon = WeaponModels.Get(index);
            if (weapon == null || !weapon.mesh) return;

            var body = model.body;
            float want = Display;
            if (body)
            {
                var sl = body.skillLocator;
                var cur = sl && sl.primary && sl.primary.stateMachine ? sl.primary.stateMachine.state : null;
                if (cur is AutoFireBase) lastFire = Time.time;
                want = !(cur is ReloadBase) && !body.isSprinting && Time.time - lastFire < HoldTime ? 1f : 0f;
            }
            raise = Mathf.MoveTowards(raise, want, Time.deltaTime / Mathf.Max(RaiseTime, 0.01f));
            float s = Mathf.SmoothStep(0f, 1f, raise);

            var mt = model.transform;
            float sign = Vector3.Dot(upR.position - upL.position, mt.right) >= 0f ? 1f : -1f;
            float modelYaw = mt.eulerAngles.y;
            var yaw = Quaternion.Euler(0f, modelYaw, 0f);
            Vector3 aim = body && body.inputBank ? body.inputBank.aimDirection : mt.forward;
            if (aim.sqrMagnitude < 0.01f) aim = mt.forward;
            aim.Normalize();
            // the weapon may only swing so far from the body's facing: turning the camera faster than the body follows must not drag the arms out of reach
            float aimYaw = Mathf.Atan2(aim.x, aim.z) * Mathf.Rad2Deg + DebugYaw;
            float aimPitch = -Mathf.Asin(Mathf.Clamp(aim.y, -1f, 1f)) * Mathf.Rad2Deg;
            float dyaw = Mathf.Clamp(Mathf.DeltaAngle(modelYaw, aimYaw), -AimYawLimit, AimYawLimit);
            var aimRot = Quaternion.Euler(Mathf.Clamp(aimPitch, -AimPitchLimit, AimPitchLimit), modelYaw + dyaw, 0f);

            Vector3 S = upR.position;
            Vector3 posHigh = S + aimRot * new Vector3(RaisedX, RaisedY, RaisedZ);
            Vector3 posLow = S + yaw * new Vector3(LowX, LowY, LowZ);
            Quaternion rotLow = yaw * Quaternion.Euler(LowPitch, LowYaw, LowRoll);
            Vector3 Wp = Vector3.Lerp(posLow, posHigh, s);
            Quaternion Wr = Quaternion.Slerp(rotLow, aimRot, s);

            Vector3 down = Vector3.down, side = mt.right * sign;
            Vector3 gripLocal = weapon.grip, foreLocal = weapon.under + new Vector3(0f, -ForeDrop, 0f);
            PlaceHand(Wr * new Vector3(0f, RFingerPitch, 1f), Wr * Vector3.left, RPalmRoll, -FingerTilt, out Quaternion hr);
            PlaceHand(Wr * new Vector3(LFingerSide, LFingerPitch, 1f), Wr * new Vector3(LNormalX, 1f, 0f), LPalmRoll, FingerTilt, out Quaternion hl);
            // palm centres in hand-bone space (measured on the gloves)
            Vector3 palmR = new Vector3(-0.074f, PalmY, 0.034f), palmL = new Vector3(0.070f, PalmY, 0.036f);

            // reach fit: slide the whole weapon until both wrists are within reach of their shoulders, so the arms never stretch to catch up
            float reachR = ((loR.position - upR.position).magnitude + (handR.position - loR.position).magnitude) * ReachFrac;
            float reachL = ((loL.position - upL.position).magnitude + (handL.position - loL.position).magnitude) * ReachFrac;
            for (int it = 0; it < 6; it++)
            {
                Vector3 dR = Wp + Wr * gripLocal - hr * palmR - upR.position;
                if (dR.magnitude > reachR) Wp -= dR.normalized * (dR.magnitude - reachR);
                Vector3 dL = Wp + Wr * foreLocal - hl * palmL - upL.position;
                if (dL.magnitude > reachL) Wp -= dL.normalized * (dL.magnitude - reachL);
            }
            root.position = Wp; root.rotation = Wr;

            Vector3 gripW = Wp + Wr * gripLocal, foreW = Wp + Wr * foreLocal;
            Solve(upR, loR, handR, gripW - hr * palmR, side * 0.7f + down - mt.forward * 0.2f);
            FinishHand(loR, handR, hr, restR, out twistR, out swingR);
            errR = (handR.TransformPoint(palmR) - gripW).magnitude;
            Solve(upL, loL, handL, foreW - hl * palmL, -side * 0.7f + down - mt.forward * 0.2f);
            FinishHand(loL, handL, hl, restL, out twistL, out swingL);
            errL = (handL.TransformPoint(palmL) - foreW).magnitude;
        }
    }
}

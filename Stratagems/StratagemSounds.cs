using RoR2.Audio;
using UnityEngine;

namespace HelldiverMod
{
    /// <summary>
    /// Blast sounds for the strike stratagems (Orbital Precision Strike, Eagle Airstrike, Eagle 500kg Bomb). The Captain airstrike projectiles reused for them
    /// are silent on their own (Captain plays their sounds from his states). The projectiles are networked, so every player's game sees each one explode
    /// and plays the sounds locally at that spot: nothing extra goes over the network (several networked point sounds in one frame get dropped).
    /// Only item sounds and the Commando's (the Helldiver's own bank) are used: other monster and survivor sound banks are loaded only while that
    /// character is in the game. The beacon keeps its stick / arm sounds; the supply beacons (EMS, Resupply) keep the Captain supply drop's own sounds.
    /// </summary>
    internal static class StratagemSounds
    {
        public const string MeteorImpact = "Play_item_use_meteor_impact";    // heavy impact with a long rumble
        public const string MissileBlast = "Play_item_proc_missile_explo";   // short, sharp blast
        public const string GrenadeBlast = "Play_commando_M2_grenade_explo"; // punchy crack on top
        public const string BigBlast = "Play_item_use_BFG_explode";          // the 500kg bomb
    }

    /// <summary>On a strike projectile: plays its blast sounds where it detonates (the projectile is destroyed when it explodes, on every client).</summary>
    public class ImpactSounds : MonoBehaviour
    {
        public string[] sounds;

        void OnDestroy()
        {
            if (!gameObject.scene.isLoaded || sounds == null) return;      // not when the stage unloads
            var pos = transform.position;
            foreach (var s in sounds) PointSoundManager.EmitSoundLocal((AkEventIdArg)s, pos);
        }
    }
}

using System;
using BepInEx.Configuration;
using HelldiverMod.States;
using R2API;
using RoR2;
using RoR2.Projectile;
using UnityEngine;

namespace HelldiverMod
{
    public enum Arrow { Up, Right, Down, Left }

    public enum BeaconKind { OrbitalStrike, EagleAirstrike, EagleBomb, Ems, Resupply }

    /// <summary>One stratagem: its HD2 arrow code, its skill and states, its beacon, and the config entries that tune it.</summary>
    internal class StratagemDef
    {
        public BeaconKind kind;
        public string id, name, icon;                 // id: skill "Helldiver" + id and tokens HELLDIVER_<ID>_NAME / _DESC
        public Arrow[] code;
        public ConfigEntry<float> damage, cooldown;   // damage %: of the strike, each Eagle bomb, or the supply beacon's landing
        public float indicatorRadius;                 // the aim indicator's size
        public Type input, armed;                     // entity states: type the code, then aim and throw
        public GameObject beacon;                     // the thrown ball that calls it in
    }

    /// <summary>Every stratagem in one table, plus the projectiles they call in.</summary>
    internal static class Stratagems
    {
        public static StratagemDef[] All;
        public static StratagemDef Get(BeaconKind kind) => All[(int)kind];

        public const float BeaconSpeed = 55f;
        public const int EagleBombsPerLane = 3;
        public const float EagleSpacing = 10f, EagleLaneGap = 18f, EagleIndicator = 12f, SupplyIndicator = 10f;
        public static GameObject StrikeProjectile, EagleStrafeProjectile, EagleBombProjectile;

        /// <summary>Build the table (in loadout order: profiles store the selected variant by index) and register the projectiles.</summary>
        public static void Create()
        {
            All = new[]
            {
                new StratagemDef { kind = BeaconKind.OrbitalStrike, id = "OrbitalStrike", name = "Orbital Precision Strike", icon = "orbital_strike", code = new[] { Arrow.Right, Arrow.Right, Arrow.Up },
                    damage = Settings.StrikeDamage, cooldown = Settings.StrikeCooldown, indicatorRadius = Settings.StrikeRadius.Value, input = typeof(InputOrbitalStrike), armed = typeof(ArmedOrbitalStrike) },
                new StratagemDef { kind = BeaconKind.EagleAirstrike, id = "EagleAirstrike", name = "Eagle Airstrike", icon = "eagle_airstrike", code = new[] { Arrow.Up, Arrow.Right, Arrow.Down, Arrow.Right },
                    damage = Settings.EagleDamage, cooldown = Settings.EagleCooldown, indicatorRadius = EagleIndicator, input = typeof(InputEagleAirstrike), armed = typeof(ArmedEagleAirstrike) },
                new StratagemDef { kind = BeaconKind.EagleBomb, id = "EagleBomb", name = "Eagle 500kg Bomb", icon = "eagle_bomb", code = new[] { Arrow.Up, Arrow.Right, Arrow.Down, Arrow.Down, Arrow.Down },
                    damage = Settings.BombDamage, cooldown = Settings.BombCooldown, indicatorRadius = Settings.BombRadius.Value, input = typeof(InputEagleBomb), armed = typeof(ArmedEagleBomb) },
                new StratagemDef { kind = BeaconKind.Ems, id = "OrbitalEms", name = "Orbital EMS Strike", icon = "orbital_ems", code = new[] { Arrow.Right, Arrow.Right, Arrow.Left, Arrow.Down },
                    damage = Settings.EmsDamage, cooldown = Settings.EmsCooldown, indicatorRadius = SupplyIndicator, input = typeof(InputOrbitalEms), armed = typeof(ArmedEms) },
                new StratagemDef { kind = BeaconKind.Resupply, id = "Resupply", name = "Resupply", icon = "resupply", code = new[] { Arrow.Down, Arrow.Down, Arrow.Up, Arrow.Right },
                    damage = Settings.ResupplyDamage, cooldown = Settings.ResupplyCooldown, indicatorRadius = SupplyIndicator, input = typeof(InputResupply), armed = typeof(ArmedResupply) },
            };

            const string airstrike = "RoR2/Base/Captain/CaptainAirstrikeProjectile1.prefab";
            StrikeProjectile = Assets.CloneProjectile(airstrike, "HelldiverOrbitalStrikeProjectile", Settings.StrikeRadius.Value, Settings.StrikeDelay.Value);
            EagleStrafeProjectile = Assets.CloneProjectile(airstrike, "HelldiverEagleBombProjectile", Settings.EagleRadius.Value, 1.6f);
            EagleBombProjectile = Assets.CloneProjectile(airstrike, "HelldiverEagle500kgProjectile", Settings.BombRadius.Value, Settings.BombDelay.Value);
            EagleBombProjectile.AddComponent<BigExplosionFx>().radius = Settings.BombRadius.Value;
            StrikeProjectile.AddComponent<ImpactSounds>().sounds = new[] { StratagemSounds.MeteorImpact, StratagemSounds.MissileBlast, StratagemSounds.GrenadeBlast };
            EagleStrafeProjectile.AddComponent<ImpactSounds>().sounds = new[] { StratagemSounds.MissileBlast, StratagemSounds.GrenadeBlast };
            EagleBombProjectile.AddComponent<ImpactSounds>().sounds = new[] { StratagemSounds.BigBlast, StratagemSounds.MeteorImpact, StratagemSounds.MissileBlast, StratagemSounds.GrenadeBlast };
            foreach (var d in All) d.beacon = MakeBeacon(d.kind);
        }

        /// <summary>HD2-style thrown beacon: a sticky ball (sticks to the world and to enemies) that calls the stratagem in where it lands.</summary>
        static GameObject MakeBeacon(BeaconKind kind)
        {
            var src = Assets.Load<GameObject>("RoR2/Junk/Commando/CommandoStickyGrenadeProjectile.prefab");
            var p = PrefabAPI.InstantiateClone(src, "HelldiverBeacon" + kind, true);
            var ie = p.GetComponent<ProjectileImpactExplosion>();
            if (ie) UnityEngine.Object.DestroyImmediate(ie);    // the beacon itself never explodes
            var simple = p.GetComponent<ProjectileSimple>();
            simple.desiredForwardSpeed = BeaconSpeed;
            simple.lifetime = 30f;
            var stick = p.GetComponent<ProjectileStickOnImpact>();
            stick.ignoreWorld = false;
            stick.ignoreCharacters = false;
            p.AddComponent<StratagemBeacon>().kind = kind;
            ContentAddition.AddProjectile(p);
            return p;
        }
    }

    /// <summary>
    /// Server-side brain of the thrown beacon: once it sticks (to the world or to an enemy, which it then follows) it waits a moment,
    /// then calls in its stratagem wherever the ball is. If it never sticks it fires after a timeout, so a throw is never wasted.
    /// </summary>
    public class StratagemBeacon : MonoBehaviour
    {
        public BeaconKind kind;
        ProjectileStickOnImpact stick;
        ProjectileController controller;
        ProjectileDamage damage;
        float born, armedAt = -1f;
        bool done;

        void Awake()
        {
            stick = GetComponent<ProjectileStickOnImpact>();
            controller = GetComponent<ProjectileController>();
            damage = GetComponent<ProjectileDamage>();
            born = Time.time;
        }

        void FixedUpdate()
        {
            if (!UnityEngine.Networking.NetworkServer.active || done) return;
            if (armedAt < 0f && stick && stick.stuck)
            {
                armedAt = Time.time;
                Util.PlaySound("Play_captain_shift_start", gameObject);
            }
            if ((armedAt >= 0f && Time.time - armedAt >= Settings.BeaconDelay.Value) || Time.time - born >= 10f) Trigger();
        }

        void Trigger()
        {
            done = true;
            var pos = transform.position;
            var owner = controller ? controller.owner : null;
            if (owner)
            {
                switch (kind)
                {
                    case BeaconKind.OrbitalStrike: Strike(Stratagems.StrikeProjectile, pos, owner, 0f); break;
                    case BeaconKind.EagleBomb: Strike(Stratagems.EagleBombProjectile, pos, owner, 0f); break;
                    case BeaconKind.EagleAirstrike: EagleRun(pos, owner); break;
                    case BeaconKind.Ems: Supply(Assets.EmsDrop, pos, owner.GetComponent<CharacterBody>()); break;
                    case BeaconKind.Resupply: Supply(Assets.ResupplyDrop, pos, owner.GetComponent<CharacterBody>()); break;
                }
            }
            Destroy(gameObject);
        }

        void Strike(GameObject prefab, Vector3 pos, GameObject owner, float fuse)
        {
            ProjectileManager.instance.FireProjectile(new FireProjectileInfo
            {
                crit = damage && damage.crit,
                owner = owner,
                position = pos,
                projectilePrefab = prefab,
                rotation = Quaternion.Euler(0f, UnityEngine.Random.Range(0f, 360f), 0f),
                speedOverride = 0f,
                damage = damage ? damage.damage : 0f,
                damageTypeOverride = new DamageTypeCombo(DamageType.Stun1s, DamageTypeExtended.Generic, DamageSource.Special),
                fuseOverride = fuse <= 0f ? -1f : fuse,
            });
        }

        // two parallel lines of three bombs, running from the thrower towards the beacon
        void EagleRun(Vector3 pos, GameObject owner)
        {
            var dir = pos - owner.transform.position;
            dir.y = 0f;
            if (dir.sqrMagnitude < 1f) { dir = owner.transform.forward; dir.y = 0f; }
            dir.Normalize();
            var side = Vector3.Cross(Vector3.up, dir);
            int n = Stratagems.EagleBombsPerLane;
            for (int lane = 0; lane < 2; lane++)
            {
                float lateral = (lane == 0 ? -0.5f : 0.5f) * Stratagems.EagleLaneGap;
                for (int i = 0; i < n; i++)
                {
                    float along = (i - (n - 1) / 2f) * Stratagems.EagleSpacing;
                    Strike(Stratagems.EagleStrafeProjectile, pos + dir * along + side * lateral, owner, 1.4f + i * 0.2f + lane * 0.05f);
                }
            }
        }

        // Captain's supply drop prefabs, set up like the vanilla state does it, placed on the ground under the beacon
        void Supply(GameObject prefab, Vector3 pos, CharacterBody ownerBody)
        {
            if (!prefab || !ownerBody) return;
            if (Physics.Raycast(pos + Vector3.up * 1f, Vector3.down, out var hit, 300f, LayerIndex.world.mask)) pos = hit.point;
            var obj = Instantiate(prefab, pos, Quaternion.identity);
            obj.GetComponent<TeamFilter>().teamIndex = ownerBody.teamComponent.teamIndex;
            obj.GetComponent<GenericOwnership>().ownerObject = ownerBody.gameObject;
            var dep = obj.GetComponent<Deployable>();
            if (dep && ownerBody.master) ownerBody.master.AddDeployable(dep, DeployableSlot.CaptainSupplyDrop);
            var pd = obj.GetComponent<ProjectileDamage>();
            if (pd)
            {
                pd.crit = damage && damage.crit;
                pd.damage = damage ? damage.damage : 0f;
                pd.damageColorIndex = DamageColorIndex.Default;
                pd.force = 9700f;
                pd.damageType = new DamageTypeCombo(DamageType.Generic, DamageTypeExtended.Generic, DamageSource.Special);
            }
            UnityEngine.Networking.NetworkServer.Spawn(obj);
        }
    }

    /// <summary>Extra, much larger visuals when the 500kg bomb detonates (the vanilla airstrike effect is small).</summary>
    public class BigExplosionFx : MonoBehaviour
    {
        public float radius = 24f;
        static GameObject nova, meteor, omni;
        static bool loaded;

        void OnDestroy()
        {
            if (!UnityEngine.Networking.NetworkServer.active || !gameObject.scene.isLoaded) return;
            if (!loaded)
            {
                loaded = true;
                nova = Assets.Load<GameObject>("RoR2/Base/Vagrant/VagrantNovaExplosion.prefab");
                meteor = Assets.Load<GameObject>("RoR2/Base/Meteor/MeteorStrikeImpact.prefab");
                omni = Assets.Load<GameObject>("RoR2/Base/Common/VFX/OmniExplosionVFX.prefab");
            }
            var pos = transform.position;
            Spawn(nova, pos, radius);
            Spawn(meteor, pos, radius * 0.9f);
            Spawn(omni, pos + Vector3.up * 2f, radius * 1.1f);
            Spawn(omni, pos + Vector3.up * 8f, radius * 0.7f);
        }

        static void Spawn(GameObject prefab, Vector3 pos, float scale)
        {
            if (prefab) EffectManager.SpawnEffect(prefab, new EffectData { origin = pos, scale = scale }, true);
        }
    }
}

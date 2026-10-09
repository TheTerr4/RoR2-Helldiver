#if LAB
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using BepInEx;
using RoR2;
using RoR2.Skills;
using UnityEngine;

namespace HelldiverMod
{
    /// <summary>
    /// Test bridge for the lab copy only: reads commands from BepInEx/hd_cmd.txt so an agent can drive a run without OS input
    /// (take screenshots, start a run, spawn enemies, hold skill buttons, inject arrow keys). Enabled by config [Dev] Bridge.
    /// </summary>
    public partial class DevBridge : MonoBehaviour
    {
        public static readonly Queue<KeyCode> InjectedKeys = new Queue<KeyCode>();
        public static bool Pending(KeyCode k)
        {
            if (InjectedKeys.Count > 0 && InjectedKeys.Peek() == k) { InjectedKeys.Dequeue(); return true; }
            return false;
        }

        readonly bool[] held = new bool[5];
        Vector3? moveOverride; bool sprintHeld, lookActive; float lookYaw, lookPitch, spinRate;
        GameObject camGo; Vector3 camOff; bool camRel; float camLookY = 0.3f;
        GameObject capeDummy; Vector3 capeAway;
        string cmdPath, shotDir;
        float nextPoll;

        void Awake()
        {
            cmdPath = System.IO.Path.Combine(Paths.BepInExRootPath, "hd_cmd.txt");
            shotDir = System.IO.Path.Combine(Paths.BepInExRootPath, "shots");
            Directory.CreateDirectory(shotDir);
            On.RoR2.PlayerCharacterMasterController.FixedUpdate += (orig, self) => { RememberClaims(); orig(self); Inject(); };
            InstallBenchHooks();
        }

        static void Say(string s) { Plugin.Log.LogInfo("[bridge] " + s); }

        /// <summary>Marks monsters the `spawn` command made on purpose, so the no-enemies sweep leaves them alone.</summary>
        class BridgeSpawned : MonoBehaviour { }

        // The lab is a test bench: no director-spawned enemies unless `enemies on` is sent.
        bool noEnemies = true;
        readonly List<GameObject> sweep = new List<GameObject>();

        void SuppressEnemies()
        {
            var dirs = CombatDirector.instancesList;   // the game adds directors while a stage loads: index, do not enumerate
            for (int i = 0; i < dirs.Count; i++) if (dirs[i] && dirs[i].enabled) dirs[i].enabled = false;
            var team = TeamComponent.GetTeamMembers(TeamIndex.Monster);
            if (team == null || team.Count == 0) return;
            sweep.Clear();
            foreach (var tc in team)
            {
                var body = tc ? tc.body : null;
                var master = body ? body.master : null;
                if (master && !master.GetComponent<BridgeSpawned>()) sweep.Add(master.gameObject);
            }
            foreach (var g in sweep)
            {
                var m = g.GetComponent<CharacterMaster>();
                var b = m ? m.GetBody() : null;
                if (b) UnityEngine.Object.Destroy(b.gameObject);
                UnityEngine.Object.Destroy(g);
            }
            if (sweep.Count > 0) Say("removed " + sweep.Count + " director-spawned enemies");
        }

        void Update()
        {
            if (noEnemies && RoR2.Run.instance) SuppressEnemies();
            if (Time.unscaledTime < nextPoll) return;
            nextPoll = Time.unscaledTime + 0.25f;
            if (!File.Exists(cmdPath)) return;
            string[] lines;
            try { lines = File.ReadAllLines(cmdPath); File.Delete(cmdPath); } catch { return; }
            foreach (var line in lines.Select(l => l.Trim()).Where(l => l.Length > 0 && !l.StartsWith("#")))
            {
                try { Run(line); } catch (Exception e) { Say("ERR " + line + " -> " + e); }
            }
        }

        // monsters spawned with "still": the AI turns itself back on when the body starts, so it is switched off and the inputs cleared every tick
        readonly List<CharacterMaster> stillMasters = new List<CharacterMaster>();
        void HoldStill()
        {
            stillMasters.RemoveAll(m => !m);
            foreach (var m in stillMasters)
            {
                foreach (var ai in m.GetComponents<RoR2.CharacterAI.BaseAI>()) if (ai.enabled) ai.SetBaseAIEnabled(false);
                var b = m.GetBody();
                if (!b || !b.inputBank) continue;
                b.inputBank.moveVector = Vector3.zero;
                b.inputBank.skill1.PushState(false); b.inputBank.skill2.PushState(false); b.inputBank.skill3.PushState(false); b.inputBank.skill4.PushState(false);
                b.inputBank.jump.PushState(false); b.inputBank.sprint.PushState(false);
            }
        }

        // The game has just pushed "not held" for this tick (which also drops a claimed press): turn that into "held" as a real key would be, so a held
        // button is one press (justPressed on its first tick only) and keeps its claim; pushing true again made every tick look like a new, unclaimed press.
        readonly bool[] claimed = new bool[5];
        void RememberClaims()
        {
            var body = LocalBody();
            if (!body || !body.inputBank) return;
            var ib = body.inputBank;
            claimed[0] = ib.skill1.hasPressBeenClaimed; claimed[1] = ib.skill2.hasPressBeenClaimed; claimed[2] = ib.skill3.hasPressBeenClaimed;
            claimed[3] = ib.skill4.hasPressBeenClaimed; claimed[4] = ib.interact.hasPressBeenClaimed;
        }

        void Hold(ref InputBankTest.ButtonState b, int i)
        {
            if (!held[i]) return;
            b.hasPressBeenClaimed = b.wasDown && claimed[i];
            b.down = true;
        }

        void Inject()
        {
            if (stillMasters.Count > 0) HoldStill();
            var body = LocalBody();
            if (!body || !body.inputBank) return;
            Hold(ref body.inputBank.skill1, 0);
            Hold(ref body.inputBank.skill2, 1);
            Hold(ref body.inputBank.skill3, 2);
            Hold(ref body.inputBank.skill4, 3);
            Hold(ref body.inputBank.interact, 4);
            if (moveOverride.HasValue) body.inputBank.moveVector = moveOverride.Value;
            if (sprintHeld) body.inputBank.sprint.PushState(true);
            if (lookActive)
            {
                lookYaw += spinRate * Time.fixedDeltaTime;
                body.inputBank.aimDirection = Quaternion.Euler(-lookPitch, lookYaw, 0f) * Vector3.forward;
                PointCamera(body.inputBank.aimDirection);
            }
        }

        // The player camera keeps its own pitch/yaw (from the mouse) and the aim follows it in Update, so a scripted "look" has to turn the camera too,
        // or throws go wherever the camera was left. The per-camera state is private to the camera mode: set through reflection (lab only).
        static FieldInfo camModeData;
        static void PointCamera(Vector3 dir)
        {
            var lu = LocalUserManager.GetFirstLocalUser();
            var rig = lu != null ? lu.cameraRigController : null;
            if (!rig || rig.cameraMode == null) return;
            if (camModeData == null) camModeData = typeof(RoR2.CameraModes.CameraModeBase).GetField("camToRawInstanceData", BindingFlags.NonPublic | BindingFlags.Instance);
            if (!(camModeData?.GetValue(rig.cameraMode) is System.Collections.IDictionary data)) return;
            foreach (var v in data.Values) v?.GetType().GetMethod("SetPitchYawFromLookVector")?.Invoke(v, new object[] { dir });
        }

        void LateUpdate()
        {
            if (!camGo) return;
            var b = LocalBody();
            if (!b) return;
            var off = camOff;
            if (camRel && b.modelLocator && b.modelLocator.modelTransform) off = Quaternion.Euler(0f, b.modelLocator.modelTransform.eulerAngles.y, 0f) * camOff;
            camGo.transform.position = b.transform.position + off;
            camGo.transform.LookAt(b.transform.position + Vector3.up * camLookY);
        }

        System.Collections.IEnumerator Burst(string prefix, int n, float interval)
        {
            for (int i = 0; i < n; i++)
            {
                ScreenCapture.CaptureScreenshot(System.IO.Path.Combine(shotDir, prefix + i.ToString("00") + ".png"));
                yield return new WaitForSecondsRealtime(interval);
            }
            Say("burst done " + prefix);
        }

        System.Collections.IEnumerator Seq(string script)
        {
            foreach (var raw in script.Split(';'))
            {
                var t = raw.Trim();
                if (t.Length == 0) continue;
                // game time: equals real time normally, and stays in step with the frames while "capture" locks the frame rate
                if (t.StartsWith("wait ")) { yield return new WaitForSeconds(float.Parse(t.Substring(5), System.Globalization.CultureInfo.InvariantCulture)); continue; }
                try { Run(t); } catch (Exception e) { Say("ERR seq " + t + " -> " + e.Message); }
            }
            Say("seq done");
        }

        // Frame-locked capture for showcase videos: Time.captureFramerate makes every rendered frame advance game time by exactly 1/fps,
        // so the saved frames play back smoothly however long each one takes to save. Audio is recorded in a separate real-time run.
        bool capturing;
        System.Collections.IEnumerator CaptureFrames(string dir, int fps, int width)
        {
            Directory.CreateDirectory(dir);
            foreach (var f in Directory.GetFiles(dir, "f*.jpg")) File.Delete(f);
            int w = width, h = width * Screen.height / Screen.width;
            var full = new RenderTexture(Screen.width, Screen.height, 0);
            var small = new RenderTexture(w, h, 0);
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            Time.captureFramerate = fps;
            capturing = true;
            int n = 0;
            Say("capture " + dir + " " + fps + " fps " + w + "x" + h);
            while (capturing)
            {
                yield return new WaitForEndOfFrame();
                ScreenCapture.CaptureScreenshotIntoRenderTexture(full);
                Graphics.Blit(full, small);
                var prev = RenderTexture.active;
                RenderTexture.active = small;
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                RenderTexture.active = prev;
                File.WriteAllBytes(System.IO.Path.Combine(dir, "f" + n.ToString("00000") + ".jpg"), tex.EncodeToJPG(94));
                n++;
            }
            Time.captureFramerate = 0;
            Destroy(full); Destroy(small); Destroy(tex);
            Say("capture stopped: " + n + " frames");
        }

        void DumpFx(GameObject g)
        {
            Say("FX " + g.name);
            foreach (var t in g.GetComponentsInChildren<Transform>(true))
            {
                string path = t.name; for (var q = t.parent; q; q = q.parent) path = q.name + "/" + path;
                Say("  " + path + " pos=" + t.localPosition.ToString("F2") + " rot=" + t.localEulerAngles.ToString("F0") + " scale=" + t.localScale.ToString("F2") + " comps=" + string.Join(",", t.GetComponents<Component>().Select(c => c.GetType().Name)));
                var ps = t.GetComponent<ParticleSystem>();
                if (ps)
                {
                    var m = ps.main; var sh = ps.shape; var em = ps.emission;
                    Say("    PS loop=" + m.loop + " dur=" + m.duration + " life=" + m.startLifetime.constantMax + " speed=" + m.startSpeed.constantMax + " size=" + m.startSizeMultiplier + " space=" + m.simulationSpace + " max=" + m.maxParticles + " rate=" + em.rateOverTime.constantMax + " shape=" + (sh.enabled ? sh.shapeType + " angle=" + sh.angle + " radius=" + sh.radius : "off") + " grav=" + m.gravityModifier.constantMax + " color=" + m.startColor.colorMax + " playOnAwake=" + m.playOnAwake + " stopAction=" + m.stopAction + " bursts=" + em.burstCount + (em.burstCount > 0 ? "[" + string.Join(";", Enumerable.Range(0, em.burstCount).Select(bi => { var bu = em.GetBurst(bi); return bu.time + "s x" + bu.count.constantMax; })) + "]" : "") + " renderMode=" + ps.GetComponent<ParticleSystemRenderer>().renderMode + " lenScale=" + ps.GetComponent<ParticleSystemRenderer>().lengthScale + " velScale=" + ps.GetComponent<ParticleSystemRenderer>().velocityScale);
                }
                var r = t.GetComponent<Renderer>();
                if (r) Say("    R " + r.GetType().Name + " mat=" + (r.sharedMaterial ? r.sharedMaterial.name + " shader=" + r.sharedMaterial.shader.name : "null"));
                var l = t.GetComponent<Light>();
                if (l) Say("    Light type=" + l.type + " range=" + l.range + " intensity=" + l.intensity + " color=" + l.color);
            }
        }

        System.Collections.IEnumerator MeasureFps(float seconds)
        {
            int frames = 0; float t0 = Time.unscaledTime, worst = 0f;
            while (Time.unscaledTime - t0 < seconds) { frames++; worst = Mathf.Max(worst, Time.unscaledDeltaTime); yield return null; }
            float el = Time.unscaledTime - t0;
            Say("fps " + (frames / el).ToString("F1") + " avg frame " + (1000f * el / frames).ToString("F2") + " ms, worst " + (worst * 1000f).ToString("F1") + " ms, capes=" + FindObjectsOfType<HelldiverCape>().Count(c => c.enabled));
        }

        static CharacterBody LocalBody()
        {
            var lu = LocalUserManager.GetFirstLocalUser();
            return lu != null && lu.cachedMasterController ? lu.cachedMasterController.master?.GetBody() : null;
        }

        void Run(string line)
        {
            var p = line.Split(new[] { ' ' }, 2);
            string cmd = p[0].ToLowerInvariant(), arg = p.Length > 1 ? p[1] : "";
            switch (cmd)
            {
                case "shot4":
                    ScreenCapture.CaptureScreenshot(System.IO.Path.Combine(shotDir, arg + ".png"), 3);
                    Say("shot4 " + arg);
                    break;
                case "shot":
                    ScreenCapture.CaptureScreenshot(System.IO.Path.Combine(shotDir, arg + ".png"));
                    Say("shot " + arg);
                    break;
                case "console":
                    RoR2.Console.instance.SubmitCmd(null, arg);
                    Say("console " + arg);
                    break;
                case "survivor":
                {
                    var def = SurvivorCatalog.allSurvivorDefs.First(s => s.cachedName == (arg.Length > 0 ? arg : "Helldiver"));
                    LocalUserManager.GetFirstLocalUser().userProfile.SetSurvivorPreference(def);
                    Say("survivor " + def.cachedName);
                    break;
                }
                case "scene": Say("scene " + UnityEngine.SceneManagement.SceneManager.GetActiveScene().name); break;
                case "skill":
                {
                    var a = arg.Split(' ');
                    held[int.Parse(a[0]) - 1] = a[1] == "down";
                    break;
                }
                case "key":
                    InjectedKeys.Enqueue((KeyCode)Enum.Parse(typeof(KeyCode), arg + "Arrow", true));
                    break;
                case "spawn":
                {
                    var a = arg.Split(' ');
                    var body = LocalBody();
                    var master = MasterCatalog.FindMasterPrefab(a[0]);
                    int n = a.Length > 1 ? int.Parse(a[1]) : 1;
                    float dist = a.Length > 2 ? float.Parse(a[2]) : 18f;
                    bool still = a.Length > 3 && a[3] == "still";      // "still": AI off, standing in a group of rows of three (targets for stratagems)
                    var fwd = body.inputBank.aimDirection; fwd.y = 0f; fwd.Normalize();
                    var side = Vector3.Cross(Vector3.up, fwd);
                    for (int i = 0; i < n; i++)
                    {
                        var pos = body.transform.position + fwd * dist + Vector3.up * 1f + (still ? side * ((i % 3) - 1) * 2.5f + fwd * (i / 3) * 2.5f : side * ((i - (n - 1) / 2f) * 3f));
                        var sm = new MasterSummon { masterPrefab = master, position = pos, rotation = Quaternion.LookRotation(-fwd), summonerBodyObject = null, teamIndexOverride = TeamIndex.Monster, ignoreTeamMemberLimit = true }.Perform();
                        if (!sm) continue;
                        sm.gameObject.AddComponent<BridgeSpawned>();
                        if (still) stillMasters.Add(sm);
                    }
                    Say("spawned " + n + " " + a[0]);
                    break;
                }
                case "beacons":     // live stratagem beacons: position, stuck, age
                    foreach (var bc in FindObjectsOfType<StratagemBeacon>())
                    {
                        var st = bc.GetComponent<RoR2.Projectile.ProjectileStickOnImpact>();
                        var rb = bc.GetComponent<Rigidbody>();
                        Say("beacon " + bc.kind + " pos=" + bc.transform.position.ToString("F1") + " stuck=" + (st && st.stuck) + " vel=" + (rb ? rb.velocity.ToString("F1") : "-") + " body=" + LocalBody().transform.position.ToString("F1"));
                    }
                    break;
                case "dumpsound":   // sound events wired into our stratagem prefabs (components, ghosts, explosion effects) and Captain's state sounds
                {
                    void Scan(string label, GameObject g, int depth)
                    {
                        if (!g || depth > 2) return;
                        foreach (var c in g.GetComponentsInChildren<Component>(true))
                        {
                            if (!c) continue;
                            foreach (var f in c.GetType().GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                            {
                                object v; try { v = f.GetValue(c); } catch { continue; }
                                if (v is string str && (str.StartsWith("Play_") || str.StartsWith("Stop_"))) Say("  " + label + " " + c.GetType().Name + "." + f.Name + " = " + str);
                                else if (v is NetworkSoundEventDef nse && nse) Say("  " + label + " " + c.GetType().Name + "." + f.Name + " = " + nse.eventName);
                                else if (v is GameObject sub && sub && depth < 2 && (f.Name.ToLower().Contains("effect") || f.Name.ToLower().Contains("ghost"))) Scan(label + ">" + f.Name, sub, depth + 1);
                            }
                        }
                    }
                    Scan("strike", Stratagems.StrikeProjectile, 0);
                    Scan("eagle", Stratagems.EagleStrafeProjectile, 0);
                    Scan("bomb", Stratagems.EagleBombProjectile, 0);
                    Scan("ems", Assets.EmsDrop, 0);
                    Scan("resupply", Assets.ResupplyDrop, 0);
                    Scan("beacon", Stratagems.All[0].beacon, 0);
                    foreach (var t in new[] { typeof(EntityStates.Captain.Weapon.CallAirstrikeBase), typeof(EntityStates.Captain.Weapon.SetupAirstrike), typeof(EntityStates.Captain.Weapon.CallAirstrike1), typeof(EntityStates.Captain.Weapon.CallAirstrikeAlt), typeof(EntityStates.Captain.Weapon.CallSupplyDropBase), typeof(EntityStates.Captain.Weapon.SetupSupplyDrop) })
                        foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Static))
                            if (f.FieldType == typeof(string)) Say("  state " + t.Name + "." + f.Name + " = " + f.GetValue(null));
                    Say("dumpsound done");
                    break;
                }
                case "findsound":   // findsound <text>: sound events (effect spawn sounds and entity state configs) whose name contains the text
                {
                    var hits = new SortedSet<string>();
                    for (int i = 0; i < EffectCatalog.effectCount; i++)
                    {
                        var def = EffectCatalog.GetEffectDef((EffectIndex)i);
                        var sn = def != null ? def.spawnSoundEventName : null;
                        if (!string.IsNullOrEmpty(sn) && sn.IndexOf(arg, StringComparison.OrdinalIgnoreCase) >= 0) hits.Add(sn + "   (effect " + (def.prefab ? def.prefab.name : "?") + ")");
                    }
                    foreach (var cfg in Resources.FindObjectsOfTypeAll<EntityStateConfiguration>())
                    {
                        var coll = cfg.serializedFieldsCollection;
                        var arr = coll.GetType().GetField("serializedFields")?.GetValue(coll) as Array;
                        if (arr == null) continue;
                        foreach (var sf in arr)
                        {
                            var name = sf.GetType().GetField("fieldName")?.GetValue(sf) as string;
                            var val = sf.GetType().GetField("fieldValue")?.GetValue(sf);
                            var str = val?.GetType().GetField("stringValue")?.GetValue(val) as string;
                            if (str != null && (str.StartsWith("Play_") || str.StartsWith("play_")) && str.IndexOf(arg, StringComparison.OrdinalIgnoreCase) >= 0) hits.Add(str + "   (" + cfg.name + "." + name + ")");
                        }
                    }
                    Say("findsound " + arg + ": " + hits.Count);
                    foreach (var h in hits.Take(120)) Say("  snd " + h);
                    break;
                }
                case "soundat":     // soundat <event> <dist>: a sound at a point that far ahead (like a stratagem impact)
                {
                    var a2 = arg.Split(' ');
                    var b = LocalBody(); var f = b.inputBank.aimDirection; f.y = 0f; f.Normalize();
                    var id = RoR2.Audio.PointSoundManager.EmitSoundLocal((RoR2.Audio.AkEventIdArg)a2[0], b.footPosition + f * float.Parse(a2[1], System.Globalization.CultureInfo.InvariantCulture));
                    Say("soundat " + arg + " id=" + id);
                    break;
                }
                case "effectat":    // effectat <effect prefab name> <dist> [scale]: spawn a catalogued effect that far ahead (does its own sound play?)
                {
                    var a2 = arg.Split(' ');
                    var b = LocalBody(); var f = b.inputBank.aimDirection; f.y = 0f; f.Normalize();
                    var idx = EffectCatalog.FindEffectIndexFromPrefab(Enumerable.Range(0, EffectCatalog.effectCount).Select(i => EffectCatalog.GetEffectDef((EffectIndex)i)).FirstOrDefault(d => d != null && d.prefab && d.prefab.name == a2[0])?.prefab);
                    if (idx == EffectIndex.Invalid) { Say("effectat: no effect " + a2[0]); break; }
                    EffectManager.SpawnEffect(idx, new EffectData { origin = b.footPosition + f * float.Parse(a2[1], System.Globalization.CultureInfo.InvariantCulture), scale = a2.Length > 2 ? float.Parse(a2[2], System.Globalization.CultureInfo.InvariantCulture) : 1f }, true);
                    Say("effectat " + arg);
                    break;
                }
                case "projinfo":    // projinfo <projectile prefab name>: when and how an exploding projectile goes off (fuse, impact, enemy contact)
                {
                    var pp = ProjectileCatalog.GetProjectilePrefab(ProjectileCatalog.FindProjectileIndex(arg));
                    var ie = pp ? pp.GetComponent<RoR2.Projectile.ProjectileImpactExplosion>() : null;
                    if (!ie) { Say("projinfo: no " + arg); break; }
                    Say("projinfo " + arg + " lifetime=" + ie.lifetime + " timerAfterImpact=" + ie.timerAfterImpact + " lifetimeAfterImpact=" + ie.lifetimeAfterImpact + " destroyOnEnemy=" + ie.destroyOnEnemy + " destroyOnWorld=" + ie.destroyOnWorld + " explodeOnLifeTimeExpiration=" + ie.explodeOnLifeTimeExpiration + " radius=" + ie.blastRadius);
                    break;
                }
                case "killall":     // remove every monster (no death effects), e.g. between showcase shots
                {
                    var team = TeamComponent.GetTeamMembers(TeamIndex.Monster).ToArray();
                    foreach (var tc in team)
                    {
                        var b = tc ? tc.body : null;
                        if (b && b.master) Destroy(b.master.gameObject);
                        if (b) Destroy(b.gameObject);
                    }
                    Say("killall " + team.Length);
                    break;
                }
                case "status":
                {
                    var b = LocalBody();
                    if (!b) { Say("status: no body"); break; }
                    var sl = b.skillLocator;
                    string Sk(GenericSkill g) => g ? (g.skillNameToken + " stock=" + g.stock + "/" + g.maxStock + " cd=" + g.cooldownRemaining.ToString("0.0")) : "-";
                    Say($"status body={b.name} hp={b.healthComponent.health:0}/{b.healthComponent.fullHealth:0} armor={b.armor} dmg={b.damage} | P:{Sk(sl.primary)} | S:{Sk(sl.secondary)} | U:{Sk(sl.utility)} | R:{Sk(sl.special)}");
                    var am = b.GetComponent<States.HelldiverAmmo>(); Say("ammo lib=" + am.liberator + " brk=" + am.breaker + " t=" + Time.time.ToString("0.000")); var mo = b.characterMotor; Say("motor grounded=" + (mo ? mo.isGrounded.ToString() : "-") + " vy=" + (mo ? mo.velocity.y.ToString("0.0") : "-") + " y=" + b.transform.position.y.ToString("0.0")); Say("states: " + string.Join(", ", b.GetComponents<EntityStateMachine>().Select(m => m.customName + "=" + m.state.GetType().Name)));
                    break;
                }
                case "fps":
                    StartCoroutine(MeasureFps(arg.Length > 0 ? float.Parse(arg) : 4f));
                    break;
                case "hide":    // hide renderers (e.g. an item display) whose name contains the text, to look at what is behind them
                {
                    int n = 0;
                    foreach (var r in LocalBody().modelLocator.modelTransform.GetComponentsInChildren<Renderer>(true))
                        if (r.transform.parent && r.transform.parent.name.Contains(arg) || r.name.Contains(arg)) { r.enabled = false; n++; }
                    Say("hid " + n + " renderers matching " + arg);
                    break;
                }
                case "dumpfx":      // hierarchy, particle systems, renderers and lights of an addressable prefab; "jet" = the vanilla dodge's jetEffect
                {
                    var g = arg == "jet" ? EntityStates.Commando.DodgeState.jetEffect : Assets.Load<GameObject>(arg);
                    if (!g) { Say("dumpfx: nothing for " + arg); break; }
                    DumpFx(g);
                    break;
                }
                case "findfx":      // addressable keys containing the text; "mat:text" / "tex:text" look for .mat / .png instead of prefabs
                {
                    string ext = ".prefab", needle = arg;
                    if (arg.StartsWith("mat:")) { ext = ".mat"; needle = arg.Substring(4); } else if (arg.StartsWith("tex:")) { ext = ".png"; needle = arg.Substring(4); }
                    var keys = new List<string>();
                    foreach (var loc in UnityEngine.AddressableAssets.Addressables.ResourceLocators)
                        foreach (var k in loc.Keys) { var ks = k as string; if (ks != null && ks.EndsWith(ext, StringComparison.OrdinalIgnoreCase) && ks.IndexOf(needle, StringComparison.OrdinalIgnoreCase) >= 0) keys.Add(ks); }
                    var uniq = keys.Distinct().OrderBy(x => x).ToList();
                    Say("findfx " + arg + ": " + uniq.Count + " keys");
                    foreach (var k in uniq.Take(90)) Say("  key " + k);
                    break;
                }
                case "seq":         // "cmd; cmd; wait 0.7; cmd" runs the commands with real-time waits in between (no file races)
                    StartCoroutine(Seq(arg));
                    break;
                case "lobbyspin":   // turn the character select display model around (it only shows its front)
                    foreach (var pk in FindObjectsOfType<HelldiverPack>())
                        if (pk.model && !pk.model.body) { pk.model.transform.Rotate(0f, float.Parse(arg), 0f, Space.World); Say("lobbyspin " + arg + " on " + pk.model.name); }
                    break;
                case "capetest":    // capetest spawn | away | info: a second Helldiver body (no master) in view, then far behind the camera: does its cape go with it?
                {
                    var b = LocalBody();
                    var fwd = b.inputBank.aimDirection; fwd.y = 0f; fwd.Normalize();
                    if (arg == "spawn") { if (capeDummy) Destroy(capeDummy); capeDummy = Instantiate(Survivor.Body, b.transform.position + fwd * 6f + Vector3.up, Quaternion.LookRotation(fwd)); UnityEngine.Networking.NetworkServer.Spawn(capeDummy); capeAway = fwd * 60f; }
                    else if (arg == "away" && capeDummy) TeleportHelper.TeleportBody(capeDummy.GetComponent<CharacterBody>(), capeDummy.transform.position - capeAway * 2f);    // far behind the camera
                    var ml = capeDummy ? capeDummy.GetComponent<ModelLocator>() : null;
                    var cape = ml && ml.modelTransform ? ml.modelTransform.GetComponent<HelldiverCape>() : null;
                    var cr = cape ? cape.LabRenderer : null;
                    if (!cr || !cape.LabBody) { Say("capetest " + arg + ": no cape yet (component=" + (bool)cape + " renderer=" + (bool)cr + " body=" + (cape && cape.LabBody) + " dummyAt=" + (capeDummy ? capeDummy.transform.position.ToString("F1") : "-") + ")"); break; }
                    Say("capetest " + arg + " capeToBody=" + Vector3.Distance(cr.bounds.center, cape.LabBody.bounds.center).ToString("F2") + " bodyVisible=" + cape.LabBody.isVisible + " capeVisible=" + cr.isVisible + " capeActive=" + cr.gameObject.activeInHierarchy);
                    break;
                }
                case "lobbyinfo":   // every Helldiver model: whose loadout it follows (display models in the lobby), weapon and pack shown
                    foreach (var hv in FindObjectsOfType<HelldiverVisuals>()) Say("lobbyinfo " + hv.Diagnostics());
                    break;
                case "packinfo":
                    foreach (var pk in FindObjectsOfType<HelldiverPack>())
                    {
                        var rs = pk.GetComponentsInChildren<Renderer>(true);
                        var chest = pk.transform;
                        Say("pack equipped=" + pk.equipped + " ready=" + pk.Ready);
                        var t = pk.model ? pk.model.GetComponentsInChildren<Transform>(true) : new Transform[0];
                        foreach (var tt in t) if (tt.name == "HD_JumpPack" || tt.name.StartsWith("HD_Thruster")) Say("  " + tt.name + " active=" + tt.gameObject.activeInHierarchy + " world=" + tt.position.ToString("F2") + " fwd=" + tt.forward.ToString("F2") + " parent=" + (tt.parent ? tt.parent.name : "-"));
                    }
                    break;
                case "capture":     // capture <dir> [fps] [width] | capture stop
                {
                    if (arg == "stop") { capturing = false; break; }
                    var cp = arg.Split(' ');
                    StartCoroutine(CaptureFrames(cp[0], cp.Length > 1 ? int.Parse(cp[1]) : 30, cp.Length > 2 ? int.Parse(cp[2]) : 1920));
                    break;
                }
                case "sound":       // sound <wwise event>: e.g. a sync marker for audio recorded in a separate run
                    Util.PlaySound(arg, LocalBody().gameObject);
                    Say("sound " + arg);
                    break;
                case "fpscap":
                    QualitySettings.vSyncCount = 0; Application.targetFrameRate = int.Parse(arg);
                    Say("fpscap " + arg);
                    break;
                case "cape":
                    foreach (var c in FindObjectsOfType<HelldiverCape>()) c.enabled = arg != "off";
                    Say("cape " + (arg != "off"));
                    break;
                case "enemies":
                    noEnemies = arg == "off";
                    if (!noEnemies) foreach (var d in CombatDirector.instancesList) d.enabled = true;
                    Say("enemies " + (noEnemies ? "suppressed" : "allowed"));
                    break;
                case "buff":        // buff <name> <seconds>: buff def names, e.g. bdCloak, bdImmune (to check that the weapon, pack and cape follow the body's look)
                {
                    var a = arg.Split(' ');
                    var bi = BuffCatalog.FindBuffIndex(a[0]); if (bi == BuffIndex.None) bi = BuffCatalog.FindBuffIndex("bd" + a[0]);
                    if (bi == BuffIndex.None) { Say("buff: no " + a[0]); break; }
                    LocalBody().AddTimedBuff(bi, a.Length > 1 ? float.Parse(a[1], System.Globalization.CultureInfo.InvariantCulture) : 5f);
                    Say("buff " + arg);
                    break;
                }
                case "god":
                    LocalBody().healthComponent.godMode = arg != "off";
                    Say("god " + (arg != "off"));
                    break;
                case "skilldef":
                {
                    var a = arg.Split(' ');
                    var b = LocalBody();
                    var slot = b.GetComponents<GenericSkill>()[int.Parse(a[0])];
                    var def = SkillCatalog.allSkillDefs.First(d => d.skillName == a[1]);
                    slot.SetBaseSkill(def);
                    slot.Reset();
                    Say("skilldef " + a[1]);
                    break;
                }
                case "tptele":
                {
                    var b = LocalBody();
                    var t = TeleporterInteraction.instance;
                    float off = arg.Length > 0 ? float.Parse(arg) : 14f;
                    TeleportHelper.TeleportBody(b, t.transform.position + new Vector3(0f, 1.5f, 0f) + t.transform.right * off);
                    Say("tptele");
                    break;
                }
                case "tpabs":       // tpabs x y z: a fixed spot on the current stage (benchmarks); "pos" prints where the body is
                {
                    var v = arg.Split(' ').Select(x => float.Parse(x, System.Globalization.CultureInfo.InvariantCulture)).ToArray();
                    TeleportHelper.TeleportBody(LocalBody(), new Vector3(v[0], v[1], v[2]));
                    Say("tpabs " + arg);
                    break;
                }
                case "pos":
                    Say("pos " + LocalBody().footPosition.ToString("F1") + " yaw " + LocalBody().modelLocator.modelTransform.eulerAngles.y.ToString("F0"));
                    break;
                case "tpup":
                {
                    var b = LocalBody();
                    TeleportHelper.TeleportBody(b, b.transform.position + Vector3.up * float.Parse(arg));
                    Say("tpup " + arg);
                    break;
                }
                case "dumpgo":
                {
                    var g = Assets.Load<GameObject>(arg);
                    Say("GO " + arg + ": " + string.Join(", ", g.GetComponents<Component>().Select(c => c.GetType().Name)));
                    var ie = g.GetComponent<RoR2.Projectile.ProjectileImpactExplosion>();
                    if (ie) Say($"  IE radius={ie.blastRadius} lifetime={ie.lifetime} destroyOnWorld={ie.destroyOnWorld} destroyOnEnemy={ie.destroyOnEnemy} impactOnWorld={ie.impactOnWorld} timerAfterImpact={ie.timerAfterImpact} lifetimeAfterImpact={ie.lifetimeAfterImpact}");
                    var st = g.GetComponent<RoR2.Projectile.ProjectileStickOnImpact>();
                    if (st) Say($"  Stick ignoreCharacters={st.ignoreCharacters} ignoreWorld={st.ignoreWorld} align={st.alignNormals}");
                    var ps = g.GetComponent<RoR2.Projectile.ProjectileSimple>();
                    if (ps) Say($"  Simple vel={ps.desiredForwardSpeed} lifetime={ps.lifetime}");
                    var rb = g.GetComponent<Rigidbody>();
                    if (rb) Say($"  RB gravity={rb.useGravity} mass={rb.mass}");
                    break;
                }
                case "dumpskel":
                {
                    var body = Assets.Load<GameObject>(arg.Length > 0 ? arg : "RoR2/Base/Commando/mdlCommandoDualies.fbx");
                    var sb = new System.Text.StringBuilder();
                    sb.AppendLine("{\"renderers\":[");
                    var rs = body.GetComponentsInChildren<SkinnedMeshRenderer>(true);
                    for (int r = 0; r < rs.Length; r++)
                    {
                        var rend = rs[r];
                        var mesh = rend.sharedMesh;
                        sb.Append("{\"name\":\"" + rend.name + "\",\"mesh\":\"" + (mesh ? mesh.name : "") + "\",\"materials\":[" + string.Join(",", rend.sharedMaterials.Select(m => "\"" + (m ? m.name + "|" + m.shader.name : "null") + "\"")) + "],");
                        sb.Append("\"verts\":" + (mesh ? mesh.vertexCount : 0) + ",\"bounds\":\"" + (mesh ? mesh.bounds.ToString("F3") : "") + "\",\"rootBone\":\"" + (rend.rootBone ? rend.rootBone.name : "") + "\",\"bones\":[");
                        var bones = rend.bones;
                        var bind = mesh ? mesh.bindposes : new Matrix4x4[0];
                        for (int i = 0; i < bones.Length; i++)
                        {
                            var m = bind.Length > i ? bind[i].inverse : Matrix4x4.identity;
                            var pos = m.GetColumn(3);
                            var fwd = m.MultiplyVector(Vector3.forward); var up = m.MultiplyVector(Vector3.up);
                            sb.Append("{\"i\":" + i + ",\"name\":\"" + (bones[i] ? bones[i].name : "null") + "\",\"parent\":\"" + (bones[i] && bones[i].parent ? bones[i].parent.name : "") + "\",\"pos\":[" + pos.x.ToString("F5") + "," + pos.y.ToString("F5") + "," + pos.z.ToString("F5") + "],\"fwd\":[" + fwd.x.ToString("F4") + "," + fwd.y.ToString("F4") + "," + fwd.z.ToString("F4") + "],\"up\":[" + up.x.ToString("F4") + "," + up.y.ToString("F4") + "," + up.z.ToString("F4") + "]}" + (i < bones.Length - 1 ? "," : ""));
                        }
                        sb.AppendLine("]}" + (r < rs.Length - 1 ? "," : ""));
                    }
                    sb.AppendLine("]}");
                    System.IO.File.WriteAllText(System.IO.Path.Combine(Paths.BepInExRootPath, "skel.json"), sb.ToString());
                    var vm = rs.Select(x => x.sharedMesh).FirstOrDefault(m => m);
                    if (vm)
                    {
                        var vs = vm.vertices; var bw = vm.boneWeights;
                        var vb = new System.Text.StringBuilder();
                        for (int i = 0; i < vs.Length; i++) vb.AppendLine(vs[i].x.ToString("F4") + " " + vs[i].y.ToString("F4") + " " + vs[i].z.ToString("F4") + " " + bw[i].boneIndex0 + " " + bw[i].weight0.ToString("F3"));
                        System.IO.File.WriteAllText(System.IO.Path.Combine(Paths.BepInExRootPath, "skelverts.txt"), vb.ToString());
                    }
                    Say("dumpskel " + rs.Length + " renderers");
                    break;
                }
                case "dumpgun":
                {
                    var b = LocalBody();
                    var sbd = new System.Text.StringBuilder();
                    foreach (var t in b.modelLocator.modelTransform.GetComponentsInChildren<Transform>(true))
                    {
                        if (!(t.name.StartsWith("GunMesh") || t.name.StartsWith("Muzzle") || t.name.StartsWith("HD_") || t.name.StartsWith("gun.") || t.name == "hand.r" || t.name == "hand.l")) continue;
                        var mf = t.GetComponent<MeshFilter>(); var mr = t.GetComponent<MeshRenderer>();
                        var chain = ""; for (var q = t; q && q != b.modelLocator.modelTransform; q = q.parent) chain = q.name + "/" + chain;
                        sbd.AppendLine("aim=" + b.inputBank.aimDirection.ToString("F3") + " bodyfwd=" + b.modelLocator.modelTransform.forward.ToString("F3")); sbd.AppendLine(t.name + " path=" + chain + " lpos=" + t.localPosition.ToString("F4") + " lrot=" + t.localEulerAngles.ToString("F1") + " lscale=" + t.localScale.ToString("F3") + " wpos=" + t.position.ToString("F3") + " wfwd=" + t.forward.ToString("F3") + " wup=" + t.up.ToString("F3") + (mf && mf.sharedMesh ? " meshBounds=" + mf.sharedMesh.bounds.ToString("F3") + " verts=" + mf.sharedMesh.vertexCount : ""));
                    }
                    System.IO.File.WriteAllText(System.IO.Path.Combine(Paths.BepInExRootPath, "gunfo.txt"), sbd.ToString());
                    Say("dumpgun done");
                    break;
                }
                case "cam":
                {
                    if (camGo) Destroy(camGo);
                    camGo = null;
                    if (arg == "off") { Say("cam off"); break; }
                    var cp = arg.Split(' ');
                    camOff = new Vector3(float.Parse(cp[0], System.Globalization.CultureInfo.InvariantCulture), float.Parse(cp[1], System.Globalization.CultureInfo.InvariantCulture), float.Parse(cp[2], System.Globalization.CultureInfo.InvariantCulture));
                    camRel = cp.Length > 3 && cp[3] == "m";
                    camLookY = cp.Length > 4 ? float.Parse(cp[4], System.Globalization.CultureInfo.InvariantCulture) : 0.3f;
                    camGo = new GameObject("HD_DebugCam");
                    var cc = camGo.AddComponent<Camera>();
                    cc.depth = 100; cc.fieldOfView = camRel ? 30f : 45f; cc.nearClipPlane = 0.05f;
                    Say("cam " + arg + " (world offsets, follows the body)");
                    break;
                }
                case "move":
                {
                    if (arg == "off") { moveOverride = null; sprintHeld = false; Say("move off"); break; }
                    var mp = arg.Split(' ');
                    moveOverride = new Vector3(float.Parse(mp[0], System.Globalization.CultureInfo.InvariantCulture), 0f, float.Parse(mp[1], System.Globalization.CultureInfo.InvariantCulture)).normalized;
                    sprintHeld = mp.Length > 2 && mp[2] == "sprint";
                    Say("move " + arg);
                    break;
                }
                case "look":
                {
                    if (arg == "off") { lookActive = false; spinRate = 0f; Say("look off"); break; }
                    var lp = arg.Split(' ');
                    lookYaw = float.Parse(lp[0], System.Globalization.CultureInfo.InvariantCulture);
                    lookPitch = float.Parse(lp[1], System.Globalization.CultureInfo.InvariantCulture);
                    spinRate = lp.Length > 2 ? float.Parse(lp[2], System.Globalization.CultureInfo.InvariantCulture) : 0f;
                    lookActive = true;
                    Say("look " + arg);
                    break;
                }
                case "burst":
                {
                    var bp = arg.Split(' ');
                    StartCoroutine(Burst(bp[0], int.Parse(bp[1]), float.Parse(bp[2], System.Globalization.CultureInfo.InvariantCulture)));
                    break;
                }
                case "setvariant":
                {
                    var vp = arg.Split(' ');
                    var prof = LocalUserManager.GetFirstLocalUser().userProfile;
                    var ld = Loadout.RequestInstance();
                    prof.CopyLoadout(ld);
                    ld.bodyLoadoutManager.SetSkillVariant(BodyCatalog.FindBodyIndex("HelldiverBody"), int.Parse(vp[0]), uint.Parse(vp[1]));
                    prof.SetLoadout(ld);
                    Loadout.ReturnInstance(ld);
                    Say("setvariant " + arg);
                    break;
                }
                case "dumprend":
                {
                    var b = LocalBody();
                    var sbr = new System.Text.StringBuilder();
                    foreach (var r in b.modelLocator.modelTransform.GetComponentsInChildren<Renderer>(true))
                    {
                        var chain = ""; for (var q = r.transform; q && q != b.modelLocator.modelTransform; q = q.parent) chain = q.name + "/" + chain;
                        var mf = r.GetComponent<MeshFilter>(); var smr = r as SkinnedMeshRenderer;
                        sbr.AppendLine(r.GetType().Name + " " + chain + " enabled=" + r.enabled + " active=" + r.gameObject.activeInHierarchy + " bounds=" + r.bounds.center.ToString("F2") + "/" + r.bounds.size.ToString("F2") + " mesh=" + (smr ? (smr.sharedMesh ? smr.sharedMesh.name + ":" + smr.sharedMesh.vertexCount : "none") : (mf && mf.sharedMesh ? mf.sharedMesh.name : "")) + " mat=" + (r.sharedMaterial ? r.sharedMaterial.name : "null"));
                    }
                    System.IO.File.WriteAllText(System.IO.Path.Combine(Paths.BepInExRootPath, "renderers.txt"), sbr.ToString());
                    Say("dumprend done");
                    break;
                }
                case "gripset":
                {
                    var parts = arg.Split(' ');
                    var flags = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static;
                    var fld = typeof(HelldiverGrip).GetField(parts[0], flags) ?? typeof(HelldiverCape).GetField(parts[0], flags);
                    if (fld == null || parts.Length < 2) { Say("gripset: unknown field " + parts[0]); break; }
                    var num = float.Parse(parts[1], System.Globalization.CultureInfo.InvariantCulture);
                    if (fld.FieldType == typeof(int)) fld.SetValue(null, (int)num); else if (fld.FieldType == typeof(bool)) fld.SetValue(null, num != 0f); else fld.SetValue(null, num);
                    Say("gripset " + parts[0] + "=" + fld.GetValue(null));
                    break;
                }
                case "capeinfo":
                {
                    foreach (var c in FindObjectsOfType<HelldiverCape>()) Say("cape " + c.GetType().GetMethod("Diagnostics")?.Invoke(c, null));
                    break;
                }
                case "gripinfo":
                {
                    foreach (var g in FindObjectsOfType<HelldiverGrip>()) Say("grip errR=" + g.errR.ToString("F3") + " errL=" + g.errL.ToString("F3") + " index=" + g.index + " twistR=" + g.twistR.ToString("F0") + " swingR=" + g.swingR.ToString("F0") + " twistL=" + g.twistL.ToString("F0") + " swingL=" + g.swingL.ToString("F0") + " rootPos=" + g.root.position.ToString("F2"));
                    break;
                }
                case "bench":       // scripted performance benchmark (DevBench.cs): idle, firing, sprinting, crowd of 12 extra Helldivers
                    StartCoroutine(Bench(arg.Length > 0 ? arg : "run"));
                    break;
                case "stage":       // go to a given stage (scene name, e.g. golemplains) so benchmarks and screenshots run in the same place
                {
                    var sd = SceneCatalog.FindSceneDef(arg);
                    if (!sd || !RoR2.Run.instance) { Say("stage: no scene " + arg); break; }
                    RoR2.Run.instance.AdvanceStage(sd);
                    Say("stage " + arg);
                    break;
                }
                default: Say("unknown command " + cmd); break;
            }
        }
    }
}
#endif

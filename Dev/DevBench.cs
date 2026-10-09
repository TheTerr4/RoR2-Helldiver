#if LAB
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Text;
using BepInEx;
using MonoMod.RuntimeDetour;
using RoR2;
using RoR2.Skills;
using UnityEngine;
using UnityEngine.Profiling;

namespace HelldiverMod
{
    /// <summary>
    /// Lab benchmark ("bench [label]"): times the mod's own per-frame code (detours on its Update/LateUpdate/OnGUI methods) and its one-off loading,
    /// and measures frame times in four scripted scenes: idle, firing the primary, sprinting in circles, and 12 extra Helldivers on screen.
    /// Results go to the log and to BepInEx/bench_[label].txt. Uncaps the frame rate while it runs.
    /// </summary>
    public partial class DevBridge
    {
        static readonly List<string> hookNames = new List<string>();
        static readonly List<Hook> hooks = new List<Hook>();
        static long[] hookTicks = new long[32], hookCalls = new long[32];
        static readonly List<string> loadLog = new List<string>();
        const BindingFlags All = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;

        static double Ms(long ticks) => ticks * 1000.0 / Stopwatch.Frequency;

        // per-frame code: an instance method without arguments
        static void Frame<T>(string method)
        {
            var mi = typeof(T).GetMethod(method, All, null, Type.EmptyTypes, null);
            if (mi == null) { Say("bench: no " + typeof(T).Name + "." + method); return; }
            int slot = hookNames.Count;
            hookNames.Add(typeof(T).Name + "." + method);
            hooks.Add(new Hook(mi, new Action<Action<T>, T>((orig, self) =>
            {
                long t0 = Stopwatch.GetTimestamp();
                orig(self);
                hookTicks[slot] += Stopwatch.GetTimestamp() - t0; hookCalls[slot]++;
            })));
        }

        // one-off loading: log how long each call took
        static Type Mod(string name) => typeof(DevBridge).Assembly.GetType("HelldiverMod." + name);

        static void Load(Type t, string method, Delegate detour)
        {
            var mi = t != null ? t.GetMethod(method, All) : null;
            if (mi == null) return;
            try { hooks.Add(new Hook(mi, detour)); } catch (Exception e) { Say("bench: " + t.Name + "." + method + " not hooked: " + e.Message); }
        }
        static void LoadDone(string what, long t0) { var s = what + " " + Ms(Stopwatch.GetTimestamp() - t0).ToString("F1") + " ms"; loadLog.Add(s); Say("[load] " + s); }

        void InstallBenchHooks()
        {
            try
            {
                // by name, so the same bench builds against older versions of the mod (A/B runs); missing ones are skipped
                foreach (var tm in new[] { "HelldiverVisuals.LateUpdate", "HelldiverVisuals.Update", "HelldiverGrip.LateUpdate", "HelldiverCape.LateUpdate", "HelldiverPack.LateUpdate", "HelldiverHud.OnGUI", "StratagemHud.OnGUI" })
                {
                    var t = Mod(tm.Split('.')[0]);
                    if (t != null) typeof(DevBridge).GetMethod("Frame", All).MakeGenericMethod(t).Invoke(null, new object[] { tm.Split('.')[1] });
                }
                Load(Mod("HelldiverModel"), "Build", new Action<Action<SkinnedMeshRenderer>, SkinnedMeshRenderer>((orig, r) => { long t0 = Stopwatch.GetTimestamp(); orig(r); LoadDone("body model", t0); }));
                Load(Mod("WeaponModels"), "Load", new Action<Action<Material>, Material>((orig, m) => { long t0 = Stopwatch.GetTimestamp(); orig(m); LoadDone("weapon models", t0); }));
                Load(Mod("HelldiverWeapons"), "Load", new Action<Action<string, Material>, string, Material>((orig, d, m) => { long t0 = Stopwatch.GetTimestamp(); orig(d, m); LoadDone("weapon models", t0); }));
                Load(Mod("HelldiverPack"), "Load", new Func<Func<SkinnedMeshRenderer, Transform, bool>, SkinnedMeshRenderer, Transform, bool>((orig, b, c) => { long t0 = Stopwatch.GetTimestamp(); var r = orig(b, c); LoadDone("jump pack model", t0); return r; }));
                Load(Mod("HelldiverCape"), "get_Available", new Func<Func<bool>, bool>(orig => { long t0 = Stopwatch.GetTimestamp(); var r = orig(); if (Ms(Stopwatch.GetTimestamp() - t0) > 1.0) LoadDone("cape data", t0); return r; }));
                Load(Mod("HelldiverCape"), "GetMaterial", new Func<Func<Material>, Material>(orig => { long t0 = Stopwatch.GetTimestamp(); var r = orig(); if (Ms(Stopwatch.GetTimestamp() - t0) > 1.0) LoadDone("cape textures", t0); return r; }));
                Load(Mod("Survivor"), "Create", new Action<Action>(orig => { long t0 = Stopwatch.GetTimestamp(); orig(); LoadDone("Survivor.Create (content registration)", t0); }));
                Load(Mod("ModelFiles"), "Preload", new Action<Action>(orig => { long t0 = Stopwatch.GetTimestamp(); orig(); LoadDone("model files (startup preload)", t0); }));
                Say("bench hooks: " + string.Join(", ", hookNames));
            }
            catch (Exception e) { Say("bench hooks failed: " + e); }
        }

        class Scene { public string name; public int frames; public double avgMs, p99Ms, maxMs, modMs; public int gc; public long monoDelta; public double[] perHook; }

        Scene lastScene;

        IEnumerator Measure(string name, float seconds)
        {
            Array.Clear(hookTicks, 0, hookTicks.Length); Array.Clear(hookCalls, 0, hookCalls.Length);
            var times = new List<float>(4096);
            int gc0 = GC.CollectionCount(0); long mono0 = Profiler.GetMonoUsedSizeLong();
            float t0 = Time.unscaledTime;
            yield return null;
            while (Time.unscaledTime - t0 < seconds) { times.Add(Time.unscaledDeltaTime); yield return null; }
            var s = new Scene { name = name, frames = times.Count, gc = GC.CollectionCount(0) - gc0, monoDelta = Profiler.GetMonoUsedSizeLong() - mono0 };
            times.Sort();
            s.avgMs = times.Average() * 1000.0; s.p99Ms = times[Math.Min(times.Count - 1, (int)(times.Count * 0.99))] * 1000.0; s.maxMs = times[times.Count - 1] * 1000.0;
            s.perHook = new double[hookNames.Count];
            for (int i = 0; i < hookNames.Count; i++) { s.perHook[i] = Ms(hookTicks[i]) / s.frames; s.modMs += s.perHook[i]; }
            lastScene = s;
        }

        // GPU size of a texture from its format (the profiler reports 0 once the CPU copy is released)
        static long GpuBytes(Texture2D t)
        {
            int bpp = t.format == TextureFormat.DXT1 ? 4 : t.format == TextureFormat.DXT5 ? 8 : 32;
            long sum = 0; int w = t.width, h = t.height;
            for (int m = 0; m < Math.Max(1, t.mipmapCount); m++)
            {
                int bw = bpp < 16 ? Math.Max(4, w) : w, bh = bpp < 16 ? Math.Max(4, h) : h;
                sum += (long)bw * bh * bpp / 8;
                w = Math.Max(1, w / 2); h = Math.Max(1, h / 2);
            }
            return sum;
        }

        // the Helldiver's own renderers (body, both weapons, pack, cape; vanilla item displays and Commando's hidden pistols left out)
        static string RenderStats(params Transform[] roots)
        {
            var sb = new StringBuilder();
            int totalV = 0, totalT = 0; long texBytes = 0;
            var seenTex = new HashSet<Texture>();
            foreach (var root in roots)
                foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                {
                    if (r is ParticleSystemRenderer || !(r.name.StartsWith("HD_") || r is SkinnedMeshRenderer && r.name == "CommandoMesh")) continue;
                    Mesh m = r is SkinnedMeshRenderer smr ? smr.sharedMesh : (r.GetComponent<MeshFilter>() ? r.GetComponent<MeshFilter>().sharedMesh : null);
                    if (!m) continue;
                    long idx = 0; for (int s = 0; s < m.subMeshCount; s++) idx += m.GetIndexCount(s);
                    totalV += m.vertexCount; totalT += (int)(idx / 3);
                    sb.Append("  ").Append(r.name).Append(r.gameObject.activeInHierarchy ? "" : " (inactive)").Append(": ").Append(m.vertexCount).Append(" verts, ").Append(idx / 3).Append(" tris");
                    var mat = r.sharedMaterial;
                    if (mat)
                        foreach (var prop in new[] { "_MainTex", "_NormalTex" })
                        {
                            if (!mat.HasProperty(prop)) continue;
                            var tex = mat.GetTexture(prop) as Texture2D;
                            if (!tex) continue;
                            long bytes = GpuBytes(tex);
                            if (seenTex.Add(tex)) texBytes += bytes;
                            sb.Append(" | ").Append(prop).Append(' ').Append(tex.width).Append('x').Append(tex.height).Append(' ').Append(tex.format).Append(tex.isReadable ? " readable" : "").Append(' ').Append((bytes / 1048576.0).ToString("F1")).Append(" MB");
                        }
                    sb.AppendLine();
                }
            sb.Insert(0, "Helldiver meshes: " + totalV + " verts, " + totalT + " tris; textures " + (texBytes / 1048576.0).ToString("F1") + " MB on the GPU\n");
            return sb.ToString();
        }

        IEnumerator Bench(string label)
        {
            var body = LocalBody();
            if (!body) { Say("bench: no body"); yield break; }
            Say("bench " + label + " starting");
            int vs = QualitySettings.vSyncCount, fr = Application.targetFrameRate;
            QualitySettings.vSyncCount = 0; Application.targetFrameRate = 1000;
            body.healthComponent.godMode = true;
            var pack = SkillCatalog.allSkillDefs.FirstOrDefault(d => d.skillName == "HelldiverJumpPack");
            if (pack) { body.skillLocator.utility.SetBaseSkill(pack); body.skillLocator.utility.Reset(); }
            const float yaw = 90f;   // fixed facing, so runs on the same stage see the same view
            lookYaw = yaw; lookPitch = 0f; spinRate = 0f; lookActive = true;
            yield return new WaitForSecondsRealtime(2f);

            var scenes = new List<Scene>();
            const float Len = 8f;
            yield return Measure("idle", Len); scenes.Add(lastScene);

            held[0] = true;
            yield return Measure("fire", Len); scenes.Add(lastScene);
            held[0] = false;
            yield return new WaitForSecondsRealtime(2.5f);   // let the reload finish

            sprintHeld = true; spinRate = 40f;
            var circle = StartCoroutine(SteerForward());
            yield return Measure("sprint", Len); scenes.Add(lastScene);
            StopCoroutine(circle); moveOverride = null; sprintHeld = false; spinRate = 0f; lookYaw = yaw;
            yield return new WaitForSecondsRealtime(1.5f);

            // 12 extra Helldivers (the character-select display: body model, weapon, cape, pack) in front of the camera
            var crowd = new List<GameObject>();
            var cam = Camera.main ? Camera.main.transform : body.transform;
            var fwd = cam.forward; fwd.y = 0f; fwd.Normalize(); var right = Vector3.Cross(Vector3.up, fwd);
            for (int i = 0; i < 12; i++)
            {
                var p = body.transform.position + fwd * (5f + (i / 4) * 2.5f) + right * ((i % 4) - 1.5f) * 1.6f + Vector3.up * 3f;
                if (Physics.Raycast(p, Vector3.down, out var hit, 10f, LayerIndex.world.mask)) p = hit.point; else p.y -= 3f;
                crowd.Add(UnityEngine.Object.Instantiate(Survivor.Display, p, Quaternion.LookRotation(-fwd)));
            }
            yield return new WaitForSecondsRealtime(2f);
            yield return Measure("crowd12", Len); scenes.Add(lastScene);
            ScreenCapture.CaptureScreenshot(System.IO.Path.Combine(shotDir, "bench_" + label + "_crowd.png"));
            yield return null;
            foreach (var g in crowd) if (g) UnityEngine.Object.Destroy(g);

            lookActive = false;
            QualitySettings.vSyncCount = vs; Application.targetFrameRate = fr;

            var sb = new StringBuilder();
            sb.AppendLine("Helldiver bench '" + label + "'  " + DateTime.Now.ToString("yyyy-MM-dd HH:mm") + "  " + Screen.width + "x" + Screen.height + "  " + SystemInfo.processorType.Trim() + " / " + SystemInfo.graphicsDeviceName);
            sb.AppendLine("scene     frames   avg fps  avg ms  1% low fps  worst ms  mod cpu ms/frame  GC  mono heap delta");
            foreach (var s in scenes)
                sb.AppendLine(string.Format("{0,-9} {1,6} {2,9:F0} {3,7:F2} {4,11:F0} {5,9:F1} {6,17:F3} {7,3} {8,10:F1} MB", s.name, s.frames, 1000.0 / s.avgMs, s.avgMs, 1000.0 / s.p99Ms, s.maxMs, s.modMs, s.gc, s.monoDelta / 1048576.0));
            sb.AppendLine("mod cpu per frame by method (ms):");
            for (int i = 0; i < hookNames.Count; i++)
                sb.AppendLine(string.Format("  {0,-28} {1}", hookNames[i], string.Join("  ", scenes.Select(s => s.name + "=" + s.perHook[i].ToString("F4")))));
            sb.AppendLine("loading: " + (loadLog.Count > 0 ? string.Join("; ", loadLog) : "(not captured)"));
            var cape = GameObject.Find("HD_Cape");
            sb.Append(cape ? RenderStats(body.modelLocator.modelTransform, cape.transform) : RenderStats(body.modelLocator.modelTransform));
            var text = sb.ToString();
            foreach (var line in text.Split('\n')) if (line.Trim().Length > 0) Say("[bench] " + line.TrimEnd());
            System.IO.File.WriteAllText(System.IO.Path.Combine(Paths.BepInExRootPath, "bench_" + label + ".txt"), text);
            Say("bench done " + label);
        }

        // sprint along the aim direction while the look spins, so the run goes in circles instead of into a wall
        IEnumerator SteerForward()
        {
            while (true)
            {
                var a = Quaternion.Euler(0f, lookYaw, 0f) * Vector3.forward;
                moveOverride = a;
                yield return null;
            }
        }
    }
}
#endif

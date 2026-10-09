using BepInEx;
using BepInEx.Logging;

namespace HelldiverMod
{
    [BepInDependency("com.bepis.r2api.content_management")]
    [BepInDependency("com.bepis.r2api.language")]
    [BepInDependency("com.bepis.r2api.prefab")]
    [BepInPlugin(Guid, "Helldiver", Version)]
    public class Plugin : BaseUnityPlugin
    {
        public const string Guid = "terr4.helldiver", Version = "1.0.3";
        public static ManualLogSource Log;
        public static string Dir;

        void Awake()
        {
            Log = Logger;
            Dir = System.IO.Path.GetDirectoryName(Info.Location);
            Settings.Bind(Config);
            gameObject.AddComponent<HelldiverHud>();
#if LAB
            if (System.Environment.GetEnvironmentVariable("HD_BRIDGE") == "1") gameObject.AddComponent<DevBridge>();
#endif
            Survivor.Create();
            ModelFiles.Preload();
            Log.LogInfo("Helldiver " + Version + " registered. For Super Earth!");
        }
    }
}

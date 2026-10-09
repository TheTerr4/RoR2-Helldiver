using HelldiverMod.States;
using RoR2;
using RoR2.UI;
using TMPro;
using UnityEngine;

namespace HelldiverMod
{
    /// <summary>
    /// On-screen prompts for the local player: the stratagem code being typed (or "beacon ready"), and the ammo counter next to the crosshair.
    /// Immediate-mode GUI, so it draws nothing (and costs next to nothing) while there is nothing to show.
    /// Also keeps the rounds left on the primary skill icon of the game's own HUD (see <see cref="UpdateSkillIcon"/>).
    /// </summary>
    public class HelldiverHud : MonoBehaviour
    {
        public static HelldiverHud Instance;

        static readonly Color Yellow = new Color(0.96f, 0.77f, 0.1f), Alert = new Color(1f, 0.45f, 0.3f), Wrong = new Color(1f, 0.25f, 0.2f), Done = new Color(0.6f, 1f, 0.6f);

        // stratagem prompt
        public bool visible, armed;
        public string title = "", hint = "";
        public Arrow[] code = new Arrow[0];
        public int progress;
        float wrongUntil;

        // ammo counter
        string ammoText = "";
        bool ammoAlert;
        float ammoUntil;

        GUIStyle big, small;

        void Awake() { Instance = this; useGUILayout = false; }

        public void ShowCode(string name, Arrow[] arrows) { visible = true; armed = false; title = name.ToUpperInvariant(); code = arrows; progress = 0; hint = "Arrow keys: enter the code   |   Special again: cancel"; }
        public void ShowArmed(string name) { visible = true; armed = true; title = name.ToUpperInvariant(); hint = "Fire: throw the beacon   |   Special: cancel"; }
        public void MarkWrong() { progress = 0; wrongUntil = Time.unscaledTime + 0.3f; }
        public void Hide() { visible = false; }

        public void ShowAmmo(string text, float seconds, bool alert = false)
        {
            if (!Settings.AmmoCounter.Value) return;
            ammoText = text; ammoAlert = alert; ammoUntil = Time.unscaledTime + seconds;
        }

        // ammo on the primary skill icon: a copy of the icon's own stock counter (the game hides the original for one-stock skills every frame)
        GameObject iconBody;
        HelldiverAmmo iconAmmo;
        SkillIcon icon;
        TextMeshProUGUI iconText;
        int iconRounds = -1, iconMagazine;

        void LateUpdate() => UpdateSkillIcon();

        void UpdateSkillIcon()
        {
            HelldiverAmmo ammo = null; SkillIcon target = null;
            if (Settings.AmmoOnSkillIcon.Value)
                foreach (var hud in HUD.readOnlyInstanceList)
                {
                    var bodyObj = hud ? hud.targetBodyObject : null;
                    if (!bodyObj || hud.skillIcons == null) continue;
                    if (bodyObj != iconBody) { iconBody = bodyObj; iconAmmo = bodyObj.GetComponent<HelldiverAmmo>(); }
                    if (!iconAmmo || !Util.HasEffectiveAuthority(bodyObj)) continue;     // magazines are only counted on the owner's game
                    foreach (var si in hud.skillIcons) if (si && si.targetSkillSlot == SkillSlot.Primary) target = si;
                    if (target) { ammo = iconAmmo; break; }
                }
            if (target != icon)
            {
                if (iconText) Destroy(iconText.gameObject);
                iconText = null; icon = target; iconRounds = -1;
                if (icon && icon.stockText)
                {
                    iconText = Instantiate(icon.stockText.gameObject, icon.stockText.transform.parent).GetComponent<TextMeshProUGUI>();
                    iconText.name = "HelldiverAmmoText";
                }
            }
            if (!iconText) return;
            int rounds = 0, magazine = 0;
            bool show = ammo && ammo.Current(out rounds, out magazine, out _);
            if (iconText.gameObject.activeSelf != show) iconText.gameObject.SetActive(show);
            if (!show || (rounds == iconRounds && magazine == iconMagazine)) return;
            iconRounds = rounds; iconMagazine = magazine;
            iconText.SetText("{0}", rounds);
            iconText.color = rounds * 4 <= magazine ? Alert : Color.white;     // last quarter of the magazine
        }

        static string Glyph(Arrow d)
        {
            switch (d) { case Arrow.Up: return "↑"; case Arrow.Right: return "→"; case Arrow.Down: return "↓"; default: return "←"; }
        }

        void OnGUI()
        {
            bool ammo = ammoText.Length > 0 && Time.unscaledTime < ammoUntil;
            if (!ammo && !visible) return;
            if (big == null)
            {
                big = new GUIStyle(GUI.skin.label) { fontSize = 46, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
                small = new GUIStyle(GUI.skin.label) { fontSize = 20, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
            }
            var prev = GUI.color;
            if (ammo)
            {
                GUI.color = ammoAlert ? Alert : Yellow;
                GUI.Label(new Rect(Screen.width / 2f + 40f, Screen.height / 2f + 30f, 260f, 30f), ammoText, small);
            }
            if (visible)
            {
                float w = 560f, h = 150f, x = (Screen.width - w) / 2f, y = Screen.height * 0.62f;
                GUI.color = new Color(0f, 0f, 0f, 0.6f);
                GUI.DrawTexture(new Rect(x, y, w, h), Texture2D.whiteTexture);
                GUI.color = Yellow;
                GUI.Label(new Rect(x, y + 6, w, 30), title, small);
                if (!armed)
                {
                    float cell = 70f, start = x + (w - cell * code.Length) / 2f;
                    bool wrong = Time.unscaledTime < wrongUntil;
                    for (int i = 0; i < code.Length; i++)
                    {
                        GUI.color = wrong ? Wrong : (i < progress ? Yellow : new Color(0.75f, 0.75f, 0.75f));
                        GUI.Label(new Rect(start + i * cell, y + 40, cell, 70), Glyph(code[i]), big);
                    }
                }
                else
                {
                    GUI.color = Done;
                    GUI.Label(new Rect(x, y + 50, w, 50), "BEACON READY", big);
                }
                GUI.color = new Color(1f, 1f, 1f, 0.85f);
                GUI.Label(new Rect(x, y + 114, w, 28), hint, small);
            }
            GUI.color = prev;
        }
    }
}

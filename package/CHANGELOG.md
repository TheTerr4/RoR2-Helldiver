# Changelog

## 1.0.3
- The mod's website link now goes to its GitHub repo (https://github.com/TheTerr4/RoR2-Helldiver). No gameplay changes.

## 1.0.2
- **Lobby**: changing your equipment no longer changes every other Helldiver in the lobby; each one shows its own player's weapon and utility.
- **Capes** no longer float where a player was last seen when that player is off screen.
- **Cancelling a stratagem** (Special again, while typing the code or holding the beacon) now cancels it. Before, it started over and closed on its own a few seconds later.
- **Auto reload**: a partly empty magazine reloads by itself after 2.5 seconds without firing (config: `Auto Reload Delay`, 0 = off).
  Reloads were already faster with attack speed; the descriptions now say so.
- **Ammo on the skill icon**: the rounds left always show on the primary skill icon, and turn red in the last quarter of the magazine (config: `Ammo On Skill Icon`).
- Grenade descriptions: they explode a second after they land, not on impact.

## 1.0.1
- Sounds for the Orbital Precision Strike and the Eagle Airstrike, which exploded silently, and a heavier blast for the Eagle 500kg Bomb.
  Every player hears them in co-op.

## 1.0.0
- **Config file** (`BepInEx/config/terr4.helldiver.cfg`): damage, fire rate, magazine, reload time, cooldowns, charges, blast radii and more for every
  weapon, grenade, utility and stratagem, plus character stats and the passive. Skill descriptions show the configured numbers.
- **Optimized models**: the body is 12,000 triangles (was 41,000), the weapons about 3,500 each (were 14,000 and 10,000), the Jump Pack 1,800 (was 4,600),
  with proper UV atlases and new normal maps. The weapons and the pack now show Helldivers 2's surface detail (panel lines, screws, vents, grip texture).
- Textures are block-compressed: about 13 MB of video memory instead of 48 MB, and no copies kept in system memory.
- Models load while the game starts instead of causing a hitch on the character select screen.
- The cape costs about a quarter of the CPU time it used to, and pauses while the diver is off screen.
- The weapon, pack and cape now follow the body's look: they fade with it when the camera is close, turn invisible with cloaking items, and show hit flashes and elite overlays.
- Throwing a stratagem beacon no longer fires the gun when the fire button is held a little long.
- One glove model only (the former "FlipPalms" option is gone, with the turned-around palms kept).
- Code reorganised and cleaned up for maintenance.

## 0.9.0
- Dive without the Commando's boot fire. The LIFT-850 Jump Pack is worn on the back when selected, with flames from its nozzles while it thrusts.

## 0.8.x
- Simulated cape with the Helldivers cape texture and logo; rewritten for performance in 0.8.1.

## 0.7.x
- Two-handed weapon hold with arm IK; idle carry across the chest.

## 0.6.0
- AR-23 Liberator and SG-225 Breaker models.

## 0.4.0
- Helldiver body model on the Commando skeleton.

## 0.2.x
- Thrown stratagem beacons that stick to the ground or to enemies.

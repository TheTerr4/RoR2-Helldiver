# Helldiver

A Helldivers 2 survivor for Risk of Rain 2: a rifle or a shotgun, grenades, a dive or the LIFT-850 Jump Pack, and HD2-style stratagems you call in by
typing their arrow codes and throwing a beacon.

## Loadout

| Slot | Choices |
|---|---|
| Passive | **Democracy Protects**: a lethal hit has a 50% chance to be survived (25% health back, 1.5 s invulnerable), at most once every 40 s. |
| Primary | **AR-23 Liberator**: automatic rifle, 70% damage per bullet, 640 rpm, 30-round magazine. **SG-225 Breaker**: shotgun, 9 pellets x 55%, 300 rpm, 6 shells. Both reload when empty or after 2.5 s without firing (faster with attack speed); the rounds left show on the skill icon. |
| Secondary | **G-12 High Explosive**: 700% damage, a second after it lands. **G-23 Stun**: 300% in a wide radius, stuns, 2 charges. |
| Utility | **Dive**: a quick dive in the direction you move. **LIFT-850 Jump Pack**: launch up and forward from the ground, or hover for 2.6 s in mid air. |
| Special | One **stratagem**, picked in the loadout (below). |

### Stratagems

Press **Special**, type the code with the **arrow keys**, aim, then **fire** to throw the beacon. It sticks to the ground or to an enemy and calls the
stratagem in on that spot after a moment. Press Special again to cancel; a charge is only spent when the beacon is thrown.

| Stratagem | Code | Effect | Cooldown |
|---|---|---|---|
| Orbital Precision Strike | → → ↑ | one shot, 8000% damage, stuns | 45 s |
| Eagle Airstrike | ↑ → ↓ → | 6 bombs in two lines toward the target, 1200% each | 50 s |
| Eagle 500kg Bomb | ↑ → ↓ ↓ ↓ | one huge bomb, 5000% in a 24 m radius | 65 s |
| Orbital EMS Strike | → → ← ↓ | a beacon that keeps shocking and stunning enemies near it | 60 s |
| Resupply | ↓ ↓ ↑ → | a beacon that heals allies near it; resets your Secondary and Utility cooldowns | 50 s |

All numbers above are the defaults; every one of them can be changed (see Configuration).

## Configuration

Settings live in `BepInEx/config/terr4.helldiver.cfg`, which is written with the defaults the first time the game starts with the mod.
In r2modman: **Config editor** → `terr4.helldiver.cfg`. The file is split into numbered sections, one per character part:

| Section | What you can change |
|---|---|
| 01. Character | base health, health per level, regen, armor, base damage, damage per level, move speed |
| 02. Passive | chance, cooldown, heal, invulnerability time |
| 03-04. Primaries | damage, fire rate (rpm), magazine size, reload time, auto reload delay; Breaker pellets |
| 05-06. Grenades | damage, blast radius, cooldown, charges |
| 07-08. Utilities | Dive cooldown; Jump Pack cooldown, launch speeds, hover time |
| 09-13. Stratagems | damage, blast radius, impact delay, cooldown (per stratagem) |
| 14. Stratagems - All | time to type a code, beacon delay, throw range |
| 15. Visuals | cape on/off, ammo counter by the crosshair on/off, ammo on the skill icon on/off |

Damage values are percentages, as in the skill descriptions (70 = 70% damage). The in-game descriptions always show the configured numbers.
Values marked "Restart" in the file (character stats, cooldowns, charges, blast radii) take effect after restarting the game; the others apply right away.
In co-op every player should use the same values.

## Installing

Requires BepInExPack and R2API (ContentManagement, Language, Prefab).

## Models

The models are built for low-end PCs: about 18,000 triangles for the Helldiver and everything it carries, block-compressed textures (about 13 MB of video memory),
loaded once while the game starts.

## Credits

- Made by Terr4 with the help of an AI coding agent (Claude), which wrote most of the code and the model conversion tools.
- Built on [BepInEx](https://github.com/BepInEx/BepInEx) and [R2API](https://github.com/risk-of-thunder/R2API).
- Made with [universal-modder](https://github.com/rehan-remade/universal-modder), a game-modding toolkit for AI coding agents.
- Helldivers 2 and its art belong to Arrowhead Game Studios and Sony Interactive Entertainment. This is a fan mod, not affiliated with or endorsed by them.

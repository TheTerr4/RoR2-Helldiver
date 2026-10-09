# Developing the Helldiver mod

Risk of Rain 2 1.4.1 (Unity 2021.3, Mono), BepInEx 5 + R2API. The survivor is a clone of the Commando body with its own skills, states and visuals.
Player-facing docs: `package/README.md` and `package/CHANGELOG.md`. The journal of how everything was found out: `../MODLOG.md`.

## Layout

| Folder / file | What is in it |
|---|---|
| `Plugin.cs` | BepInEx entry point: binds the config, registers the survivor, preloads the model files |
| `Settings.cs` | every config entry (`BepInEx/config/terr4.helldiver.cfg`); gameplay code reads `Settings.X.Value`, damage via `.Coef()` |
| `Content/` | `Survivor.cs` (body, skill families, display, survivor def), `Tokens.cs` (English text built from the config), `Assets.cs` (vanilla assets, grenades, icons), `Passive.cs` |
| `States/` | entity states: `Primary.cs` (magazines, reloads, the two guns), `Secondary.cs` (grenades), `Utility.cs` (Dive, Jump Pack), `StratagemStates.cs` (type the code, aim and throw) |
| `Stratagems/` | `Stratagems.cs` (the table of the five stratagems, their projectiles, the beacon that calls them in), `Hud.cs` (code prompt and ammo counter) |
| `Visuals/` | the optional Helldiver look: `ModelFiles.cs` (Model folder, HDX reader, texture compression), `HelldiverVisuals.cs` (per model: applies everything), `HelldiverModel.cs` (body), `WeaponModels.cs`, `Grip.cs` (two-handed IK), `JumpPack.cs`, `Cape.cs` (cloth) |
| `Dev/` | lab-only test bridge and benchmark (`-c Lab`, never in a release) |
| `Assets/` | skill icons (embedded in the DLL) and the HD2 logo source for the cape (not embedded) |
| `Model/` | the converted models (full package only), made by `tools/hd2` |
| `tools/` | `package.py` (release zips), `hd2/` (model pipeline, see its README), icon scripts |

Adding a stratagem: a row in `Stratagems.Create`, an `Input...`/`Armed...` pair in `StratagemStates.cs` (one line each), its config entries in `Settings.cs`,
its text in `Tokens.cs`, an icon in `Assets/`, and its effect in `StratagemBeacon.Trigger`. Append it at the end: player profiles store the selected variant by index.

## Build

```
dotnet build -c Release -o outrel                                   # the shipped DLL
dotnet build -c Lab -o out                                          # + Dev/ (test bridge, benchmark), with the Model folder
uv run --with pillow python tools/package.py                        # builds Release and writes Helldiver-<v>.zip (Thunderstore) and -standalone.zip to ../dist
```

References come straight from a copy of the game with BepInEx and R2API installed, `../lab` by default; point elsewhere with
`-p:Lab="D:\path\to\Risk of Rain 2\\"` (keep the trailing backslash). The version is `Plugin.Version`.

## Lab (work/risk-of-rain-2)

A separate copy of the game with BepInEx; the Lab build reads commands from `BepInEx/hd_cmd.txt` when started with `HD_BRIDGE=1`
(`relaunch.ps1` does that). The scripts in the lab folder drive it:

- `startrun.ps1 [-Src out]` launches the build and starts a run as the Helldiver; `waitmain.ps1` waits until the drop pod opens.
- `fulltest.ps1`: every feature once (character select, both guns, grenades, Jump Pack, Dive, all stratagems) and the errors in the log.
- `benchrun.ps1 -Tag x`: benchmark on Titanic Plains at a fixed spot (idle, firing, sprinting, 12 extra Helldivers): FPS, 1% lows, the mod's CPU time
  per method, GC, mesh and texture sizes, load times. `abbench.ps1` runs it for v0.9.0 and the current build.
- `lookshots.ps1 -Tag x`, `visualtest.ps1`: screenshots from fixed camera spots.
- `showcase_setup.ps1` + `showcase_take.ps1 [-Capture]`: the scripted showcase take (frame-locked video pass, real-time audio pass); edit in `showcase/` (see MODLOG).

Bridge commands worth knowing: `seq a; wait 0.5; b` (timed sequences: separate files less than ~1.5 s apart get lost), `skill <1-5> down|up`,
`key Up|Right|Down|Left`, `skilldef <slot> <skill>`, `setvariant <slot> <variant>`, `cam x y z m lookY`, `shot name`, `status`, `stage <scene>`,
`tpabs x y z`, `buff <name> <s>`, `killall`, `spawn <master> n dist [still]`, `capture <dir> [fps] [width]` / `capture stop`, `gripset <static field> <value>` (live tuning of Grip/Cape statics), `capeinfo`, `bench <tag>`, `findsound <text>` / `soundat <event> <dist>` / `dumpsound` (picking and checking sound events),
`lobbyinfo` (whose loadout each Helldiver model follows), `projinfo <projectile>` (fuse / impact settings), `capetest spawn|away|info` (a second Helldiver body moved out of view: does its cape follow).
`skill N down` holds the button like a real key: one press, which keeps its claim (`hasPressBeenClaimed`) while held.
Director enemies are removed in the lab unless `enemies on`.

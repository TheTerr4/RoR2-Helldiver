# Helldiver for Risk of Rain 2

A Helldivers 2 survivor for Risk of Rain 2: the AR-23 Liberator or SG-225 Breaker, high-explosive and stun grenades, dive or
jump pack, and stratagems called in by typing their arrow-key codes. Works in multiplayer, and every number can be changed in
the config.

- **Install:** through r2modman or Thunderstore Mod Manager, or by hand (see [`package/README.md`](package/README.md)).
- **Changes:** [`package/CHANGELOG.md`](package/CHANGELOG.md).
- **Bugs and ideas:** open an issue.

## What is in this repo

The mod's source code, its procedural skill icons and the scripts that build the release. It does **not** contain the Helldivers 2
models (`Model/`): those are converted from a Helldivers 2 install with the scripts in [`tools/hd2`](tools/hd2/README.md) and
belong to Arrowhead Game Studios. Without them the Helldiver is a recoloured Commando.

## Building

Needs the .NET SDK and a copy of Risk of Rain 2 with BepInEx and R2API installed (the project references its DLLs, which are
not in this repo). See [`DEVELOPING.md`](DEVELOPING.md) for the layout, the build commands and the lab test tools.

```
dotnet build -c Release -o outrel -p:Lab="D:\path\to\Risk of Rain 2\\"
```

## Credits

- Made by Terr4 with the help of an AI coding agent (Claude), which wrote most of the code and the model conversion tools.
- Built on [BepInEx](https://github.com/BepInEx/BepInEx) and [R2API](https://github.com/risk-of-thunder/R2API).
- Made with [universal-modder](https://github.com/rehan-remade/universal-modder), a game-modding toolkit for AI coding agents.
- Helldivers 2 and its art belong to Arrowhead Game Studios and Sony Interactive Entertainment. This is a fan mod, not
  affiliated with or endorsed by them.

## License

The code is under the [MIT License](LICENSE). Helldivers 2 names and art are not covered by it.

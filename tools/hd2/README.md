# Helldiver model pipeline (tools/hd2)

Everything in the shipped `Model` folder is made here, offline, from the player's **own Helldivers 2 install**. None of the inputs or intermediate files
belong in a repository or a public package: they are converted game assets. Keep them in a private folder (here `work/hd2-extract`, git-ignored).

Tools: [filediver](https://github.com/xypwn/filediver) (reads the HD2 install, writes GLB/PNG), Python through `uv` (numpy, pillow), Blender 4.0 for the last step.

## Overview

```
HD2 install --filediver--> GLB units --fit/paint/fixhands, weapon.py, pack.py, cape.py--> high-poly sources --optimize.py (Blender)--> Model/*.hdx + _tex/_nrm.png
                                                                                       \--capegrid.py, capetex.py--> Model/cape.bin + cape_tex/_nrm.png
```

The high-poly sources (`work/hd2-extract/highpoly`) are what the game showed up to 0.9.0: triangle soups with a per-triangle colour atlas.
`optimize.py` turns each one into the shipped model: decimated, properly unwrapped, with a colour map and a normal map baked from the source.
To change a polygon budget or a texture size, edit `optimize_all.ps1` and run it; nothing upstream has to be redone.

## Steps

| Asset | Extract (filediver, read-only on the install) | Convert | Optimize |
|---|---|---|---|
| Body | `content/fac_helldivers/cha_avatar/avatar_helldiver` | `fit.py avatar.glb commando_skel.json fitted.bin`, then `paint.py fitted.bin painted_tex.png 2048` (also writes painted_tex.bin), then `fixhands.py painted_tex.bin helldiver_mesh.bin --flip`; the texture is `helldiver_mesh_tex.png` | 12,000 tris, 2048 maps |
| AR-23 Liberator | `primary_weapons/assault_rifle` + `attachment/magazine/assaultrifle_standard_magazine` | `weapon.py liberator <out> assault_rifle.unit.glb assaultrifle_standard_magazine.unit.glb:attach_mag --detail` (relative paths: the `glb:node` argument splits on `:`) | 3,500 tris, 1024 |
| SG-225 Breaker | `primary_weapons/pump_shotgun` | `weapon.py breaker <out> pump_shotgun.unit.glb --detail` | 3,600 tris, 1024 |
| LIFT-850 Jump Pack | `equipment/backpacks/jumppack_backpack` | `pack.py jumppack_backpack.unit.glb avatar_helldiver.unit.glb commando_skel.json <out> --detail` | 1,800 tris, 1024 |
| Cape | `fac_helldivers/capes/*` (textures as PNG) | `cape.py` (avatar GLB mesh 1), `capegrid.py` (9 x 13 grid), `capetex.py <cfd.png> <tear.png> Model ../../Assets/Helldivers_2_Logo_white.png Model/cape.bin` | not needed (runtime cloth) |

`commando_skel.json` is the Commando rest skeleton, dumped from the game with the lab bridge (`dumpskel`).
`--detail` makes weapon.py / pack.py also write the HD2 UVs and normal maps (detail.py), so the bake keeps HD2's panel lines, screws and vents;
HD2 stores no albedo for these, so their colours are baked per region by the scripts. The body has no extractable textures: its normal map comes from its geometry.

## optimize.py

Runs inside Blender (`optimize_all.ps1` has the exact calls):
1. reads the source, welds the soup, decimates it (collapse) to the triangle budget; vertex weights follow along for the skinned body;
2. Smart UV Project + island packing (4 texel padding);
3. Cycles bakes the colour (from the source's emission) and a tangent-space normal map (from the source's normals, plus the HD2 normal maps with `--detail`),
   selected-to-active with a short ray distance;
4. writes HDX1 with Blender's MikkTSpace tangents, so the game decodes the normal map exactly as it was baked.

`--preview <prefix>` renders the source and the result side by side (Eevee); `sheet.py <prefix>` puts the renders on one sheet.

## Formats

- **HDX1** (shipped meshes): header, named key points (muzzle, foregrip, thruster exits...), bone names, positions, normals, tangents, UVs,
  optional 4 bone weights, 16-bit triangles. Documented at the top of `optimize.py`; read by `Visuals/ModelFiles.cs`.
- **HDC2** (cape grid): `capegrid.py`; read by `Visuals/Cape.cs`.
- Intermediate only: HDM1 (body soup with weights), HDW1 (weapon), HDP1 (pack), HDC1 (full cape).

Textures are plain PNGs (colour sRGB, normal maps RGB with +Y up). The game block-compresses them when it starts (`ModelFiles.Texture`).

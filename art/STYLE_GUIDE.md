# Helldiver art style guide (original model for 1.1.0)

Goal: an original Helldiver, made from scratch, that looks like it belongs to Risk of Rain 2's survivor roster. It must not be a
port of Helldivers 2's assets.

**Originality rule:**
- No geometry, texture, UV, normal map or logo file from Helldivers 2 may enter a Blender scene or a texture script.
- HD2 images may be looked at on screen, as reference only.
- Commando's skeleton dump is used only to build the rig.

## What was measured
In the 1.5.0 lab, every survivor's display model was placed and inspected with the lab bridge commands `lineup` and `matdump`
(`Dev/DevArt.cs`):
- the raw dump of meshes and all material values (`art-ref/matdump.txt`);
- line-ups of all 21 survivors, front, side and back (`art-ref/style_p*_*.png`);
- close-ups of Commando, Engineer, Artificer, Mercenary, Loader, Captain, Railgunner, Enforcer2 and the current Helldiver
  (`art-ref/solo_sheet.png`).

The screenshots stay local in `work/risk-of-rain-2/art-ref/` (they show the game's art) and are not committed.

**Size and triangles** (whole display model, weapons and effects included):

| | Height (m) | Triangles |
|---|---|---|
| Commando | 2.00 | 7,432 |
| Mercenary | 2.33 | 7,610 |
| Engineer | 2.58 | 11,700 |
| Loader | 2.82 | 11,631 |
| Railgunner | 2.65 | 12,760 |
| Artificer | 2.08 | 13,606 |
| Captain | 2.57 | 15,999 |
| Enforcer2 | 2.78 | 19,128 |
| **Median of all 21** | | **about 12,700** |
| **Helldiver now** (HD2-derived) | 2.06 | **17,300** |

**Materials:**
- All characters use `Hopoo Games/Deferred/Standard` (110 of the 135 materials).
- Body materials almost always have `_Smoothness` 0, `_RampInfo` 0 (the default two-tone ramp) and low specular (0 to 0.6).
- **Palette textures:** Commando's whole body is one **64×8 palette texture** plus a 64×8 emission palette. Captain's body is a
  256×256 palette. Loader, Captain and Railgunner add shared trim sheets with vertex colours.
- **Texture sizes:** body maps are 256-1024 (a few older ones 2048). Normal maps, when there is one, are 128-512.
- **Glows are emission maps** with a strong colour:

  | | `_EmColor` | `_EmPower` | Emission map |
  |---|---|---|---|
  | Loader visor | cyan (0, 0.84, 1) | 3 | 512 |
  | Enforcer2 visor | amber (1, 0.74, 0) | 1, plus a fresnel ramp | 256 |
  | Commando | warm yellow | 0.11 | 64×8 palette |
  | Railgunner and Captain lights | red/pink | 3-6 | |

## Style traits (what makes a RoR2 survivor)
1. **The silhouette comes first.** Big, simple, readable forms: a chunky helmet, shoulder pads, big boots and gloves. Detail is
   carried by shape, not by texture noise.
2. **Flat colour blocks.** Two or three main hues and one accent per character, close to flat fills. Shading comes from the
   two-tone ramp and from the geometry: bevels and plane changes catch the light. There is no painted grime and no photo
   texture.
3. **Glowing elements are the face.** Most armoured survivors have no visible face, and a glowing visor or eye is the focal
   point: Loader, Enforcer2, Engineer, Mercenary, Huntress, REX.
4. **Low, honest geometry.** Hard-surface pieces built from bevelled boxes and cylinders; organic parts kept smooth with few
   loops.
5. **Proportions:** about 2-2.8 m tall in game units. The head and helmet, hands and boots are slightly oversized, and the
   limbs fairly slim. Commando, the base we skin to, is 2.0 m.
6. **Small or no normal maps.** Bevels are modelled, not baked.

## Helldiver → RoR2 translation
| Helldivers 2 trait | Our version |
|---|---|
| Rounded helmet with a dark visor | Chunky rounded helmet with one wide **glowing visor band** (emission). The concept tests amber and cyan. |
| Layered armour, many straps | 4-5 big plates (chest, back, two shoulder pads, a belt with 2-3 boxy pouches); no straps |
| Grey/black armour with yellow trim | Charcoal armour, a lighter grey undersuit, **Super Earth yellow** trim and stripes as flat colour |
| Long dark cape | Kept: a dark cape with a yellow hem stripe and **our own emblem** (drawn from scratch), on the existing cloth simulation |
| Kneepads, heavy boots | Oversized knee pads and boots: a strong lower silhouette |
| Gloves | Chunky gloves with fingers on Commando's finger bones, so they can close on the rifle grip |

## Budgets and technical targets
**Triangles:**

| Part | Budget |
|---|---|
| Body | ≤ 7,000 (12,000 now) |
| Each weapon | ≤ 2,000 |
| Jump pack | ≤ 1,500 |
| Cape | 192 (unchanged) |
| **Total visible** | **≤ 11,000**, under the median (17,300 now) |

**Textures:**
- **Colour:** one 512×512 atlas per asset. The top half holds flat palette swatches, each with a slight vertical gradient (UVs
  point into the swatches, as Commando does). The bottom half holds decals: hazard stripes, the emblem, numbers.
- **Emission:** a matching 512 emission atlas (black except the visor and the lights). In the material, `_EmColor` is white,
  `_EmPower` about 2 and the colour lives in the map; tune in game next to Loader and Enforcer2.
- **Normal map:** none for the body (modelled bevels); a 256 one only if a weapon needs it.

**Material:** `_Smoothness` 0, `_SpecularStrength` about 0.2, `_SpecularExponent` about 3, ramp 0, Commando's fresnel values.
The code already copies Commando's material, so only these values change.

**Memory:** 512 DXT1 colour plus 512 DXT1 emission is about 0.35 MB per asset, against 2.7 MB for the body now (2048 colour,
1024 normal).

## References
- In-game measurements and screenshots above.
- "Single colours and clever use of lighting", silhouette outline: [Gamedev.tv, Game Design Deep Dive: Risk of Rain 2](https://gamedev.tv/articles/game-design-deep-dive-risk-of-rain-2).
- The move to 3D: [Kotaku, Risk of Rain 2 developers discuss the shift to 3D](https://kotaku.com/risk-of-rain-2-developers-discuss-the-games-shift-to-3d-1821553824).
- The community route for custom survivor models (Blender + Unity, match the survivor armature): [R2Wiki, creating a skin with a custom model](https://github-wiki-see.page/m/risk-of-thunder/R2Wiki/wiki/Mod-Creation_Assets_Skins_Creating-skin-for-vanilla-characters-with-custom-model).

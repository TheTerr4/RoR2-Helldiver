"""
Build the release DLL and the two zips into ../dist:

  Helldiver-<version>.zip               for Thunderstore and r2modman: the files at the top of the zip
  Helldiver-<version>-standalone.zip    for installing by hand: the same files inside a Helldiver-<version>/ folder

Both hold the DLL, the Model folder (models converted from a Helldivers 2 install), manifest, README, CHANGELOG and icon.

  uv run --with pillow python tools/package.py [--no-build]

The version comes from Plugin.cs (Plugin.Version); README.md and CHANGELOG.md from package/; the icon from Assets/portrait.png.
"""
import io, json, os, re, subprocess, sys, zipfile
from PIL import Image

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(os.path.dirname(MOD), "dist")
DOTNET = os.path.join(os.path.dirname(os.path.dirname(MOD)), "tools", "dotnet", "dotnet.exe")
OUT = os.path.join(MOD, "outrel")

VER = re.search(r'Version = "([0-9.]+)"', open(os.path.join(MOD, "Plugin.cs"), encoding="utf-8").read()).group(1)
MANIFEST = {
    "name": "Helldiver",
    "version_number": VER,
    "website_url": "https://github.com/TheTerr4/RoR2-Helldiver",
    "description": "Helldivers 2 survivor: rifle or shotgun, grenades, dive or jump pack, and stratagems you call in with arrow-key codes. Fully configurable.",
    "dependencies": ["bbepis-BepInExPack-5.4.2122", "RiskofThunder-R2API_ContentManagement-1.0.11", "RiskofThunder-R2API_Language-1.1.0", "RiskofThunder-R2API_Prefab-1.1.1"],
}

if "--no-build" not in sys.argv:
    r = subprocess.run([DOTNET, "build", MOD, "-c", "Release", "-o", OUT, "-nologo", "-v", "q"], capture_output=True, text=True)
    if r.returncode != 0: sys.exit(r.stdout + r.stderr)
dll = os.path.join(OUT, "HelldiverMod.dll")
if b"Helldivers_2_Logo" in open(dll, "rb").read(): sys.exit("the HD2 logo is embedded in the DLL; it is only baked into the cape texture")
model_dir = os.path.join(MOD, "Model")
if not os.path.isdir(model_dir) or not os.listdir(model_dir): sys.exit("no Model folder: build it with tools/hd2 first (see tools/hd2/README.md)")

icon = io.BytesIO()
Image.open(os.path.join(MOD, "Assets", "portrait.png")).convert("RGBA").resize((256, 256), Image.LANCZOS).save(icon, "PNG")
os.makedirs(DIST, exist_ok=True)

def build(name, root):
    """root: the folder every file goes in ("" = the top of the zip). Paths use forward slashes, as Thunderstore and r2modman expect."""
    path = os.path.join(DIST, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(root + "manifest.json", json.dumps(MANIFEST, indent=2))
        z.writestr(root + "icon.png", icon.getvalue())
        z.write(os.path.join(MOD, "package", "README.md"), root + "README.md")
        z.write(os.path.join(MOD, "package", "CHANGELOG.md"), root + "CHANGELOG.md")
        z.write(dll, root + "HelldiverMod.dll")
        for fn in sorted(os.listdir(model_dir)):
            z.write(os.path.join(model_dir, fn), root + "Model/" + fn)
    print("%-40s %10d bytes" % (name, os.path.getsize(path)))

build("Helldiver-%s.zip" % VER, "")
build("Helldiver-%s-standalone.zip" % VER, "Helldiver-%s/" % VER)

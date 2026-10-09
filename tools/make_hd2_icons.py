"""Frames icons extracted from the user's own Helldivers 2 install into Assets_hd2/ (private, never shipped).
usage: python make_hd2_icons.py <hd2-extract-dir>   (expects arch/*.png and sq.txt from the contact-sheet step)"""
import sys, os
from PIL import Image, ImageDraw
src = sys.argv[1]
rows = [l.split() for l in open(os.path.join(src, "sq.txt"))]
m = {int(r[0]): os.path.join(src, r[1]) for r in rows}
out = os.path.join(os.path.dirname(__file__), "..", "Assets_hd2")
os.makedirs(out, exist_ok=True)
Y = (245, 197, 24, 255); D = (28, 30, 34, 255)
picks = {"orbital_strike": m[144], "eagle_airstrike": m[61], "eagle_bomb": m[76], "orbital_ems": m[192], "resupply": m[196],
         "jump": os.path.join(src, "content/ui/shared/stratagem/icon_strat_hud_supportbackpack_jumppack.png")}
for name, path in picks.items():
    g = Image.open(path).convert("RGBA")
    base = Image.new("RGBA", (128, 128), (0, 0, 0, 0)); d = ImageDraw.Draw(base)
    d.rounded_rectangle([4, 4, 123, 123], 14, fill=D, outline=Y, width=4)
    g.thumbnail((88, 88), Image.LANCZOS)
    base.alpha_composite(g, ((128 - g.width) // 2, (128 - g.height) // 2))
    base.save(os.path.join(out, name + ".png"))
print(sorted(os.listdir(out)))

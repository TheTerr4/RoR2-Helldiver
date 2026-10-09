"""Procedural placeholder icons (original artwork, no game assets). Run: uv run --with pillow python tools/make_icons.py"""
from PIL import Image, ImageDraw
import math, os
S = 128
Y = (245, 197, 24, 255); D = (28, 30, 34, 255); G = (70, 74, 82, 255); R = (220, 60, 50, 255); B = (90, 170, 255, 255)
out = os.path.join(os.path.dirname(__file__), "..", "Assets")

def base(accent=Y):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, S - 5, S - 5], 14, fill=D, outline=accent, width=4)
    return im, d

def save(im, name): im.save(os.path.join(out, name + ".png"))

def rifle():
    im, d = base()
    d.rectangle([18, 62, 100, 74], fill=Y); d.rectangle([84, 56, 110, 66], fill=Y)
    d.polygon([(30, 74), (50, 74), (46, 100), (32, 100)], fill=Y); d.rectangle([54, 74, 62, 90], fill=G)
    d.rectangle([14, 58, 26, 78], fill=G)
    for i in range(3): d.line([(112 + i * 0, 60 + i * 4 - 4), (122, 60 + i * 6 - 6)], fill=Y, width=2)
    save(im, "rifle")

def shotgun():
    im, d = base()
    d.rectangle([16, 54, 108, 62], fill=Y); d.rectangle([16, 66, 108, 74], fill=Y)
    d.polygon([(16, 54), (40, 54), (40, 86), (24, 98), (14, 90)], fill=G)
    for a in (-18, 0, 18):
        x = 112; y = 64
        d.line([(x, y), (x + 12, y + a * 0.6)], fill=Y, width=3)
    save(im, "shotgun")

def grenade(c=Y):
    im, d = base(c)
    d.ellipse([34, 44, 94, 104], fill=c); d.rectangle([54, 28, 74, 46], fill=G)
    d.rectangle([60, 18, 92, 26], fill=G); d.ellipse([84, 18, 98, 32], outline=c, width=4)
    for i in range(3): d.line([(40, 60 + i * 14), (88, 60 + i * 14)], fill=D, width=3)
    save(im, "grenade_he")
    im, d = base(B)
    d.ellipse([34, 44, 94, 104], fill=B); d.rectangle([54, 28, 74, 46], fill=G)
    for r in (14, 24, 34): d.arc([64 - r, 74 - r, 64 + r, 74 + r], 200, 340, fill=D, width=3)
    save(im, "grenade_stun")

def dive():
    im, d = base()
    d.polygon([(22, 90), (86, 58), (104, 70), (96, 84), (40, 100)], fill=Y)
    d.ellipse([84, 36, 108, 60], fill=Y)
    for i in range(3): d.line([(16, 70 + i * 10), (44, 70 + i * 10 - 8)], fill=G, width=3)
    save(im, "dive")

def jump():
    im, d = base()
    d.rectangle([44, 30, 84, 80], fill=G, outline=Y, width=3)
    d.polygon([(48, 80), (80, 80), (72, 112), (56, 112)], fill=Y)
    d.polygon([(54, 112), (74, 112), (64, 124)], fill=R)
    d.polygon([(64, 8), (74, 28), (54, 28)], fill=Y)
    save(im, "jump")

def strike(name, big=False):
    im, d = base()
    cx, cy = 64, 80
    d.ellipse([cx - 30, cy - 12, cx + 30, cy + 12], outline=Y, width=3)
    d.line([(cx, cy - 30), (cx, cy + 30)], fill=Y, width=2); d.line([(cx - 40, cy), (cx + 40, cy)], fill=Y, width=2)
    d.polygon([(cx - 6, 14), (cx + 6, 14), (cx + 2, cy - 4), (cx - 2, cy - 4)], fill=R if not big else Y)
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=R)
    save(im, name)

def eagle():
    im, d = base()
    d.polygon([(64, 22), (82, 52), (118, 66), (82, 62), (64, 46), (46, 62), (10, 66), (46, 52)], fill=Y)
    for x in (34, 54, 74, 94):
        d.ellipse([x - 5, 88, x + 5, 104], fill=G); d.line([(x, 76), (x, 88)], fill=Y, width=2)
    save(im, "eagle_airstrike")
    im, d = base()
    d.polygon([(64, 14), (80, 40), (112, 52), (80, 50), (64, 36), (48, 50), (16, 52), (48, 40)], fill=Y)
    d.ellipse([38, 62, 90, 114], fill=G, outline=Y, width=3)
    d.text((47, 80), "500", fill=Y)
    save(im, "eagle_bomb")

def ems():
    im, d = base(B)
    d.polygon([(72, 14), (38, 70), (60, 70), (50, 114), (92, 54), (68, 54)], fill=B)
    d.arc([14, 30, 114, 130], 200, 340, fill=B, width=3)
    save(im, "orbital_ems")

def resupply():
    im, d = base()
    d.rectangle([24, 44, 104, 106], fill=G, outline=Y, width=4)
    d.rectangle([56, 54, 72, 96], fill=Y); d.rectangle([42, 68, 86, 82], fill=Y)
    d.polygon([(34, 14), (94, 14), (84, 40), (44, 40)], fill=Y)
    save(im, "resupply")

def passive():
    im, d = base()
    d.polygon([(64, 12), (112, 30), (104, 80), (64, 116), (24, 80), (16, 30)], fill=G, outline=Y)
    d.polygon([(64, 24), (100, 38), (94, 76), (64, 104), (34, 76), (28, 38)], outline=Y, fill=D)
    d.polygon([(64, 40), (74, 62), (96, 62), (78, 76), (86, 98), (64, 84), (42, 98), (50, 76), (32, 62), (54, 62)], fill=Y)
    save(im, "passive_democracy")

def portrait():
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    for y in range(256): d.line([(0, y), (256, y)], fill=(20 + y // 12, 24 + y // 10, 30 + y // 8, 255))
    d.ellipse([58, 40, 198, 190], fill=(74, 82, 70, 255), outline=Y, width=4)           # helmet
    d.rounded_rectangle([78, 104, 178, 150], 16, fill=(18, 20, 22, 255), outline=Y, width=3)  # visor
    d.polygon([(86, 112), (170, 112), (160, 124), (96, 124)], fill=(250, 210, 60, 140))
    d.rectangle([108, 150, 148, 176], fill=(40, 44, 40, 255))
    d.polygon([(30, 256), (60, 190), (196, 190), (226, 256)], fill=(66, 74, 62, 255), outline=Y)
    d.rectangle([118, 190, 138, 256], fill=Y)
    save(im, "portrait")

rifle(); shotgun(); grenade(); dive(); jump()
strike("orbital_strike"); eagle(); ems(); resupply(); passive(); portrait()
print(sorted(os.listdir(out)))

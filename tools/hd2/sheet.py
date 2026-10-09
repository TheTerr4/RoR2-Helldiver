"""
Side-by-side contact sheet of optimize.py --preview renders: one row per view, the high-poly on the left, the optimized model on the right.

  uv run --with pillow python sheet.py <preview prefix> [out.png] [crop fraction]
"""
import sys, os
from PIL import Image, ImageDraw
prefix = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else prefix + "_sheet.png"
crop = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
views = [v for v in ("front", "back", "left", "right") if os.path.exists("%s_%s_high.png" % (prefix, v))]
cells = []
for v in views:
    row = []
    for m in ("high", "low"):
        im = Image.open("%s_%s_%s.png" % (prefix, v, m)).convert("RGB")
        if crop: w, h = im.size; im = im.crop((int(w * crop), int(h * crop), int(w * (1 - crop)), int(h * (1 - crop))))
        row.append(im.resize((450, 450), Image.LANCZOS))
    cells.append(row)
sheet = Image.new("RGB", (900, 450 * len(cells)), (20, 20, 22))
d = ImageDraw.Draw(sheet)
for r, row in enumerate(cells):
    for c, im in enumerate(row):
        sheet.paste(im, (c * 450, r * 450))
        d.text((c * 450 + 8, r * 450 + 6), ("before " if c == 0 else "after ") + views[r], fill=(230, 230, 230))
sheet.save(out); print(out, sheet.size)

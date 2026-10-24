#!/usr/bin/env bash
# Gate renders of the body against the concept views (blender-image-to-3d skill scripts):
#   gate.sh <tag> [mode]  ->  art/review/<tag>/<mode>_{front,side,back}.png and compare_*.png / *.json
set -e
TAG=$1; MODE=${2:-clay}
ART='H:\universal-modder\work\risk-of-rain-2\HelldiverMod\art'
BLEND="$ART"'\helldiver.blend'
OUT="$ART"'\review\'"$TAG"
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
SK=/c/Users/Terr4/.claude/skills/blender-image-to-3d/scripts
"$B" --background --python $SK/review_render.py -- --blend "$BLEND" --out "$OUT" --collections Body --views front,side,back --mode "$MODE" --res 1024 2>&1 | grep -E "^size|Error|Traceback" || true
cd /h/universal-modder/work/risk-of-rain-2/HelldiverMod/art
for v in front side back; do
  echo "$v: $(uv run -q --with pillow python $SK/compose_review.py --ref ref/$v.png --render review/$TAG/${MODE}_$v.png --out review/$TAG/compare_$v.png --measure --gameplay-px 128 2>&1 | grep IoU)"
done

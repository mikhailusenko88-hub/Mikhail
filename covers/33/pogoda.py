# Солнце над раскрытой шишкой и туча с каплями над закрытой (обложка 33) — поверх афиши: python3 pogoda.py a.jpg cover.jpg
# Шишки v_cone_open/closed.png — лист вещей движка «pinecone» и «pinecone:closed» (propstudio.js + cutout.py).
import sys, math
from PIL import Image, ImageDraw
S = 2; im = Image.open(sys.argv[1]).convert('RGBA'); W, H = im.size; big = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
sx, sy, r = 493 * S, 128 * S, 46 * S
for i in range(12):
    a = i / 12 * 2 * math.pi; d.line([(sx + math.cos(a) * (r + 10 * S), sy + math.sin(a) * (r + 10 * S)), (sx + math.cos(a) * (r + 30 * S), sy + math.sin(a) * (r + 30 * S))], fill=(255, 196, 40, 255), width=9 * S)
d.ellipse([sx - r - 5 * S, sy - r - 5 * S, sx + r + 5 * S, sy + r + 5 * S], fill=(60, 40, 20, 255)); d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 214, 60, 255)); d.ellipse([sx - r * .55, sy - r * .6, sx - r * .05, sy - r * .15], fill=(255, 240, 160, 255))
cx, cy = 768 * S, 118 * S; blobs = [(-48, 8, 34), (-14, -12, 42), (28, -4, 38), (56, 12, 28), (0, 14, 36)]
for dx, dy, rr in blobs: d.ellipse([cx + (dx - rr - 5) * S, cy + (dy - rr - 5) * S, cx + (dx + rr + 5) * S, cy + (dy + rr + 5) * S], fill=(40, 50, 70, 255))
for dx, dy, rr in blobs: d.ellipse([cx + (dx - rr) * S, cy + (dy - rr) * S, cx + (dx + rr) * S, cy + (dy + rr) * S], fill=(150, 170, 200, 255))
for dx in (-40, -8, 26, 54):
    x, y = cx + dx * S, cy + 62 * S
    d.polygon([(x, y - 14 * S), (x - 9 * S, y + 4 * S), (x + 9 * S, y + 4 * S)], fill=(40, 60, 110, 255)); d.ellipse([x - 11 * S, y - 6 * S, x + 11 * S, y + 14 * S], fill=(40, 60, 110, 255))
    d.polygon([(x, y - 10 * S), (x - 7 * S, y + 4 * S), (x + 7 * S, y + 4 * S)], fill=(90, 170, 240, 255)); d.ellipse([x - 8 * S, y - 3 * S, x + 8 * S, y + 11 * S], fill=(90, 170, 240, 255))
im.alpha_composite(big.resize((W, H), Image.LANCZOS)); im.convert('RGB').save(sys.argv[2], quality=92)

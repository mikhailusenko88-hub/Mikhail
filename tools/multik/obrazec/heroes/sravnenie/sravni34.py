import sys
from PIL import Image
def cr(v, box): return Image.open('/home/claude/out/geroi/obr/%s_maxresdefault.jpg' % v).convert('RGB').crop(box)
REF = {'fila': [cr('Zd2QhucOkRI', (500, 180, 720, 400)), cr('Xn3vyfdqCuo', (610, 190, 850, 430))],
       'topa': [cr('Xn3vyfdqCuo', (390, 90, 640, 340)), cr('0VAW6h7-Yf0', (60, 200, 300, 440))]}
name, kfile, out = sys.argv[1:4]; idx = [int(x) for x in (sys.argv[4] if len(sys.argv) > 4 else '1,0').split(',')]
k = Image.open(kfile).convert('RGB'); n = k.size[0] // 600
mine = [k.crop((i * 600, 0, i * 600 + 600, 600)) for i in idx]
ims = REF[name] + mine; H = 380; ims = [i.resize((int(i.size[0] * H / i.size[1]), H), Image.LANCZOS) for i in ims]
S = Image.new('RGB', (sum(i.size[0] for i in ims) + 12, H), (255, 255, 255)); x = 0
for j, i in enumerate(ims): S.paste(i, (x, 0)); x += i.size[0] + (12 if j == 1 else 0)
S.save(out, quality=90)

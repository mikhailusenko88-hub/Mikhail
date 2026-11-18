# Элемент обложки 29: изогнутая пунктирная стрелка «жёлудь → дуб» (белая с коричневой обводкой), прозрачный PNG
import math, sys
from PIL import Image, ImageDraw, ImageFilter
W, H = 900, 900
def bez(t, p0, p1, p2): return ((1-t)**2*p0[0]+2*(1-t)*t*p1[0]+t*t*p2[0], (1-t)**2*p0[1]+2*(1-t)*t*p1[1]+t*t*p2[1])
p0, p1, p2 = (90, 820), (180, 160), (780, 120)
def draw(width, col, img, dash=True):
    d = ImageDraw.Draw(img); n = 60
    pts = [bez(i/n, p0, p1, p2) for i in range(n+1)]
    end = len(pts) - 6
    for i in range(end):
        if dash and (i // 4) % 2: continue
        d.line([pts[i], pts[i+1]], fill=col, width=width)
        d.ellipse([pts[i][0]-width/2, pts[i][1]-width/2, pts[i][0]+width/2, pts[i][1]+width/2], fill=col)
    # наконечник
    tip = pts[-1]; bx, by = pts[-7]; a = math.atan2(tip[1]-by, tip[0]-bx); L = width*3.2
    l = (tip[0]-L*math.cos(a)+L*.75*math.sin(a), tip[1]-L*math.sin(a)-L*.75*math.cos(a))
    r = (tip[0]-L*math.cos(a)-L*.75*math.sin(a), tip[1]-L*math.sin(a)+L*.75*math.cos(a))
    d.polygon([(tip[0]+width*.6*math.cos(a), tip[1]+width*.6*math.sin(a)), l, r], fill=col)
im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
o = Image.new('RGBA', (W, H), (0, 0, 0, 0)); draw(64, (110, 52, 14, 255), o)
w = Image.new('RGBA', (W, H), (0, 0, 0, 0)); draw(40, (255, 255, 255, 255), w)
sh = o.copy(); sh = Image.merge('RGBA', (*Image.new('RGB', (W, H), (20, 10, 30)).split(), o.split()[3].point(lambda v: v // 3))).filter(ImageFilter.GaussianBlur(10))
im.alpha_composite(sh, (6, 10)); im.alpha_composite(o); im.alpha_composite(w)
im = im.crop(im.getbbox()); im.save(sys.argv[1]); print(im.size)

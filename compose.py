# Сборка ролика из готовых слоёв (так будет делать телефон): фон + герой, камера с параллаксом, дыхание, моргание, рот под речь.
import numpy as np, subprocess, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

D = 'out'; W, H, FPS, DUR = 1280, 720, 25, 7.0
bg = np.asarray(Image.open(f'{D}/layer_bg.png').convert('RGB'), np.float32) / 255
L = {k: np.asarray(Image.open(f'{D}/layer_{k}.png').convert('RGBA'), np.float32) / 255 for k in ['base', 'a', 'o', 'blink']}
SH, SW = bg.shape[:2]

# маски рта и глаз — по положению в 3D, спроецированному камерой (та же камера, что в Blender)
CAM, TGT, LENS, SENS = np.array([0.62, -2.4, 0.82]), np.array([0.0, -0.03, 0.6]), 55.0, 36.0
fw = (TGT - CAM) / np.linalg.norm(TGT - CAM); rt = np.cross(fw, [0, 0, 1]); rt /= np.linalg.norm(rt); up = np.cross(rt, fw); FX = LENS / SENS * SW
def proj(p):
    q = np.asarray(p) - CAM; z = q @ fw; return SW / 2 + FX * (q @ rt) / z, SH / 2 - FX * (q @ up) / z
def ell_mask(centers, rx, ry, blur):
    m = Image.new('L', (SW, SH), 0); dr = ImageDraw.Draw(m)
    for c in centers:
        x, y = proj(c); dr.ellipse([x - rx, y - ry, x + rx, y + ry], fill=255)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(blur)), np.float32)[..., None] / 255
EYES3 = [[-0.081, -0.142, 0.768], [0.081, -0.142, 0.768]]
MOUTH3 = [[0, -0.205, 0.655]]
M = {'a': ell_mask(MOUTH3, 34, 26, 7), 'o': ell_mask(MOUTH3, 34, 26, 7), 'blink': ell_mask(EYES3, 62, 54, 8)}
HEAD = proj([0, -0.1, 0.76])

# речь: «При-вет! Я Бар-сик. Пой-дём гу-лять?» — слоги -> форма рта
SYL = [('а', .16), ('а', .2), ('-', .22), ('а', .18), ('а', .16), ('а', .14), ('-', .3), ('о', .16), ('о', .2), ('о', .14), ('а', .22), ('-', .2)]
T0 = 1.7
def mouth_at(t):
    x = T0
    for v, d in SYL:
        if x <= t < x + d:
            if v == '-': return 'base', 0
            ph = (t - x) / d; k = np.sin(np.pi * ph)   # открылся — закрылся
            return ('a' if v == 'а' else 'o'), float(np.clip(k * 1.6, 0, 1))
        x += d
    return 'base', 0
SUB_END = T0 + sum(d for _, d in SYL)
def blink_at(t):
    for b in (0.9, 4.9):
        if b <= t < b + 0.16: return min(1.0, float(np.sin(np.pi * (t - b) / 0.16) * 1.4))
    return 0.0

def warp(img, scale, cx, cy, ox, oy, sy=1.0, ay=None):
    """Камера: увеличение вокруг (cx,cy) + сдвиг; sy — «дыхание» по вертикали вокруг ay."""
    hgt, wid = img.shape[:2]
    jj, ii = np.meshgrid(np.arange(H, dtype=np.float32), np.arange(W, dtype=np.float32), indexing='ij')
    X = (ii - W / 2) / scale + cx + ox; Y = (jj - H / 2) / scale + cy + oy
    if ay is not None: Y = ay + (Y - ay) / sy
    x0 = np.clip(X.astype(int), 0, wid - 2); y0 = np.clip(Y.astype(int), 0, hgt - 2); fx = np.clip(X - x0, 0, 1)[..., None]; fy = np.clip(Y - y0, 0, 1)[..., None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)

try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 34)
except Exception: font = ImageFont.load_default()
os.makedirs('/tmp/frames', exist_ok=True)
N = int(DUR * FPS)
feet_y = SH * 0.93
for f in range(N):
    t = f / FPS; e = 0.5 - 0.5 * np.cos(np.pi * min(1, t / DUR))
    # герой: базовый слой + подмена рта и глаз по маскам
    hero = L['base'].copy()
    mk, mw = mouth_at(t)
    if mk != 'base' and mw > 0: hero = hero * (1 - M[mk] * mw) + L[mk] * (M[mk] * mw)
    bw = blink_at(t)
    if bw > 0: hero = hero * (1 - M['blink'] * bw) + L['blink'] * (M['blink'] * bw)
    breath = 1 + 0.006 * np.sin(2 * np.pi * t / 3.2)
    # камера: медленный наезд к голове; фон сдвигается меньше (он дальше)
    s_h = (W / SW) * (1.0 + 0.085 * e); s_b = (W / SW) * (1.0 + 0.03 * e)
    cx = SW / 2 + (HEAD[0] - SW / 2) * 0.5 * e; cy = SH / 2 - 18 * e
    pan = -40 * e
    bgf = warp(bg, s_b, SW / 2 + (cx - SW / 2) * 0.45, SH / 2 + (cy - SH / 2) * 0.45, pan * 0.4, 0)
    hf = warp(hero, s_h, cx, cy, pan, 0, breath, feet_y)
    a = hf[..., 3:4]
    img = bgf * (1 - a) + hf[..., :3] * a   # прозрачность «прямая», как сохраняет Blender; тень — тёмный цвет с прозрачностью
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    if T0 - 0.1 <= t <= SUB_END + 0.4:
        dr = ImageDraw.Draw(im); txt = 'Привет! Я Барсик. Пойдём гулять?'
        tw = dr.textlength(txt, font=font); x = (W - tw) / 2; y = H - 78
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)]: dr.text((x + dx, y + dy), txt, font=font, fill=(20, 20, 20))
        dr.text((x, y), txt, font=font, fill=(255, 255, 255))
    im.save(f'/tmp/frames/{f:04d}.png')
    if f % 25 == 0: print('кадр', f, flush=True)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', '/tmp/frames/%04d.png', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', f'{D}/obrazec.mp4'], check=True)
print('готово', f'{D}/obrazec.mp4')

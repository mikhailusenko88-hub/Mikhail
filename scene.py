# «Телефон»: собирает сцену из готовой библиотеки движений — фон + клипы + рот по голосу + камера + звук.
# python scene.py [голос] -> out/scene20.mp4
import numpy as np, subprocess, os, sys, time, json, wave, glob
from PIL import Image, ImageDraw, ImageFont
t_start = time.time()
SPK = sys.argv[1] if len(sys.argv) > 1 else 'xenia'
W, H, FPS, NFC = 1280, 720, 25, 60
SW, SH = 1600, 900
bg = np.asarray(Image.open('out/clips/bg_lib.png').convert('RGB'), np.float32) / 255
_cache = {}
def clip_frame(c, v, i):
    k = (c, v, i)
    if k not in _cache:
        _cache[k] = np.asarray(Image.open('out/clips/%s_%s_%03d.webp' % k).convert('RGBA'), np.float32) / 255
    return _cache[k]

# сценарий: (клип, сколько раз, реплика)
PLAN = [('idle', 1, None), ('wave', 1, None), ('talk', 1, 'l1'), ('look', 1, None), ('talk', 2, 'l2'), ('talk', 1, 'l3'), ('happy', 1, None), ('idle', 1, None)]
SUBS = {'l1': 'Привет! Я Барсик!', 'l2': 'Ой... Кто это там шуршит в кустах?', 'l3': 'Пойдём посмотрим! Ура!'}
TOTAL = 20.0; NF = int(TOTAL * FPS)
# раскладка по кадрам
seq = []; lines = []
for c, n, ln in PLAN:
    f0 = len(seq)
    for _ in range(n):
        for i in range(NFC): seq.append((c, i))
    if ln: lines.append((ln, f0 + 4))          # реплика начинается чуть позже начала клипа
seq = seq[:NF]
# голос: громкость по кадрам -> форма рта
def load_wav(p):
    with wave.open(p) as w: return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768, w.getframerate()
mouth = ['base'] * NF; sub = [None] * NF; audio = np.zeros(int(TOTAL * 48000) + 48000, np.float32)
for ln, f0 in lines:
    a, sr = load_wav(f'out/voice/{SPK}_{ln}.wav'); s0 = int(f0 / FPS * sr); audio[s0:s0 + len(a)] += a[:len(audio) - s0]
    hop = sr // FPS; nfr = len(a) // hop + 1; rms = np.array([np.sqrt(np.mean(a[j * hop:(j + 1) * hop] ** 2) + 1e-12) for j in range(nfr)]); rms /= rms.max()
    for j, r in enumerate(rms):
        f = f0 + j
        if f < NF:
            mouth[f] = 'a' if r > 0.5 else 'o' if r > 0.16 else 'base'; sub[f] = SUBS[ln]
    for j in range(nfr + 12):
        if 0 <= f0 + j < NF: sub[f0 + j] = SUBS[ln]
# камера: общий план — крупнее при репликах — снова общий в конце
def cam(f):
    t = f / FPS; c = seq[f][0]
    close = 1.0 if c == 'talk' else 0.0
    return close
zoom = np.array([cam(f) for f in range(NF)], np.float32)
k = np.ones(13) / 13; zoom = np.convolve(np.pad(zoom, 6, mode='edge'), k, 'valid')   # плавные наезды
HEAD = (785.0, 346.0)   # где голова в кадре 1600×900 (из проекции камеры)
try: font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 34)
except Exception: font = ImageFont.load_default()
def view(img, s, cx, cy):
    hgt, wid = img.shape[:2]
    jj, ii = np.meshgrid(np.arange(H, dtype=np.float32), np.arange(W, dtype=np.float32), indexing='ij')
    X = np.clip((ii - W / 2) / s + cx, 0, wid - 1.001); Y = np.clip((jj - H / 2) / s + cy, 0, hgt - 1.001)
    x0 = X.astype(int); y0 = Y.astype(int); fx = (X - x0)[..., None]; fy = (Y - y0)[..., None]
    return img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy
os.makedirs('/tmp/sf', exist_ok=True); [os.remove(p) for p in glob.glob('/tmp/sf/*.png')]
for f in range(NF):
    c, i = seq[f]; v = mouth[f] if c == 'talk' else 'base'
    hero = clip_frame(c, v, i)
    z = float(zoom[f]); s = (W / SW) * (1.0 + 0.42 * z); cx = SW / 2 + (HEAD[0] - SW / 2) * z * 0.9; cy = SH / 2 + (HEAD[1] - SH / 2) * z * 0.62
    sb = (W / SW) * (1.0 + 0.16 * z)
    b = view(bg, sb, SW / 2 + (cx - SW / 2) * 0.4, SH / 2 + (cy - SH / 2) * 0.4)
    h = view(hero, s, cx, cy); a = h[..., 3:4]
    img = b * (1 - a) + h[..., :3] * a
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    if sub[f]:
        d = ImageDraw.Draw(im); txt = sub[f]; tw = d.textlength(txt, font=font); x, y = (W - tw) / 2, H - 76
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2): d.text((x + dx, y + dy), txt, font=font, fill=(20, 20, 20))
        d.text((x, y), txt, font=font, fill=(255, 255, 255))
    im.save('/tmp/sf/%04d.png' % f)
a16 = (np.clip(audio[:int(TOTAL * 48000)], -1, 1) * 32767).astype(np.int16)
with wave.open('/tmp/scene.wav', 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(a16.tobytes())
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', '/tmp/sf/%04d.png', '-i', '/tmp/scene.wav', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '160k', '-shortest', 'out/scene20_%s.mp4' % SPK], check=True)
print('сборка заняла %.0f с' % (time.time() - t_start), '-> out/scene20_%s.mp4' % SPK)

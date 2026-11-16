# Текстуры декоров «под дерево» для 3D-стены на сайте (расчёт стены): из вырезок реек tex_decor (ветка paneli-render,
# tools/decor_tex.py — рейки с фото каталога, выпрямленные) собирается одна длинная полоса на артикул:
# вырезки ставятся друг за другом по длине с плавным переходом, яркость выровнена. Полоса зеркально повторяется по длине,
# у каждой рейки на стене свой сдвиг — повтор рисунка не бросается в глаза.
# python3 make_decor_tex.py <папка сайта 0f7s1eez> <папка tex_decor>  →  <сайт>/img/tex3/<артикул>.jpg + печатает DECOR для index.html
import json, os, sys
import numpy as np, cv2

SITE, SRC = sys.argv[1], sys.argv[2]
OUT = f'{SITE}/img/tex3'
SLAT = {'2': 30.0, '3': 29.5, '5': 10.5}      # ширина лица рейки, мм (как woodParts на сайте)
TW = {'2': 256, '3': 256, '5': 128}           # ширина текстуры, px
TH = 2048
STRETCH = 1.35                                # по длине рисунок чуть вытянут: длиннее период, волокна спокойнее
os.makedirs(OUT, exist_ok=True)
idx = json.load(open(f'{SRC}/index.json', encoding='utf-8'))
res = {}
for art in sorted(idx, key=lambda a: [int(p) for p in a.split('-')]):
    s = art.split('-')[0]
    crops = []
    k = 0
    while os.path.exists(f'{SRC}/{art}_{k}.jpg'):
        crops.append(cv2.imread(f'{SRC}/{art}_{k}.jpg')); k += 1
    if not crops:
        continue
    n = len(crops)
    lens = [SLAT[s] * c.shape[0] / c.shape[1] for c in crops]        # настоящая длина вырезки, мм
    total = sum(lens) * STRETCH
    cell = TH // n
    ov = int(cell * 0.14)                                             # перекрытие для плавного перехода
    lab = [cv2.cvtColor(cv2.resize(c, (TW[s], cell + ov), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB).astype(np.float32) for c in crops]
    m = np.mean([l.reshape(-1, 3).mean(0) for l in lab], axis=0)
    for l in lab:                                                     # общий тон у всех вырезок
        l += (m - l.reshape(-1, 3).mean(0))
        # убрать плавный перепад яркости вдоль и поперёк вырезки (свет на фото) — иначе на стыках видна ступенька
        L = l[..., 0]
        L -= cv2.GaussianBlur(L, (0, 0), TW[s] * 0.9) - L.mean()
    strip = np.zeros((cell * n, TW[s], 3), np.float32)
    wsum = np.zeros((cell * n, 1, 1), np.float32)
    ramp = np.ones(cell + ov, np.float32)
    ramp[:ov] = np.linspace(0, 1, ov, endpoint=False) ** 1.0
    ramp[-ov:] = np.linspace(1, 0, ov, endpoint=False)
    for i, l in enumerate(lab):
        y0 = i * cell - ov // 2
        for yy in range(cell + ov):
            y = (y0 + yy) % (cell * n)                               # последний переходит в первый: полоса бесшовна и при простом повторе
            strip[y] += l[yy] * ramp[yy]; wsum[y] += ramp[yy]
    strip /= np.maximum(wsum, 1e-6)
    out = cv2.cvtColor(np.clip(strip, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    out = cv2.resize(out, (TW[s], TH), interpolation=cv2.INTER_LANCZOS4)
    slug = art.lower()
    cv2.imwrite(f'{OUT}/{slug}.jpg', out, [cv2.IMWRITE_JPEG_QUALITY, 84, cv2.IMWRITE_JPEG_PROGRESSIVE, 1])
    avg = out.reshape(-1, 3).mean(0)[::-1]
    res[art] = ['#%02x%02x%02x' % tuple(int(round(v)) for v in avg), int(round(total))]
print('const DECOR = ' + json.dumps(res, ensure_ascii=False, separators=(',', ':')) + ';')
print('файлов:', len(res), 'размер, КБ:', sum(os.path.getsize(f'{OUT}/{f}') for f in os.listdir(OUT)) // 1024, file=sys.stderr)

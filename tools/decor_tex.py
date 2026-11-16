# Текстуры декоров реечных панелей «под дерево» из фото каталога (сайт, img/2x/<артикул>.jpg):
# находит рейку, ближайшую к центру кадра, выпрямляет её построчно (на фото панель в перспективе — рейки сходятся),
# выравнивает свет и пишет tex_decor/<артикул>.jpg (×4, Lanczos) + index.json (ratio = длина/ширина рейки на фото).
import sys, os, json, re
import numpy as np, cv2
from PIL import Image, ImageFilter

SITE = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/mikhail/0f7s1eez'
DST = sys.argv[2] if len(sys.argv) > 2 else 'tex_decor'
os.makedirs(DST, exist_ok=True)


def runs_of(mask, minw):
    out, x, n = [], 0, len(mask)
    while x < n:
        if mask[x]:
            x0 = x
            while x < n and mask[x]:
                x += 1
            if x - x0 >= minw:
                out.append((x0, x))
        x += 1
    return out


def slat_rows(a):
    H, W, _ = a.shape
    L = a @ np.array([0.299, 0.587, 0.114])
    sat = a.max(2) - a.min(2)
    wood = ((L > 62) | ((L > 40) & (sat > 22))).astype(np.uint8)
    wood = cv2.morphologyEx(wood, cv2.MORPH_CLOSE, np.ones((5, 9), np.uint8))
    wood = cv2.morphologyEx(wood, cv2.MORPH_OPEN, np.ones((9, 5), np.uint8))
    y_mid = int(H * 0.42)
    rs = runs_of(wood[y_mid] > 0, W * 0.012)
    if not rs:
        return None
    med = np.median([r[1] - r[0] for r in rs])
    rs = [r for r in rs if 0.6 * med <= r[1] - r[0] <= 1.6 * med]
    out = []
    for cur in rs:
        rows = {y_mid: cur}
        for step in (-1, 1):
            prev, y = cur, y_mid + step
            while 0 <= y < H:
                cand = [r for r in runs_of(wood[y] > 0, 0.6 * (prev[1] - prev[0])) if min(r[1], prev[1]) - max(r[0], prev[0]) > 0.7 * (prev[1] - prev[0]) and r[1] - r[0] < 1.25 * (prev[1] - prev[0])]
                if not cand:
                    break
                prev = max(cand, key=lambda r: min(r[1], prev[1]) - max(r[0], prev[0]))
                rows[y] = prev
                y += step
        out.append(rows)
    return out


def rectify(a, rows):
    ys = sorted(rows)
    y0, y1 = ys[0] + int(0.04 * len(ys)) + 4, ys[-1] - int(0.02 * len(ys)) - 2
    yy = np.arange(y0, y1)
    ws = np.array([rows[y][1] - rows[y][0] for y in yy])
    wmed = float(np.median(ws))
    wout = int(round(wmed * 0.90))
    out = np.zeros((len(yy), wout, 3))
    l = np.polyval(np.polyfit(yy, [rows[y][0] for y in yy], 2), yy)   # края рейки — сглаженные линии
    r = np.polyval(np.polyfit(yy, [rows[y][1] for y in yy], 2), yy)
    for k, y in enumerate(yy):
        m = (r[k] - l[k]) * 0.05
        xs = np.linspace(l[k] + m, r[k] - m, wout)
        x0 = np.clip(np.floor(xs).astype(int), 0, a.shape[1] - 2)
        t = (xs - x0)[:, None]
        out[k] = a[y, x0] * (1 - t) + a[y, x0 + 1] * t
    return out, wmed


def main():
    s = open(f'{SITE}/index.html', encoding='utf-8').read()
    cat = json.loads(s[s.find('const CAT=') + len('const CAT='):s.find('];', s.find('const CAT=')) + 1])
    photo = json.loads(re.search(r'const PHOTO0? = (\{.*?\});', s).group(1))
    idx = {}
    for c in cat:
        if c['c'] != 'color':
            continue
        art = c['a']
        fn = f'{SITE}/img/2x/{art}.jpg' if not os.path.exists(f'{SITE}/img/src/{art}.jpg') else f'{SITE}/img/src/{art}.jpg'
        a = np.asarray(Image.open(fn).convert('RGB')).astype(np.float64)
        slats = slat_rows(a)
        n = int(art[0])
        if len(slats) > n:      # блики в глянцевых пазах (серия 5) — оставить n самых длинных и светлых дорожек
            Lm = a @ np.array([0.299, 0.587, 0.114])
            def score(rows):
                ys = sorted(rows)
                v = np.mean([Lm[y, rows[y][0]:rows[y][1]].mean() for y in ys[::8]])
                return len(ys) * v
            keep = sorted(sorted(slats, key=score, reverse=True)[:n], key=lambda rows: rows[sorted(rows)[len(rows) // 2]][0])
            slats = keep
        if len(slats) != n:
            print(art, '!!! реек найдено', len(slats), 'ожидалось', n)
        tiles = [rectify(a, rows) for rows in slats]
        allpx = np.concatenate([t.reshape(-1, 3) for t, _ in tiles])
        mean = allpx.mean(0)
        info = []
        for i, (out, wmed) in enumerate(tiles):
            rowm = out.mean((1, 2))
            k = max(3, len(rowm) // 5)
            sm = np.convolve(np.pad(rowm, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'same')[k:-k]
            colm = out.mean((0, 2))
            kc = max(2, out.shape[1] // 4)
            cs = np.convolve(np.pad(colm, kc, mode='edge'), np.ones(2 * kc + 1) / (2 * kc + 1), 'same')[kc:-kc]
            out = out / (sm / sm.mean())[:, None, None] / (cs / cs.mean())[None, :, None]
            out = out * (mean / out.reshape(-1, 3).mean(0)).mean()        # рейки одной панели — одной яркости
            h, w = out.shape[:2]
            f = 4
            up = cv2.resize(np.clip(out, 0, 255).astype(np.uint8), (w * f, h * f), interpolation=cv2.INTER_LANCZOS4)
            Image.fromarray(up).filter(ImageFilter.UnsharpMask(radius=3, percent=60, threshold=0)).save(f'{DST}/{art}_{i}.jpg', quality=92)
            info.append(round(h / wmed, 3))
        idx[art] = {'ratio': info, 'mean': [round(float(v), 1) for v in mean]}
        print(art, 'реек', len(tiles), 'ratio', info, 'цвет', mean.round())
    json.dump(idx, open(f'{DST}/index.json', 'w'), ensure_ascii=False, indent=0)


main()

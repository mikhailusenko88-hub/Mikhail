# Готовит текстуры декоров панелей: берёт CC0-шпон Poly Haven (высокое разрешение) и приводит цвет
# к образцу из каталога (среднее и разброс в Lab). Пишет assets/decor/<декор>_diff.jpg.
# С аргументом lab=<папка> делает лист сравнения кандидатов с образцом.
import json, os, sys
import numpy as np
import cv2

ARGS = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
CFG = json.load(open('decors.json', encoding='utf-8'))
REF = json.load(open('ref/stats.json', encoding='utf-8'))
os.makedirs('assets/decor', exist_ok=True)


def src_path(aid):
    for ext in ('jpg', 'png'):
        p = f'assets/textures/{aid}/diff.{ext}'
        if os.path.exists(p):
            return p
    return None


def load_src(aid):
    p = src_path(aid)
    if not p:
        return None
    im = cv2.imread(p, cv2.IMREAD_COLOR)
    g = cv2.cvtColor(cv2.resize(im, (512, 512), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = np.abs(np.diff(g, axis=1)).mean()
    gy = np.abs(np.diff(g, axis=0)).mean()
    rot = gy > gx * 1.15          # волокна горизонтальные -> повернуть, чтобы шли вдоль V
    if rot:
        im = cv2.rotate(im, cv2.ROTATE_90_CLOCKWISE)
    print('src', aid, im.shape, 'gx/gy', round(float(gx), 2), round(float(gy), 2), 'rotated' if rot else '')
    return im


def transfer(im, ref, gain_l=1.0, max_l_gain=2.2, sat=1.0, dl=0.0):
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    m = lab.reshape(-1, 3).mean(0)
    s = lab.reshape(-1, 3).std(0) + 1e-6
    rm, rs = np.array(ref['lab_mean'], np.float32), np.array(ref['lab_std'], np.float32)
    kl = min(rs[0] * gain_l / s[0], max_l_gain)
    out = np.empty_like(lab)
    out[..., 0] = (lab[..., 0] - m[0]) * kl + rm[0] + dl
    for c in (1, 2):
        k = float(np.clip(rs[c] / s[c], 0.6, 1.6)) * sat
        out[..., c] = (lab[..., c] - m[c]) * k + (rm[c] - 128) * sat + 128
    out = np.clip(out, 0, 255).astype(np.uint8)
    return cv2.cvtColor(out, cv2.COLOR_LAB2BGR), float(kl)


def strip_preview(tex, mm_w, px_per_mm=3.2, lam_mm=24.8, gap_mm=15.2, n=3, length_mm=260, seed=1):
    rng = np.random.RandomState(seed)
    h, w = tex.shape[:2]
    k = w / mm_w                       # px текстуры на мм
    lw, gw, lh = int(lam_mm * px_per_mm), int(gap_mm * px_per_mm), int(length_mm * px_per_mm)
    out = np.full((lh, n * (lw + gw) + gw, 3), 14, np.uint8)
    for i in range(n):
        sw, sh = max(2, int(lam_mm * k)), max(2, int(length_mm * k))
        x0 = rng.randint(0, max(1, w - sw))
        y0 = rng.randint(0, max(1, h - sh))
        piece = tex[y0:y0 + sh, x0:x0 + sw]
        piece = cv2.resize(piece, (lw, lh), interpolation=cv2.INTER_AREA if sw > lw else cv2.INTER_CUBIC)
        x = gw + i * (lw + gw)
        out[:, x:x + lw] = piece
    return out


made = {}
for decor, c in CFG['decors'].items():
    im = load_src(c['src'])
    if im is None:
        print('NO SOURCE for', decor, c['src'])
        continue
    res, kl = transfer(im, REF[decor], c.get('gain_l', 0.8), c.get('max_l_gain', 2.2), c.get('sat', 1.0), c.get('dl', 0.0))
    cv2.imwrite(f'assets/decor/{decor}_diff.jpg', res, [cv2.IMWRITE_JPEG_QUALITY, 95])
    made[decor] = {'src': c['src'], 'size_mm': c.get('size_mm', 1000), 'l_gain': round(kl, 2), 'shape': list(res.shape[:2]),
                   'mean_bgr': [round(float(v), 1) for v in res.reshape(-1, 3).mean(0)]}
    print('decor', decor, made[decor])
json.dump(made, open('assets/decor/made.json', 'w'), indent=1)

if 'lab' in ARGS:
    os.makedirs(ARGS['lab'], exist_ok=True)
    for decor, cands in CFG.get('lab', {}).items():
        tiles = []
        ref = cv2.imread(f'ref/{decor}.jpg')
        if ref is not None:
            sc = 832 / ref.shape[0]
            tiles.append(cv2.resize(ref, (int(ref.shape[1] * sc), 832)))
        for aid, mm in cands:
            im = load_src(aid)
            if im is None:
                continue
            c = CFG['decors'][decor]
            res, kl = transfer(im, REF[decor], c.get('gain_l', 0.8), c.get('max_l_gain', 2.2), c.get('sat', 1.0), c.get('dl', 0.0))
            t = strip_preview(res, mm)
            cv2.putText(t, f'{aid} k{kl:.1f}', (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(t)
        if tiles:
            H = max(t.shape[0] for t in tiles)
            row = [cv2.copyMakeBorder(t, 0, H - t.shape[0], 0, 16, cv2.BORDER_CONSTANT, value=(60, 60, 60)) for t in tiles]
            sheet = np.concatenate(row, axis=1)
            cv2.imwrite(f"{ARGS['lab']}/lab_{decor}.jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
            print('lab sheet', decor, sheet.shape)

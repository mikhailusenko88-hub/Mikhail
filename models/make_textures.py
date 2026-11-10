# Текстуры декоров для 3D-моделей дизайнерам: CC0-шпон/бетон Poly Haven, цвет приведён к фото каталога (Lab).
# Выход: tex_out/<код>.jpg (512×2048, вдоль длины ламели), tex_out/small/<код>.jpg (256×1024, для GLB), tex_out/tex.json
import json, os
import numpy as np
import cv2

SRC = {'3': 'teak_veneer', '4': 'oak_veneer_02', '5': 'ash_veneer', '6': 'white_oak_veneer', '7': 'mocha_oak_veneer',
       '8': 'oak_veneer_05', '9': 'walnut_veneer_02', '10': 'american_walnut_veneer', '11': 'smoked_walnut_veneer',
       '12': 'concrete_floor_01', '13': 'european_walnut_veneer_04', '14': 'oak_veneer_04', '15': 'oak_veneer_01'}
SIZE_MM = {'oak_veneer_01': 1830, 'concrete_floor_01': 2000}
STATS = json.load(open('decor_stats.json', encoding='utf-8'))
os.makedirs('tex_out/small', exist_ok=True)


def load(aid):
    for ext in ('jpg', 'png'):
        p = f'assets/textures/{aid}/diff.{ext}'
        if os.path.exists(p):
            im = cv2.imread(p, cv2.IMREAD_COLOR)
            g = cv2.cvtColor(cv2.resize(im, (512, 512), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
            gx, gy = np.abs(np.diff(g, axis=1)).mean(), np.abs(np.diff(g, axis=0)).mean()
            if gy > gx * 1.15:                       # волокна должны идти вдоль длины (по вертикали)
                im = cv2.rotate(im, cv2.ROTATE_90_CLOCKWISE)
            return im
    return None


def transfer(im, ref):
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    m = lab.reshape(-1, 3).mean(0, dtype=np.float64).astype(np.float32)
    s = lab.reshape(-1, 3).std(0, dtype=np.float64).astype(np.float32) + 1e-6
    rm, rs = np.array(ref['lab_mean'], np.float32), np.array(ref['lab_std'], np.float32)
    out = np.empty_like(lab)
    out[..., 0] = (lab[..., 0] - m[0]) * min(rs[0] / s[0], 2.2) + rm[0]
    for c in (1, 2):
        out[..., c] = (lab[..., c] - m[c]) * float(np.clip(rs[c] / s[c], 0.6, 1.6)) + rm[c]
    return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


info = {}
for suf, aid in SRC.items():
    im = load(aid)
    if im is None:
        print('NO SOURCE', suf, aid)
        continue
    h, w = im.shape[:2]
    size_mm = SIZE_MM.get(aid, 1000)
    crop = im[:, (w - w // 4) // 2:(w - w // 4) // 2 + w // 4]   # полоса шириной 1/4 — по высоте целиком (повторяется без шва)
    res = transfer(crop, STATS[suf])
    big = cv2.resize(res, (512, 2048), interpolation=cv2.INTER_AREA)
    cv2.imwrite(f'tex_out/{suf}.jpg', big, [cv2.IMWRITE_JPEG_QUALITY, 88])
    cv2.imwrite(f'tex_out/small/{suf}.jpg', cv2.resize(big, (256, 1024), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])
    info[suf] = {'file': f'{suf}.jpg', 'name': STATS[suf]['name'], 'w_mm': size_mm / 4, 'h_mm': size_mm, 'src': aid,
                 'kb': os.path.getsize(f'tex_out/{suf}.jpg') // 1024}
    print('tex', suf, info[suf])
json.dump(info, open('tex_out/tex.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

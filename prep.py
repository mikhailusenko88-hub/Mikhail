# Подготовка картинок для «картинка → 3D» (менеджер, 18.11.2026): голова героя с обложки — чистая, с жёсткой маской, без чужого.
# 1) вырезка из обложки (cfg.json: box) увеличивается в 4 раза;
# 2) маска — нейросеть BiRefNet (rembg, «birefnet-general»), для сравнения — isnet-anime;
# 3) маска жёсткая: > 0,5 — герой, иначе фон; всё вне многоугольника keep — фон (чужие герои, лапы, кисти, сундук);
# 4) остаётся самая большая часть, дырки внутри заливаются; итог — in/<имя>.png (RGBA) и предпросмотры в out/prep/.
import json, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw
from rembg import remove, new_session

cfg = json.load(open('cfg.json', encoding='utf-8'))
os.makedirs('in', exist_ok=True); os.makedirs('out/prep', exist_ok=True)
MODELS = ['birefnet-general', 'isnet-anime']
sess = {m: new_session(m) for m in MODELS}
K = 4
rep = {}
for n, c in cfg.items():
    if n.startswith('_'): continue
    im = Image.open(f"covers/{c['cover']}.jpg").convert('RGB').crop(tuple(c['box']))
    big = im.resize((im.width * K, im.height * K), Image.LANCZOS)
    keep = Image.new('L', big.size, 0)
    ImageDraw.Draw(keep).polygon([(x * K / 2, y * K / 2) for x, y in c['keep']], fill=255)
    keep = np.asarray(keep) > 0
    masks = {}
    for m, s in sess.items():
        a = np.asarray(remove(big, session=s, only_mask=True).convert('L')).astype(np.float32) / 255
        masks[m] = a
        Image.fromarray((a * 255).astype(np.uint8)).save(f'out/prep/{n}_{m}.png')
    a = masks['birefnet-general']
    semi = float(((a > 0.08) & (a < 0.92) & keep).sum() / max(1, ((a > 0.08) & keep).sum()))
    hard = ((a > 0.5) & keep).astype(np.uint8)
    nl, lab, st, _ = cv2.connectedComponentsWithStats(hard, 8)
    if nl > 1: hard = (lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    h, w = hard.shape
    ff = np.pad((1 - hard).astype(np.uint8), 1, constant_values=1)     # рамка фона: фон, касающийся края, связан
    cv2.floodFill(ff, np.zeros((h + 4, w + 4), np.uint8), (0, 0), 2)
    hard[ff[1:-1, 1:-1] == 1] = 1                                       # дырки внутри головы
    hard = cv2.morphologyEx(hard, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    ys, xs = np.where(hard > 0); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    pad = int(0.06 * max(y1 - y0, x1 - x0))
    y0, x0 = max(0, y0 - pad), max(0, x0 - pad); y1, x1 = min(h, y1 + pad), min(w, x1 + pad)
    rgba = np.dstack([np.asarray(big), hard * 255]).astype(np.uint8)[y0:y1, x0:x1]
    Image.fromarray(rgba, 'RGBA').save(f'in/{n}.png')
    for col, tag in (((255, 0, 255), 'mag'), ((255, 255, 255), 'white')):
        bg = Image.new('RGBA', (x1 - x0, y1 - y0), col + (255,)); bg.alpha_composite(Image.fromarray(rgba, 'RGBA'))
        bg.convert('RGB').save(f'out/prep/{n}_{tag}.jpg', quality=90)
    rep[n] = {'size': [int(x1 - x0), int(y1 - y0)], 'semi_birefnet': round(semi, 3),
              'agree_isnet': round(float((((masks['isnet-anime'] > 0.5) & keep) == ((a > 0.5) & keep)).mean()), 4)}
    print(n, rep[n], flush=True)
json.dump(rep, open('out/prep/prep.json', 'w'), ensure_ascii=False, indent=1)

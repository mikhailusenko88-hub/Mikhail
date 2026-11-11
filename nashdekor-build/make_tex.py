#!/usr/bin/env python3
"""Текстуры дерева и бетона для 3D (img/tex/<файл>, 64×1024) из фото товара.
Берёт ламель ближе к центру кадра, обрезает края, выравнивает свет по ширине и высоте, делает бесшовной по высоте.
Источник — фото в 2 раза крупнее (img/2x/, нейросеть), чтобы текстура была чёткой (11.11.2026; раньше 64×512 с зеркальным швом).
Запуск из корня репозитория: python3 nashdekor-build/make_tex.py 0f7s1eez/img/2x 0f7s1eez/img/tex <файлы панелей под дерево>"""
import sys, os, json, re
import numpy as np
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]; os.makedirs(dst, exist_ok=True)
names = sys.argv[3:]
OUT_W, OUT_H = 64, 1024   # ширина как у ламели в масштабе (не растягивать рисунок вширь)
def slat_box(a):
    H, W, _ = a.shape
    bg = np.abs(a - np.array([38, 41, 46])).sum(2) < 36
    L = a @ np.array([0.299, 0.587, 0.114])
    wood = (~bg) & (L > 55)
    band = wood[int(H * .25):int(H * .85)]
    colf = band.mean(0)
    runs, x = [], 0
    while x < W:
        if colf[x] > .85:
            x0 = x
            while x < W and colf[x] > .85: x += 1
            runs.append((x0, x))
        x += 1
    runs = [r for r in runs if r[1] - r[0] >= W * 0.03]
    if not runs: return None
    cx = W / 2
    x0, x1 = min(runs, key=lambda r: (abs((r[0] + r[1]) / 2 - cx) - (r[1] - r[0]) * 2))
    rowf = wood[:, x0:x1].mean(1)
    ys = np.where(rowf > .95)[0]
    y0, y1 = ys.min(), ys.max()
    m = int((x1 - x0) * .14); mh = int((y1 - y0) * .03)
    return x0 + m, y0 + mh, x1 - m, y1 - mh
for n in names:
    im = Image.open(os.path.join(src, n)).convert('RGB'); a = np.asarray(im).astype(float)
    b = slat_box(a)
    if not b: print(n, 'ламель не найдена'); continue
    x0, y0, x1, y1 = b
    crop = a[y0:y1, x0:x1]
    # выровнять свет по ширине и высоте ламели (убрать градиент рендера), цвет — средний как на фото
    mean = crop.reshape(-1, 3).mean(0)
    colm = crop.mean((0, 2)); colm = colm / colm.mean()
    rowm = crop.mean((1, 2)); k = max(3, len(rowm) // 8)
    rows = np.convolve(np.pad(rowm, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'same')[k:-k]; rows = rows / rows.mean()
    crop = crop / colm[None, :, None] / rows[:, None, None]
    t = Image.fromarray(np.clip(crop, 0, 255).astype(np.uint8)).resize((OUT_W, OUT_H + OUT_H // 8), Image.LANCZOS)
    t = np.asarray(t).astype(float); ov = OUT_H // 8
    alpha = np.linspace(0, 1, ov)[:, None, None]
    out = t[:OUT_H].copy(); out[:ov] = t[OUT_H:OUT_H + ov] * (1 - alpha) + t[:ov] * alpha   # бесшовный стык по высоте
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(os.path.join(dst, n), quality=90)
    print(n, 'ламель', (int(x0), int(y0), int(x1), int(y1)), 'средний цвет', mean.round())

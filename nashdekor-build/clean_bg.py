#!/usr/bin/env python3
"""Выравнивание синего фона на каталожных фото ARTDEC.

Что делает: все пиксели синего фона приводит к одному цвету сайта (#16233F),
убирает светлые блики и перепады освещения фона; тени от изделия рядом с ним
оставляет (они дают объём), дальше 120 px от изделия фон ровный.
Изделие (белое, дерево, чёрная основа, пол) не трогает.

Использование: clean_bg.py <src_dir> <dst_dir> [имена файлов…]
"""
import sys, os
import numpy as np
from PIL import Image
from scipy import ndimage

TARGET = np.array([0x16, 0x23, 0x3F], dtype=float)   # #16233F — фон карточек на сайте


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def clean(src, dst):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(float)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(2); mn = a.min(2)
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    # мягкая маска фона: синий оттенок и заметная насыщенность
    w = ss(10, 22, B - R) * ss(0.22, 0.32, s) * ss(-2, 4, B - G)
    bg = w > 0.5
    if bg.mean() < 0.05:
        im.save(dst, quality=92); return "фон не найден — скопировано"
    L = 0.299 * R + 0.587 * G + 0.114 * B
    Lmed = np.median(L[bg])
    # расстояние от изделия (не-фон): тени оставляем только рядом с ним
    prod = ~bg
    prod = ndimage.binary_opening(prod, iterations=2)          # убрать одиночные точки в фоне
    d = ndimage.distance_transform_edt(~prod)
    keep = 1 - ss(30, 120, d)                                   # 1 у изделия → 0 вдали
    k = np.minimum(1.0, L / max(Lmed, 1))                       # темнее медианы — тень, светлее — блик (срезаем)
    k = 1 - (1 - k) * keep                                      # вдали тени не нужны
    k = np.clip(k, 0.35, 1)
    newbg = TARGET[None, None, :] * k[..., None]
    out = a * (1 - w[..., None]) + newbg * w[..., None]
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(dst, quality=92, subsampling=0)
    return "фон %.0f%%, медиана L=%.0f" % (bg.mean() * 100, Lmed)


if __name__ == "__main__":
    src_dir, dst_dir = sys.argv[1], sys.argv[2]
    names = sys.argv[3:] or sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".jpg"))
    os.makedirs(dst_dir, exist_ok=True)
    for n in names:
        print(n, "—", clean(os.path.join(src_dir, n), os.path.join(dst_dir, n)))

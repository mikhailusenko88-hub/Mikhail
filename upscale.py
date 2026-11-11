#!/usr/bin/env python3
"""Увеличение фото товаров в 2 раза: Real-ESRGAN (x4) → уменьшение Lanczos до x2 → лёгкая резкость.
Аргументы: "<имя> model=general|x4plus|both files=a.jpg,b.jpg|all scale=2" <папка фото> <папка весов>"""
import os, sys, time
import numpy as np, torch
from PIL import Image, ImageFilter
from spandrel import ModelLoader

spec, src, wdir = sys.argv[1], sys.argv[2], sys.argv[3]
parts = spec.split(); name = parts[0]; opt = dict(p.split('=', 1) for p in parts[1:])
models = ['general', 'x4plus'] if opt.get('model', 'general') == 'both' else [opt.get('model', 'general')]
scale = float(opt.get('scale', 2))
files = sorted(f for f in os.listdir(src) if f.endswith('.jpg')) if opt.get('files', 'all') == 'all' else opt['files'].split(',')
torch.set_num_threads(os.cpu_count() or 4)
out = os.path.join('out', name); os.makedirs(out, exist_ok=True)

def run(desc, im):
    x = torch.from_numpy(np.asarray(im).astype(np.float32) / 255).permute(2, 0, 1)[None]
    tile, pad, sc = 256, 16, desc.scale
    _, _, H, W = x.shape; y = torch.zeros(1, 3, H * sc, W * sc)
    with torch.no_grad():
        for t in range(0, H, tile):
            for l in range(0, W, tile):
                t0, l0 = max(t - pad, 0), max(l - pad, 0); t1, l1 = min(t + tile + pad, H), min(l + tile + pad, W)
                o = desc.model(x[:, :, t0:t1, l0:l1]).clamp(0, 1)
                y[:, :, t * sc:min(t + tile, H) * sc, l * sc:min(l + tile, W) * sc] = o[:, :, (t - t0) * sc:(t - t0 + min(tile, H - t)) * sc, (l - l0) * sc:(l - l0 + min(tile, W - l)) * sc]
    return Image.fromarray((y[0].permute(1, 2, 0).numpy() * 255).round().astype(np.uint8))

for m in models:
    model = ModelLoader().load_from_file(os.path.join(wdir, m + '.pth')).eval()
    os.makedirs(os.path.join(out, m), exist_ok=True)
    for f in files:
        t = time.time(); im = Image.open(os.path.join(src, f)).convert('RGB')
        big = run(model, im)
        W, H = round(im.width * scale), round(im.height * scale)
        res = big.resize((W, H), Image.LANCZOS)
        res.save(os.path.join(out, m, f), quality=88, optimize=True, progressive=True, subsampling=0)
        print(f'{m} {f} {im.size} -> {res.size} {time.time() - t:.1f}s', flush=True)

# сравнение: кусок 100 % — исходник (Lanczos x2) | general | x4plus
for f in files[:12]:
    im = Image.open(os.path.join(src, f)).convert('RGB'); W, H = im.width * 2, im.height * 2
    cols = [im.resize((W, H), Image.LANCZOS)] + [Image.open(os.path.join(out, m, f)) for m in models]
    cw, ch = 520, 420; x0, y0 = W // 2 - cw // 2, H // 2 - ch // 2
    sheet = Image.new('RGB', (cw * len(cols) + 10 * (len(cols) - 1), ch), 'white')
    for i, c in enumerate(cols):
        sheet.paste(c.crop((x0, y0, x0 + cw, y0 + ch)), (i * (cw + 10), 0))
    sheet.save(os.path.join(out, 'compare_' + f), quality=90)

# Наборы для Авито от 16.11.2026: первые два фото — как на сайте (карточка товара: главное и второе из карусели),
# остальные шесть — из прежнего набора. Михаил: «чтобы они точно так же главные были на Авито».
# Фото сайта 1580×898 (тёмный фон) дополняются тем же фоном до 4:3 и приводятся к 1600×1200, как остальные фото набора:
# в выдаче Авито главное фото обрезается до 4:3, без полей у товара срезало бы края.
# На 3D-отрезках реек под дерево — подпись «3D-визуализация» (правило выкладки); A910 и A703 на сайте — фото живых образцов, без подписи.
# Запуск: python3 assemble_v7.py <папка img/2x сайта из ветки mebel>
import sys, os, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SITE = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/site_mebel/0f7s1eez/img/2x'
FONT = '/usr/share/fonts/opentype/inter/Inter-Medium.otf'
if not os.path.exists(FONT):
    FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
W, H = 1600, 1200
# артикул: (новая папка, прежняя папка, подпись)
SETS = {
    '3-7': ('3-7v5', '3-7v4', '3D-визуализация'),
    '3-15': ('3-15v5', '3-15v4', '3D-визуализация'),
    '3-9': ('3-9v5', '3-9v4', '3D-визуализация'),
    'A910': ('A910v6', 'A910v5', ''),
    'A703': ('A703v5', 'A703v4', ''),
}


def pad43(src, dst, caption):
    im = Image.open(src).convert('RGB')
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    th = round(w * 3 / 4)
    top = (th - h) // 2
    bot = th - h - top
    # поля — продолжение крайних строк фона, сглаженное вдоль строки, чтобы не было полос
    def bar(rows, n):
        line = rows.mean(axis=0)                                  # (w, 3)
        k = 81
        pad = np.pad(line, ((k // 2, k // 2), (0, 0)), mode='edge')
        ker = np.ones(k, np.float32) / k
        sm = np.stack([np.convolve(pad[:, c], ker, mode='valid') for c in range(3)], axis=1)
        return np.repeat(sm[None, :, :], n, axis=0)
    out = np.concatenate([bar(a[:6], top), a, bar(a[-6:], bot)], axis=0)
    # лёгкий шум в полях, чтобы стык с зерном фото не читался
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 0.6, out.shape).astype(np.float32)
    mask = np.zeros(out.shape[:2], np.float32); mask[:top] = 1; mask[top + h:] = 1
    out = out + noise * mask[..., None]
    res = Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    if caption:
        fs = max(13, round(W * 0.0125))
        f = ImageFont.truetype(FONT, fs)
        ov = Image.new('RGBA', res.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        x, y = round(W * 0.018), H - round(W * 0.018) - fs
        d.text((x + 1, y + 1), caption, font=f, fill=(0, 0, 0, 90))
        d.text((x, y), caption, font=f, fill=(255, 255, 255, 185))
        res = Image.alpha_composite(res.convert('RGBA'), ov).convert('RGB')
    res.save(dst, quality=92, subsampling=0, optimize=True)
    return dst


if __name__ == '__main__':
    for art, (new, old, cap) in SETS.items():
        d = os.path.join('avito_foto', new)
        os.makedirs(d, exist_ok=True)
        pad43(os.path.join(SITE, art + '.jpg'), os.path.join(d, '1.jpg'), cap)
        pad43(os.path.join(SITE, art + '_2.jpg'), os.path.join(d, '2.jpg'), cap)
        for i in range(3, 9):
            shutil.copyfile(os.path.join('avito_foto', old, f'{i}.jpg'), os.path.join(d, f'{i}.jpg'))
        print(new, sorted(os.listdir(d)), [os.path.getsize(os.path.join(d, f'{i}.jpg')) // 1024 for i in (1, 2)], 'КБ')

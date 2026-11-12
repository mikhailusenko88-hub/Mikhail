# Главное фото плинтуса в фирменном стиле: кадр + полоса «Антрацит» слева с сечением и размерами (без логотипа — для Авито).
# python3 main_inset.py <кадр 1600x1200> <выход.jpg> [доля_сдвига_кадра 0..1, по умолчанию 0.5]
import sys
from PIL import Image, ImageDraw, ImageFont

ANTH, BLUE, HAZE, SUBD = (0x26, 0x29, 0x2E), (0x7E, 0x97, 0xAD), (0xD9, 0xDE, 0xE3), (0xC3, 0xCA, 0xD2)
FD = '/usr/share/fonts/opentype/inter/'
S = 2
W, H, STRIP = 1600, 1200, 380
A703 = [[0.0, 6.99], [9.97, 15.0], [80.0, 15.0], [80.0, 9.82], [65.01, 9.82], [65.01, 0.0], [60.92, 0.0], [60.73, 0.57], [60.11, 0.93],
        [59.41, 0.74], [59.17, 0.47], [59.04, 0.0], [54.78, 0.0], [54.78, 9.82], [13.28, 9.79], [12.37, 9.54], [11.57, 9.08],
        [10.66, 8.05], [10.3, 7.2], [10.17, 6.25], [10.17, 0.0], [5.97, 0.0], [5.7, 0.66], [5.16, 0.93], [4.45, 0.74], [4.16, 0.36],
        [4.09, 0.0], [0.0, 0.0]]


def font(sz, w='Regular'):
    return ImageFont.truetype(f'{FD}Inter-{w}.otf', int(sz * S))


def arrow(d, x, y, dx, dy, col):
    a = 7 * S
    nx, ny = -dy, dx
    d.polygon([(x, y), (x + dx * a * 1.8 + nx * a * 0.5, y + dy * a * 1.8 + ny * a * 0.5),
               (x + dx * a * 1.8 - nx * a * 0.5, y + dy * a * 1.8 - ny * a * 0.5)], fill=col)


def make(src, dst, shift=0.5):
    ph = Image.open(src).convert('RGB').resize((W, H), Image.LANCZOS)
    cw = W - STRIP
    x0 = int((W - cw) * shift)
    im = Image.new('RGB', (W * S, H * S), ANTH)
    im.paste(ph.crop((x0, 0, x0 + cw, H)).resize((cw * S, H * S), Image.LANCZOS), (STRIP * S, 0))
    d = ImageDraw.Draw(im)
    # заголовок
    d.text((44 * S, 70 * S), 'Плинтус', font=font(40, 'SemiBold'), fill=(255, 255, 255))
    d.text((44 * S, 118 * S), 'напольный', font=font(40, 'SemiBold'), fill=(255, 255, 255))
    d.text((44 * S, 182 * S), 'белый · под покраску', font=font(24), fill=SUBD)
    # сечение: высота вниз, толщина вправо; стена слева
    k = 7.0
    sx, sy = 118, 330
    fy = sy + 80 * k
    d.rectangle([(sx - 40) * S, (sy - 26) * S, sx * S, fy * S], fill=(0x3A, 0x3E, 0x45))
    d.rectangle([(sx - 40) * S, fy * S, (sx + 190) * S, (fy + 22) * S], fill=(0x3A, 0x3E, 0x45))
    d.text(((sx - 20) * S, (sy - 34) * S), 'стена', font=font(17), fill=SUBD, anchor='ms')
    d.text(((sx + 120) * S, (fy + 48) * S), 'пол', font=font(17), fill=SUBD, anchor='ms')
    poly = [((sx + t * k) * S, (sy + u * k) * S) for u, t in A703]
    d.polygon(poly, fill=(250, 250, 248))
    # высота
    xv = sx + 15 * k + 34
    for y in (sy, fy):
        d.line([((xv - 11) * S, y * S), ((xv + 11) * S, y * S)], fill=BLUE, width=S)
        d.line([((sx + 15 * k + 6) * S, y * S), ((xv - 4) * S, y * S)], fill=(0x55, 0x5C, 0x66), width=S)
    d.line([(xv * S, sy * S), (xv * S, fy * S)], fill=BLUE, width=S)
    arrow(d, xv * S, sy * S, 0, 1, BLUE)
    arrow(d, xv * S, fy * S, 0, -1, BLUE)
    pill(d, xv + 14, (sy + fy) / 2, '80 мм')
    # толщина
    yh = sy - 70
    for x in (sx, sx + 15 * k):
        d.line([(x * S, (yh - 11) * S), (x * S, (yh + 11) * S)], fill=BLUE, width=S)
    d.line([(sx * S, yh * S), ((sx + 15 * k) * S, yh * S)], fill=BLUE, width=S)
    pill(d, sx + 15 * k + 20, yh, '15 мм')
    d.text((44 * S, (fy + 92) * S), 'Длина 2 м', font=font(26, 'Medium'), fill=(255, 255, 255))
    d.text((44 * S, (fy + 130) * S), 'Сзади — канал для кабеля', font=font(20), fill=SUBD)
    d.text((44 * S, (fy + 158) * S), 'Сверху — фаска', font=font(20), fill=SUBD)
    d.text(((STRIP + 22) * S, (H - 22) * S), '3D-визуализация', font=font(17, 'Medium'), fill=(255, 255, 255, 190), anchor='ls')
    im.resize((W, H), Image.LANCZOS).save(dst, quality=92, subsampling=0, optimize=True)


def pill(d, x, y, s):
    f = font(24, 'SemiBold')
    l, t, r, b = d.textbbox((0, 0), s, font=f)
    w, h = (r - l) / S + 22, (b - t) / S + 14
    d.rounded_rectangle([x * S, (y - h / 2) * S, (x + w) * S, (y + h / 2) * S], radius=8 * S, fill=HAZE)
    d.text(((x + w / 2) * S, y * S), s, font=f, fill=ANTH, anchor='mm')


if __name__ == '__main__':
    make(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.5)
    print('ok', sys.argv[2])

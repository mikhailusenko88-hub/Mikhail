#!/usr/bin/env python3
"""Значок сайта для мелких размеров (favicon) — знак «Галерея», утверждён 11.11.2026.

Тот же знак, что в логотипе (две вложенные рамки, большая и малая), но:
- крупнее в квадрате (≈ 88 % ширины вместо 50 %), чтобы читался в выдаче Яндекса/Google (16–18 px) и во вкладке;
- линии привязаны к пиксельной сетке: 32 px — рамки 2 px, внутренние 1 px; 16 px — отдельная попиксельная версия;
- фон «Антрацит» со скруглением 1/8 стороны.

Пишет: files/site/favicon.ico (16/32/48/96/144), files/site/icon.svg, files/svg/favicon-small.svg,
files/svg/favicon-16.svg, files/png/favicon-small-{16,32,48,96,120,144,192}.png.
Слои 96 и 144 в favicon.ico (с 14.11.2026) — для Google: он просит значок крупнее 48×48 и сам уменьшает его
до 16–28 px в выдаче; браузеры во вкладке по-прежнему берут 16/32 (или icon.svg).
Нужен rsvg-convert (пакет librsvg2-bin) и Pillow. Запуск: python3 brand/favicon.py
Иконки «на экран Домой» (apple-touch-icon, icon-192/512) остаются из build.py — знак там с полями, как в логотипе."""
import os, subprocess
from PIL import Image

A, G, B = "#26292E", "#F8F8F6", "#7E97AD"   # Антрацит, Галерея, Серо-голубой
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files")

# Сетка 32: координаты — по осям линий (рамка 2 px с центром на целом, 1 px — на половинке)
SVG32 = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">'
         f'<rect width="32" height="32" rx="4" fill="{A}"/><g fill="none">'
         f'<rect x="3" y="6" width="14" height="20" stroke="{G}" stroke-width="2"/>'        # большая рамка
         f'<rect x="5.5" y="8.5" width="9" height="15" stroke="{B}"/>'                       # большая внутренняя
         f'<rect x="21" y="10" width="8" height="12" stroke="{G}" stroke-width="2"/>'      # малая рамка
         f'<rect x="23.5" y="12.5" width="3" height="7" stroke="{B}"/></g></svg>')          # малая внутренняя

# Сетка 16: попиксельно (рамки 1 px, малая внутренняя — штрих 1×2)
SVG16 = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">'
         f'<rect width="16" height="16" rx="2" fill="{A}"/><g fill="none" shape-rendering="crispEdges">'
         f'<rect x="1.5" y="2.5" width="7" height="11" stroke="{G}"/>'
         f'<rect x="3.5" y="4.5" width="3" height="7" stroke="{B}"/>'
         f'<rect x="10.5" y="5.5" width="4" height="5" stroke="{G}"/></g>'
         f'<rect x="12" y="7" width="1" height="2" fill="{B}"/></svg>')


def render(svg_path, px, out):
    subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px), svg_path, "-o", out], check=True)


def main():
    for d in ("svg", "png", "site"):
        os.makedirs(f"{OUT}/{d}", exist_ok=True)
    s32, s16 = f"{OUT}/svg/favicon-small.svg", f"{OUT}/svg/favicon-16.svg"
    open(s32, "w").write(SVG32); open(s16, "w").write(SVG16)
    open(f"{OUT}/site/icon.svg", "w").write(SVG32)
    png = lambda px: f"{OUT}/png/favicon-small-{px}.png"
    render(s16, 16, png(16))
    for px in (32, 48, 96, 120, 144, 192):
        render(s32, px, png(px))
    ico = (144, 96, 48, 32, 16)  # первый — самый крупный (Pillow не увеличивает)
    ims = [Image.open(png(px)).convert("RGBA") for px in ico]
    ims[0].save(f"{OUT}/site/favicon.ico", format="ICO", sizes=[(px, px) for px in ico], append_images=ims[1:])
    print("favicon: готово")


if __name__ == "__main__":
    main()

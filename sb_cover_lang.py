#!/usr/bin/env python3
"""Обложка сборника на языке дубляжа (27.11.2026): как studio/sborniki/kollazh.py, но карточки — обложки серий на этом языке
(dub-files/<сборка>/cover_<язык>.jpg), надписи на языке. Строка sbcover-request.txt:
  <имя сборника> <язык> <минуты> <сборка1> … <сборка5>     например: sb-32-36 fr 28 32dub 33dub 34dub 35d 36f
Итог: out_cover/<имя>/cover_<язык>.jpg"""
import os, sys, glob, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
TXT = {"fr": ("5 ÉPISODES D'AFFILÉE !", "{m} minutes"), "ar": ("5 حلقات متتالية!", "{m} دقيقة"),
       "en": ("5 EPISODES IN A ROW!", "{m} minutes"), "es": ("¡5 EPISODIOS SEGUIDOS!", "{m} minutos"),
       "pt": ("5 EPISÓDIOS SEGUIDOS!", "{m} minutos"), "de": ("5 FOLGEN AM STÜCK!", "{m} Minuten")}
def font(lang, px):
    if lang == "ar":
        for pat in ["NotoSansArabic-Black.ttf", "NotoSansArabic-ExtraBold.ttf", "NotoSansArabic-Bold.ttf", "NotoKufiArabic-Bold.ttf"]:
            f = glob.glob(f"/usr/share/fonts/**/{pat}", recursive=True)
            if f:
                return ImageFont.truetype(f[0], int(px * 0.9), layout_engine=ImageFont.Layout.RAQM)
    for p in ["/usr/share/fonts/truetype/inter/Inter-Black.ttf", "/usr/share/fonts/opentype/inter/Inter-Black.otf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    raise SystemExit("нет шрифта")
def main(line):
    name, lang, mins, *builds = line.split()
    W, H = 1280, 720
    bg = Image.new("RGB", (W, H)); d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H; d.line([(0, y), (W, y)], fill=(int(120 + 110 * t), int(190 + 50 * t), int(240 + 12 * t)))
    def card(b, cx, cy, w, ang):
        p = f"df/{b}/cover_{lang}.jpg"
        im = Image.open(p).convert("RGB").resize((w, int(w * 9 / 16)), Image.LANCZOS)
        bd = 8; c = Image.new("RGBA", (im.width + 2 * bd, im.height + 2 * bd), (255, 255, 255, 255)); c.paste(im, (bd, bd))
        m = Image.new("L", c.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, c.width - 1, c.height - 1], 18, fill=255); c.putalpha(m)
        c = c.rotate(ang, resample=Image.BICUBIC, expand=True)
        sh = Image.new("RGBA", c.size, (0, 0, 0, 0)); sh.putalpha(c.split()[3].point(lambda a: a * 0.35)); sh = sh.filter(ImageFilter.GaussianBlur(10))
        bg.paste(sh, (cx - c.width // 2 + 6, cy - c.height // 2 + 10), sh); bg.paste(c, (cx - c.width // 2, cy - c.height // 2), c)
    card(builds[0], 225, 260, 400, 3); card(builds[1], 640, 245, 400, -1.5); card(builds[2], 1055, 262, 400, -3)
    card(builds[3], 420, 548, 430, 2); card(builds[4], 860, 553, 430, -2)
    t1, t2 = TXT[lang]; t2 = t2.format(m=mins)
    f1 = font(lang, 64); tw = d.textlength(t1, font=f1)
    while tw > W - 200:
        f1 = font(lang, int(f1.size * 0.92) if lang != "ar" else int(f1.size / 0.9 * 0.92)); tw = d.textlength(t1, font=f1)
    x0 = (W - tw) / 2 - 44
    ban = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(ban)
    bd.rounded_rectangle([x0, 14, x0 + tw + 88, 104], 30, fill=(225, 45, 50, 255), outline=(255, 255, 255, 255), width=6)
    ty = 22 if lang != "ar" else 14
    bd.text((x0 + 44 + 3, ty + 3), t1, font=f1, fill=(120, 0, 0, 255)); bd.text((x0 + 44, ty), t1, font=f1, fill=(255, 255, 255, 255))
    ban = ban.rotate(1.2, resample=Image.BICUBIC, center=(W / 2, 60)); bg.paste(ban, (0, 0), ban)
    f2 = font(lang, 34); w2 = d.textlength(t2, font=f2)
    d.rounded_rectangle([(W - w2) / 2 - 26, 362, (W + w2) / 2 + 26, 414], 26, fill=(255, 205, 40), outline=(255, 255, 255), width=4)
    d.text(((W - w2) / 2, 366 if lang != "ar" else 360), t2, font=f2, fill=(40, 30, 10))
    out = f"out_cover/{name}"; os.makedirs(out, exist_ok=True)
    bg.save(f"{out}/cover_{lang}.jpg", quality=92); bg.resize((320, 180), Image.LANCZOS).save(f"{out}/cover_{lang}_mini.jpg", quality=90)
    print(out, lang)
if __name__ == "__main__":
    for line in open("sbcover-request.txt", encoding="utf-8"):
        if line.strip() and not line.startswith("#"):
            main(line)

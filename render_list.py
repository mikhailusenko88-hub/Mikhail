"""Карточка-список «5 мыслей» (H35, 20.11.2026): одна неподвижная карточка на весь ролик.
python3 render_list.py <день> [слот]  ->  out/<name>.mp4 + out/<name>.txt

Зачем: у быстрых соседей-цитатников (Психология людей «6 МУДРЫХ ЦИТАТ О ЖИЗНИ» — 138 тыс. за 1,5 дня,
Между строк, zdoroviedushi) весь ролик — одна светлая карточка со списком; у Почерка тишины такой ролик
набрал в 3,5 раза больше медианы. У Living Lines — три цитаты по очереди, уходят на первой.
В плане такие ролики помечены "kind": "list": "header" — заголовок карточки (строки), "quotes" — ключи банка (до 6),
"scenes" — одна акварель под списком, "music" — оркестровый стиль.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import fastvid as fv
import orchestra as orchestra_mod
import quotecard as qc
from quotes_bank import QUOTES

HERE = Path(__file__).parent
OUT = HERE / "out"
W, H, FPS = qc.W, qc.H, qc.FPS

INK = (34, 28, 25, 255)          # текст цитат
AUTH = (112, 96, 84, 255)      # автор
ACCENT = (120, 82, 50)           # кружки с номерами, заголовок
X_NUM, X_TXT, X_MAX = 92, 172, 958   # правее 958 — кнопки Shorts (лайк, комментарии)
LIST_TOP = 418


def flat(s):
    return s if isinstance(s, str) else " ".join(s)


def author_short(a):
    return a.split("  ·  ")[0]


def layout(items, size):
    f_q = qc.font(qc.F_RU, size)
    f_a = qc.font(qc.F_SMALL, max(25, int(size * 0.70)))
    blocks, y = [], LIST_TOP
    for k, (ru, au) in enumerate(items):
        lines = qc.wrap_text(ru, f_q, X_MAX - X_TXT)
        lh = int(size * 1.30)
        b = dict(n=k + 1, y=y, lines=lines, f_q=f_q, f_a=f_a, au=au, lh=lh)
        y += lh * len(lines) + int(size * 0.18)
        b["y_auth"] = y
        y += int(f_a.size * 1.25) + int(size * 0.62)
        blocks.append(b)
    return blocks, y


def card(v, log=print):
    items = [(flat(QUOTES[q]["ru"]), author_short(QUOTES[q]["author_ru"])) for q in v["quotes"]]
    # шрифт — самый крупный, при котором список влезает до низа зоны текста
    for size in range(48, 33, -1):
        blocks, y_end = layout(items, size)
        if y_end <= 1250:
            break
    log(f"  шрифт цитат {size}, список до {y_end}")
    canvas = qc.PAPER.copy()
    # акварель под списком — дорисована целиком с первого кадра
    px0, px1, py0, py1 = 70, 1010, y_end + 100, 1830
    fn, hor_frac = qc.SCENES[v["scenes"][0]]
    ops, _, _ = fn((px0, px1, py0, py1), int(py0 + hor_frac * (py1 - py0)), seed=v["seed"])
    for op in ops:
        t = op.t1 + 0.1
        col = op.colour(t) if isinstance(op, qc.Dots) and op.multi else op.col
        qc.apply(canvas, op.alpha(t), col, op.box, op.kind)
    img = Image.fromarray((np.clip(canvas * qc.FACT, 0, 1) * 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    # шапка: знак канала и заголовок карточки
    mark = qc.text_sprite("ЖИВЫЕ СТРОКИ  ·  LIVING LINES", qc.font(qc.F_MARK, 28, 600), (128, 110, 96, 255), spacing=5)
    img.alpha_composite(mark, (int((W - mark.size[0]) / 2), 158))
    hs = 58
    while hs > 44 and max(qc.font(qc.F_RU, hs).getlength(s) for s in v["header"]) > 930:
        hs -= 2
    f_h = qc.font(qc.F_RU, hs)
    for i, s in enumerate(v["header"]):
        spr = qc.text_sprite(s, f_h, ACCENT + (255,))
        img.alpha_composite(spr, (int((W - spr.size[0]) / 2), 206 + i * 74))
    y_div = 206 + len(v["header"]) * 74 + 22
    d.rounded_rectangle([W / 2 - 90, y_div, W / 2 + 90, y_div + 4], radius=2, fill=(176, 146, 96, 220))
    # список
    f_n = qc.font(f"{qc.FONTS}/PT_Serif-Web-Bold.ttf", 34)
    for b in blocks:
        cy = b["y"] + 10 + b["lh"] / 2 - 4
        r = 30
        d.ellipse([X_NUM - r + 20, cy - r, X_NUM + r + 20, cy + r], fill=ACCENT + (255,))
        num = str(b["n"])
        tw = f_n.getlength(num)
        asc, dsc = f_n.getmetrics()
        d.text((X_NUM + 20 - tw / 2, cy - (asc + dsc) / 2 + 2), num, font=f_n, fill=(250, 244, 232, 255))
        for i, s in enumerate(b["lines"]):
            img.alpha_composite(qc.text_sprite(s, b["f_q"], INK), (X_TXT - 10, b["y"] + i * b["lh"]))
        img.alpha_composite(qc.text_sprite("— " + b["au"], b["f_a"], AUTH), (X_TXT - 10, b["y_auth"]))
    # вопрос для комментариев (как у zdoroviedushi)
    if v.get("ask"):
        spr = qc.text_sprite(v["ask"], qc.font(qc.F_EN, 40, 600), (110, 84, 62, 255))
        img.alpha_composite(spr, (int((W - spr.size[0]) / 2), y_end - 6))
    return img.convert("RGB"), sum(len(flat(QUOTES[q]["ru"]).split()) for q in v["quotes"])


def render(v, out_path, log=print):
    img, words = card(v, log)
    total = float(min(26.0, max(18.0, 4.0 + words * 0.42)))
    log(f"  слов {words}, ролик {total:.1f} с")
    writer = fv.Writer(out_path, fps=FPS)
    grain = fv.GrainPool(sigma=1.5)
    n = int(total * FPS)
    for i in range(n):
        z = 1.0 + 0.025 * i / n          # медленный наезд, как у роликов канала
        x0, y0, cw, ch = fv.camera_window(W / 2, H / 2 - 120, z)
        frame = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)
        writer.add(grain.apply(frame, i))
    audio = orchestra_mod.make_music(v["music"], total, v["seed"] + 100, [0.3])
    writer.close(audio, peak=0.7)
    return total, img


if __name__ == "__main__":
    day = int(sys.argv[1])
    slot = int(sys.argv[2]) if len(sys.argv) > 2 else None
    OUT.mkdir(exist_ok=True)
    for v in json.loads((HERE / "schedule_30d.json").read_text(encoding="utf-8")):
        if v["day"] != day or v.get("kind") != "list" or (slot and v["slot"] != slot):
            continue
        print(f"== {v['name']} {v['date']} {v['time']} | {v['quotes']} | {v['scenes']} | {v['music']}", flush=True)
        total, img = render(v, str(OUT / f"{v['name']}.mp4"))
        img.save(OUT / f"{v['name']}_card.jpg", quality=90)
        (OUT / f"{v['name']}.txt").write_text(v["title"] + "\n\n" + v["description"] + "\n", encoding="utf-8")

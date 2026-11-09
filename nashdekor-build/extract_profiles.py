#!/usr/bin/env python3
"""Снять профили (сечения) молдингов, плинтусов, карнизов и уголков из PDF-каталога ARTDEC.

В каталоге рядом с каждым артикулом нарисован тёмно-синий силуэт сечения — векторный путь (заливка CMYK ≈ 0.98/0.79/0.47/0.50).
Скрипт берёт эти пути, сопоставляет с артикулами (таблица MAP — проверена глазами по подписям 09.11.2026),
переводит в мм по габаритам из каталога сайта (ширина × толщина из CAT в index.html) и пишет profiles-mold.json:
  { "A002": {"w": 40, "t": 19, "outer": [[x, y], …], "holes": [[[x, y], …], …]}, … }
x — вдоль ширины изделия (для плинтуса — вдоль высоты, слева в каталоге — верх), y — рельеф от стены (0 — стена).
Запуск: python3 nashdekor-build/extract_profiles.py <каталог.pdf>
"""
import sys, os, json, re
import pdfplumber

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "0f7s1eez")
PDF = sys.argv[1]

# порядок силуэтов на страницах 13–27 каталога ArtDec 2026 (34 стр.) → артикул
MAP = ["A002", "A002/2", "A35", "A35/2", "A25", "A302", "A161", "A152", "A151", "A400", "A10", "A23", "A157", "A157/2", "A156", "A602", "A301", "A611/2",
       "A150", "A601", "A605", "A611", "A130", "A165", "A608", "A354", "A004", "A005", None, "A122", "A15", "A701", "A702", "A50", "A33", "A55", "A88", "A703",
       "A704", "A705", "A11-80", "A11-100", "AP1-100", "A707", "A12-100", "AP70", "A31", "A49", "A137", "A153", "A706", "A105", "A116", "A06", "A38", "A503",
       "A172", None, None, None, None, None, None, None, None, "A504", None]
SAME = {"A611/3": "A611", "A611/4": "A611/2"}   # те же профили, длина 3 м
CORNICE = {"A38", "A503", "A172", "A504"}

src = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
i = src.index("const CAT=") + len("const CAT="); depth = 0
for j in range(i, len(src)):
    if src[j] == "[": depth += 1
    elif src[j] == "]":
        depth -= 1
        if depth == 0: CAT = json.loads(src[i:j + 1]); break
DIM = {x["a"]: (x["w"], x["t"]) for x in CAT}

def bez(p0, p1, p2, p3, n=12):
    out = []
    for k in range(1, n + 1):
        t = k / n; u = 1 - t
        out.append((u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0], u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1]))
    return out

def subpaths(path):
    subs, cur = [], []
    for seg in path:
        op, pts = seg[0], seg[1:]
        if op == "m":
            if len(cur) > 2: subs.append(cur)
            cur = [tuple(pts[0])]
        elif op == "l": cur.append(tuple(pts[0]))
        elif op == "c": cur.extend(bez(cur[-1], pts[0], pts[1], pts[2]))
        elif op == "h":
            if len(cur) > 2: subs.append(cur)
            cur = [cur[0]] if cur else []
    if len(cur) > 2: subs.append(cur)
    return subs

def area(poly): return 0.5 * sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly)))

def simplify(pts, tol):
    if len(pts) < 3: return pts
    def dp(a, b):
        if b - a < 2: return [a, b]
        (x0, y0), (x1, y1) = pts[a], pts[b]; dx, dy = x1 - x0, y1 - y0; L = (dx*dx + dy*dy) ** .5 or 1e-9
        far, idx = 0, a
        for k in range(a + 1, b):
            d = abs(dy * pts[k][0] - dx * pts[k][1] + x1*y0 - y1*x0) / L
            if d > far: far, idx = d, k
        return dp(a, idx)[:-1] + dp(idx, b) if far > tol else [a, b]
    # замкнутый контур: убрать повтор первой точки и упрощать двумя половинами (от первой точки до самой дальней)
    if pts[0] == pts[-1]: pts = pts[:-1]
    far = max(range(len(pts)), key=lambda k: (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2)
    keep = dp(0, far)[:-1] + dp(far, len(pts) - 1)
    return [pts[k] for k in keep]

pdf = pdfplumber.open(PDF)
sil = []
for pi in range(11, 34):
    p = pdf.pages[pi]
    for o in p.curves + p.rects:
        c = o.get("non_stroking_color")
        if not o.get("fill") or not c or len(c) != 4 or not (c[0] > 0.9 and 0.7 < c[1] < 0.9 and 0.4 < c[2] < 0.6): continue
        if o["x1"] - o["x0"] < 16 or o["bottom"] - o["top"] < 6: continue
        sil.append(o)
assert len(sil) == len(MAP), (len(sil), len(MAP))

out = {}
for o, a in zip(sil, MAP):
    if not a: continue
    W, T = DIM[a]
    subs = [s for s in subpaths(o["path"]) if abs(area(s)) > 1]
    xs = [x for s in subs for x, _ in s]; ys = [y for s in subs for _, y in s]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cornice = a in CORNICE
    if cornice:   # в каталоге карниз нарисован как в углу: стена слева, потолок сверху; масштаб один по обеим осям (по высоте W)
        k = W / (y1 - y0); T = round((x1 - x0) * k, 1)
    def mm(s):
        if cornice: pts = [(round((y - y0) * k, 2), round((x - x0) * k, 2)) for x, y in s]   # x — вниз по стене от потолка, y — вылет от стены
        else: pts = [(round((x - x0) / (x1 - x0) * W, 2), round((y1 - y) / (y1 - y0) * T, 2)) for x, y in s]
        pts = simplify(pts, 0.08)
        if pts[0] == pts[-1]: pts = pts[:-1]
        return [list(p) for p in pts]
    subs.sort(key=lambda s: -abs(area(s)))
    out[a] = {"w": W, "t": T, "outer": mm(subs[0]), "holes": [mm(s) for s in subs[1:]]}
    if cornice: print("  карниз", a, "высота", W, "вылет по чертежу", T, "(в каталоге толщина", DIM[a][1], ")")
for a, b in SAME.items():
    out[a] = dict(out[b], w=DIM[a][0], t=DIM[a][1])
json.dump(out, open(os.path.join(HERE, "profiles-mold.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("профилей:", len(out), "точек всего:", sum(len(v["outer"]) + sum(len(h) for h in v["holes"]) for v in out.values()))
for a, v in out.items():
    if v["holes"]: print("  с отверстиями:", a, len(v["holes"]))

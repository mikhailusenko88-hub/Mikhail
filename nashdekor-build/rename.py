#!/usr/bin/env python3
"""Переименовать товары в CAT (0f7s1eez/index.html) по единой формуле из документа
«Наш декор — запросы, названия, страницы, продвижение» (09.11.2026):
  {Тип} {артикул} {покрытие или цвет}, {Ш}×{Т}×{Д} мм
Материал в описании — «дюрополимер» (полистирол высокой плотности). Запуск из корня репозитория, потом build.py.
"""
import json, os, re

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "0f7s1eez")
p = os.path.join(SITE, "index.html")
src = open(p, encoding="utf-8").read()
i = src.index("const CAT=") + len("const CAT="); depth = 0
for j in range(i, len(src)):
    if src[j] == "[": depth += 1
    elif src[j] == "]":
        depth -= 1
        if depth == 0: end = j + 1; break
CAT = json.loads(src[i:end])

def dims(x): return "%d×%d×%d мм" % (x["w"], x["t"], x["l"])

for x in CAT:
    a, c, d = x["a"], x["c"], x["d"]
    first = d.split(",")[0].strip()          # «широкие ламели с тонкими швами» / «дуб натуральный» / «40×19×2000 мм»
    led = "LED" in d or "подсветк" in d
    cable = "канал" in d
    if c == "panel":
        x["n"] = "Реечная панель %s белая под покраску, %s" % (a, dims(x))
        x["d"] = "%s, %s, дюрополимер, под покраску — белая, красится в любой цвет" % (first, dims(x))
    elif c == "color":
        x["n"] = "Реечная панель %s %s, %s" % (a, first, dims(x))
        x["d"] = "%s, %s, дюрополимер, готовый декор — красить не нужно" % (first, dims(x))
    elif c == "mold":
        extra = " с кабель-каналом" if cable else (" универсальный" if "универсальн" in d else "")
        x["n"] = "Молдинг для стен %s под покраску%s, %s" % (a, extra, dims(x))
        tail = ", сзади канал под кабель" if cable else (", подходит как молдинг, плинтус или наличник" if "универсальн" in d else "")
        x["d"] = "%s, дюрополимер, под покраску%s" % (dims(x), tail)
    elif c == "plinth":
        x["n"] = ("Плинтус напольный с подсветкой %s под покраску, %s" if led else "Плинтус напольный %s под покраску, %s") % (a, dims(x))
        x["d"] = "высота %d мм, %s, дюрополимер, под покраску%s" % (x["w"], dims(x), ", паз под LED-ленту" if led else "")
    elif c == "cornice":
        x["n"] = ("Потолочный плинтус под подсветку %s, %s" if led else "Потолочный плинтус %s под покраску, %s") % (a, dims(x))
        x["d"] = "%s, дюрополимер, под покраску%s" % (dims(x), ", ниша под LED-ленту — парящий потолок" if led else "")
    elif c == "corner":
        x["n"] = "Уголок декоративный %s под покраску, %s" % (a, dims(x))
        x["d"] = "%s, для внешних углов и торцов панелей, дюрополимер, под покраску" % dims(x)

new = json.dumps(CAT, ensure_ascii=False, separators=(",", ":"))
src = src[:i] + new + src[end:]
open(p, "w", encoding="utf-8").write(src)
print("переименовано:", len(CAT))
for x in CAT[:3] + [y for y in CAT if y["a"] in ("2-7", "A35/2", "A11-80", "A503", "A116")]: print(" ", x["n"], "|", x["d"])

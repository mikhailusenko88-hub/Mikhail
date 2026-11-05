"""Темы (лиги) гонок шариков для канала «Kim yutadi?» (Узбекистан).

Надписи — узбекский (латиница) + русский, одинаково заметно. Поле "kk" — главный язык (узбекский):
так названо, чтобы движок гонок остался тем же, что у казахского канала.
  cities — города Узбекистана («Qaysi shahar yutadi?»)
  cars   — машины, на которых ездит Узбекистан («Qaysi mashina yutadi?»)
"""
import difflib

# ---------- узбекская латиница → кириллица (только чтобы понять, отличается ли русское название) ----------
_PAIRS = [("oʻ", "у"), ("gʻ", "г"), ("o'", "у"), ("g'", "г"), ("sh", "ш"), ("ch", "ч"), ("ng", "нг"),
          ("ya", "я"), ("yo", "ё"), ("yu", "ю"), ("ye", "е")]
_ONE = str.maketrans("abdefghijklmnopqrstuvxyzʻ'", "абдефгхижклмнопкрстувхйз  ")


def uz2cyr(s):
    s = s.lower()
    for a, b in _PAIRS:
        s = s.replace(a, b)
    return s.translate(_ONE).replace(" ", "")


def kz2ru(s):          # движок зовёт это для имён — здесь просто кириллица
    return uz2cyr(s)


def differs(uz, ru):
    """Русское пишем отдельно, только если оно звучит иначе (Qoʻqon — Коканд, Jizzax — Джизак);
    Toshkent — Ташкент, Nukus — Нукус, Jiguli — Жигули — одной строкой."""
    a = uz2cyr(uz).replace("о", "а").replace("ы", "и")
    b = ru.lower().replace("о", "а").replace("ы", "и").replace("ё", "е").replace("ь", "")
    if a == b or uz.lower() == ru.lower():
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() < 0.85


# ---------- города: узбекский, русский, широта, долгота ----------
CITIES = [
    ("Toshkent", "Ташкент", 41.31, 69.28),
    ("Samarqand", "Самарканд", 39.65, 66.96),
    ("Buxoro", "Бухара", 39.77, 64.42),
    ("Namangan", "Наманган", 41.00, 71.67),
    ("Andijon", "Андижан", 40.78, 72.34),
    ("Fargʻona", "Фергана", 40.38, 71.79),
    ("Qoʻqon", "Коканд", 40.53, 70.94),
    ("Margʻilon", "Маргилан", 40.47, 71.72),
    ("Nukus", "Нукус", 42.46, 59.60),
    ("Qarshi", "Карши", 38.86, 65.79),
    ("Termiz", "Термез", 37.22, 67.28),
    ("Jizzax", "Джизак", 40.12, 67.84),
    ("Navoiy", "Навои", 40.10, 65.37),
    ("Urganch", "Ургенч", 41.55, 60.63),
    ("Xiva", "Хива", 41.38, 60.36),
    ("Guliston", "Гулистан", 40.49, 68.78),
    ("Chirchiq", "Чирчик", 41.47, 69.58),
    ("Olmaliq", "Алмалык", 40.84, 69.60),
    ("Angren", "Ангрен", 41.02, 70.14),
    ("Shahrisabz", "Шахрисабз", 39.06, 66.83),
    ("Asaka", "Асака", 40.64, 72.24),
    ("Zarafshon", "Зарафшан", 41.57, 64.20),
]
# Города, которые можно добавить, если попросят в комментариях (вписать в CITIES):
#   Denov 38.27 67.90 · Chust 41.00 71.24 · Kattaqoʻrgʻon 39.90 66.26 · Bekobod 40.22 69.27 · Urgut 39.40 67.24
#   Gʻijduvon 40.10 64.68 · Xonqa 41.47 60.78 · Beruniy 41.69 60.75 · Quvasoy 40.30 71.98 · Nurafshon 41.05 69.35

# ---------- машины: название (одинаково на обоих языках), по-русски, кузов ----------
CARS = [
    ("Cobalt", "Cobalt", "sedan"),
    ("Gentra", "Gentra", "sedan"),
    ("Nexia", "Nexia", "sedan"),
    ("Lacetti", "Lacetti", "hatch"),
    ("Spark", "Spark", "mini"),
    ("Matiz", "Matiz", "mini"),
    ("Tico", "Tico", "mini"),
    ("Damas", "Damas", "van"),
    ("Labo", "Labo", "pickup"),
    ("Malibu", "Malibu", "sedan"),
    ("Captiva", "Captiva", "suv"),
    ("Tracker", "Tracker", "suv"),
    ("Onix", "Onix", "sedan"),
    ("Equinox", "Equinox", "suv"),
    ("Tahoe", "Tahoe", "suv"),
    ("Epica", "Epica", "sedan"),
    ("Kia K5", "Kia K5", "sedan"),
    ("BYD Song", "BYD Song", "suv"),
    ("Chery Tiggo", "Chery Tiggo", "suv"),
    ("Jiguli", "Жигули", "classic"),
]
BODY = {k: b for k, _, b in CARS}


def _e(key, kk, ru, num, **kw):
    d = {"key": key, "kk": kk, "ru": ru, "num": num, "full_kk": kw.pop("full_kk", kk.upper()),
         "full_ru": kw.pop("full_ru", ru.upper())}
    d.update(kw)
    return d


def entries(league, extra=None, rnd=None):
    """Участники: основной список + добавленные по просьбам зрителей (extra — ключи из uz_places)."""
    import uz_places as P
    if league == "cities":
        rows = list(CITIES)
        have = {r[0] for r in rows}
        for k in extra or []:
            if k in P.CITY_BY_KEY and k not in have:
                kk, ru, la, lo, _ = P.CITY_BY_KEY[k]
                rows.append((kk, ru, la, lo))
                have.add(k)
        return [_e(kk, kk, ru, str(i + 1), lat=la, lon=lo) for i, (kk, ru, la, lo) in enumerate(rows)]
    if league == "cars":
        rows = list(CARS)
        have = {r[0] for r in rows}
        for k in extra or []:
            if k in P.CAR_BY_KEY and k not in have:
                kk, ru, b, _ = P.CAR_BY_KEY[k]
                rows.append((kk, ru, b))
                have.add(k)
        return [_e(kk, kk, ru, str(i + 1), body=b) for i, (kk, ru, b) in enumerate(rows)]
    raise ValueError(f"нет такой темы: {league}")


TAGS_COMMON = ["oʻzbekiston", "uzbekistan", "узбекистан", "poyga", "sharchalar poygasi", "гонка шариков",
               "marble race"]

LEAGUES = {
    "cities": {
        "name": "гонка городов",
        "head": ("QAYSI SHAHAR YUTADI?", "КАКОЙ ГОРОД ПОБЕДИТ?"),
        "map": True, "panel": "kk", "label": "kk",
        "early": ("Kim yutadi? Bashoratingni yoz!", "Кто победит? Пиши прогноз!"),
        "cta": ("Sen qaysi shahar muxlisisan?", "А ты за какой город болеешь?"),
        "title": "Qaysi shahar yutadi? Какой город победит? 🏁 №{no}",
        "q": "Qaysi shahar yutadi? Какой город победит?",
        "season": "week",
        "desc": ("{n} ta shahar — bitta marra! Sen qaysi shahar muxlisisan? Izohlarda yoz 👇\n"
                 "{n} городов Узбекистана в одной гонке. За какой город болеешь? Пиши в комментариях!\n\n"
                 "Har kuni — yangi poyga. Каждый день новая гонка и турнирная таблица.\n"
                 "Shahringiz yoʻqmi? Yozing — qoʻshamiz! Нет твоего города? Напиши — добавим!\n\n"
                 "#uzbekistan #ozbekiston #toshkent #samarqand #poyga #гонкашариков #shorts"),
        "tags": TAGS_COMMON + ["toshkent", "samarqand", "buxoro", "namangan", "andijon", "fargʻona",
                               "города узбекистана", "shaharlar"],
    },
    "cars": {
        "name": "гонка машин",
        "head": ("QAYSI MASHINA YUTADI?", "КАКАЯ МАШИНА ПОБЕДИТ?"),
        "map": False, "panel": "kk", "label": "kk", "car": True,
        "early": ("Sening mashinang yutadimi?", "Твоя машина победит?"),
        "cta": ("Sen qaysi mashinada yurasan?", "А ты на какой машине ездишь?"),
        "title": "Qaysi mashina yutadi? Какая машина победит? 🚗 №{no}",
        "q": "Qaysi mashina yutadi? Какая машина победит?",
        "season": "week",
        "desc": ("Cobalt, Gentra, Nexia, Damas… qaysi biri tezroq? Izohlarda yoz 👇\n"
                 "{n} машин в одной гонке: Cobalt, Gentra, Nexia, Damas, Malibu и другие. "
                 "Какая победит? Пиши в комментариях!\n\n"
                 "Har kuni — yangi poyga. Каждый день новая гонка и турнирная таблица.\n\n"
                 "#uzbekistan #cobalt #gentra #nexia #damas #mashina #гонкашариков #shorts"),
        "tags": TAGS_COMMON + ["mashina", "cobalt", "gentra", "nexia", "damas", "malibu", "chevrolet",
                               "машины узбекистана"],
    },
}

SEASON_TXT = {
    "week": {
        "final_label": "HAFTA FINALI  ·  ФИНАЛ НЕДЕЛИ",
        "pill2": ("Yakshanba kuni — hafta finali!", "В воскресенье — финал недели!"),
        "prev": ("Oʻtgan hafta chempioni — {kk} ★", "Чемпион прошлой недели — {ru} ★"),
        "prev_desc": "🏆 Oʻtgan hafta chempioni: {kk} · Чемпион прошлой недели: {ru}",
        "champ": ("HAFTA CHEMPIONI", "ЧЕМПИОН НЕДЕЛИ"),
        "table": ("HAFTA JADVALI", "ТАБЛИЦА НЕДЕЛИ"),
        "hall": "CHEMPIONLAR · ЧЕМПИОНЫ НЕДЕЛЬ",
        "next": ("Dushanbadan — yangi hafta!", "С понедельника — новая неделя!"),
        "team_sum": "Hafta hisobi · Счёт недели",
        "final_title": "Hafta finali · Финал недели",
        "note": "Yakshanba kuni — hafta finali! В воскресенье — финал недели!",
        "final_desc": ("🏆 Hafta finali: haftaning eng yaxshilari bitta poygada! Kim chempion boʻladi?\n"
                       "Финал недели: лучшие участники недели в одной гонке. Кто станет чемпионом?\n"
                       "Dushanbadan — yangi hafta, jadval noldan boshlanadi. С понедельника — новая неделя.\n\n"),
    },
}

# Надписи движка (раньше были казахские прямо в коде)
UI = {
    "race": ("POYGA №{n}", "ЗАЕЗД №{n}"),
    "race_band": "POYGA №{n}  ·  ЗАЕЗД №{n}",
    "start": "START!",
    "finish": "MARRA · ФИНИШ",
    "winner": ("GʻOLIB!", "ПОБЕДИТЕЛЬ!"),
    "race_winner": ("POYGA №{n} GʻOLIBI", "ПОБЕДИТЕЛЬ ЗАЕЗДА №{n}"),
    "final_q": ("FINAL! Kim chempion boʻladi?", "ФИНАЛ! Кто станет чемпионом?"),
    "final_res": ("FINAL NATIJALARI", "ИТОГИ ФИНАЛА"),
    "race_res": ("POYGA №{n} NATIJALARI", "ИТОГИ ЗАЕЗДА №{n}"),
    "after": "{n} poygadan keyin",
    "tour": "TURNIR JADVALI",
    "top5": ("ENG YAXSHI BESHLIK · 1-poyga", "ПЯТЁРКА ЛИДЕРОВ · заезд №1"),
    "write": "Izohlarda yoz · Пиши в комментариях",
    "new": ("Yangi: {uz} — izohlardan!", "Новые: {ru} — из комментариев!"),
    "marks": {"tunnel": "TUNNEL · ТУННЕЛЬ", "stairs": "ZINAPOYA · ЛЕСЕНКА", "bumps": "DOʻNGLIKLAR · КОЧКИ",
              "tramp": "BATUT · БАТУТ", "hammer": "BOLGʻA · МОЛОТ", "fork": "IKKI YOʻL · ДВА ПУТИ"},
}


def countdown(days):
    """(«Finalgacha 3 kun», «До финала 3 дня») или None."""
    if days is None or days < 0:
        return None
    if days == 0:
        return ("Final — bugun kechqurun!", "Финал — сегодня вечером!")
    if days == 1:
        return ("Final — ertaga!", "Финал — завтра!")
    d = days
    ru = "день" if d % 10 == 1 and d % 100 != 11 else ("дня" if 2 <= d % 10 <= 4 and not 12 <= d % 100 <= 14 else "дней")
    return (f"Finalgacha {d} kun", f"До финала {d} {ru}")


def stxt(league):
    return SEASON_TXT[LEAGUES[league].get("season", "week")]


def season_label(league, ch, n):
    return f"{n}-hafta · Неделя {n}"


def make_title(league, no, ent, final=False):
    if final:
        return f"{LEAGUES[league]['q']} 🏆 {stxt(league)['final_title']}"
    return LEAGUES[league]["title"].format(no=no)


def make_desc(league, ent, final=False, n=None, new=None):
    d = LEAGUES[league]["desc"].format(n=n or len(ent))
    if new:
        ru = ", ".join(e["ru"] for e in new)
        uz = ", ".join(e["kk"] for e in new)
        d = f"🆕 Yangi: {uz} — izohlaringiz boʻyicha! · Новые по вашим комментариям: {ru}\n\n" + d
    if final:
        return stxt(league)["final_desc"] + d
    head, sep, tags = d.rpartition("\n\n")
    return head + "\n\n" + stxt(league)["note"] + sep + tags

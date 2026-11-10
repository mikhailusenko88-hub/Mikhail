"""«Білесің бе?»: города, которые зрители просят в комментариях, — сами попадают в гонку «Қай қала жеңеді?».

Один город — одна запись, сколько бы способов написать его ни было:
  Өскемен = Ускемен = Ускимен = Усть-Каменогорск = Oskemen;  Шымкент = Чимкент;  Алматы = Алма-Ата …
Сравниваются «скелеты» слов (всё в латиницу, похожие буквы — одинаково), поэтому город, который уже
есть в гонке, второй раз под другим написанием не добавится. В гонку попадают ТОЛЬКО города из списка ниже —
случайные слова никогда.

Комментарии читаются так же, как их видит любой зритель (без ключей): список роликов — из открытой
RSS-ленты канала, комментарии — пакетом youtube-comment-downloader.

Проверка на сервере (ничего не меняет):  python3 kz_places.py --dry
Вручную добавить город:                  srv city Степногорск
"""
import datetime as dt
import difflib
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
CHANNEL_ID = "UCN5T4AgjFCPUOETZpzTKA8g"        # «Білесің бе?» (@bilesin_be_kz)
CAP = 30                                        # больше шариков трасса и таблица не вмещают
PER_RACE = 2                                    # новых городов за один заезд — не больше

# ---------- казахское название, русское, широта, долгота, другие написания (через пробел) ----------
CITY_POOL = [
    # уже в гонке (race_leagues.CITIES) — здесь ради узнавания других написаний
    ("Астана", "Астана", 51.17, 71.45, "Astana Нурсултан НурСултан Nursultan Целиноград"),
    ("Алматы", "Алматы", 43.24, 76.95, "Almaty АлмаАта Алмата Almata AlmaAta"),
    ("Шымкент", "Шымкент", 42.32, 69.60, "Shymkent Чимкент Chimkent"),
    ("Қарағанды", "Караганда", 49.80, 73.10, "Karaganda Qaragandy Qaraghandy Карагандa"),
    ("Ақтөбе", "Актобе", 50.28, 57.17, "Aktobe Aqtobe Актюбинск"),
    ("Тараз", "Тараз", 42.90, 71.37, "Taraz Джамбул Жамбыл"),
    ("Павлодар", "Павлодар", 52.29, 76.97, "Pavlodar"),
    ("Өскемен", "Усть-Каменогорск", 49.95, 82.61,
     "Oskemen Ускемен Ускимен Оскемен Өскемен Усткаменогорск УстьКаменогорск UstKamenogorsk"),
    ("Семей", "Семей", 50.41, 80.25, "Semey Semei Семипалатинск Semipalatinsk"),
    ("Атырау", "Атырау", 47.10, 51.92, "Atyrau Гурьев"),
    ("Қостанай", "Костанай", 53.21, 63.62, "Kostanay Qostanay Кустанай"),
    ("Қызылорда", "Кызылорда", 44.85, 65.51, "Kyzylorda Qyzylorda Кзылорда"),
    ("Орал", "Уральск", 51.23, 51.37, "Oral Uralsk"),
    ("Петропавл", "Петропавловск", 54.87, 69.15, "Petropavl Petropavlovsk"),
    ("Ақтау", "Актау", 43.65, 51.20, "Aktau Aqtau Шевченко"),
    ("Түркістан", "Туркестан", 43.30, 68.25, "Turkistan Turkestan"),
    ("Көкшетау", "Кокшетау", 53.28, 69.39, "Kokshetau Кокчетав"),
    ("Талдықорған", "Талдыкорган", 45.02, 78.37, "Taldykorgan Taldyqorgan Талдык"),
    ("Жезқазған", "Жезказган", 47.80, 67.71, "Zhezkazgan Jezkazgan"),
    ("Қонаев", "Конаев", 43.87, 77.07, "Konaev Qonaev Капшагай Капчагай Kapchagay Kapshagay"),
    ("Талғар", "Талгар", 43.30, 77.24, "Talgar"),
    ("Жаркент", "Жаркент", 44.17, 80.00, "Zharkent Jarkent Панфилов"),
    # можно добавить по просьбе
    ("Екібастұз", "Экибастуз", 51.72, 75.32, "Ekibastuz Екибастуз"),
    ("Теміртау", "Темиртау", 50.05, 72.96, "Temirtau"),
    ("Рудный", "Рудный", 52.97, 63.12, "Rudny Rudnyy"),
    ("Жаңаөзен", "Жанаозен", 43.34, 52.86, "Zhanaozen Janaozen"),
    ("Балқаш", "Балхаш", 46.85, 74.98, "Balkhash Balqash"),
    ("Сәтбаев", "Сатпаев", 47.90, 67.53, "Satpayev Satbayev Сатбаев"),
    ("Кентау", "Кентау", 43.52, 68.51, "Kentau"),
    ("Риддер", "Риддер", 50.34, 83.51, "Ridder Лениногорск"),
    ("Ақсу", "Аксу", 52.04, 76.93, "Aksu"),
    ("Степногорск", "Степногорск", 52.35, 71.88, "Stepnogorsk"),
    ("Щучинск", "Щучинск", 52.94, 70.20, "Shchuchinsk Щучье Шучинск"),
    ("Байқоңыр", "Байконур", 45.62, 63.32, "Baikonur Baykonur Байконыр"),
    ("Арқалық", "Аркалык", 50.25, 66.91, "Arkalyk"),
    ("Құлсары", "Кульсары", 46.95, 54.02, "Kulsary"),
    ("Ленгір", "Ленгер", 42.18, 69.88, "Lenger"),
    ("Сарыағаш", "Сарыагаш", 41.46, 69.17, "Saryagash"),
    ("Қаскелең", "Каскелен", 43.20, 76.62, "Kaskelen"),
    ("Үшарал", "Ушарал", 46.17, 80.94, "Usharal"),
    ("Хромтау", "Хромтау", 50.25, 58.44, "Khromtau"),
    ("Қандыағаш", "Кандыагаш", 49.47, 57.42, "Kandyagash"),
    ("Шахтинск", "Шахтинск", 49.71, 72.59, "Shakhtinsk"),
    ("Сарань", "Сарань", 49.80, 72.85, "Saran"),
    ("Аягөз", "Аягоз", 47.96, 80.43, "Ayagoz Аягуз"),
    ("Зайсан", "Зайсан", 47.47, 84.87, "Zaysan Zaisan"),
    ("Шемонаиха", "Шемонаиха", 50.63, 81.91, "Shemonaikha"),
    ("Лисаковск", "Лисаковск", 52.54, 62.50, "Lisakovsk"),
    ("Атбасар", "Атбасар", 51.81, 68.36, "Atbasar"),
    ("Ерейментау", "Ерейментау", 51.62, 73.11, "Ereymentau"),
    ("Бурабай", "Бурабай", 53.08, 70.31, "Burabay Боровое"),
    ("Сарқан", "Саркан", 45.41, 79.92, "Sarkand Саркант Sarqan"),
    ("Текелі", "Текели", 44.83, 78.82, "Tekeli"),
    ("Жітіқара", "Житикара", 52.19, 61.20, "Zhitikara"),
    ("Арал", "Аральск", 46.80, 61.67, "Aralsk"),
    ("Жаңатас", "Жанатас", 43.56, 69.75, "Zhanatas"),
    ("Қаратау", "Каратау", 43.18, 70.46, "Karatau"),
    ("Шардара", "Шардара", 41.25, 67.97, "Shardara"),
    ("Жетісай", "Жетысай", 40.78, 68.33, "Zhetisay"),
    ("Қордай", "Кордай", 43.04, 74.71, "Korday"),
    ("Мерке", "Мерке", 42.87, 73.18, "Merke"),
    ("Ембі", "Эмба", 48.83, 58.14, "Emba Емба"),
    ("Ақсай", "Аксай", 51.17, 52.99, "Aksai Aksay"),
    ("Бейнеу", "Бейнеу", 45.32, 55.20, "Beyneu"),
    ("Теңге", "Тенге", 43.30, 52.80, "Tenge"),      # село у Жанаозена, 17 тыс. жителей — просили 9.11.2026
    ("Курчатов", "Курчатов", 50.76, 78.54, "Kurchatov"),
    ("Приозерск", "Приозерск", 46.03, 73.70, "Priozersk"),
    ("Қарқаралы", "Каркаралинск", 49.41, 75.47, "Karkaralinsk Каркаралы"),
    ("Сайрам", "Сайрам", 42.30, 69.77, "Sayram"),
    ("Қазалы", "Казалинск", 45.76, 62.10, "Kazaly Казалы"),
    ("Шиелі", "Шиели", 44.17, 66.75, "Shieli"),
]
# Есік («дверь»), Шу, Абай, Шалқар, Есіл нарочно не берём — это обычные слова или названия областей/рек.
# Слова, которые бывают обычными: город из них берём, только если рядом слово «қала/город/из»
STOP = {"орал", "семей", "арал", "ақсу", "аксу", "мерке", "сайрам", "теңге", "тенге", "tenge"}   # теңге — ещё и валюта

_CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
        "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "ң": "n", "о": "o", "ө": "o", "ў": "o", "п": "p",
        "р": "r", "с": "s", "т": "t", "у": "u", "ү": "u", "ұ": "u", "ф": "f", "х": "x", "ҳ": "h", "һ": "h", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "і": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ә": "a"}


def skel(s):
    """«Скелет» слова: одинаковый для Өскемен / Оскемен / Ускемен / Oskemen."""
    s = s.lower()
    s = "".join(_CYR.get(c, c) for c in s)
    s = re.sub(r"[^a-z0-9]", "", s)
    for a, b in (("dzh", "j"), ("dj", "j"), ("zh", "j"), ("kh", "h"), ("sh", "$"), ("ch", "%"), ("ts", "s"),
                 ("yo", "o"), ("yu", "u"), ("ya", "a"), ("ye", "e")):
        s = s.replace(a, b)
    s = s.replace("q", "k").replace("x", "h").replace("o", "a").replace("e", "i").replace("y", "i").replace("w", "v")
    s = re.sub(r"(.)\1+", r"\1", s)
    return s


NO_INDEX = {"Арал"}          # «Арал» и «Орал» пишутся почти одинаково — Аральск узнаём только как «Аральск»
INDEX = []
for _r in CITY_POOL:
    for _n in [n for n in [_r[0], _r[1]] if n not in NO_INDEX] + _r[4].split():
        if skel(_n):
            INDEX.append((skel(_n), _r[0]))
BY_KEY = {r[0]: r for r in CITY_POOL}

# окончания: Өскеменнен, Алматыданмын, из Караганды, шымкенттікпін, Павлодарда…
SUFFIX = {skel(x) for x in ("нан", "нен", "дан", "ден", "тан", "тен", "да", "де", "та", "те", "ға", "ге", "қа", "ке",
                            "ның", "нің", "дың", "дің", "тың", "тің", "лық", "лік", "дық", "дік", "тық", "тік",
                            "лықпын", "лікпін", "тікпін", "дықпын", "мын", "мін", "пын", "пін", "ым", "ім", "а", "е",
                            "у", "ом", "ы", "и", "ец", "цы", "ский", "ская", "ане", "ане", "ова")}


def _match(word, force=False):
    k = skel(word)
    if len(k) < 3 or (not force and word.lower() in STOP):
        return None
    for kk, key in INDEX:
        if kk == k:
            return key
    best = None
    for kk, key in INDEX:
        if len(kk) >= 4 and k.startswith(kk) and (best is None or len(kk) > len(best[0])):
            rest = k[len(kk):]
            if rest in SUFFIX or (len(kk) >= 6 and len(rest) <= 6):
                best = (kk, key)
    if best:
        return best[1]
    if len(k) < 5:
        return None
    key_, score = None, 0.0
    for kk, key in INDEX:
        if len(kk) >= 5:
            r = difflib.SequenceMatcher(None, k, kk).ratio()
            if r > score:
                key_, score = key, r
    return key_ if score >= 0.86 else None


def find(text):
    """Города из комментария (ключи — казахские названия), без повторов. Длинные тексты не разбираем."""
    words = re.findall(r"[A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі0-9-]+", text or "")
    words = [w.replace("-", "") for w in words if w.replace("-", "")]
    if not words or len(words) > 15:
        return []
    city_word = {skel(x) for x in ("қала", "қаласы", "город", "из", "қаласынан", "city")}
    near = {i for i, w in enumerate(words) if skel(w) in city_word}
    grams = [(w, (i - 1 in near or i + 1 in near)) for i, w in enumerate(words)] + \
            [(a + b, False) for a, b in zip(words, words[1:])]
    out = []
    for g, force in grams:
        key = _match(g, force)
        if key and key not in out:
            out.append(key)
    return out


# ---------- комментарии (открыто, как видит зритель) ----------

def channel_videos(channel_id, limit=15):
    import requests
    r = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", timeout=30)
    return re.findall(r"<yt:videoId>([\w-]{11})</yt:videoId>", r.text)[:limit] if r.status_code == 200 else []


def read_comments(channel_id, per_video=60):
    """[(id комментария, текст, id автора)] — свежие комментарии под последними роликами канала."""
    from youtube_comment_downloader import SORT_BY_RECENT, YoutubeCommentDownloader
    dl = YoutubeCommentDownloader()
    out = []
    for vid in channel_videos(channel_id):
        try:
            for n, c in enumerate(dl.get_comments_from_url(f"https://www.youtube.com/watch?v={vid}",
                                                           sort_by=SORT_BY_RECENT)):
                if n >= per_video:
                    break
                if not c.get("reply"):
                    out.append((c.get("cid", ""), c.get("text", ""), c.get("channel", "")))
        except Exception:  # noqa: BLE001
            pass
    return out


def _in_race(ls):
    import race_leagues as RL
    return [c[0] for c in RL.CITIES] + [e["kk"] for e in ls.get("extra", [])]


def _log_file(lines):
    if lines:
        with open(BASE / "city_requests.log", "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def take_requests(state, ls, log=print, cfg=None, dry=False):
    """Новые города из комментариев и из файла city_requests.txt → в гонку (ls['extra']).
    Возвращает список добавленных сейчас (казахские названия)."""
    ch = (cfg or {}).get("channel_id") or CHANNEL_ID
    seen = ls.setdefault("city_seen", [])
    seen_set = set(seen)
    have = _in_race(ls)
    asked = ls.setdefault("city_asked", {})
    now = f"{dt.datetime.now():%Y-%m-%d %H:%M}"
    lines = []
    texts = []
    # вручную: city_requests.txt (srv city Степногорск)
    f = BASE / "city_requests.txt"
    if f.exists():
        for s in f.read_text(encoding="utf-8").splitlines():
            if s.strip():
                texts.append(("файл", s.strip(), 3))          # ручная просьба весит как 3 комментария
        if not dry:
            f.write_text("", encoding="utf-8")
    try:
        for cid, text, author in read_comments(ch):
            if cid in seen_set or (author and author == ch):
                continue
            seen_set.add(cid)
            seen.append(cid)
            texts.append(("коммент", text, 1))
    except Exception as e:  # noqa: BLE001
        log(f"Города из комментариев: не прочитал ({e})")
    ls["city_seen"] = seen[-3000:]
    for src, text, w in texts:
        for key in find(text):
            if key in have:
                lines.append(f"{now} | {key} | уже есть | {text[:70]}")
                continue
            asked[key] = asked.get(key, 0) + w
            lines.append(f"{now} | {key} | просьба №{asked[key]} | {text[:70]}")
        if src == "файл" and not find(text):
            lines.append(f"{now} | ? | нет в списке городов (нужны координаты — скажи Claude) | {text[:70]}")
    added = []
    room = CAP - len(have)
    for key in sorted(asked, key=lambda k: -asked[k]):
        if key in have or len(added) >= min(PER_RACE, max(0, room)):
            continue
        added.append(key)
    if not dry:
        for key in added:
            r = BY_KEY[key]
            ls.setdefault("extra", []).append({"kk": r[0], "ru": r[1], "lat": r[2], "lon": r[3], "date": now})
            asked.pop(key, None)
        for key in added:
            lines.append(f"{now} | {key} | ДОБАВЛЕН в гонку")
        _log_file(lines)
    if added:
        log(f"Города из комментариев: добавляю {', '.join(added)}")
    elif texts:
        log(f"Города из комментариев: новых просьб нет (прочитано {len(texts)})")
    if room <= 0 and asked:
        log(f"Города из комментариев: трасса полная ({CAP}), ждут: {', '.join(asked)}")
    return added, lines


def note(added):
    """Строка в начало описания ролика."""
    if not added:
        return ""
    kk = ", ".join(added)
    ru = ", ".join(BY_KEY[k][1] for k in added)
    return f"🆕 Пікірлерде сұрадыңыздар — жаңа қала: {kk} · Новый город по вашей просьбе: {ru}\n\n"


def fix_desc(desc, n):
    """«Жиырма екі қала / 22 города» → настоящее число городов."""
    w = "город" if n % 10 == 1 and n % 100 != 11 else ("города" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "городов")
    desc = re.sub(r"Жиырма(?: [а-яәғқңөұүһі]+)? қала — бір мәре!", f"{n} қала — бір мәре!", desc)
    return re.sub(r"\d+ город\w* Казахстана", f"{n} {w} Казахстана", desc)


if __name__ == "__main__":
    if "--dry" in sys.argv:          # проверка: что нашлось бы сейчас (ничего не меняет)
        st = json.loads((BASE / "state.json").read_text(encoding="utf-8")) if (BASE / "state.json").exists() else {}
        ls_ = json.loads(json.dumps(st.get("race", {})))
        added_, lines_ = take_requests(st, ls_, dry=True)
        print("\n".join(lines_[-25:]) or "Просьб в комментариях пока нет.")
        print(f"\nВ гонке сейчас городов: {len(_in_race(ls_))}. В следующий заезд добавился бы: {', '.join(added_) or 'никто'}")
    else:
        for t in sys.argv[1:]:
            print(t, "→", find(t))

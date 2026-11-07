"""«Білесің бе?»: роды (ру), которые зрители пишут в комментариях, — сами попадают в гонку «Қай ру жеңеді?».

Берутся ТОЛЬКО настоящие ру из справочника ниже (шежіре трёх жузов) — выдуманные слова никогда.
Один ру — одна запись при любом написании: Уақ = Уак = Uaq, Қыпшақ = Кыпшак = Кипчак, Шапырашты = Шапрашты …
Окончания понимает: Адаймын, Найманнан, Арғынбыз, Дулатпын, руым Керей.

Подроды не добавляются отдельным шариком — засчитываются своему ру:
  Тобықты, Атығай, Қуандық… → Арғын;  Матай, Қаракерей… → Найман;  Ботбай, Сиқым → Дулат.
Слова, которые бывают обычными (Алтын «золото», Таз «лысый», Кете «уйти», Төре «судья» …), берём,
только если рядом слово «ру/руым/рудан/род/жүз» или комментарий из одного слова («Алтын», «Алтын жеңеді») под роликом с ру.

Где читаем: под роликами «Қай ру жеңеді?» — все комментарии; под остальными — только если рядом «ру/род/жүз».
Комментарии читаются как у любого зрителя (без ключей): youtube-comment-downloader.

Проверка на сервере (ничего не меняет):  python3 kz_ru.py --dry
Вручную добавить ру:                     srv ru Тарақты
Проверить слово:                         python3 kz_ru.py "Адаймын"
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

from kz_places import CHANNEL_ID, skel

BASE = Path(__file__).resolve().parent
CAP = 30           # больше шариков трасса и таблица не вмещают
PER_RACE = 3       # новых ру за один заезд — не больше (тема ру выходит раз в 5 дней)

# ---------- настоящие ру: казахское, русское, жүз, другие написания (через пробел) ----------
# жүз: ұлы — Старший, орта — Средний, кіші — Младший, тыс — вне жузов (төре, қожа)
RU_POOL = [
    # Ұлы жүз
    ("Дулат", "Дулат", "ұлы", "Dulat Дулаты"),
    ("Албан", "Албан", "ұлы", "Alban"),
    ("Суан", "Суан", "ұлы", "Suan"),
    ("Жалайыр", "Жалаир", "ұлы", "Jalayir Zhalayir Жалайр"),
    ("Шапырашты", "Шапрашты", "ұлы", "Shaprashty Shapyrashty Шапрашты Шапырашты Шапрашти"),
    ("Қаңлы", "Канлы", "ұлы", "Kangly Qangly Канглы"),
    ("Сіргелі", "Сиргели", "ұлы", "Sirgeli Сергели"),
    ("Сарыүйсін", "Сары-Уйсун", "ұлы", "Saryuysin Сарыуйсын Сарыуйсун Сарыүйсін"),
    ("Ысты", "Ысты", "ұлы", "Ysty Isty"),
    ("Ошақты", "Ошакты", "ұлы", "Oshakty Oshaqty"),
    ("Шанышқылы", "Шанышкылы", "ұлы", "Shanyshkyly"),
    ("Қатаған", "Катаган", "ұлы", "Katagan Qatagan"),
    # Орта жүз
    ("Арғын", "Аргын", "орта", "Argyn Aргын Аргин"),
    ("Найман", "Найман", "орта", "Naiman Nayman"),
    ("Қыпшақ", "Кыпшак", "орта", "Kypshak Qypshaq Kipchak Кипчак Кыпчак Қыпчақ"),
    ("Қоңырат", "Конырат", "орта", "Konyrat Qongyrat Конрат Кунграт Коңырат Қоңырат"),
    ("Керей", "Керей", "орта", "Kerei Kerey Кирей"),
    ("Уақ", "Уак", "орта", "Uak Uaq Уаки"),
    ("Тарақты", "Таракты", "орта", "Tarakty Taraqty"),
    # Кіші жүз — Байұлы
    ("Адай", "Адай", "кіші", "Adai Aday"),
    ("Беріш", "Берш", "кіші", "Berish Bersh Бериш Берыш"),
    ("Байбақты", "Байбакты", "кіші", "Baibakty Baybakty"),
    ("Жаппас", "Жаппас", "кіші", "Zhappas Jappas"),
    ("Шеркеш", "Шеркеш", "кіші", "Sherkesh"),
    ("Ысық", "Ысык", "кіші", "Ysyk Исык"),
    ("Қызылқұрт", "Кызылкурт", "кіші", "Kyzylkurt"),
    ("Масқар", "Маскар", "кіші", "Maskar"),
    ("Есентемір", "Есентемир", "кіші", "Esentemir"),
    ("Алаша", "Алаша", "кіші", "Alasha"),
    ("Тана", "Тана", "кіші", "Tana"),
    ("Таз", "Таз", "кіші", "Taz"),
    ("Алтын", "Алтын", "кіші", "Altyn"),
    # Кіші жүз — Әлімұлы
    ("Шөмекей", "Шомекей", "кіші", "Shomekei Shomekey Шумекей"),
    ("Шекті", "Шекты", "кіші", "Shekti Shekty Шекти"),
    ("Төртқара", "Торткара", "кіші", "Tortkara"),
    ("Қарасақал", "Карасакал", "кіші", "Karasakal"),
    ("Кете", "Кете", "кіші", "Kete"),
    # Кіші жүз — Жетіру
    ("Табын", "Табын", "кіші", "Tabyn"),
    ("Тама", "Тама", "кіші", "Tama"),
    ("Жағалбайлы", "Жагалбайлы", "кіші", "Zhagalbaily Jagalbaily"),
    ("Кердері", "Кердери", "кіші", "Kerderi"),
    ("Керейт", "Керейт", "кіші", "Kereit Kereyt"),
    ("Тілеу", "Тлеу", "кіші", "Tileu Tleu Тилеу"),
    ("Рамадан", "Рамадан", "кіші", "Ramadan"),
    # вне жузов
    ("Төре", "Торе", "тыс", "Tore Төре"),
    ("Қожа", "Кожа", "тыс", "Koja Kozha Qozha Ходжа"),
]

# подроды → свой ру (отдельным шариком не добавляются)
SUB = {
    "Арғын": "Тобықты Tobykty Тобыкты Атығай Атыгай Atygai Қуандық Куандык Kuandyk Сүйіндік Суйиндик Suyindik "
             "Бәсентиін Басентиин Басентеин Қаржас Каржас Karzhas Шақшақ Шакшак",
    "Найман": "Матай Matai Қаракерей Каракерей Karakerei Садыр Sadyr Төртуыл Тортуыл Бағаналы Баганалы Baganaly "
              "Байжігіт Байжигит Baizhigit",
    "Дулат": "Ботбай Botbai Сиқым Сикым Sikym Жаныс Zhanys",
    "Керей": "Абақ Абак Abak Ашамайлы Ashamaily",
    "Қыпшақ": "Қарақыпшақ Каракыпшак Karakypshak",
}

# обычные слова/имена — только при «ру/род/жүз» рядом или если комментарий из 1–2 слов под роликом с ру
STOP = {"Алтын", "Таз", "Тана", "Кете", "Тама", "Төре", "Қожа", "Рамадан", "Алаша", "Тілеу", "Масқар",
        "Есентемір", "Шекті", "Табын", "Суан", "Албан", "Жаныс"}
# общие названия союзов — не ру, просим уточнить (в журнал)
UNIONS = {skel(x): n for n, xs in (("Үйсін", "Үйсін Уйсун Уйсин Uysin"), ("Алшын", "Алшын Алшин Alshyn"),
                                   ("Байұлы", "Байұлы Байулы Baiuly"), ("Әлімұлы", "Әлімұлы Алимулы Alimuly"),
                                   ("Жетіру", "Жетіру Жетиру Zhetiru")) for x in xs.split()}
# есть в двух жузах — непонятно, какой (Қаракесек: Арғын и Әлімұлы)
AMBIG = {skel(x): "Қаракесек" for x in ("Қаракесек", "Каракесек", "Karakesek")}

ZHUZ = {"ұлы": ("Ұлы жүз", "Старший жуз"), "орта": ("Орта жүз", "Средний жуз"),
        "кіші": ("Кіші жүз", "Младший жуз"), "тыс": ("Жүзден тыс", "Вне жузов")}

BY_KEY = {r[0]: r for r in RU_POOL}
INDEX = {}                           # скелет → (ру, подрод или None)
for _r in RU_POOL:
    for _n in [_r[0], _r[1]] + _r[3].split():
        if skel(_n):
            INDEX[skel(_n)] = (_r[0], None)
for _p, _subs in SUB.items():
    for _n in _subs.split():
        if skel(_n) and skel(_n) not in INDEX:
            INDEX[skel(_n)] = (_p, _n)

# окончания: Адаймын, Найманнан, Арғынбыз, Дулатпын, Керейлер, Уақтан, Қыпшақтың…
SUFFIX = {skel(x) for x in (
    "мын", "мін", "пын", "пін", "бын", "бін", "мыз", "міз", "пыз", "піз", "быз", "біз",
    "нан", "нен", "дан", "ден", "тан", "тен", "ның", "нің", "дың", "дің", "тың", "тің",
    "лар", "лер", "дар", "дер", "тар", "тер", "ға", "ге", "қа", "ке", "да", "де", "та", "те",
    "мен", "пен", "бен", "дықпын", "лықпын", "ым", "ім", "ы", "і",
    "лармыз", "лерміз", "дармыз", "дерміз", "тармыз", "термиз", "ларбыз", "дарбыз", "тарбыз",
    "ы", "а", "ов", "ский", "цы", "ец", "ам")}
CTX = {skel(x) for x in ("ру", "руым", "руы", "рудан", "руданмын", "руынан", "руымыз", "руың", "руым", "рулы",
                         "род", "рода", "родом", "роду", "жүз", "жүзден", "жүзбен", "жуз", "жуза", "жузе")}
# «Есентемір жеңеді», «Алтын алға» — второе слово просто болеет, комментарий всё равно про ру
CHEER = {skel(x) for x in ("жеңеді", "жеңсін", "жеңеміз", "алға", "күшті", "мықты", "кетті", "топ", "сила",
                           "вперед", "вперёд", "победит", "лучшие", "чемпион", "жарайсың")}


def _sfx(kk, rest):
    """Окончание? Учитываем, что двойные буквы в «скелете» слиты: Найман+нан → naimanan."""
    return rest in SUFFIX or (bool(kk) and (kk[-1] + rest) in SUFFIX)


# «я — …»: Табынмын, Алтынбыз — так про ру и говорят (кроме Кете: «кетемін» = «ухожу»)
PERSON = {skel(x) for x in ("мын", "мін", "пын", "пін", "бын", "бін", "мыз", "міз", "пыз", "піз", "быз", "біз")}


def _match(word):
    """(ру, подрод или None, точное ли слово) или None. «Табынмын» считается точным."""
    k = skel(word)
    if len(k) < 3:
        return None
    if k in INDEX:
        return INDEX[k] + (True,)
    best = None
    for kk, val in INDEX.items():
        if len(kk) >= 3 and k.startswith(kk) and _sfx(kk, k[len(kk):]):
            if best is None or len(kk) > len(best[0]):
                best = (kk, val)
    if not best:
        return None
    rest = k[len(best[0]):]
    exact = best[1][0] != "Кете" and (rest in PERSON or best[0][-1] + rest in PERSON)
    return best[1] + (exact,)


def find(text, ru_video=True):
    """[(ру, подрод или None)] из комментария, без повторов. Длинные тексты не разбираем."""
    words = re.findall(r"[A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі-]+", text or "")
    words = [w.replace("-", "") for w in words if w.replace("-", "")]
    if not words or len(words) > 15:
        return []
    ctx = any(skel(w) in CTX for w in words)
    if not ru_video and not ctx:
        return []                        # под чужими роликами — только если явно про ру
    short = len(words) == 1 or (len(words) == 2 and any(skel(w) in CHEER for w in words))
    grams = list(words) + [a + b for a, b in zip(words, words[1:])]   # Сары Үйсін, Қара Керей
    out = []
    for g in grams:
        if skel(g) in CTX:
            continue
        m = _match(g)
        if not m:
            continue
        key, sub, exact = m
        if key in STOP and not sub and not (exact and (ctx or (short and ru_video) or skel(g) != skel(key) and ru_video)):
            continue
        if (key, sub) not in out and all(o[0] != key for o in out):
            out.append((key, sub))
    return out


def unclear(text):
    """Союзы (Үйсін, Алшын…) и Қаракесек — в журнал «уточни ру»."""
    ws = [skel(w) for w in re.findall(r"[A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]+", text or "")]
    out = []
    for k in ws:
        for d in (UNIONS, AMBIG):
            for kk, name in d.items():
                if k == kk or (k.startswith(kk) and _sfx(kk, k[len(kk):])):
                    if name not in out:
                        out.append(name)
    return out


# ---------- комментарии (открыто, как видит зритель) ----------

def channel_videos(channel_id, limit=15):
    """[(id ролика, название)] последних роликов канала из открытой RSS-ленты."""
    import requests
    r = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", timeout=30)
    if r.status_code != 200:
        return []
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", r.text, re.S)[:limit]:
        v = re.search(r"<yt:videoId>([\w-]{11})</yt:videoId>", e)
        t = re.search(r"<title>(.*?)</title>", e, re.S)
        if v:
            out.append((v.group(1), t.group(1) if t else ""))
    return out


def _vid(link):
    return (link or "").rstrip("/").rsplit("/", 1)[-1].split("=")[-1]


def read_comments(channel_id, ls, per_video=100):
    """[(id комментария, текст, id автора, под роликом с ру?)]"""
    from youtube_comment_downloader import SORT_BY_RECENT, YoutubeCommentDownloader
    vids = {}
    for vid, title in channel_videos(channel_id):
        vids[vid] = "ру жеңеді" in title.lower() or "какой род" in title.lower()
    for r in ls.get("results", [])[-6:]:              # прошлые ролики с ру — даже если ушли из ленты
        v = _vid(r.get("link"))
        if len(v) == 11:
            vids[v] = True
    dl = YoutubeCommentDownloader()
    out = []
    for vid, is_ru in vids.items():
        try:
            for n, c in enumerate(dl.get_comments_from_url(f"https://www.youtube.com/watch?v={vid}",
                                                           sort_by=SORT_BY_RECENT)):
                if n >= per_video:
                    break
                if not c.get("reply"):
                    out.append((c.get("cid", ""), c.get("text", ""), c.get("channel", ""), is_ru))
        except Exception:  # noqa: BLE001
            pass
    return out


def in_race(ls):
    import race_leagues as RL
    return [r[0] for r in RL.RU] + [e["kk"] for e in ls.get("extra", [])]


def _log_file(lines):
    if lines:
        with open(BASE / "ru_requests.log", "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def take_requests(state, ls, log=print, cfg=None, dry=False):
    """Новые ру из комментариев и из файла ru_requests.txt → в гонку (ls['extra']).
    Возвращает список добавленных сейчас (казахские названия)."""
    ch = (cfg or {}).get("channel_id") or CHANNEL_ID
    seen = ls.setdefault("ru_seen", [])
    seen_set = set(seen)
    have = in_race(ls)
    asked = ls.setdefault("ru_asked", {})
    now = f"{dt.datetime.now():%Y-%m-%d %H:%M}"
    lines, texts = [], []
    f = BASE / "ru_requests.txt"                      # вручную: srv ru Тарақты
    if f.exists():
        for s in f.read_text(encoding="utf-8").splitlines():
            if s.strip():
                texts.append(("файл", s.strip(), 3, True))   # ручная просьба весит как 3 комментария
        if not dry:
            f.write_text("", encoding="utf-8")
    try:
        for cid, text, author, is_ru in read_comments(ch, ls):
            if cid in seen_set or (author and author == ch):
                continue
            seen_set.add(cid)
            seen.append(cid)
            texts.append(("коммент", text, 1, is_ru))
    except Exception as e:  # noqa: BLE001
        log(f"Ру из комментариев: не прочитал ({e})")
    ls["ru_seen"] = seen[-3000:]
    for src, text, w, is_ru in texts:
        hits = find(text, ru_video=is_ru)
        for key, sub in hits:
            via = f" (подрод {sub})" if sub else ""
            if key in have:
                lines.append(f"{now} | {key}{via} | уже есть | {text[:70]}")
                continue
            asked[key] = asked.get(key, 0) + w
            lines.append(f"{now} | {key}{via} | просьба №{asked[key]} | {text[:70]}")
        if not hits:
            for name in unclear(text):
                lines.append(f"{now} | {name} | общее название, не ру — не добавляю | {text[:70]}")
            if src == "файл" and not unclear(text):
                lines.append(f"{now} | ? | нет в списке настоящих ру — не добавляю | {text[:70]}")
    room = CAP - len(have)
    added = [k for k in sorted(asked, key=lambda k: -asked[k]) if k not in have][:min(PER_RACE, max(0, room))]
    if not dry:
        for key in added:
            r = BY_KEY[key]
            ls.setdefault("extra", []).append({"kk": r[0], "ru": r[1], "zhuz": r[2], "date": now})
            asked.pop(key, None)
            lines.append(f"{now} | {key} | ДОБАВЛЕН в гонку")
        _log_file(lines)
    if added:
        log(f"Ру из комментариев: добавляю {', '.join(added)}")
    elif texts:
        log(f"Ру из комментариев: новых просьб нет (прочитано {len(texts)})")
    if room <= 0 and asked:
        log(f"Ру из комментариев: трасса полная ({CAP}), ждут: {', '.join(asked)}")
    return added, lines


def note(added):
    """Строка в начало описания ролика."""
    if not added:
        return ""
    kk = ", ".join(added)
    ru = ", ".join(BY_KEY[k][1] for k in added)
    return f"🆕 Пікірлерде сұрадыңыздар — жаңа ру: {kk} · Новый род по вашей просьбе: {ru}\n\n"


if __name__ == "__main__":
    if "--dry" in sys.argv:          # проверка: что нашлось бы сейчас (ничего не меняет)
        st = json.loads((BASE / "state.json").read_text(encoding="utf-8")) if (BASE / "state.json").exists() else {}
        ls_ = json.loads(json.dumps(st.get("leagues", {}).get("ru", {})))
        added_, lines_ = take_requests(st, ls_, dry=True)
        print("\n".join(lines_[-25:]) or "Про ру в комментариях пока не писали.")
        print(f"\nВ гонке сейчас ру: {len(in_race(ls_))}. В следующий заезд добавился бы: {', '.join(added_) or 'никто'}")
    else:
        for t in sys.argv[1:]:
            print(t, "→", find(t) or unclear(t) or "[]")

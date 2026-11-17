"""Выкладка серий «Кот Барсик» на YouTube через API (только requests). Сделано по образцу бота Flagball Arena (ветка flagball, yt.py).

Вход — секрет GitHub BARSIK_YT: строка из barsik-login.sh (BK1:…:END) или JSON {"client_id","client_secret","refresh_token"}.
Вход должен быть сделан с аккаунта ВЛАДЕЛЬЦА канала: «менеджера» из прав доступа YouTube Studio API не пускает.
Защита: работаем только с каналом CHANNEL_ID; серия уходит закрытой («private») — либо как черновик, либо с таймером выхода (publishAt).
"""
import base64, collections
import hashlib
import json
import os
import re
import time

import requests

API = "https://www.googleapis.com/youtube/v3"
UP = "https://www.googleapis.com/upload/youtube/v3"
CHANNEL_ID = "UCe72zB7nk8xkf3cHFL15luA"      # @cartoon_friend3 «Кот Барсик | Мультфильмы для детей»
PLAYLIST_WORD = "барсик"                      # запасной признак плейлиста канала
# Как устроен канал (смотрел в Studio 17.11.2026): два открытых плейлиста —
#   «Кот Барсик 🐱 | Все серии подряд | Мультики для детей» — все полные серии, по порядку с 1-й (новая — в конец);
#   «Кот Барсик 🐱 | Смешные моменты и Shorts» — все Shorts.
PLAYLIST_KEYS = {"episode": "все серии", "short": "shorts"}
HANDLE = "@cartoon_friend3"
SHORT_PHRASES = ["Что было дальше?", "Вот это да!", "Ну и дела!", "Ты только посмотри!", "Кто бы мог подумать!", "Вот это поворот!", "Угадаешь разгадку?"]
SHORT_TAGS = "#КотБарсик #МультикиДляДетей #Shorts #Мультфильмы #ДетскиеМультфильмы #МультикДляМалышей #cartoon #kidscartoon #shorts"
BASE_TAGS = ["Кот Барсик", "мультики", "мультики для детей", "мультфильм", "мультфильмы для детей", "новая серия",
             "мультик про кота", "развивающие мультики", "для малышей"]
SECRET = "BARSIK_YT"


WS = r"[\s\u200b-\u200f\ufeff\u00a0]+"


def secret_shape(raw):
    """Только форма секрета (длины и счётчики), без единого его знака: статус попадает в открытый репозиторий."""
    flat = re.sub(WS, "", raw)
    cyr = sum(1 for c in flat if "а" <= c.lower() <= "я" or c in "ёЁ")
    b64 = sum(1 for c in flat if re.match(r"[A-Za-z0-9+/=]", c))
    col = flat.count(":")
    parts = [len(x) for x in flat.split(":")]
    kind = ""
    if col:                                                    # что это за строка, если не строка входа: только вид, без содержимого
        pre, rest = flat.split(":", 1)
        known = {"vpn": "ключ VPN (vpn://…)", "http": "ссылка", "https": "ссылка", "ss": "ключ VPN", "vless": "ключ VPN", "ssh": "адрес ssh",
                 "bk1": "строка входа «Кот Барсик»", "fb1": "строка входа другого канала", "kz1": "строка входа другого канала"}
        kind = known.get(pre.lower()) or ("начало из " + "".join("б" if c.isalpha() else "ц" if c.isdigit() else "?" for c in pre[:6]) + " (б — буква, ц — цифра)")
        kind = f"вид: {kind}, после двоеточия «//» {'есть' if rest.startswith('//') else 'нет'}, «END» за {len(flat) - flat.rfind('END') - 3 if 'END' in flat else '—'} зн. до конца, "
        try:
            d = base64.urlsafe_b64decode(re.sub(r"[^A-Za-z0-9_\-]", "", rest.lstrip("/")) + "===")
            kind += ("внутри сжатые данные (так устроен ключ Amnezia VPN), " if len(d) > 5 and d[4] == 0x78 else
                     "внутри JSON, " if d[:1] == b"{" else "внутри не JSON, ")
        except Exception:
            kind += "не base64, "
    odd = [(i, c) for i, c in enumerate(flat) if not re.match(r"[A-Za-z0-9+/=:]", c)]
    hist = collections.Counter(c for _, c in odd)
    gaps = [odd[i + 1][0] - odd[i][0] for i in range(len(odd) - 1)]
    kind += ("посторонние знаки: " + ", ".join(f"«{c}»×{n}" if c.isascii() and not c.isalnum() else f"U+{ord(c):04X}×{n}" for c, n in hist.most_common(8))
             + f"; шаг между ними {gaps[:24]}; первый на {odd[0][0] if odd else '—'}; " if odd else "")
    esc = collections.Counter(x.upper() for x in re.findall(r"%([0-9A-Fa-f]{2})", flat))
    if esc:                                                    # какие знаки телефон записал «по-ссылочному»: 0A — перенос, 3A — двоеточие, 2B — плюс, 20 — пробел
        order = "".join("-" if c == "-" else "%" for _, c in odd)
        kind += "записи «%XX»: " + ", ".join(f"{c}×{n}" for c, n in esc.most_common(8)) + f"; порядок посторонних знаков {order}; "
        codes = [x.upper() for x in re.findall(r"%([0-9A-Fa-f]{2})", flat)]
        kind += f"коды по порядку {' '.join(codes)}; "
    kind += (f"заглавных {sum(c.isupper() for c in flat)}, строчных {sum(c.islower() for c in flat)}, цифр {sum(c.isdigit() for c in flat)}, "
             f"«+» {flat.count('+')}, «/» {flat.count('/')}, «=» {flat.count('=')} (первый на {flat.find('=')}), ")
    return (kind + f"длина {len(raw)}, строк {raw.count(chr(10)) + 1}, пробелов {raw.count(' ')}, двоеточий {col}, "
            f"куски между двоеточиями {parts[:8]}, русских букв {cyr}, прочих знаков {len(flat) - b64 - col - cyr}, "
            f"«BK1» {'есть' if 'BK1' in flat else 'нет'}, «END» {'есть' if 'END' in flat else 'нет'}")


def _try_b64(body, chk):
    b64 = re.sub(r"[^A-Za-z0-9+/=]", "", body).rstrip("=")
    try:
        data = base64.b64decode(b64 + "=" * (-len(b64) % 4))
    except Exception:
        return None
    return data if hashlib.sha256(data).hexdigest()[:8] == chk else None


OCR_NARROW = ["Il1", "O0"]                                   # что распознавание текста путает чаще всего
OCR_WIDE = ["Il1", "O0oQD", "5Ss", "8B", "2Zz", "6G", "9gq", "cC", "kK", "pP", "uU", "vV", "wW", "xX", "yY", "mM", "jJ", "E3", "T7", "nh", "ec", "ao"]
REPAIR_NOTE = ""                                               # что пришлось исправить (число мест, без самих знаков) — в статус


def _ocr_search(body, chk, groups, max_err, deadline):
    """Ключ прошёл через распознавание текста с картинки: ищем, какие 1…max_err знаков прочитаны неверно. Проверка — 8 знаков sha256."""
    import binascii, itertools
    alt = {}
    for g in groups:
        for c in g:
            alt.setdefault(c, set()).update(x for x in g if x != c)
    arr = bytearray(body.encode())
    pos = [(i, [ord(x) for x in sorted(alt[chr(b)])]) for i, b in enumerate(arr) if chr(b) in alt]
    want = bytes.fromhex(chk)
    pad = b"=" * (-len(arr) % 4)
    n = 0
    for k in range(1, max_err + 1):
        for combo in itertools.combinations(pos, k):
            for repl in itertools.product(*[c[1] for c in combo]):
                old = [arr[c[0]] for c in combo]
                for c, r in zip(combo, repl):
                    arr[c[0]] = r
                try:
                    d = binascii.a2b_base64(bytes(arr) + pad)
                    if hashlib.sha256(d).digest()[:4] == want and d[:1] == b"{":
                        json.loads(d)
                        return d, k
                except Exception:
                    pass
                for c, o in zip(combo, old):
                    arr[c[0]] = o
                n += 1
                if n % 200000 == 0 and time.time() > deadline:
                    return None, 0
    return None, 0


def _repair(raw):
    """Строка, прошедшая через чужие руки: телефон принял «BK1:…» за ссылку (строчные буквы в начале, %0A вместо переносов, %3A вместо двоеточий,
    «+» стал пробелом или «-»), переносы стали «\\n» или <br>, двоеточия пропали, текст сняли с картинки. Собираем заново; верно ли собрали —
    скажут 8 проверочных знаков в конце."""
    global REPAIR_NOTE
    import html, itertools, urllib.parse
    seen = []
    for v in (raw, urllib.parse.unquote(raw), html.unescape(raw), urllib.parse.unquote(html.unescape(raw))):
        for w in (v, re.sub(r"\\[rnt]", "", v), re.sub(r"<[^<>]{0,8}>", "", v)):
            if w not in seen:
                seen.append(w)
    ocr = []
    for v in seen:
        t = re.sub(r"[\r\n\t\u200b-\u200f\ufeff]", "", v.strip())            # переносы — точно не часть ключа (и «END» бывает разорван переносом)
        t = re.sub(r"^.*?(?:bk1|fb1)[^A-Za-z0-9+/=]*", "", t, count=1, flags=re.I | re.S)
        t = re.sub(r"[^A-Za-z0-9+/=]*E[^A-Za-z0-9]*N[^A-Za-z0-9]*D[^A-Za-z0-9]*$", "", t)
        t = t.replace(":", "")
        spots = [m.start() for m in re.finditer(r"[^A-Za-z0-9+/=]", t)]    # пробел, «-», «_»… — либо мусор, либо бывший «+» или «/»; «|» — бывшая l, I или 1
        if len(t) < 60:
            continue
        escaped = bool(re.search(r"%[0-9A-Fa-f]{2}", v))                   # «%0A» ещё не развёрнуты — эта запись годится только для прямой проверки
        if len(spots) > 9:                                                 # слишком много неясных мест — пробуем только «всё выбросить»
            spots, t = [], re.sub(r"[^A-Za-z0-9+/=|]", "", t)
            spots = [m.start() for m in re.finditer(r"\|", t)][:6]
        opts = [("l", "I", "1") if t[p] == "|" else ("", "+", "/") for p in spots]
        for fill in itertools.product(*opts):
            u, last = [], 0
            for pos, f in zip(spots, fill):
                u.append(t[last:pos] + f)
                last = pos + 1
            u = "".join(u) + t[last:]
            b64, chk = u[:-8], u[-8:].lower()
            data = _try_b64(b64, chk)
            if data and data[:1] == b"{":
                if spots:
                    REPAIR_NOTE = f"ключ собран заново: неясных мест {len(spots)}"
                return data
            if not escaped and all(f == "" for p, f in zip(spots, fill) if t[p] != "|"):   # мусор выброшен, «|» заменён — заготовки для поиска опечаток
                chk2 = chk.translate(str.maketrans("olisgqzb", "01159926")) if not re.fullmatch(r"[0-9a-f]{8}", chk) else chk
                if re.fullmatch(r"[0-9a-f]{8}", chk2) and len(b64.rstrip("=")) % 4 != 1 and (b64, chk2) not in ocr and len(ocr) < 3:
                    ocr.append((b64, chk2))
    t0 = time.time()
    for groups, max_err, budget in ((OCR_WIDE, 1, 5), (OCR_NARROW, 3, 10), (OCR_WIDE, 2, 45)):
        for b64, chk in ocr[:1] if max_err > 1 else ocr:                    # неверно выбранная замена «|» найдётся как ещё одна опечатка
            data, k = _ocr_search(b64, chk, groups, max_err, time.time() + budget)
            if data:
                REPAIR_NOTE = f"ключ был снят с картинки с ошибками — исправлено знаков: {k} (плюс замена «|»), поиск {time.time() - t0:.0f} с. Лучше вставить ключ заново, текстом"
                return data
    return None


def parse_secret(raw):
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit(f"ЖДУ ВХОД: нет секрета {SECRET} — вход в канал ещё не сделан")
    flat = re.sub(WS, "", raw)   # строка приходит порезанной на строчки по 24 знака: «:END» и «BK1:» могут оказаться разорваны переносом
    k = None
    m = re.search(r":([0-9a-fA-F]{8}):?END", flat)
    if m:                                                      # <что-то>:<8 знаков проверки>:END — начало может быть испорчено или потеряно
        chk, pre = m.group(1).lower(), flat[:m.start()]
        a = re.search(r"(BK1|FB1):", pre)
        cands = ([pre[a.end():]] if a else []) + [pre[i + 1:] for i, c in enumerate(pre[:40]) if c == ":"] + [pre]
        data = next((d for d in (_try_b64(b, chk) for b in cands) if d), None)
        if data is None:                                       # пропала первая строчка из 24 знаков («BK1:» + 20): её содержимое известно, кроме одного знака
            body = re.sub(r"[^A-Za-z0-9+/=]", "", pre)
            for ch in "0123456789":
                head = base64.b64encode(('{"client_id":"' + ch).encode()).decode()
                data = _try_b64(head + body, chk)
                if data:
                    break
        if data is None:
            data = _repair(raw)
        if data is None:
            raise SystemExit(f"строка входа скопирована не целиком или испорчена: проверка не сходится ({secret_shape(raw)})")
        k = json.loads(data)
    elif "{" in raw:
        t = raw.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
        i, j = t.find("{"), t.rfind("}")
        if j > i:
            k = json.loads(re.sub(WS, "", t[i:j + 1]))
    if k is None:
        fixed = _repair(raw)                                   # запись «по-ссылочному», потерянные двоеточия, текст с картинки
        if fixed is not None:
            k = json.loads(fixed)
    if k is None:
        raise SystemExit(f"секрет {SECRET} не похож на строку входа ({secret_shape(raw)})")   # сам секрет не печатаем
    if not all(k.get(x) for x in ("client_id", "client_secret", "refresh_token")):
        raise SystemExit(f"в секрете {SECRET} не хватает полей входа")
    return k


def tags_for(desc):
    tags = list(BASE_TAGS)
    for h in re.findall(r"#([\w\dА-Яа-яЁё]+)", desc or ""):
        if h.lower() not in [t.lower().replace(" ", "") for t in tags]:
            tags.append(h)
    out, n = [], 0
    for t in tags:                                             # у YouTube предел — около 500 знаков на все теги
        n += len(t) + 3
        if n > 450:
            break
        out.append(t)
    return out


def iso_seconds(d):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    return sum(int(x or 0) * k for x, k in zip(m.groups(), (86400, 3600, 60, 1))) if m else 0


def lang_snippet(sn, lang="ru", category="1"):
    """Тело для videos.update(part=snippet): всё, что YouTube иначе сотрёт (описание, теги), переносим как было."""
    new = {"title": sn["title"], "description": sn.get("description", ""), "categoryId": category, "defaultLanguage": lang, "defaultAudioLanguage": lang}
    if sn.get("tags"):
        new["tags"] = sn["tags"]
    return new


def video_body(title, desc, publish_at=None, category="1"):
    """publish_at — время выхода в UTC, вид 2026-11-18T12:30:00Z; без него ролик остаётся закрытым черновиком."""
    st = {"privacyStatus": "private", "selfDeclaredMadeForKids": True, "embeddable": True, "publicStatsViewable": True,
          "license": "youtube"}
    if publish_at:
        st["publishAt"] = publish_at
    return {"snippet": {"title": title[:100], "description": desc[:4900], "tags": tags_for(desc), "categoryId": str(category),
                        "defaultLanguage": "ru", "defaultAudioLanguage": "ru"}, "status": st}


def with_playlist_link(desc, playlist_id):
    """В описание серии — строка со ссылкой на плейлист «Все серии подряд» (перед хэштегами), если её там ещё нет."""
    if not playlist_id or "playlist?list=" in (desc or ""):
        return desc
    line = f"📺 Все серии подряд: https://www.youtube.com/playlist?list={playlist_id}"
    rows = (desc or "").rstrip().split("\n")
    i = len(rows)
    while i > 0 and (rows[i - 1].strip().startswith("#") or not rows[i - 1].strip()):
        i -= 1                                                 # хэштеги остаются последними строками
    return "\n".join(rows[:i] + ["", line, ""] + [r for r in rows[i:] if r.strip()])


def short_body(name, num, full_id, playlist_id=None, publish_at=None, category="1"):
    """Shorts по образцу тех, что уже стоят на канале: «<название серии> 🐱 Кот Барсик | N серия #shorts»."""
    title = f"{name.strip()} 🐱 Кот Барсик | {num} серия #shorts"
    if len(title) > 100:
        title = f"{name.strip()[:100 - len(title) - 1].rstrip()}… 🐱 Кот Барсик | {num} серия #shorts"
    rows = [f"{SHORT_PHRASES[int(num) % len(SHORT_PHRASES)]} 😺 Отрывок из мультика «Кот Барсик», {num} серия.", "",
            f"🎬 Полная серия: https://www.youtube.com/watch?v={full_id}",
            f"📺 Все серии подряд: https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else f"📺 Все серии на канале: https://www.youtube.com/{HANDLE}",
            "", "Котёнок Барсик и его друзья — мышонок Пик, щенок Рон, медвежонок Топа и зайчонок Филя. Добрые и смешные истории о дружбе для детей.",
            "❤️ Подписывайтесь, чтобы не пропустить новые серии!", "", SHORT_TAGS]
    return video_body(title, "\n".join(rows), publish_at, category)


class YT:
    def __init__(self, raw=None):
        self.k = parse_secret(raw if raw is not None else os.environ.get(SECRET, ""))
        self.tok, self.t_tok = None, 0

    def h(self, extra=None):
        if not self.tok or time.time() - self.t_tok > 2700:
            r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data=dict(
                client_id=self.k["client_id"], client_secret=self.k["client_secret"],
                refresh_token=self.k["refresh_token"], grant_type="refresh_token"))
            if r.status_code != 200:
                raise SystemExit(f"Google не пустил (вход устарел или отозван): {r.status_code} {r.text[:200]}")
            self.tok, self.t_tok = r.json()["access_token"], time.time()
        h = {"Authorization": f"Bearer {self.tok}"}
        h.update(extra or {})
        return h

    def channel(self):
        r = requests.get(f"{API}/channels", params={"part": "snippet,statistics,contentDetails", "mine": "true"}, headers=self.h(), timeout=30)
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            raise SystemExit("под этим входом нет канала — вход сделан не с аккаунта владельца канала")
        c = items[0]
        if c["id"] != CHANNEL_ID:
            raise SystemExit(f"вход сделан не в тот канал: «{c['snippet']['title']}» — выкладку отменил")
        return c

    def playlists(self):
        r = requests.get(f"{API}/playlists", params={"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}, headers=self.h(), timeout=30)
        return [{"id": p["id"], "title": p["snippet"]["title"], "n": p["contentDetails"]["itemCount"]} for p in r.json().get("items", [])] if r.status_code == 200 else []

    def last_videos(self, n=15):
        up = self.channel()["contentDetails"]["relatedPlaylists"]["uploads"]
        r = requests.get(f"{API}/playlistItems", params={"part": "contentDetails", "playlistId": up, "maxResults": min(50, n)}, headers=self.h(), timeout=30)
        ids = [i["contentDetails"]["videoId"] for i in r.json().get("items", [])] if r.status_code == 200 else []
        if not ids:
            return []
        r = requests.get(f"{API}/videos", params={"part": "snippet,status,statistics,contentDetails", "id": ",".join(ids)}, headers=self.h(), timeout=30)
        out = []
        for v in r.json().get("items", []) if r.status_code == 200 else []:
            s, st, cd = v["snippet"], v["status"], v.get("statistics", {})
            out.append({"id": v["id"], "title": s["title"], "published": s.get("publishedAt"), "privacy": st.get("privacyStatus"), "publishAt": st.get("publishAt"),
                        "kids": st.get("madeForKids"), "category": s.get("categoryId"), "dur": v["contentDetails"].get("duration"),
                        "views": int(cd.get("viewCount", 0)), "likes": int(cd.get("likeCount", 0))})
        return out

    def set_lang(self, lang="ru", category="1", limit=30, min_sec=180):
        """Старым полным сериям — язык и категория «Фильмы и анимация». Название, описание и теги остаются как были; Shorts не трогаем."""
        up = self.channel()["contentDetails"]["relatedPlaylists"]["uploads"]
        ids, tok = [], None
        for _ in range(3):
            r = requests.get(f"{API}/playlistItems", params={"part": "contentDetails", "playlistId": up, "maxResults": 50, **({"pageToken": tok} if tok else {})},
                             headers=self.h(), timeout=30)
            r.raise_for_status()
            ids += [i["contentDetails"]["videoId"] for i in r.json().get("items", [])]
            tok = r.json().get("nextPageToken")
            if not tok:
                break
        done, skip, shorts, errs = [], 0, 0, []
        for i in range(0, len(ids), 50):
            r = requests.get(f"{API}/videos", params={"part": "snippet,contentDetails", "id": ",".join(ids[i:i + 50])}, headers=self.h(), timeout=30)
            r.raise_for_status()
            for v in r.json().get("items", []):
                sn = v["snippet"]
                if iso_seconds(v["contentDetails"].get("duration")) < min_sec:
                    shorts += 1
                    continue
                new = lang_snippet(sn, lang, category)
                if all(sn.get(k) == new[k] for k in ("categoryId", "defaultLanguage", "defaultAudioLanguage")):
                    skip += 1
                    continue
                if len(done) >= limit or (errs and errs[-1].startswith("СТОП")):
                    continue
                rr = requests.put(f"{API}/videos", params={"part": "snippet"}, headers=self.h({"Content-Type": "application/json"}),
                                  data=json.dumps({"id": v["id"], "snippet": new}), timeout=30)
                if rr.status_code == 200:
                    back = rr.json().get("snippet", {})
                    same = back.get("title") == sn["title"] and back.get("description", "") == sn.get("description", "")
                    done.append({"id": v["id"], "title": sn["title"], "was": [sn.get("categoryId"), sn.get("defaultLanguage"), sn.get("defaultAudioLanguage")],
                                 "now": [back.get("categoryId"), back.get("defaultLanguage"), back.get("defaultAudioLanguage")], "text_same": same})
                else:
                    errs.append(("СТОП " if rr.status_code in (401, 403, 429) else "") + f"{v['id']}: {rr.status_code} {rr.text[:160]}")
                time.sleep(.4)
        return done, skip, shorts, errs

    def upload(self, path, body, notify=True):
        size = os.path.getsize(path)
        r = requests.post(f"{UP}/videos", params={"uploadType": "resumable", "part": "snippet,status", "notifySubscribers": "true" if notify else "false"},
                          headers=self.h({"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4",
                                          "X-Upload-Content-Length": str(size)}), data=json.dumps(body), timeout=60)
        if r.status_code != 200:
            raise SystemExit(f"YouTube не начал загрузку: {r.status_code} {r.text[:500]}")
        url, CH, pos, fails, err = r.headers["Location"], 16 * 1024 * 1024, 0, 0, ""
        with open(path, "rb") as f:
            while True:
                f.seek(pos)
                chunk = f.read(CH)
                end = pos + len(chunk) - 1
                try:
                    rr = requests.put(url, headers=self.h({"Content-Length": str(len(chunk)), "Content-Range": f"bytes {pos}-{end}/{size}"}), data=chunk, timeout=300)
                except requests.RequestException as e:
                    rr, err = None, str(e)
                if rr is not None and rr.status_code in (200, 201):
                    return rr.json()["id"]
                if rr is not None and rr.status_code == 308:
                    rg = rr.headers.get("Range")
                    pos, fails = (int(rg.split("-")[1]) + 1 if rg else 0), 0
                    print(f"  загрузка {pos * 100 // size}%", flush=True)
                    continue
                if rr is not None and rr.status_code < 500 and rr.status_code != 429:
                    raise SystemExit(f"YouTube отказал: {rr.status_code} {rr.text[:500]}")
                fails += 1
                if fails > 8:
                    raise SystemExit(f"загрузка оборвалась: {rr.status_code if rr is not None else err}")
                time.sleep(min(60, 2 ** fails))
                q = requests.put(url, headers=self.h({"Content-Length": "0", "Content-Range": f"bytes */{size}"}), timeout=60)
                if q.status_code in (200, 201):
                    return q.json()["id"]
                rg = q.headers.get("Range")
                pos = int(rg.split("-")[1]) + 1 if (q.status_code == 308 and rg) else 0

    def thumbnail(self, vid, jpg):
        with open(jpg, "rb") as f:
            r = requests.post(f"{UP}/thumbnails/set", params={"videoId": vid}, headers=self.h({"Content-Type": "image/jpeg"}), data=f.read(), timeout=120)
        return "обложка поставлена" if r.status_code == 200 else f"обложка: {r.status_code} {r.text[:200]}"

    def playlist_for(self, kind="episode", pls=None):
        """Плейлист канала под полные серии («Все серии подряд») или под Shorts; None — если не нашёлся."""
        pls = self.playlists() if pls is None else pls
        key = PLAYLIST_KEYS[kind]
        hit = [p for p in pls if key in p["title"].lower()]
        if not hit and kind == "episode":                        # плейлист переименовали — берём самый большой «барсиковый» не про Shorts
            hit = [p for p in pls if PLAYLIST_WORD in p["title"].lower() and PLAYLIST_KEYS["short"] not in p["title"].lower()]
        return sorted(hit, key=lambda x: -x["n"])[0] if hit else None

    def to_playlist(self, vid, kind="episode"):
        p = self.playlist_for(kind)
        if not p:
            return f"плейлист для «{kind}» не найден — ролик без плейлиста"
        r = requests.post(f"{API}/playlistItems", params={"part": "snippet"}, headers=self.h(), timeout=30,
                          json={"snippet": {"playlistId": p["id"], "resourceId": {"kind": "youtube#video", "videoId": vid}}})
        return f"в плейлисте «{p['title']}»" if r.status_code == 200 else f"плейлист: {r.status_code} {r.text[:200]}"

    def status(self, vid):
        r = requests.get(f"{API}/videos", params={"part": "status,processingDetails", "id": vid}, headers=self.h(), timeout=30)
        items = r.json().get("items", []) if r.status_code == 200 else []
        return {**items[0]["status"], "processing": items[0].get("processingDetails", {}).get("processingStatus")} if items else {}

    def cancel(self, vid):
        """Снять таймер выхода: ролик остаётся закрытым. Уже вышедший ролик этим не закрывается — только по отдельной просьбе Михаила."""
        st = self.status(vid)
        if not st:
            return "ролик не найден"
        if st.get("privacyStatus") != "private":
            return f"ролик уже {st.get('privacyStatus')} — не трогаю"
        body = {"id": vid, "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": bool(st.get("selfDeclaredMadeForKids", True)),
                                       "embeddable": st.get("embeddable", True), "license": st.get("license", "youtube")}}
        r = requests.put(f"{API}/videos", params={"part": "status"}, headers=self.h({"Content-Type": "application/json"}), data=json.dumps(body), timeout=30)
        return "таймер снят, ролик закрыт" if r.status_code == 200 else f"не снялся: {r.status_code} {r.text[:200]}"

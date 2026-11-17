"""Выкладка серий «Кот Барсик» на YouTube через API (только requests). Сделано по образцу бота Flagball Arena (ветка flagball, yt.py).

Вход — секрет GitHub BARSIK_YT: строка из barsik-login.sh (BK1:…:END) или JSON {"client_id","client_secret","refresh_token"}.
Вход должен быть сделан с аккаунта ВЛАДЕЛЬЦА канала: «менеджера» из прав доступа YouTube Studio API не пускает.
Защита: работаем только с каналом CHANNEL_ID; серия уходит закрытой («private») — либо как черновик, либо с таймером выхода (publishAt).
"""
import base64
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


def parse_secret(raw):
    raw = (raw or "").strip()
    if not raw:
        raise SystemExit(f"ЖДУ ВХОД: нет секрета {SECRET} — вход в канал ещё не сделан")
    m = re.search(r"(BK1|FB1):", raw)
    if m and ":END" in raw:
        body = raw[m.end():raw.rindex(":END")]
        body = re.sub(r"[^A-Za-z0-9+/=:]", "", body)          # переносы и мусор от копирования с телефона
        b64, chk = body.rsplit(":", 1)
        data = base64.b64decode(b64 + "=" * (-len(b64) % 4))
        if hashlib.sha256(data).hexdigest()[:8] != chk:
            raise SystemExit("строка входа испорчена при копировании (не сходится проверка) — скопируй ещё раз")
        k = json.loads(data)
    else:
        t = raw.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
        i, j = t.find("{"), t.rfind("}")
        if i < 0 or j <= i:
            raise SystemExit(f"секрет {SECRET} не похож на строку входа (длина {len(raw)})")   # сам секрет не печатаем
        k = json.loads(re.sub(r"[\s​-‏﻿   ]+", "", t[i:j + 1]))
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

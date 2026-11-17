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
PLAYLIST_WORD = "барсик"                      # серия кладётся в плейлист, в названии которого есть это слово
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

    def to_playlist(self, vid):
        pl = [p for p in self.playlists() if PLAYLIST_WORD in p["title"].lower()]
        if not pl:
            return "плейлист со словом «Барсик» не найден"
        p = sorted(pl, key=lambda x: -x["n"])[0]
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

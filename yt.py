"""Выкладка на YouTube (канал «Kim yutadi?») напрямую через API, только requests."""
import json
import os
import time

import requests

import ytkey

API = "https://www.googleapis.com/youtube/v3"
UP = "https://www.googleapis.com/upload/youtube/v3"
CHANNEL_MUST = "yutadi"            # защита: выкладываем только на «Kim yutadi?»


def token(cid, sec, rt):
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data=dict(
        client_id=cid, client_secret=sec, refresh_token=rt, grant_type="refresh_token"))
    if r.status_code != 200:
        raise SystemExit(f"Google не пустил (вход устарел? нужен mode: login): {r.status_code} {r.text[:300]}")
    return r.json()["access_token"]


# другие каналы Михаила — на них эта гонка не выкладывается никогда, даже если их переименовать
OTHER = {"@bilesin_be_kz", "@flagballarenatv", "@pochemu_tak_fakty", "@beautiful_shorts-s6u"}


def channel_info(access):
    r = requests.get(f"{API}/channels", params={"part": "snippet,statistics", "mine": "true"},
                     headers={"Authorization": f"Bearer {access}"}, timeout=30)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return {"title": "", "id": "", "handle": "", "videos": 0}
    it = items[0]
    return {"title": it["snippet"]["title"], "id": it["id"], "handle": (it["snippet"].get("customUrl") or "").lower(),
            "videos": int(it.get("statistics", {}).get("videoCount", 0))}


def channel_report(access):
    """Что сейчас стоит на канале: название, адрес, описание, страна, ключевые слова, «для детей», картинки."""
    r = requests.get(f"{API}/channels", params={"part": "snippet,brandingSettings,status,statistics", "mine": "true"},
                     headers={"Authorization": f"Bearer {access}"}, timeout=30)
    items = r.json().get("items", []) if r.status_code == 200 else []
    if not items:
        return f"канал не прочитался: {r.status_code} {r.text[:200]}"
    it = items[0]
    sn, br, st = it.get("snippet", {}), it.get("brandingSettings", {}), it.get("status", {})
    ch = br.get("channel", {})
    th = (sn.get("thumbnails") or {}).get("high", {}).get("url", "")
    lines = [f"Название: {sn.get('title')}", f"Адрес: {sn.get('customUrl') or '— (ещё нет)'}",
             f"Ссылка: https://www.youtube.com/channel/{it['id']}",
             f"Страна: {sn.get('country') or ch.get('country') or '— НЕ УКАЗАНА'}",
             f"Ключевые слова: {ch.get('keywords') or '— нет'}",
             f"Для детей: {st.get('madeForKids')} (сам указал: {st.get('selfDeclaredMadeForKids')})",
             f"Фото: {th or '— нет'}",
             f"Шапка: {'есть' if (br.get('image') or {}).get('bannerExternalUrl') else '— нет'}",
             f"Подписчики: {it.get('statistics', {}).get('subscriberCount')} · роликов: {it.get('statistics', {}).get('videoCount')}",
             "Описание:", sn.get("description") or "— пусто"]
    return "\n".join(lines)


def channel_title(access):
    c = channel_info(access)
    return c["title"], c["id"]


def wrong_channel(c, expect_id=None):
    """Почему этот канал не наш (или None, если наш)."""
    if CHANNEL_MUST not in c["title"].lower():
        return f"вход сделан не в тот канал: «{c['title']}»"
    if c["handle"] in OTHER:
        return f"это другой канал ({c['handle']}), хоть и называется «{c['title']}»"
    if expect_id and c["id"] != expect_id:
        return f"канал не тот, что подключали ({c['id']} вместо {expect_id})"
    return None


class YT:
    def __init__(self):
        self.k = ytkey.credentials()
        if not self.k:
            raise SystemExit("вход в канал ещё не сделан (mode: login)")
        self.tok, self.t_tok = None, 0
        self.handle = ""
        self.retag = None

    def h(self, extra=None):
        if not self.tok or time.time() - self.t_tok > 2700:
            self.tok = token(self.k["client_id"], self.k["client_secret"], self.k["refresh_token"])
            self.t_tok = time.time()
        h = {"Authorization": f"Bearer {self.tok}"}
        h.update(extra or {})
        return h

    def channel(self):
        self.h()
        c = channel_info(self.tok)
        if not c["title"]:
            raise SystemExit("под этим входом нет канала")
        if not self.k.get("channel_id") and not os.environ.get("UZ_YT", "").strip():
            raise SystemExit("вход без номера канала (старый) — нужен новый вход (mode: login)")
        why = wrong_channel(c, self.k.get("channel_id"))
        if why:
            raise SystemExit(why + " — выкладку отменил")
        self.handle = c["handle"]
        return f"{c['title']} {c['handle']} ({c['id']})"

    def upload(self, path, meta):
        # теги — без ʻ и спецзнаков (YouTube на них отвечает INVALID_REQUEST_METADATA), всего не больше 450 знаков
        tags, n = [], 0
        for t in meta.get("tags", []):
            t = t.replace("ʻ", "").replace("'", "").replace("<", "").replace(">", "").strip()
            if t and n + len(t) + 3 <= 450:
                tags.append(t)
                n += len(t) + 3
        title = meta["title"].replace("<", "").replace(">", "")[:100]
        desc = meta["description"].replace("<", "").replace(">", "")[:4900]
        variants = [
            {"title": title, "description": desc, "tags": tags, "categoryId": "24", "defaultLanguage": "uz"},
            {"title": title, "description": desc, "categoryId": "24"},          # запасной: без тегов и языка
        ]
        size = os.path.getsize(path)
        for k, sn in enumerate(variants):
            body = {"snippet": sn,
                    "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "embeddable": True}}
            r = requests.post(f"{UP}/videos", params={"uploadType": "resumable", "part": "snippet,status"},
                              headers=self.h({"Content-Type": "application/json; charset=UTF-8",
                                              "X-Upload-Content-Type": "video/mp4",
                                              "X-Upload-Content-Length": str(size)}),
                              data=json.dumps(body), timeout=60)
            if r.status_code == 200:
                if k:
                    print("загрузка: запасной вариант (без тегов)", flush=True)
                    self.retag = tags
                break
            print(f"YouTube не принял описание (вариант {k + 1}): {r.status_code} {r.text[:300]}", flush=True)
        if r.status_code != 200:
            raise SystemExit(f"YouTube не начал загрузку: {r.status_code} {r.text[:500]}")
        url = r.headers["Location"]
        CH = 16 * 1024 * 1024
        pos, fails, err = 0, 0, ""
        with open(path, "rb") as f:
            while True:
                f.seek(pos)
                chunk = f.read(CH)
                end = pos + len(chunk) - 1
                try:
                    rr = requests.put(url, headers=self.h({"Content-Length": str(len(chunk)),
                                                          "Content-Range": f"bytes {pos}-{end}/{size}"}),
                                      data=chunk, timeout=300)
                except requests.RequestException as e:
                    rr, err = None, str(e)
                if rr is not None and rr.status_code in (200, 201):
                    vid = rr.json()["id"]
                    print(f"загружено: {vid}", flush=True)
                    return vid
                if rr is not None and rr.status_code == 308:
                    rg = rr.headers.get("Range")
                    pos = int(rg.split("-")[1]) + 1 if rg else 0
                    fails = 0
                    continue
                if rr is not None and rr.status_code < 500 and rr.status_code != 429:
                    raise SystemExit(f"YouTube отказал: {rr.status_code} {rr.text[:500]}")
                fails += 1
                if fails > 8:
                    raise SystemExit(f"загрузка оборвалась: {rr.status_code if rr is not None else err}")
                time.sleep(min(60, 2 ** fails))
                q = requests.put(url, headers=self.h({"Content-Length": "0", "Content-Range": f"bytes */{size}"}),
                                 timeout=60)
                if q.status_code in (200, 201):
                    return q.json()["id"]
                rg = q.headers.get("Range")
                pos = int(rg.split("-")[1]) + 1 if (q.status_code == 308 and rg) else 0

    def status(self, vid):
        r = requests.get(f"{API}/videos", params={"part": "status", "id": vid}, headers=self.h(), timeout=30)
        items = r.json().get("items", []) if r.status_code == 200 else []
        return items[0]["status"] if items else {}

    def to_playlist(self, vid, name):
        """Плейлист по теме (создаётся сам при первом ролике)."""
        r = requests.get(f"{API}/playlists", params={"part": "snippet", "mine": "true", "maxResults": 50},
                         headers=self.h(), timeout=30)
        if r.status_code != 200:
            return f"плейлисты не прочитались: {r.status_code}"
        pid = next((p["id"] for p in r.json().get("items", []) if p["snippet"]["title"].strip() == name), None)
        if not pid:
            r = requests.post(f"{API}/playlists", params={"part": "snippet,status"}, headers=self.h(), timeout=30,
                              json={"snippet": {"title": name, "defaultLanguage": "uz"},
                                    "status": {"privacyStatus": "public"}})
            if r.status_code != 200:
                return f"плейлист не создался: {r.status_code} {r.text[:200]}"
            pid = r.json()["id"]
        q = requests.get(f"{API}/playlistItems", params={"part": "id", "playlistId": pid, "videoId": vid},
                         headers=self.h(), timeout=30)
        if q.status_code == 200 and q.json().get("items"):
            return "в плейлисте"
        r = requests.post(f"{API}/playlistItems", params={"part": "snippet"}, headers=self.h(), timeout=30,
                          json={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}})
        return "в плейлисте" if r.status_code == 200 else f"плейлист: {r.status_code} {r.text[:200]}"

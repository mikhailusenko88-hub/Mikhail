"""Выкладка на YouTube (канал Flagball Arena) напрямую через API, только requests.

Ключ берётся из секрета GitHub FLAGBALL_YT — одна строка JSON:
{"client_id": "...", "client_secret": "...", "refresh_token": "..."}
"""
import json
import os
import time

import requests

API = "https://www.googleapis.com/youtube/v3"
UP = "https://www.googleapis.com/upload/youtube/v3"
TAGS = ["marble race", "country marble race", "countryballs", "marble run", "elimination", "32 countries",
        "flags", "satisfying", "marble league", "who wins"]
CHANNEL_MUST = "flagball"          # защита: выкладываем только на Flagball Arena
PLAYLIST = "daily races"


class YT:
    def __init__(self):
        raw = os.environ.get("FLAGBALL_YT", "").strip()
        if not raw:
            raise SystemExit("нет секрета FLAGBALL_YT — вход в YouTube ещё не сделан")
        self.k = json.loads(raw)
        self.tok = None
        self.t_tok = 0

    def h(self, extra=None):
        if not self.tok or time.time() - self.t_tok > 2700:
            r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data=dict(
                client_id=self.k["client_id"], client_secret=self.k["client_secret"],
                refresh_token=self.k["refresh_token"], grant_type="refresh_token"))
            if r.status_code != 200:
                raise SystemExit(f"Google не пустил (вход устарел?): {r.status_code} {r.text[:300]}")
            self.tok, self.t_tok = r.json()["access_token"], time.time()
        h = {"Authorization": f"Bearer {self.tok}"}
        h.update(extra or {})
        return h

    def channel(self):
        r = requests.get(f"{API}/channels", params={"part": "snippet", "mine": "true"}, headers=self.h(), timeout=30)
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            raise SystemExit("под этим входом нет канала")
        title = items[0]["snippet"]["title"]
        if CHANNEL_MUST not in title.lower():
            raise SystemExit(f"вход сделан не в тот канал: «{title}» — выкладку отменил")
        return title

    def upload(self, path, meta):
        body = {
            "snippet": {"title": meta["title"][:100], "description": meta["description"][:4900], "tags": TAGS,
                        "categoryId": "24", "defaultLanguage": "en"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "embeddable": True},
        }
        size = os.path.getsize(path)
        r = requests.post(f"{UP}/videos", params={"uploadType": "resumable", "part": "snippet,status"},
                          headers=self.h({"Content-Type": "application/json; charset=UTF-8",
                                          "X-Upload-Content-Type": "video/mp4",
                                          "X-Upload-Content-Length": str(size)}),
                          data=json.dumps(body), timeout=60)
        if r.status_code != 200:
            raise SystemExit(f"YouTube не начал загрузку: {r.status_code} {r.text[:500]}")
        url = r.headers["Location"]
        CH = 16 * 1024 * 1024
        pos, fails = 0, 0
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
                    rr = None
                    err = str(e)
                if rr is not None and rr.status_code in (200, 201):
                    vid = rr.json()["id"]
                    print(f"загружено: {vid}", flush=True)
                    return vid
                if rr is not None and rr.status_code == 308:
                    rg = rr.headers.get("Range")
                    pos = int(rg.split("-")[1]) + 1 if rg else 0
                    fails = 0
                    print(f"  загрузка {pos * 100 // size}%", flush=True)
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

    def thumbnail(self, vid, jpg):
        with open(jpg, "rb") as f:
            r = requests.post(f"{UP}/thumbnails/set", params={"videoId": vid},
                              headers=self.h({"Content-Type": "image/jpeg"}), data=f.read(), timeout=120)
        return r.status_code, r.text[:300]

    def to_playlist(self, vid):
        r = requests.get(f"{API}/playlists", params={"part": "snippet", "mine": "true", "maxResults": 50},
                         headers=self.h(), timeout=30)
        if r.status_code != 200:
            return f"плейлисты не прочитались: {r.status_code}"
        pid = next((p["id"] for p in r.json().get("items", []) if p["snippet"]["title"].strip().lower() == PLAYLIST), None)
        if not pid:
            return "плейлист Daily Races не найден"
        r = requests.post(f"{API}/playlistItems", params={"part": "snippet"}, headers=self.h(), timeout=30,
                          json={"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}})
        return "в плейлисте" if r.status_code == 200 else f"плейлист: {r.status_code} {r.text[:200]}"

    def status(self, vid):
        r = requests.get(f"{API}/videos", params={"part": "status", "id": vid}, headers=self.h(), timeout=30)
        items = r.json().get("items", []) if r.status_code == 200 else []
        return items[0]["status"] if items else {}

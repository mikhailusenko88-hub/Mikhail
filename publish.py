"""Студия «Кот Барсик»: выкладка на YouTube по строке в publish.txt (ветка studio). Вход — секрет BARSIK_YT (см. yt_barsik.py).

Строка (первая без «#»):
  check                                  — проверить вход: канал, плейлисты, последние ролики
  draft <релиз> <серия>                  — загрузить серию закрытым черновиком (никто не видит)
  plan  <релиз> <серия> <ГГГГ-ММ-ДДTЧЧ:ММ> — загрузить закрытой и поставить таймер выхода (время московское)
  short <релиз> <серия> <ГГГГ-ММ-ДДTЧЧ:ММ> — Shorts этой серии (ep-<релиз>-shorts.mp4) с таймером выхода; полная серия уже должна быть загружена
  cancel <id ролика>                     — снять таймер выхода (ролик остаётся закрытым)
  stats                                  — последние ролики канала: просмотры, статус
<релиз> — имя сборки студии (релиз studio-<релиз>, файл ep-<релиз>.mp4); название, описание и обложка — со страницы
супруги (ветка mebel, s9kbars/serii.json и serii/<серия>/cover.jpg). Итог — youtube/status.txt и youtube/<релиз>.json.
Куда что кладётся (как на канале): полная серия — в плейлист «Все серии подряд», Shorts — в «Смешные моменты и Shorts»;
категория «Фильмы и анимация», язык русский, «для детей»; в описание серии добавляется ссылка на плейлист всех серий.
DRY=1 — ничего не отправлять, только показать, что ушло бы.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

import requests

import yt_barsik as Y

REPO = "mikhailusenko88-hub/Mikhail"
RAW = f"https://raw.githubusercontent.com/{REPO}"
MSK = dt.timezone(dt.timedelta(hours=3))
DRY = os.environ.get("DRY") == "1"
OUT = "youtube"


def say(*a):
    print(*a, flush=True)


def finish(lines, data=None, name=None):
    os.makedirs(OUT, exist_ok=True)
    now = dt.datetime.now(MSK).strftime("%d.%m.%Y %H:%M МСК")
    open(f"{OUT}/status.txt", "w", encoding="utf-8").write("\n".join([lines[0] + f"  ({now})"] + lines[1:]) + "\n")
    if data is not None and name:
        json.dump(data, open(f"{OUT}/{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say("\n".join(lines))


def request_line():
    for ln in open("publish.txt", encoding="utf-8"):
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            return ln.split()
    return []


def card(num):
    loc = os.environ.get("SERII_JSON")                      # для проверки без сети
    d = json.load(open(loc, encoding="utf-8")) if loc else requests.get(f"{RAW}/mebel/s9kbars/serii.json", timeout=30).json()
    it = next((x for x in d.get("items", []) if str(x.get("num")) == str(num)), None)
    if not it:
        raise SystemExit(f"серии {num} нет на странице (serii.json)")
    if f"серия {num}" not in it["title"].lower():
        raise SystemExit(f"в названии нет «серия {num}»: {it['title']}")
    return it


def fetch(url, path, min_bytes):
    subprocess.run(["curl", "-sSL", "--fail", "--retry", "3", "-o", path, url], check=True)
    n = os.path.getsize(path)
    if n < min_bytes:
        raise SystemExit(f"файл слишком мал ({n} байт): {url}")
    return n


def when_utc(s):
    t = dt.datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=MSK)
    left = (t - dt.datetime.now(MSK)).total_seconds()
    if left < 20 * 60:
        raise SystemExit(f"время выхода {s} МСК ближе 20 минут или уже прошло")
    if left > 30 * 86400:
        raise SystemExit(f"время выхода {s} МСК дальше 30 дней — похоже на ошибку")
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), t.strftime("%d.%m.%Y %H:%M МСК")


def short_name(it):
    """Название серии для Shorts: из строки сценария «СЕРИЯ: 27. Почему лодка не тонет?», иначе — вопрос из названия ролика."""
    m = re.search(r"СЕРИЯ:\s*\d+\.\s*(.+)", it.get("scenario") or "")
    if m:
        return m.group(1).strip()
    t = re.sub(r"[^\w\s?!,.«»—-]", "", it["title"].split("|")[0]).strip()
    return (t[:1] + t[1:].lower()).replace("?!", "?") if t.isupper() else t


def short(yt, a, rel, num, it, body_when, last, pe):
    """Shorts серии: как на канале — своё название, ссылка на полную серию, плейлист «Смешные моменты и Shorts»."""
    full = [v for v in last if v["title"].strip() == it["title"].strip()]
    if not full:
        return finish([f"SHORTS НЕ ЗАГРУЖАЛ: полной серии {num} на канале ещё нет — сначала plan {rel} {num} <время>"])
    body = Y.short_body(short_name(it), num, full[0]["id"], pe["id"] if pe else None, body_when[0])
    same = [v for v in last if v["title"].strip() == body["snippet"]["title"].strip()]
    if same and "--again" not in a:
        return finish([f"SHORTS НЕ ЗАГРУЖАЛ: такой уже есть ({same[0]['privacy']}, https://youtu.be/{same[0]['id']}). Повтор — только с --again"])
    full_at = full[0].get("publishAt") or full[0].get("published")
    if full[0]["privacy"] == "private" and full[0].get("publishAt") and body_when[0] < full[0]["publishAt"]:
        return finish([f"SHORTS НЕ ЗАГРУЖАЛ: он вышел бы раньше полной серии ({full_at}) — ссылка вела бы на закрытый ролик"])
    os.makedirs("tmp", exist_ok=True)
    mb = fetch(f"https://github.com/{REPO}/releases/download/studio-{rel}/ep-{rel}-shorts.mp4", "tmp/short.mp4", 500_000) / 1e6
    say(f"Shorts серии {num}, файл {mb:.0f} МБ; загружаю закрытым, выход {body_when[1]}")
    vid = yt.upload("tmp/short.mp4", body)
    pl, st = yt.to_playlist(vid, "short"), yt.status(vid)
    ok = st.get("privacyStatus") == "private" and bool(st.get("publishAt"))
    data = {"mode": "short", "release": rel, "episode": int(num), "id": vid, "url": f"https://youtu.be/{vid}", "full": full[0]["id"],
            "title": body["snippet"]["title"], "publishAt": st.get("publishAt"), "when": body_when[1], "status": st, "playlist": pl, "mb": round(mb, 1)}
    head = f"SHORTS ЗАГРУЖЕН, выйдет {body_when[1]}" if ok else f"SHORTS ЗАГРУЖЕН, НО СТАТУС НЕ ТОТ: {st}"
    finish([f"{head}: серия {num} — https://youtu.be/{vid}", body["snippet"]["title"], f"{pl}; для детей: {st.get('selfDeclaredMadeForKids')}; обработка: {st.get('processing')}",
            f"править в Studio: https://studio.youtube.com/video/{vid}/edit"], data, f"{rel}-short")


def main():
    a = request_line()
    mode = a[0] if a else ""
    if mode not in ("check", "draft", "plan", "short", "cancel", "stats"):
        return finish([f"НЕ ПОНЯЛ строку publish.txt: {' '.join(a)}"])
    if mode in ("draft", "plan", "short"):
        rel, num = a[1], a[2]
        it = card(num)
        body_when = when_utc(a[3]) if mode in ("plan", "short") else (None, None)
        if DRY:
            body = (Y.short_body(short_name(it), num, "<id полной серии>", "<id плейлиста>", body_when[0]) if mode == "short"
                    else Y.video_body(it["title"], Y.with_playlist_link(it["yt_desc"], "<id плейлиста>"), body_when[0]))
            say(json.dumps(body, ensure_ascii=False, indent=1))
            return finish([f"ПРОБА БЕЗ ОТПРАВКИ: {'Shorts серии' if mode == 'short' else 'серия'} {num} из сборки {rel}" + (f", выход {body_when[1]}" if body_when[1] else ", черновик")])
    if not os.environ.get(Y.SECRET, "").strip():
        return finish([f"ЖДУ ВХОД: нет секрета {Y.SECRET} — вход в канал ещё не сделан (режим {mode})"])
    yt = Y.YT()
    ch = yt.channel()
    title = ch["snippet"]["title"]
    if mode in ("check", "stats"):
        vids, pls = yt.last_videos(20), yt.playlists()
        os.makedirs(OUT, exist_ok=True)
        json.dump({"channel": title, "subs": ch["statistics"].get("subscriberCount"), "videos": ch["statistics"].get("videoCount"),
                   "playlists": pls, "last": vids}, open(f"{OUT}/channel.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        plan = [v for v in vids if v["privacy"] == "private" and v.get("publishAt")]
        pe, ps = yt.playlist_for("episode", pls), yt.playlist_for("short", pls)
        return finish([f"ВХОД РАБОТАЕТ: канал «{title}», роликов {ch['statistics'].get('videoCount')}",
                       "плейлисты: " + "; ".join(f"{p['title']} ({p['n']})" for p in pls),
                       f"серии пойдут в: {pe['title'] if pe else 'НЕ НАЙДЕН'}; Shorts — в: {ps['title'] if ps else 'НЕ НАЙДЕН'}",
                       "ждут выхода по таймеру: " + ("; ".join(f"{v['title'][:50]} → {v['publishAt']}" for v in plan) or "нет"),
                       "последний: " + (f"{vids[0]['title'][:70]} — {vids[0]['views']} просмотров, категория {vids[0]['category']}, для детей: {vids[0]['kids']}" if vids else "—")])
    if mode == "cancel":
        return finish([f"ОТМЕНА {a[1]}: {yt.cancel(a[1])}"])
    last, pls = yt.last_videos(50), yt.playlists()
    pe = yt.playlist_for("episode", pls)
    if mode == "short":
        return short(yt, a, rel, num, it, body_when, last, pe)
    body = Y.video_body(it["title"], Y.with_playlist_link(it["yt_desc"], pe["id"] if pe else None), body_when[0])
    same = [v for v in last if v["title"].strip() == it["title"].strip()]
    if same and "--again" not in a:
        v = same[0]
        return finish([f"НЕ ЗАГРУЖАЛ: ролик с таким названием уже есть ({v['privacy']}, https://youtu.be/{v['id']}). Повтор — только с --again"])
    os.makedirs("tmp", exist_ok=True)
    mb = fetch(f"https://github.com/{REPO}/releases/download/studio-{rel}/ep-{rel}.mp4", "tmp/ep.mp4", 20_000_000) / 1e6
    fetch(f"{RAW}/mebel/s9kbars/{it.get('cover') or f'serii/{num}/cover.jpg'}", "tmp/cover.jpg", 20_000)
    say(f"канал «{title}»; серия {num}, файл {mb:.0f} МБ; загружаю закрытой" + (f", выход {body_when[1]}" if body_when[1] else ""))
    vid = yt.upload("tmp/ep.mp4", body)
    th, pl, st = yt.thumbnail(vid, "tmp/cover.jpg"), yt.to_playlist(vid), yt.status(vid)
    ok = st.get("privacyStatus") == "private" and (mode == "draft" or bool(st.get("publishAt")))
    data = {"mode": mode, "release": rel, "episode": int(num), "id": vid, "url": f"https://youtu.be/{vid}", "studio": f"https://studio.youtube.com/video/{vid}/edit",
            "title": it["title"], "publishAt": st.get("publishAt"), "when": body_when[1], "status": st, "thumbnail": th, "playlist": pl, "mb": round(mb)}
    head = (f"ЗАГРУЖЕНО, выйдет {body_when[1]}" if mode == "plan" else "ЗАГРУЖЕНО черновиком (закрыт)") if ok else f"ЗАГРУЖЕНО, НО СТАТУС НЕ ТОТ: {st}"
    finish([f"{head}: серия {num} — https://youtu.be/{vid}", it["title"], f"{th}; {pl}; для детей: {st.get('selfDeclaredMadeForKids')}; обработка: {st.get('processing')}",
            f"править в Studio: https://studio.youtube.com/video/{vid}/edit"], data, rel)


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code not in (None, 0):
            finish([f"СБОЙ: {e.code}"])
            sys.exit(1)
    except Exception as e:                                     # сеть, ответ YouTube не по форме и т. п. — секретов в тексте ошибки нет
        finish([f"СБОЙ: {type(e).__name__}: {str(e)[:300]}"])
        sys.exit(1)

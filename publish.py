"""Студия «Кот Барсик»: выкладка на YouTube по строке в publish.txt (ветка studio). Вход — секрет BARSIK_YT (см. yt_barsik.py).

Строка (первая без «#»):
  check                                  — проверить вход: канал, плейлисты, последние ролики
  draft <релиз> <серия>                  — загрузить серию закрытым черновиком (никто не видит)
  plan  <релиз> <серия> <ГГГГ-ММ-ДДTЧЧ:ММ> — загрузить закрытой и поставить таймер выхода (время московское)
  short <релиз> <серия> <ГГГГ-ММ-ДДTЧЧ:ММ> — Shorts этой серии (ep-<релиз>-shorts.mp4) с таймером выхода; полная серия уже должна быть загружена
    … --file=<путь в ветке> — взять Shorts из файла ветки studio, а не из релиза (Shorts в формате сервера: shorts_server.py)
  cancel <id ролика>                     — снять таймер выхода (ролик остаётся закрытым)
  retime <id ролика> <ГГГГ-ММ-ДДTЧЧ:ММ>  — перенести таймер выхода закрытого ролика (время московское)
  stats                                  — последние ролики канала: просмотры, статус
  lang [сколько] [от скольки секунд]     — старым полным сериям проставить русский язык и категорию «Фильмы и анимация» (текст не меняется, Shorts не трогает)
  thumb <id ролика> <серия>              — заменить обложку ролика на serii/<серия>/cover.jpg со страницы; только закрытому (ещё не вышедшему) ролику
  kanal [--go]                           — главная канала по kanal.json (описание, трейлер для неподписанных); без --go только показать «было/станет»
  sbornik <имя> <ГГГГ-ММ-ДДTЧЧ:ММ>       — сборник серий подряд по sborniki/<имя>.json (склейка ep-<релиз>.mp4 без пересжатия, главы в описании), закрытым с таймером
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
    if Y.REPAIR_NOTE and not lines[0].startswith("СБОЙ"):
        lines = lines + ["ВНИМАНИЕ: " + Y.REPAIR_NOTE]
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
    own = next((x.split("=", 1)[1] for x in a if x.startswith("--file=")), None)   # 22.11: свой файл из ветки (Shorts в формате сервера, проба H28)
    if own:
        if not os.path.exists(own) or os.path.getsize(own) < 500_000:
            return finish([f"SHORTS НЕ ЗАГРУЖАЛ: нет файла {own} в ветке studio"])
        subprocess.run(["cp", own, "tmp/short.mp4"], check=True); mb = os.path.getsize(own) / 1e6
    else:
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
    if mode not in ("check", "draft", "plan", "short", "cancel", "stats", "lang", "retime", "thumb", "kanal", "sbornik"):
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
    if mode == "retime":                                       # перенести таймер: retime <id ролика> <ГГГГ-ММ-ДДTЧЧ:ММ>
        at, human = when_utc(a[2])
        ok, msg = yt.retime(a[1], at)
        return finish([("ТАЙМЕР ПЕРЕНЕСЁН" if ok else "ТАЙМЕР НЕ ПЕРЕНЕСЁН") + f": https://youtu.be/{a[1]} — выйдет {human}" if ok else f"ТАЙМЕР НЕ ПЕРЕНЕСЁН: https://youtu.be/{a[1]}", msg])
    if mode == "thumb":                                        # новая обложка ещё не вышедшему ролику: thumb <id ролика> <серия> (Михаил 19.11: надпись меньше)
        vid, num = a[1], a[2]
        it, st = card(num), yt.status(vid)
        if not st:
            return finish([f"ОБЛОЖКА НЕ ЗАМЕНЕНА: ролика {vid} нет на канале"])
        if st.get("privacyStatus") != "private" and "--public" not in a:
            return finish([f"ОБЛОЖКА НЕ ЗАМЕНЕНА: https://youtu.be/{vid} уже {st.get('privacyStatus')} — вышедшее меняю только с --public (после «да» Михаила)"])
        os.makedirs("tmp", exist_ok=True)
        n = fetch(f"{RAW}/mebel/s9kbars/{it.get('cover') or f'serii/{num}/cover.jpg'}", "tmp/cover.jpg", 20_000)
        th = yt.thumbnail(vid, "tmp/cover.jpg")
        return finish([("ОБЛОЖКА ЗАМЕНЕНА" if th == "обложка поставлена" else "ОБЛОЖКА НЕ ЗАМЕНЕНА") + f": серия {num} — https://youtu.be/{vid} ({st.get('privacyStatus')}, выход {st.get('publishAt')})",
                       f"{th}; файл со страницы {n} байт"])
    if mode == "lang":                                         # старым полным сериям — русский язык и категория «Фильмы и анимация» (разрешил Михаил 17.11.2026)
        done, skip, shorts, errs = yt.set_lang(limit=int(a[1]) if len(a) > 1 and a[1].isdigit() else 30,      # «lang 1» — сначала одна серия на пробу
                                               min_sec=int(a[2]) if len(a) > 2 and a[2].isdigit() else 180)   # «lang 5 60» — и короткие серии-части (не Shorts)
        bad = [d for d in done if not d["text_same"] or d["now"] != ["1", "ru", "ru"]]
        return finish([f"ЯЗЫК И КАТЕГОРИЯ: исправлено серий {len(done)}, уже были в порядке {skip}, Shorts не трогал {shorts}"
                       + (f", ОШИБОК {len(errs)}" if errs else "") + (f", ПРОВЕРИТЬ {len(bad)}" if bad else ""),
                       "название и описание остались как были: " + ("да, у всех" if all(d["text_same"] for d in done) else "НЕ У ВСЕХ")]
                      + [f"  {d['id']} {d['title'][:60]} — было {d['was']}, стало {d['now']}" for d in done] + errs
                      + ["короткие ролики длиннее минуты (проверить, не серии ли): " + ("; ".join(f"{x['title'][:40]} — {x['sec']} с" for x in getattr(yt, "short_list", []) if x["sec"] > 60) or "нет")],
                      {"done": done, "skip": skip, "shorts": shorts, "errs": errs, "short_list": getattr(yt, "short_list", [])}, "lang")
    if mode == "kanal":                                        # главная канала (Михаил 20.11: «ты менеджер, решаешь сам»)
        want = json.load(open("kanal.json", encoding="utf-8"))
        b = yt.branding().get("channel", {})
        lines = [f"КАНАЛ сейчас: трейлер {b.get('unsubscribedTrailer') or 'нет'}; описание {len(b.get('description') or '')} знаков",
                 "разделы главной: " + "; ".join(f"{s.get('pos')}: {s.get('type')} {s.get('title') or ''} {s.get('playlists') or ''}".strip() for s in yt.sections())]
        if "--go" not in a:
            return finish(["ПРОБА (без --go ничего не менял)"] + lines + ["станет: трейлер " + str(want.get("trailer")), "описание станет:", want.get("description", "")],
                          {"now": b, "want": want}, "kanal")
        ok, err, was, now = yt.set_branding(want.get("description"), want.get("trailer"))
        c = now.get("channel", {})
        return finish([("КАНАЛ ОБНОВЛЁН" if ok else "КАНАЛ НЕ ОБНОВЛЁН: " + err),
                       f"трейлер: было {was.get('channel', {}).get('unsubscribedTrailer') or 'нет'}, стало {c.get('unsubscribedTrailer') or 'нет'}",
                       f"описание: {'новое' if c.get('description') == want.get('description') else 'НЕ СОВПАЛО с kanal.json'}; ключевые слова сохранились: {was.get('channel', {}).get('keywords') == c.get('keywords')}"] + lines,
                      {"was": was, "now": now}, "kanal")
    if mode == "sbornik":                                      # сборник: sbornik <имя> <ГГГГ-ММ-ДДTЧЧ:ММ>
        name, (at, human) = a[1], when_utc(a[2])
        sb = json.load(open(f"sborniki/{name}.json", encoding="utf-8"))
        last, pls = yt.last_videos(50), yt.playlists()
        same = [v for v in last if v["title"].strip() == sb["title"].strip()]
        if same and "--again" not in a:
            return finish([f"НЕ ЗАГРУЖАЛ: сборник с таким названием уже есть ({same[0]['privacy']}, https://youtu.be/{same[0]['id']})"])
        if subprocess.run("command -v ffmpeg", shell=True).returncode:
            subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg >/dev/null", shell=True, check=True)
        os.makedirs("tmp", exist_ok=True)
        t0, chapters, files = 0.0, [], []
        for it in sb["items"]:
            f = f"tmp/ep-{it['rel']}.mp4"
            fetch(f"https://github.com/{REPO}/releases/download/studio-{it['rel']}/ep-{it['rel']}.mp4", f, 20_000_000)
            d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip())
            name_ep = it.get("name") or card(str(it["num"]))["title"].split(" | ")[0].strip()
            chapters.append(f"{int(t0 // 60)}:{int(t0 % 60):02d} {name_ep}")
            files.append(f)
            t0 += d
        open("tmp/list.txt", "w").write("".join(f"file '{os.path.basename(f)}'\n" for f in files))
        subprocess.run(["ffmpeg", "-v", "error", "-f", "concat", "-safe", "0", "-i", "tmp/list.txt", "-c", "copy", "-movflags", "+faststart", "tmp/sbornik.mp4"], check=True)
        mb = os.path.getsize("tmp/sbornik.mp4") / 1e6
        pe = yt.playlist_for("episode", pls)
        desc = sb["desc"].replace("{CHAPTERS}", "\n".join(chapters)).replace("{PLAYLIST}", f"https://www.youtube.com/playlist?list={pe['id']}" if pe else f"https://www.youtube.com/{Y.HANDLE}")
        body = Y.video_body(sb["title"], desc, at)
        say(f"сборник {name}: {len(files)} серий, {t0 / 60:.1f} мин, {mb:.0f} МБ; загружаю закрытым, выход {human}")
        vid = yt.upload("tmp/sbornik.mp4", body)
        th = yt.thumbnail(vid, sb["cover"]) if os.path.exists(sb.get("cover", "")) else "обложки нет — YouTube возьмёт кадр"
        st = yt.status(vid)
        ok = st.get("privacyStatus") == "private" and bool(st.get("publishAt"))
        return finish([(f"СБОРНИК ЗАГРУЖЕН, выйдет {human}" if ok else f"СБОРНИК ЗАГРУЖЕН, НО СТАТУС НЕ ТОТ: {st}") + f": https://youtu.be/{vid}", sb["title"],
                       f"{len(files)} серий, {t0 / 60:.1f} мин, {mb:.0f} МБ; {th}; для детей: {st.get('selfDeclaredMadeForKids')}", "главы:"] + chapters,
                      {"id": vid, "url": f"https://youtu.be/{vid}", "title": sb["title"], "publishAt": st.get("publishAt"), "chapters": chapters, "mb": round(mb), "status": st}, f"sbornik-{name}")
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

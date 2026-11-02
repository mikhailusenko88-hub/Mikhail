"""Гонки шариков для бота «Білесің бе?» — 3 ролика в день.

Расписание по времени Астаны (config.json → "race_slots"):
    12:00 — гонка городов «Қай қала жеңеді?»
    15:00 — тема дня по очереди (config "theme_leagues"): мүшел → регионы по номерам → имена
    18:00 — гонка городов
Вручную:  run_daily.py --league names     (cities | regions | mushel | names)
Проба без выкладки:  run_daily.py --test --league mushel
Если тема почему-то не собралась — вместо неё выходит гонка городов (слот не пропадает).

Сезон — неделя (пн–вс по Астане): очки копятся в таблице недели. В воскресенье последний заезд
каждой таблицы (города — в 18:00, тема — в 15:00) — ФИНАЛ лучших недели (топ-8, у мүшел топ-6),
без очков: победитель — чемпион недели. С понедельника таблица начинается заново.
Вручную финал: run_daily.py --league cities --final

Включается в config.json: "mode": "race". Вернуть старые ролики-факты: "mode": "facts".
Таблицы в state.json: "race" — города (как раньше), "leagues" → regions / mushel / names.
Для имён бот сам читает комментарии под прошлыми роликами с именами и добавляет
названные имена (только настоящие имена из списка) в следующий заезд.
Ещё можно вписать имена вручную в файл names_requests.txt (по одному в строке).
"""
import datetime as dt
import json
import random
import sys
import time
import traceback

ASTANA = dt.timezone(dt.timedelta(hours=5))
DEFAULT_SLOTS = {"12": "cities", "15": "theme", "18": "cities"}
DEFAULT_THEMES = ["mushel", "regions", "names"]


def pick_league(cfg, state, argv):
    """Какую гонку делать сейчас. Возвращает (лига, это_тема_дня, последний_слот_этой_лиги_за_день)."""
    slots = cfg.get("race_slots") or DEFAULT_SLOTS
    now = dt.datetime.now(ASTANA)
    if "--league" in argv:
        return argv[argv.index("--league") + 1], False, False
    mins = now.hour * 60 + now.minute
    kind, hour = "cities", None
    for h, v in sorted(slots.items(), key=lambda kv: int(kv[0])):
        if 0 <= mins - int(h) * 60 < 120:      # cron мог запуститься чуть позже
            kind, hour = v, int(h)
    if kind == "theme":
        themes = cfg.get("theme_leagues") or DEFAULT_THEMES
        return themes[state.get("theme_turn", 0) % len(themes)], True, True
    last = hour is not None and hour == max(int(h) for h, v in slots.items() if v == kind)
    return kind, False, last


def week_id(d=None):
    d = d or dt.datetime.now(ASTANA)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def new_week(ls, league, log):
    """С понедельника — новая неделя: таблица начинается заново (старая уходит в архив)."""
    wk = week_id()
    if ls.get("week") == wk:
        return
    if ls.get("week") is None:
        # первый запуск после обновления: уже набранные очки считаем очками этой недели
        ls["week_races"] = ls.get("no", 0)
        ls["week"] = wk
        return
    arch = ls.setdefault("weeks", [])
    top = sorted(ls.get("points", {}).items(), key=lambda kv: -kv[1])[:8]
    arch.append({"week": ls["week"], "top": top, "teams": ls.get("teams"), "champion": ls.get("champion")})
    ls["weeks"] = arch[-60:]
    ls["points"], ls["teams"], ls["champion"], ls["week_races"] = {}, {}, None, 0
    ls["week"] = wk
    log(f"Новая неделя ({wk}): таблица «{league}» начата заново")


def league_state(state, key):
    if key == "cities":
        return state.setdefault("race", {"no": 0, "points": {}, "results": []})
    return state.setdefault("leagues", {}).setdefault(key, {"no": 0, "points": {}, "results": []})


def _vid(link):
    return (link or "").rstrip("/").rsplit("/", 1)[-1]


def collect_name_requests(BASE, ls, cfg, log):
    """Имена, которые зрители написали в комментариях под прошлыми роликами с именами + из файла."""
    import race_leagues as RL
    req = ls.setdefault("requests", [])
    have = {n for n, _ in req}
    added = []
    # вручную: names_requests.txt
    f = BASE / "names_requests.txt"
    if f.exists():
        left = []
        for line in f.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s:
                continue
            team = {"м": "boys", "ж": "girls"}.get(s[:2].strip().lower()) if s[1:2] == " " else None
            name = s[2:].strip() if team else s
            hit = RL.NAME_INDEX.get(RL._norm(name))
            if hit:
                name, team = hit
            if team:
                if name not in have:
                    req.append([name, team])
                    have.add(name)
                    added.append(name)
            else:
                left.append(s)
        f.write_text("\n".join(left) + ("\n" if left else ""), encoding="utf-8")
    # из комментариев
    if cfg.get("post_to_youtube") and (BASE / "yt_token.json").exists() and cfg.get("read_comments", True):
        try:
            import yt_upload
            yt = yt_upload._yt()
            seen = ls.setdefault("seen_comments", [])
            seen_set = set(seen)
            for r in ls.get("results", [])[-4:]:
                vid = _vid(r.get("link"))
                if not vid:
                    continue
                resp = yt.commentThreads().list(part="snippet", videoId=vid, maxResults=100,
                                                textFormat="plainText").execute()
                for it in resp.get("items", []):
                    if it["id"] in seen_set:
                        continue
                    seen_set.add(it["id"])
                    seen.append(it["id"])
                    sn = it["snippet"]["topLevelComment"]["snippet"]
                    if sn.get("authorChannelId", {}).get("value") == it["snippet"].get("channelId"):
                        continue          # свои комментарии не считаем
                    for name, team in RL.names_in_text(sn.get("textOriginal") or sn.get("textDisplay")):
                        if name not in have:
                            req.append([name, team])
                            have.add(name)
                            added.append(name)
            ls["seen_comments"] = seen[-600:]
        except Exception as e:
            log(f"Комментарии: не прочитал ({e})")
    if added:
        log(f"Имена из комментариев/файла: {', '.join(added)}")


def post_first_comment(link, text, log):
    try:
        import yt_upload
        yt_upload._yt().commentThreads().insert(part="snippet", body={"snippet": {
            "videoId": _vid(link), "topLevelComment": {"snippet": {"textOriginal": text}}}}).execute()
        log("Первый комментарий: оставил")
    except Exception as e:
        log(f"Первый комментарий: не получилось ({e})")


def run_league(BASE, cfg, log, notify, state, state_f, league, is_theme, test, no_youtube, last_slot=False):
    import race_video as rv
    import race_leagues as RL
    ls = league_state(state, league)
    new_week(ls, league, log)
    no = ls.get("no", 0) + 1
    ent = None
    if league == "names":
        if not test:
            collect_name_requests(BASE, ls, cfg, log)
        ent = RL.entries("names", ls, random.Random())
    # воскресенье, последний заезд дня для этой таблицы — финал недели
    final = False
    want_final = "--final" in sys.argv or (dt.datetime.now(ASTANA).weekday() == 6 and last_slot)
    if want_final and RL.LEAGUES[league].get("weekly") and ls.get("final_week") != week_id():
        allx = RL.entries(league)
        top_n = 8 if len(allx) >= 16 else 6
        best = [k for k, _ in sorted(ls.get("points", {}).items(), key=lambda kv: -kv[1])][:top_n]
        by_key = {e["key"]: e for e in allx}
        best = [k for k in best if k in by_key]
        if len(best) >= 4:
            ent = [by_key[k] for k in best]
            final = True
            log(f"ФИНАЛ НЕДЕЛИ ({league}): {', '.join(best)}")
    out_dir = BASE / "out"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{dt.datetime.now():%Y-%m-%d_%H%M%S}_{league}{no}.mp4"
    info = rv.build_race(out, race_no=no, points=ls.get("points", {}), log=log, music_dir=BASE / "music",
                         handle=cfg.get("channel_handle", "@bilesin_be_kz"), league=league, entries=ent,
                         team_total=ls.get("teams"), final=final,
                         week_races=None if final else ls.get("week_races", 0) + 1,
                         champions=ls.get("champions", []))
    out.with_suffix(".txt").write_text(info["title"] + "\n\n" + info["description"], encoding="utf-8")
    log(f"Заезд №{no} ({RL.LEAGUES[league]['name']}{', ФИНАЛ НЕДЕЛИ' if final else ''}): победил {info['winner']}, "
        f"топ-3: {', '.join(info['ranking'][:3])}, ролик {info['duration']:.0f} с")
    if test:
        log(f"Тестовый режим: ничего не выкладываю, таблицу не меняю. Ролик: {out}")
        return 0

    link = None
    want_yt = cfg.get("post_to_youtube") and (BASE / "yt_token.json").exists() and not no_youtube
    if want_yt:
        try:
            import yt_upload
            link = yt_upload.upload(out, info["title"], info["description"], info["tags"], cfg)
            log(f"YouTube: {link}")
        except Exception as e:
            log(f"YouTube: ошибка {e}")
            notify(f"Заезд №{no} собран, но не выложен: {e}")
    if link and cfg.get("first_comment", True):
        post_first_comment(link, RL.LEAGUES[league]["first_comment"], log)

    if link or not want_yt:   # заезд засчитываем, только если ролик вышел (или выкладка выключена)
        ls["no"] = no
        if league == "names":
            ls["teams"] = info["team_total"]
            used = ls.setdefault("used", {})
            names_now = set(info["ranking"])
            for n in names_now:
                used[n] = used.get(n, 0) + 1
            ls["requests"] = [r for r in ls.get("requests", []) if r[0] not in names_now]
        elif final:
            ls["champion"] = info["winner"]
            ls["final_week"] = week_id()
            ls.setdefault("champions", []).append({"week": week_id(), "champion": info["winner"], "link": link})
        else:
            ls["points"] = info["points"]
        if not final:
            ls["week_races"] = ls.get("week_races", 0) + 1
        ls.setdefault("results", []).append({"no": no, "date": f"{dt.datetime.now(ASTANA).date()}",
                                             "winner": info["winner"], "top3": info["ranking"][:3],
                                             "link": link, "final": final})
        ls["results"] = ls["results"][-300:]
        if is_theme:
            state["theme_turn"] = state.get("theme_turn", 0) + 1
        state["n_done"] = state.get("n_done", 0) + 1
        state.setdefault("history", []).append({"date": f"{dt.date.today()}", "title": info["title"],
                                                "links": [link] if link else ["вручную"]})
        state["history"] = state["history"][-200:]
        state_f.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if (link or not want_yt) else 1


def run(BASE, cfg, log, notify, test=False, no_youtube=False):
    state_f = BASE / "state.json"
    state = json.loads(state_f.read_text(encoding="utf-8")) if state_f.exists() else \
        {"used_titles": [], "n_done": 0, "history": []}
    league, is_theme, last_slot = pick_league(cfg, state, sys.argv)
    try:
        rc = run_league(BASE, cfg, log, notify, state, state_f, league, is_theme, test, no_youtube, last_slot)
    except Exception as e:
        if league == "cities":
            raise
        log(f"Тема «{league}» не собралась: {e}\n{traceback.format_exc()}")
        log("Вместо неё — гонка городов")
        notify(f"Тема «{league}» не собралась ({e}) — вышла гонка городов")
        if is_theme and not test:
            state["theme_turn"] = state.get("theme_turn", 0) + 1   # завтра — следующая тема
        rc = run_league(BASE, cfg, log, notify, state, state_f, "cities", False, test, no_youtube)

    if cfg.get("post_to_youtube") and (BASE / "yt_token.json").exists() and not no_youtube and not test:
        try:
            import yt_queue
            if yt_queue.pending():
                yt_queue.upload_next(cfg, 1)
        except Exception as e:
            log(f"Очередь YouTube: ошибка {e}")

    out_dir = BASE / "out"
    keep = cfg.get("keep_days", 7)
    for f in list(out_dir.glob("*.mp4")) + list(out_dir.glob("*.txt")):
        if time.time() - f.stat().st_mtime > keep * 86400:
            f.unlink()
    return rc

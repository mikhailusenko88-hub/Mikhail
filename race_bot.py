"""Гонки шариков для бота «Білесің бе?» — 3 ролика в день.

Расписание по времени Астаны (config.json → "race_slots"):
    12:00 — гонка городов «Қай қала жеңеді?»
    15:00 — тема дня по очереди (config "theme_leagues"): мүшел → регионы по номерам → имена
    18:00 — гонка городов
Вручную:  run_daily.py --league names     (cities | regions | mushel | names)
Проба без выкладки:  run_daily.py --test --league mushel
Если тема почему-то не собралась — вместо неё выходит гонка городов (слот не пропадает).

Сезоны:
  города — неделя (пн–вс по Астане): в воскресенье в 18:00 ФИНАЛ топ-8 недели, с понедельника заново;
  темы (мүшел, регионы, имена) — месяц: последний заезд темы в месяце — ФИНАЛ месяца
  (топ-8, у мүшел топ-6; у имён — итог месяца «мальчики vs девочки»), с 1-го числа заново.
Финал без очков, победитель — чемпион (★ у шарика, история чемпионов хранится всегда).
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


def season_id(league, d=None):
    import race_leagues as RL
    d = d or dt.datetime.now(ASTANA)
    if RL.LEAGUES[league].get("season") == "month":
        return f"{d.year}-{d.month:02d}"
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def new_season(ls, league, log):
    """Новая неделя (города) / новый месяц (темы): таблица начинается заново, старая — в архив."""
    sid = season_id(league)
    if ls.get("season") == sid:
        return
    if ls.get("season") is None:
        # первый запуск после обновления: уже набранные очки считаем очками этого сезона
        ls["season_races"] = ls.get("no", 0)
        ls["season"] = sid
        return
    arch = ls.setdefault("seasons", [])
    top = sorted(ls.get("points", {}).items(), key=lambda kv: -kv[1])[:8]
    arch.append({"season": ls["season"], "top": top, "teams": ls.get("teams"), "champion": ls.get("champion")})
    ls["seasons"] = arch[-60:]
    ls["points"], ls["teams"], ls["champion"], ls["season_races"] = {}, {}, None, 0
    ls["season"] = sid
    log(f"Новый сезон ({sid}): таблица «{league}» начата заново")


def days_to_final(cfg, league, ls):
    """Сколько дней до финала этого сезона (для надписи «До финала N дней»)."""
    import race_leagues as RL
    if ls.get("final_season") == season_id(league):
        return None                                   # финал уже был — ждём новый сезон
    now = dt.datetime.now(ASTANA)
    if RL.LEAGUES[league].get("season") == "month":
        n = len(cfg.get("theme_leagues") or DEFAULT_THEMES)
        nxt = (now.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        left = (nxt.date() - now.date()).days - 1    # дней после сегодняшнего до конца месяца
        return n * (left // n)
    return 6 - now.weekday()


def want_final(cfg, league, is_theme, last_slot, argv):
    """Финал: города — воскресенье, последний заезд дня; тема — её последний заезд в этом месяце."""
    import race_leagues as RL
    if "--final" in argv:
        return True
    now = dt.datetime.now(ASTANA)
    if RL.LEAGUES[league].get("season") == "month":
        if not is_theme:
            return False
        n = len(cfg.get("theme_leagues") or DEFAULT_THEMES)
        return (now + dt.timedelta(days=n)).month != now.month     # в этом месяце эта тема больше не выйдет
    return now.weekday() == 6 and last_slot


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


def post_first_comment(link, text, log, tries=4, pause=60):
    """Комментарий от канала под роликом. Сразу после загрузки YouTube может ещё не пускать —
    тогда пробуем снова через минуту (до 4 раз)."""
    import yt_upload
    err = None
    for k in range(tries):
        if k:
            time.sleep(pause)
        try:
            yt_upload._yt().commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": _vid(link), "topLevelComment": {"snippet": {"textOriginal": text}}}}).execute()
            log("Первый комментарий: оставил" + (f" (с {k + 1}-й попытки)" if k else ""))
            return True
        except Exception as e:
            err = e
            msg = str(e)
            if "insufficient" in msg.lower():      # нет прав — повтор не поможет
                break
    log(f"Первый комментарий: ошибка — {str(err)[:300]}")
    return False


def comment_last(BASE, log=print):
    """srv comment — оставить первый комментарий под последним выложенным роликом."""
    import race_leagues as RL
    state = json.loads((BASE / "state.json").read_text(encoding="utf-8"))
    for h in reversed(state.get("history", [])):
        link = next((l for l in h.get("links", []) if "youtu" in l), None)
        if not link:
            continue
        lg = next((k for k, v in RL.LEAGUES.items() if h.get("title", "").startswith(v["q"])), "cities")
        log(f"Ролик: {h.get('title', '')[:60]} → {link}")
        return 0 if post_first_comment(link, RL.LEAGUES[lg]["first_comment"], log, tries=2, pause=20) else 1
    log("Не нашёл выложенных роликов")
    return 1


def run_league(BASE, cfg, log, notify, state, state_f, league, is_theme, test, no_youtube, last_slot=False):
    import race_video as rv
    import race_leagues as RL
    ls = league_state(state, league)
    new_season(ls, league, log)
    sid = season_id(league)
    no = ls.get("no", 0) + 1
    ent = None
    if league == "names":
        if not test:
            collect_name_requests(BASE, ls, cfg, log)
        ent = RL.entries("names", ls, random.Random())
    final = False
    if want_final(cfg, league, is_theme, last_slot, sys.argv) and ls.get("final_season") != sid:
        if RL.LEAGUES[league].get("teams"):
            final = True
            log(f"ФИНАЛ МЕСЯЦА ({league}): итог «мальчики vs девочки»")
    if not final and want_final(cfg, league, is_theme, last_slot, sys.argv) and ls.get("final_season") != sid \
            and not RL.LEAGUES[league].get("teams"):
        allx = RL.entries(league)
        top_n = 8 if len(allx) >= 16 else 6
        best = [k for k, _ in sorted(ls.get("points", {}).items(), key=lambda kv: -kv[1])][:top_n]
        by_key = {e["key"]: e for e in allx}
        best = [k for k in best if k in by_key]
        if len(best) >= 4:
            ent = [by_key[k] for k in best]
            final = True
            log(f"ФИНАЛ ({league}, {sid}): {', '.join(best)}")
    out_dir = BASE / "out"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{dt.datetime.now():%Y-%m-%d_%H%M%S}_{league}{no}.mp4"
    info = rv.build_race(out, race_no=no, points=ls.get("points", {}), log=log, music_dir=BASE / "music",
                         handle=cfg.get("channel_handle", "@bilesin_be_kz"), league=league, entries=ent,
                         team_total=ls.get("teams"), final=final,
                         season_races=None if final else ls.get("season_races", 0) + 1,
                         champions=ls.get("champions", []), season_id=sid,
                         final_in=None if final else days_to_final(cfg, league, ls))
    out.with_suffix(".txt").write_text(info["title"] + "\n\n" + info["description"], encoding="utf-8")
    log(f"Заезд №{no} ({RL.LEAGUES[league]['name']}{', ФИНАЛ' if final else ''}): победил {info['winner']}, "
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
    if link or not want_yt:   # заезд засчитываем, только если ролик вышел (или выкладка выключена)
        ls["no"] = no
        if league == "names":
            ls["teams"] = info["team_total"]
            used = ls.setdefault("used", {})
            names_now = set(info["ranking"])
            for n in names_now:
                used[n] = used.get(n, 0) + 1
            ls["requests"] = [r for r in ls.get("requests", []) if r[0] not in names_now]
            if final:
                tb, tg = info["team_total"].get("boys", 0), info["team_total"].get("girls", 0)
                if tb != tg:
                    ls["champion"] = "boys" if tb > tg else "girls"
                    ls.setdefault("champions", []).append({"season": sid, "champion": ls["champion"],
                                                           "score": [tb, tg], "link": link})
                ls["final_season"] = sid
        elif final:
            ls["champion"] = info["winner"]
            ls["final_season"] = sid
            ls.setdefault("champions", []).append({"season": sid, "champion": info["winner"], "link": link})
        else:
            ls["points"] = info["points"]
        if not final:
            ls["season_races"] = ls.get("season_races", 0) + 1
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
    if link and cfg.get("first_comment", True):
        post_first_comment(link, RL.LEAGUES[league]["first_comment"], log)
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


if __name__ == "__main__":
    from pathlib import Path
    if "comment" in sys.argv:
        sys.exit(comment_last(Path(__file__).resolve().parent))
    print(__doc__)

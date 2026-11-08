"""Один запуск на GitHub для канала «Kim yutadi?»: гонка → YouTube → таблица сохраняется в ветке uz-race.

Расписание по Ташкенту (UTC+5), 3 ролика в день:
  слот 1 — ~12:00 гонка городов   (Qaysi shahar yutadi?)
  слот 2 — ~16:00 гонка машин     (Qaysi mashina yutadi?)
  слот 3 — ~20:00 гонка футбольных клубов (Qaysi jamoa yutadi?)
Сезон — неделя (пн–вс по Ташкенту): в воскресенье последний заезд темы — ФИНАЛ (топ-8 недели), с понедельника
таблица заново, чемпионы недель сохраняются навсегда (★ у шарика).

request.txt (ручной запуск — поменять и запушить):
  mode:   test (собрать, не выкладывать) | publish (собрать и выложить) | login (вход в канал кодом,
          после входа сразу выкладывается гонка текущего слота) | check (что стоит на канале → status/channel.txt)
  league: auto | cities | cars | clubs
  final:  auto | yes
  mode: comments — только прочитать комментарии и добавить просьбы (без ролика)
  extra:  yes — ещё один ролик прямо сейчас, сверх расписания (то же делает кнопка Run workflow на GitHub)
Отчёт всегда в status/last.txt (логи Actions из облака не видно).
"""
import datetime as dt
import json
import os
import random
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
TASH = dt.timezone(dt.timedelta(hours=5))
WORK = Path("/tmp/uz")
LOG = []
SLOTS = {1: ("cities", 12), 2: ("cars", 16), 3: ("clubs", 20)}
LAST_SLOT = {"cities": 1, "cars": 2, "clubs": 3}           # в воскресенье в этот слот — финал недели
PLAYLIST = {"cities": "Qaysi shahar yutadi? · Гонка городов", "cars": "Qaysi mashina yutadi? · Гонка машин",
            "clubs": "Qaysi jamoa yutadi? · Гонка клубов"}
HANDLE = "@kimyutadi_uz"


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(f"{dt.datetime.now(TASH):%H:%M:%S} {s}")
    print(s, flush=True)


def write_status(head, extra="", name="last.txt"):
    os.makedirs("status", exist_ok=True)
    with open(f"status/{name}", "w", encoding="utf-8") as f:
        f.write(head + "\n\n" + extra + "\n\n--- журнал (время Ташкента) ---\n" + "\n".join(LOG[-120:]) + "\n")


def git_push(msg, paths):
    subprocess.run(["git", "config", "user.name", "uz-race-bot"])
    subprocess.run(["git", "config", "user.email", "uz-race-bot@users.noreply.github.com"])
    subprocess.run(["git", "add", "-A"] + paths)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return
    subprocess.run(["git", "commit", "-qm", msg])
    for _ in range(5):
        if subprocess.run(["git", "pull", "-q", "--rebase", "origin", "uz-race"]).returncode == 0 and \
                subprocess.run(["git", "push", "-q", "origin", "HEAD:uz-race"]).returncode == 0:
            return
        time.sleep(5)


def read_request():
    req = {"mode": "publish", "league": "auto", "final": "auto", "date": "auto", "slot": "auto"}
    if os.environ.get("EVENT") == "push" and os.path.exists("request.txt"):
        for line in open("request.txt", encoding="utf-8"):
            line = line.split("#")[0].strip()
            if ":" in line:
                k, v = (x.strip() for x in line.split(":", 1))
                req[k] = v
    if os.environ.get("EVENT") == "workflow_dispatch":
        if os.environ.get("IN_KIND") == "schedule":         # будильник с сервера — как обычный запуск по расписанию
            req.update({"mode": "publish"})
        else:                                               # кнопка «Run workflow» на GitHub — ещё один ролик сейчас
            req.update({"mode": "publish", "extra": "yes", "league": os.environ.get("IN_LEAGUE") or "auto"})
    return req


def due_slot(now, history):
    """Догонялка: самый ранний слот, время которого уже наступило, а ролика ещё нет.
    GitHub иногда пропускает запуск по расписанию — тогда следующий запуск выложит пропущенный."""
    done = {(h.get("date"), h.get("slot")) for h in history}
    cands = []
    if now.hour < 5:                                        # вечерний слот вчера (запуск ушёл за полночь)
        cands.append((now.date() - dt.timedelta(days=1), 3))
    for s, (_, hr) in sorted(SLOTS.items()):
        start = dt.datetime(now.year, now.month, now.day, hr, tzinfo=TASH) - dt.timedelta(minutes=40)
        if now >= start:
            cands.append((now.date(), s))
    for d, s in cands:
        if (d.isoformat(), s) not in done:
            return d, s
    return None


def auto_slot(now):
    h = now.hour
    if h < 5:
        return now.date() - dt.timedelta(days=1), 3
    if h < 14:
        return now.date(), 1
    if h < 18:
        return now.date(), 2
    return now.date(), 3


# ---------------- вход в канал (google.com/device) ----------------

def login():
    import requests
    import ytkey
    import yt
    cid, sec = ytkey.app_client()
    r = requests.post("https://oauth2.googleapis.com/device/code", timeout=30,
                      data={"client_id": cid, "scope": "https://www.googleapis.com/auth/youtube"}).json()
    if "device_code" not in r:
        write_status(f"ВХОД: Google не выдал код: {r}", name="login.txt")
        raise SystemExit(f"Google не выдал код: {r}")
    url, code = r.get("verification_url", "https://www.google.com/device"), r["user_code"]
    left = r.get("expires_in", 1800)
    log(f"код {code}, действует {left // 60} мин")
    write_status(f"ВХОД: КОД {code}  ·  открыть {url}  ·  до {dt.datetime.now(TASH) + dt.timedelta(seconds=left):%H:%M} Ташкента",
                 "Открой ссылку, введи код, выбери аккаунт и канал Kim yutadi?, нажми «Разрешить».", name="login.txt")
    git_push(f"ВХОД: код {code}", ["status/login.txt"])
    iv, deadline = r.get("interval", 5), time.time() + left - 5
    while time.time() < deadline:
        time.sleep(iv)
        t = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
            "client_id": cid, "client_secret": sec, "device_code": r["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}).json()
        e = t.get("error")
        if e == "authorization_pending":
            continue
        if e == "slow_down":
            iv += 5
            continue
        if "refresh_token" not in t:
            write_status(f"ВХОД НЕ ПОЛУЧИЛСЯ: {t}", name="login.txt")
            raise SystemExit(f"вход не получился: {t}")
        c = yt.channel_info(t["access_token"])
        title, ch_id = c["title"], c["id"]
        why = yt.wrong_channel(c)
        if not why and c["videos"] > 30:
            why = f"на канале «{title}» уже {c['videos']} роликов — это не новый канал"
        if why:
            write_status(f"ВХОД В ДРУГОЙ КАНАЛ: {why} — нужен новый Kim yutadi?, запусти вход ещё раз",
                         name="login.txt")
            raise SystemExit(why)
        ytkey.seal(t["refresh_token"], cid, sec, title, ch_id)
        log(f"вход сделан: «{title}» {c['handle']} ({ch_id}), роликов {c['videos']}")
        write_status(f"ВХОД ОК: канал «{title}» https://www.youtube.com/channel/{ch_id}",
                     yt.channel_report(t["access_token"]), name="login.txt")
        git_push(f"ВХОД ОК: {title}", ["status/login.txt", "login"])
        return True
    write_status("ВХОД: код истёк, никто не ввёл — запусти вход ещё раз", name="login.txt")
    raise SystemExit("код истёк")


# ---------------- сезоны ----------------

CAP = {"cities": 30, "cars": 28, "clubs": 26}       # больше шариков трасса не вмещает красиво


def take_requests(state, yt, log):
    """Новые города и машины из комментариев: узнаём в любом написании, уже участвующих не добавляем второй раз."""
    import race_leagues as RL
    import uz_places as P
    vids = [h["link"].rsplit("/", 1)[-1] for h in state.get("history", []) if h.get("link")]
    try:
        items, err = yt.comments(yt.k.get("channel_id"), vids)
    except Exception as e:  # noqa: BLE001
        log(f"комментарии не прочитались: {str(e)[:150]}")
        return
    if err:
        log(f"комментарии: {err.strip(' ·')}")
    seen = state.setdefault("seen_comments", [])
    seen_set = set(seen)
    fresh = [c for c in items if c[0] not in seen_set][::-1]          # от старых к новым
    rows = []
    for cid, text, _ in fresh:
        seen.append(cid)
        for lg in ("cities", "cars"):
            ls = league_state(state, lg)
            for key in P.find(text, lg):
                have = {e["key"] for e in RL.entries(lg, ls.get("extra"))}
                if key in have:
                    res = "уже есть"
                elif len(have) >= CAP[lg]:
                    q = ls.setdefault("queue", [])
                    res = "в очереди (трасса полная)" if key in q else (q.append(key) or "в очереди (трасса полная)")
                else:
                    ls.setdefault("extra", []).append(key)
                    ls.setdefault("new_pending", []).append(key)
                    res = "ДОБАВЛЕН"
                    log(f"из комментария добавлен: {key} ({lg})")
                rows.append(f"| {dt.datetime.now(TASH):%m-%d %H:%M} | {lg} | {key} | {res} | {text[:60].replace('|', '/')} |")
    state["seen_comments"] = seen[-3000:]
    if fresh:
        log(f"комментариев новых: {len(fresh)}, просьб: {len(rows)}")
    if rows:
        f = Path("status/comments.md")
        old = f.read_text(encoding="utf-8").splitlines()[2:] if f.exists() else []
        f.write_text("| когда | гонка | что | итог | комментарий |\n|---|---|---|---|---|\n" +
                     "\n".join((rows[::-1] + old)[:300]) + "\n", encoding="utf-8")


def league_state(state, key):
    return state.setdefault("leagues", {}).setdefault(key, {"no": 0, "points": {}, "results": []})


def season_id(now):
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def new_season(ls, sid):
    if ls.get("season") == sid:
        return
    if ls.get("season") is not None:
        arch = ls.setdefault("seasons", [])
        top = sorted(ls.get("points", {}).items(), key=lambda kv: -kv[1])[:8]
        arch.append({"season": ls["season"], "top": top, "champion": ls.get("champion")})
        ls["seasons"] = arch[-60:]
        log(f"новая неделя ({sid}): таблица начата заново")
    ls["points"], ls["champion"], ls["season_races"] = {}, None, 0
    ls["season"] = sid


def main():
    t0 = time.time()
    req = read_request()
    mode = req["mode"]
    log(f"режим {mode}, событие {os.environ.get('EVENT')}")
    if mode == "login":
        then = req.get("then", "publish")
        if not login() or then not in ("publish", "comments"):
            return
        log(f"вход сделан — дальше: {then}")
        mode = req["mode"] = then
    if mode == "probe":          # проверка чтения комментариев на чужом/старом ролике: probe: VIDEOID
        import comments_pub
        import uz_places as P
        from youtube_comment_downloader import SORT_BY_RECENT, YoutubeCommentDownloader
        got = []
        for n, c in enumerate(YoutubeCommentDownloader().get_comments_from_url(
                f"https://www.youtube.com/watch?v={req.get('probe')}", sort_by=SORT_BY_RECENT)):
            if n >= 20:
                break
            got.append(f"- {c.get('text', '')[:80]} → города {P.find(c.get('text', ''), 'cities')}")
        write_status(f"ПРОБА комментариев {req.get('probe')}: прочитано {len(got)}", "\n".join(got))
        return
    if mode == "comments":       # только прочитать комментарии и добавить просьбы (без ролика)
        import yt as ytmod
        y_ = ytmod.YT()
        log("канал:", y_.channel())
        st_ = json.loads(Path("state.json").read_text(encoding="utf-8"))
        take_requests(st_, y_, log)
        Path("state.json").write_text(json.dumps(st_, ensure_ascii=False, indent=1), encoding="utf-8")
        ex = {lg: v.get("extra", []) for lg, v in st_.get("leagues", {}).items()}
        write_status(f"КОММЕНТАРИИ прочитаны; добавлены по просьбам: {json.dumps(ex, ensure_ascii=False)}")
        return
    if mode == "check":          # что сейчас стоит на канале (описание, страна, ключевые слова…)
        import yt as ytmod
        y_ = ytmod.YT()
        y_.h()
        write_status("КАНАЛ: " + y_.channel(), ytmod.channel_report(y_.tok), name="channel.txt")
        return

    now = dt.datetime.now(TASH)
    d, slot = auto_slot(now)
    if mode == "publish" and req.get("extra") != "yes" and req["date"] == "auto" and req["slot"] == "auto":
        st0 = json.loads(Path("state.json").read_text(encoding="utf-8"))
        due = due_slot(now, st0.get("history", []))
        if due is None:
            log("все слоты на это время уже выложены — ничего не делаю")
            write_status(f"ПРОПУСК {now:%Y-%m-%d %H:%M}: всё по расписанию уже выложено", name="kick.txt")
            return
        if due != (d, slot):
            log(f"догоняю пропущенный слот: {due[0]} слот {due[1]}")
        d, slot = due
    if req["date"] != "auto":
        d = dt.date.fromisoformat(req["date"])
    if req["slot"] != "auto":
        slot = int(req["slot"])
    league = SLOTS[slot][0] if req["league"] == "auto" else req["league"]
    day = dt.datetime(d.year, d.month, d.day, SLOTS[slot][1], tzinfo=TASH)

    state = json.loads(Path("state.json").read_text(encoding="utf-8"))
    extra = req.get("extra") == "yes"
    if extra:            # дополнительный ролик сверх расписания: слот 0, расписание не трогает
        d, slot, day = now.date(), 0, now
        if req["league"] == "auto":
            last = [h.get("league") for h in state.get("history", [])]
            league = {"cities": "cars", "cars": "clubs"}.get(last[-1] if last else "", "cities")
        log(f"дополнительный ролик сейчас: {league}")
    if mode == "publish" and not extra and any(h.get("date") == d.isoformat() and h.get("slot") == slot
                                 for h in state.get("history", [])):
        log("этот слот уже выложен — пропускаю")
        write_status(f"ПРОПУСК {d} слот {slot}: уже выложено")
        return

    yt = None
    if mode == "publish":
        import ytkey
        if not ytkey.credentials():
            log("вход в канал ещё не сделан — ничего не выкладываю")
            write_status(f"ЖДУ ВХОД: канал не подключён ({d} слот {slot} пропущен)")
            return
        import yt as ytmod
        yt = ytmod.YT()
        log("канал:", yt.channel())
        # ролики, которые сразу после выкладки не встали в плейлист (YouTube ещё обрабатывал) — добавляем сейчас
        for h_ in state.get("history", [])[-12:]:
            if h_.get("link") and not h_.get("pl"):
                try:
                    res = yt.to_playlist(h_["link"].rsplit("/", 1)[-1], PLAYLIST[h_["league"]])
                except Exception as e:  # noqa: BLE001
                    res = str(e)[:120]
                h_["pl"] = res == "в плейлисте"
                log(f"плейлист для {h_['league']} №{h_['no']}: {res[:120]}")
        try:
            take_requests(state, yt, log)
        except Exception as e:  # noqa: BLE001 — просьбы из комментариев не должны мешать выкладке
            log(f"просьбы из комментариев: ошибка {type(e).__name__}: {str(e)[:150]}")

    import race_leagues as RL
    import race_video as rv
    ls = league_state(state, league)
    sid = season_id(day)
    new_season(ls, sid)
    no = ls.get("no", 0) + 1
    extra = ls.get("extra", [])
    ent, final = RL.entries(league, extra), False
    want_final = req["final"] == "yes" or (day.weekday() == 6 and slot == LAST_SLOT[league])
    if want_final and ls.get("final_season") != sid and (ls.get("season_races", 0) >= 2 or req["final"] == "yes"):
        allx = RL.entries(league, extra)
        by_key = {e["key"]: e for e in allx}
        best = [k for k, _ in sorted(ls.get("points", {}).items(), key=lambda kv: -kv[1]) if k in by_key][:8]
        if len(best) >= 4:
            ent, final = [by_key[k] for k in best], True
            log(f"ФИНАЛ НЕДЕЛИ ({league}, {sid}): {', '.join(best)}")
    final_in = None if (final or ls.get("final_season") == sid) else 6 - day.weekday()

    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / f"{d}_{slot}_{league}{no}.mp4"
    info = rv.build_race(out, race_no=no, points=ls.get("points", {}), log=log, music_dir=BASE / "music",
                         handle=(yt.handle if yt and yt.handle else HANDLE), league=league, entries=ent, final=final,
                         season_races=None if final else ls.get("season_races", 0) + 1,
                         champions=ls.get("champions", []), season_id=sid, final_in=final_in,
                         seed=random.SystemRandom().randrange(100000), extra=extra,
                         new=None if final else ls.get("new_pending", []))
    size = out.stat().st_size / 1e6
    log(f"ролик готов: {info['duration']:.0f} с, {size:.0f} МБ, сборка {time.time() - t0:.0f} с; "
        f"победил {info['winner']}, топ-3: {', '.join(info['ranking'][:3])}")
    meta = {"title": info["title"], "description": info["description"], "tags": info["tags"]}

    if mode != "publish":
        # кадры для проверки: начало, середина, победа, финал
        shutil.rmtree("status/test", ignore_errors=True)
        os.makedirs("status/test", exist_ok=True)
        dur = info["duration"]
        for k, ts in enumerate((2.5, dur * 0.45, dur - 9.0, dur - 3.0, dur - 0.5)):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{max(0, ts):.2f}", "-i", str(out),
                            "-frames:v", "1", "-vf", "scale=540:-1", f"status/test/{league}_{k + 1}.jpg"])
        write_status(f"ТЕСТ ОК: {league} №{no}{' ФИНАЛ' if final else ''} собран за {time.time() - t0:.0f} с, "
                     f"{size:.0f} МБ (не выложен)", json.dumps(meta, ensure_ascii=False, indent=1))
        return

    vid = yt.upload(str(out), meta)
    link = f"https://youtube.com/shorts/{vid}"
    log("YouTube:", link)
    pl = yt.to_playlist(vid, PLAYLIST[league])
    log(pl)
    st = yt.status(vid)
    log("статус:", st.get("privacyStatus"), st.get("uploadStatus"))
    # таблица двигается только после удачной выкладки
    ls["no"] = no
    if not final:
        ls["new_pending"] = []
    if final:
        ls["champion"] = info["winner"]
        ls["final_season"] = sid
        ls.setdefault("champions", []).append({"season": sid, "champion": info["winner"], "link": link})
    else:
        ls["points"] = info["points"]
        ls["season_races"] = ls.get("season_races", 0) + 1
    ls.setdefault("results", []).append({"no": no, "date": d.isoformat(), "slot": slot, "winner": info["winner"],
                                         "top3": info["ranking"][:3], "link": link, "final": final})
    ls["results"] = ls["results"][-300:]
    state.setdefault("history", []).append({"date": d.isoformat(), "slot": slot, "league": league, "no": no,
                                            "final": final, "link": link, "title": info["title"],
                                            "pl": pl == "в плейлисте"})
    state["history"] = state["history"][-500:]
    Path("state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    with open("status/uploads.md", "a", encoding="utf-8") as f:
        f.write(f"| {d} | {slot} | {league} №{no}{' ФИНАЛ' if final else ''} | {info['winner']} | {link} | "
                f"{st.get('privacyStatus')} |\n")
    warn = "" if st.get("privacyStatus") == "public" else "  ⚠️ НЕ ОТКРЫТ"
    write_status(f"ВЫЛОЖЕНО {d} слот {slot}: {league} №{no}{' ФИНАЛ' if final else ''} {link}{warn}, "
                 f"за {time.time() - t0:.0f} с", json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        LOG.append(traceback.format_exc()[-2500:])
        if not isinstance(e, SystemExit) or str(e):
            write_status(f"ОШИБКА: {e}")
        print(e, flush=True)
        sys.exit(1)

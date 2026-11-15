"""Один запуск на GitHub: заезд сезона → обложка → YouTube → сезон сохраняется в ветке.

По расписанию (3 раза в день) — выкладка. По изменению request.txt — что там написано:
  mode: test     собрать ролик и обложку, ничего не выкладывать, лигу не менять
  mode: publish  собрать и выложить (как по расписанию)
  date / slot    auto или конкретные значения
Отчёт всегда в status/last.txt (из облака логи Actions не видно, поэтому пишем сюда).
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
MSK = dt.timezone(dt.timedelta(hours=3))
WORK = "/tmp/fb"
LOG = []
HEATS_PER_VIDEO = {1: 2, 2: 3, 3: 2, 4: 1}     # заездов в одном видео по раундам
# С 15.11.2026 длинное видео — раз в неделю (воскресенье, вечерний слот = мега-трасса) и в гранд-финал.
# В остальные слоты на канал идёт только Shorts: длинные набирали 13–180 просмотров, Shorts — сотни и тысячи.
LONG_SLOTS = {(6, 2)}                           # (день недели: 0 = понедельник … 6 = воскресенье, слот)
ARENA_SLOT = 3      # с 15.11.2026: слот 3 — ролик из игры Flagball Arena (проверка H14), гонки — в слотах 1 и 2
GAMES_REPO = "https://github.com/mikhailusenko88-hub/Mikhail"
ARENA_SERVER = "wss://89.126.192.214/ws"


def long_due(d, slot, final, req):
    v = (req.get("long") or "auto").lower()
    if v in ("yes", "да", "1"):
        return True
    if v in ("no", "нет", "0"):
        return False
    return final or (d.weekday(), slot) in LONG_SLOTS


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(f"{dt.datetime.now(MSK):%H:%M:%S} {s}")
    print(s, flush=True)


def read_request():
    req = {"mode": "publish", "date": "auto", "slot": "auto"}
    if os.environ.get("EVENT") == "push" and os.path.exists("request.txt"):
        for line in open("request.txt", encoding="utf-8"):
            line = line.split("#")[0].strip()
            if ":" in line:
                k, v = (x.strip() for x in line.split(":", 1))
                req[k] = v
    return req


SLOT_HOURS = {1: 7, 2: 15, 3: 23}                  # по Москве; запуск ~за 30 мин до выхода


def due_slot(now, history):
    """Догонялка: самый ранний слот, время которого уже наступило, а ролика ещё нет.
    GitHub иногда пропускает запуск по расписанию — тогда следующий запуск выложит пропущенный."""
    done = {(h.get("date"), h.get("slot")) for h in history} | arena_done()
    cands = []
    if now.hour < 5:                                   # вечерний слот вчера (запуск ушёл за полночь)
        cands.append((now.date() - dt.timedelta(days=1), 3))
    for s, hr in sorted(SLOT_HOURS.items()):
        start = dt.datetime(now.year, now.month, now.day, hr, tzinfo=MSK) - dt.timedelta(minutes=45)
        if now >= start:
            cands.append((now.date(), s))
    for d, s in cands:
        if (d.isoformat(), s) not in done:
            return d, s
    return None


def auto_slot(now):
    """Слоты по Москве: 1 — утро (~07:00), 2 — день (~15:00), 3 — вечер (~23:00)."""
    h = now.hour
    if h < 5:                                   # вечерний запуск задержался за полночь
        return now.date() - dt.timedelta(days=1), 3
    if h < 11:
        return now.date(), 1
    if h < 19:
        return now.date(), 2
    return now.date(), 3


def write_status(head, extra=""):
    os.makedirs("status", exist_ok=True)
    with open("status/last.txt", "w", encoding="utf-8") as f:
        f.write(head + "\n\n" + extra + "\n\n--- журнал ---\n" + "\n".join(LOG[-80:]) + "\n")


def arena_done():
    """Слоты, где ролик из игры уже был (или пытались — чтобы неудача не блокировала гонки)."""
    out = set()
    if os.path.exists("status/arena_done.txt"):
        for line in open("status/arena_done.txt", encoding="utf-8"):
            p = line.split()
            if len(p) >= 2:
                out.add((p[0], int(p[1])))
    return out


def arena_slot(d, slot, mode, t0):
    """Слот 3: Shorts с арены игры Flagball Arena (камера-зритель, широкий план, ~25 с) → YouTube."""
    G = "/tmp/games"
    shutil.rmtree(G, ignore_errors=True)
    run = lambda *a, **k: subprocess.run(*a, check=True, **k)  # noqa: E731
    try:
        run(["git", "clone", "-q", "--depth", "1", "--branch", "games", "--single-branch", "--filter=blob:none",
             "--sparse", GAMES_REPO, G])
        run(["git", "-C", G, "sparse-checkout", "set", "online", "core", "shorts"])
        subprocess.run("sudo apt-get install -y -qq fonts-noto-color-emoji >/dev/null 2>&1", shell=True)
        run(["npm", "i", "--silent", "--no-save", "--prefix", G, "playwright-core@1"])
        web = f"{G}/web"
        os.makedirs(web, exist_ok=True)
        for f in ("online/game.js", "online/index.html", "core/core.js"):
            shutil.copy(f"{G}/{f}", web)
        srv = subprocess.Popen([sys.executable, "-m", "http.server", "8770"], cwd=web, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        env = dict(os.environ, PLAYWRIGHT=f"{G}/node_modules/playwright-core", GAME_URL="http://localhost:8770/index.html",
                   SERVER=ARENA_SERVER, ROOM="main", CLIP="19", WIDE="2.2", CHROME="/usr/bin/google-chrome",
                   END_CAP="FLAGBALL ARENA · COMING SOON")
        out = f"{WORK}/arena"
        try:
            p = subprocess.run(["node", "shorts/record.js", out], cwd=G, env=env, capture_output=True, text=True,
                               timeout=900)
        finally:
            srv.terminate()
        for line in (p.stdout + p.stderr).splitlines()[-15:]:
            LOG.append(line)
        if p.returncode:
            raise RuntimeError(f"съёмка арены упала (код {p.returncode})")
        meta = json.load(open(f"{out}/meta.json"))
        mp4 = f"{out}/{meta['file']}"
        log(f"ролик с арены: {meta['duration']} с, победа {meta.get('winner')}, людей {meta.get('players')}")
        # названия стран полностью (в record.js короткий словарь → «BD», «SA»)
        NM = json.load(open("names.json"))
        SHORTN = {"us": "USA", "gb": "UK", "ae": "UAE", "kr": "Korea", "ru": "Russia", "cz": "Czechia"}
        nm = lambda c: SHORTN.get(c.lower(), NM.get(c.lower(), c.upper()))  # noqa: E731
        flag = lambda c: "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in c.upper()) if len(c) == 2 else ""  # noqa: E731
        top = meta.get("top") or []
        vs = " vs ".join(f"{flag(c)} {nm(c)}" for c, _ in top[:3])
        meta["title"] = (("Real players! " if meta.get("players") else "") +
                         (f"Which country wins? {vs}" if vs else "Which country wins this round?") + " #shorts")
        win = meta.get("winner")
        desc = (f"Round won by {flag(win)} {nm(win)}!\n\n" if win else "") + (
            ("Online battle" if meta.get("players") else "Gameplay") + " from Flagball Arena: every ball is a country. "
            "Eat smaller balls, run from bigger ones, win the round for your flag.\n\n"
            "Is your country here? Write it in the comments!")
        desc += ("\n\nFlagball Arena — the online game is coming soon. Daily country marble races on this channel."
                 "\n\n#shorts #flagball #countryballs #iogame #flags #countries")
        title = meta["title"][:100]
        if mode != "publish":
            os.makedirs("status", exist_ok=True)
            for tt in (0.3, 3, 10, 20):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(tt), "-i", mp4, "-frames:v", "1",
                                "-vf", "scale=360:-2", f"status/test_arena_{tt:04.1f}.jpg"])
            with open("status/test_arena.txt", "w", encoding="utf-8") as f:
                f.write(title + "\n\n" + desc + "\n")
            write_status(f"ТЕСТ АРЕНЫ ОК: {meta['duration']} с за {time.time() - t0:.0f} с (не выложено)", title)
            return
        import yt as ytmod
        yt = ytmod.YT()
        svid = yt.upload(mp4, {"title": title, "description": desc})
        sst = yt.status(svid)
        with open("status/uploads.md", "a", encoding="utf-8") as f:
            f.write(f"| arena | {d} | {slot} | {meta.get('winner')} | https://youtube.com/shorts/{svid} | "
                    f"{sst.get('privacyStatus')} (игра) |\n")
        with open("status/arena_done.txt", "a", encoding="utf-8") as f:
            f.write(f"{d.isoformat()} {slot} {svid} {meta['duration']}\n")
        warn = "" if sst.get("privacyStatus") == "public" else "  ⚠️ НЕ ОТКРЫТ"
        write_status(f"ВЫЛОЖЕНО АРЕНА {d} слот {slot}: Shorts https://youtube.com/shorts/{svid} "
                     f"({sst.get('privacyStatus')}){warn}, за {time.time() - t0:.0f} с", json.dumps(meta, ensure_ascii=False))
    except BaseException as e:  # noqa: BLE001
        if mode == "publish":       # неудача не должна блокировать следующие гонки
            with open("status/arena_done.txt", "a", encoding="utf-8") as f:
                f.write(f"{d.isoformat()} {slot} FAILED\n")
        LOG.append(traceback.format_exc()[-1500:])
        write_status(f"ОШИБКА АРЕНЫ {d} слот {slot}: {e}")


def main():
    t0 = time.time()
    req = read_request()
    mode = req["mode"]
    now = dt.datetime.now(MSK)
    d, slot = auto_slot(now)
    if req["date"] != "auto":
        d = dt.date.fromisoformat(req["date"])
    if req["slot"] != "auto":
        slot = int(req["slot"])
    state = json.load(open("season_state.json"))
    if mode == "publish" and req["date"] == "auto" and req["slot"] == "auto":
        due = due_slot(now, state["history"])
        if due is None:
            log("все слоты на это время уже выложены — ничего не делаю")
            os.makedirs("status", exist_ok=True)
            with open("status/kick.txt", "w", encoding="utf-8") as f:
                f.write(f"ПРОПУСК {now:%Y-%m-%d %H:%M} МСК: всё по расписанию уже выложено\n")
            return
        if due != (d, slot):
            log(f"догоняю пропущенный слот: {due[0]} слот {due[1]}")
        d, slot = due
    if slot == ARENA_SLOT and req.get("arena", "auto").lower() not in ("no", "нет", "0"):
        log(f"режим {mode}, {d} слот {slot}: ролик из игры Flagball Arena")
        if mode == "publish" and not os.environ.get("FLAGBALL_YT", "").strip():
            write_status(f"ЖДУ ВХОД: нет секрета FLAGBALL_YT ({d} слот {slot} пропущен)")
            return
        arena_slot(d, slot, mode, t0)
        return
    n = state["race_no"] + 1
    log(f"режим {mode}, гонка #{n}, {d} слот {slot}, событие {os.environ.get('EVENT')}")
    import season
    log("по плану:", f"S{state['season']}", season.label(season.current(state)))

    if mode == "publish" and any(h.get("date") == d.isoformat() and h.get("slot") == slot for h in state["history"]):
        log("эта гонка уже выложена — пропускаю")
        write_status(f"ПРОПУСК {d} слот {slot}: уже выложено")
        return

    yt = None
    if mode == "publish" and not os.environ.get("FLAGBALL_YT", "").strip():
        log("секрета FLAGBALL_YT пока нет — жду вход в канал, ничего не делаю")
        write_status(f"ЖДУ ВХОД: нет секрета FLAGBALL_YT ({d} слот {slot} пропущен)")
        return
    if mode == "publish":
        import yt as ytmod
        yt = ytmod.YT()
        log("канал:", yt.channel())

    os.makedirs(WORK, exist_ok=True)
    tmp_state = f"{WORK}/state.json"
    shutil.copy("season_state.json", tmp_state)

    # ---- сколько заездов в одном видео: раунд целиком (отбор — по 2), чтобы ролик был 4–8 минут
    import season as SE
    cur = SE.current(state)
    left = cur["heats"] - (cur["heat"] - 1)
    k = 1 if cur.get("lives_mode") else min(HEATS_PER_VIDEO.get(cur["round"], 1), left)   # «3 жизни»: 1 гонка = 1 видео
    log(f"в этом видео заездов: {k} (раунд {cur['round']}, осталось в раунде {left})")
    parts = []
    for j in range(k):
        name = f"{WORK}/race_{n + j:03d}"
        cmd = [sys.executable, "race.py", "--date", d.isoformat(), "--slot", str(slot), "--state", tmp_state,
               "--out", name + ".mp4"]
        if j < k - 1:
            cmd.append("--no-next")
        if req.get("preview"):
            cmd += ["--preview", req["preview"]]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            line = line.rstrip()
            print(line, flush=True)
            if not line.startswith("кадр "):
                LOG.append(line)
        if p.wait():
            raise SystemExit("race.py упал")
        parts.append((name + ".mp4", json.load(open(name + ".json"))))
        log(f"заезд {j + 1}/{k} готов: {os.path.getsize(name + '.mp4') / 1e6:.0f} МБ, {time.time() - t0:.0f} с")

    # ---- склейка
    name = f"{WORK}/video_{n:03d}"
    if k == 1:
        shutil.copy(parts[0][0], name + ".mp4")
    else:
        with open(f"{WORK}/concat.txt", "w") as f:
            for mp4, _ in parts:
                f.write(f"file '{mp4}'\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{WORK}/concat.txt",
                        "-c", "copy", "-movflags", "+faststart", name + ".mp4"], check=True)
    metas = [m for _, m in parts]
    m0 = metas[0]
    codes = [c for m in metas for c in m["codes"]]
    meta = dict(m0)
    meta.update({"codes": codes, "n": sum(m["n"] for m in metas), "survive": sum(m["survive"] for m in metas),
                 "heats_in_video": k, "ranking": [c for m in metas for c in m["ranking"]],
                 "races": [m["race_no"] for m in metas], "slot": slot})
    # «лица» выкладки: три страны из одного заезда — тот же заезд идёт в Shorts.
    # Название видео, обложка и Shorts показывают одни и те же страны (зритель из Shorts
    # жмёт «связанное видео» и видит то, что обещали).
    import popular
    best = max(parts, key=lambda pm: -popular.POS.get(popular.featured(pm[1]["codes"], 1)[0], 999))
    trio = popular.featured(best[1]["codes"], 3)
    meta["featured"] = trio
    if k > 1:
        h0, h1 = m0["heat"], metas[-1]["heat"]
        meta["heat_label"] = f"HEATS {h0}–{h1}/{m0['heats']}"
        meta["label"] = f"{m0['label'].split(' · ')[0]} · HEATS {h0}–{h1}/{m0['heats']}"
        import race as RC
        plan = {"season": m0["season"], "round": m0["round"], "heat": h0, "heats": m0["heats"], "codes": m0["codes"],
                "survive": meta["survive"], "final": m0["final"], "race_no": m0["race_no"], "alive": 0}
        meta["title"] = RC.titles(plan, "", codes=trio, heats_txt=f"Heats {h0}–{h1}/{m0['heats']}")
        blocks = []
        for m in metas:
            names = ", ".join(sorted(RC.NAMES[c] for c in m["codes"]))
            blocks.append(f"Heat {m['heat']}/{m['heats']} — {m['n']} countries, {m['survive']} survive: {names}.")
        tail = metas[-1]["description"]
        i = tail.find("Countries still in the game")
        tail = tail[i:] if i >= 0 else ""
        meta["description"] = (f"Flagball Arena · Season {m0['season']}, {meta['label'].title()}: {meta['n']} countries, "
                               f"only {meta['survive']} survive.\n\n" + "\n\n".join(blocks) + "\n\n" + tail)
        # главы
        t = 0.0
        ch = []
        for m in metas:
            mm, ss = divmod(int(t), 60)
            ch.append(f"{mm:02d}:{ss:02d} Heat {m['heat']}/{m['heats']} — {RC.vs_line(m['codes'], 2)}")
            t += m.get("duration", 0)
        meta["description"] = meta["description"].rstrip() + "\n\nChapters:\n" + "\n".join(ch)
    json.dump(meta, open(name + ".json", "w"), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, "thumb.py", name + ".json", name + ".jpg"], check=True)
    size = os.path.getsize(name + ".mp4") / 1e6
    log(f"видео готово: {size:.0f} МБ, {sum(m.get('duration', 0) for m in metas) / 60:.1f} мин, "
        f"{time.time() - t0:.0f} с с начала; название: {meta['title']}")

    # ---- Shorts из самого «кликабельного» заезда (1 на выкладку — лимит YouTube API)
    short = None
    try:
        import shorts
        pre = {"lives": cur.get("lives") or {}, "alive": cur.get("alive"), "heat": cur.get("heat"),
               "heats": cur.get("heats"), "eliminated": state.get("eliminated") or [],
               "final_date": state.get("final_date")}
        short = shorts.make(best[0], best[0][:-4] + ".json", name + "_short.mp4", pre=pre)
        short["meta"] = best[1]
        log(f"Shorts готов: {short['duration']:.0f} с — {short['title']}")
    except Exception as e:  # noqa: BLE001 — Shorts не должен ломать выкладку
        log(f"Shorts не собрался: {e}")

    long_video = long_due(d, slot, bool(m0.get("final")), req)
    log("длинное видео в этом слоте:", "да" if long_video else "нет (только Shorts)")
    if short is None and not long_video:
        long_video = True
        log("Shorts не собрался — выкладываю длинное видео, чтобы слот не пропал")

    if mode != "publish":
        shutil.copy(name + ".jpg", "status/test_thumb.jpg")
        if short:
            for t in (0, 0.5, 1.5, 3, 5.5, 6.5, 10, max(0.1, short["duration"] - 3)):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", name + "_short.mp4",
                                "-frames:v", "1", "-vf", "scale=540:-2", f"status/test_short_{t:04.1f}.jpg"])
            with open("status/test_short.txt", "w", encoding="utf-8") as f:
                f.write(f"{short['title']}\n{short['duration']:.1f} с\nдлинное видео в слоте: {long_video}\n\n"
                        + shorts.story_description(short["meta"], short.get("pre"),
                                                   "" if not long_video else "https://youtu.be/XXXX"))
        write_status(f"ТЕСТ ОК: видео #{n} ({k} заезд.) собрано за {time.time() - t0:.0f} с, {size:.0f} МБ (не выложено)",
                     json.dumps({kk: v for kk, v in meta.items() if kk != "ranking"}, ensure_ascii=False, indent=1))
        return

    if not long_video:
        # ---- только Shorts: сезон двигается после удачной выкладки Shorts
        smeta = {"title": short["title"], "description": shorts.story_description(short["meta"], short.get("pre"))}
        svid = yt.upload(name + "_short.mp4", smeta)
        sst = yt.status(svid)
        log("Shorts на YouTube:", sst)
        shutil.copy(tmp_state, "season_state.json")
        for m in metas:
            m["video_id"] = None
            m["short_id"] = svid
            json.dump(m, open(f"races/race_{m['race_no']:03d}.json", "w"), ensure_ascii=False, indent=1)
        with open("status/uploads.md", "a", encoding="utf-8") as f:
            f.write(f"| shorts | {d} | {slot} | {short['vs']} | https://youtube.com/shorts/{svid} | "
                    f"{sst.get('privacyStatus')} (только Shorts) |\n")
        warn = "" if sst.get("privacyStatus") == "public" else "  ⚠️ НЕ ОТКРЫТ"
        write_status(f"ВЫЛОЖЕНО #{n} {d} слот {slot}: Shorts https://youtube.com/shorts/{svid} "
                     f"({sst.get('privacyStatus')}, без длинного){warn}, за {time.time() - t0:.0f} с",
                     json.dumps({kk: v for kk, v in meta.items() if kk != "ranking"}, ensure_ascii=False, indent=1))
        return

    vid = yt.upload(name + ".mp4", meta)
    meta["video_id"] = vid
    th = yt.thumbnail(vid, name + ".jpg")
    log("обложка:", th[0], "" if th[0] == 200 else th[1])
    log(yt.to_playlist(vid))
    st = yt.status(vid)
    meta["privacy"] = st.get("privacyStatus")
    log("статус на YouTube:", st)
    # сезон двигается только после удачной выкладки
    shutil.copy(tmp_state, "season_state.json")
    for m in metas:
        m["video_id"] = vid
        json.dump(m, open(f"races/race_{m['race_no']:03d}.json", "w"), ensure_ascii=False, indent=1)
    with open("status/uploads.md", "a", encoding="utf-8") as f:
        f.write(f"| {'–'.join(str(x) for x in meta['races'])} | {d} | {slot} | S{meta['season']} {meta['label']} | "
                f"https://youtu.be/{vid} | {meta['privacy']} |\n")
    short_link = ""
    if short:
        try:
            smeta = {"title": short["title"],
                     "description": shorts.story_description(short["meta"], short.get("pre"), f"https://youtu.be/{vid}")}
            svid = yt.upload(name + "_short.mp4", smeta)
            short_link = f" + Shorts https://youtube.com/shorts/{svid}"
            with open("status/uploads.md", "a", encoding="utf-8") as f:
                f.write(f"| shorts | {d} | {slot} | {short['vs']} | https://youtube.com/shorts/{svid} | |\n")
        except BaseException as e:  # noqa: BLE001
            log(f"Shorts не выложился: {e}")
    warn = "" if meta["privacy"] == "public" else "  ⚠️ НЕ ОТКРЫТ"
    write_status(f"ВЫЛОЖЕНО #{n} {d} слот {slot}: https://youtu.be/{vid} ({meta['privacy']}){warn}{short_link}, "
                 f"за {time.time() - t0:.0f} с", json.dumps({kk: v for kk, v in meta.items() if kk != "ranking"},
                                                             ensure_ascii=False, indent=1))


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        LOG.append(traceback.format_exc()[-2000:])
        write_status(f"ОШИБКА: {e}")
        print(e, flush=True)
        sys.exit(1)

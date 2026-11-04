"""Один запуск на GitHub: гонка → обложка → YouTube → лига сохраняется в ветке.

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
    state = json.load(open("league_state.json"))
    n = state["race_no"] + 1
    log(f"режим {mode}, гонка #{n}, {d} слот {slot}, событие {os.environ.get('EVENT')}")

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
    shutil.copy("league_state.json", tmp_state)
    name = f"{WORK}/race_{n:03d}"
    cmd = [sys.executable, "race.py", "--date", d.isoformat(), "--slot", str(slot), "--state", tmp_state,
           "--out", name + ".mp4"]
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
    subprocess.run([sys.executable, "thumb.py", name + ".json", name + ".jpg"], check=True)
    meta = json.load(open(name + ".json"))
    meta["slot"] = slot
    size = os.path.getsize(name + ".mp4") / 1e6
    log(f"ролик готов: {size:.0f} МБ, {time.time() - t0:.0f} с с начала; название: {meta['title']}")

    if mode != "publish":
        shutil.copy(name + ".jpg", "status/test_thumb.jpg")
        write_status(f"ТЕСТ ОК: гонка #{n} собрана за {time.time() - t0:.0f} с, {size:.0f} МБ (не выложена)",
                     json.dumps(meta, ensure_ascii=False, indent=1))
        return

    vid = yt.upload(name + ".mp4", meta)
    meta["video_id"] = vid
    th = yt.thumbnail(vid, name + ".jpg")
    log("обложка:", th[0], "" if th[0] == 200 else th[1])
    log(yt.to_playlist(vid))
    st = yt.status(vid)
    meta["privacy"] = st.get("privacyStatus")
    log("статус на YouTube:", st)
    # лига: только после удачной выкладки
    shutil.copy(tmp_state, "league_state.json")
    json.dump(meta, open(f"races/race_{n:03d}.json", "w"), ensure_ascii=False, indent=1)
    with open("status/uploads.md", "a", encoding="utf-8") as f:
        f.write(f"| {n} | {d} | {slot} | https://youtu.be/{vid} | {meta['privacy']} | {meta['ranking'][0]} |\n")
    warn = "" if meta["privacy"] == "public" else "  ⚠️ НЕ ОТКРЫТ"
    write_status(f"ВЫЛОЖЕНО #{n} {d} слот {slot}: https://youtu.be/{vid} ({meta['privacy']}){warn}, "
                 f"за {time.time() - t0:.0f} с", json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        LOG.append(traceback.format_exc()[-2000:])
        write_status(f"ОШИБКА: {e}")
        print(e, flush=True)
        sys.exit(1)

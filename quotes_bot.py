"""Бот «Живые строки»: выкладывает готовые ролики-цитаты по плану в 09:00, 14:00 и 19:00 МСК.

  quotes tick    — запускает cron каждые 10 минут (сам решает, пора ли)
  quotes status  — что выложено и что дальше
  quotes now     — выложить следующий ролик прямо сейчас
  quotes pause / quotes resume — остановить / продолжить выкладку

Ролики берутся по порядку из schedule_30d.json и скачиваются с GitHub (ветки quotes-out-dXX)
незадолго до выкладки; после выкладки файл удаляется. Пропущенное время не сжигает ролики —
очередь просто сдвигается на следующий слот.
"""
import datetime as dt
import fcntl
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
MSK = dt.timezone(dt.timedelta(hours=3))
SLOTS = ["09:00", "14:00", "19:00"]
LATE_OK = dt.timedelta(hours=3)          # слот считается «своим» ещё 3 часа
RAW = "https://raw.githubusercontent.com/mikhailusenko88-hub/Mikhail"
STATE = BASE / "state.json"
PLAN = BASE / "schedule_30d.json"
CFG = BASE / "config.json"
VID = BASE / "videos"


def log(msg):
    line = f"{dt.datetime.now(MSK):%Y-%m-%d %H:%M}  {msg}"
    print(line, flush=True)
    with open(BASE / "bot.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_state(st):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def plan():
    return sorted(load(PLAN, []), key=lambda v: v["n"])


def state():
    st = load(STATE, {})
    st.setdefault("next", 1)
    st.setdefault("slots_done", [])
    st.setdefault("posted", [])
    return st


def next_video(st):
    for v in plan():
        if v["n"] == st["next"]:
            return v
    return None


def ensure_file(v):
    VID.mkdir(exist_ok=True)
    path = VID / f"{v['name']}.mp4"
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    url = f"{RAW}/quotes-out-d{v['day']:02d}/{v['name']}.mp4"
    tmp = path.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    if tmp.stat().st_size < 1_000_000:
        tmp.unlink()
        raise RuntimeError(f"скачался слишком маленький файл {v['name']}")
    tmp.replace(path)
    log(f"скачал {v['name']} ({path.stat().st_size / 1e6:.1f} МБ)")
    return path


def due_slot(now, st):
    for s in reversed(SLOTS):
        h, m = map(int, s.split(":"))
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        key = f"{t:%Y-%m-%d} {s}"
        if t <= now and now - t < LATE_OK and key not in st["slots_done"]:
            return key
    return None


def upload(v, path, cfg):
    import yt_upload
    from googleapiclient.http import MediaFileUpload
    yt = yt_upload._yt()
    tags = [t.lstrip("#") for t in re.findall(r"#[\wА-Яа-яЁё]+", v["description"])]
    tags = list(dict.fromkeys(tags + cfg.get("yt_extra_tags", [])))[:15]
    body = {
        "snippet": {"title": v["title"][:100], "description": v["description"][:4900], "tags": tags,
                    "categoryId": str(cfg.get("youtube_category_id", "22")),
                    "defaultLanguage": "ru", "defaultAudioLanguage": "ru"},
        "status": {"privacyStatus": cfg.get("youtube_privacy", "public"), "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(path), chunksize=8 * 1024 * 1024,
                                                        resumable=True, mimetype="video/mp4"))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtube.com/shorts/{resp['id']}"


def post(st, cfg, key):
    v = next_video(st)
    if not v:
        log("план закончился — все ролики выложены")
        return False
    path = ensure_file(v)
    link = upload(v, path, cfg)
    st["slots_done"] = (st["slots_done"] + [key])[-200:]
    st["posted"].append({"n": v["n"], "name": v["name"], "slot": key, "link": link})
    st["next"] = v["n"] + 1
    save_state(st)
    path.unlink(missing_ok=True)
    log(f"выложил №{v['n']} {v['name']} → {link}")
    nv = next_video(st)
    if nv:
        try:
            ensure_file(nv)
        except Exception as e:  # noqa: BLE001
            log(f"не скачал заранее {nv['name']}: {e}")
    return True


def tick():
    cfg = load(CFG, {})
    st = state()
    if not cfg.get("enabled", True) or st.get("paused"):
        return
    if not (BASE / "yt_token.json").exists():
        return
    v = next_video(st)
    if not v:
        return
    try:
        ensure_file(v)
    except Exception as e:  # noqa: BLE001
        log(f"ошибка скачивания {v['name']}: {e}")
        return
    key = due_slot(dt.datetime.now(MSK), st)
    if key:
        try:
            post(st, cfg, key)
        except Exception as e:  # noqa: BLE001
            log(f"ошибка выкладки {v['name']}: {e}")


def status():
    st = state()
    p = plan()
    print(f"Выложено: {len(st['posted'])} из {len(p)}" + ("   (на паузе)" if st.get("paused") else ""))
    for x in st["posted"][-5:]:
        print(f"  №{x['n']} {x['slot']} → {x['link']}")
    v = next_video(st)
    if v:
        now = dt.datetime.now(MSK)
        nxt = None
        for d in range(0, 3):
            for s in SLOTS:
                h, m = map(int, s.split(":"))
                t = (now + dt.timedelta(days=d)).replace(hour=h, minute=m, second=0, microsecond=0)
                if t + LATE_OK > now and f"{t:%Y-%m-%d} {s}" not in st["slots_done"]:
                    nxt = t
                    break
            if nxt:
                break
        print(f"Дальше: №{v['n']} {v['name']} — {nxt:%d.%m %H:%M} МСК" if nxt else f"Дальше: №{v['n']}")
        print(f"  {v['title']}")
    else:
        print("Все ролики плана выложены.")
    if not (BASE / "yt_token.json").exists():
        print("⚠️ Нет входа в YouTube: запусти  quotes login")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    lock = open(BASE / ".lock", "w")
    if cmd in ("tick", "now"):
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.exit(0)
    if cmd == "tick":
        tick()
    elif cmd == "now":
        st = state()
        post(st, load(CFG, {}), f"{dt.datetime.now(MSK):%Y-%m-%d %H:%M} вручную")
    elif cmd in ("pause", "resume"):
        st = state()
        st["paused"] = cmd == "pause"
        save_state(st)
        log("выкладка на паузе" if cmd == "pause" else "выкладка продолжена")
    else:
        status()

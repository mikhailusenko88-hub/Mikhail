#!/usr/bin/env python3
"""Ежедневный запуск: сценарий -> ролик -> VK (и, если включено, YouTube).

  python3 run_daily.py          — собрать и выложить
  python3 run_daily.py --test   — только собрать ролик в out/, ничего не выкладывать
  python3 run_daily.py --count 5 — выложить сразу 5 роликов (для старта сообщества)
  python3 run_daily.py --manual --count 5 — собрать 5 новых роликов в out/ для ручной выкладки
"""
import datetime as dt
import fcntl
import json
import os
import sys
import time
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.chdir(BASE)


def load_env():
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


LOG = BASE / "bot.log"


def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def notify(text):
    """Сообщение в Telegram, если заданы TG_BOT_TOKEN и TG_CHAT_ID (необязательно)."""
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not (tok and chat):
        return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      data={"chat_id": chat, "text": text, "disable_web_page_preview": 1}, timeout=20)
    except Exception as e:
        log(f"Telegram: {e}")


def tg_send_video(path, caption):
    """Если настроен Telegram — присылает готовый ролик туда (удобно выкладывать с телефона)."""
    tok, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not (tok and chat):
        return
    try:
        import requests
        with open(path, "rb") as f:
            requests.post(f"https://api.telegram.org/bot{tok}/sendVideo",
                          data={"chat_id": chat, "caption": caption[:1000], "supports_streaming": 1},
                          files={"video": f}, timeout=300)
    except Exception as e:
        log(f"Telegram видео: {e}")


def main():
    load_env()
    test = "--test" in sys.argv
    import make_video as mv
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    state_f = BASE / "state.json"
    state = json.loads(state_f.read_text(encoding="utf-8")) if state_f.exists() else \
        {"used_titles": [], "n_done": 0, "history": []}

    out_dir = BASE / "out"
    out_dir.mkdir(exist_ok=True)
    skip = list(state["used_titles"]) + state.get("failed_titles", [])
    for attempt in range(3):  # если ролик не собрать — берём следующий сценарий
        script, source = mv.get_script(cfg, skip, state["n_done"], log)
        log(f"Сценарий ({source}): [{script.get('format')}] {script['title']}")
        out = out_dir / f"{dt.datetime.now():%Y-%m-%d_%H%M%S}.mp4"
        t0 = time.time()
        try:
            dur = mv.build(script, cfg, out, BASE / "work", log=log)
            break
        except Exception as e:
            log(f"Не собрался ({e}), пробую другой сценарий")
            skip.append(script["title"])
            state.setdefault("failed_titles", []).append(script["title"])
            state_f.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        raise RuntimeError("3 сценария подряд не собрались")
    log(f"Ролик готов: {out.name}, {dur:.0f} сек, сборка {time.time() - t0:.0f} сек")
    if test:
        log("Тестовый режим: ничего не выкладываю")
        return 0
    if "--manual" in sys.argv or not cfg.get("post_to_vk"):
        # ручная выкладка: ролик + подпись рядом, тема считается использованной
        desc = mv.caption(script, cfg)
        out.with_suffix(".txt").write_text(desc, encoding="utf-8")
        state["used_titles"].append(script["title"])
        state["n_done"] += 1
        state["history"].append({"date": f"{dt.date.today()}", "title": script["title"], "links": ["вручную"]})
        state_f.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"Для ручной выкладки: {out.name} + подпись {out.with_suffix('.txt').name}")
        link = None
        if cfg.get("web_page", True):
            try:
                import web_page
                link, page = web_page.publish(out, desc, script["title"], f"{dt.date.today():%d.%m.%Y}", cfg)
                log(f"На странице: {link}")
            except Exception as e:
                log(f"Страница: ошибка {e}")
        # YouTube выкладывается автоматически, если включён и вход сделан (yt_upload.py --setup)
        if cfg.get("post_to_youtube") and (BASE / "yt_token.json").exists() and "--no-youtube" not in sys.argv:
            try:
                import yt_upload
                tags = script.get("tags", []) + cfg.get("default_tags", [])
                yt_title = script["title"] + (" | " + script["title_ru"] if script.get("title_ru") else "")
                yt_link = yt_upload.upload(out, yt_title, desc, tags, cfg)
                log(f"YouTube: {yt_link}")
                state["history"][-1]["links"].append("YouTube: " + yt_link)
                state_f.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            except Exception as e:
                log(f"YouTube: ошибка {e}")
            # плюс 1 ролик из очереди yt_queue/ (если там что-то есть)
            try:
                import yt_queue
                if yt_queue.pending():
                    yt_queue.upload_next(cfg, 1)
            except Exception as e:
                log(f"Очередь YouTube: ошибка {e}")
        # чистим старые ролики
        keep = cfg.get("keep_days", 7)
        for f in list(out_dir.glob("*.mp4")) + list(out_dir.glob("*.txt")):
            if time.time() - f.stat().st_mtime > keep * 86400:
                f.unlink()
        return 0

    desc = mv.caption(script, cfg)
    links = []
    if cfg.get("post_to_vk"):
        try:
            import vk_upload
            url, kind = vk_upload.upload(str(out), script["title"], desc, cfg, log)
            links.append(f"VK ({kind}): {url}")
        except Exception as e:
            log(f"VK: ошибка {e}")
    if cfg.get("post_to_youtube"):
        try:
            import yt_upload
            tags = script.get("tags", []) + cfg.get("default_tags", [])
            links.append("YouTube: " + yt_upload.upload(out, script["title"], desc, tags, cfg))
        except Exception as e:
            log(f"YouTube: ошибка {e}")

    if not links:
        notify(f"Ролик «{script['title']}» собран, но не выложен. Смотри bot.log")
        return 1

    for l in links:
        log("Выложено — " + l)
    state["used_titles"].append(script["title"])
    state["n_done"] += 1
    state["history"].append({"date": f"{dt.date.today()}", "title": script["title"], "links": links})
    state["history"] = state["history"][-200:]
    state_f.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    notify(f"Вышел ролик «{script['title']}»\n" + "\n".join(links))

    # чистим старые ролики
    keep = cfg.get("keep_days", 7)
    for f in out_dir.glob("*.mp4"):
        if time.time() - f.stat().st_mtime > keep * 86400:
            f.unlink()
    return 0


def count_arg():
    if "--count" in sys.argv:
        try:
            return max(1, min(10, int(sys.argv[sys.argv.index("--count") + 1])))
        except (IndexError, ValueError):
            pass
    return 1


if __name__ == "__main__":
    try:
        load_env()
        lock = open(BASE / ".lock", "w")  # одна блокировка на весь запуск (и на --count)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("Уже идёт другой запуск, выхожу")
            sys.exit(0)
        n = count_arg()
        code = 0
        for k in range(n):
            if n > 1:
                log(f"=== Ролик {k + 1} из {n} ===")
            code = main() or code
            if n > 1 and k < n - 1:
                time.sleep(5 if "--manual" in sys.argv else 90)  # пауза между выкладками
        sys.exit(code)
    except Exception:
        log("Сбой:\n" + traceback.format_exc())
        notify("Бот роликов: сбой, смотри bot.log")
        sys.exit(1)

"""Очередь готовых роликов для YouTube.

Положи пары «ролик.mp4 + ролик.txt (подпись)» в папку yt_queue/ рядом с ботом.
  .venv/bin/python yt_queue.py --count 4   — выложить сейчас 4 ролика из очереди
Ежедневный запуск (run_daily.py) сам выкладывает по 1 ролику из очереди в день.
Выложенные переносятся в yt_queue/done/.
"""
import datetime as dt
import json
import re
import shutil
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
QUEUE = BASE / "yt_queue"


def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(BASE / "bot.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def pending():
    if not QUEUE.exists():
        return []
    return sorted(QUEUE.glob("*.mp4"))


def upload_next(cfg, n=1):
    import yt_upload
    done_dir = QUEUE / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    links = []
    for mp4 in pending()[:n]:
        txt = mp4.with_name(mp4.stem + " (подпись).txt")
        if not txt.exists():
            txt = mp4.with_suffix(".txt")
        caption = txt.read_text(encoding="utf-8").strip() if txt.exists() else mp4.stem
        title = caption.splitlines()[0].strip() or mp4.stem
        title = re.sub(r"^\d+\s*-\s*", "", title)
        tags = [t.lstrip("#") for t in re.findall(r"#[\wА-Яа-яЁё]+", caption)]
        try:
            link = yt_upload.upload(mp4, title, caption, tags, cfg)
        except Exception as e:
            log(f"Очередь YouTube: ошибка на «{title}»: {e}")
            break
        log(f"Очередь YouTube: «{title}» → {link}")
        links.append(link)
        shutil.move(str(mp4), done_dir / mp4.name)
        if txt.exists():
            shutil.move(str(txt), done_dir / txt.name)
        time.sleep(10)
    return links


if __name__ == "__main__":
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    n = 1
    if "--count" in sys.argv:
        n = int(sys.argv[sys.argv.index("--count") + 1])
    print(f"В очереди: {len(pending())}")
    upload_next(cfg, n)
    print(f"Осталось в очереди: {len(pending())}")

#!/usr/bin/env python3
"""Озвучщик «Альбина» для бота «Почему так?»: живёт рядом с server.py службы multik-tts
(/opt/multik-tts), берёт оттуда тот же голос, ударения (ruaccent) и «мягкий тон».

Запускается ботом на время одного ролика (albina.py), общается строками JSON:
  -> {"text", "speaker", "soft", "rate", "pitch", "out": "/путь/фраза.wav"}
  <- {"ok": true, "marked": "текст с ударениями", "s": секунды}
Первая строка ответа после загрузки: {"ready": true, "load_s", "rss_mb"}.
"""
import json
import os
import re
import resource
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)

# весь «шум» (print из server.py, предупреждения torch) — в stderr, в stdout только ответы
proto = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
os.dup2(2, 1)


def rss():
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)


def answer(d):
    proto.write(json.dumps(d, ensure_ascii=False) + "\n")
    proto.flush()


t0 = time.time()
try:
    import server
    server.CACHE = os.path.join(D, "cache-bot")      # свой кэш, не мешает службе
    server.CACHE_MB = 150
    os.makedirs(server.CACHE, exist_ok=True)
    server.load()
except Exception as e:  # noqa
    answer({"ready": False, "error": str(e)})
    sys.exit(1)
if not server.state.get("ready"):
    answer({"ready": False, "error": server.state.get("error") or "не загрузился"})
    sys.exit(1)
answer({"ready": True, "load_s": round(time.time() - t0, 1), "rss_mb": rss()})

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        q = json.loads(line)
    except Exception:
        continue
    if q.get("cmd") == "quit":
        break
    try:
        t = time.time()
        text = re.sub(r"\s+", " ", str(q.get("text") or "")).strip()
        style = str(q.get("style", "bot")) if hasattr(server, "bot_marks") else ""
        qp = q.get("qpitch")
        if qp is not None and hasattr(server, "BOT_Q_PITCH"):   # пробы разного подъёма в вопросе
            server.BOT_Q_PITCH = qp
        server.CACHE = os.path.join(D, "cache-bot" + ("-q" + (qp or "none") if qp is not None else ""))
        os.makedirs(server.CACHE, exist_ok=True)
        args = (text, q.get("speaker", "ru_albina"), bool(q.get("soft", True)), q.get("rate", "medium"), q.get("pitch", "medium"))
        wav = server.make(*args, style=style) if style else server.make(*args)
        tmp = q["out"] + ".tmp"
        with open(tmp, "wb") as f:
            f.write(wav)
        os.replace(tmp, q["out"])
        try:
            marked = server.marked_for(text, style) if hasattr(server, "marked_for") else server.mark(text[:server.MAX_TEXT])
        except Exception:
            marked = ""
        answer({"ok": True, "s": round(time.time() - t, 2), "marked": marked, "rss_mb": rss()})
    except Exception as e:
        answer({"ok": False, "error": str(e)[:300]})

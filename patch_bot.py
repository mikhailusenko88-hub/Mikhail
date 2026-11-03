#!/usr/bin/env python3
"""Подключает albina.py к make_video.py бота (две вставки, повторный запуск ничего не ломает).
  python3 patch_bot.py /путь/к/make_video.py
Код возврата: 0 — подключено (или уже было), 2 — не нашёл, куда вставить (файл не тронут)."""
import re
import sys
from pathlib import Path

MARK = "# --- голос «Альбина»"
HEAD = '''# --- голос «Альбина» (Silero, MIT): albina.py рядом; если что-то не так — прежний голос ---
try:
    import albina as _albina
    speak = _albina.wrap(speak)
except Exception as _e:  # без Альбины бот работает как раньше
    print("Альбина не подключилась:", _e)


'''
TAIL = '''

# --- голос «Альбина»: сбой посреди ролика — весь ролик прежним голосом; память — сразу после ролика ---
try:
    build = _albina.wrap_build(build)
except Exception:
    pass
'''


def main(path):
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if MARK in s:
        print("   код: Альбина уже подключена")
        return 0
    if len(re.findall(r"^def build\(", s, re.M)) != 1 or not re.search(r"^def speak\(", s, re.M):
        print("   ! код: не нашёл def speak(...) и def build(...) — make_video.py не тронут")
        return 2
    if s.index("def speak(") > s.index("def build("):
        print("   ! код: speak объявлен после build — make_video.py не тронут")
        return 2
    s = re.sub(r"^def build\(", lambda m: HEAD + "def build(", s, count=1, flags=re.M)
    s = s.rstrip("\n") + "\n" + TAIL
    p.write_text(s, encoding="utf-8")
    print("   код: Альбина подключена к make_video.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

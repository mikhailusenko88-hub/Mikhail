"""Какие файлы из in/ ещё не разобраны (или все, если в request.txt есть слово force)."""
import glob
import os

force = os.path.exists("request.txt") and "force" in open("request.txt").read()
for p in sorted(glob.glob("in/*")):
    if os.path.splitext(p)[1].lower() not in (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".opus", ".webm", ".mp4"):
        continue
    name = os.path.splitext(os.path.basename(p))[0]
    if force or not os.path.exists(f"out/{name}.md"):
        print(p)

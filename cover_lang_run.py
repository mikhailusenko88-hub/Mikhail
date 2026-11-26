#!/usr/bin/env python3
"""Обложки серии на языках по запросу cover-request.txt (workflow cover-lang).
Первая строка без «#»: «<сборка> <номер серии> <скрипт или план в covers/<номер>/>», дальше по строке на язык: «язык;СЕРИЯ N;ВОПРОС НА СВИТКЕ».
Рядом (папка w/): afisha.py, compose.py, covers/ из ветки studio, el/ — элементы сборки. Итог — out_cover/<сборка>/cover_<язык>.jpg."""
import os, subprocess, sys, zipfile

lines = [l.strip() for l in open("cover-request.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
build, num, script = lines[0].split()[:3]
W = "w"
z = zipfile.ZipFile(f"{W}/elementy.zip")
for info in z.infolist():                     # имена с кириллицей в архиве записаны как cp437 — вернуть
    name = info.filename
    try:
        name = name.encode("cp437").decode("utf-8")
    except Exception:
        pass
    if name.endswith("/"):
        continue
    dst = os.path.join(W, name)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "wb").write(z.read(info))
print("элементов:", len(os.listdir(f"{W}/el")))
lz = f"{W}/covers/31/luzha.py"
if os.path.exists(lz):
    subprocess.run([sys.executable, lz, f"{W}/el"], check=False)
# свои элементы обложки серии, которых нет в elementy.zip (план ссылается на них): скрипт из covers/<N>/ и его аргументы (пути от папки w/)
OWN = {"29": [["dub.py", "el/f4_meadow_day.jpg", "el/v_dub.png"], ["strelka.py", "el/v_strelka.png"]]}
for sc, *args in OWN.get(num, []):
    r = subprocess.run([sys.executable, f"covers/{num}/{sc}", *args], cwd=W, capture_output=True, text=True)
    print("элемент", sc, "ok" if r.returncode == 0 else "ОШИБКА " + r.stderr[-500:])
out = os.path.abspath(f"out_cover/{build}"); os.makedirs(out, exist_ok=True)
bad = 0
for l in lines[1:]:
    lang, series, text = [x.strip() for x in l.split(";", 2)]
    dst = f"{out}/cover_{lang}.jpg"
    src = f"covers/{num}/{script}"
    args = [sys.executable, "oblozhka_lang.py", src, dst, series, text, lang] + ([] if src.endswith(".json") else ["el", dst])
    r = subprocess.run(args, cwd=W, capture_output=True, text=True)
    print(lang, "→", dst, "ok" if r.returncode == 0 and os.path.exists(dst) else "ОШИБКА", r.stdout[-300:], r.stderr[-1500:])
    bad += r.returncode != 0
sys.exit(1 if bad else 0)

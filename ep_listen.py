#!/usr/bin/env python3
# «Послушать» готовую серию мультика: скачать звук с Rutube, разбить на фразы, найти слова с ударением не там и смазанные слова.
#   python ep_listen.py r1      — самая новая серия на Rutube (r2 — предыдущая …)
#   python ep_listen.py e17     — серия № 17
# Результат: ep/<имя>/report.md, words.json, фразы с ошибками — картинки (спектр + высота голоса).
import json, os, re, subprocess, sys, urllib.request, shutil, traceback
arg = sys.argv[1]
RT = os.environ.get("RUTUBE", "82826859")
def get(u, t=60):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t).read()
def ep_num(t):
    t = (t or "").lower(); m = re.search(r"сери[яию]\s*№?\s*(\d+)", t) or re.search(r"(\d+)\s*[-–]?\s*(?:я\s+)?сери", t)
    return int(m.group(1)) if m else None
rts = []
for page in range(1, 9):
    try:
        j = json.loads(get(f"https://rutube.ru/api/video/person/{RT}/?page={page}")); rts += j.get("results") or []
        if not j.get("has_next"): break
    except Exception as ex:
        print("rutube api", ex); break
eps = {}
for v in rts:
    n = ep_num(v.get("title")); print("rt:", n, v.get("duration"), v.get("title"), flush=True)
    if n and (v.get("duration") or 0) > 100 and n not in eps: eps[n] = v
order = sorted(eps, reverse=True)
if arg[0] == "r":
    k = int(arg[1:]) - 1
    if k >= len(order): print("нет такой серии"); sys.exit(0)
    n = order[k]
else:
    n = int(arg[1:])
    if n not in eps: print("серии нет на Rutube:", n, "есть:", order); sys.exit(0)
v = eps[n]; name = f"ep{n:02d}"; D = f"ep/{name}"; os.makedirs(D, exist_ok=True)
print("серия", n, v.get("title"), v.get("video_url"), flush=True)
mp4 = "/tmp/ep.mp4"
for fmt in ["wv*+wa/w", "b"]:
    r = subprocess.run(["yt-dlp", "-q", "-f", fmt, "-o", mp4, "--force-overwrites", v.get("video_url")], capture_output=True, text=True, timeout=1800)
    if os.path.exists(mp4): break
    print("yt-dlp", r.stderr[-500:])
if not os.path.exists(mp4): print("не скачалась"); sys.exit(1)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", "/tmp/a16.wav"], check=True)
from faster_whisper import WhisperModel
m = WhisperModel(os.environ.get("FW", "medium"), device="cpu", compute_type="int8")
segs, _ = m.transcribe("/tmp/a16.wav", language="ru", beam_size=5, word_timestamps=True, vad_filter=True, condition_on_previous_text=False)
words = []
for s in segs:
    if s.no_speech_prob > 0.6 or s.avg_logprob < -1.0: continue
    for w in (s.words or []): words.append((w.start, w.end, w.word.strip(), w.probability))
print("слов распознано:", len(words), flush=True)
# фразы: по знаку конца предложения, паузе > 0.5 с или длине > 11 с
phr, cur = [], []
for i, w in enumerate(words):
    cur.append(w)
    gap = words[i + 1][0] - w[1] if i + 1 < len(words) else 9
    if re.search(r"[.!?…]$", w[2]) or gap > 0.5 or w[1] - cur[0][0] > 11:
        phr.append(cur); cur = []
if cur: phr.append(cur)
import voice_check as vc
os.makedirs("in", exist_ok=True)
rows, bad_words = [], []
VOW = "аеёиоуыэюя"
for i, p in enumerate(phr):
    text = " ".join(w[2] for w in p).strip()
    if not re.search(r"[а-яё]{2,}", text.lower()): continue
    if not any(sum(c in VOW for c in t.lower()) > 1 for t in re.findall(r"[А-Яа-яЁё]+", text)): continue
    t0, t1 = max(0, p[0][0] - 0.15), p[-1][1] + 0.25
    nm = f"{name}_{i:03d}"; wav, txt = f"in/{nm}.wav", f"in/{nm}.txt"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.2f}", "-t", f"{t1 - t0:.2f}", "-i", "/tmp/a16.wav", wav], check=True)
    open(txt, "w", encoding="utf-8").write(text)
    try:
        rep = vc.analyze(nm, wav, txt)
    except Exception:
        print("FAIL", nm, traceback.format_exc()[-400:], flush=True); continue
    flags = []
    for w in rep.get("words", []):
        e, d = w.get("exp"), w.get("det")
        if e is None or d is None or e == d: continue
        mg = w.get("margin") or 0
        if mg >= 0.5:
            lvl = "ОШИБКА" if mg >= 1.0 else "возможно"
            flags.append({"w": w["w"], "need": vc.mark(w["w"], e), "got": vc.mark(w["w"], d), "lvl": lvl, "margin": round(mg, 2)})
            bad_words.append({"t": round(t0, 1), "w": w["w"], "need": vc.mark(w["w"], e), "got": vc.mark(w["w"], d), "lvl": lvl, "f0": rep.get("f0_median_hz"), "phrase": text})
    rows.append({"i": i, "t0": round(t0, 2), "t1": round(t1, 2), "text": text, "heard": rep.get("heard"), "match": rep.get("match"), "diff": rep.get("diff"), "utmos": rep.get("utmos"),
                 "f0": rep.get("f0_median_hz"), "range": rep.get("f0_range"), "rate": rep.get("rate"), "flags": flags, "minp": round(min(w[3] for w in p), 2)})
    if any(f["lvl"] == "ОШИБКА" for f in flags) and os.path.exists(f"out/{nm}.png"): shutil.copy(f"out/{nm}.png", f"{D}/{nm}.png")
    print(nm, f"{t0:6.1f}", text[:70], "|", "; ".join(f"{f['need']}→{f['got']} {f['lvl']}" for f in flags), flush=True)
mmss = lambda t: f"{int(t // 60)}:{int(t % 60):02d}"
L = [f"# Серия {n}: {v.get('title')}", "", f"Фраз проверено: {len(rows)} · слов с ударением не там: {sum(1 for b in bad_words if b['lvl'] == 'ОШИБКА')} (+{sum(1 for b in bad_words if b['lvl'] != 'ОШИБКА')} возможных)", "",
     "| время | высота, Гц | слово: нужно → звучит | уверенность | фраза |", "|---|---|---|---|---|"]
for b in bad_words: L.append(f"| {mmss(b['t'])} | {b['f0']} | {b['need']} → {b['got']} | {b['lvl']} | {b['phrase'][:90]} |")
L += ["", "## Слова, которые распознаватель услышал неуверенно (возможно смазаны)", ""]
for r in rows:
    if r["minp"] < 0.35: L.append(f"- {mmss(r['t0'])} ({r['f0']} Гц) «{r['text'][:110]}» — уверенность {r['minp']}")
L += ["", "## Все фразы", "", "| время | Гц | диапазон | темп | UTMOS | текст |", "|---|---|---|---|---|---|"]
for r in rows: L.append(f"| {mmss(r['t0'])} | {r['f0']} | {r['range']} | {r['rate']} | {r['utmos']} | {r['text'][:120]} |")
open(f"{D}/report.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
json.dump({"num": n, "title": v.get("title"), "rows": rows, "bad": bad_words}, open(f"{D}/words.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print("готово", name)

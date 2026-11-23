#!/usr/bin/env python3
"""Свой голос, круг 3 (23.11.2026): качество. Смеси внутри Silero дали прибавку маленькую (UTMOS 3,61 → 3,70).
Пробуем модель поколением новее — Chatterbox Multilingual (Resemble AI, лицензия MIT, русский есть): она говорит
голосом по образцу. Образец — наш же сборный голос «Новый 2» (r13, из MIT-модели), так что голос остаётся своим.

  python svoy_cb.py ref        (обычная среда) r13 читает все фразы → pack/R__r13__NN.flac, образец pack/ref.wav
  python svoy_cb.py cb         (среда chatterbox) фразы голосом по образцу, два режима → in/ для voice_check
  python svoy_cb.py final      итог cast3/itog.md, cast3/proba3.mp4
"""
import glob, json, os, shutil, subprocess, sys

MODES = {"cb1": dict(exaggeration=0.5, cfg_weight=0.5), "cb2": dict(exaggeration=0.65, cfg_weight=0.3)}
REF_PHR = [1, 3, 4, 9]          # образец — из фраз, которых нет в ролике


def log(*a):
    print(*a, flush=True)


def ref():
    import svoy2
    os.makedirs("pack", exist_ok=True)
    shutil.rmtree("in", ignore_errors=True); os.makedirs("in")
    w = json.load(open("cast2/krug2.json", encoding="utf-8"))["light"]["r13"]["w"]
    svoy2.prep_marks()
    net = svoy2.Net(svoy2.CIS)
    rows = net.build(w)
    for k, (t, _) in enumerate(svoy2.PHRASES):
        p = f"in/R__r13__{k:02d}.wav"
        net.say(rows, t, p)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, f"pack/R__r13__{k:02d}.flac"], check=True)
    seq = []
    for k in REF_PHR:
        seq += ["-i", f"in/R__r13__{k:02d}.wav"]
    fc = "".join(f"[{j}:a]" for j in range(len(REF_PHR))) + f"concat=n={len(REF_PHR)}:v=0:a=1[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *seq, "-filter_complex", fc, "-map", "[o]", "-ar", "24000", "-ac", "1",
                    "pack/ref.wav"], check=True)
    json.dump([t for t, _ in svoy2.PHRASES], open("pack/phrases.json", "w", encoding="utf-8"), ensure_ascii=False)
    log("образец:", subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     "pack/ref.wav"], capture_output=True, text=True).stdout.strip(), "с")


def cb():
    import time, torch, torchaudio as ta
    _orig = torch.load

    def _load(*a, **k):
        k.setdefault("map_location", "cpu")
        return _orig(*a, **k)
    torch.load = _load
    torch.set_num_threads(os.cpu_count() or 4)
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    P = json.load(open("pack/phrases.json", encoding="utf-8"))
    shutil.rmtree("in", ignore_errors=True); os.makedirs("in")
    for mode, kw in MODES.items():
        for k, t in enumerate(P):
            t0 = time.time()
            torch.manual_seed(1000 + k)
            try:
                wav = m.generate(t, language_id="ru", audio_prompt_path="pack/ref.wav", **kw)
            except TypeError:
                wav = m.generate(t, language_id="ru", audio_prompt_path="pack/ref.wav")
            name = f"C__{mode}__{k:02d}"
            ta.save(f"in/{name}.wav", wav, m.sr)
            open(f"in/{name}.txt", "w", encoding="utf-8").write(t + "\n")
            open(f"in/{name}.voice", "w", encoding="utf-8").write(f"chatterbox:{mode}:ref=r13\n")
            log(name, f"{time.time() - t0:.1f} с")


def final():
    import svoy, svoy2
    os.makedirs("cast3", exist_ok=True)
    R = svoy.load_reps()
    K2 = json.load(open("cast2/krug2.json", encoding="utf-8"))
    base = next((f for f in K2["finalists"] if f["id"] == "r13"), None)
    rows = [("Новый 2 — как в прошлой пробе", "R__r13", base.get("full") if base else {})]
    names = {"cb1": "Модель новее — спокойно", "cb2": "Модель новее — живее"}
    for mode in MODES:
        reps = R.get(f"C__{mode}")
        rows.append((names[mode], f"C__{mode}", svoy.agg(reps) if reps else {}))
    L = ["# Свой голос, круг 3 — модель новее (Chatterbox Multilingual, MIT) по образцу нашего голоса", "",
         "| | голос | слова | UTMOS | ошибки удар. | интонация | диапазон | Гц | темп | оценка |", "|---|---|---|---|---|---|---|---|---|---|"]
    for i, (t, _, a) in enumerate(rows, 1):
        a = a or {}
        L.append(f"| {i} | {t} | {a.get('match') or 0:.3f} | {a.get('utmos') or 0:.2f} | {a.get('err') or 0:.2f} | "
                 f"{a.get('inton') or 0:.2f} | {a.get('range') or 0:.1f} | {a.get('f0') or 0:.0f} | {a.get('rate') or 0:.1f} | "
                 f"{svoy.score(a) if a else '—'} |")
    bad = []
    for j in sorted(glob.glob("pack/C__*__*.json")):
        r = json.load(open(j, encoding="utf-8"))
        if r.get("diff") or r.get("stress_errors"):
            bad.append(f"- {r['name']}: «{r['text']}» → «{r.get('heard', '')}»; ошибок ударений {r.get('stress_errors', 0)}")
    L += ["", "## Где распознаватель услышал не то или ударение не там", ""] + bad
    open("cast3/itog.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    log("\n".join(L))
    pick = []
    for t, tag, a in rows:
        a = a or {}
        pick.append((t, tag, f"естественность {a['utmos']:.2f}" if a.get("utmos") else " "))
    svoy2.video(pick, "cast3/proba3.mp4", svoy2.PHRASES)


if __name__ == "__main__":
    {"ref": ref, "cb": cb, "final": final}[sys.argv[1]]()

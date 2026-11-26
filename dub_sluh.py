# Слух дубляжа «для носителя» (26.11.2026, просьба Михаила: «чтобы им приятно было слышать»).
#   python dub_sluh.py <сборка> <язык> [сколько реплик]
# Для каждой реплики готового дубляжа (настройки — из out_dub/<сборка>/report_<язык>.json: текст, герой, скорость голоса)
# заново проходит путь: родной голос-источник → перекраска в голос героя → итог (высота как у героя) и меряет на каждом шаге:
#   естественность UTMOS (1–5, живой диктор ≈ 4–4,5), разборчивость точным распознавателем (faster-whisper large-v3-turbo),
#   мелодию конца вопросов (подъём/спад в полутонах), живость (размах высоты), темп.
# Так видно, где звучание портит перекраска, где — ускорение, а где сам текст.
# Итог: out_sluh/<сборка>/<язык>.md и .json, пары «источник → итог» худших реплик: out_sluh/<сборка>/pairs_<язык>.mp3.
import json, os, re, sys, time, traceback, zipfile

import numpy as np

import dubcore as D

NAME, LANG = sys.argv[1], sys.argv[2]
LIM = int(sys.argv[3]) if len(sys.argv) > 3 else 0
SRM = 44100
G = json.load(open("geroi.json", encoding="utf-8"))
OUT = os.path.join("out_sluh", NAME)
os.makedirs(os.path.join(OUT, "tmp"), exist_ok=True)
REP = json.load(open(f"out_dub/{NAME}/report_{LANG}.json", encoding="utf-8"))
WH = {"en": r"^(what|where|who|whom|whose|why|how|when|which)\b", "de": r"^(was|wo|wer|wen|wem|wessen|warum|wieso|weshalb|wie|wann|welche[rsmn]?|woher|wohin)\b",
      "es": r"^(¿)?(qué|dónde|quién|quiénes|por qué|cómo|cuándo|cuál|adónde)\b", "pt": r"^(o que|que|onde|quem|por que|porque|como|quando|qual)\b",
      "fr": r"^(qu[e']|quoi|où|qui|pourquoi|comment|quand|quel)", "hi": r"$^", "ar": r"$^"}

_mos = {}


def utmos(arr):
    import torch
    if "m" not in _mos:
        _mos["m"] = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
    a = D.resample(np.asarray(arr, dtype=np.float32), D.SR, 16000)
    with torch.no_grad():
        return round(float(_mos["m"](torch.from_numpy(a)[None], 16000)), 2)


def pitch(arr):
    import parselmouth
    s = parselmouth.Sound(np.asarray(arr, dtype=np.float64), D.SR)
    p = s.to_pitch(time_step=0.01, pitch_floor=70, pitch_ceiling=700)
    f = p.selected_array["frequency"]
    t = p.xs()
    v = f > 0
    if v.sum() < 8:
        return None
    st = 12 * np.log2(f[v] / np.median(f[v]))
    tv = t[v]
    # конец фразы: последние 30 % озвученного времени — разница «конец − середина конца» в полутонах
    k = max(4, int(len(st) * 0.3))
    tail = st[-k:]
    rise = float(np.median(tail[-max(2, k // 3):]) - np.median(tail[:max(2, k // 3)]))
    return {"range": round(float(np.percentile(st, 90) - np.percentile(st, 10)), 1), "end": round(rise, 1),
            "dur": round(float(tv[-1] - tv[0]), 2)}


def kind(text):
    t = text.strip()
    if not t.endswith("?") and not t.endswith("?!") and not t.endswith("? !") and not t.endswith(" ?"):
        return "утв"
    last = re.split(r"(?<=[.!?])\s+", t)[-1].lower().strip("¿¡ ")
    return "вопр-слово" if re.search(WH.get(LANG, r"$^"), last) else "вопр-да/нет"


def main():
    t0 = time.time()
    src_dir = os.path.join("tmp_dubsrc", NAME)
    if not os.path.isdir(os.path.join(src_dir, "dub")):
        zipfile.ZipFile(os.path.join(src_dir, "dub.zip")).extractall(src_dir)
    dd = os.path.join(src_dir, "dub")
    L = json.load(open(os.path.join(dd, "lines.json"), encoding="utf-8"))
    byi = {ln["i"]: ln for ln in L["lines"]}
    # образцы героев — как в dub.py (их же реплики из серии, ~12 с)
    refs, f0s = {}, {}
    for name in sorted({ln["name"] for ln in L["lines"] if not ln["vocal"]}):
        mine = sorted([ln for ln in L["lines"] if ln["name"] == name and not ln["vocal"]], key=lambda x: -x["bdur"])
        pieces, tot = [], 0.0
        for ln in mine:
            if tot > 12:
                break
            a = D.trim(D.resample(D.load(os.path.join(dd, "lines", f"{ln['i']:03d}.wav"), SRM), SRM, D.SR))
            pieces += [a, D.silence(0.3)]
            tot += len(a) / D.SR
        p = os.path.join(OUT, "tmp", f"ref_{name}.wav")
        D.save(np.concatenate(pieces), p)
        refs[name] = p
        f0s[name] = G.get("f0", {}).get(name) or D.measure(np.concatenate(pieces))["f0"]
    rows = [r for r in REP["rows"] if r.get("text") and r.get("name") in refs]
    if LIM:
        rows = rows[:LIM]
    wsize = G.get("whisper_lang", {}).get(LANG, "fw:large-v3-turbo") if LANG in ("hi", "ar") else "fw:large-v3-turbo"
    res, keep = [], {}
    for n, r in enumerate(rows):
        i, name, text = r["i"], r["name"], r["text"]
        hero = G["heroes"].get(name, {})
        spec = dict((hero.get("src") or {}).get(LANG) or G["src"][LANG])
        spec["speed"] = r.get("speed") or spec.get("speed", 1.0)
        pre = (hero.get("pre") or {}).get(LANG) or hero.get("pre_all")
        row = {"i": i, "name": name, "text": text, "ru": byi.get(i, {}).get("text"), "speed": spec["speed"], "kind": kind(text),
               "clear_dub": r.get("clear")}
        try:
            s = D.source(text, spec)
            if pre:
                s = D.change(s, f0=pre.get("f0", 0), F=pre.get("F", 1.0), rng=pre.get("range", 1.0))
            s = D.trim(s)
            raw = D.trim(D.vc(s, refs[name]))
            out, shift = D.match_pitch(raw, f0s[name], 1.5)
            out = D.trim(out)
            row["mos"] = {"src": utmos(s), "vc": utmos(raw), "out": utmos(out)}
            row["pitch"] = {"src": pitch(s), "out": pitch(out)}
            heard = D.heard(out, LANG, wsize)
            row["heard"] = heard
            row["clear"] = D.char_pct(text, heard) if LANG in G.get("by_chars", []) else D.clear_pct(text, heard)[0]
            row["sps"] = round(sum(len(re.findall("[aeiouyäöüéèêàâîôûœæ]+", w.lower())) for w in text.split()) / max(0.3, len(out) / D.SR), 1)
            keep[i] = (s, out)
        except Exception:
            row["error"] = traceback.format_exc()[-400:]
        res.append(row)
        D.log(f"{n + 1}/{len(rows)}", i, name, row.get("mos"), row.get("kind"), (row.get("pitch") or {}).get("out"))

    ok = [x for x in res if "mos" in x]
    def avg(k):
        return round(float(np.mean([x["mos"][k] for x in ok])), 2) if ok else None
    loss = sorted(ok, key=lambda x: x["mos"]["out"] - x["mos"]["src"])
    worst = sorted(ok, key=lambda x: x["mos"]["out"])[:10]
    qbad = [x for x in ok if x["kind"] == "вопр-да/нет" and x["pitch"]["out"] and x["pitch"]["out"]["end"] < 1.0]
    qlost = [x for x in qbad if x["pitch"]["src"] and x["pitch"]["src"]["end"] >= 1.5]
    flat = [x for x in ok if x["pitch"]["out"] and x["pitch"]["out"]["range"] < 3.0 and len(x["text"].split()) >= 4]
    fast = [x for x in ok if (x["speed"] or 1) > 1.15]
    S = {"build": NAME, "lang": LANG, "n": len(ok), "mos_src": avg("src"), "mos_vc": avg("vc"), "mos_out": avg("out"),
         "by_hero": {h: round(float(np.mean([x["mos"]["out"] for x in ok if x["name"] == h])), 2) for h in sorted({x["name"] for x in ok})},
         "by_hero_src": {h: round(float(np.mean([x["mos"]["src"] for x in ok if x["name"] == h])), 2) for h in sorted({x["name"] for x in ok})},
         "clear": round(float(np.mean([x["clear"] for x in ok])), 1) if ok else None,
         "q_yesno": sum(1 for x in ok if x["kind"] == "вопр-да/нет"), "q_bad": [x["i"] for x in qbad], "q_lost_by_vc": [x["i"] for x in qlost],
         "flat": [x["i"] for x in flat], "fast": [x["i"] for x in fast], "minutes": round((time.time() - t0) / 60, 1)}
    json.dump({"summary": S, "rows": res}, open(os.path.join(OUT, f"{LANG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    M = [f"# Слух дубляжа {NAME} — {LANG}", "",
         f"Реплик {S['n']}. Естественность UTMOS (1–5; живой диктор ≈ 4–4,5): родной голос-источник **{S['mos_src']}** → после перекраски **{S['mos_vc']}** → итог **{S['mos_out']}**.",
         f"Разборчивость (large-v3-turbo): {S['clear']} %.", "",
         "По героям (итог / источник): " + ", ".join(f"{h} {S['by_hero'][h]} / {S['by_hero_src'][h]}" for h in S["by_hero"]), "",
         f"Вопросы «да/нет» ({S['q_yesno']}): без подъёма в конце {len(qbad)} — {S['q_bad']}; из них подъём был у источника и пропал после перекраски — {S['q_lost_by_vc']}.",
         f"Ровно, без мелодии (размах < 3 пт, фраза от 4 слов): {S['flat']}.", f"Ускорено больше ×1,15: {S['fast']}.", "",
         "## Больше всего теряет при перекраске", "| № | герой | текст | UTMOS источник → после перекраски → итог | слышно |", "|---|---|---|---|---|"]
    for x in loss[:12]:
        M.append(f"| {x['i']} | {x['name']} | {x['text']} | {x['mos']['src']} → {x['mos']['vc']} → {x['mos']['out']} | {x['heard']} |")
    M += ["", "## Худшие по итогу", "| № | герой | текст | итог UTMOS | скорость | мелодия конца (пт) | слышно |", "|---|---|---|---|---|---|---|"]
    for x in worst:
        M.append(f"| {x['i']} | {x['name']} | {x['text']} | {x['mos']['out']} | {x['speed']} | {(x['pitch']['out'] or {}).get('end')} | {x['heard']} |")
    M += ["", "## Все реплики", "| № | герой | вид | текст | UTMOS ист/пер/итог | конец ист→итог | размах | слог/с | понято |", "|---|---|---|---|---|---|---|---|---|"]
    for x in res:
        if "mos" not in x:
            M.append(f"| {x['i']} | {x['name']} | | {x['text']} | ОШИБКА | | | | |")
            continue
        ps, po = x["pitch"]["src"] or {}, x["pitch"]["out"] or {}
        M.append(f"| {x['i']} | {x['name']} | {x['kind']} | {x['text']} | {x['mos']['src']}/{x['mos']['vc']}/{x['mos']['out']} | {ps.get('end')}→{po.get('end')} | {po.get('range')} | {x['sps']} | {x['clear']} |")
    open(os.path.join(OUT, f"{LANG}.md"), "w", encoding="utf-8").write("\n".join(M) + "\n")

    # пары «источник → итог» для худших 8 (по потере при перекраске): слушать глазами и ушами
    pieces = []
    for x in loss[:8]:
        s, o = keep[x["i"]]
        pieces += [s * 0.9 / max(1e-4, np.abs(s).max()), D.silence(0.35), o * 0.9 / max(1e-4, np.abs(o).max()), D.silence(1.0)]
    if pieces:
        p = os.path.join(OUT, "tmp", "pairs.wav")
        D.save(np.concatenate(pieces), p)
        D.ff("-i", p, "-af", "loudnorm=I=-16:TP=-1.5", "-ar", "44100", "-codec:a", "libmp3lame", "-q:a", "4", os.path.join(OUT, f"pairs_{LANG}.mp3"))
    D.log("готово", S)


if __name__ == "__main__":
    main()

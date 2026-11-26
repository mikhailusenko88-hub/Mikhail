# Пробы улучшений звучания дубляжа «для носителя» (26.11.2026, по итогам dub_sluh.py):
#   q   — вопросы «да/нет» в английском звучат как утверждения (у 37i 8 из 8 без подъёма): подъём конца +3/+5 пт (Praat);
#   pik — Пик хуже всех (UTMOS 3,0 против 4,3 у Барсика): другие родные голоса-источники, с поднятием высоты и без;
#   pre — Филя и Рон теряют 0,2–0,4 на подгонке высоты после перекраски: поднимать высоту источника ДО перекраски.
#   python dub_sluh_lab.py <сборка> <язык> <q|pik|pre>
# Меряет: UTMOS итога, узнаваемость героя (ECAPA с образцом), разборчивость, мелодию конца. Пары «было → стало» — mp3.
import json, os, sys, time

import numpy as np
from parselmouth.praat import call

import dubcore as D
import dub_sluh as S

NAME, LANG, WHAT = sys.argv[1], sys.argv[2], sys.argv[3]
OUT = os.path.join("out_sluh", NAME)
os.makedirs(os.path.join(OUT, "tmp"), exist_ok=True)


def qrise(arr, st=4.0, tail=0.35):
    """Конец фразы: от высоты за tail секунд до конца — плавный подъём на st полутонов (выпуклый, к самому концу)."""
    s = D.snd(arr)
    man = call(s, "To Manipulation", 0.01, 75, 700)
    pt = call(man, "Extract pitch tier")
    n = int(call(pt, "Get number of points"))
    if n < 5:
        return arr
    tv = [(call(pt, "Get time from index", i), call(pt, "Get value at index", i)) for i in range(1, n + 1)]
    tend = tv[-1][0]
    t0 = tend - tail
    before = [v for t, v in tv if t < t0]
    base = float(np.median(before[-5:])) if before else tv[0][1]
    call(pt, "Remove points between", t0, tend + 0.01)
    for t, v in tv:
        if t >= t0:
            x = (t - t0) / max(1e-3, tend - t0)
            call(pt, "Add point", t, base * 2 ** (st * x * x / 12))
    call([pt, man], "Replace pitch tier")
    out = call(man, "Get resynthesis (overlap-add)")
    a = np.asarray(out.values[0], dtype=np.float32)
    pk = float(np.max(np.abs(a))) or 1.0
    return a / pk * 0.9 if pk > 0.99 else a


def setup():
    REP = json.load(open(f"out_dub/{NAME}/report_{LANG}.json", encoding="utf-8"))
    src_dir = os.path.join("tmp_dubsrc", NAME)
    if not os.path.isdir(os.path.join(src_dir, "dub")):
        import zipfile
        zipfile.ZipFile(os.path.join(src_dir, "dub.zip")).extractall(src_dir)
    dd = os.path.join(src_dir, "dub")
    L = json.load(open(os.path.join(dd, "lines.json"), encoding="utf-8"))
    refs, f0s = {}, {}
    for name in sorted({ln["name"] for ln in L["lines"] if not ln["vocal"]}):
        mine = sorted([ln for ln in L["lines"] if ln["name"] == name and not ln["vocal"]], key=lambda x: -x["bdur"])
        pieces, tot = [], 0.0
        for ln in mine:
            if tot > 12:
                break
            a = D.trim(D.resample(D.load(os.path.join(dd, "lines", f"{ln['i']:03d}.wav"), 44100), 44100, D.SR))
            pieces += [a, D.silence(0.3)]
            tot += len(a) / D.SR
        p = os.path.join(OUT, "tmp", f"ref_{name}.wav")
        ref = np.concatenate(pieces)
        D.save(ref, p)
        refs[name] = p
        f0s[name] = D.measure(ref)["f0"]
    return REP, refs, f0s


def spec_for(name, speed):
    hero = S.G["heroes"].get(name, {})
    spec = dict((hero.get("src") or {}).get(LANG) or S.G["src"][LANG])
    spec["speed"] = speed
    pre = (hero.get("pre") or {}).get(LANG) or hero.get("pre_all")
    return spec, pre


def make(text, spec, pre, ref, f0):
    s = D.source(text, spec)
    if pre:
        s = D.change(s, f0=pre.get("f0", 0), F=pre.get("F", 1.0), rng=pre.get("range", 1.0))
    raw = D.trim(D.vc(D.trim(s), ref))
    out, shift = D.match_pitch(raw, f0, 1.5)
    return D.trim(out), shift


def score(a, text, refemb):
    e = D.embed(a)
    h = D.heard(a, LANG, "fw:large-v3-turbo")
    return {"mos": S.utmos(a), "sim": round(float(np.dot(e, refemb)), 3), "clear": D.clear_pct(text, h)[0], "heard": h,
            "end": (S.pitch(a) or {}).get("end"), "dur": round(len(a) / D.SR, 2)}


def mp3(pieces, name):
    p = os.path.join(OUT, "tmp", name + ".wav")
    D.save(np.concatenate(pieces), p)
    D.ff("-i", p, "-af", "loudnorm=I=-16:TP=-1.5", "-ar", "44100", "-codec:a", "libmp3lame", "-q:a", "4", os.path.join(OUT, name + ".mp3"))


def nrm(a):
    return a * 0.9 / max(1e-4, float(np.abs(a).max()))


def main():
    t0 = time.time()
    REP, refs, f0s = setup()
    remb = {n: D.embed(D.load(p)) for n, p in refs.items()}
    rows = [r for r in REP["rows"] if r.get("text") and r.get("name") in refs]
    res, pieces = [], []
    if WHAT == "q":
        qs = [r for r in rows if S.kind(r["text"]) == "вопр-да/нет"]
        for r in qs:
            spec, pre = spec_for(r["name"], r.get("speed") or 1.0)
            out, _ = make(r["text"], spec, pre, refs[r["name"]], f0s[r["name"]])
            row = {"i": r["i"], "name": r["name"], "text": r["text"], "base": score(out, r["text"], remb[r["name"]])}
            v = {}
            for st in (3.0, 5.0):
                a = qrise(out, st)
                row[f"rise{int(st)}"] = score(a, r["text"], remb[r["name"]])
                v[st] = a
            res.append(row)
            pieces += [nrm(out), D.silence(0.4), nrm(v[3.0]), D.silence(0.4), nrm(v[5.0]), D.silence(1.0)]
            D.log(row["i"], row["name"], {k: (row[k]["mos"], row[k]["end"]) for k in ("base", "rise3", "rise5")})
        mp3(pieces, f"lab_q_{LANG}")
    elif WHAT == "pik":
        pk = [r for r in rows if r["name"] == "Пик"]
        hero = S.G["heroes"]["Пик"]
        base_pre = hero.get("pre_all")
        voices = ["af_heart", "af_sky", "af_nicole", "af_bella", "af_nova", "af_kore", "af_jessica"] if LANG == "en" else []
        variants = [("сейчас", None, base_pre)] + [(f"{v} без подъёма", v, None) for v in voices] + [(f"{v} подъём", v, base_pre) for v in voices[1:4]]
        best = {}
        for label, voice, pre in variants:
            agg = []
            for r in pk:
                spec, _ = spec_for("Пик", r.get("speed") or 1.0)
                if voice:
                    spec = dict(spec, voice=voice)
                try:
                    out, shift = make(r["text"], spec, pre, refs["Пик"], f0s["Пик"])
                    sc = score(out, r["text"], remb["Пик"])
                    sc["shift"] = shift
                    agg.append(dict(sc, i=r["i"]))
                    best.setdefault(label, []).append(out)
                except Exception as e:
                    agg.append({"i": r["i"], "error": str(e)[:200]})
            ok = [a for a in agg if "mos" in a]
            res.append({"variant": label, "mos": round(float(np.mean([a["mos"] for a in ok])), 2) if ok else None,
                        "sim": round(float(np.mean([a["sim"] for a in ok])), 3) if ok else None,
                        "clear": round(float(np.mean([a["clear"] for a in ok])), 1) if ok else None,
                        "shift": round(float(np.mean([abs(a["shift"]) for a in ok])), 1) if ok else None, "lines": agg})
            D.log(label, res[-1]["mos"], res[-1]["sim"], res[-1]["clear"])
        top = sorted([x for x in res[1:] if x["mos"]], key=lambda x: -(x["mos"] + 4 * (x["sim"] - res[0]["sim"])))[:2]
        for k in range(min(5, len(best.get("сейчас", [])))):
            pieces += [nrm(best["сейчас"][k]), D.silence(0.4)] + sum([[nrm(best[t["variant"]][k]), D.silence(0.4)] for t in top if len(best.get(t["variant"], [])) > k], []) + [D.silence(0.8)]
        mp3(pieces, f"lab_pik_{LANG}")
        res.append({"pairs_order": ["сейчас"] + [t["variant"] for t in top]})
    elif WHAT == "pre":
        for name in ("Филя", "Рон"):
            sel = [r for r in rows if r["name"] == name and len(r["text"].split()) >= 3][:10]
            for r in sel:
                spec, pre0 = spec_for(name, r.get("speed") or 1.0)
                out0, sh0 = make(r["text"], spec, pre0, refs[name], f0s[name])
                pre1 = dict(pre0 or {}, f0=f0s[name])
                out1, sh1 = make(r["text"], spec, pre1, refs[name], f0s[name])
                row = {"i": r["i"], "name": name, "text": r["text"], "base": dict(score(out0, r["text"], remb[name]), shift=sh0),
                       "pre": dict(score(out1, r["text"], remb[name]), shift=sh1)}
                res.append(row)
                if len(pieces) < 40:
                    pieces += [nrm(out0), D.silence(0.4), nrm(out1), D.silence(1.0)]
                D.log(name, r["i"], row["base"]["mos"], "→", row["pre"]["mos"], "сходство", row["base"]["sim"], "→", row["pre"]["sim"])
        mp3(pieces, f"lab_pre_{LANG}")
    json.dump({"what": WHAT, "rows": res, "minutes": round((time.time() - t0) / 60, 1)},
              open(os.path.join(OUT, f"lab_{WHAT}_{LANG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # коротко
    M = [f"# Проба «{WHAT}» — {NAME} {LANG}", ""]
    if WHAT == "q":
        for k in ("base", "rise3", "rise5"):
            M.append(f"- {k}: UTMOS {np.mean([r[k]['mos'] for r in res]):.2f}, сходство {np.mean([r[k]['sim'] for r in res]):.3f}, понято {np.mean([r[k]['clear'] for r in res]):.1f}, конец {np.mean([r[k]['end'] or 0 for r in res]):+.1f} пт")
        M.append("\nПары: как сейчас → +3 пт → +5 пт (lab_q_*.mp3)")
    elif WHAT == "pik":
        M += [f"- {x['variant']}: UTMOS {x['mos']}, сходство с Пиком {x['sim']}, понято {x['clear']}, подгонка высоты {x['shift']} пт" for x in res if "variant" in x]
        M.append(f"\nПары (lab_pik_*.mp3): {res[-1]['pairs_order']}")
    else:
        for name in ("Филя", "Рон"):
            R = [r for r in res if r["name"] == name]
            if R:
                M.append(f"- {name}: UTMOS {np.mean([r['base']['mos'] for r in R]):.2f} → {np.mean([r['pre']['mos'] for r in R]):.2f}; сходство {np.mean([r['base']['sim'] for r in R]):.3f} → {np.mean([r['pre']['sim'] for r in R]):.3f}; понято {np.mean([r['base']['clear'] for r in R]):.1f} → {np.mean([r['pre']['clear'] for r in R]):.1f}")
        M.append("\nПары: как сейчас → высота до перекраски (lab_pre_*.mp3)")
    open(os.path.join(OUT, f"lab_{WHAT}_{LANG}.md"), "w", encoding="utf-8").write("\n".join(M) + "\n")


if __name__ == "__main__":
    main()

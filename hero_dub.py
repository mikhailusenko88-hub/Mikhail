# Проверка дубляжа со свободными голосами героев (правило Михаила 24.11.2026: только свои свободные голоса).
# Те же реплики серии на языке перекрашиваются (Chatterbox VC, как в dub.py ветки golos-en) в НЫНЕШНИЙ голос героя
# (образец — его реплики из сборки серии) и в НОВЫЙ (образец — реплики из пробы в настоящем движке).
# Мерки, как в навыке dublyazh-barsik: понято ≥ 90 % (хинди — по буквам), свой образец ближе, чем соседи, высота как у образца.
#   python hero_dub.py run <язык>      — один язык, итог в hdub/<язык>.json + pack/*.flac
#   python hero_dub.py final           — сводка hdub/itog.md и ролики hdub/dub_<герой>.mp4
import json, os, re, subprocess, sys, traceback

import numpy as np

CFG = json.load(open("hero_dub.json", encoding="utf-8"))
OUT = "hdub"
SRM = 44100
LANGS = ["en", "es", "pt", "hi", "de"]
LNAME = {"en": "английский", "es": "испанский", "pt": "португальский", "hi": "хинди", "de": "немецкий"}
SLUG = {"Барсик": "barsik", "Рон": "ron", "Пик": "pik", "Филя": "filya", "Топа": "topa"}


def log(*a):
    print(*a, flush=True)


def lines_of(build):
    dd = f"dubz/{build}/dub"
    return dd, json.load(open(f"{dd}/lines.json", encoding="utf-8"))["lines"]


def make_ref(D, build, name, path):
    """Образец голоса: самые длинные реплики героя из сборки, всего ~12 с (как в dub.py)."""
    dd, L = lines_of(build)
    mine = sorted([ln for ln in L if ln["name"] == name and not ln["vocal"]], key=lambda x: -x["bdur"])
    if not mine:
        raise RuntimeError(f"в сборке {build} нет реплик «{name}»")
    pieces, tot = [], 0.0
    for ln in mine:
        if tot > 12:
            break
        a = D.trim(D.resample(D.load(f"{dd}/lines/{ln['i']:03d}.wav", SRM), SRM, D.SR))
        pieces += [a, D.silence(0.3)]
        tot += len(a) / D.SR
    ref = np.concatenate(pieces)
    D.save(ref, path)
    return ref, D.measure(ref)["f0"], round(tot, 1)


def variants(hero):
    """[(метка, сборка, имя в сборке, подпись)] — нынешний голос и новые кандидаты."""
    v = [("old", CFG["old_build"], hero, "как сейчас")]
    for k, c in enumerate(CFG["new"].get(hero, []), 1):
        v.append((f"new{k}", CFG["new_build"], c["name"], c["note"]))
    return v


def run(lang):
    sys.path.insert(0, "ge")
    import dubcore as D
    G = json.load(open("ge/geroi.json", encoding="utf-8"))
    P = json.load(open(f"ge/perevod/{CFG['perevod']}.json", encoding="utf-8"))
    for d in (OUT, "pack", D.TMP):
        os.makedirs(d, exist_ok=True)
    wsz = G.get("whisper_lang", {}).get(lang, G.get("whisper", "small"))
    by_chars = lang in G.get("by_chars", [])

    # образцы: нынешние пятеро (сборка серии) и новые кандидаты (проба движка)
    refs, f0s, E = {}, {}, {}
    for hero in SLUG:
        vs = variants(hero) if hero in CFG["heroes"] else [("old", CFG["old_build"], hero, "как сейчас")]
        for tag, build, name, _ in vs:
            key = f"{SLUG[hero]}_{tag}"
            p = f"{D.TMP}/ref_{key}.wav"
            try:
                a, f0, sec = make_ref(D, build, name, p)
            except Exception as ex:
                log("нет образца", key, ex); continue
            refs[key], f0s[key], E[key] = p, f0, D.embed(a)
            log("образец", key, f"{f0} Гц", f"{sec} с")

    rows = []
    for hero in CFG["heroes"]:
        hs = G["heroes"].get(hero, {})
        ids = [i for i, w in P["who"].items() if w == hero and P[lang].get(i)]
        ids = [i for i in ids if 3 <= len(D.words(P["en"].get(i, P[lang][i]))) <= 12][:CFG.get("lines", 6)]
        log(hero, lang, "реплики", ids)
        for tag, build, name, note in variants(hero):
            key = f"{SLUG[hero]}_{tag}"
            if key not in refs:
                continue
            got, clears, pieces = [], [], []
            for k, i in enumerate(ids):
                text = P[lang][i]
                spec = dict((hs.get("src") or {}).get(lang) or G["src"][lang])
                if hs.get("speed"):
                    spec["speed"] = round(spec.get("speed", 1.0) * hs["speed"], 3)
                pre = (hs.get("pre") or {}).get(lang) or hs.get("pre_all")
                best = None
                for attempt in range(2):
                    try:
                        a, info = D.render(text, spec, refs[key], f0s[key], pre=pre)
                        h = D.heard(a, lang, wsz)
                        clear, extra = D.clear_pct(text, h)
                        if by_chars:
                            clear, extra = D.char_pct(text, h), 0
                        if best is None or clear - 10 * extra > best[1] - 10 * best[2]:
                            best = (a, clear, extra, h, info["shift_st"])
                        if clear >= 85 and extra <= 1:
                            break
                        spec = dict(spec, speed=round(max(0.8, spec.get("speed", 1.0) * 0.92), 3))
                    except Exception:
                        traceback.print_exc()
                if best is None:
                    continue
                a, clear, extra, h, shift = best
                D.save(a, f"{D.TMP}/o.wav")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{D.TMP}/o.wav", "-ar", "48000", "-ac", "1",
                                f"pack/{lang}_{key}__{k:02d}.flac"], check=True)
                got.append({"i": i, "text": text, "heard": h, "clear": clear, "extra": extra, "shift": shift})
                clears.append(clear); pieces += [a, D.silence(0.3)]
                log(f"{lang} {key} {i:>3} понято {clear:5.1f}% лишних {extra} | {text} | {h}")
            if not pieces:
                continue
            arr = np.concatenate(pieces)
            e = D.embed(arr)
            m = D.measure(arr)
            # соседи: для нового голоса — новые голоса остальных героев (первый кандидат) и нынешние Филя, Топа; для нынешнего — нынешние
            others = []
            for h2 in SLUG:
                if h2 == hero:
                    continue
                k2 = f"{SLUG[h2]}_new1" if (tag != "old" and f"{SLUG[h2]}_new1" in E) else f"{SLUG[h2]}_old"
                if k2 in E:
                    others.append((k2, float(e @ E[k2])))
            near = max(others, key=lambda x: x[1]) if others else ("", 0.0)
            rows.append({"hero": hero, "tag": tag, "note": note, "lang": lang, "n": len(got),
                         "clear": round(float(np.mean(clears)), 1), "min": round(float(np.min(clears)), 1),
                         "weak": sum(1 for c in clears if c < 85),
                         "sim": round(float(e @ E[key]), 3), "other": round(near[1], 3), "nearest": near[0],
                         "sim_old": round(float(e @ E[f"{SLUG[hero]}_old"]), 3) if f"{SLUG[hero]}_old" in E else None,
                         "f0": m["f0"], "f0_ref": f0s[key], "lines": got})
            log("ИТОГ", lang, key, rows[-1]["clear"], "сходство", rows[-1]["sim"], "сосед", near)
    json.dump({"lang": lang, "rows": rows, "ids": {h: [r["i"] for r in next((x["lines"] for x in rows if x["hero"] == h), [])]
                                                   for h in CFG["heroes"]}},
              open(f"{OUT}/{lang}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def final():
    import svoy2
    os.makedirs(OUT, exist_ok=True)
    R = []
    for lang in LANGS:
        p = f"{OUT}/{lang}.json"
        if os.path.exists(p):
            R += json.load(open(p, encoding="utf-8"))["rows"]
    md = ["# Дубляж со свободными голосами героев — проверка на 5 языках", "",
          f"Те же реплики серии ({CFG['perevod']}) перекрашены в нынешний голос героя (сборка {CFG['old_build']}) и в новый "
          f"(проба движка {CFG['new_build']}). Источники и перекраска — как в дубляже (Kokoro, Piper, Chatterbox — свободные).",
          "Планка: понято ≥ 90 % (хинди — по буквам), свой образец ближе соседей, высота как у образца.", ""]
    ok_all = {}
    for hero in CFG["heroes"]:
        md += [f"## {hero}", "", "| голос | язык | понято % | худшая | слабых | сходство со своим | ближайший сосед | Гц (образец) | вывод |",
               "|---|---|---|---|---|---|---|---|---|"]
        for tag, build, name, note in variants(hero):
            for lang in LANGS:
                r = next((x for x in R if x["hero"] == hero and x["tag"] == tag and x["lang"] == lang), None)
                if not r:
                    md.append(f"| {note} | {LNAME[lang]} | нет данных | | | | | | |"); continue
                old = next((x for x in R if x["hero"] == hero and x["tag"] == "old" and x["lang"] == lang), None)
                good = (r["clear"] >= 90 or (old and r["clear"] >= old["clear"] - 2)) and r["sim"] > r["other"]
                ok_all.setdefault((hero, tag), []).append(good)
                why = "годится" if good else ("слова хуже" if r["clear"] < 90 else "похож на соседа")
                md.append(f"| {note} | {LNAME[lang]} | {r['clear']} | {r['min']} | {r['weak']} из {r['n']} | {r['sim']} | "
                          f"{r['other']} ({r['nearest']}) | {r['f0']} ({r['f0_ref']}) | {why} |")
        md.append("")
    md += ["## Сводка", ""]
    for (hero, tag), v in ok_all.items():
        md.append(f"- {hero}, {tag}: годится на {sum(v)} из {len(v)} языков")
    md += ["", "## Что услышал распознаватель (новые голоса, реплики ниже 85 %)", ""]
    for r in R:
        if r["tag"] == "old":
            continue
        for ln in r["lines"]:
            if ln["clear"] < 85:
                md.append(f"- {r['hero']} {r['tag']} {r['lang']}: {ln['clear']} % | {ln['text']} | {ln['heard']}")
    open(f"{OUT}/itog.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(R, open(f"{OUT}/hero_dub.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log("\n".join(md[:60]))
    # ролики: по герою — на каждом языке «как сейчас» и новые голоса, по две реплики
    for hero in CFG["heroes"]:
        pick = []
        for lang in LANGS:
            for tag, build, name, note in variants(hero):
                r = next((x for x in R if x["hero"] == hero and x["tag"] == tag and x["lang"] == lang), None)
                if r:
                    pick.append((f"{hero}: {LNAME[lang]} — {note}", f"{lang}_{SLUG[hero]}_{tag}", f"понято {r['clear']} %"))
        try:
            svoy2.video(pick, f"{OUT}/dub_{SLUG[hero]}.mp4", [("", k < CFG.get("listen", 2)) for k in range(12)], soft=False)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    run(sys.argv[2]) if sys.argv[1] == "run" else final()

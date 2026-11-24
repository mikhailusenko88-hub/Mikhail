#!/usr/bin/env python3
"""Свободные голоса Барсику и Рону (25.11.2026). Правило Михаила: голоса с некоммерческой лицензией не используем.
Сейчас Барсик — xenia, Рон — kseniya (обе — Silero v5_ru, CC BY-NC). Ищем им замену на v5_cis (MIT), как можно ближе к нынешним.
Основа — pik_free.py чата мультика (ветка golos-pik): кандидат = диктор + обработка как в движке (тон ×P, тембр ×F, темп ×T; здесь через WORLD).

Мерка — реплики героя из сборок студии (dubz/<сборка>/dub/lines/NNN.wav из релиза studio-<сборка>/dub.zip), только для сравнения.
Кандидаты читают те же 8 реплик. Оценка: похожесть тембра (resemblyzer), высота, яркость, темп, слова (whisper), естественность (UTMOS)
и чистота произношения GOP (svoy_lib.ali) — чтобы отсеять дикторов с акцентом (Рону Михаил выбрал kseniya именно за речь без акцента).
  python hero_free.py r1 <barsik|ron> <part> <n>
  python hero_free.py final          → hero/itog_<герой>.md, hero/hero_free.json, hero/proba_<герой>.mp4
"""
import glob, json, math, os, subprocess, sys
import numpy as np
import svoy_lib as SL

HEROES = {"barsik": "Барсик", "ron": "Рон"}
BUILDS = ["38g", "39f"]
# женские дикторы v5_cis с хорошей разборчивостью (cast/kasting.json). Заняты: ru_alfia — Филя, ru_miyau — Топа, ru_albina — рассказчица,
# ru_zara — проба Пика (чат мультика)
SPK = ["ru_zinaida", "ru_kermen", "ru_aigul", "ru_nurgul", "ru_vika", "ru_zhadyra", "ru_oksana", "ru_ekaterina", "ru_zhazira", "ru_saida"]
FF = [1.0, 1.08, 1.16]
NPH = 8
LISTEN = (0, 2, 4, 6)


def log(*a):
    print(*a, flush=True)


def lines_of(hero):
    out = []
    for b in BUILDS:
        f = f"dubz/{b}/dub/lines.json"
        if not os.path.exists(f):
            log("нет", f); continue
        for l in json.load(open(f, encoding="utf-8"))["lines"]:
            if l["name"] != HEROES[hero] or l.get("vocal") or l.get("soft"):
                continue
            n = len(l["text"].split())
            if 3 <= n <= 14 and 1.0 <= l["dur"] <= 7:
                out.append({"b": b, "i": l["i"], "text": l["text"], "path": f"dubz/{b}/dub/lines/{l['i']:03d}.wav", "n": n})
    return out


def eval_lines(L):
    """8 реплик для сравнения: из первой сборки, 4–10 слов, без повторов."""
    seen, out = set(), []
    for l in L:
        if 4 <= l["n"] <= 10 and l["text"] not in seen:
            seen.add(l["text"]); out.append(l)
        if len(out) == NPH:
            break
    return out


def target(hero, save_ref):
    import svoy_omo, svoy_free
    L = lines_of(hero)
    E = eval_lines(L)
    A, Fs = [], []
    for l in L[:40]:
        a = SL.load(l["path"], SL.SR16); A.append(a); Fs.append(SL.feats(a, l["text"]))
    T = {k: float(np.median([x[k] for x in Fs])) for k in ("f0", "cen", "range", "rate")}
    T["emb"] = SL.emb(A).tolist()
    T["n"] = len(L)
    if save_ref:      # образец и его замеры пишет одно задание (одноимённые файлы из разных заданий портятся при слиянии)
        g, u, m = [], [], []
        for k, l in enumerate(E):
            a = SL.load(l["path"], SL.SR16)
            _, q = SL.ali(a, l["text"]); g.append(q["gop"]); u.append(SL.utmos(a)); m.append(SL.heard_match(l["path"], l["text"])[1])
            if k in LISTEN:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", l["path"], "-ar", "48000", "-ac", "1", f"pack/T__{hero}__{k:02d}.flac"], check=True)
        T.update(gop=float(np.mean(g)), utmos=float(np.mean(u)), match=float(np.mean(m)))
        json.dump({k: v for k, v in T.items()}, open(f"pack/target_{hero}.json", "w"))
        json.dump([l["text"].replace("\u0301", "").replace("\u0300", "") for l in E], open(f"pack/phrases_{hero}.json", "w", encoding="utf-8"), ensure_ascii=False)
    return T, E


def engine(x, sr, P, F, Tm):
    """Как движок (multik-bars-golos.js, say()): модель читает с тоном ×P/F и темпом ×T/F (здесь WORLD), потом звук проигрывается в F раз быстрее."""
    import pyworld as pw
    x = x.astype(np.float64)
    f0, t = pw.harvest(x, sr, f0_floor=80, f0_ceil=600, frame_period=5.0)
    sp = pw.cheaptrick(x, f0, t, sr); ap = pw.d4c(x, f0, t, sr)
    k = Tm / F
    n = max(2, int(round(len(f0) / k)))
    idx = np.linspace(0, len(f0) - 1, n)
    i0 = np.floor(idx).astype(int); i1 = np.minimum(i0 + 1, len(f0) - 1); w = (idx - i0)[:, None]
    f0n = np.where((f0[i0] > 0) & (f0[i1] > 0), f0[i0] * (1 - w[:, 0]) + f0[i1] * w[:, 0], 0) * (P / F)
    spn = np.exp(np.log(sp[i0] + 1e-12) * (1 - w) + np.log(sp[i1] + 1e-12) * w)
    apn = ap[i0] * (1 - w) + ap[i1] * w
    y = pw.synthesize(np.ascontiguousarray(f0n), np.ascontiguousarray(spn), np.ascontiguousarray(apn), sr, 5.0)
    if abs(F - 1) > .004:
        m = int(np.floor((len(y) - 2) / F)); y = np.interp(np.arange(m) * F, np.arange(len(y)), y)
    y = y / (np.abs(y).max() + 1e-9) * 0.9
    return y.astype(np.float32)


def J(r, T):
    dst = abs(12 * math.log2(max(r["f0"], 1) / T["f0"]))
    return round(3 * r["sim"] + 2 * r["match"] + 0.6 * r["utmos"] + 2 * r["gop"] - 0.2 * dst - 0.3 * abs(r["rate"] - T["rate"])
                 - 0.0006 * abs(r["cen"] - T["cen"]) - 0.03 * abs(r["range"] - T["range"]), 3)


def r1(hero, part, n):
    import gen, svoy_free, svoy_omo, svoy2
    os.makedirs("pack", exist_ok=True); os.makedirs("tmp", exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    T, E = target(hero, save_ref=(part == 0))
    log(hero, "мерка:", {k: round(T[k], 2) for k in ("f0", "cen", "range", "rate")}, "реплик", T["n"])
    PH = [l["text"].replace("\u0301", "").replace("\u0300", "") for l in E]      # знак ударения из сценария («Са́харом») ломал разметку
    marks = {t: svoy_free.mark_full(t) for t in PH}
    log("разметка:", marks[PH[0]], "|", marks[PH[1]])
    m = gen.silero_model("v5_cis_base")
    temb = np.array(T["emb"])
    for s in SPK[part::n]:
        base, bf = {}, []
        for k, t in enumerate(PH):
            a = m.apply_tts(text=marks[t], speaker=s, sample_rate=48000)
            a = a.numpy() if hasattr(a, "numpy") else np.asarray(a)
            p = f"tmp/{s}_{k}.wav"; SL.save(a, p, 48000)
            base[k] = SL.load(p, 24000); bf.append(SL.feats(SL.load(p, SL.SR16), t))
        b_f0 = float(np.median([x["f0"] for x in bf])); b_rate = float(np.median([x["rate"] for x in bf]))
        log(s, "свой тон", round(b_f0), "Гц, темп", round(b_rate, 2))
        C = []
        for ft in (0.96 * T["f0"], 1.04 * T["f0"]):
            for F in FF:
                t0 = min(1.35, max(0.85, T["rate"] / b_rate))
                for Tm in (round(t0, 2), round(t0 * 0.92, 2)):
                    C.append({"id": f"{s[3:]}_{int(round(ft))}_{F}_{Tm}", "spk": s, "P": round(ft / b_f0, 3), "F": F, "T": Tm})
        for c in C:
            try:
                outs, res = [], []
                for k, t in enumerate(PH):
                    y = engine(base[k], 24000, c["P"], c["F"], c["T"])
                    p = f"tmp/{hero}_{c['id']}_{k}.wav"; SL.save(y, p, 24000)
                    a16 = SL.load(p, SL.SR16); outs.append(a16)
                    heard, mt = SL.heard_match(p, t)
                    _, q = SL.ali(a16, t)
                    res.append({"ut": SL.utmos(a16), "match": mt, "heard": heard, "gop": q["gop"], "f": SL.feats(a16, t)})
                    if k in LISTEN:
                        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ar", "48000", f"pack/C__{hero}__{c['id']}__{k:02d}.flac"], check=True)
                r = dict(c, hero=hero, sim=round(float(np.dot(SL.emb(outs), temb)), 4),
                         utmos=round(float(np.mean([x["ut"] for x in res])), 3), match=round(float(np.mean([x["match"] for x in res])), 3),
                         gop=round(float(np.mean([x["gop"] for x in res])), 4),
                         **{q: round(float(np.median([x["f"][q] for x in res])), 2) for q in ("f0", "cen", "range", "rate")},
                         bad=[(PH[k], x["heard"]) for k, x in enumerate(res) if x["match"] < 0.85])
                r["J"] = J(r, T)
                json.dump(r, open(f"pack/L_{hero}_{c['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
                log(hero, c["id"], "J", r["J"], "похожесть", r["sim"], "Гц", r["f0"], "темп", r["rate"], "UTMOS", r["utmos"],
                    "слова", r["match"], "GOP", r["gop"])
            except Exception as e:
                import traceback
                log("ОШИБКА", c["id"], repr(e)); traceback.print_exc()


def final():
    import svoy2
    os.makedirs("hero", exist_ok=True)
    R, TT = {}, {}
    for hero in HEROES:
        R[hero] = sorted([json.load(open(j, encoding="utf-8")) for j in glob.glob(f"pack/L_{hero}_*.json")], key=lambda r: -r["J"])
        TT[hero] = json.load(open(f"pack/target_{hero}.json")) if os.path.exists(f"pack/target_{hero}.json") else None
    # лучший у каждого диктора
    by = {}
    for hero, L in R.items():
        seen, b = set(), []
        for r in L:
            if r["spk"] not in seen:
                seen.add(r["spk"]); b.append(r)
        by[hero] = b
    # разные дикторы у Барсика и Рона: перебор пар из первых пяти
    pick, bestsum = {}, -1e9
    for a in by.get("barsik", [])[:5] or [None]:
        for b in by.get("ron", [])[:5] or [None]:
            if a and b and a["spk"] == b["spk"]:
                continue
            s = (a["J"] if a else 0) + (b["J"] if b else 0)
            if s > bestsum:
                bestsum, pick = s, {"barsik": a, "ron": b}
    out = {"made": "2026-11-25", "model": "v5_cis_base (MIT)", "voices": {}}
    for hero, L in R.items():
        T = TT[hero]
        if not L or not T:
            continue
        Lm = [f"# Свободный голос героя «{HEROES[hero]}» (Silero v5_cis, MIT) — ближе к нынешнему", "",
              f"Мерка — нынешний голос ({T['n']} реплик сборок {', '.join(BUILDS)}): {T['f0']:.0f} Гц, центроид {T['cen']:.0f} Гц, темп {T['rate']:.1f} слога/с, "
              f"живость {T['range']:.1f} полутона; на 8 репликах: слова {T.get('match', 0):.3f}, UTMOS {T.get('utmos', 0):.2f}, GOP {T.get('gop', 0):.3f}.",
              "J = 3·похожесть + 2·слова + 0,6·UTMOS + 2·GOP − 0,2·разница высоты (полутоны) − 0,3·разница темпа − 0,0006·разница центроида − 0,03·разница живости.",
              "GOP — чистота произношения (уверенность фонемного распознавателя в ожидаемых звуках): чем ближе к мерке, тем меньше акцента.",
              f"Строка для движка: `{HEROES[hero]}:girl:speaker=<диктор>:P=<P>:F=<F>:T=<T>:R=1.15`. Тон и темп здесь через WORLD — итоговую пробу делает движок.", "",
              "| | кандидат | J | похожесть | Гц | центроид | темп | живость | UTMOS | слова | GOP | P | F | T |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(L[:25], 1):
            Lm.append(f"| {i} | {r['id']} | {r['J']} | {r['sim']} | {r['f0']:.0f} | {r['cen']:.0f} | {r['rate']} | {r['range']} | {r['utmos']} | "
                      f"{r['match']} | {r['gop']} | {r['P']} | {r['F']} | {r['T']} |")
        Lm += ["", "## Лучший вариант каждого диктора", "", "| диктор | J | похожесть | Гц | темп | UTMOS | слова | GOP | P/F/T |", "|---|---|---|---|---|---|---|---|---|"]
        for r in by[hero]:
            Lm.append(f"| {r['spk']} | {r['J']} | {r['sim']} | {r['f0']:.0f} | {r['rate']} | {r['utmos']} | {r['match']} | {r['gop']} | {r['P']}/{r['F']}/{r['T']} |")
        p = pick.get(hero)
        if p:
            Lm += ["", f"**Выбор (разные дикторы у Барсика и Рона): `{HEROES[hero]}:girl:speaker={p['spk']}:P={p['P']}:F={p['F']}:T={p['T']}:R=1.15`**"]
        open(f"hero/itog_{hero}.md", "w", encoding="utf-8").write("\n".join(Lm) + "\n")
        log("\n".join(Lm[:16]))
        top = ([p] if p else []) + [r for r in by[hero] if not p or r["spk"] != p["spk"]][:2]
        out["voices"][hero] = [{"id": r["id"], "golos": f"girl:speaker={r['spk']}:P={r['P']}:F={r['F']}:T={r['T']}:R=1.15", "J": r["J"],
                                "sim": r["sim"], "f0": r["f0"], "utmos": r["utmos"], "match": r["match"], "gop": r["gop"]} for r in top]
        ph = json.load(open(f"pack/phrases_{hero}.json", encoding="utf-8")) if os.path.exists(f"pack/phrases_{hero}.json") else [""] * NPH
        vp = [(f"{HEROES[hero]} — сейчас", f"T__{hero}", "нынешний голос (образец)")]
        for i, r in enumerate(top, 1):
            vp.append((f"{HEROES[hero]} — свободный {i}", f"C__{hero}__{r['id']}", f"{r['spk'][3:]}, похожесть {r['sim']:.2f}"))
        try:
            svoy2.video(vp, f"hero/proba_{hero}.mp4", [(t, k in LISTEN) for k, t in enumerate(ph)])
        except Exception as e:
            log("ролик не собран:", hero, repr(e))
    json.dump(out, open("hero/hero_free.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "r1":
        r1(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        final()

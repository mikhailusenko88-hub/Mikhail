# Дубляж серии «Кот Барсик» на другой язык голосами наших героев (вариант 2 — перекраска, выбран Михаилом 22.11.2026).
#   python dub.py <сборка> <язык>      например: python dub.py 36dub en
# Берёт из релиза studio-<сборка> файл dub.zip (студия кладёт: dub/lines/NNN.wav — каждая реплика, dub/lines.json — расписание,
# dub/me_NN.wav — музыка и шумы без голосов, dub/full.wav — полное сведение), перевод perevod/<серия>.json,
# настройки голосов geroi.json. Каждая реплика: источник с родным произношением → перекраска в голос героя (образец —
# его же реплики из этой серии) → высота как у героя → по времени в окно русской реплики → громкость как у русской.
# Смех и вздохи остаются свои. Сведение: громкость музыки и голосов подбирается по полному русскому сведению.
# Итог: out_dub/<сборка>/dub_<язык>.wav (для YouTube Studio → Языки → Дубляж), отчёт по репликам.
import json, os, subprocess, sys, time, traceback, zipfile

import numpy as np
import soundfile as sf

import dubcore as D

NAME, LANG = sys.argv[1], sys.argv[2]
SRM = 44100                       # частота сведения студии
OUT = os.path.join("out_dub", NAME)
os.makedirs(OUT, exist_ok=True)
G = json.load(open("geroi.json", encoding="utf-8"))


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    vals = [float(x.split("I:")[1].split("LUFS")[0]) for x in r.stderr.splitlines() if "I:" in x and "LUFS" in x]
    return vals[-1] if vals else None


def normalize(src, dst, target=-15.0):
    """Как studio.js: усиление до −15 LUFS и ограничитель 0.84, до трёх подходов."""
    I = lufs(src)
    gain = target - (I if I is not None else target)
    for _ in range(3):
        D.ff("-i", src, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.84:attack=5:release=80:level=disabled", "-ar", str(SRM), dst)
        J = lufs(dst)
        if J is None or abs(J - target) < 0.4:
            break
        gain += target - J
    return I, lufs(dst)


VOW = "aeiouyáéíóúàâêôãõüöäåæøœіыэяюёаеиоу"


def syllables(text):
    """Грубо: группы гласных (для сравнения темпа языков, не для точного счёта)."""
    import re
    return max(1, len(re.findall(f"[{VOW}]+", text.lower())))


def with_speed(spec, k):
    s = dict(spec)
    s["speed"] = round(max(0.8, min(1.45, s.get("speed", 1.0) * k)), 3)
    return s


def render_fit(text, spec, ref, f0, pre, target):
    """Озвучить так, чтобы длина была близка к русской реплике: второй проход с темпом источника,
    а не растяжкой готового звука — речь остаётся естественной на любом языке."""
    a, info = D.render(text, spec, ref, f0, pre=pre)
    r = len(a) / D.SR / max(0.3, target)
    if r > 1.08 or r < 0.85:
        sp2 = with_speed(spec, r if r > 1 else max(r, 0.9))
        a2, info2 = D.render(text, sp2, ref, f0, pre=pre)
        r2 = len(a2) / D.SR / max(0.3, target)
        if abs(np.log(r2)) < abs(np.log(r)):
            return a2, info2, sp2, r2
    return a, info, spec, r


def place(track, arr, t, sr=SRM):
    i0 = int(round(t * sr))
    if i0 >= len(track):
        return
    n = min(len(arr), len(track) - i0)
    track[i0:i0 + n] += arr[:n]


def main():
    t_start = time.time()
    src_dir = os.path.join("tmp_dubsrc", NAME)
    if not os.path.isdir(os.path.join(src_dir, "dub")):
        os.makedirs(src_dir, exist_ok=True)
        zipfile.ZipFile(os.path.join(src_dir, "dub.zip")).extractall(src_dir)
    dd = os.path.join(src_dir, "dub")
    L = json.load(open(os.path.join(dd, "lines.json"), encoding="utf-8"))
    ep = G.get("builds", {}).get(NAME, NAME)
    P = json.load(open(f"perevod/{ep}.json", encoding="utf-8"))
    T = P[LANG]
    D.log(f"{NAME} → {LANG}: реплик {len(L['lines'])}, длина {L['dur']:.1f} с, перевод perevod/{ep}.json")

    # русские реплики (44.1 кГц), проверка, что перевод от этой же серии
    ru = {}
    bad = []
    for ln in L["lines"]:
        a = D.load(os.path.join(dd, "lines", f"{ln['i']:03d}.wav"), SRM)
        ru[ln["i"]] = a
        if not ln["vocal"] and P.get("ru", {}).get(str(ln["i"])) not in (None, ln["text"]):
            bad.append(ln["i"])
    if bad:
        D.log("ВНИМАНИЕ: текст реплик не совпадает с переводом:", bad[:10])

    # образцы голосов героев — их же реплики из этой серии (самые длинные, всего ~12 с)
    refs, f0s = {}, {}
    for name in sorted({ln["name"] for ln in L["lines"] if not ln["vocal"]}):
        mine = sorted([ln for ln in L["lines"] if ln["name"] == name and not ln["vocal"]], key=lambda x: -x["bdur"])
        pieces, tot = [], 0.0
        for ln in mine:
            if tot > 12:
                break
            a = D.trim(D.resample(ru[ln["i"]], SRM, D.SR))
            pieces += [a, D.silence(0.3)]
            tot += len(a) / D.SR
        ref = np.concatenate(pieces)
        p = os.path.join(OUT, f"ref_{G['slug'].get(name, name)}.wav")
        D.save(ref, p)
        refs[name] = p
        f0s[name] = G.get("f0", {}).get(name) or D.measure(ref)["f0"]
    D.log("высота героев", f0s)

    # озвучка реплик
    rows, dub = [], {}
    starts = [ln["t"] for ln in L["lines"]]
    for k, ln in enumerate(L["lines"]):
        if ln["vocal"]:
            continue
        i, name = ln["i"], ln["name"]
        text = T.get(str(i))
        row = {"i": i, "name": name, "t": ln["t"], "ru": ln["text"], "text": text}
        if not text:
            row["error"] = "нет перевода"
            rows.append(row)
            continue
        hero = G["heroes"].get(name, {})
        spec = dict((hero.get("src") or {}).get(LANG) or G["src"][LANG])
        if hero.get("speed"):
            spec["speed"] = round(spec.get("speed", 1.0) * hero["speed"], 3)
        pre = (hero.get("pre") or {}).get(LANG) or hero.get("pre_all")
        nxt = min([s for s in starts if s > ln["t"] + 0.05] + [L["dur"]])
        window = max(ln["bdur"], nxt - ln["t"] - 0.08)
        target = min(window, max(ln["bdur"], 0.4) * hero.get("len_k", 1.0))   # длина русской реплики (и не дальше следующей)
        best = None
        for attempt in range(3):
            try:
                tgt = target if attempt == 0 else min(window, target * 1.3)   # вторая попытка — можно чуть длиннее (в паузу)
                a, info, used, ratio = render_fit(text, spec, refs[name], f0s[name], pre, tgt)
                heard = D.heard(a, LANG, G.get("whisper", "small"))
                clear, extra = D.clear_pct(text, heard)
                cand = {"a": a, "heard": heard, "clear": clear, "extra": extra, "shift": info["shift_st"],
                        "speed": used.get("speed", 1.0), "ratio": round(ratio, 2)}
                if best is None or (clear - 10 * extra) > (best["clear"] - 10 * best["extra"]):
                    best = cand
                if clear >= 85 and extra <= 1:
                    break
                spec = with_speed(spec, 0.92)   # вторая попытка — медленнее (разборчивее)
            except Exception as ex:
                traceback.print_exc()
                row["error"] = f"{type(ex).__name__}: {ex}"[:200]
        if best is None:
            rows.append(row)
            continue
        a = best["a"]
        k_t = len(a) / D.SR / window
        if k_t > 1.0:
            a = D.tempo(a, min(k_t, 1.3))
        a = D.resample(a, D.SR, SRM)
        r_ru, r_db = D.rms(D.trim(ru[i], sr=SRM)), D.rms(a)
        if r_db > 0:
            a = a * (r_ru / r_db)
        if ln.get("soft"):
            a = a * 0.65
        dub[i] = a
        row.update(heard=best["heard"], clear=best["clear"], extra=best["extra"], shift=best["shift"],
                   speed=best["speed"], tempo=round(max(1.0, k_t), 2), over=round(max(0.0, len(a) / SRM - window), 2),
                   sec=round(len(a) / SRM, 2), window=round(window, 2), ru_sec=round(ln["bdur"], 2),
                   syl_ru=round(syllables(ln["text"]) / max(0.3, ln["bdur"]), 1),
                   syl=round(syllables(text) / max(0.3, len(a) / SRM), 1))
        rows.append(row)
        D.log(f"{i:3d} {name:7s} понято {best['clear']:5.1f}% лишних {best['extra']} темп ×{row['tempo']} | {text}")

    # сведение: подобрать громкость музыки (a) и голосов (b) по русскому полному сведению
    me = np.concatenate([D.load(os.path.join(dd, f), SRM) for f in sorted(os.listdir(dd)) if f.startswith("me_")])
    full = D.load(os.path.join(dd, "full.wav"), SRM).astype(np.float64)
    n = max(len(me), len(full))
    me = np.pad(me, (0, n - len(me)))
    full = np.pad(full, (0, n - len(full)))
    # голоса в полном сведении сдвинуты на несколько мс (пересчёт частоты) — найти сдвиг и громкость по репликам
    lags, scales = [], []
    quiet = np.ones(n, dtype=bool)
    for ln in L["lines"]:
        quiet[int(ln["t"] * SRM):int((ln["t"] + ln["bdur"]) * SRM) + SRM // 5] = False
    mq = me[quiet].astype(np.float64)
    a0 = float(np.dot(mq, full[quiet]) / max(1e-9, np.dot(mq, mq))) if quiet.any() else 0.0
    res0 = full - a0 * me.astype(np.float64)
    for ln in [x for x in L["lines"] if not x["vocal"]][:24]:
        a = ru[ln["i"]].astype(np.float64)
        i0 = int(round(ln["t"] * SRM))
        lo = max(0, i0 - SRM // 10)
        seg = res0[lo:i0 + len(a) + SRM // 10]
        if len(seg) <= len(a) or not np.any(a):
            continue
        x = np.correlate(seg, a, mode="valid")
        k = int(np.argmax(np.abs(x)))
        lags.append(k - (i0 - lo))
        scales.append(x[k] / float(np.dot(a, a)))
    lag = int(np.median(lags)) if lags else 0
    gb = float(np.median(scales)) if scales else 1.0
    v_ru = np.zeros(n, dtype=np.float64)
    for ln in L["lines"]:
        place(v_ru, ru[ln["i"]] * (0.65 if ln.get("soft") else 1.0), ln["t"] + lag / SRM)
    mem = me.astype(np.float64)
    ga = float(np.dot(mem, full - gb * v_ru) / max(1e-9, np.dot(mem, mem)))
    # совпадение по громкости во времени (огибающая 50 мс) — сравнение по форме волны занижает из-за сдвигов в доли мс
    fr = SRM // 20
    m_ = (n // fr) * fr

    def env(x):
        return np.sqrt(np.mean(np.asarray(x[:m_], dtype=np.float64).reshape(-1, fr) ** 2, axis=1))
    e_full, e_mod = env(full), env(ga * mem + gb * v_ru)
    fit = 1 - float(np.sum((e_full - e_mod) ** 2) / max(1e-9, np.sum(e_full ** 2)))
    D.log(f"сведение: сдвиг голосов {lag} отсч. ({lag / SRM * 1000:.1f} мс), музыка ×{ga:.3f}, голоса ×{gb:.3f}, совпадение с русским сведением {fit:.3f}")

    v_dub = np.zeros(n, dtype=np.float64)
    for ln in L["lines"]:
        if ln["vocal"]:
            place(v_dub, ru[ln["i"]] * (0.65 if ln.get("soft") else 1.0), ln["t"] + lag / SRM)   # смех и вздохи — свои
        elif ln["i"] in dub:
            place(v_dub, dub[ln["i"]], ln["t"] + lag / SRM)
    mix = ga * me.astype(np.float64) + gb * v_dub
    pk = float(np.max(np.abs(mix))) or 1.0
    mix = mix / pk * 0.89
    raw = os.path.join(OUT, f"mix_{LANG}.wav")
    sf.write(raw, mix.astype(np.float32), SRM)
    fin = os.path.join(OUT, f"dub_{LANG}.wav")
    I0, I1 = normalize(raw, fin)
    os.remove(raw)
    D.log(f"громкость {I0} → {I1} LUFS; длина {n / SRM:.1f} с (русская {len(full) / SRM:.1f} с)")

    ok = [r for r in rows if "clear" in r]
    report = {"build": NAME, "lang": LANG, "fit": round(fit, 4), "gain_music": round(float(ga), 4), "gain_voice": round(float(gb), 4),
              "lufs": I1, "dur": round(n / SRM, 2), "lines": len(rows), "done": len(ok),
              "clear_avg": round(float(np.mean([r["clear"] for r in ok])), 1) if ok else None,
              "low": [r["i"] for r in ok if r["clear"] < 80 or r["extra"] > 1],
              "stretched": [r["i"] for r in ok if r["tempo"] > 1.15], "over": [r["i"] for r in ok if r["over"] > 0.1],
              "minutes": round((time.time() - t_start) / 60, 1),
              "syl_ru": round(float(np.median([r["syl_ru"] for r in ok])), 1) if ok else None,
              "syl": round(float(np.median([r["syl"] for r in ok])), 1) if ok else None,
              "len_ratio": round(float(np.median([r["sec"] / max(0.3, r["ru_sec"]) for r in ok])), 2) if ok else None,
              "fast": [r["i"] for r in ok if r["speed"] > 1.25], "rows": rows}
    json.dump(report, open(os.path.join(OUT, f"report_{LANG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = [f"# Дубляж {NAME} → {LANG}", "",
          f"Реплик {report['lines']}, озвучено {report['done']}, понято в среднем {report['clear_avg']}%; "
          f"плохо понятых {len(report['low'])}: {report['low']}; ускорено больше ×1,15: {report['stretched']}; "
          f"вылезли за окно: {report['over']}. Сведение совпало с русским на {fit:.3f}. Громкость {I1} LUFS. {report['minutes']} мин.", "",
          f"Темп: по-русски {report['syl_ru']} слог/с, здесь {report['syl']} слог/с; реплика длиннее русской в {report['len_ratio']} раза (медиана). "
          f"Пришлось ускорять голос больше ×1,25 (перевод длинноват — сократить): {report['fast']}.", "",
          "| № | Герой | Русский | Перевод | Понято | Лишних | Скорость голоса | Растяжка | Сек (рус) | Услышано |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['i']} | {r['name']} | {r['ru']} | {r.get('text') or ''} | {r.get('clear', r.get('error', ''))} | "
                  f"{r.get('extra', '')} | {r.get('speed', '')} | {r.get('tempo', '')} | {r.get('sec', '')} ({r.get('ru_sec', '')}) | {r.get('heard', '')} |")
    open(os.path.join(OUT, f"report_{LANG}.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    D.log("готово", report["minutes"], "мин")


if __name__ == "__main__":
    main()

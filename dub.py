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


def _words(t):
    # латиница: «averigüemos» = «averiguemos», «adónde» = «a dónde» — это не ошибка голоса, а запись распознавателя
    import re, unicodedata
    t = t.lower()
    if all(ord(c) < 0x250 or not c.isalpha() for c in t):
        t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
        t = re.sub(r"\ba donde\b", "adonde", t)
    return re.findall(r"\w+", t)


D.words = _words                  # D.clear_pct берёт words из модуля dubcore

NAME, LANG = sys.argv[1], sys.argv[2]
# Долгие языки (арабский — весь через Chatterbox Multilingual, на процессоре минуты на реплику): «part=k/N» — озвучить только свою
# долю реплик и сохранить; «merge» — собрать доли и свести. Без третьего слова — как раньше, всё одним заданием.
MODE = sys.argv[3] if len(sys.argv) > 3 else ""
PART = tuple(int(x) for x in MODE[5:].split("/")) if MODE.startswith("part=") else None
# Пробы (26.11): DUB_TAG — суффикс файлов (report_ar<тег>, parts_ar<тег>, dub_ar<тег>), чтобы не затереть основную дорожку;
# DUB_TKEY — какой ключ перевода брать (например ar_v2); DUB_SRC — другой источник голоса для языка (silma).
TAG = os.environ.get("DUB_TAG", "")
TKEY = os.environ.get("DUB_TKEY") or None
SRC_PRESET = {"silma": {"engine": "silma", "nfe": 32}}
LT = LANG + TAG
SRM = 44100                       # частота сведения студии
OUT = os.path.join("out_dub", NAME)
os.makedirs(OUT, exist_ok=True)
G = json.load(open("geroi.json", encoding="utf-8"))
LENK = float(os.environ.get("DUB_LENK") or G.get("len_k_lang", {}).get(LANG, 1.0))
# 27.11.2026 (Михаил: «да»): каждую реплику озвучивать в TAKES дублях (перекраска каждый раз звучит по-своему: одна реплика 3,2…4,2 UTMOS)
# и брать самый естественный из разборчивых. Если задание идёт дольше BUDGET минут — дальше по одному дублю (лимит задания 330 мин).
_TK = G.get("takes", {})
TAKES = int(os.environ.get("DUB_TAKES") or _TK.get(LANG, _TK.get("default", 1)))
BUDGET = float(os.environ.get("DUB_BUDGET_MIN") or _TK.get("budget_min", 200))
# 27.11.2026 (Михаил: «да, не много»): вопрос «да/нет» — подъём в конце на QRISE полутонов (в этих языках такой вопрос идёт вверх)
QRISE = float(os.environ.get("DUB_QRISE") or G.get("qrise", {}).get(LANG, 0) or 0)
WH = {"en": r"^(what|where|who|whom|whose|why|how|when|which)\b", "de": r"^(was|wo|wer|wen|wem|wessen|warum|wieso|weshalb|wie|wann|welche[rsmn]?|woher|wohin)\b",
      "es": r"^(qué|dónde|quién|quiénes|por qué|cómo|cuándo|cuál|cuánto|adónde)\b", "pt": r"^(o que|que|onde|quem|por que|porque|como|quando|qual|quanto)\b",
      "fr": r"^(qu[e']|quoi|où|qui|pourquoi|comment|quand|quel|combien)"}


def yesno(text):
    """Вопрос «да/нет»: последняя фраза кончается «?» и не начинается с вопросительного слова (с «и/а/но» в начале — тоже)."""
    import re
    t = text.strip().rstrip("!").rstrip()
    if not t.endswith("?") or LANG not in WH:
        return False
    last = re.split(r"(?<=[.!?])\s+", t)[-1].lower().strip("¿¡ ")
    last = re.sub(r"^(and|but|so|und|aber|y|pero|e|mas|et|mais)\s+", "", last)
    return not re.search(WH[LANG], last)
if os.environ.get("DUB_SRC"):
    G["src"][LANG] = dict(SRC_PRESET.get(os.environ["DUB_SRC"]) or json.loads(os.environ["DUB_SRC"]))
    for _h in G["heroes"].values():
        (_h.get("src") or {}).pop(LANG, None)


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
    rn = G.get("rename", {}).get(NAME) or {}   # серии из телефона (dubsrc.py): кластер голоса S1…Sk → имя героя; «-» — не переводить (песня, шум)
    for ln in L["lines"]:
        if rn.get(ln["name"]) == "-":
            ln["vocal"] = True
        ln["name"] = rn.get(ln["name"], ln["name"]) if rn.get(ln["name"]) != "-" else ln["name"]
    ep = G.get("builds", {}).get(NAME, NAME)
    P = json.load(open(f"perevod/{ep}.json", encoding="utf-8"))
    T = P[TKEY or LANG]
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
    nv = -1
    for k, ln in enumerate(L["lines"]):
        if ln["vocal"] or MODE == "merge":
            continue
        nv += 1
        if PART and nv % PART[1] != PART[0]:
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
        # длина русской реплики (и не дальше следующей); LENK — языку можно чуть длиннее русской, в паузу (хинди 26.11: голос медленный,
        # реплики ускорялись до ×1,45 — речь «торопится»)
        target = min(window, max(ln["bdur"], 0.4) * hero.get("len_k", 1.0) * LENK)
        best, good, failed = None, [], 0
        n_takes = TAKES if (time.time() - t_start) / 60 < BUDGET else 1
        for attempt in range(3 + n_takes - 1):
            try:
                tgt = target if not failed else min(window, target * 1.3)   # после неразборчивой попытки — можно чуть длиннее (в паузу)
                a, info, used, ratio = render_fit(text, spec, refs[name], f0s[name], pre, tgt)
                heard = D.heard(a, LANG, G.get("whisper_lang", {}).get(LANG, G.get("whisper", "small")))
                clear, extra = D.clear_pct(text, heard)
                if LANG in G.get("by_chars", []):       # хинди: написание слов «плавает» — считаем по буквам
                    clear, extra = D.char_pct(text, heard), 0
                cand = {"a": a, "heard": heard, "clear": clear, "extra": extra, "shift": info["shift_st"],
                        "speed": used.get("speed", 1.0), "ratio": round(ratio, 2), "tk": D.LAST.get("tk")}
                if LANG in G.get("by_chars", []):       # и по словам (без огласовок, алиф = алиф) — строже, для сравнения проб
                    cand["words"] = D.clear_pct(" ".join(D.norm_chars(w) for w in text.split()),
                                                " ".join(D.norm_chars(w) for w in heard.split()))[0]
                if best is None or (clear - 10 * extra) > (best["clear"] - 10 * best["extra"]):
                    best = cand
                if clear >= 85 and extra <= 1:
                    if n_takes > 1:
                        try:
                            cand["mos"] = D.utmos(a)
                        except Exception:
                            traceback.print_exc()
                            cand["mos"] = 0.0
                    good.append(cand)
                    if len(good) >= n_takes:
                        break
                    continue                          # следующий дубль — с теми же настройками
                failed += 1
                if failed >= 3:
                    break
                spec = with_speed(spec, 0.92)   # следующая попытка — медленнее (разборчивее)
            except Exception as ex:
                traceback.print_exc()
                row["error"] = f"{type(ex).__name__}: {ex}"[:200]
        if best is None:
            rows.append(row)
            continue
        if good:
            best = max(good, key=lambda c: c.get("mos", 0.0))   # из разборчивых — самый естественный
            if len(good) > 1:
                row["takes"] = [c.get("mos") for c in good]
        a = best["a"]
        if QRISE and yesno(text):
            try:
                a = D.qrise(a, QRISE)
                row["qrise"] = QRISE
            except Exception:
                traceback.print_exc()
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
        if best.get("words") is not None:
            row["words"] = best["words"]
        if best.get("tk"):
            row["tk"] = best["tk"]
        if best.get("mos") is not None:
            row["mos"] = best["mos"]
        row.update(heard=best["heard"], clear=best["clear"], extra=best["extra"], shift=best["shift"],
                   speed=best["speed"], tempo=round(max(1.0, k_t), 2), over=round(max(0.0, len(a) / SRM - window), 2),
                   sec=round(len(a) / SRM, 2), window=round(window, 2), ru_sec=round(ln["bdur"], 2),
                   syl_ru=round(syllables(ln["text"]) / max(0.3, ln["bdur"]), 1),
                   syl=round(syllables(text) / max(0.3, len(a) / SRM), 1))
        rows.append(row)
        D.log(f"{i:3d} {name:7s} понято {best['clear']:5.1f}% лишних {best['extra']} темп ×{row['tempo']} | {text}")

    pdir = os.path.join(OUT, f"parts_{LT}")
    if PART:
        os.makedirs(pdir, exist_ok=True)
        np.savez_compressed(os.path.join(pdir, f"p{PART[0]}.npz"), **{str(i): np.asarray(a, dtype=np.float32) for i, a in dub.items()})
        json.dump({"rows": rows, "minutes": round((time.time() - t_start) / 60, 1)}, open(os.path.join(pdir, f"p{PART[0]}.json"), "w", encoding="utf-8"), ensure_ascii=False)
        D.log("доля готова", PART, "реплик", len(rows), "мин", round((time.time() - t_start) / 60, 1))
        return
    if MODE == "merge" and os.environ.get("DUB_BEST"):
        # «Лучшее из проходов» (26.11): доли нескольких прогонов (папки через запятую) — по каждой реплике берётся та озвучка,
        # которую распознаватель понял лучше (меньше лишних слов, не за окном). Голос случаен от прогона к прогону: ±10–60 % на реплике.
        import glob
        mins, cand = 0.0, {}
        for d in [x for x in os.environ["DUB_BEST"].split(",") if x]:
            for f in sorted(glob.glob(os.path.join(d, "**", "p*.json"), recursive=True)):
                J = json.load(open(f, encoding="utf-8")); mins = max(mins, J.get("minutes", 0))
                z = np.load(f[:-5] + ".npz")
                for r in J["rows"]:
                    if "clear" not in r or str(r["i"]) not in z.files:
                        continue
                    sc = r["clear"] - 10 * r.get("extra", 0) - 150 * max(0.0, r.get("over", 0.0) - 0.05)   # 27.11: −30/с проигрывал короткой реплике (одно слово распознаётся хуже) — за окном 0,2–0,3 с оставалось
                    if r["i"] not in cand or sc > cand[r["i"]][0]:
                        cand[r["i"]] = (sc, dict(r, pick=d.rstrip("/").split("/")[-1]), z[str(r["i"])])
        rows = sorted((c[1] for c in cand.values()), key=lambda r: r["i"])
        dub = {i: c[2] for i, c in cand.items()}
        t_start -= mins * 60
        from collections import Counter
        D.log("лучшее из проходов: реплик", len(rows), "откуда:", dict(Counter(r["pick"] for r in rows)))
    elif MODE == "merge":
        import glob
        mins = 0.0
        for f in sorted(glob.glob(os.path.join(pdir, "p*.json"))):
            J = json.load(open(f, encoding="utf-8")); rows += J["rows"]; mins = max(mins, J.get("minutes", 0))
        for f in sorted(glob.glob(os.path.join(pdir, "p*.npz"))):
            z = np.load(f)
            dub.update({int(k_): z[k_] for k_ in z.files})
        rows.sort(key=lambda r: r["i"])
        t_start -= mins * 60          # в отчёте — время самой долгой доли
        D.log("доли собраны: реплик", len(rows), "звук у", len(dub))

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
    raw = os.path.join(OUT, f"mix_{LT}.wav")
    sf.write(raw, mix.astype(np.float32), SRM)
    fin = os.path.join(OUT, f"dub_{LT}.wav")
    I0, I1 = normalize(raw, fin)
    os.remove(raw)
    D.log(f"громкость {I0} → {I1} LUFS; длина {n / SRM:.1f} с (русская {len(full) / SRM:.1f} с)")

    ok = [r for r in rows if "clear" in r]
    report = {"build": NAME, "lang": LANG, "tag": TAG, "lenk": LENK, "tkey": TKEY or LANG, "src": G["src"][LANG], "fit": round(fit, 4), "gain_music": round(float(ga), 4), "gain_voice": round(float(gb), 4),
              "lufs": I1, "dur": round(n / SRM, 2), "lines": len(rows), "done": len(ok),
              "clear_avg": round(float(np.mean([r["clear"] for r in ok])), 1) if ok else None,
              "low": [r["i"] for r in ok if r["clear"] < 80 or r["extra"] > 1],
              "stretched": [r["i"] for r in ok if r["tempo"] > 1.15], "over": [r["i"] for r in ok if r["over"] > 0.1],
              "minutes": round((time.time() - t_start) / 60, 1),
              "syl_ru": round(float(np.median([r["syl_ru"] for r in ok])), 1) if ok else None,
              "syl": round(float(np.median([r["syl"] for r in ok])), 1) if ok else None,
              "len_ratio": round(float(np.median([r["sec"] / max(0.3, r["ru_sec"]) for r in ok])), 2) if ok else None,
              "fast": [r["i"] for r in ok if r["speed"] > 1.25], "rows": rows,
              "mos_avg": round(float(np.mean([r["mos"] for r in ok if r.get("mos")])), 2) if any(r.get("mos") for r in ok) else None,
              "takes": TAKES, "qrise": QRISE, "q_rise": [r["i"] for r in ok if r.get("qrise")]}
    if any("pick" in r for r in ok):
        from collections import Counter
        report["picks"] = dict(Counter(r.get("pick") for r in ok))
    if any("words" in r for r in ok):
        report["words_avg"] = round(float(np.mean([r.get("words", 0) for r in ok])), 1)
    json.dump(report, open(os.path.join(OUT, f"report_{LT}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = [f"# Дубляж {NAME} → {LT}", "",
          f"Реплик {report['lines']}, озвучено {report['done']}, понято в среднем {report['clear_avg']}%; "
          f"плохо понятых {len(report['low'])}: {report['low']}; ускорено больше ×1,15: {report['stretched']}; "
          f"вылезли за окно: {report['over']}. Сведение совпало с русским на {fit:.3f}. Громкость {I1} LUFS. {report['minutes']} мин.", "",
          f"Дублей на реплику: {report['takes']}; естественность выбранных (UTMOS): {report['mos_avg']}. Подъём вопросов +{report['qrise']} пт: {report['q_rise']}.", "",
          f"Темп: по-русски {report['syl_ru']} слог/с, здесь {report['syl']} слог/с; реплика длиннее русской в {report['len_ratio']} раза (медиана). "
          f"Пришлось ускорять голос больше ×1,25 (перевод длинноват — сократить): {report['fast']}.", "",
          "| № | Герой | Русский | Перевод | Понято | Лишних | Скорость голоса | Растяжка | Сек (рус) | Услышано |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['i']} | {r['name']} | {r['ru']} | {r.get('text') or ''} | {r.get('clear', r.get('error', ''))} | "
                  f"{r.get('extra', '')} | {r.get('speed', '')} | {r.get('tempo', '')} | {r.get('sec', '')} ({r.get('ru_sec', '')}) | {r.get('heard', '')} |")
    open(os.path.join(OUT, f"report_{LT}.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    D.log("готово", report["minutes"], "мин")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Свой «сборный» голос (23.11.2026, просьба Михаила: взять у всех лучшее — интонации, ударения, звуки — и сделать один голос).

У каждого диктора модели Silero v5 CIS (лицензия MIT) три строки-отпечатка:
  dp  — длительности: ритм, паузы, темп, длина ударного слога;
  pp  — высота: мелодия, интонация, выделение ударения голосом;
  spe — основная: тембр и звуки.
Берём каждую часть у того, у кого она лучше, вписываем на место неиспользуемого диктора — получается один новый голос,
который работает везде, где уже работает модель (бот «Почему так?», ферма, телефон), как ru_nash3.

  python svoy.py genA <part> <n>   кастинг: каждый русский диктор (и наши ru_nash1–3) читает тестовые фразы
  python svoy.py pack <tag>        сложить анализ и звук в pack/
  python svoy.py rank              по кастингу выбрать кандидатов на каждую часть → pack/combos.json
  python svoy.py genB <part> <n>   озвучить сборные голоса
  python svoy.py final             итог: cast/itog.md, cast/golosa.json (формат voices.json), cast/proba.mp4
"""
import glob, json, os, re, shutil, subprocess, sys
import numpy as np

# (текст, слушать ли в итоговом ролике)
PHRASES = [
    ("Почему у жирафа такая длинная шея?", True),
    ("Оказывается, верблюд хранит в горбу не воду, а жир.", False),
    ("Сердце синего кита весит около шестисот килограммов.", True),
    ("Летучие мыши совсем не слепые, они отлично видят в сумерках.", False),
    ("Этот мост строили почти пять тысяч дней, и он до сих пор стоит.", False),
    ("Ты видел снег в пустыне?", True),
    ("Жил на свете кот Барсик, и однажды утром он нашёл в саду странный зелёный камень.", True),
    ("Ого! Какая огромная лужа!", False),
    ("Первый орёл, второй беркут, третий сокол.", False),
    ("Учёные до сих пор спорят, зачем зебре полоски.", False),
]
# служебные слова из одного слога — без ударения (как в режиме bot «Почему так?»)
CLIT = set("в во на не ни и а но же ж бы б ли ль с со к ко у о об от до по за из без над под при про что то уж".split())
SLOT = "bak_miyau"           # неиспользуемый диктор, на его место вписываем голос (как в nash_voices.py)
BASE = {"m": "ru_nash3", "f": "ru_albina"}   # голоса, которые сейчас стоят: мужской в «Почему так?», рассказчица мультика
SOFT = ("highpass=f=70,bass=g=2.5:f=160:w=0.7,equalizer=f=3200:t=q:w=1.0:g=-2.5,deesser=i=0.35,"
        "acompressor=threshold=-22dB:ratio=2.2:attack=12:release=220:makeup=1.5,"
        "aecho=0.85:0.6:28|47:0.08|0.05,loudnorm=I=-16:TP=-1.5:LRA=9")
TKEYS = {"dp": "dp.spe.weight", "pp": "pp.spe.weight", "spe": "spe.weight"}


def log(*a):
    print(*a, flush=True)


# ---------------- модель ----------------
class Model:
    def __init__(self):
        import torch, gen
        self.torch = torch
        self.m = gen.silero_model("v5_cis_base")
        pack = self.m.packages[0]
        jm = pack.models[0]
        self.ids = pack.speaker_to_ids[0]
        self.T = {"dp": jm.dur_predictor.dur_pred.speaker_embedding.weight,
                  "pp": jm.pitch_predictor.pitch_pred.speaker_embedding.weight,
                  "spe": jm.tacotron.speaker_embedding.weight}
        self.coef = getattr(jm, "mean_std_coef", None)
        n = len(self.ids)
        log("дикторов в модели:", n, "| mean_std_coef:", type(self.coef).__name__,
            getattr(self.coef, "shape", None) if self.coef is not None else None)
        try:   # разведка: нет ли ещё таблиц по дикторам, кроме трёх известных
            for name, p in list(jm.named_parameters()) + list(jm.named_buffers()):
                if p.dim() >= 1 and p.shape[0] == n:
                    log("  по дикторам:", name, tuple(p.shape))
        except Exception as e:
            log("  разведка не удалась:", repr(e))
        self.orig = {s: self._read(i) for s, i in self.ids.items()}   # строки до любых правок
        V = json.load(open("voices.json", encoding="utf-8"))
        for name, v in V["voices"].items():
            self.orig[name] = {k: torch.tensor(v["rows"][TKEYS[k]]) for k in TKEYS}
            self.orig[name]["coef"] = v.get("coef")
        self.fingerprint = V.get("fingerprint")

    def _read(self, i):
        r = {k: t[i].detach().clone() for k, t in self.T.items()}
        try:
            r["coef"] = float(self.coef[i])
        except Exception:
            r["coef"] = None
        return r

    def russian(self):
        return sorted(s for s in self.ids if s.startswith("ru_")) + ["ru_nash1", "ru_nash2", "ru_nash3"]

    def put(self, rec):
        sid = self.ids[SLOT]
        with self.torch.no_grad():
            for k, t in self.T.items():
                t[sid].copy_(rec[k])
            if self.coef is not None and rec.get("coef") is not None:
                try:
                    self.coef[sid] = rec["coef"]
                except Exception as e:
                    log("высоту (coef) не поправил:", repr(e))

    def say(self, rec, text, path):
        import gen
        self.put(rec)
        a = self.m.apply_tts(text=mark(text), speaker=SLOT, sample_rate=48000)
        gen.save_wav(a.numpy() if hasattr(a, "numpy") else a, path)


def mark(text):
    """Ударения «+» во всех словах, кроме служебных из одного слога (словарь ruaccent, как в gen.py)."""
    import voice_check as vc
    ws = vc.tokenize(text)
    vc.accentize(text, ws)
    out = []
    for w in ws:
        e = w["exp"]
        if len(w["vows"]) == 1 and w["w"].lower() not in CLIT:
            e = 0
        if e is None or (len(w["vows"]) == 1 and w["w"].lower() in CLIT):
            out.append(w["w"] + w["punct"]); continue
        k = -1; t2 = ""
        for c in w["w"]:
            if c.lower() in vc.VOW:
                k += 1
                if k == e:
                    t2 += "+"
            t2 += c
        out.append(t2 + w["punct"])
    return " ".join(out)


def fresh():
    for d in ("in", "out"):
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d)


def write_take(M, rec, voice, tag, text, k):
    name = f"{tag}__{k:02d}"
    M.say(rec, text, f"in/{name}.wav")
    open(f"in/{name}.txt", "w", encoding="utf-8").write(text + "\n")
    open(f"in/{name}.voice", "w", encoding="utf-8").write(voice + "\n")


# ---------------- шаги ----------------
def genA(part, n):
    fresh()
    M = Model()
    spk = M.russian()
    log("русских дикторов (с нашими):", len(spk), spk)
    json.dump(spk, open("in/_speakers.json", "w"))
    for s in spk[part::n]:
        for k, (t, _) in enumerate(PHRASES):
            try:
                write_take(M, M.orig[s], f"cast:{s}", f"A__{s}", t, k)
            except Exception as e:
                log("ошибка", s, k, repr(e))
        log("озвучен", s)
    log("пример разметки:", mark(PHRASES[6][0]))


def pack():
    os.makedirs("pack", exist_ok=True)
    for j in glob.glob("out/*__*.json"):
        shutil.copy(j, "pack/")
    for w in glob.glob("in/*__*.wav"):
        b = os.path.basename(w)[:-4]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", w, f"pack/{b}.flac"], check=True)
    for f in glob.glob("in/_rows_*.json") + glob.glob("in/_speakers.json"):
        shutil.copy(f, "pack/")
    log("сложено:", len(os.listdir("pack")))


def load_reps():
    R = {}
    for j in glob.glob("pack/*__*.json"):
        try:
            r = json.load(open(j, encoding="utf-8"))
        except Exception:
            continue
        who = os.path.basename(j).rsplit("__", 1)[0]
        R.setdefault(who, []).append(r)
    return R


def agg(reps):
    def mean(vals):
        vals = [v for v in vals if v is not None]
        return float(np.mean(vals)) if vals else None
    it = [s for r in reps for s in r.get("intonation", [])]
    f0 = [r.get("f0_median_hz") for r in reps if r.get("f0_median_hz")]
    return {
        "n": len(reps),
        "match": mean([r.get("match") for r in reps]),
        "utmos": mean([r.get("utmos") for r in reps]),
        "err": mean([r.get("stress_errors", 0) + 0.5 * r.get("stress_maybe", 0) for r in reps]),
        "inton": (sum(1 for s in it if s["ok"]) / len(it)) if it else None,
        "range": mean([r.get("f0_range") for r in reps]),
        "f0": float(np.median(f0)) if f0 else None,
        "rate": mean([r.get("rate") for r in reps]),
    }


def gender(a):
    f = a.get("f0") or 0
    return "m" if f < 165 else "f" if f < 255 else "child"


def score(a):
    """Общая оценка: разборчивость главнее всего, потом естественность, ударения, интонация, живость."""
    if not a or a.get("match") is None:
        return -99
    s = 4 * a["match"] + 0.8 * (a["utmos"] or 0) - 0.5 * (a["err"] or 0) + 1.0 * (a["inton"] or 0)
    s += 0.08 * min(a["range"] or 0, 9)
    r = a.get("rate") or 5
    s -= 0.5 * max(0, 4 - r, r - 6.5)
    return round(s, 3)


def rank():
    R = load_reps()
    A = {w[3:]: agg(r) for w, r in R.items() if w.startswith("A__")}
    for s, a in A.items():
        a["g"] = gender(a); a["score"] = score(a)
    combos = []
    lines = ["| диктор | пол | слова | UTMOS | ошибки удар. | интонация | диапазон | Гц | темп | оценка |", "|---|---|---|---|---|---|---|---|---|---|"]
    for s, a in sorted(A.items(), key=lambda x: -x[1]["score"]):
        lines.append(f"| {s} | {a['g']} | {a['match'] or 0:.3f} | {a['utmos'] or 0:.2f} | {a['err'] or 0:.2f} | "
                     f"{a['inton'] or 0:.2f} | {a['range'] or 0:.1f} | {a['f0'] or 0:.0f} | {a['rate'] or 0:.1f} | {a['score']} |")
    for g in ("m", "f"):
        pool = {s: a for s, a in A.items() if a["g"] == g and a.get("match") is not None}
        if not pool:
            continue
        kdp = lambda s: 10 * pool[s]["match"] - (pool[s]["err"] or 0) + 0.1 * (pool[s]["utmos"] or 0)
        kpp = lambda s: -(pool[s]["err"] or 0) + 2 * (pool[s]["inton"] or 0) + 0.15 * min(pool[s]["range"] or 0, 9) + 0.5 * pool[s]["match"]
        dp = sorted(pool, key=kdp, reverse=True)[:3]
        pp = sorted(pool, key=kpp, reverse=True)[:3]
        base = BASE[g] if BASE[g] in pool else max(pool, key=lambda s: pool[s]["utmos"] or 0)
        spe = [base] + [s for s in sorted(pool, key=lambda s: -(pool[s]["utmos"] or 0)) if s != base][:1]
        log(g, "ритм (dp):", dp, "| мелодия (pp):", pp, "| тембр (spe):", spe)
        i = 0
        for t in spe:
            for d in dp:
                for p in pp:
                    i += 1
                    combos.append({"name": f"{g}{i:02d}", "g": g, "dp": d, "pp": p, "spe": t})
    json.dump({"combos": combos, "cast": A, "table": lines}, open("pack/combos.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log("\n".join(lines))
    log("сборных голосов:", len(combos))


def genB(part, n):
    fresh()
    M = Model()
    C = json.load(open("pack/combos.json", encoding="utf-8"))["combos"]
    for c in C[part::n]:
        rec = {"dp": M.orig[c["dp"]]["dp"], "pp": M.orig[c["pp"]]["pp"], "spe": M.orig[c["spe"]]["spe"],
               "coef": M.orig[c["pp"]]["coef"]}
        voice = f"mix:{c['name']} dp={c['dp']} pp={c['pp']} spe={c['spe']}"
        for k, (t, _) in enumerate(PHRASES):
            try:
                write_take(M, rec, voice, f"B__{c['name']}", t, k)
            except Exception as e:
                log("ошибка", c["name"], k, repr(e))
        json.dump({"recipe": c, "coef": rec["coef"],
                   "rows": {TKEYS[k]: [round(float(x), 6) for x in rec[k].tolist()] for k in TKEYS}},
                  open(f"in/_rows_{c['name']}.json", "w"))
        log("озвучен", voice)


def final():
    os.makedirs("cast", exist_ok=True)
    R = load_reps()
    J = json.load(open("pack/combos.json", encoding="utf-8"))
    A = J["cast"]
    B = {}
    for c in J["combos"]:
        r = R.get("B__" + c["name"])
        if r:
            a = agg(r); a.update(c); a["score"] = score(a); B[c["name"]] = a
    L = ["# Свой сборный голос — итог кастинга", "",
         "Каждая часть голоса — у того диктора модели Silero v5 CIS (MIT), у кого она лучше: ритм (dp), мелодия (pp), тембр (spe).",
         "Оценка = 4·слова + 0,8·UTMOS − 0,5·ошибки ударений + интонация + живость (диапазон) − штраф за темп вне 4–6,5.", "",
         "## Сборные голоса", "",
         "| голос | пол | ритм от | мелодия от | тембр от | слова | UTMOS | ошибки удар. | интонация | диапазон | Гц | темп | оценка |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for nm, a in sorted(B.items(), key=lambda x: -x[1]["score"]):
        L.append(f"| {nm} | {a['g']} | {a['dp']} | {a['pp']} | {a['spe']} | {a['match'] or 0:.3f} | {a['utmos'] or 0:.2f} | "
                 f"{a['err'] or 0:.2f} | {a['inton'] or 0:.2f} | {a['range'] or 0:.1f} | {a['f0'] or 0:.0f} | {a['rate'] or 0:.1f} | {a['score']} |")
    L += ["", "## Кастинг: каждый диктор целиком", ""] + J["table"]
    # лучшие сборные против нынешних
    pick, golosa = [], {}
    for g in ("m", "f"):
        base = BASE[g]
        bs = A.get(base, {}).get("score", -99)
        top = [nm for nm, a in sorted(B.items(), key=lambda x: -x[1]["score"]) if a["g"] == g
               and not (a["dp"] == a["pp"] == a["spe"])][:2]
        if base in A:
            pick.append((f"Сейчас: {'наш мужской (nash3)' if g == 'm' else 'Альбина'}", f"A__{base}", None))
        L += ["", f"**{'Мужской' if g == 'm' else 'Женский'}:** сейчас {base} — оценка {bs}; лучшие сборные: " +
              ", ".join(f"{nm} ({B[nm]['score']})" for nm in top)]
        for i, nm in enumerate(top, 1):
            a = B[nm]
            pick.append((f"{'Сборный мужской' if g == 'm' else 'Сборная женская'} {i}",
                         f"B__{nm}", f"ритм {a['dp'][3:]}, мелодия {a['pp'][3:]}, тембр {a['spe'][3:]}"))
            rf = f"pack/_rows_{nm}.json"
            if os.path.exists(rf):
                rw = json.load(open(rf))
                golosa[f"ru_sbor_{g}{i}"] = {"desc": f"сборный: ритм {a['dp']}, мелодия {a['pp']}, тембр {a['spe']}",
                                             "recipe": rw["recipe"], "coef": rw["coef"], "rows": rw["rows"],
                                             "score": a["score"]}
    V = json.load(open("voices.json", encoding="utf-8"))
    json.dump({"model": V.get("model"), "made": "2026-11-23", "how": "сборные голоса: строки dp/pp/spe от разных дикторов",
               "fingerprint": V.get("fingerprint"), "voices": golosa},
              open("cast/golosa.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({"cast": A, "mix": B}, open("cast/kasting.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L += ["", "## В ролике proba.mp4 по порядку", ""] + [f"{i}. {p[0]}" + (f" — {p[2]}" if p[2] else "") for i, p in enumerate(pick, 1)]
    open("cast/itog.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    log("\n".join(L))
    # ролик для прослушки: на экране номер и что за голос, звук — 4 фразы подряд, мягкая обработка у всех одинаковая
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    os.makedirs("tmp", exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.7",
                    "-c:a", "pcm_s16le", "tmp/sil.wav"], check=True)
    parts = []
    for i, (title, tag, sub) in enumerate(pick, 1):
        fl = [f"pack/{tag}__{k:02d}.flac" for k, (_, lis) in enumerate(PHRASES) if lis]
        fl = [f for f in fl if os.path.exists(f)]
        if not fl:
            continue
        seq = ["tmp/sil.wav"]
        for f in fl:
            seq += [f, "tmp/sil.wav"]
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for f in seq:
            cmd += ["-i", f]
        fc = "".join(f"[{j}:a]aresample=48000,aformat=channel_layouts=mono[x{j}];" for j in range(len(seq)))
        fc += "".join(f"[x{j}]" for j in range(len(seq))) + f"concat=n={len(seq)}:v=0:a=1,{SOFT}[o]"
        subprocess.run(cmd + ["-filter_complex", fc, "-map", "[o]", "-ar", "48000", "-ac", "1", f"tmp/a{i}.wav"], check=True)
        open(f"tmp/t{i}.txt", "w", encoding="utf-8").write(f"{i}. {title}")
        open(f"tmp/s{i}.txt", "w", encoding="utf-8").write(sub or " ")
        vf = (f"drawtext=fontfile={font}:textfile=tmp/t{i}.txt:fontsize=46:fontcolor=white:x=(w-text_w)/2:y=h/2-80,"
              f"drawtext=fontfile={font}:textfile=tmp/s{i}.txt:fontsize=30:fontcolor=0xbbbbbb:x=(w-text_w)/2:y=h/2+10")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x1e2230:s=1080x1080:r=25",
                        "-i", f"tmp/a{i}.wav", "-vf", vf, "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-tune", "stillimage", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", f"tmp/v{i}.mp4"], check=True)
        parts.append(f"tmp/v{i}.mp4")
    if parts:
        with open("tmp/all.txt", "w") as fh:
            for p in parts:
                fh.write(f"file '../{p}'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "tmp/all.txt", "-c", "copy",
                        "cast/proba.mp4"], check=True)
        log("ролик:", os.path.getsize("cast/proba.mp4"), "байт")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "genA":
        genA(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "genB":
        genB(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == "pack":
        pack()
    elif cmd == "rank":
        rank()
    elif cmd == "final":
        final()

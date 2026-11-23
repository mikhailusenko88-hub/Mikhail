#!/usr/bin/env python3
"""Свой голос, круг 2 (23.11.2026). Михаил выбрал основу — №3 из пробы (ритм Марата, мелодия nash3, тембр nash2),
но «не очень качественно», надо «из всех собрать самый приятный», а у кота Барсика некоторые слова звучат лучше всех.

Две дорожки:
  cis  — модель Silero v5 CIS (MIT): каждая часть голоса (ритм dp, мелодия pp, тембр spe) — смесь строк многих дикторов
         с долями; поиск долей, при которых голос естественнее и разборчивее (UTMOS + распознаватель), от №3;
  bars — модель Барсика (Silero v5_ru, голоса aidar, baya, kseniya, xenia, eugene; лицензия CC BY-NC): манера xenia
         (ритм, мелодия) с мужским тембром aidar / eugene. Сама ставит ударения и омографы.

  python svoy2.py gen1 <part> <n>    круг 1: кандидаты, быстрая оценка → pack/
  python svoy2.py pick               лучшие → кандидаты круга 2 → pack/round2.json
  python svoy2.py gen2 <part> <n>    круг 2
  python svoy2.py finpick            финалисты → pack/finalists.json
  python svoy2.py fin <i>            финалист i: полная озвучка для voice_check.py
  python svoy2.py pack               сложить
  python svoy2.py final              cast2/itog.md, cast2/golosa2.json, cast2/proba2.mp4
"""
import difflib, glob, json, os, random, shutil, subprocess, sys
import numpy as np
import svoy

PHRASES = svoy.PHRASES + [
    ("На двери висел тяжёлый замок, а за рекой стоял старый замок.", True),
    ("Все пришли вовремя, и всё было готово.", False),
]
CIS, RU = "v5_cis_base", "v5_6_ru"
SLOT = {CIS: "bak_miyau", RU: "baya"}
BASE3 = {"dp": {"ru_marat": 1.0}, "pp": {"ru_nash3": 1.0}, "spe": {"ru_nash2": 1.0}}   # №3 из пробы 23.11
NASH3 = {"dp": {"ru_nash3": 1.0}, "pp": {"ru_nash3": 1.0}, "spe": {"ru_nash3": 1.0}}   # сейчас в «Почему так?»
MALE = ["ru_nash1", "ru_nash2", "ru_nash3", "ru_bogdan", "ru_eduard", "ru_miyau", "ru_marat", "ru_kejilgan",
        "ru_roman", "ru_alexandr", "ru_safarhuja", "ru_dmitriy"]
ROLE_OF_NASH = {"dp": "dp.spe.weight", "pp": "pp.spe.weight", "spe": "spe.weight"}
log = svoy.log


def patch_ruaccent():
    """voice_check.accentize грузит словарь на каждую фразу (~9 с) — держим один экземпляр."""
    try:
        import ruaccent
    except Exception:
        return
    if getattr(ruaccent.RUAccent, "_cached", False):
        return
    real, hold = ruaccent.RUAccent, {}

    class Proxy:
        _cached = True

        def load(self, *a, **k):
            if "a" not in hold:
                r = real(); r.load(*a, **k); hold["a"] = r

        def process_all(self, t):
            return hold["a"].process_all(t)
    ruaccent.RUAccent = Proxy


class Net:
    def __init__(self, mid):
        import torch, gen
        self.torch, self.mid = torch, mid
        self.m = gen.silero_model(mid)
        try:
            pk = self.m.packages[0]
            self.ids = dict(pk.speaker_to_ids[0])
            jm = pk.models[0]
        except Exception:
            log("устройство модели", mid, type(self.m).__name__, [a for a in dir(self.m) if not a.startswith("__")][:60])
            raise
        n = len(self.ids)
        self.tabs = {}
        for name, p in list(jm.named_parameters()) + list(jm.named_buffers()):
            if "speaker" in name and p.dim() == 2 and p.shape[0] >= n:
                role = "dp" if "dur" in name else "pp" if "pitch" in name else "spe"
                self.tabs[name] = (role, p)
        self.coef = getattr(jm, "mean_std_coef", None)
        log(mid, "дикторов:", n, sorted(self.ids)[:8], "… таблицы:", {k: (r, tuple(t.shape)) for k, (r, t) in self.tabs.items()},
            "coef:", type(self.coef).__name__)
        self.rows = {s: self._read(i) for s, i in self.ids.items()}
        if mid == CIS:
            V = json.load(open("voices.json", encoding="utf-8"))
            by_role = {r: k for k, (r, _) in self.tabs.items()}
            for name, v in V["voices"].items():
                self.rows[name] = {by_role[r]: torch.tensor(v["rows"][ROLE_OF_NASH[r]]) for r in ROLE_OF_NASH}
                self.rows[name]["coef"] = v.get("coef")

    def _read(self, i):
        r = {k: t[i].detach().clone() for k, (_, t) in self.tabs.items()}
        try:
            r["coef"] = float(self.coef[i])
        except Exception:
            r["coef"] = None
        return r

    def build(self, w):
        """w = {"dp": {диктор: доля}, "pp": {...}, "spe": {...}} → строки таблиц; сила строки — как у взятых дикторов."""
        T = self.torch
        out = {}
        for k, (role, t) in self.tabs.items():
            ws = w[role]; tot = sum(ws.values())
            row = sum(self.rows[s][k] * (x / tot) for s, x in ws.items())
            norm = sum(float(self.rows[s][k].norm()) * (x / tot) for s, x in ws.items())
            out[k] = row * (norm / max(float(row.norm()), 1e-9))
        cs = [(self.rows[s]["coef"], x) for s, x in w["pp"].items()]
        out["coef"] = (sum(c * x for c, x in cs) / sum(x for _, x in cs)) if all(c is not None for c, _ in cs) else None
        return out

    def put(self, rows):
        sid = self.ids[SLOT[self.mid]]
        with self.torch.no_grad():
            for k, (_, t) in self.tabs.items():
                t[sid].copy_(rows[k])
            if self.coef is not None and rows.get("coef") is not None:
                try:
                    self.coef[sid] = rows["coef"]
                except Exception as e:
                    log("coef не поправил:", repr(e))

    def say(self, rows, text, path):
        import gen
        self.put(rows)
        sp = SLOT[self.mid]
        if self.mid == CIS:
            a = self.m.apply_tts(text=MARKS.get(text) or svoy.mark(text), speaker=sp, sample_rate=48000)
        else:
            try:
                a = self.m.apply_tts(text=text, speaker=sp, sample_rate=48000, put_accent=True, put_yo=True)
            except TypeError:
                a = self.m.apply_tts(text=text, speaker=sp, sample_rate=48000)
        gen.save_wav(a.numpy() if hasattr(a, "numpy") else a, path)


MARKS = {}


def prep_marks():
    patch_ruaccent()
    for t, _ in PHRASES:
        MARKS[t] = svoy.mark(t)
    log("разметка:", MARKS[PHRASES[-2][0]], "|", MARKS[PHRASES[-1][0]])


# ---------------- кандидаты ----------------
def jitter(w, pool, rng, keep=(0.45, 0.85), kmax=3):
    """Часть голоса: основа сохраняет долю keep, остальное — 1–kmax других дикторов из pool."""
    base = dict(w)
    others = [s for s in pool if s not in base]
    k = rng.randint(1, kmax)
    pick = rng.sample(others, min(k, len(others)))
    kb = rng.uniform(*keep)
    out = {s: x * kb / sum(base.values()) for s, x in base.items()}
    ds = np.random.default_rng(rng.randint(0, 10 ** 6)).dirichlet([1.0] * len(pick))
    for s, d in zip(pick, ds):
        out[s] = out.get(s, 0) + (1 - kb) * float(d)
    return {s: round(x, 3) for s, x in out.items() if x >= 0.01}


def round1():
    rng = random.Random(2311)
    cast = json.load(open("cast/kasting.json", encoding="utf-8"))["cast"]
    allsp = sorted(cast)                         # 32 русских диктора CIS вместе с nash1–3
    good = sorted(allsp, key=lambda s: -cast[s]["score"])[:16]
    C = [{"id": "c00", "track": "cis", "w": BASE3, "note": "№3 из пробы"},
         {"id": "c01", "track": "cis", "w": NASH3, "note": "сейчас в «Почему так?»"}]
    for i in range(2, 48):
        w = {r: dict(BASE3[r]) for r in BASE3}
        for r, pool, kmax in (("dp", good, 3), ("pp", good, 3), ("spe", MALE, 2)):
            if rng.random() < 0.75:
                w[r] = jitter(w[r], pool, rng, kmax=kmax)
        C.append({"id": f"c{i:02d}", "track": "cis", "w": w})
    B = [{"id": "b_xenia", "track": "bars", "w": {r: {"xenia": 1.0} for r in BASE3}, "note": "Барсик (xenia без подъёма)"},
         {"id": "b_aidar", "track": "bars", "w": {r: {"aidar": 1.0} for r in BASE3}},
         {"id": "b_eugene", "track": "bars", "w": {r: {"eugene": 1.0} for r in BASE3}}]
    i = 0
    for spe in ("aidar", "eugene"):
        for dp in ("xenia", "kseniya", spe):
            for pp in ({"xenia": 1.0}, {"xenia": 0.5, spe: 0.5}):
                i += 1
                B.append({"id": f"b{i:02d}", "track": "bars", "w": {"dp": {dp: 1.0}, "pp": dict(pp), "spe": {spe: 1.0}}})
    return C + B


def light(path, text):
    import torch, voice_check as vc
    a = vc.load16(path)
    with torch.no_grad():
        ut = float(vc.utmos_model()(torch.from_numpy(a)[None], vc.SR))
    heard = vc.whisper_model().transcribe(path, language="ru", fp16=False)["text"]
    match = difflib.SequenceMatcher(None, vc.norm_words(text), vc.norm_words(heard)).ratio()
    P = vc.prosody(a)
    fv = P[2][P[2] > 0]
    rng_ = float(np.percentile([vc.st(x) for x in fv], 95) - np.percentile([vc.st(x) for x in fv], 5)) if len(fv) > 10 else 0
    fr = a[: len(a) // 320 * 320].reshape(-1, 320)
    rms = np.sqrt((fr ** 2).mean(1) + 1e-12)
    act = (rms > rms.max() * 10 ** (-35 / 20)).sum() * 0.02
    nv = sum(1 for c in text.lower() if c in "аеёиоуыэюя")
    return {"utmos": round(ut, 3), "match": round(match, 3), "range": round(rng_, 2),
            "f0": float(np.median(fv)) if len(fv) else 0, "rate": round(nv / max(act, 0.1), 2), "heard": heard}


def J(r):
    s = 4 * r["match"] + r["utmos"] + 0.3 * r["utmos_min"] + 0.08 * min(r["range"], 9)
    s -= 0.4 * max(0, 4.3 - r["rate"], r["rate"] - 6.8)
    return round(s, 3)


def evaluate(cands, tag):
    shutil.rmtree("in", ignore_errors=True); os.makedirs("in"); os.makedirs("pack", exist_ok=True)
    prep_marks()
    nets = {}
    for c in cands:
        mid = CIS if c["track"] == "cis" else RU
        try:
            if mid not in nets:
                nets[mid] = Net(mid)
            net = nets[mid]
            rows = net.build(c["w"])
            res = []
            for k, (t, lis) in enumerate(PHRASES):
                p = f"in/{c['id']}__{k:02d}.wav"
                net.say(rows, t, p)
                res.append(light(p, t))
                if lis:
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, f"pack/{c['id']}__{k:02d}.flac"], check=True)
            agg = {x: round(float(np.mean([r[x] for r in res])), 3) for x in ("utmos", "match", "range", "f0", "rate")}
            agg["utmos_min"] = round(min(r["utmos"] for r in res), 3)
            agg.update(id=c["id"], track=c["track"], w=c["w"], note=c.get("note", ""), J=0, tag=tag,
                       bad=[(PHRASES[k][0], r["heard"]) for k, r in enumerate(res) if r["match"] < 0.85])
            agg["J"] = J(agg)
            json.dump(agg, open(f"pack/L_{c['id']}.json", "w", encoding="utf-8"), ensure_ascii=False)
            log(c["id"], c["track"], "J", agg["J"], "UTMOS", agg["utmos"], "слова", agg["match"], "Гц", round(agg["f0"]), c["w"])
        except Exception as e:
            import traceback
            log("ОШИБКА", c["id"], repr(e)); traceback.print_exc()


def loadL():
    return {os.path.basename(j)[2:-5]: json.load(open(j, encoding="utf-8")) for j in glob.glob("pack/L_*.json")}


def pick():
    L = loadL()
    rng = random.Random(2312)
    cast = json.load(open("cast/kasting.json", encoding="utf-8"))["cast"]
    good = sorted(cast, key=lambda s: -cast[s]["score"])[:16]
    cis = sorted([r for r in L.values() if r["track"] == "cis"], key=lambda r: -r["J"])
    bars = sorted([r for r in L.values() if r["track"] == "bars" and r["id"] != "b_xenia"], key=lambda r: -r["J"])
    for r in cis[:8] + bars[:5]:
        log("круг 1:", r["id"], r["J"], r["utmos"], r["match"], r["w"])
    C = []
    for j, r in enumerate(cis[:4]):
        for i in range(5):
            w = {k: dict(v) for k, v in r["w"].items()}
            role = ("dp", "pp", "spe", "pp", "spe")[i]
            w[role] = jitter(w[role], MALE if role == "spe" else good, rng, keep=(0.7, 0.9), kmax=1)
            C.append({"id": f"r{j}{i}", "track": "cis", "w": w, "from": r["id"]})
    for j, r in enumerate(bars[:2]):
        spe = list(r["w"]["spe"])[0]
        for i, (a, b) in enumerate(((0.7, 0.3), (0.3, 0.7), (0.5, 0.5))):
            w = {k: dict(v) for k, v in r["w"].items()}
            if i < 2:
                w["pp"] = {"xenia": a, spe: b}
            else:
                w["dp"] = {"xenia": a, spe: b}
            C.append({"id": f"q{j}{i}", "track": "bars", "w": w, "from": r["id"]})
    json.dump(C, open("pack/round2.json", "w", encoding="utf-8"), ensure_ascii=False)
    log("круг 2:", len(C))


def finpick():
    L = loadL()
    cis = sorted([r for r in L.values() if r["track"] == "cis" and r["id"] not in ("c00", "c01")], key=lambda r: -r["J"])
    bars = sorted([r for r in L.values() if r["track"] == "bars" and not r["id"].startswith("b_")], key=lambda r: -r["J"])
    F = []
    if "c00" in L:
        F.append(dict(L["c00"], title="Как №3 в прошлой пробе"))
    for i, r in enumerate(cis[:2], 1):
        F.append(dict(r, title=f"Новый {i}"))
    if bars:
        F.append(dict(bars[0], title="Манера Барсика, мужской голос"))
    if "b_xenia" in L:
        F.append(dict(L["b_xenia"], title="Барсик для сравнения (его голос без подъёма)"))
    if "c01" in L:
        F.append(dict(L["c01"], title="Сейчас в «Почему так?» (nash3)", hide=True))
    json.dump(F, open("pack/finalists.json", "w", encoding="utf-8"), ensure_ascii=False)
    for f in F:
        log("финалист:", f["id"], f["title"], f["J"], f["w"])


def fin(i):
    F = json.load(open("pack/finalists.json", encoding="utf-8"))
    shutil.rmtree("in", ignore_errors=True); shutil.rmtree("out", ignore_errors=True); os.makedirs("in"); os.makedirs("out")
    if i >= len(F):
        log("финалиста", i, "нет"); return
    f = F[i]
    prep_marks()
    net = Net(CIS if f["track"] == "cis" else RU)
    rows = net.build(f["w"])
    for k, (t, _) in enumerate(PHRASES):
        name = f"F__{f['id']}__{k:02d}"
        net.say(rows, t, f"in/{name}.wav")
        open(f"in/{name}.txt", "w", encoding="utf-8").write(t + "\n")
        open(f"in/{name}.voice", "w", encoding="utf-8").write(f"{f['track']}:{f['id']}\n")
    keys = {r: k for k, (r, _) in net.tabs.items()}
    json.dump({"id": f["id"], "track": f["track"], "w": f["w"], "coef": rows["coef"], "model": net.mid,
               "rows": {(ROLE_OF_NASH[r] if net.mid == CIS else k): [round(float(x), 6) for x in rows[k].tolist()]
                        for r, k in keys.items()}},
              open(f"in/_rows_{f['id']}.json", "w"))


def final():
    os.makedirs("cast2", exist_ok=True)
    F = json.load(open("pack/finalists.json", encoding="utf-8"))
    L = loadL()
    R = svoy.load_reps()
    rows = []
    for f in F:
        reps = R.get("F__" + f["id"])
        a = svoy.agg(reps) if reps else {}
        f["full"] = a; f["score"] = svoy.score(a) if a else None
    L2 = ["# Свой голос, круг 2 — итог", "",
          "Основа — №3 из первой пробы (ритм Марата, мелодия nash3, тембр nash2). Каждая часть — смесь многих дикторов с долями;",
          "доли подбирались по естественности (UTMOS) и разборчивости (распознаватель), круг 1 — 48 смесей, круг 2 — 20 вокруг лучших.",
          "Отдельно — модель Барсика (v5_ru, лицензия CC BY-NC): манера xenia с мужским тембром.", "",
          "## Финалисты (полная проверка, 12 фраз)", "",
          "| | голос | состав | слова | UTMOS | ошибки удар. | интонация | диапазон | Гц | темп | оценка |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda w: "; ".join(f"{r}: " + " + ".join(f"{s.replace('ru_', '')} {x:.2f}" for s, x in sorted(v.items(), key=lambda z: -z[1])) for r, v in w.items())
    for i, f in enumerate(F, 1):
        a = f["full"] or {}
        L2.append(f"| {i} | {f['title']} ({f['id']}) | {fmt(f['w'])} | {a.get('match') or 0:.3f} | {a.get('utmos') or 0:.2f} | "
                  f"{a.get('err') or 0:.2f} | {a.get('inton') or 0:.2f} | {a.get('range') or 0:.1f} | {a.get('f0') or 0:.0f} | "
                  f"{a.get('rate') or 0:.1f} | {f['score']} |")
    L2 += ["", "## Быстрая оценка всех смесей (J = 4·слова + UTMOS + 0,3·худший UTMOS + живость − темп)", "",
           "| смесь | дорожка | J | UTMOS | худший | слова | Гц | состав |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(L.values(), key=lambda r: -r["J"]):
        L2.append(f"| {r['id']} | {r['track']} | {r['J']} | {r['utmos']} | {r['utmos_min']} | {r['match']} | {r['f0']:.0f} | {fmt(r['w'])} |")
    open("cast2/itog.md", "w", encoding="utf-8").write("\n".join(L2) + "\n")
    log("\n".join(L2[:20]))
    gol = {}
    for f in F:
        rf = f"pack/_rows_{f['id']}.json"
        if os.path.exists(rf):
            gol[f["id"]] = dict(json.load(open(rf)), title=f["title"], score=f["score"])
    json.dump(gol, open("cast2/golosa2.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump({"finalists": F, "light": L}, open("cast2/krug2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # ролик: финалисты по порядку (кроме скрытых), фразы «слушать»
    pick = []
    for f in F:
        if f.get("hide"):
            continue
        a = f["full"] or {}
        sub = f"естественность {a.get('utmos') or f['utmos']:.2f}" if (a.get('utmos') or f.get('utmos')) else " "
        pick.append((f["title"], f"F__{f['id']}", sub))
    video(pick, "cast2/proba2.mp4", PHRASES)


def video(pick, outp, phrases):
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    os.makedirs("tmp", exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.7",
                    "-c:a", "pcm_s16le", "tmp/sil.wav"], check=True)
    parts = []
    for i, (title, tag, sub) in enumerate(pick, 1):
        fl = [f"pack/{tag}__{k:02d}.flac" for k, (_, lis) in enumerate(phrases) if lis]
        fl = [f for f in fl if os.path.exists(f)]
        if not fl:
            log("нет звука для", tag); continue
        seq = ["tmp/sil.wav"]
        for f in fl:
            seq += [f, "tmp/sil.wav"]
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for f in seq:
            cmd += ["-i", f]
        fc = "".join(f"[{j}:a]aresample=48000,aformat=channel_layouts=mono[x{j}];" for j in range(len(seq)))
        fc += "".join(f"[x{j}]" for j in range(len(seq))) + f"concat=n={len(seq)}:v=0:a=1,{svoy.SOFT}[o]"
        subprocess.run(cmd + ["-filter_complex", fc, "-map", "[o]", "-ar", "48000", "-ac", "1", f"tmp/a{i}.wav"], check=True)
        open(f"tmp/t{i}.txt", "w", encoding="utf-8").write(f"{i}. {title}")
        open(f"tmp/s{i}.txt", "w", encoding="utf-8").write(sub or " ")
        vf = (f"drawtext=fontfile={font}:textfile=tmp/t{i}.txt:fontsize=44:fontcolor=white:x=(w-text_w)/2:y=h/2-80,"
              f"drawtext=fontfile={font}:textfile=tmp/s{i}.txt:fontsize=30:fontcolor=0xbbbbbb:x=(w-text_w)/2:y=h/2+10")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x1e2230:s=1080x1080:r=25",
                        "-i", f"tmp/a{i}.wav", "-vf", vf, "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-tune", "stillimage", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", f"tmp/v{i}.mp4"], check=True)
        parts.append(f"tmp/v{i}.mp4")
    if parts:
        with open("tmp/all.txt", "w") as fh:
            for p in parts:
                fh.write(f"file '../{p}'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "tmp/all.txt", "-c", "copy", outp], check=True)
        log("ролик:", outp, os.path.getsize(outp))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "gen1":
        p, n = int(sys.argv[2]), int(sys.argv[3])
        evaluate(round1()[p::n], "1")
    elif cmd == "pick":
        pick()
    elif cmd == "gen2":
        p, n = int(sys.argv[2]), int(sys.argv[3])
        evaluate(json.load(open("pack/round2.json", encoding="utf-8"))[p::n], "2")
    elif cmd == "finpick":
        finpick()
    elif cmd == "fin":
        fin(int(sys.argv[2]))
    elif cmd == "pack":
        svoy.pack()
    elif cmd == "final":
        final()

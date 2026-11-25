#!/usr/bin/env python3
"""Свой голос в свободной модели, ПОДОБРАННЫЙ СЛУХОМ (25.11.2026).

Смешивание готовых дикторов (svoy_free, sluh_mix) даёт только то, что лежит между ними. Здесь строка тембра (spe, 128 чисел)
ищется свободно — эволюцией (CMA-ES) в пространстве главных осей всех 60 дикторов свободной модели v5_cis (MIT). Мерка —
три узнавателя голоса из sluh2.py: насколько синтез свободной модели с этой строкой похож на образец.
Образец (несвободная модель) в ролики не идёт — он только мерка, как у пародиста.

  python sluh_opt.py <образец> <зерно> [поколений]      образец: n4 | xenia | kseniya | eugene
  → cast10/opt_<образец>_<зерно>.json (строки голоса, ход поиска), .mp3 (образец, потом находка — посмотреть и послушать)
"""
import json, os, subprocess, sys, time, traceback
import numpy as np

OUT = "cast10"
log = lambda *a: print(*a, flush=True)
REF = {"ecapa": (0.97, 0.30), "wavlm": (0.99, 0.92), "resem": (0.98, 0.65)}     # (образец сам с собой, в среднем с чужими) — из sluh/itog.md
BASE = {"n4": ("g03", "low"), "eugene": ("g03", "low"), "xenia": ("ru_zhadyra", "medium"), "kseniya": ("ru_zhazira", "medium")}
NPC = int(os.environ.get("NPC", "24"))


class Lab:
    def __init__(self, target):
        import torch, sluh2, svoy2, svoy_bars, svoy_kot3 as K3
        torch.set_num_threads(4)
        self.torch, self.S, self.K3, self.svoy2 = torch, sluh2, K3, svoy2
        ph = sluh2.phrases24()
        self.ph = [ph[i] for i in (0, 2, 5, 6, 9, 11, 14, 17)]
        ru = svoy2.Net(svoy2.RU)
        if target == "n4":
            ru.put(ru.build(svoy_bars.W4)); spk = svoy2.SLOT[svoy2.RU]
        else:
            spk = target
        E = {k: [] for k in REF}
        f0, self.tw = [], []
        for t in self.ph:
            a = ru.m.apply_tts(ssml_text=K3.text_for({"model": "ru", "pitch": "medium", "rate": "medium"}, t), speaker=spk, sample_rate=48000,
                               put_accent=True, put_yo=True)
            self.tw.append(a.numpy().copy())
            x = self.to16(a); e = sluh2.embeds(x)
            for k in E:
                E[k].append(e[k])
            f0.append(self.f0(x))
        self.Tk = {k: np.array(v) for k, v in E.items()}             # по фразам
        self.T = {k: self.norm(np.mean(v, 0)) for k, v in E.items()}
        self.f0t = float(np.median(f0))
        del ru
        self.net = svoy2.Net(svoy2.CIS)
        net = self.net
        self.spe_key = next(k for k, (r, _) in net.tabs.items() if r == "spe")
        names = [s for s in net.ids if s in net.rows and not s.startswith("ru_nash")]
        M = torch.stack([net.rows[s][self.spe_key] for s in names]).double().numpy()
        self.mu = M.mean(0)
        U, sv, Vt = np.linalg.svd(M - self.mu, full_matrices=False)
        self.pc = Vt[:NPC]; self.sd = sv[:NPC] / np.sqrt(len(names) - 1)
        self.norms = (float(np.percentile(np.linalg.norm(M, axis=1), 10)), float(np.percentile(np.linalg.norm(M, axis=1), 90)))
        self.names, self.M = names, M
        b, self.pitch = BASE[target]
        if b == "g03":
            w = json.load(open("cast7/golos_free.json", encoding="utf-8"))["voices"]["ru_svoy1"]["w"]
        else:
            w = {r: {b: 1.0} for r in ("dp", "pp", "spe")}
        self.base_rows = net.build(w)
        self.texts = {}
        log("образец", target, f"{self.f0t:.0f} Гц; дикторов в основе", len(names), "осей", NPC, "доля разброса", round(float((sv[:NPC] ** 2).sum() / (sv ** 2).sum()), 3))

    norm = staticmethod(lambda v: v / (np.linalg.norm(v) + 1e-9))

    @staticmethod
    def to16(a):
        import torch, torchaudio
        a = a if hasattr(a, "numpy") else torch.tensor(a)
        return torchaudio.functional.resample(a.float(), 48000, 16000).numpy()

    @staticmethod
    def f0(x):
        import parselmouth
        p = parselmouth.Sound(x.astype(np.float64), 16000).to_pitch_ac(time_step=0.01, pitch_floor=50, pitch_ceiling=600).selected_array["frequency"]
        return float(np.median(p[p > 0])) if (p > 0).sum() > 5 else 0.0

    def z_of(self, row):
        return ((np.asarray(row, dtype=float) - self.mu) @ self.pc.T) / self.sd

    def row_of(self, z):
        r = self.mu + (np.asarray(z) * self.sd) @ self.pc
        n = np.linalg.norm(r)
        return r * (min(max(n, self.norms[0]), self.norms[1]) / (n + 1e-9))

    def say(self, row, t, extra=None, rate="medium"):
        """row — строка тембра; extra = {ключ таблицы: строка, "coef": число} — своя мелодия (pp), ритм (dp), размах."""
        rows = dict(self.base_rows)
        rows[self.spe_key] = self.torch.tensor(row, dtype=self.base_rows[self.spe_key].dtype)
        for k, v in (extra or {}).items():
            rows[k] = float(v) if k == "coef" else self.torch.tensor(v, dtype=self.base_rows[k].dtype)
        self.net.put(rows)
        key = (t, rate)
        if key not in self.texts:
            self.texts[key] = self.K3.text_for({"model": "cis", "pitch": self.pitch, "rate": rate}, t)
        return self.net.m.apply_tts(ssml_text=self.texts[key], speaker=self.svoy2.SLOT[self.svoy2.CIS], sample_rate=48000)

    def score(self, row, idx):
        """Близость к образцу на фразах idx: сравнение по тем же фразам + штраф за высоту дальше ±2 полутонов."""
        E = {k: [] for k in REF}
        f0 = []
        for i in idx:
            x = self.to16(self.say(row, self.ph[i]))
            e = self.S.embeds(x)
            for k in E:
                E[k].append(e[k])
            f0.append(self.f0(x))
        sims = {k: float(self.norm(np.mean(v, 0)) @ self.norm(self.Tk[k][idx].mean(0))) for k, v in E.items()}
        pos = {k: (sims[k] - o) / (s - o) for k, (s, o) in REF.items()}
        close = 0.5 * pos["ecapa"] + 0.25 * pos["wavlm"] + 0.25 * pos["resem"]
        fm = float(np.median(f0)) if f0 else 0.0
        dst = abs(12 * np.log2(max(fm, 1) / self.f0t))
        return close - 0.03 * max(0.0, dst - 2.0), {"close": round(close, 4), "sims": {k: round(v, 3) for k, v in sims.items()}, "f0": round(fm, 1)}

    def quality(self, row):
        """Не мусор ли: слова (распознаватель), естественность (UTMOS), чёткость — на трёх фразах."""
        import svoy_lib as SL, gen as g
        mt, ut = [], []
        for i in (1, 3, 6):
            p = f"tmp/q_{i}.wav"
            a = self.say(row, self.ph[i]); g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p)
            try:
                mt.append(SL.heard_match(p, self.ph[i])[1]); ut.append(SL.utmos(SL.load(p, 16000)))
            except Exception:
                traceback.print_exc()
        return {"match": round(float(np.mean(mt)), 3) if mt else None, "utmos": round(float(np.mean(ut)), 2) if ut else None}


def main(target, seed, gens):
    import cma, svoy_omo, svoy2, gen as g
    for d in (OUT, "tmp", "models"):
        os.makedirs(d, exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    L = Lab(target)
    rnd = np.random.default_rng(seed)
    all8 = list(range(8))
    # старт: лучший из готовых дикторов и прежней смеси по полной мерке
    starts = [("основа", L.base_rows[L.spe_key].double().numpy())]
    cand = []
    for s in L.names:
        if s.startswith("ru_"):
            sc, info = L.score(L.net.rows[s][L.spe_key].double().numpy(), [0, 3, 6])
            cand.append((sc, s, info))
    cand.sort(reverse=True)
    log("лучшие готовые дикторы:", [(s, round(sc, 3), i["sims"]["ecapa"], i["f0"]) for sc, s, i in cand[:6]])
    for sc, s, i in cand[:2]:
        starts.append((s, L.net.rows[s][L.spe_key].double().numpy()))
    import glob
    for f in sorted(glob.glob(f"{OUT}/opt_{target}_*.json")):          # прошлые находки — продолжаем с лучшей
        try:
            pr = json.load(open(f, encoding="utf-8"))
            starts.append((os.path.basename(f), np.array(pr["win"]["spe"], dtype=float)))
        except Exception:
            traceback.print_exc()
    best = None
    for name, row in starts:
        sc, info = L.score(row, all8)
        log("старт", name, round(sc, 4), info)
        if best is None or sc > best[0]:
            best = (sc, row, info, name)
    start_info = {"name": best[3], "score": round(best[0], 4), **best[2]}
    z0 = L.z_of(best[1])
    log("старт поиска:", best[3], "; строка в осях восстановлена с ошибкой", round(float(np.linalg.norm(L.row_of(z0) - best[1]) / np.linalg.norm(best[1])), 3))
    es = cma.CMAEvolutionStrategy(z0.tolist(), float(os.environ.get("SIGMA", "0.35")), {"popsize": 14, "seed": seed + 1, "bounds": [-3.5, 3.5], "verbose": -9})
    trail, t0 = [], time.time()
    top = [(best[0], best[1], best[2])]
    for gi in range(gens):
        idx = sorted(rnd.choice(8, size=3, replace=False).tolist())
        Z = es.ask()
        F = []
        for z in Z:
            try:
                sc, _ = L.score(L.row_of(z), idx)
            except Exception as e:
                log("ОШИБКА", repr(e)); sc = -1.0
            F.append(-sc)
        es.tell(Z, F)
        if gi % 5 == 4 or gi == gens - 1:
            row = L.row_of(es.mean)
            sc, info = L.score(row, all8)
            top.append((sc, row, info))
            trail.append({"gen": gi + 1, "score": round(sc, 4), **info, "sigma": round(float(es.sigma), 3), "min": round((time.time() - t0) / 60, 1)})
            log("поколение", gi + 1, trail[-1])
        if time.time() - t0 > 70 * 60:
            log("время вышло"); break
    top.sort(key=lambda x: -x[0])
    res = []
    for sc, row, info in top[:3]:
        q = L.quality(row)
        res.append({"score": round(sc, 4), **info, **q, "spe": [round(float(x), 6) for x in row]})
        log("итог", res[-1]["score"], info, q)
    ok = [r for r in res if (r["match"] or 0) >= 0.85] or res
    win = ok[0]
    out = {"target": target, "seed": seed, "f0_target": L.f0t, "start": start_info, "trail": trail, "best": res, "win": win,
           "base": BASE[target], "ready": [(s, round(sc, 4), i) for sc, s, i in cand[:10]], "spe_key": L.spe_key}
    tag = os.environ.get("TAG", "")
    seed = f"{seed}{tag}"
    json.dump(out, open(f"{OUT}/opt_{target}_{seed}.json", "w", encoding="utf-8"), ensure_ascii=False)
    # послушать и посмотреть: три фразы образцом, потом находкой
    parts = []
    for j, i in enumerate((0, 3, 6)):
        p = f"tmp/t_{j}.wav"; g.save_wav(L.tw[i], p); parts.append(p)
    for j, i in enumerate((0, 3, 6)):
        p = f"tmp/w_{j}.wav"; a = L.say(np.array(win["spe"]), L.ph[i]); g.save_wav(a.numpy() if hasattr(a, "numpy") else a, p); parts.append(p)
    lst = "tmp/list.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "libmp3lame", "-q:a", "3",
                    f"{OUT}/opt_{target}_{seed}.mp3"], check=True)
    for j, p in enumerate(parts):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ar", "44100", "-ac", "1", f"{OUT}/opt_{target}_{seed}_{'t' if j < 3 else 'w'}{j % 3}.flac"], check=True)
    log("готово", target, seed, "старт", start_info["score"], "→", win["score"], win["sims"])


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 60)

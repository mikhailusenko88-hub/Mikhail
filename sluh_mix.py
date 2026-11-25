#!/usr/bin/env python3
"""Смесь тембра свободной модели под образец — тем слухом, который прошёл проверку (sluh2.py): три узнавателя голоса
(ECAPA, WavLM-SV, resemblyzer), а не один resemblyzer, как в svoy_free.py (он ставил 0,85 там, где ECAPA слышит 0,57).

  python sluh_mix.py <образец> <часть> <всего>     образец: n4 (голос №4) | eugene | xenia | kseniya …
  python sluh_mix.py final <образец>

Близость = средняя доля пути от «чужого» к «тому же» по трём узнавателям (точки отсчёта — из sluh/sluh.json).
Ход: 1) каждый диктор по одному (три высоты SSML); 2) жадно подмешиваем к лучшему других дикторов; 3) подгонка долей.
Ритм и мелодия (dp, pp) — от нашей смеси g03: здесь ищется только тембр.
"""
import glob, json, os, sys, traceback
import numpy as np

OUT = "cast10"
log = lambda *a: print(*a, flush=True)
PITCHES = ("x-low", "low", "medium")


def base_refs(target):
    """Точки отсчёта из прошлого прогона слуха: похожесть образца сам с собой и средняя с чужими."""
    R = json.load(open("sluh/sluh.json", encoding="utf-8"))["groups"]["№4"]
    ref = {}
    for k in ("ecapa", "wavlm", "resem"):
        o = [v for i, v in R["others"][k] if not i.startswith("eugene")]
        ref[k] = (R["floor"][k + "_m"], float(np.mean(o)))
    return ref


class Ear:
    def __init__(self, target):
        import sluh2, svoy2, svoy_bars, svoy_kot3 as K3, svoy_manera
        self.S, self.K3, self.svoy2 = sluh2, K3, svoy2
        ph = sluh2.phrases24()
        self.ph = [ph[i] for i in (0, 2, 5, 6, 9, 11, 14, 17)]
        self.ref = base_refs(target)
        ru = svoy2.Net(svoy2.RU)
        if target == "n4":
            ru.put(ru.build(svoy_bars.W4)); spk = svoy2.SLOT[svoy2.RU]
        else:
            spk = target
        E = {k: [] for k in self.ref}
        f0 = []
        for t in self.ph:
            a = ru.m.apply_tts(ssml_text=K3.text_for({"model": "ru", "pitch": "medium", "rate": "medium"}, t), speaker=spk, sample_rate=48000,
                               put_accent=True, put_yo=True)
            x = self.to16(a)
            e = sluh2.embeds(x)
            for k in E:
                E[k].append(e[k])
            f0.append(self.f0(x))
        self.T = {k: self.norm(np.mean(v, 0)) for k, v in E.items()}
        self.f0t = float(np.median(f0))
        del ru
        self.net = svoy2.Net(svoy2.CIS)
        self.pool = svoy_manera.pool()
        self.g03 = json.load(open("cast7/golos_free.json", encoding="utf-8"))["voices"]["ru_svoy1"]["w"]
        self.texts = {}
        log("образец", target, f"{self.f0t:.0f} Гц; точки отсчёта", {k: (round(a, 2), round(b, 2)) for k, (a, b) in self.ref.items()})

    @staticmethod
    def norm(v):
        return v / (np.linalg.norm(v) + 1e-9)

    @staticmethod
    def to16(a):
        import torch, torchaudio
        a = a if hasattr(a, "numpy") else torch.tensor(a)
        return torchaudio.functional.resample(a.float(), 48000, 16000).numpy()

    @staticmethod
    def f0(x):
        import parselmouth
        p = parselmouth.Sound(x.astype(np.float64), 16000).to_pitch_ac(time_step=0.01, pitch_floor=50, pitch_ceiling=500).selected_array["frequency"]
        return float(np.median(p[p > 0])) if (p > 0).sum() > 5 else 0.0

    def score(self, spe, pitch="low", n=5):
        """spe = {диктор: доля} → близость к образцу (0…1), похожести, высота."""
        w = {"dp": self.g03["dp"], "pp": self.g03["pp"], "spe": spe}
        self.net.put(self.net.build(w))
        E = {k: [] for k in self.ref}
        f0 = []
        for t in self.ph[:n]:
            key = (t, pitch)
            if key not in self.texts:
                self.texts[key] = self.K3.text_for({"model": "cis", "pitch": pitch, "rate": "medium"}, t)
            a = self.net.m.apply_tts(ssml_text=self.texts[key], speaker=self.svoy2.SLOT[self.svoy2.CIS], sample_rate=48000)
            x = self.to16(a)
            e = self.S.embeds(x)
            for k in E:
                E[k].append(e[k])
            f0.append(self.f0(x))
        sims = {k: float(self.norm(np.mean(v, 0)) @ self.T[k]) for k, v in E.items()}
        close = float(np.mean([(sims[k] - o) / (s - o) for k, (s, o) in self.ref.items()]))
        return {"close": round(close, 4), "sims": {k: round(v, 3) for k, v in sims.items()}, "f0": round(float(np.median(f0)), 1)}


def mixed(a, b, alpha):
    w = {k: v * (1 - alpha) for k, v in a.items()}
    w[b] = w.get(b, 0) + alpha
    return {k: round(v, 4) for k, v in w.items() if v > 0.02}


def run(target, part, n):
    import svoy_omo, svoy2
    os.makedirs(OUT, exist_ok=True); os.makedirs("tmp", exist_ok=True); os.makedirs("models", exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    ear = Ear(target)
    res = []
    if part == 0:
        r = ear.score(ear.g03["spe"], "low", n=8); r.update(id="g03", spe=ear.g03["spe"], pitch="low"); res.append(r)
        log("наша прежняя смесь g03:", r)
    # 1. дикторы по одному — эта часть набора
    singles = []
    for i, s in enumerate(ear.pool):
        if i % n != part:
            continue
        best = None
        for p in PITCHES:
            try:
                r = ear.score({s: 1.0}, p)
            except Exception as e:
                log("ОШИБКА", s, p, repr(e)); continue
            r.update(id=f"{s[3:]}@{p}", spe={s: 1.0}, pitch=p)
            res.append(r)
            if abs(12 * np.log2(max(r["f0"], 1) / ear.f0t)) < 2.5 and (best is None or r["close"] > best["close"]):
                best = r
        log(s, [(x["pitch"], x["close"], x["f0"]) for x in res[-3:]])
    json.dump({"target": target, "f0": ear.f0t, "res": res}, open(f"{OUT}/s_{target}_{part}.json", "w", encoding="utf-8"), ensure_ascii=False)


def greedy(target):
    """Второй шаг — одним заданием: по итогам «по одному» жадно подмешиваем дикторов."""
    import svoy_omo, svoy2
    os.makedirs(OUT, exist_ok=True); os.makedirs("tmp", exist_ok=True); os.makedirs("models", exist_ok=True)
    svoy_omo.ruacc(); svoy2.patch_ruaccent()
    S = []
    for f in sorted(glob.glob(f"{OUT}/s_{target}_*.json")):
        S += json.load(open(f, encoding="utf-8"))["res"]
    ear = Ear(target)
    ok = [r for r in S if r["id"] != "g03" and abs(12 * np.log2(max(r["f0"], 1) / ear.f0t)) < 2.5]
    ok.sort(key=lambda r: -r["close"])
    log("лучшие по одному:", [(r["id"], r["close"], r["sims"]["ecapa"]) for r in ok[:12]])
    top = []
    for r in ok:                                   # лучшие дикторы (каждый один раз) — из них подмешиваем
        s = list(r["spe"])[0]
        if s not in top:
            top.append(s)
    top = top[:12]
    trail = []
    best = dict(ok[0]) if ok else None
    g03 = next((r for r in S if r["id"] == "g03"), None)
    starts = [dict(ok[0])] + ([dict(g03)] if g03 else [])
    finals = []
    for st in starts:
        cur = ear.score(st["spe"], st["pitch"], n=8); cur.update(spe=st["spe"], pitch=st["pitch"])
        log("старт", st["id"], cur["close"])
        for it in range(5):
            cand = []
            for s in top:
                for a in (0.15, 0.3):
                    w = mixed(cur["spe"], s, a)
                    try:
                        r = ear.score(w, cur["pitch"])
                    except Exception as e:
                        log("ОШИБКА", repr(e)); continue
                    r.update(spe=w, pitch=cur["pitch"]); cand.append(r)
            cand.sort(key=lambda r: -r["close"])
            chk = []
            for r in cand[:3]:                          # лучших перепроверяем на всех восьми фразах
                q = ear.score(r["spe"], r["pitch"], n=8); q.update(spe=r["spe"], pitch=r["pitch"]); chk.append(q)
            chk.sort(key=lambda r: -r["close"])
            log("шаг", it, "лучший", chk[0]["close"], chk[0]["sims"], chk[0]["spe"], "было", cur["close"])
            trail.append({"start": st["id"], "it": it, "best": chk[0]})
            if chk[0]["close"] <= cur["close"] + 0.004:
                break
            cur = chk[0]
        for p in PITCHES:                               # высота SSML для итоговой смеси
            if p != cur["pitch"]:
                q = ear.score(cur["spe"], p, n=8); q.update(spe=cur["spe"], pitch=p)
                if abs(12 * np.log2(max(q["f0"], 1) / ear.f0t)) < 2.5 and q["close"] > cur["close"]:
                    cur = q
        cur["start"] = st["id"]; finals.append(cur)
    finals.sort(key=lambda r: -r["close"])
    out = {"target": target, "f0": ear.f0t, "ref": ear.ref, "g03": g03, "singles": [{k: r[k] for k in ("id", "close", "sims", "f0")} for r in ok[:20]],
           "finals": finals, "trail": trail}
    json.dump(out, open(f"{OUT}/mix_{target}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = [f"# Смесь тембра под образец {target} — новым слухом", "",
          f"Образец {ear.f0t:.0f} Гц. Близость — средняя доля пути от «чужого» к «тому же» по трём узнавателям (100 % — тот же голос).", "",
          f"Прежняя смесь g03: {100 * g03['close']:.0f} % ({g03['sims']})." if g03 else "", "",
          "## Дикторы по одному", "", "| диктор@высота | близость | ECAPA | WavLM | resemblyzer | Гц |", "|---|---|---|---|---|---|"]
    for r in ok[:15]:
        md.append(f"| {r['id']} | {100 * r['close']:.0f} % | {r['sims']['ecapa']:.2f} | {r['sims']['wavlm']:.2f} | {r['sims']['resem']:.2f} | {r['f0']:.0f} |")
    md += ["", "## Итоговые смеси", ""]
    for r in finals:
        md.append(f"- старт {r['start']}: близость {100 * r['close']:.0f} %, {r['sims']}, {r['f0']:.0f} Гц, высота SSML {r['pitch']}, тембр {r['spe']}")
    open(f"{OUT}/mix_{target}.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    log("\n".join(md))


if __name__ == "__main__":
    if sys.argv[1] == "final":
        greedy(sys.argv[2])
    else:
        run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))

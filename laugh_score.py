"""Оценка сгенерированных смехов: классификатор AudioSet (AST, MIT/ast-finetuned-audioset-10-10-0.4593),
высота голоса (Praat), обрезка тишины, нормировка. gen/*.wav → out/wav/<id>.wav, out/png/<id>.png, out/report.json, out/report.md
"""
import glob, json, os, sys
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

LAUGH = ["Laughter", "Giggle", "Chuckle, chortle", "Belly laugh", "Snicker", "Baby laughter"]
BAD = ["Speech", "Music", "Singing", "Child speech, kid speaking", "Narration, monologue", "Conversation"]


def env_db(y, sr, win=0.01):
    w = max(1, int(sr * win))
    n = len(y) // w
    e = np.sqrt(np.mean(y[: n * w].reshape(n, w) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(e + 1e-9), w


def trim(y, sr, th_db=-38, pad=0.05):
    db, w = env_db(y, sr)
    db = db - db.max()
    idx = np.where(db > th_db)[0]
    if len(idx) == 0:
        return y
    a = max(0, idx[0] * w - int(pad * sr))
    b = min(len(y), (idx[-1] + 1) * w + int(pad * 2 * sr))
    z = y[a:b].copy()
    f = min(len(z) // 4, int(sr * 0.012))
    if f > 0:
        ramp = np.linspace(0, 1, f)
        z[:f] *= ramp
        z[-f:] *= ramp[::-1]
    return z


def syllables(y, sr):
    db, w = env_db(y, sr, 0.01)
    db = db - db.max()
    # сглаженная огибающая, пики = слоги «ха»
    k = np.ones(3) / 3
    s = np.convolve(db, k, mode="same")
    pk = []
    last = -99
    for i in range(1, len(s) - 1):
        if s[i] > -20 and s[i] >= s[i - 1] and s[i] >= s[i + 1] and i - last >= 7:
            # заметный провал между пиками
            lo = s[max(0, last if last > 0 else 0): i].min() if last > 0 else -99
            if last < 0 or s[i] - lo > 4:
                pk.append(i * w / sr)
                last = i
    return pk


def pitch_stats(y, sr):
    try:
        import parselmouth
        snd = parselmouth.Sound(y.astype(np.float64), sr)
        p = snd.to_pitch(time_step=0.01, pitch_floor=70, pitch_ceiling=800)
        f = p.selected_array["frequency"]
        v = f[f > 0]
        if len(v) < 5:
            return {"f0": 0, "f0lo": 0, "f0hi": 0, "voiced": 0.0}
        return {"f0": float(np.median(v)), "f0lo": float(np.percentile(v, 10)), "f0hi": float(np.percentile(v, 90)),
                "voiced": float(len(v) / len(f))}
    except Exception as e:
        print("pitch", e)
        return {"f0": 0, "f0lo": 0, "f0hi": 0, "voiced": 0.0}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "gen"
    out = sys.argv[2] if len(sys.argv) > 2 else "out"
    os.makedirs(out + "/wav", exist_ok=True)
    os.makedirs(out + "/png", exist_ok=True)
    import torch
    from transformers import ASTFeatureExtractor, ASTForAudioClassification
    name = "MIT/ast-finetuned-audioset-10-10-0.4593"
    fe = ASTFeatureExtractor.from_pretrained(name)
    model = ASTForAudioClassification.from_pretrained(name).eval()
    id2label = model.config.id2label
    lab = {v: k for k, v in id2label.items()}
    li = [lab[x] for x in LAUGH if x in lab]
    bi = [lab[x] for x in BAD if x in lab]
    print("laugh classes:", [id2label[i] for i in li], "bad:", [id2label[i] for i in bi])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = []
    for wp in sorted(glob.glob(os.path.join(src, "*.wav"))):
        cid = os.path.splitext(os.path.basename(wp))[0]
        meta = {}
        jp = os.path.join(src, cid + ".json")
        if os.path.exists(jp):
            meta = json.load(open(jp))
        y, sr = sf.read(wp, dtype="float32")
        if y.ndim > 1:
            y = y.mean(axis=1)
        y = trim(y, sr)
        if len(y) < sr * 0.3:
            rows.append({"id": cid, "skip": "too short", **meta})
            continue
        y = y / (np.max(np.abs(y)) + 1e-9) * 0.9
        y16 = resample_poly(y, 16000, sr) if sr != 16000 else y
        inp = fe(y16, sampling_rate=16000, return_tensors="pt")
        with torch.no_grad():
            pr = torch.sigmoid(model(**inp).logits)[0].numpy()
        top = np.argsort(-pr)[:5]
        laugh = {id2label[i]: round(float(pr[i]), 3) for i in li}
        bad = {id2label[i]: round(float(pr[i]), 3) for i in bi}
        score = max(laugh.values()) - 0.6 * max(bad.values())
        ps = pitch_stats(y, sr)
        syl = syllables(y, sr)
        sf.write(os.path.join(out, "wav", cid + ".wav"), y, sr, subtype="PCM_16")
        row = {"id": cid, "dur": round(len(y) / sr, 2), "score": round(float(score), 3), "laugh": laugh, "bad": bad,
               "top": [(id2label[i], round(float(pr[i]), 3)) for i in top], **ps, "syl": len(syl),
               "rate": round(len(syl) / max(0.3, len(y) / sr), 1), "prompt": meta.get("prompt"), "preset": meta.get("preset"),
               "gen_sec": meta.get("sec")}
        rows.append(row)
        # картинка: волна + спектрограмма
        fig, ax = plt.subplots(2, 1, figsize=(7, 3.4), sharex=True)
        tt = np.arange(len(y)) / sr
        ax[0].plot(tt, y, lw=.4, color="#2a6")
        for s in syl:
            ax[0].axvline(s, color="#d33", lw=.6, alpha=.6)
        ax[0].set_title(f"{cid}  score {score:.2f}  {max(laugh, key=laugh.get)} {max(laugh.values()):.2f}  speech {bad.get('Speech', 0):.2f}  f0 {ps['f0']:.0f} Hz ({ps['f0lo']:.0f}-{ps['f0hi']:.0f})  syl {len(syl)}  {len(y)/sr:.1f}s", fontsize=7)
        ax[1].specgram(y, Fs=sr, NFFT=512, noverlap=384, cmap="magma", vmin=-110, vmax=-20)
        ax[1].set_ylim(0, 6000)
        plt.tight_layout()
        plt.savefig(os.path.join(out, "png", cid + ".png"), dpi=90)
        plt.close(fig)
        print(cid, row["dur"], row["score"], row["top"][:3], flush=True)

    rows.sort(key=lambda r: -r.get("score", -9))
    json.dump(rows, open(os.path.join(out, "report.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(out, "report.md"), "w") as f:
        f.write("| id | score | dur | laugh | speech | f0 | range | syl | rate | prompt | preset |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            if "skip" in r:
                f.write(f"| {r['id']} | skip | | | | | | | | | |\n")
                continue
            lk = max(r["laugh"], key=r["laugh"].get)
            f.write(f"| {r['id']} | {r['score']:.2f} | {r['dur']} | {lk} {r['laugh'][lk]:.2f} | {r['bad'].get('Speech', 0):.2f} | {r['f0']:.0f} | {r['f0lo']:.0f}-{r['f0hi']:.0f} | {r['syl']} | {r['rate']} | {r['prompt']} | {r['preset']} |\n")
    print("done", len(rows))


if __name__ == "__main__":
    main()

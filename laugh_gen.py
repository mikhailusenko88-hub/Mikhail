"""Генерация настоящих смехов нейросетью Bark (suno/bark, MIT) на CPU.
Запуск: python laugh_gen.py --shard I --nshards N [--small] [--out gen]
Каждый клип: gen/<id>.wav (24 кГц, моно) + gen/<id>.json (промпт, пресет, время).
"""
import argparse, json, os, time, sys, zlib
import numpy as np

PROMPTS = [
    ("lt", "[laughter]"),
    ("ha", "Hahahaha! [laughs]"),
    ("hee", "Hee hee hee hee hee! [laughs]"),
    ("heh", "[chuckles] Heh heh heh heh."),
    ("ho", "Ho ho ho ho! [laughter]"),
    ("ru", "Ха-ха-ха-ха-ха! [laughs]"),
]
PRESETS = ["v2/en_speaker_2", "v2/en_speaker_3", "v2/en_speaker_5", "v2/en_speaker_6",
           "v2/en_speaker_7", "v2/en_speaker_9", "v2/ru_speaker_3", "v2/ru_speaker_5",
           "v2/ru_speaker_6", "v2/ru_speaker_9", "v2/fr_speaker_1", "v2/de_speaker_3"]
# набор 2: только промпты и голоса, которые дали настоящий смех в первом прогоне
PROMPTS2 = [
    ("ha", "Hahahaha! [laughs]"),
    ("hee", "Hee hee hee hee hee! [laughs]"),
    ("heh", "[chuckles] Heh heh heh heh."),
    ("ho", "Ho ho ho ho ho! [laughs]"),
]
PRESETS2 = ["v2/en_speaker_9", "v2/en_speaker_3", "v2/en_speaker_5", "v2/de_speaker_3", "v2/fr_speaker_1",
            "v2/en_speaker_2", "v2/en_speaker_6", "v2/ru_speaker_5", "v2/en_speaker_8", "v2/ru_speaker_4",
            "v2/pl_speaker_5", "v2/it_speaker_2"]


def tasks(reps, set_=1):
    T = []
    P, V = (PROMPTS2, PRESETS2) if set_ == 2 else (PROMPTS, PRESETS)
    for rep in range(reps):
        for pk, ptxt in P:
            for pr in V:
                T.append({"id": f"s{set_}-{pk}-{pr.split('/')[-1]}-{rep}" if set_ != 1 else f"{pk}-{pr.split('/')[-1]}-{rep}", "prompt": ptxt, "preset": pr, "rep": rep})
    return T


def request_opts():
    o = {"set": 1, "reps": 1}
    try:
        for tok in open("request.txt").read().split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                if k in o:
                    o[k] = int(v)
    except Exception:
        pass
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--out", default="gen")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ro = request_opts()
    T = tasks(max(a.reps, ro["reps"]), ro["set"])[a.shard::a.nshards]
    if a.limit:
        T = T[:a.limit]
    print(f"shard {a.shard}/{a.nshards}: {len(T)} clips", flush=True)

    import torch, soundfile as sf
    from transformers import AutoProcessor, BarkModel
    torch.set_num_threads(max(1, os.cpu_count() or 4))
    name = "suno/bark-small" if a.small else "suno/bark"
    t0 = time.time()
    processor = AutoProcessor.from_pretrained(name)
    model = BarkModel.from_pretrained(name)
    model.eval()
    sr = model.generation_config.sample_rate
    print(f"model {name} loaded in {time.time()-t0:.0f}s, sr={sr}", flush=True)

    for i, t in enumerate(T):
        wav_path = os.path.join(a.out, t["id"] + ".wav")
        if os.path.exists(wav_path):
            continue
        seed = (zlib.crc32(t["id"].encode()) & 0xffff) + 1
        torch.manual_seed(seed)
        t1 = time.time()
        try:
            inputs = processor(t["prompt"], voice_preset=t["preset"], return_tensors="pt")
            with torch.no_grad():
                try:
                    audio = model.generate(**inputs, do_sample=True, semantic_max_new_tokens=360,
                                           semantic_temperature=0.7, coarse_temperature=0.7, fine_temperature=0.5)
                except TypeError as e:
                    print("fallback generate:", e, flush=True)
                    audio = model.generate(**inputs, do_sample=True)
            y = audio.cpu().numpy().squeeze().astype(np.float32)
            pk = float(np.max(np.abs(y)) + 1e-9)
            if pk > 1:
                y = y / pk
            sf.write(wav_path, y, sr, subtype="PCM_16")
            meta = dict(t, sr=sr, dur=round(len(y) / sr, 2), sec=round(time.time() - t1, 1), model=name, seed=seed)
        except Exception as e:
            meta = dict(t, error=repr(e), model=name)
            print("ERR", t["id"], repr(e), flush=True)
        with open(os.path.join(a.out, t["id"] + ".json"), "w") as f:
            json.dump(meta, f, ensure_ascii=False)
        print(f"[{i+1}/{len(T)}] {t['id']} {meta.get('dur','-')}s in {meta.get('sec','-')}s", flush=True)


if __name__ == "__main__":
    main()

"""Смех нейроголосом Orpheus-TTS (canopylabs, Apache-2.0) на CPU через llama.cpp (GGUF) + декодер SNAC (MIT).
Запуск: python laugh_gen_orpheus.py --shard I --nshards N [--out gen]
"""
import argparse, json, os, time, zlib
import numpy as np

PROMPTS = [
    ("lg", "<laugh>"),
    ("lg2", "<laugh> <laugh>"),
    ("gg", "<giggle>"),
    ("ch", "<chuckle>"),
    ("ha", "Hahahaha! <laugh>"),
    ("hee", "Hee hee hee hee! <giggle>"),
]
VOICES = ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"]
GGUF = [
    ("isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF", "orpheus-3b-0.1-ft-q4_k_m.gguf"),
    ("unsloth/orpheus-3b-0.1-ft-GGUF", "orpheus-3b-0.1-ft-Q4_K_M.gguf"),
    ("lex-au/Orpheus-3b-FT-Q4_K_M.gguf", "Orpheus-3b-FT-Q4_K_M.gguf"),
    ("lex-au/Orpheus-3b-FT-Q8_0.gguf", "Orpheus-3b-FT-Q8_0.gguf"),
]
AUDIO0 = 128266  # первый аудио-токен: 128256 + 10
EOS = 128258


def tasks(reps):
    T = []
    for rep in range(reps):
        for pk, ptxt in PROMPTS:
            for v in VOICES:
                T.append({"id": f"o-{pk}-{v}-{rep}", "prompt": ptxt, "preset": v, "rep": rep})
    return T


def get_model():
    from huggingface_hub import hf_hub_download
    last = None
    for repo, fn in GGUF:
        try:
            p = hf_hub_download(repo, fn)
            print("gguf:", repo, fn, flush=True)
            return p
        except Exception as e:
            last = e
            print("no", repo, fn, repr(e)[:120], flush=True)
    raise last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--out", default="gen")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    T = tasks(a.reps)[a.shard::a.nshards]
    if a.limit:
        T = T[:a.limit]
    print(f"shard {a.shard}/{a.nshards}: {len(T)} clips", flush=True)

    import torch, soundfile as sf
    from llama_cpp import Llama
    from snac import SNAC
    t0 = time.time()
    llm = Llama(model_path=get_model(), n_ctx=2048, n_threads=os.cpu_count() or 4, verbose=False, logits_all=False)
    snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").eval()
    print(f"loaded in {time.time()-t0:.0f}s", flush=True)

    for i, t in enumerate(T):
        wav_path = os.path.join(a.out, t["id"] + ".wav")
        if os.path.exists(wav_path):
            continue
        seed = (zlib.crc32(t["id"].encode()) & 0xffff) + 1
        t1 = time.time()
        try:
            text = f"{t['preset']}: {t['prompt']}"
            ids = [128259] + llm.tokenize(text.encode(), add_bos=False, special=True) + [128009, 128260]
            llm.set_seed(seed)
            out = []
            for tok in llm.generate(ids, temp=0.6, top_p=0.8, repeat_penalty=1.3, reset=True):
                if tok == EOS or len(out) > 900:
                    break
                out.append(tok)
            aud = [x for x in out if x >= AUDIO0]
            codes = []
            for k, x in enumerate(aud):
                codes.append(x - AUDIO0 - (k % 7) * 4096)
            n = len(codes) // 7
            codes = codes[: n * 7]
            if n < 3 or any(c < 0 or c > 4095 for c in codes):
                raise RuntimeError(f"bad codes n={n} tokens={len(out)} audio={len(aud)}")
            c0, c1, c2 = [], [], []
            for j in range(n):
                f = codes[7 * j: 7 * j + 7]
                c0.append(f[0]); c1 += [f[1], f[4]]; c2 += [f[2], f[3], f[5], f[6]]
            cz = [torch.tensor(c0).unsqueeze(0), torch.tensor(c1).unsqueeze(0), torch.tensor(c2).unsqueeze(0)]
            with torch.no_grad():
                y = snac.decode(cz).squeeze().cpu().numpy().astype(np.float32)
            pk = float(np.max(np.abs(y)) + 1e-9)
            if pk > 1:
                y = y / pk
            sf.write(wav_path, y, 24000, subtype="PCM_16")
            meta = dict(t, sr=24000, dur=round(len(y) / 24000, 2), sec=round(time.time() - t1, 1), model="orpheus-3b-gguf", seed=seed, ntok=len(out))
        except Exception as e:
            meta = dict(t, error=repr(e)[:300], model="orpheus-3b-gguf")
            print("ERR", t["id"], repr(e)[:200], flush=True)
        with open(os.path.join(a.out, t["id"] + ".json"), "w") as f:
            json.dump(meta, f, ensure_ascii=False)
        print(f"[{i+1}/{len(T)}] {t['id']} {meta.get('dur','-')}s in {meta.get('sec','-')}s", flush=True)


if __name__ == "__main__":
    main()

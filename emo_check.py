#!/usr/bin/env python3
# «Какая эмоция слышна»: два распознавателя эмоций русской речи, распознаватель звуков (шёпот, крик, плач),
# слова (Whisper), естественность (UTMOS) и простые измерения голоса (высота, размах, темп, яркость).
# Вход: emo/<имя>.flac (+ emo/<имя>.txt — текст реплики). Выход: emo_out/report.json, report.md.
import glob, hashlib, json, os, sys, traceback, difflib
import numpy as np
os.makedirs("emo_out", exist_ok=True)
files = sorted(glob.glob("emo/*.flac") + glob.glob("emo/*.wav"))
if not files:
    print("нет файлов"); sys.exit(0)
done = {}
if os.path.exists("emo_out/report.json"):
    try: done = {r["name"]: r for r in json.load(open("emo_out/report.json", encoding="utf-8"))}
    except Exception: done = {}
import torch
import voice_check as vc
from transformers import HubertForSequenceClassification, Wav2Vec2FeatureExtractor, AutoModelForAudioClassification, AutoFeatureExtractor, ASTForAudioClassification
def log(*a): print(*a, flush=True)
fe1 = Wav2Vec2FeatureExtractor.from_pretrained("facebook/hubert-large-ls960-ft")
m1 = HubertForSequenceClassification.from_pretrained("xbgoose/hubert-large-speech-emotion-recognition-russian-dusha-finetuned").eval()
L1 = ["neutral", "angry", "positive", "sad", "other"]
m2 = None
try:
    m2 = AutoModelForAudioClassification.from_pretrained("Aniemore/wav2vec2-emotion-russian-resd").eval()
    try: fe2 = AutoFeatureExtractor.from_pretrained("Aniemore/wav2vec2-emotion-russian-resd")
    except Exception: fe2 = Wav2Vec2FeatureExtractor(feature_size=1, sampling_rate=16000, padding_value=0.0, do_normalize=True, return_attention_mask=True)
    L2 = m2.config.id2label; log("SER2 labels:", L2)
except Exception:
    log("SER2 FAIL", traceback.format_exc()[-600:]); m2 = None
ast_fe = AutoFeatureExtractor.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")
ast = ASTForAudioClassification.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593").eval()
lab2id = {v: k for k, v in ast.config.id2label.items()}
AST_G = {"шёпот": ["Whispering"], "крик": ["Shout", "Yell", "Screaming", "Children shouting", "Bellow", "Whoop"], "плач": ["Crying, sobbing", "Whimper", "Wail, moan", "Baby cry, infant cry"],
         "смех": ["Laughter", "Giggle", "Chuckle, chortle", "Snicker"], "речь": ["Speech", "Child speech, kid speaking", "Female speech, woman speaking", "Male speech, man speaking", "Narration, monologue"], "вздох": ["Sigh", "Gasp", "Breathing"]}
def acoustics(x, text):
    import parselmouth
    snd = parselmouth.Sound(x.astype(np.float64), 16000)
    f0 = snd.to_pitch(time_step=0.01, pitch_floor=90, pitch_ceiling=700).selected_array["frequency"]; v = f0[f0 > 0]
    w = 320; e = np.array([np.sqrt(np.mean(x[i:i + w] ** 2)) for i in range(0, len(x) - w, w)]); thr = max(0.006, 0.05 * np.percentile(e, 95)) if len(e) else 0
    act = np.where(e > thr)[0]; dur = (act[-1] - act[0] + 1) * w / 16000 if len(act) else len(x) / 16000
    S = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2; fr = np.fft.rfftfreq(len(x), 1 / 16000)
    hf = 10 * np.log10((S[fr >= 3000].sum() + 1e-12) / (S[(fr >= 100) & (fr < 3000)].sum() + 1e-12))
    syl = sum(c in "аеёиоуыэюя" for c in (text or "").lower())
    return dict(f0=round(float(np.median(v)), 0) if len(v) > 5 else None, range=round(float(12 * np.log2(np.percentile(v, 95) / np.percentile(v, 5))), 1) if len(v) > 5 else None,
                voiced=round(float(len(v) / max(1, len(f0))), 2), rate=round(syl / dur, 1) if syl and dur > 0 else None, hf=round(float(hf), 1), dur=round(float(dur), 2))
rows = []
for f in files:
    name = os.path.basename(f).rsplit(".", 1)[0]; tp = f"emo/{name}.txt"; text = open(tp, encoding="utf-8").read().strip() if os.path.exists(tp) else ""
    h = hashlib.md5(open(f, "rb").read() + text.encode()).hexdigest()
    if name in done and done[name].get("hash") == h: rows.append(done[name]); continue
    try:
        x = vc.load16(f); r = dict(name=name, text=text, hash=h)
        with torch.no_grad():
            p = torch.softmax(m1(fe1(x, sampling_rate=16000, return_tensors="pt", padding=True)["input_values"]).logits, -1)[0].numpy()
            r["ser1"] = {L1[i]: round(float(p[i]), 3) for i in range(len(L1))}
            if m2 is not None:
                inp = fe2(x, sampling_rate=16000, return_tensors="pt", padding=True)
                p2 = torch.softmax(m2(**{k: v for k, v in inp.items() if k in ("input_values", "attention_mask")}).logits, -1)[0].numpy()
                r["ser2"] = {str(L2[i]): round(float(p2[i]), 3) for i in range(len(p2))}
            pa = torch.sigmoid(ast(**ast_fe(x, sampling_rate=16000, return_tensors="pt")).logits)[0].numpy()
            r["ast"] = {g: round(float(max(pa[lab2id[l]] for l in ls if l in lab2id)), 3) for g, ls in AST_G.items()}
            r["ast_top"] = [[ast.config.id2label[int(i)], round(float(pa[i]), 2)] for i in np.argsort(-pa)[:5]]
            r["utmos"] = round(float(vc.utmos_model()(torch.from_numpy(x)[None], 16000)), 2)
        if text:
            heard = vc.whisper_model().transcribe(f, language="ru", fp16=False)["text"].strip(); a, b = vc.norm_words(text), vc.norm_words(heard)
            r["heard"] = heard; r["match"] = round(difflib.SequenceMatcher(None, a, b).ratio(), 3)
        r.update(acoustics(x, text)); rows.append(r); log("готово", name, r.get("ser1"), r.get("match"), r.get("utmos"))
    except Exception:
        log("FAIL", name, traceback.format_exc()[-800:])
json.dump(rows, open("emo_out/report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
k2 = sorted({k for r in rows for k in r.get("ser2", {})})
md = ["| файл | слова | UTMOS | Гц | размах | темп | яркость | " + " | ".join(L1) + " | " + " | ".join(k2) + " | " + " | ".join(AST_G) + " |", "|" + "---|" * (8 + len(L1) + len(k2) + len(AST_G))]
for r in sorted(rows, key=lambda r: r["name"]):
    md.append(f"| {r['name']} | {r.get('match', '—')} | {r.get('utmos', '—')} | {r.get('f0', '—')} | {r.get('range', '—')} | {r.get('rate', '—')} | {r.get('hf', '—')} | "
              + " | ".join(str(r.get("ser1", {}).get(k, "—")) for k in L1) + " | " + " | ".join(str(r.get("ser2", {}).get(k, "—")) for k in k2) + " | " + " | ".join(str(r.get("ast", {}).get(k, "—")) for k in AST_G) + " |")
open("emo_out/report.md", "w", encoding="utf-8").write("\n".join(md) + "\n")

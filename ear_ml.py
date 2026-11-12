"""Слух, часть 1 (Essentia): обученные сети настроения/инструментов/стиля + тональность, аккорды, темп, громкость,
линия мелодии. Пишет out/<имя>.ml.json. Запуск: python ear_ml.py todo.txt"""
import json
import os
import sys
import traceback
import urllib.request

import numpy as np
import essentia

essentia.log.warningActive = False
essentia.log.infoActive = False
import essentia.standard as es  # noqa: E402

MD = os.path.expanduser("~/models")
BASE = "https://essentia.upf.edu/models/"


def get(*rels):
    """скачать модель (пробует несколько путей), вернуть локальный путь"""
    os.makedirs(MD, exist_ok=True)
    p = os.path.join(MD, os.path.basename(rels[0]))
    if os.path.exists(p) and os.path.getsize(p) > 0:
        return p
    err = None
    for rel in rels:
        try:
            urllib.request.urlretrieve(BASE + rel, p)
            return p
        except Exception as e:  # noqa: BLE001
            err = e
    raise RuntimeError(f"не скачать {rels}: {err}")


EFF = get("feature-extractors/discogs-effnet/discogs-effnet-bs64-1.pb",
          "music-style-classification/discogs-effnet/discogs-effnet-bs64-1.pb")
MUSICNN = get("feature-extractors/musicnn/msd-musicnn-1.pb")

HEADS = [  # (имя, суффикс, какое вложение)
    ("mtg_jamendo_moodtheme", "discogs-effnet-1", "eff"),
    ("mtg_jamendo_instrument", "discogs-effnet-1", "eff"),
    ("mtg_jamendo_genre", "discogs-effnet-1", "eff"),
    ("mood_sad", "discogs-effnet-1", "eff"),
    ("mood_happy", "discogs-effnet-1", "eff"),
    ("mood_relaxed", "discogs-effnet-1", "eff"),
    ("mood_aggressive", "discogs-effnet-1", "eff"),
    ("mood_acoustic", "discogs-effnet-1", "eff"),
    ("mood_electronic", "discogs-effnet-1", "eff"),
    ("voice_instrumental", "discogs-effnet-1", "eff"),
    ("gender", "discogs-effnet-1", "eff"),
    ("tonal_atonal", "discogs-effnet-1", "eff"),
    ("approachability_regression", "discogs-effnet-1", "eff"),
    ("engagement_regression", "discogs-effnet-1", "eff"),
    ("emomusic", "msd-musicnn-2", "mn"),
    ("deam", "msd-musicnn-2", "mn"),
]
_cache = {}


def head(name, suffix):
    if name not in _cache:
        j = json.load(open(get(f"classification-heads/{name}/{name}-{suffix}.json")))
        pb = get(f"classification-heads/{name}/{name}-{suffix}.pb")
        inp = j["schema"]["inputs"][0]["name"]
        outs = [o["name"] for o in j["schema"]["outputs"] if o.get("output_purpose") == "predictions"]
        _cache[name] = (j.get("classes") or [name], es.TensorflowPredict2D(graphFilename=pb, input=inp, output=outs[0]))
    return _cache[name]


def analyze(path):
    R = {"file": os.path.basename(path)}
    a16 = es.MonoLoader(filename=path, sampleRate=16000, resampleQuality=4)()
    a44 = es.MonoLoader(filename=path, sampleRate=44100)()
    R["duration"] = round(len(a44) / 44100, 2)
    emb = {"eff": es.TensorflowPredictEffnetDiscogs(graphFilename=EFF, output="PartitionedCall:1")(a16),
           "mn": es.TensorflowPredictMusiCNN(graphFilename=MUSICNN, output="model/dense/BiasAdd")(a16)}
    R["emb_frames"] = {k: int(len(v)) for k, v in emb.items()}
    R["heads"] = {}
    for name, suf, kind in HEADS:
        try:
            classes, model = head(name, suf)
            p = np.asarray(model(emb[kind]), dtype=float)
            R["heads"][name] = {"classes": classes, "mean": p.mean(0).round(4).tolist(),
                                "series": p.round(3).tolist()}
        except Exception as e:  # noqa: BLE001
            R["heads"][name] = {"error": str(e)[:300]}
    # тональность (несколько профилей)
    R["key"] = {}
    for prof in ("krumhansl", "temperley", "edma", "bgate"):
        try:
            k, s, st = es.KeyExtractor(profileType=prof)(a44)
            R["key"][prof] = [k, s, round(float(st), 3)]
        except Exception as e:  # noqa: BLE001
            R["key"][prof] = ["?", str(e)[:80], 0]
    # темп
    try:
        bpm, beats, conf, _, _ = es.RhythmExtractor2013(method="multifeature")(a44)
        R["bpm"] = round(float(bpm), 1)
        R["bpm_conf"] = round(float(conf), 2)
    except Exception as e:  # noqa: BLE001
        R["bpm"] = None
        R["bpm_err"] = str(e)[:200]
    # громкость EBU R128 по стерео
    try:
        st, sr, nch, *_ = es.AudioLoader(filename=path)()
        if st.shape[1] == 1:
            st = np.hstack([st, st])
        mom, sht, integ, lra = es.LoudnessEBUR128(sampleRate=sr, hopSize=0.1)(st)
        R["lufs"] = round(float(integ), 1)
        R["lra"] = round(float(lra), 1)
        R["lufs_short"] = np.round(sht, 1).tolist()
        R["true_peak_dbfs"] = round(float(20 * np.log10(np.abs(st).max() + 1e-12)), 2)
    except Exception as e:  # noqa: BLE001
        R["lufs_err"] = str(e)[:200]
    # аккорды по HPCP + шероховатость (диссонанс)
    try:
        w = es.Windowing(type="blackmanharris62")
        spec = es.Spectrum()
        peaks = es.SpectralPeaks(orderBy="magnitude", magnitudeThreshold=1e-5, minFrequency=40, maxFrequency=5000, maxPeaks=60)
        peaks_f = es.SpectralPeaks(orderBy="frequency", magnitudeThreshold=1e-5, minFrequency=40, maxFrequency=8000, maxPeaks=80)
        hp12 = es.HPCP()
        diss = es.Dissonance()
        H, D = [], []
        for fr in es.FrameGenerator(a44, frameSize=4096, hopSize=2048, startFromZero=True):
            s = spec(w(fr))
            f, m = peaks(s)
            H.append(hp12(f, m))
            f2, m2 = peaks_f(s)
            D.append(float(diss(f2, m2)) if len(f2) > 1 and m2.max() > 0 else 0.0)
        H = np.array(H, dtype=np.float32)
        chords, strength = es.ChordsDetection(hopSize=2048, sampleRate=44100, windowSize=2.0)(H)
        R["chords"] = list(chords)
        R["chords_strength"] = np.round(strength, 2).tolist()
        R["chords_hop_s"] = 2048 / 44100
        R["dissonance"] = np.round(D, 3).tolist()
    except Exception as e:  # noqa: BLE001
        R["chords_err"] = traceback.format_exc()[-400:]
    # линия главной мелодии (Melodia), шаг 128 сэмплов
    try:
        pitch, conf = es.PredominantPitchMelodia(frameSize=2048, hopSize=128, guessUnvoiced=False)(es.EqualLoudness()(a44))
        R["melody_hop_s"] = 128 / 44100
        R["melody_hz"] = np.round(pitch, 2).tolist()
        R["melody_conf"] = np.round(conf, 2).tolist()
    except Exception as e:  # noqa: BLE001
        R["melody_err"] = str(e)[:200]
    return R


def main():
    os.makedirs("out", exist_ok=True)
    for line in open(sys.argv[1]):
        path = line.strip()
        if not path:
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        print("==", name, flush=True)
        try:
            R = analyze(path)
        except Exception:  # noqa: BLE001
            R = {"file": os.path.basename(path), "fatal": traceback.format_exc()[-1500:]}
            print(R["fatal"])
        json.dump(R, open(f"out/{name}.ml.json", "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()

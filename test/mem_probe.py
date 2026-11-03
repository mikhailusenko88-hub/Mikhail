#!/usr/bin/env python3
"""Сколько памяти и времени берёт голос с разными словарями ударений.
  python mem_probe.py <вариант>   варианты: tts | ra_turbo_dict | ra_tiny_dict | ra_turbo_nodict | ra_tiny_nodict | ss"""
import json, os, re, resource, sys, time
v = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
lines = [l for s in json.load(open(os.path.join(here, "scripts.json"), encoding="utf-8")) for l in s["lines"]]
lines += ["На двери висел тяжёлый замок, а на холме стоял старинный замок.", "Белки прыгают по веткам, а в мясе много белка.",
          "Все люди разные, но всё равно похожи.", "Мука нужна для теста, а не для мук.", "Он открыл окно и увидел, что идёт дождь."]
rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
t0 = time.time()
out = {"variant": v}
import torch
torch.set_num_threads(2)
marks = []
if v == "tts":
    m = torch.package.PackageImporter("/opt/multik-tts/v5_cis_base.pt").load_pickle("tts_models", "model")
    out["load_s"] = round(time.time() - t0, 1)
    ts = []
    for l in lines[:6]:
        t = time.time(); a = m.apply_tts(text=l, speaker="ru_albina", sample_rate=48000); ts.append((time.time() - t) / (len(a) / 48000))
    out["rtf_2threads"] = round(sum(ts) / len(ts), 3)
    torch.set_num_threads(1)
    t = time.time(); a = m.apply_tts(text=lines[1], speaker="ru_albina", sample_rate=48000)
    out["rtf_1thread"] = round((time.time() - t) / (len(a) / 48000), 3)
elif v.startswith("ra_"):
    from ruaccent import RUAccent
    a = RUAccent()
    size = "turbo3.1" if "turbo" in v else "tiny2"
    try:
        a.load(omograph_model_size=size, use_dictionary=("nodict" not in v))
    except Exception as e:
        a.load(omograph_model_size="tiny", use_dictionary=("nodict" not in v)); out["note"] = str(e)[:100]
    out["load_s"] = round(time.time() - t0, 1)
    marks = [a.process_all(l) for l in lines]
elif v == "ss":
    import silero_stress, inspect
    out["api"] = [n for n in dir(silero_stress) if not n.startswith("_")]
    acc = silero_stress.load_accentor()
    out["load_s"] = round(time.time() - t0, 1)
    try:
        out["sig"] = str(inspect.signature(acc.__call__ if hasattr(acc, "__call__") else acc))[:200]
    except Exception:
        pass
    marks = [acc(l) for l in lines]
out["rss_mb"] = rss()
out["marks"] = marks
print(json.dumps(out, ensure_ascii=False))

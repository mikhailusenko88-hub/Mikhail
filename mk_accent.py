#!/usr/bin/env python3
# Ударения ruaccent (независимый словарь) для реплик мультика: python mk_accent.py <index.json> <out.json>
import json, sys
from ruaccent import RUAccent
idx = json.load(open(sys.argv[1], encoding="utf-8"))
acc = RUAccent()
for size in ["turbo3.1", "turbo3", "turbo2", "turbo", "tiny2", "tiny"]:
    try:
        acc.load(omograph_model_size=size, use_dictionary=True); break
    except Exception:
        continue
out = {}
for k, v in idx.items():
    try: out[k] = acc.process_all(v["t"])
    except Exception as e: out[k] = None
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("готово", len(out))

"""Рендер роликов из плана: python3 render_day.py <день> [слот]  ->  out/dDD_S.mp4 + out/dDD_S.txt (название + описание)"""
import json
import sys
from pathlib import Path

import quotecard as qc
from quotes_bank import QUOTES

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)


def build(v, mark=None):
    segs = []
    for q_, s in zip(v["quotes"], v["scenes"]):
        d = QUOTES[q_]
        segs.append(dict(scene=s, ru=d["ru"], en=d["en"], author_ru=d["author_ru"], author_en=d["author_en"]))
    cfg = dict(music=v["music"], seed=v["seed"], segments=segs)
    if mark:
        cfg["mark"] = mark
    return cfg


if __name__ == "__main__":
    day = int(sys.argv[1])
    slot = int(sys.argv[2]) if len(sys.argv) > 2 else None
    videos = json.loads((HERE / "schedule_30d.json").read_text(encoding="utf-8"))
    for v in videos:
        if v["day"] != day or (slot and v["slot"] != slot):
            continue
        out = OUT / f"{v['name']}.mp4"
        if out.exists():
            print("уже есть", out)
            continue
        print(f"== {v['name']} {v['date']} {v['time']} | {v['quotes']} | {v['scenes']} | {v['music']}", flush=True)
        qc.render_multi(build(v), str(out))
        (OUT / f"{v['name']}.txt").write_text(v["title"] + "\n\n" + v["description"] + "\n", encoding="utf-8")

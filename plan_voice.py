"""Свои мелодии с низким голосом — через один ролик, начиная с заданного номера.
python3 plan_voice.py <номер первого ролика с новой мелодией>
Ролики start, start+2, start+4… получают стили golos_* по кругу; прежний стиль сохраняется в поле music_was.
Остальные ролики остаются с прежней оркестровой музыкой."""
import json
import sys
from pathlib import Path

import voice_music as vm

PLAN = Path(__file__).parent / "schedule_30d.json"

if __name__ == "__main__":
    start = int(sys.argv[1])
    videos = json.loads(PLAN.read_text(encoding="utf-8"))
    k = 0
    for v in sorted(videos, key=lambda v: v["n"]):
        if v["n"] < start:
            continue
        if (v["n"] - start) % 2 == 0:
            v.setdefault("music_was", v["music"])
            v["music"] = vm.ORDER[k % len(vm.ORDER)]
            k += 1
        elif "music_was" in v:                      # при пересчёте с другого номера возвращаем прежнюю музыку
            v["music"] = v.pop("music_was")
    PLAN.write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"роликов с голосом: {k}, с №{start}; дни:", sorted({v['day'] for v in videos if v['music'] in vm.STYLES})[:3], "…")

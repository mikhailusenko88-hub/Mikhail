"""Замена звука в уже готовых роликах дня — картинка не перерисовывается.
python3 remusic_day.py <день> <папка с готовыми роликами дня>  ->  out/ (все файлы дня)
У роликов, которым в schedule_30d.json назначен стиль golos_* (свои мелодии с низким голосом), звук заменяется;
остальные копируются как есть."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import fastvid as fv
import voice_music as vm

HERE = Path(__file__).parent
OUT = HERE / "out"


def probe(path):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,channels,nb_frames,r_frame_rate,duration",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    st = json.loads(o)["streams"]
    v = [s for s in st if s["codec_type"] == "video"][0]
    a = [s for s in st if s["codec_type"] == "audio"]
    num, den = map(int, v["r_frame_rate"].split("/"))
    vdur = int(v["nb_frames"]) * den / num if v.get("nb_frames", "N/A").isdigit() else float(v["duration"])
    return dict(vdur=vdur, channels=int(a[0]["channels"]) if a else 0, adur=float(a[0]["duration"]) if a else 0.0)


if __name__ == "__main__":
    day, src = int(sys.argv[1]), Path(sys.argv[2])
    OUT.mkdir(exist_ok=True)
    videos = [v for v in json.loads((HERE / "schedule_30d.json").read_text(encoding="utf-8")) if v["day"] == day]
    if not videos:
        sys.exit(f"в плане нет дня {day}")
    for v in videos:
        s, o = src / f"{v['name']}.mp4", OUT / f"{v['name']}.mp4"
        if not s.exists():
            sys.exit(f"нет готового ролика {s} — сначала рендер дня")
        if v["music"] in vm.STYLES:
            p = probe(s)
            audio = vm.make_music(v["music"], p["vdur"], v["seed"] + 100)
            fv.mux_stereo(s, audio, o)
            q = probe(o)
            if q["channels"] != 2 or abs(q["vdur"] - p["vdur"]) > 0.05 or abs(q["adur"] - p["vdur"]) > 0.15:
                sys.exit(f"{v['name']}: после замены звука что-то не так: {q} (было {p})")
            print(f"== {v['name']}: новый звук {v['music']} (был {v.get('music_was', '?')}), {q['vdur']:.2f} с", flush=True)
        else:
            shutil.copy2(s, o)
            print(f"== {v['name']}: без изменений ({v['music']})", flush=True)
        (OUT / f"{v['name']}.txt").write_text(v["title"] + "\n\n" + v["description"] + "\n", encoding="utf-8")

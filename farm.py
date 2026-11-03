#!/usr/bin/env python3
"""Озвучка заранее (в GitHub Actions): тексты будущих роликов «Почему так?» -> готовые фразы голосом Альбины.
Бот на сервере (961 МБ памяти) голос не запускает — только скачивает эти фразы.

  ALBINA_NO_GH=1 python farm.py <bank.json или адрес> <папка> [--prev ПАПКА] [--shard i/n] [--max-minutes M]
  python farm.py --merge <bank.json> <папка> <часть1> <часть2> …   — собрать части в одну папку и убрать лишнее

В папке: v/<ключ>.mp3 (ключ — albina.cache_key), index.json {ключ: {"t": текст, "m": с ударениями}}, report.md.
Фразы идут в порядке банка — первыми озвучиваются ближайшие ролики."""
import argparse
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

os.environ["ALBINA_NO_GH"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import albina  # noqa: E402


def load_bank(src):
    if src.startswith("http"):
        with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "albina-farm"}), timeout=60) as r:
            return json.load(r)
    return json.loads(Path(src).read_text(encoding="utf-8"))


def needed(bank):
    need = {}
    for voice in bank.get("voices") or ["albina"]:
        st = bank.get("selftest") or albina.SELFTEST_TEXT
        need[albina.cache_key(st, voice)] = (st, voice)
        for s in bank.get("scripts", []):
            for line in s.get("lines", []):
                need.setdefault(albina.cache_key(line, voice), (line, voice))
    return need


def read_index(d):
    p = Path(d) / "index.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def merge(bank, out, parts):
    out = Path(out)
    (out / "v").mkdir(parents=True, exist_ok=True)
    index = read_index(out)
    for part in parts:
        for f in Path(part).glob("**/v/*.mp3"):
            shutil.copyfile(f, out / "v" / f.name)
        for ip in Path(part).glob("**/index.json"):
            index.update(read_index(ip.parent))
    need = needed(bank)
    removed = 0
    if bank.get("scripts"):
        for f in (out / "v").glob("*.mp3"):
            if f.stem not in need:
                f.unlink(); removed += 1
    index = {k: v for k, v in index.items() if k in need and (out / "v" / f"{k}.mp3").exists()}
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    have = sum(1 for k in need if (out / "v" / f"{k}.mp3").exists())
    # сколько ближайших сценариев озвучено целиком
    full = 0
    for s in bank.get("scripts", []):
        if all((out / "v" / f"{albina.cache_key(l, (bank.get('voices') or ['albina'])[0])}.mp3").exists() for l in s["lines"]):
            full += 1
        else:
            break
    size = sum(f.stat().st_size for f in (out / "v").glob("*.mp3")) / 1e6
    rep = [f"# Озвучка заранее — {time.strftime('%Y-%m-%d %H:%M')} UTC",
           f"- сценариев в банке: {len(bank.get('scripts', []))}, фраз: {len(need)}, озвучено: {have}",
           f"- ближайших сценариев готово подряд: {full}",
           f"- убрано старых: {removed}, папка: {size:.1f} МБ",
           f"- тексты выложены сервером: {bank.get('updated')}, ИИ-сценарии: {'включены' if bank.get('use_ai') else 'нет'}",
           "", "## Пример ударений"] + [f"- {v['m']}" for v in list(index.values())[:12]]
    (out / "report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))


def farm(bank, out, prev=None, shard=(0, 1), max_minutes=0):
    out = Path(out).resolve()
    (out / "v").mkdir(parents=True, exist_ok=True)
    prev = Path(prev) if prev else out
    pindex = read_index(prev)
    index = read_index(out) if out != prev else dict(pindex)
    need = needed(bank)
    i, n = shard
    t0, made, kept, fail = time.time(), 0, 0, []
    for key, (line, voice) in need.items():
        if int(key[:8], 16) % n != i:
            continue
        old = prev / "v" / f"{key}.mp3"
        if old.exists() and old.stat().st_size > 2000 and key in pindex:
            kept += 1
            continue
        if max_minutes and time.time() - t0 > max_minutes * 60:
            print(f"! время вышло — остальное в следующий раз (озвучено {made})")
            break
        try:
            albina.say(line, voice, out / "v" / f"{key}.mp3")
            index[key] = {"t": line, "m": albina._st["last"]}
            made += 1
        except Exception as e:
            fail.append(f"{line} — {e}")
            print("  не вышло:", line[:60], "—", str(e)[:200], flush=True)
            if len(fail) >= 5 and not made:
                print("! 5 фраз подряд не озвучились — останавливаюсь"); break
        if made and made % 25 == 0:
            (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
            print(f"  часть {i}/{n}: озвучено {made}, {time.time() - t0:.0f} с", flush=True)
    albina.close()
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"часть {i}/{n}: новых {made}, уже были {kept}, не вышло {len(fail)}, {time.time() - t0:.0f} с")
    for x in fail[:20]:
        print("  не вышло:", x)
    return made, kept, fail


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--merge":
        merge(load_bank(sys.argv[2]), sys.argv[3], sys.argv[4:])
        sys.exit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("bank"); ap.add_argument("out")
    ap.add_argument("--prev"); ap.add_argument("--shard", default="0/1"); ap.add_argument("--max-minutes", type=float, default=0)
    a = ap.parse_args()
    b = load_bank(a.bank)
    si, sn = (int(x) for x in a.shard.split("/"))
    made, kept, fail = farm(b, a.out, a.prev, (si, sn), a.max_minutes)
    if sn == 1 and not a.prev:
        merge(b, a.out, [])
    sys.exit(1 if fail and not made and not kept else 0)

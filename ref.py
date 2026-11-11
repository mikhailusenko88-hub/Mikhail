"""request.txt: строка 1 — канал или ссылка на ролик; строка 2 — слова для поиска в названии (через |)."""
import json, os, re, subprocess, sys, glob
os.makedirs("out", exist_ok=True); os.makedirs("status", exist_ok=True)
req = [l.strip() for l in open("request.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
src = req[0]
pat = re.compile(req[1], re.I) if len(req) > 1 else None
CLIENTS = ["default", "android_vr", "ios", "tv", "mweb", "web_safari", "tv_embedded"]

def run(cmd, timeout=600):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p

def P(*a):
    print(*a, flush=True)

items = []
if "watch?v=" in src or "/shorts/" in src or "youtu.be" in src:
    items = [dict(id=src, title="(ссылка)")]
else:
    for tab in ("shorts", "videos", "streams"):
        p = run(["yt-dlp", "--flat-playlist", "-J", "--extractor-args", "youtube:player_client=default,web_safari,ios,tv", f"{src.rstrip('/')}/{tab}"], 300)
        try:
            d = json.loads(p.stdout)
            ents = d.get("entries") or []
        except Exception:
            ents = []
            P(tab, "ошибка:", p.stderr[-300:])
        for e in ents:
            items.append(dict(id=e.get("id"), title=e.get("title") or "", tab=tab, dur=e.get("duration")))
        P(tab, len(ents))
with open("status/list.txt", "w", encoding="utf-8") as f:
    for it in items:
        f.write(f"{it.get('tab','')}\t{it['id']}\t{it.get('dur')}\t{it['title']}\n")
hits = [it for it in items if (pat.search(it["title"]) if pat else True)] if pat else items[:1]
# метаданные (описание, место, музыка из ролика) — для роликов, снятых вживую (не сгенерированных)
GEN = re.compile(r"ring|ball|vs |who wins|grows|bounce|glass|trend|watercolor|escape|country", re.I)
meta_lines = []
only = [x.strip() for x in (req[2].split(",") if len(req) > 2 else []) if x.strip()]
scan = [it for it in items if not GEN.search(it["title"])]
for it in scan:
    p = run(["yt-dlp", "--skip-download", "-J", "--extractor-args", "youtube:player_client=default,web_safari,ios,tv,mweb", f"https://www.youtube.com/watch?v={it['id']}"], 120)
    try:
        d = json.loads(p.stdout)
    except Exception:
        meta_lines.append(f"{it['id']}\t{it['title']}\tМЕТА НЕ ПОЛУЧЕНА: {(p.stderr or '')[-160:]}")
        continue
    info = dict(date=d.get("upload_date"), dur=d.get("duration"), track=d.get("track"), artist=d.get("artist") or d.get("creator"), album=d.get("album"),
                loc=d.get("location"), desc=(d.get("description") or "")[:300].replace("\n", " "), tags=",".join(d.get("tags") or [])[:200])
    it.update(info)
    meta_lines.append(f"{it['id']}\t{it['title']}\t" + json.dumps(info, ensure_ascii=False))
    blob = " ".join(str(v) for v in info.values()) + " " + it["title"]
    if pat and pat.search(blob) and it not in hits:
        hits.append(it)
open("status/meta.txt", "w", encoding="utf-8").write("\n".join(meta_lines))
for x in only:
    hits.append(dict(id=x, title=next((i["title"] for i in items if i["id"] == x), x)))
P("с метаданными — совпадений:", [(h["id"], h["title"]) for h in hits])
P("совпадений:", len(hits), [h["title"] for h in hits])
report = []
for h in hits[:6]:
    url = h["id"] if h["id"].startswith("http") else f"https://www.youtube.com/watch?v={h['id']}"
    base = f"out/{re.sub(r'[^A-Za-z0-9_-]', '_', h['id'])[-11:]}"
    got = None
    for cl in CLIENTS:
        for f in glob.glob(base + ".*"):
            os.remove(f)
        args = ["yt-dlp", "-f", "bestaudio/best", "-o", base + ".%(ext)s", url]
        if cl != "default":
            args[1:1] = ["--extractor-args", f"youtube:player_client={cl}"]
        p = run(args, 300)
        fs = [f for f in glob.glob(base + ".*") if not f.endswith(".part")]
        if fs:
            got = fs[0]; P("скачано через", cl, got); break
        P("не скачалось через", cl, (p.stderr or "")[-200:].replace("\n", " "))
    if not got:
        report.append(f"## {h['title']} ({url})\nСкачать не удалось.\n")
        continue
    wav = base + ".wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", got, "-ac", "2", "-ar", "22050", wav])
    p = run([sys.executable, "analyze_ref.py", wav, h["title"], url], 900)
    report.append(p.stdout + ("\nОШИБКА: " + p.stderr[-1500:] if p.returncode else ""))
open("status/report.md", "w", encoding="utf-8").write("\n\n".join(report) or "нет совпадений")
P("\n".join(report))

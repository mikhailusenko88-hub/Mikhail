"""Страницы роликов (без скачивания видео): название, описание, место, звук/музыка из ролика."""
import json, re, subprocess, sys, html
ids = [l.split("\t") for l in open("status/list.txt", encoding="utf-8") if l.strip()]
GEN = re.compile(r"ring|ball|vs |who wins|grows|bounce|glass|trend|watercolor|escape|country", re.I)
out = []
for tab, vid, dur, title in [(x + ["", "", "", ""])[:4] for x in ids]:
    if GEN.search(title):
        continue
    url = f"https://www.youtube.com/shorts/{vid}" if tab == "shorts" else f"https://www.youtube.com/watch?v={vid}"
    p = subprocess.run(["curl", "-sL", "--max-time", "25", "-H", "Accept-Language: ru,en;q=0.8", "-H", "Cookie: CONSENT=YES+1; SOCS=CAI",
                        "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", url], capture_output=True, text=True)
    h = p.stdout
    rec = {"id": vid, "title": title.strip(), "len": len(h)}
    m = re.search(r'"shortDescription":"(.*?)","', h)
    rec["desc"] = m.group(1)[:300] if m else None
    m = re.search(r'"keywords":\[(.*?)\]', h)
    rec["kw"] = m.group(1)[:200] if m else None
    snd = set()
    for pat in [r'"soundAttribution[^"]*":\{[^}]*?"text":"([^"]+)"', r'"songTitle":"([^"]+)"', r'"musicTitle":"([^"]+)"', r'"song":\{"simpleText":"([^"]+)"',
                r'"artist":\{"simpleText":"([^"]+)"', r'"title":"([^"]{2,80})","subtitle":"([^"]{2,80})"', r'"reelSoundMetadataRenderer".{0,400}?"text":"([^"]+)"',
                r'"musicCardRenderer".{0,600}?"text":"([^"]+)"', r'"videoAttributeViewModel".{0,500}?"title":"([^"]+)".{0,200}?"subtitle":"([^"]+)"',
                r'"originalAudioAttribution".{0,300}?"text":"([^"]+)"', r'"soundMetadata".{0,300}?"text":"([^"]+)"']:
        for mm in re.finditer(pat, h):
            snd.add(" · ".join(g for g in mm.groups() if g))
    for key in ("videoDescriptionMusicSectionRenderer", "musicAttribution", "soundAttribution", "reelSound", "carouselLockupRenderer", "infoRowRenderer"):
        for mm in re.finditer(key, h):
            chunk = h[mm.start(): mm.start() + 2500]
            for c in re.findall(r'"(?:content|simpleText|text)":"([^"]{2,100})"', chunk)[:10]:
                snd.add(key[:12] + ": " + c)
    rec["sound"] = sorted(snd)[:20]
    m = re.search(r'"location":\{[^}]*?"text":"([^"]+)"', h) or re.search(r'"locationText":"([^"]+)"', h)
    rec["loc"] = m.group(1) if m else None
    rec["milan"] = bool(re.search(r"milan|милан|duomo|milano", h, re.I))
    mm = re.search(r"milan|милан|duomo|milano", h, re.I)
    i = mm.start() if mm else -1
    rec["milan_ctx"] = html.unescape(h[max(0, i - 300): i + 300]) if i >= 0 else None
    out.append(rec)
    print(json.dumps(rec, ensure_ascii=False)[:600], flush=True)
open("status/pages.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))

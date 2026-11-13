"""Аналитика YouTube для ветки yt-status: история просмотров, скан ниш (поиск, хэштеги), детали роликов.

Вызывается из yt_check.py. Всё — только чтение открытых данных YouTube.

  history/channels-YYYY-MM.csv  — подписчики и число роликов каждого канала на момент проверки
  history/videos-YYYY-MM.csv    — просмотры каждого ролика на момент проверки (rss = точно, tab = округлено)
  history/scans-YYYY-MM.csv     — что выдаёт YouTube по запросам и хэштегам ниш (топы, соседи)
  status/scans/<slug>.json|md   — последний скан каждого запроса
"""
import csv
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HIST = Path("history")
SCANS = Path("status") / "scans"


# ---------- числа и даты ----------

def num(s):
    """'1,2 тыс. просмотров' -> 1200, '36 подписчиков' -> 36, '1 053' -> 1053, '1 тысяча' -> 1000."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    s = str(s).replace("\xa0", " ").replace(" ", " ").lower()
    s = re.sub(r"(?<=\d) (?=\d{3}\b)", "", s)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(тыс|млн|млрд|k|m|b|thousand|million)?", s)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    mult = {"тыс": 1e3, "k": 1e3, "thousand": 1e3, "млн": 1e6, "m": 1e6, "million": 1e6, "млрд": 1e9, "b": 1e9}
    return int(round(v * mult.get(m.group(2) or "", 1)))


def age_hours(txt):
    """'5 часов назад' -> 5, '2 дня назад' -> 48, '1 неделю назад' -> 168. None если не понять."""
    if not txt:
        return None
    t = txt.lower()
    m = re.search(r"(\d+)\s*(сек|мин|час|дн|день|недел|месяц|мес|год|лет|second|minute|hour|day|week|month|year)", t)
    if not m:
        return None
    n = int(m.group(1))
    u = m.group(2)
    for keys, h in ((("сек", "second"), 1 / 3600), (("мин", "minute"), 1 / 60), (("час", "hour"), 1),
                    (("дн", "день", "day"), 24), (("недел", "week"), 168), (("месяц", "мес", "month"), 720),
                    (("год", "лет", "year"), 8760)):
        if u.startswith(keys):
            return n * h
    return None


def hashtags(*texts):
    out = []
    for t in texts:
        out += [h.lower() for h in re.findall(r"#[\wЀ-ӿӘ-ө]+", t or "")]
    return out


def hist_append(name, header, rows, now):
    if not rows:
        return
    HIST.mkdir(exist_ok=True)
    path = HIST / f"{name}-{now.strftime('%Y-%m')}.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


# ---------- запись истории каналов ----------

def record_channel(info, now, tab_rows=True, tab_limit=60):
    stamp = now.strftime("%Y-%m-%d %H:%M")
    h = info.get("handle")
    subs = vids = None
    for p in info.get("header") or []:
        if re.search(r"подпис|subscri", p, re.I):
            subs = num(p)
        elif re.search(r"видео|video", p, re.I):
            vids = num(p)
    hist_append("channels", ["checked_utc", "handle", "channel_id", "subs", "videos", "page_status"],
                [[stamp, h, info.get("channel_id"), subs, vids, info.get("page_status")]], now)
    rows, in_rss = [], set()
    for r in info.get("rss") or []:
        in_rss.add(r["id"])
        rows.append([stamp, h, r["id"], r.get("published", "")[:16], r.get("views"), "rss", r.get("title", "")[:150]])
    if tab_rows:
        for s in (info.get("shorts") or [])[:tab_limit]:
            if s.get("id") and s["id"] not in in_rss:
                rows.append([stamp, h, s["id"], "", num(s.get("views")), "tab", (s.get("title") or "")[:150]])
    hist_append("videos", ["checked_utc", "handle", "video_id", "published_utc", "views", "src", "title"], rows, now)


# ---------- разбор страниц ----------

def _text(x):
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        if "simpleText" in x:
            return x["simpleText"]
        if isinstance(x.get("content"), str):
            return x["content"]
        if "runs" in x:
            return "".join(r.get("text", "") for r in x["runs"])
    return ""


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def parse_items(d):
    """Ролики из ytInitialData любой страницы (поиск, хэштег, вкладка канала)."""
    items = []
    for node in _walk(d):
        if "videoRenderer" in node and isinstance(node["videoRenderer"], dict):
            v = node["videoRenderer"]
            runs = (v.get("ownerText") or v.get("longBylineText") or {}).get("runs") or [{}]
            be = ((runs[0].get("navigationEndpoint") or {}).get("browseEndpoint") or {})
            length = _text(v.get("lengthText", {}))
            nav = v.get("navigationEndpoint") or {}
            is_short = "reelWatchEndpoint" in nav or (length and re.fullmatch(r"0?:?[0-5]?\d|1:00|0:\d\d", length) is not None)
            items.append({"id": v.get("videoId"), "kind": "short" if is_short else "video",
                          "title": _text(v.get("title", {})), "views": num(_text(v.get("viewCountText", {}))),
                          "views_txt": _text(v.get("viewCountText", {})), "age": _text(v.get("publishedTimeText", {})),
                          "length": length, "channel": runs[0].get("text", ""),
                          "handle": (be.get("canonicalBaseUrl") or "").lstrip("/"), "channel_id": be.get("browseId", ""),
                          "snippet": " ".join(_text(s.get("snippetText", {})) for s in v.get("detailedMetadataSnippets") or [])})
        elif "shortsLockupViewModel" in node and isinstance(node["shortsLockupViewModel"], dict):
            v = node["shortsLockupViewModel"]
            vid = None
            for n in _walk(v):
                if "reelWatchEndpoint" in n:
                    vid = n["reelWatchEndpoint"].get("videoId")
                    break
            om = v.get("overlayMetadata", {})
            items.append({"id": vid, "kind": "short", "title": _text(om.get("primaryText", {})),
                          "views": num(_text(om.get("secondaryText", {}))), "views_txt": _text(om.get("secondaryText", {})),
                          "age": "", "length": "", "channel": "", "handle": "", "channel_id": "", "snippet": ""})
        elif "reelItemRenderer" in node and isinstance(node["reelItemRenderer"], dict):
            v = node["reelItemRenderer"]
            items.append({"id": v.get("videoId"), "kind": "short", "title": _text(v.get("headline", {})),
                          "views": num(_text(v.get("viewCountText", {}))), "views_txt": _text(v.get("viewCountText", {})),
                          "age": "", "length": "", "channel": "", "handle": "", "channel_id": "", "snippet": ""})
    seen, out = set(), []
    for it in items:
        if it["id"] and it["id"] not in seen:
            seen.add(it["id"])
            out.append(it)
    return out


# ---------- детали ролика ----------

def player(vid, headers, log):
    """Детали через youtubei/v1/player: длина, теги, описание, дата, автор. Пусто, если YouTube не отдал."""
    out = {}
    for client in ({"clientName": "WEB", "clientVersion": "2.20251105.01.00"},
                   {"clientName": "ANDROID", "clientVersion": "19.44.38", "androidSdkVersion": 34}):
        body = json.dumps({"context": {"client": {**client, "hl": "ru", "gl": "RU"}}, "videoId": vid}).encode()
        req = urllib.request.Request("https://www.youtube.com/youtubei/v1/player?prettyPrint=false", data=body,
                                     headers={**headers, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                j = json.loads(r.read().decode("utf-8", "ignore"))
            log.append(f"200 player {client['clientName']} {vid}")
        except Exception as e:  # noqa: BLE001
            log.append(f"ERR player {client['clientName']} {vid} {e}")
            continue
        vd = j.get("videoDetails") or {}
        mf = (j.get("microformat") or {}).get("playerMicroformatRenderer") or {}
        if vd:
            out = {"length_s": int(vd.get("lengthSeconds") or 0) or None, "keywords": vd.get("keywords") or [],
                   "description": (vd.get("shortDescription") or "")[:1500], "views": num(vd.get("viewCount")),
                   "author": vd.get("author"), "channel_id": vd.get("channelId"),
                   "publish": mf.get("publishDate") or mf.get("uploadDate") or "", "category": mf.get("category", ""),
                   "playability": (j.get("playabilityStatus") or {}).get("status"), "client": client["clientName"]}
            if out["publish"] or client["clientName"] == "ANDROID":
                return out
    return out


def oembed(vid, headers, log):
    u = f"https://www.youtube.com/oembed?url=https://www.youtube.com/shorts/{vid}&format=json"
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=headers), timeout=20) as r:
            j = json.loads(r.read().decode("utf-8", "ignore"))
        return {"channel": j.get("author_name", ""), "handle": (j.get("author_url") or "").rsplit("/", 1)[-1]}
    except Exception as e:  # noqa: BLE001
        log.append(f"ERR oembed {vid} {e}")
        return {}


# ---------- скан ниши ----------

SEARCH_SP = {"": "", "week": "EgIIAw%253D%253D", "shorts": "EgIQCQ%253D%253D", "views": "CAM%253D"}


def scan_url(kind, q):
    qq = urllib.parse.quote(q)
    if kind == "hashtag":
        return f"https://www.youtube.com/hashtag/{urllib.parse.quote(q.lstrip('#'))}/shorts"
    sp = SEARCH_SP.get(kind.split("-", 1)[1] if "-" in kind else "", "")
    return f"https://www.youtube.com/results?search_query={qq}" + (f"&sp={sp}" if sp else "")


def slugify(s):
    return re.sub(r"[^\w]+", "_", s, flags=re.U).strip("_")[:60] or "scan"


def run_scan(spec, get, initial_data, headers, log, now, details_top=12):
    """spec: 'search:цитаты' | 'search-week:цитаты' | 'search-shorts:...' | 'hashtag:цитаты'."""
    kind, q = spec.split(":", 1)
    kind, q = kind.strip(), q.strip()
    st, html = get(scan_url(kind, q))
    d = initial_data(html) if html else {}
    items = parse_items(d)
    header = ""
    if kind == "hashtag":
        for node in _walk(d.get("header", {})):
            for k in ("content", "simpleText"):
                v = node.get(k) if isinstance(node, dict) else None
                if isinstance(v, str) and re.search(r"\d", v) and re.search(r"видео|канал|video|channel", v, re.I):
                    header += v + " · "
    # кто автор и какие теги — у первых роликов
    for it in items[:details_top]:
        if not it["handle"]:
            it.update({k: v for k, v in oembed(it["id"], headers, log).items() if v})
        det = player(it["id"], headers, log)
        if det:
            it["det"] = det
            if not it.get("views") and det.get("views"):
                it["views"] = det["views"]
        time.sleep(0.7)
    for it in items:
        it["age_h"] = age_hours(it.get("age"))
        if not it["age_h"] and (it.get("det") or {}).get("publish"):
            try:
                p = datetime.fromisoformat(it["det"]["publish"].replace("Z", "+00:00"))
                if p.tzinfo is None:
                    p = p.replace(tzinfo=timezone.utc)
                it["age_h"] = max(1.0, (now - p).total_seconds() / 3600)
            except Exception:  # noqa: BLE001
                pass
        it["per_day"] = int(it["views"] / max(it["age_h"], 1) * 24) if it.get("views") and it.get("age_h") else None
        it["tags"] = sorted(set(hashtags(it.get("title"), (it.get("det") or {}).get("description"))))
    res = {"spec": spec, "url": scan_url(kind, q), "status": st, "checked": now.strftime("%Y-%m-%d %H:%M UTC"),
           "header": header.strip(" ·"), "items": items}
    SCANS.mkdir(parents=True, exist_ok=True)
    slug = slugify(spec)
    (SCANS / f"{slug}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    stamp = now.strftime("%Y-%m-%d %H:%M")
    hist_append("scans", ["checked_utc", "scan", "rank", "video_id", "kind", "handle", "channel", "views", "age_h",
                          "length_s", "title", "tags"],
                [[stamp, spec, i + 1, it["id"], it["kind"], it.get("handle", ""), it.get("channel", ""), it.get("views"),
                  round(it["age_h"], 1) if it.get("age_h") else "", (it.get("det") or {}).get("length_s") or "",
                  (it.get("title") or "")[:150], " ".join(it["tags"])] for i, it in enumerate(items[:40])], now)
    # короткая сводка
    md = [f"# Скан: {spec}", f"Проверено: {res['checked']} · HTTP {st} · найдено {len(items)}",
          f"Ссылка: {res['url']}", ""]
    if res["header"]:
        md.append(f"Хэштег: {res['header']}\n")
    md.append("| # | просм. | возраст | в сутки | канал | длит. | название |")
    md.append("|---|---|---|---|---|---|---|")
    for i, it in enumerate(items[:30]):
        age = f"{it['age_h']:.0f} ч" if it.get("age_h") and it["age_h"] < 72 else (f"{it['age_h'] / 24:.0f} дн" if it.get("age_h") else "?")
        md.append(f"| {i + 1} | {it.get('views') or '?'} | {age} | {it.get('per_day') or '?'} | {it.get('channel') or '?'} "
                  f"(@{it.get('handle', '').lstrip('@') or '?'}) | {(it.get('det') or {}).get('length_s') or it.get('length') or '?'} | "
                  f"{(it.get('title') or '').replace('|', '/')[:90]} |")
    tags = Counter()
    for it in items[:30]:
        for t in it["tags"]:
            tags[t] += 1
    if tags:
        md += ["", "Хэштеги у первых 30: " + ", ".join(f"{t} ×{n}" for t, n in tags.most_common(25))]
    (SCANS / f"{slug}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return res


# ---------- списки для ежедневного обхода ----------

def read_list(path):
    """channels.txt / scans.txt: строки без # ; в channels.txt формат '@handle  группа  своя|сосед'."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip() if not line.strip().startswith(("search", "hashtag")) else line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out

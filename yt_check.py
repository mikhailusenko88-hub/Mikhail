"""Проверка YouTube-каналов (публичные данные) для отчёта в ветку yt-status.

Читает request.txt:
  @handle        — канал: подписчики, число роликов, последние Shorts и ролики с просмотрами
  video:ID       — отдельный ролик: открыт ли он (oEmbed: 200 = открыт, 401/403 = закрыт, 404 = удалён)
  # ...          — комментарий (меняй его, чтобы перезапустить проверку)
Пишет status/<handle>.md, status/<handle>.json, status/videos.md, status/_log.txt.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Cookie": "CONSENT=YES+1; SOCS=CAI",
}
OUT = Path("status")
OUT.mkdir(exist_ok=True)
LOG = []


def get(url):
    req = urllib.request.Request(url, headers=H)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read().decode("utf-8", "ignore")
            LOG.append(f"{r.status} {url}")
            return r.status, body
    except urllib.error.HTTPError as e:
        LOG.append(f"{e.code} {url}")
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        LOG.append(f"ERR {url} {e}")
        return 0, ""


def initial_data(html):
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", html, re.S) or \
        re.search(r"ytInitialData\"\]\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:  # noqa: BLE001
        return {}


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def text_of(x):
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        if "simpleText" in x:
            return x["simpleText"]
        if "content" in x and isinstance(x["content"], str):
            return x["content"]
        if "runs" in x:
            return "".join(r.get("text", "") for r in x["runs"])
    return ""


def channel_info(handle):
    st, html = get(f"https://www.youtube.com/@{handle}")
    info = {"handle": handle, "page_status": st}
    if not html:
        return info
    m = re.search(r'"externalId":"(UC[\w-]{22})"', html) or re.search(r'"channelId":"(UC[\w-]{22})"', html)
    info["channel_id"] = m.group(1) if m else None
    d = initial_data(html)
    md = d.get("metadata", {}).get("channelMetadataRenderer", {})
    info["title"] = md.get("title")
    info["description"] = (md.get("description") or "")[:200]
    # строки шапки: «N подписчиков», «N видео»
    header = d.get("header", {})
    parts = []
    for node in walk(header):
        for k in ("content", "simpleText"):
            v = node.get(k)
            if isinstance(v, str) and re.search(r"\d", v) and re.search(r"подпис|subscri|видео|video", v, re.I):
                parts.append(v)
    info["header"] = list(dict.fromkeys(parts))
    # предупреждения на странице (если канал ограничен/удалён)
    alerts = []
    for node in walk(d.get("alerts", [])):
        t = text_of(node.get("text", "")) if isinstance(node, dict) else ""
        if t:
            alerts.append(t)
    info["alerts"] = alerts
    return info


def shorts_tab(handle):
    st, html = get(f"https://www.youtube.com/@{handle}/shorts")
    items = []
    d = initial_data(html) if html else {}
    for node in walk(d):
        if "shortsLockupViewModel" in node:
            v = node["shortsLockupViewModel"]
            vid = None
            for n in walk(v):
                if "reelWatchEndpoint" in n:
                    vid = n["reelWatchEndpoint"].get("videoId")
                    break
            om = v.get("overlayMetadata", {})
            items.append({"id": vid,
                          "title": text_of(om.get("primaryText", {})),
                          "views": text_of(om.get("secondaryText", {})),
                          "a11y": v.get("accessibilityText", "")})
        elif "reelItemRenderer" in node:
            v = node["reelItemRenderer"]
            items.append({"id": v.get("videoId"), "title": text_of(v.get("headline", {})),
                          "views": text_of(v.get("viewCountText", {})), "a11y": ""})
    seen, uniq = set(), []
    for it in items:
        if it["id"] and it["id"] not in seen:
            seen.add(it["id"])
            uniq.append(it)
    return st, uniq


def rss(cid):
    st, xml = get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
    rows = []
    if not xml:
        return st, rows
    ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/",
          "yt": "http://www.youtube.com/xml/schemas/2015"}
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return st, rows
    for e in root.findall("a:entry", ns):
        stat = e.find("m:group/m:community/m:statistics", ns)
        rows.append({
            "id": (e.find("yt:videoId", ns).text if e.find("yt:videoId", ns) is not None else ""),
            "published": e.find("a:published", ns).text,
            "title": e.find("a:title", ns).text,
            "views": int(stat.get("views")) if stat is not None and stat.get("views") else None,
        })
    return st, rows


def video_status(vid):
    st, body = get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json")
    meaning = {200: "открыт (виден всем или по ссылке)", 401: "закрыт (частный) или встраивание запрещено",
               403: "закрыт (частный)", 404: "не найден / удалён / заблокирован"}.get(st, f"код {st}")
    title = ""
    if body:
        try:
            title = json.loads(body).get("title", "")
        except Exception:  # noqa: BLE001
            pass
    return st, meaning, title


def video_info(vid):
    """Строка info:ID — описание, длительность, просмотры и обложки ролика (status/thumbs/)."""
    import re
    st, html = get(f"https://www.youtube.com/watch?v={vid}&hl=ru")
    out = {"id": vid, "status": st}
    if html:
        for key in ("title", "shortDescription", "lengthSeconds", "viewCount", "ownerChannelName", "publishDate", "uploadDate"):
            m = re.search(r'"%s":"((?:[^"\\]|\\.)*)"' % key, html)
            if m:
                try:
                    out[key] = json.loads('"' + m.group(1) + '"')
                except Exception:  # noqa: BLE001
                    out[key] = m.group(1)[:1000]
        i = html.find("likeButtonViewModel")
        if i > 0:
            m = re.search(r'"title":"([^"]*)"', html[i:i + 4000])
            if m:
                out["likes"] = m.group(1)
            m = re.search(r'"accessibilityText":"([^"]*)"', html[i:i + 6000])
            if m:
                out["likes_text"] = m.group(1)[:200]
        out["like_snips"] = re.findall(r'"[^"]{0,90}(?:[Нн]равится|отмет\w* «Нравится»|like this video)[^"]{0,90}"', html)[:4]
        out["html_len"] = len(html)
        m = re.search(r'"keywords":\[(.*?)\]', html)
        if m:
            out["keywords"] = m.group(1)[:600]
    thumbs = OUT / "thumbs"
    thumbs.mkdir(exist_ok=True)
    for name in ("oar2.jpg", "hqdefault.jpg"):
        req = urllib.request.Request(f"https://i.ytimg.com/vi/{vid}/{name}", headers=H)
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            (thumbs / f"{vid}_{name}").write_bytes(data)
            out.setdefault("thumbs", []).append(name)
            LOG.append(f"200 thumb {vid}/{name} {len(data)} B")
        except Exception as e:  # noqa: BLE001
            LOG.append(f"ERR thumb {vid}/{name} {e}")
    return out


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [l.strip() for l in Path("request.txt").read_text(encoding="utf-8").splitlines()]
    handles = [l.lstrip("@") for l in lines
               if l and not l.startswith("#") and not l.startswith("video:") and not l.startswith("info:")]
    videos = [l.split(":", 1)[1].strip() for l in lines if l.startswith("video:")]
    infos = [l.split(":", 1)[1].strip() for l in lines if l.startswith("info:")]

    for h in handles:
        info = channel_info(h)
        sst, shorts = shorts_tab(h)
        rst, feed = rss(info["channel_id"]) if info.get("channel_id") else (0, [])
        info.update({"checked": now, "shorts_status": sst, "shorts": shorts, "rss_status": rst, "rss": feed})
        (OUT / f"{h}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")

        md = [f"# {info.get('title') or h}  (@{h})", f"Проверено: {now}", ""]
        md.append(f"- Страница канала: HTTP {info.get('page_status')}; ID: {info.get('channel_id')}")
        if info.get("header"):
            md.append("- Шапка: " + " · ".join(info["header"]))
        if info.get("alerts"):
            md.append("- ⚠️ Сообщения YouTube: " + " | ".join(info["alerts"]))
        md += ["", f"## Последние открытые ролики (RSS, точные просмотры) — {len(feed)} шт."]
        for r in feed:
            md.append(f"- {r['published'][:16].replace('T', ' ')} · {r['views']} просм. · {r['title']} · {r['id']}")
        if not feed:
            md.append("- (пусто или лента недоступна, HTTP %s)" % rst)
        md += ["", f"## Вкладка Shorts (видно всем) — {len(shorts)} шт. на первой странице"]
        for s in shorts[:30]:
            md.append(f"- {s['views'] or '?'} · {s['title']} · {s['id']}")
        (OUT / f"{h}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        time.sleep(1)

    if videos:
        md = [f"# Проверка отдельных роликов", f"Проверено: {now}", ""]
        for v in videos:
            st, meaning, title = video_status(v)
            md.append(f"- {v}: {meaning} {('· ' + title) if title else ''}")
        (OUT / "videos.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if infos:
        data = []
        for v in infos:
            data.append(video_info(v))
            time.sleep(4)
        (OUT / "info.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        md = ["# Подробности роликов", f"Проверено: {now}", ""]
        for d in data:
            md.append(f"## {d.get('title', '?')} · {d['id']}")
            md.append(f"- HTTP {d['status']} · опубликован {d.get('publishDate', '?')} · {d.get('lengthSeconds', '?')} с · {d.get('viewCount', '?')} просм. · лайки: {d.get('likes', '?')} ({d.get('likes_text', '')}) · "
                      f"канал: {d.get('ownerChannelName', '?')} · обложки: {', '.join(d.get('thumbs', [])) or 'нет'}")
            if d.get("shortDescription"):
                md.append("- Описание: " + d["shortDescription"].replace("\n", " / ")[:1200])
            if d.get("keywords"):
                md.append("- Теги: " + d["keywords"][:400])
            md.append("")
        (OUT / "info.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    (OUT / "_log.txt").write_text(now + "\n" + "\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

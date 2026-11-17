"""Проверка YouTube-каналов (публичные данные) для отчёта в ветку yt-status.

Читает request.txt:
  @handle        — канал: подписчики, число роликов, последние Shorts и ролики с просмотрами
  video:ID       — отдельный ролик: открыт ли он (oEmbed: 200 = открыт, 401/403 = закрыт, 404 = удалён)
  info:ID        — подробности ролика: длина, теги, описание, дата, обложки
  scan:search:запрос | scan:search-week:запрос | scan:hashtag:тег — что YouTube выдаёт в нише (топы, соседи)
  all            — обход всех каналов из channels.txt и сканов из scans.txt (так же работает ежедневный запуск)
  # ...          — комментарий (меняй его, чтобы перезапустить проверку)
Пишет status/<handle>.md, status/<handle>.json, status/videos.md, status/_log.txt.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import yt_analytics as YA

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Cookie": "CONSENT=YES+1; SOCS=CAI",
}
OUT = Path("status")
OUT.mkdir(exist_ok=True)
LOG = []
RSS_FAILS = [0]
T0 = time.time()


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
    # аватар и шапка канала — картинками в status/branding (чтобы видеть, что сейчас стоит)
    imgs = {}
    av = (md.get("avatar") or {}).get("thumbnails") or []
    if av:
        imgs["avatar"] = av[-1].get("url")
    for node in walk(header):
        bn = node.get("imageBannerViewModel") if isinstance(node, dict) else None
        if bn:
            src = (bn.get("image") or {}).get("sources") or []
            if src:
                imgs["banner"] = max(src, key=lambda x: x.get("width", 0)).get("url")
    br = OUT / "branding"
    br.mkdir(exist_ok=True)
    for k, u in imgs.items():
        if not u:
            continue
        u = u if u.startswith("http") else "https:" + u
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=25) as r:
                (br / f"{handle}_{k}.jpg").write_bytes(r.read())
            LOG.append(f"200 {k} {handle}")
        except Exception as e:  # noqa: BLE001
            LOG.append(f"ERR {k} {handle} {e}")
    info["images"] = imgs
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


def videos_tab(handle):
    """Вкладка «Видео» (длинные ролики): название, просмотры (округлено), «N часов назад».
    Нужна, когда RSS не отвечает: серии мультиков и длинные Flagball видны только здесь и в RSS."""
    st, html = get(f"https://www.youtube.com/@{handle}/videos")
    items = []
    d = initial_data(html) if html else {}
    for node in walk(d):
        if "videoRenderer" in node:
            v = node["videoRenderer"]
            items.append({"id": v.get("videoId"), "title": text_of(v.get("title", {})),
                          "views": text_of(v.get("viewCountText", {})),
                          "ago": text_of(v.get("publishedTimeText", {})),
                          "length": text_of(v.get("lengthText", {}))})
        elif "lockupViewModel" in node:
            v = node["lockupViewModel"]
            meta = (v.get("metadata") or {}).get("lockupMetadataViewModel") or {}
            parts = [text_of(p.get("text", {})) for p in walk(meta) if isinstance(p, dict) and "text" in p and isinstance(p.get("text"), dict)]
            parts = [p for p in parts if p]
            views = next((p for p in parts if re.search(r"просм|view", p, re.I)), "")
            ago = next((p for p in parts if re.search(r"назад|ago", p, re.I)), "")
            items.append({"id": v.get("contentId"), "title": text_of(meta.get("title", {})),
                          "views": views, "ago": ago, "length": ""})
    seen, uniq = set(), []
    for it in items:
        if it["id"] and it["id"] not in seen:
            seen.add(it["id"])
            uniq.append(it)
    return st, uniq


def rss(cid):
    # 14–16.11.2026: лента канала временами отдаёт серверу GitHub 404 на все каналы подряд.
    # Тогда — лента плейлиста «все загрузки» (UU…), потом ещё одна попытка ленты канала.
    urls = [f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"]
    if cid.startswith("UC"):
        urls.append(f"https://www.youtube.com/feeds/videos.xml?playlist_id=UU{cid[2:]}")
    urls.append(urls[0])
    if RSS_FAILS[0] >= 3:          # три канала подряд без ленты — дальше без запасных попыток
        urls = urls[:1]
    st, xml = 0, ""
    for i, u in enumerate(urls):
        if i:
            time.sleep(2 + 2 * i)
        st, xml = get(u)
        if st == 200 and xml:
            break
    RSS_FAILS[0] = 0 if (st == 200 and xml) else RSS_FAILS[0] + 1
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
            "desc": ((e.find("m:group/m:description", ns).text or "") if e.find("m:group/m:description", ns) is not None else "")[:5000],
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
    det = YA.player(vid, H, LOG)
    if det:
        out["det"] = det
        out.setdefault("lengthSeconds", det.get("length_s"))
        out.setdefault("shortDescription", det.get("description"))
        out.setdefault("publishDate", det.get("publish"))
        if det.get("keywords") and "keywords" not in out:
            out["keywords"] = ", ".join(det["keywords"])[:600]
    thumbs = OUT / "thumbs"
    thumbs.mkdir(exist_ok=True)
    for name in ("maxresdefault.jpg", "sddefault.jpg", "oar2.jpg", "hqdefault.jpg", "hq1.jpg", "hq2.jpg", "hq3.jpg"):   # maxres — обложка 1280×720; hq1–3 — кадры из ролика (25/50/75%)
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
    global T0
    T0 = time.time()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.strftime("%Y-%m-%d %H:%M UTC")
    daily = "--daily" in sys.argv
    lines = [] if daily else [l.strip() for l in Path("request.txt").read_text(encoding="utf-8").splitlines()]
    full = os.environ.get("YT_FULL") == "1" or not daily
    if daily or "all" in lines:
        # channels.txt: '@handle группа своя|сосед'
        lines = [l for l in lines if l != "all"]
        for row in YA.read_list("channels.txt"):
            parts = row.split()
            if daily and not full and (len(parts) < 3 or parts[2] != "своя"):
                continue  # в промежуточных запусках — только свои каналы
            lines.append(parts[0])
        if full:
            lines += ["scan:" + x for x in YA.read_list("scans.txt")]
    rivals = {r.split()[0].lstrip("@") for r in YA.read_list("channels.txt") if len(r.split()) >= 3 and r.split()[2] != "своя"}
    for l in lines:   # «rss-retry:0» в request.txt — не ждать RSS (быстрая проверка); «rss-retry:N» — минут от старта (≤ 12)
        if l.startswith("rss-retry:"):
            os.environ["RSS_RETRY_MIN"] = l.split(":", 1)[1].strip() or "0"
    handles = [l.lstrip("@") for l in lines
               if l and not l.startswith("#") and not l.startswith(("video:", "info:", "scan:", "rss-retry:"))]
    videos = [l.split(":", 1)[1].strip() for l in lines if l.startswith("video:")]
    infos = [l.split(":", 1)[1].strip() for l in lines if l.startswith("info:")]
    scans = [l.split(":", 1)[1].strip() for l in lines if l.startswith("scan:")]

    def save_channel(h, info, stamp_dt):
        stamp = stamp_dt.strftime("%Y-%m-%d %H:%M UTC")
        info["checked"] = stamp
        feed, rst, shorts = info.get("rss") or [], info.get("rss_status"), info.get("shorts") or []
        try:
            YA.record_channel(info, stamp_dt, tab_rows=full, tab_limit=24 if h in rivals else 60)
        except Exception as e:  # noqa: BLE001
            LOG.append(f"ERR history {h} {e}")
        if h in rivals:
            (OUT / "rivals").mkdir(exist_ok=True)
            (OUT / "rivals" / f"{h}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
            return
        (OUT / f"{h}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        md = [f"# {info.get('title') or h}  (@{h})", f"Проверено: {stamp}", ""]
        md.append(f"- Страница канала: HTTP {info.get('page_status')}; ID: {info.get('channel_id')}")
        if info.get("header"):
            md.append("- Шапка: " + " · ".join(info["header"]))
        if info.get("alerts"):
            md.append("- ⚠️ Сообщения YouTube: " + " | ".join(info["alerts"]))
        if info.get("rss_tries", 1) > 1:
            md.append(f"- RSS: попыток {info['rss_tries']}, последний ответ HTTP {rst}")
        md += ["", f"## Последние открытые ролики (RSS, точные просмотры) — {len(feed)} шт."]
        for r in feed:
            md.append(f"- {r['published'][:16].replace('T', ' ')} · {r['views']} просм. · {r['title']} · {r['id']}")
        if not feed:
            md.append("- (пусто или лента недоступна, HTTP %s)" % rst)
        if info.get("videos") is not None:
            md += ["", f"## Вкладка «Видео» (RSS не ответил; просмотры округлены) — {len(info['videos'])} шт., HTTP {info.get('videos_status')}"]
            for r in info["videos"][:15]:
                md.append(f"- {r['ago'] or '?'} · {r['views'] or '?'} · {r['length']} · {r['title']} · {r['id']}")
        md += ["", f"## Вкладка Shorts (видно всем) — {len(shorts)} шт. на первой странице"]
        for sh in shorts[:30]:
            md.append(f"- {sh['views'] or '?'} · {sh['title']} · {sh['id']}")
        (OUT / f"{h}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    pending = {}   # свои каналы, у которых RSS не ответил: повторять до ответа (Михаил, 16.11.2026: «сразу перезагружай»)
    for h in dict.fromkeys(handles):
        info = channel_info(h)
        sst, shorts = shorts_tab(h)
        rst, feed = rss(info["channel_id"]) if info.get("channel_id") else (0, [])
        info.update({"checked": now, "shorts_status": sst, "shorts": shorts, "rss_status": rst, "rss": feed, "rss_tries": 1})
        if not feed and h not in rivals and info.get("channel_id"):
            time.sleep(1)
            vst, vids = videos_tab(h)
            info.update({"videos_status": vst, "videos": vids})
            pending[h] = info
            time.sleep(1)
            continue
        save_channel(h, info, now_dt)
        time.sleep(1)

    for sc in scans:
        try:
            YA.run_scan(sc, get, initial_data, H, LOG, now_dt)
        except Exception as e:  # noqa: BLE001
            LOG.append(f"ERR scan {sc} {e}")
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

    if pending:
        # RSS у своих каналов молчит — перезапрашивать каждые RSS_RETRY_EVERY с, пока не ответит,
        # но не дольше RSS_RETRY_MIN минут (утренние 404 14–16.11.2026 проходили сами через 1–2 ч).
        # Окно — до конца бюджета запуска от его старта, чтобы уложиться в тайм-аут Actions
        # (yt-check — 15 мин, yt-daily — 30 мин): по умолчанию 12 и 25 мин от старта.
        every = int(os.environ.get("RSS_RETRY_EVERY", "120"))
        budget = min(float(os.environ.get("RSS_RETRY_MIN") or (25 if daily else 12)), 25 if daily else 12)
        limit = T0 + 60 * budget
        while pending and time.time() + every + 60 < limit:
            time.sleep(every)
            RSS_FAILS[0] = 3          # в повторах — по одному запросу на канал, чтобы круг был коротким
            for h in list(pending):
                info = pending[h]
                rst, feed = rss(info["channel_id"])
                info["rss_tries"] = info.get("rss_tries", 1) + 1
                info["rss_status"] = rst
                if feed:
                    info["rss"] = feed
                    sst, shorts = shorts_tab(h)   # вкладка Shorts — на тот же момент, что и RSS
                    if shorts:
                        info.update({"shorts_status": sst, "shorts": shorts})
                    info.pop("videos", None)
                    info.pop("videos_status", None)
                    LOG.append(f"RSS {h}: ответил с попытки {info['rss_tries']}")
                    save_channel(h, info, datetime.now(timezone.utc))
                    del pending[h]
                time.sleep(1)
        for h, info in pending.items():
            LOG.append(f"RSS {h}: не ответил за {info['rss_tries']} попыток — данные только с вкладок")
            save_channel(h, info, now_dt)

    (OUT / "_log.txt").write_text(now + "\n" + "\n".join(LOG) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())

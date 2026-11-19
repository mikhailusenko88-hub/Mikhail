"""Комментарии под роликами канала — открытым способом, как их видит любой зритель (без ключей).
Вход бота в YouTube (устройство + код) не даёт права читать комментарии через API, поэтому читаем как браузер:
список роликов — из открытой RSS-ленты канала, комментарии — пакетом youtube-comment-downloader."""
import re

import requests


def channel_videos(channel_id, limit=15):
    r = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", timeout=30)
    if r.status_code != 200:
        return []
    return re.findall(r"<yt:videoId>([\w-]{11})</yt:videoId>", r.text)[:limit]


def comments(channel_id, extra_ids=(), per_video=60):
    """[(id, текст, id_автора)] — свежие комментарии под последними роликами канала."""
    from youtube_comment_downloader import SORT_BY_RECENT, YoutubeCommentDownloader
    ids = []
    for v in channel_videos(channel_id) + list(extra_ids)[-15:]:
        if v not in ids:
            ids.append(v)
    dl = YoutubeCommentDownloader()
    out, errs = [], 0
    for vid in ids[:20]:
        try:
            for n, c in enumerate(dl.get_comments_from_url(f"https://www.youtube.com/watch?v={vid}",
                                                           sort_by=SORT_BY_RECENT)):
                if n >= per_video:
                    break
                if c.get("reply"):
                    continue
                out.append((c.get("cid", ""), c.get("text", ""), c.get("channel", "")))
        except Exception:  # noqa: BLE001
            errs += 1
    return out, (f"{errs} роликов не прочиталось" if errs else None), len(ids)

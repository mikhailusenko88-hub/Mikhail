import json, os
from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_RECENT
cfg = json.load(open('targets.json', encoding='utf-8'))
dl = YoutubeCommentDownloader()
res = {}
os.makedirs('out', exist_ok=True)
for ch, vids in cfg.items():
    out = []
    for vid, label in vids:
        cs, err = [], None
        try:
            for n, c in enumerate(dl.get_comments_from_url(f'https://www.youtube.com/watch?v={vid}', sort_by=SORT_BY_RECENT)):
                if n >= 400:
                    break
                cs.append({k: c.get(k) for k in ('cid', 'text', 'author', 'channel', 'time', 'votes', 'reply', 'heart')})
        except Exception as e:  # noqa
            err = repr(e)[:300]
        out.append({'id': vid, 'label': label, 'comments': cs, 'err': err})
        print(ch, vid, len(cs), err or '')
    res[ch] = out
json.dump(res, open('out/comments.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

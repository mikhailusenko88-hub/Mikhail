"""Публикация ролика на свою страницу сервера (секретная ссылка) + ссылка в Telegram."""
import html
import json
import os
import secrets
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent


def web_cfg(cfg):
    root = Path(cfg.get("web_root", "/var/www/html"))
    key_f = BASE / ".web_key"
    if not key_f.exists():
        key_f.write_text(secrets.token_urlsafe(9).replace("-", "a").replace("_", "b"))
    key = key_f.read_text().strip()
    folder = root / f"klipy-{key}"
    base_url = cfg.get("web_base_url", "http://89.207.252.121").rstrip("/") + f"/klipy-{key}/"
    return folder, base_url


PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Почему так? — ролики</title>
<style>.empty{{color:var(--mute);text-align:center;padding:40px 10px}}
:root{{--bg:#f4f5f8;--card:#fff;--ink:#16181d;--mute:#6b7280;--acc:#2856c8;--ok:#1a7f45}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111318;--card:#1b1e25;--ink:#eef0f4;--mute:#9aa3b2;--acc:#7aa2ff;--ok:#4cc38a}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,system-ui,sans-serif}}
main{{max-width:560px;margin:0 auto;padding:16px}}
h1{{font-size:22px;margin:8px 0 16px}}
.card{{background:var(--card);border-radius:16px;padding:14px;margin-bottom:18px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.date{{color:var(--mute);font-size:13px}} h2{{font-size:18px;margin:4px 0 10px}}
video{{width:100%;aspect-ratio:9/16;max-height:70vh;border-radius:12px;background:#000;display:block}}
pre{{white-space:pre-wrap;background:var(--bg);border-radius:10px;padding:10px;font-family:inherit;font-size:15px;line-height:1.4;margin:10px 0}}
.row{{display:flex;gap:8px;flex-wrap:wrap}}
a.btn,button{{flex:1;min-width:140px;text-align:center;border:0;border-radius:10px;padding:12px;font-family:inherit;font-size:15px;font-weight:600;
background:var(--acc);color:#fff;text-decoration:none;cursor:pointer}}
button.copied{{background:var(--ok)}}
</style></head><body><main><h1>Почему так? — ролики</h1>{cards}</main>
<script>
document.querySelectorAll('button[data-t]').forEach(b=>b.onclick=async()=>{{
 const t=document.getElementById(b.dataset.t).innerText;
 try{{await navigator.clipboard.writeText(t)}}catch(e){{const r=document.createRange();
 r.selectNode(document.getElementById(b.dataset.t));getSelection().removeAllRanges();getSelection().addRange(r);document.execCommand('copy')}}
 b.textContent='Скопировано ✓';b.classList.add('copied');setTimeout(()=>{{b.textContent='Скопировать подпись';b.classList.remove('copied')}},2000)}});
</script></body></html>"""

CARD = """<div class="card" id="{id}"><div class="date">{date}</div><h2>{title}</h2>
<video src="{file}#t=0.1" controls playsinline preload="metadata"></video>
<pre id="c{id}">{caption}</pre>
<div class="row"><a class="btn" href="{file}?dl=1" download="{file}">Скачать ролик</a>
<button data-t="c{id}">Скопировать подпись</button></div></div>"""


def render(folder, items):
    cards = "".join(CARD.format(id=i["id"], date=html.escape(i["date"]), title=html.escape(i["title"]),
                                file=html.escape(i["file"]), caption=html.escape(i["caption"])) for i in items)
    if not cards:
        cards = '<div class="empty">Пока роликов нет. Новый появляется каждый день в 19:00 по Москве.</div>'
    (folder / "index.html").write_text(PAGE.format(cards=cards), encoding="utf-8")
    os.chmod(folder / "index.html", 0o644)


def publish(video, caption, title, date, cfg, keep=30):
    """Кладёт ролик на страницу, возвращает ссылку на него."""
    folder, base_url = web_cfg(cfg)
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video, folder / video.name)
    items_f = folder / "items.json"
    items = json.loads(items_f.read_text(encoding="utf-8")) if items_f.exists() else []
    vid_id = video.stem.replace("-", "").replace("_", "")
    items.insert(0, {"id": vid_id, "file": video.name, "title": title, "caption": caption, "date": date})
    for old in items[keep:]:  # старые ролики удаляем, чтобы не забивать диск
        try:
            (folder / old["file"]).unlink()
        except FileNotFoundError:
            pass
    items = items[:keep]
    items_f.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    render(folder, items)
    os.chmod(folder, 0o755)
    for p in folder.iterdir():
        os.chmod(p, 0o644)
    return f"{base_url}#{vid_id}", base_url


def ensure_page(cfg):
    """Создаёт/пересобирает страницу и возвращает постоянную ссылку."""
    folder, base_url = web_cfg(cfg)
    folder.mkdir(parents=True, exist_ok=True)
    os.chmod(folder, 0o755)
    items_f = folder / "items.json"
    items = json.loads(items_f.read_text(encoding="utf-8")) if items_f.exists() else []
    render(folder, items)
    return base_url


if __name__ == "__main__":
    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    print("\nТвоя ссылка на ролики (добавь в закладки):\n" + ensure_page(cfg) + "\n")

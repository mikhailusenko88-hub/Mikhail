"""«Дизайнеры → Документы для дизайнеров»: 3D-модели по программам, каталог и другие файлы для дизайнеров.

Файлы — это раздел «Дизайнерам» в «Документах» (docs.py), поэтому попадают в резервную копию и их можно класть
тремя путями: загрузкой здесь, из «Документов» и через канал Claude (ветка outbox, docs/*.json).
У каждого файла есть ссылка на скачивание без входа в CRM (https://crm.<домен>/api/f/<ключ>/<имя>):
- общая — «Скопировать ссылку» для мессенджера;
- личная — в письме «Отправить на почту»: по ней видно, скачал ли дизайнер.
Ключ случайный (144 бита), ссылку можно заменить («Новая ссылка»). Других файлов CRM по этим ссылкам не достать.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from typing import Any
from urllib.parse import quote

from flask import Flask, abort, flash, redirect, request, send_file, url_for

from docs import DESIGNER_FOLDER, INLINE_OK, Docs
from pochta import size_h

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]{1,64}@[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})*\.[A-Za-z]{2,24}$")
DL_WINDOW = 3600          # по одной ссылке — не больше DL_MAX скачиваний в час (защита канала сервера)
DL_MAX = 40
SEND_MAX_DAY = 60         # писем дизайнерам в сутки из этого раздела
MARK = "{ссылки}"
DEFAULT_SUBJECT = "3D-модели и каталог «Наш декор»"
DEFAULT_TEXT = """Здравствуйте!

Отправляем материалы «Наш декор» — стеновые панели, плинтусы и молдинги под покраску и под дерево:

{ссылки}

Модели в натуральную величину, с точными сечениями профилей. Если нужен расчёт по проекту — пришлите развёртку стены, вернём спецификацию по артикулам.

Каталог с ценами и 3D-просмотр каждого профиля: https://%(dom)s"""


def register(app: Flask, store: Any, docs: Docs, h: dict[str, Any]) -> None:
    admin_required, who, send_mail, dom = h["admin_required"], h["who"], h["send_mail"], h["shop_domain"]
    recent: dict[str, deque[float]] = defaultdict(deque)

    def link_url(token: str, filename: str) -> str:
        return f"https://crm.{dom}/api/f/{token}/{quote(filename, safe='')}"

    def dz_docs() -> list[dict[str, Any]]:
        out = []
        for d in docs.list(DESIGNER_FOLDER):
            out.append({**dict(d), "url": link_url(docs.share(d["id"], who()), d["filename"]), "hits": docs.hits(d["id"]),
                        "size_h": size_h(d["size"])})
        return out

    def dz_emails() -> list[tuple[str, str]]:
        rows = store.c().execute("SELECT name, email FROM clients WHERE kind='d' AND email<>'' ORDER BY name").fetchall()
        return [(r["email"], r["name"]) for r in rows]

    @app.context_processor
    def dz_ctx() -> dict[str, Any]:
        return {"dz_docs": dz_docs, "dz_sends": docs.sends, "dz_emails": dz_emails, "DESIGNER_FOLDER": DESIGNER_FOLDER,
                "DZ_SUBJECT": DEFAULT_SUBJECT, "DZ_TEXT": DEFAULT_TEXT % {"dom": dom}, "DZ_MARK": MARK}

    @app.post("/designers/docs/<did>/relink")
    @admin_required
    def designer_doc_relink(did: str) -> Any:
        d = docs.get(did)
        if not d or d["folder"] != DESIGNER_FOLDER:
            abort(404, "Файла нет.")
        docs.reshare(did, who())
        flash(f"У «{d['title']}» новая ссылка, прежняя больше не работает.", "ok")
        return redirect(url_for("designers_view") + "#docs")

    @app.post("/designers/docs/send")
    @admin_required
    def designer_docs_send() -> Any:
        back = url_for("designers_view") + "#send"
        email = (request.form.get("email") or "").strip()
        ids = [x for x in request.form.getlist("ids") if x]
        subject = re.sub(r"\s+", " ", request.form.get("subject") or "").strip()[:150] or DEFAULT_SUBJECT
        text = (request.form.get("text") or "").replace("\r\n", "\n").strip()[:6000] or DEFAULT_TEXT % {"dom": dom}
        if not EMAIL_RE.match(email):
            flash("Проверьте адрес почты.", "err")
            return redirect(back)
        chosen = [d for d in (docs.get(i) for i in ids) if d and d["folder"] == DESIGNER_FOLDER]
        if not chosen:
            flash("Отметьте хотя бы один файл.", "err")
            return redirect(url_for("designers_view", to=email) + "#send")
        day = docs._now()[:10]
        n_today = store.c().execute("SELECT COUNT(DISTINCT sent_to || substr(created_at,1,16)) AS n FROM doc_links"
                                    " WHERE sent_to<>'' AND substr(created_at,1,10)=?", (day,)).fetchone()["n"]
        if int(n_today) >= SEND_MAX_DAY:
            flash(f"Сегодня уже отправлено {n_today} писем — остальное завтра (защита от попадания в спам).", "err")
            return redirect(back)
        cid = store.find_client(store.c(), email=email)
        tokens, lines = [], []
        for d in chosen:
            t = docs.new_link(d["id"], who(), sent_to=email, client_id=cid)
            tokens.append(t)
            lines.append(f"{d['title']} ({size_h(d['size'])}):\n{link_url(t, d['filename'])}")
        block = "\n\n".join(lines)
        body = text.replace(MARK, block) if MARK in text else text + "\n\n" + block
        ch = app.extensions["mail_channel"]() if "mail_channel" in app.extensions else ""
        body += f"\n\nС уважением, {who()}, «Наш декор»\nhttps://{dom} · info@{dom}" + (f"\nКанал в MAX: {ch}" if ch else "")
        if not send_mail(email, subject, body, sender=f"Наш декор <info@{dom}>", reply_to=f"info@{dom}"):
            docs.links_off(tokens)
            flash("Письмо не ушло — почтовый сервер не принял. Попробуйте позже или скопируйте ссылки и отправьте в мессенджере.", "err")
            return redirect(url_for("designers_view", to=email) + "#send")
        if cid:
            with store.tx() as c:
                store.log(c, "Отправлены материалы для дизайнеров: " + ", ".join(d["title"] for d in chosen), who(), client_id=cid)
        dzl = app.extensions.get("dz")
        if dzl is not None:
            dzl.after_models(email, [d["title"] for d in chosen], who())
        flash(f"Письмо отправлено на {email}: {len(chosen)} файл(ов) по ссылкам. Когда дизайнер скачает — будет видно ниже.", "ok")
        return redirect(url_for("designers_view") + "#sent")

    @app.route("/api/f/<token>")
    @app.route("/api/f/<token>/<path:name>")
    def designer_file(token: str, name: str = "") -> Any:
        row = docs.link(token)
        path = docs.path(row["id"]) if row else None
        if not row or not path:
            abort(404)
        q = recent[token]
        now = time.monotonic()
        while q and now - q[0] > DL_WINDOW:
            q.popleft()
        if len(q) >= DL_MAX:
            abort(429)
        inline = row["mime"] in INLINE_OK
        resp = send_file(str(path), mimetype=row["mime"] if inline else "application/octet-stream",
                         as_attachment=not inline, download_name=row["filename"], max_age=0)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        resp.headers["Cache-Control"] = "private, no-store"
        if inline:
            resp.headers["Content-Security-Policy"] = "sandbox"
        rng = request.headers.get("Range", "")
        if request.method == "GET" and (not rng.startswith("bytes=") or rng.startswith("bytes=0-")):   # докачку кусками не считаем
            q.append(now)
            docs.hit(token)
        return resp

#!/usr/bin/env python3
"""Новые письма в ящиках магазина → строки JSON для CRM (пуш «Новое письмо», письмо клиента — в его сделку).

Запускается от root из cron (prostranstvo-crm mail-watch) раз в минуту, только читает заголовки писем:
  python3 -I mailwatch.py ДОМЕН zakaz info
Печатает по строке JSON на каждое новое письмо: {"box", "from", "name", "subject"}.
Помнит, что уже видел, в /var/lib/prostranstvo-mailwatch/seen.json; при первом запуске ничего не шлёт (старые письма — не новость).
Пропускает свои уведомления (noreply@ДОМЕН) и письма, помеченные как спам.

Второй режим — выгрузка писем для раздела CRM «Почта» (текст и вложения, тоже от root):
  python3 -I mailwatch.py --export /var/lib/prostranstvo-pochta prostranstvo ДОМЕН zakaz info
Папка принадлежит root (группа приложения читает, писать не может): CRM видит письма, но не может
подсунуть root'у ссылку на чужой файл. В папке: index.json (список без текста), <id>.json (письмо),
<id>/<n> (вложения). Письма старше EXPORT_DAYS и удалённые из ящика убираются.
"""
import email
import grp
import hashlib
import html
import json
import os
import re
import shutil
import stat
import sys
import time
from email import policy as email_policy
from email.header import decode_header, make_header
from email.policy import compat32
from email.utils import parseaddr, parsedate_to_datetime

VMAIL = os.environ.get("MAILWATCH_VMAIL", "/var/mail/vhosts")
STATE_DIR = os.environ.get("MAILWATCH_STATE", "/var/lib/prostranstvo-mailwatch")
KEEP = 8 * 86400          # сколько помнить увиденные письма
FRESH = 3 * 86400         # письма старше — не новость (например, перенос ящика)

EXPORT_DAYS = 120         # «Почта» в CRM: письма за столько дней
EXPORT_MAX = 400          # и не больше стольких на ящик
MAX_TEXT = 60_000         # символов текста письма
MAX_RAW = 60 * 2**20      # письма больше — читаем начало
MAX_ATT = 15 * 2**20      # вложение больше — только название
MAX_ATT_TOTAL = 30 * 2**20
FOLDERS = (("", False), (".Junk", True), (".Spam", True))
ID_RE = re.compile(r"^[0-9a-f]{20}$")


def mail_key(box, fn):
    """Постоянный id письма: ящик + имя файла без флагов (не меняется, когда письмо прочитали или перенесли из new в cur)."""
    return hashlib.sha1((box + "/" + fn.split(":", 1)[0]).encode("utf-8", "replace")).hexdigest()[:20]


def dec(v):
    try:
        return str(make_header(decode_header(v or ""))).strip()
    except Exception:  # noqa: BLE001
        return (v or "").strip()


def html_text(x):
    """HTML-письмо → читаемый текст (без разметки; в CRM показываем только текст — так безопасно)."""
    x = re.sub(r"(?is)<(style|script|head|title)\b.*?</\1\s*>", "", x)
    x = re.sub(r"(?s)<!--.*?-->", "", x)
    x = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h[1-6]|table|blockquote|ul|ol)\s*>", "\n", x)
    x = re.sub(r"(?i)<li\b[^>]*>", "• ", x)
    x = re.sub(r"(?i)</t[dh]\s*>", " ", x)
    x = re.sub(r"<[^>]*>", "", x)
    x = html.unescape(x).replace("\xa0", " ").replace("\u200b", "")
    x = re.sub(r"[ \t\r\f\v]+", " ", x)
    x = re.sub(r" *\n *", "\n", x)
    return re.sub(r"\n{3,}", "\n\n", x).strip()


def _hdr(m, k):
    try:
        v = m.get(k, "")
    except Exception:  # noqa: BLE001
        return ""
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _part_text(p):
    try:
        return p.get_content()
    except Exception:  # noqa: BLE001
        try:
            return (p.get_payload(decode=True) or b"").decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            return ""


def _safe_name(n, i):
    n = re.sub(r'[\x00-\x1f\x7f\\/:*?"<>|]', "_", str(n or "")).strip(" .")[:150]
    return n or f"вложение-{i}"


def _wfile(path, data, gid):
    """Записать файл атомарно, без перехода по ссылкам; группа приложения может читать."""
    tmp = path + ".tmp"
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
    try:
        os.fchown(fd, -1, gid)
        os.fchmod(fd, 0o640)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, path)


def _mkdir(path, gid):
    try:
        os.mkdir(path, 0o750)
    except FileExistsError:
        pass
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode):
        raise RuntimeError(f"{path} — не папка")
    os.chown(path, -1, gid)
    os.chmod(path, 0o750)


def _rm(path):
    st = os.lstat(path)
    if stat.S_ISDIR(st.st_mode):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def parse_letter(path, box, spam, mid, mtime):
    """Письмо из Maildir → (метаданные, полное письмо, вложения [(n, bytes)])."""
    with open(path, "rb") as f:
        raw = f.read(MAX_RAW)
    m = email.message_from_bytes(raw, policy=email_policy.default)
    name, addr = parseaddr(_hdr(m, "From"))
    try:
        ts = int(parsedate_to_datetime(_hdr(m, "Date")).timestamp())
    except Exception:  # noqa: BLE001
        ts = int(mtime)
    if ts > mtime + 86400:                                  # дата из будущего — берём время прихода
        ts = int(mtime)
    try:
        body = m.get_body(("plain", "html"))
    except Exception:  # noqa: BLE001
        body = None
    text, html_only = "", False
    if body is not None:
        text = _part_text(body)
        if body.get_content_type() == "text/html":
            text, html_only = html_text(text), True
    text = text.replace("\r\n", "\n").strip()
    atts, files, total, n = [], [], 0, 0
    for p in m.walk():
        if p.is_multipart() or p is body:
            continue
        try:
            fn, disp = p.get_filename(), p.get_content_disposition()
        except Exception:  # noqa: BLE001
            fn, disp = None, None
        if not fn and disp != "attachment":
            continue
        n += 1
        try:
            data = p.get_payload(decode=True) or b""
        except Exception:  # noqa: BLE001
            data = b""
        a = {"n": n, "name": _safe_name(fn, n), "mime": p.get_content_type(), "size": len(data), "saved": False}
        if data and len(data) <= MAX_ATT and total + len(data) <= MAX_ATT_TOTAL:
            a["saved"], total = True, total + len(data)
            files.append((n, data))
        atts.append(a)
        if n >= 50:
            break
    refs = []
    for k in ("In-Reply-To", "References"):
        for r in re.findall(r"<[^<>\s]{1,250}>", _hdr(m, k)):
            if r not in refs:
                refs.append(r)
    meta = {"id": mid, "box": box, "spam": spam, "ts": ts, "from": addr.lower()[:200], "name": name[:200],
            "subject": _hdr(m, "Subject")[:300], "natt": len(atts), "msgid": _hdr(m, "Message-ID")[:250],
            "refs": refs[-30:]}
    full = dict(meta, to=_hdr(m, "To")[:1000], cc=_hdr(m, "Cc")[:1000], reply_to=_hdr(m, "Reply-To")[:300],
                text=text[:MAX_TEXT], cut=len(text) > MAX_TEXT, html_only=html_only, atts=atts)
    return meta, full, files


def export(out, group, domain, boxes, now=None):
    """Выгрузка писем для раздела CRM «Почта». Повторный запуск разбирает только новые письма."""
    gid = grp.getgrnam(group).gr_gid
    now = now or time.time()
    _mkdir(out, gid)
    ipath = os.path.join(out, "index.json")
    try:
        with open(ipath, encoding="utf-8") as f:
            old = {e["id"]: e for e in json.load(f).get("letters", [])}
    except Exception:  # noqa: BLE001
        old = {}
    found = []
    for box in boxes:
        root = os.path.join(VMAIL, domain, box, "Maildir")
        cand = []
        for folder, spam in FOLDERS:
            for sub in ("new", "cur"):
                d = os.path.join(root, folder, sub) if folder else os.path.join(root, sub)
                try:
                    names = os.listdir(d)
                except OSError:
                    continue
                for fn in names:
                    full = os.path.join(d, fn)
                    try:
                        st = os.lstat(full)
                    except OSError:
                        continue
                    if not stat.S_ISREG(st.st_mode) or now - st.st_mtime > EXPORT_DAYS * 86400:
                        continue
                    cand.append((st.st_mtime, full, fn, spam))
        cand.sort(reverse=True)
        seen_ids = set()
        for mtime, full, fn, spam in cand:
            mid = mail_key(box, fn)
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            found.append((mtime, full, box, spam, mid))
            if len(seen_ids) >= EXPORT_MAX:
                break
    letters, made = [], 0
    for mtime, full, box, spam, mid in found:
        e = old.get(mid)
        if e and e.get("spam") == spam and os.path.isfile(os.path.join(out, mid + ".json")):
            letters.append(e)
            continue
        try:
            meta, letter, files = parse_letter(full, box, spam, mid, mtime)
        except Exception as ex:  # noqa: BLE001
            print(f"не разобрал письмо {box}/{os.path.basename(full)[:40]}: {ex}", file=sys.stderr)
            continue
        adir = os.path.join(out, mid)
        if os.path.lexists(adir):
            _rm(adir)
        if files:
            _mkdir(adir, gid)
            for n, data in files:
                _wfile(os.path.join(adir, str(n)), data, gid)
        _wfile(os.path.join(out, mid + ".json"), json.dumps(letter, ensure_ascii=False).encode(), gid)
        letters.append(meta)
        made += 1
    keep = {e["id"] for e in letters}
    for name in os.listdir(out):
        base = name.split(".", 1)[0]
        if (ID_RE.match(base) and base not in keep) or name.endswith(".tmp"):
            try:
                _rm(os.path.join(out, name))
            except OSError:
                pass
    letters.sort(key=lambda e: (-int(e.get("ts") or 0), e["id"]))
    data = json.dumps({"v": 1, "letters": letters}, ensure_ascii=False).encode()
    try:
        with open(ipath, "rb") as f:
            same = f.read() == data
    except OSError:
        same = False
    if not same:
        _wfile(ipath, data, gid)
    if made:
        print(f"выгружено писем: {made}", file=sys.stderr)
    return 0


def main(argv):
    if argv[:1] == ["--export"]:
        if len(argv) < 5:
            print("Нужно: mailwatch.py --export ПАПКА ГРУППА ДОМЕН ящик [ящик…]", file=sys.stderr)
            return 2
        return export(argv[1], argv[2], argv[3].lower(), argv[4:])
    if len(argv) < 2:
        print("Нужно: mailwatch.py ДОМЕН ящик [ящик…]", file=sys.stderr)
        return 2
    domain, boxes = argv[0].lower(), argv[1:]
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    path = os.path.join(STATE_DIR, "seen.json")
    first = not os.path.exists(path)
    try:
        seen = json.load(open(path)) if not first else {}
    except Exception:  # noqa: BLE001
        seen, first = {}, True
    now = time.time()
    out = []
    for box in boxes:
        root = os.path.join(VMAIL, domain, box, "Maildir")
        for sub in ("new", "cur"):                       # телефон может сразу забрать письмо из new в cur
            d = os.path.join(root, sub)
            try:
                names = os.listdir(d)
            except OSError:
                continue
            for fn in names:
                key = box + "/" + fn.split(":", 1)[0]
                if key in seen:
                    continue
                full = os.path.join(d, fn)
                try:
                    mt = os.path.getmtime(full)
                except OSError:
                    continue
                seen[key] = now
                if first or now - mt > FRESH:
                    continue
                try:
                    with open(full, "rb") as f:
                        msg = email.message_from_binary_file(f, policy=compat32, _class=email.message.Message)
                except Exception:  # noqa: BLE001
                    continue
                name, addr = parseaddr(dec(msg.get("From", "")))
                addr = addr.lower()
                if addr == "noreply@" + domain or addr.startswith("mailer-daemon@"):
                    continue
                if (msg.get("X-Spam-Flag", "") or "").strip().upper() == "YES" or (msg.get("X-Spam", "") or "").strip().lower() == "yes":
                    continue
                out.append({"box": box, "from": addr, "name": name, "subject": dec(msg.get("Subject", ""))[:200],
                            "key": mail_key(box, fn)})
    seen = {k: v for k, v in seen.items() if now - v < KEEP}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(seen, f)
    os.replace(tmp, path)
    for o in out[:30]:
        print(json.dumps(o, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

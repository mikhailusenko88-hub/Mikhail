#!/usr/bin/env python3
"""Аварийная панель «Наш декор» — https://crm.<домен>/rescue/

Отдельная от CRM маленькая программа (только стандартная библиотека Python). Работает, даже если CRM сломалась,
зависла или новая версия всё испортила: свой процесс (служба prostranstvo-rescue, root, 127.0.0.1:8099), своя копия
кода вне папки CRM (/usr/local/lib/prostranstvo/rescue.py), свой пароль (/etc/prostranstvo/rescue-pass) — своя страница
входа с cookie (системное окно логина iPhone не показывает в приложении с экрана «Домой»).
Ставит и обновляет setup-crm.sh — новая версия панели ставится, только если прошла самопроверку (--selftest).

Кнопки (только перечисленные — произвольных команд нет):
  CRM: перезапустить · откатить на прошлую версию / вернуть обратно · выключить / включить
  Автоматика (письма клиентам, письма с zapros@, интеграции, правки сайта из CRM): пауза / снова работать
  Сайт: показать версии · вернуть выбранную (автообновление на паузе) · снова обновлять автоматически
  Почта и веб-сервер: перезапустить · сервер: перезагрузить
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("RESCUE_PORT", "8099"))
CRM_PORT = os.environ.get("CRM_PORT", "8081")
CRM_HOST = os.environ.get("CRM_HOST", "")
DOMAIN = os.environ.get("DOMAIN", "")
CRM_BASE = os.environ.get("CRM_BASE", "/opt/prostranstvo-crm")
CRM_SRC, CRM_PREV = os.path.join(CRM_BASE, "src"), os.path.join(CRM_BASE, "prev")
SITE_SRC = os.environ.get("SITE_SRC", "/opt/prostranstvo-src")
SITE_WWW = os.environ.get("SITE_WWW", "/var/www/prostranstvo")
SITE_USER = os.environ.get("SITE_USER", "prostranstvo")
SITE_BRANCH, SITE_SUBDIR = os.environ.get("SITE_BRANCH", "mebel"), os.environ.get("SITE_SUBDIR", "0f7s1eez")
SITE_CRON = os.environ.get("SITE_CRON", "/etc/cron.d/prostranstvo")
STATE = os.environ.get("STATE_DIR", "/var/lib/prostranstvo")
PAUSE_FLAG = os.path.join(STATE, "pause-auto")
PASS_FILE = os.environ.get("RESCUE_PASS_FILE", "/etc/prostranstvo/rescue-pass")
COOKIE = "rescue"
SESSION_DAYS = 30
KEY = secrets.token_bytes(32)              # запасная подпись, если файла с паролем нет
FAILS: dict[str, list[float]] = {}         # неверные пароли по адресам: 10 за 10 минут — пауза 15 минут
SITE_PIN = os.path.join(STATE, "site-pin")
TOKEN = secrets.token_urlsafe(24)          # защита кнопок от чужих сайтов: токен есть только на странице панели
LOCK = threading.Lock()
LAST: dict[str, str] = {"msg": "", "ok": "1", "at": ""}
VERSIONS: list[tuple[str, str, str]] = []  # версии сайта: (sha, дата, описание)


def sh(cmd: list[str], timeout: int = 60, user: str = "") -> tuple[int, str]:
    if user:
        cmd = ["runuser", "-u", user, "--"] + cmd
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C.UTF-8"})
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "не ответило за %d с" % timeout
    except OSError as e:
        return 127, str(e)


def http_code(url: str, host: str = "", timeout: int = 6) -> str:
    cmd = ["curl", "-s", "-k", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout)]
    if host:
        cmd += ["--resolve", f"{host}:443:127.0.0.1"]
    rc, out = sh(cmd + [url], timeout=timeout + 3)
    return out.strip()[-3:] if out else "000"


def git_line(path: str, user: str = "") -> str:
    rc, out = sh(["git", "-C", path, "log", "-1", "--format=%h · %cd · %s", "--date=format-local:%d.%m.%Y %H:%M"], 15, user)
    return out.splitlines()[0][:140] if rc == 0 and out else "нет данных"


def crm_ok() -> bool:
    return http_code(f"http://127.0.0.1:{CRM_PORT}/api/health") == "200"


def wait_crm(sec: int = 30) -> bool:
    for _ in range(sec):
        if crm_ok():
            return True
        time.sleep(1)
    return False


def site_cron(enable: bool) -> bool:
    """Автообновление сайта из GitHub: включить/выключить строку prostranstvo-sync в cron."""
    try:
        with open(SITE_CRON, encoding="utf-8") as f:
            lines = f.read().split("\n")
    except OSError:
        return False
    out = []
    for ln in lines:
        if "prostranstvo-sync" in ln and not ln.lstrip().startswith("# ") or ln.startswith("#RESCUE# "):
            core = ln[len("#RESCUE# "):] if ln.startswith("#RESCUE# ") else ln
            ln = core if enable else "#RESCUE# " + core
        out.append(ln)
    tmp = SITE_CRON + ".rescue"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    os.chmod(tmp, 0o644)
    os.replace(tmp, SITE_CRON)
    return True


def site_auto() -> bool:
    try:
        with open(SITE_CRON, encoding="utf-8") as f:
            return not any(ln.startswith("#RESCUE# ") for ln in f.read().split("\n"))
    except OSError:
        return True


# ---------------------------------------------------------------- действия
def act_crm_restart(_: str) -> tuple[bool, str]:
    sh(["systemctl", "restart", "prostranstvo-crm"], 60)
    return (True, "CRM перезапущена и отвечает.") if wait_crm() else (False, "CRM перезапущена, но не отвечает. Попробуйте «Откатить CRM на прошлую версию».")


def act_crm_rollback(_: str) -> tuple[bool, str]:
    if not os.path.isdir(os.path.join(CRM_PREV, "crm")):
        return False, "Прошлой версии CRM нет (она появляется после первого «Обновить CRM»)."
    tmp = CRM_BASE + "/swap.tmp"
    sh(["rm", "-rf", tmp], 60)
    os.rename(CRM_SRC, tmp)
    os.rename(CRM_PREV, CRM_SRC)
    os.rename(tmp, CRM_PREV)
    sh(["find", os.path.join(CRM_SRC, "crm"), "-name", "__pycache__", "-prune", "-exec", "rm", "-rf", "{}", "+"], 30)
    sh(["systemctl", "restart", "prostranstvo-crm"], 60)
    ok = wait_crm()
    return ok, (f"CRM переключена на версию: {git_line(CRM_SRC)}. " + ("Работает." if ok else "Но не отвечает — нажмите ещё раз, чтобы вернуть как было.")
                + " Вернуть как было — эта же кнопка ещё раз.")


def act_crm_stop(_: str) -> tuple[bool, str]:
    rc, out = sh(["systemctl", "stop", "prostranstvo-crm"], 60)
    return rc == 0, "CRM выключена. Сайт и почта работают; заявки с сайта не принимаются, пока CRM выключена." if rc == 0 else out[-300:]


def act_crm_start(_: str) -> tuple[bool, str]:
    sh(["systemctl", "start", "prostranstvo-crm"], 60)
    return (True, "CRM включена и отвечает.") if wait_crm() else (False, "CRM не отвечает после включения. Попробуйте откатить на прошлую версию.")


def act_auto(on: bool) -> tuple[bool, str]:
    if on:
        try:
            os.remove(PAUSE_FLAG)
        except FileNotFoundError:
            pass
        return True, "Автоматика снова работает: письма клиентам, письма с zapros@, интеграции, правки сайта из CRM."
    with open(PAUSE_FLAG, "w", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M") + "\n")
    os.chmod(PAUSE_FLAG, 0o644)
    return True, "Автоматика на паузе: CRM не шлёт письма клиентам и с zapros@, не отправляет интеграции, сайт не берёт правки из CRM. Всё копится и уйдёт после «Снова работать»."


def act_site_list(_: str) -> tuple[bool, str]:
    rc, out = sh(["git", "-C", SITE_SRC, "fetch", "--quiet", "--depth", "30", "--no-tags", "origin",
                  f"+refs/heads/{SITE_BRANCH}:refs/remotes/origin/{SITE_BRANCH}"], 120, SITE_USER)
    if rc != 0:
        return False, "GitHub не ответил: " + out[-200:]
    rc, out = sh(["git", "-C", SITE_SRC, "log", "-30", "--format=%H\t%cd\t%s", "--date=format-local:%d.%m.%Y %H:%M",
                  f"refs/remotes/origin/{SITE_BRANCH}"], 30, SITE_USER)
    VERSIONS.clear()
    for ln in out.splitlines():
        p = ln.split("\t", 2)
        if len(p) == 3 and re.match(r"^[0-9a-f]{40}$", p[0]):
            VERSIONS.append((p[0], p[1], p[2][:120]))
    return bool(VERSIONS), f"Версий сайта: {len(VERSIONS)}. Выберите ниже, какую вернуть." if VERSIONS else "Версии не нашлись."


def deploy_site(sha: str) -> tuple[bool, str]:
    rc, out = sh(["git", "-C", SITE_SRC, "fetch", "--quiet", "--depth", "1", "--no-tags", "origin", sha], 120, SITE_USER)
    if rc != 0:
        return False, "не удалось скачать эту версию: " + out[-200:]
    rc, out = sh(["git", "-C", SITE_SRC, "reset", "--quiet", "--hard", sha], 60, SITE_USER)
    if rc != 0:
        return False, "git reset: " + out[-200:]
    idx = os.path.join(SITE_SRC, SITE_SUBDIR, "index.html")
    if not os.path.isfile(idx) or os.path.getsize(idx) < 10000:
        return False, "в этой версии нет нормальной главной страницы — сайт не тронут"
    rc, out = sh(["rsync", "-a", "--delete", "--delay-updates", "--exclude=.git*", "--exclude=.keep", "--chmod=D755,F644",
                  os.path.join(SITE_SRC, SITE_SUBDIR) + "/", SITE_WWW + "/"], 180, SITE_USER)
    if rc != 0:
        return False, "rsync: " + out[-200:]
    return True, ""


def act_site_pin(sha: str) -> tuple[bool, str]:
    if not re.match(r"^[0-9a-f]{40}$", sha or "") or sha not in [v[0] for v in VERSIONS]:
        return False, "Сначала нажмите «Показать версии сайта» и выберите версию из списка."
    site_cron(False)
    ok, why = deploy_site(sha)
    if not ok:
        return False, "Сайт не переключён: " + why + ". Автообновление на паузе — нажмите «Снова обновлять автоматически», чтобы вернуть как было."
    with open(SITE_PIN, "w", encoding="utf-8") as f:
        f.write(sha + "\n")
    v = next(x for x in VERSIONS if x[0] == sha)
    return True, f"На сайте версия от {v[1]} ({v[2]}). Автообновление из GitHub на паузе — новые правки не придут, пока не нажмёте «Снова обновлять автоматически»."


def act_site_resume(_: str) -> tuple[bool, str]:
    site_cron(True)
    try:
        os.remove(SITE_PIN)
    except FileNotFoundError:
        pass
    rc, out = sh(["/usr/local/sbin/prostranstvo-sync", "--verbose"], 300)
    return rc == 0, ("Автообновление сайта включено, сайт — последняя версия из GitHub." if rc == 0 else "Автообновление включено, но обновить сразу не вышло: " + out[-200:])


def act_simple(cmd: list[str], ok_msg: str) -> tuple[bool, str]:
    rc, out = sh(cmd, 120)
    return rc == 0, ok_msg if rc == 0 else out[-300:]


ACTIONS = {
    "crm_restart": act_crm_restart, "crm_rollback": act_crm_rollback, "crm_stop": act_crm_stop, "crm_start": act_crm_start,
    "auto_off": lambda a: act_auto(False), "auto_on": lambda a: act_auto(True),
    "site_list": act_site_list, "site_pin": act_site_pin, "site_resume": act_site_resume,
    "web_restart": lambda a: act_simple(["sh", "-c", "nginx -t && systemctl restart nginx"], "Веб-сервер перезапущен."),
    "mail_restart": lambda a: act_simple(["systemctl", "restart", "postfix", "dovecot"], "Почта перезапущена."),
    "reboot": lambda a: act_simple(["systemctl", "reboot", "--no-block"], "Сервер перезагружается — панель откроется снова через 1–2 минуты."),
}
CONFIRM = {"crm_rollback", "crm_stop", "site_pin", "reboot"}


# ---------------------------------------------------------------- страница
def status() -> dict[str, str]:
    s: dict[str, str] = {}
    s["crm"] = "работает" if crm_ok() else "НЕ ОТВЕЧАЕТ"
    rc, out = sh(["systemctl", "is-active", "prostranstvo-crm"], 10)
    s["crm_service"] = out.strip() or "?"
    s["crm_ver"] = git_line(CRM_SRC)
    s["crm_prev"] = git_line(CRM_PREV) if os.path.isdir(os.path.join(CRM_PREV, "crm")) else ""
    code = http_code(f"https://{DOMAIN}/", DOMAIN) if DOMAIN else "000"
    s["site"] = "работает" if code in ("200", "301", "302") else f"НЕ ОТВЕЧАЕТ (код {code})"
    s["site_ver"] = git_line(SITE_SRC, SITE_USER)
    s["site_auto"] = "да" if site_auto() else "НА ПАУЗЕ"
    s["auto"] = "НА ПАУЗЕ" if os.path.exists(PAUSE_FLAG) else "работает"
    rc, out = sh(["df", "-h", "--output=avail,pcent", "/"], 10)
    s["disk"] = " ".join(out.split()[2:4]) if rc == 0 else "?"
    rc, out = sh(["systemctl", "is-active", "nginx", "postfix", "dovecot"], 10)
    s["services"] = ", ".join(f"{n}: {v}" for n, v in zip(("веб", "почта (отправка)", "почта (ящики)"), out.split()))
    return s


CSS = """body{font:16px/1.45 -apple-system,system-ui,sans-serif;margin:0;background:#F8F8F6;color:#26292E}
main{max-width:640px;margin:0 auto;padding:16px}h1{font-size:22px;margin:4px 0 12px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.04em;margin:22px 0 8px;color:#4F6A82}
.box{background:#fff;border:1px solid #DCDDE0;border-radius:12px;padding:12px 14px;margin:8px 0}.row{display:flex;justify-content:space-between;gap:10px;padding:4px 0}
.bad{color:#B3261E;font-weight:600}.good{color:#1D6B3A;font-weight:600}.d{color:#6B7178;font-size:14px}
form{margin:6px 0}button{font:inherit;font-weight:600;border:0;border-radius:10px;padding:12px 14px;width:100%;margin:4px 0;cursor:pointer}
.b1{background:#26292E;color:#fff}.b2{background:#E8EAEC;color:#26292E}.b3{background:#B3261E;color:#fff}
.msg{border-radius:12px;padding:12px 14px;margin:10px 0;font-weight:500}.ok{background:#E3F1E7}.err{background:#FBE4E2}
label{display:flex;gap:8px;align-items:center;font-size:14px;margin:4px 0}.v{border-top:1px solid #EEE;padding:8px 0}"""


def page(s: dict[str, str]) -> str:
    e = html.escape

    def btn(act: str, text: str, cls: str = "b2", arg: str = "", confirm: str = "") -> str:
        c = f'<label><input type="checkbox" name="yes" value="1" required> {e(confirm)}</label>' if confirm else ""
        return (f'<form method="post" action="/rescue/act"><input type="hidden" name="t" value="{TOKEN}">'
                f'<input type="hidden" name="act" value="{act}"><input type="hidden" name="arg" value="{e(arg)}">{c}'
                f'<button class="{cls}">{e(text)}</button></form>')

    def st(v: str) -> str:
        return f'<span class="{"bad" if v.isupper() or "НЕ " in v or "ПАУЗ" in v else "good"}">{e(v)}</span>'

    msg = f'<div class="msg {"ok" if LAST["ok"] == "1" else "err"}">{e(LAST["msg"])} <span class="d">{e(LAST["at"])}</span></div>' if LAST["msg"] else ""
    vers = "".join(f'<div class="v"><b>{e(d)}</b> <span class="d">{e(m)}</span>{btn("site_pin", "Вернуть эту версию сайта", "b2", sha, "Да, вернуть эту версию")}</div>'
                   for sha, d, m in VERSIONS[:20])
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Аварийная панель · Наш декор</title><meta name="apple-mobile-web-app-title" content="Аварийная"><meta name="apple-mobile-web-app-capable" content="yes">
<style>{CSS}</style></head><body><main>
<h1>🛟 Аварийная панель</h1>
<p class="d">Работает отдельно от CRM. Если что-то сломалось или зависло — здесь можно вернуть как было. Ничего не удаляется: любое действие можно отменить.</p>
{msg}
<div class="box">
<div class="row"><span>CRM</span>{st(s["crm"])}</div>
<div class="row d"><span>версия</span><span>{e(s["crm_ver"])}</span></div>
<div class="row"><span>Сайт</span>{st(s["site"])}</div>
<div class="row d"><span>версия</span><span>{e(s["site_ver"])}</span></div>
<div class="row"><span>Сайт обновляется из GitHub</span>{st(s["site_auto"])}</div>
<div class="row"><span>Автоматика (письма, интеграции)</span>{st(s["auto"])}</div>
<div class="row d"><span>{e(s["services"])}</span><span>диск: {e(s["disk"])}</span></div>
</div>
<form method="get" action="/rescue/"><button class="b2">Обновить состояние</button></form>

<h2>CRM</h2>
{btn("crm_restart", "Перезапустить CRM", "b1")}
{btn("crm_rollback", "Откатить CRM на прошлую версию" if s["crm_prev"] else "Прошлой версии CRM пока нет", "b2", "", "Да, переключить версию CRM (данные не трогаются)") if s["crm_prev"] else ""}
{('<p class="d">Прошлая версия: ' + e(s["crm_prev"]) + '. Нажать ещё раз — вернуть обратно.</p>') if s["crm_prev"] else ""}
{btn("crm_start", "Включить CRM", "b1") if s["crm_service"] != "active" else btn("crm_stop", "Выключить CRM", "b2", "", "Да, выключить CRM")}

<h2>Автоматика</h2>
<p class="d">Письма клиентам (расчёты, напоминания), письма с zapros@, интеграции, правки сайта из CRM.</p>
{btn("auto_on", "Автоматика — снова работать", "b1") if s["auto"] != "работает" else btn("auto_off", "Автоматика — пауза", "b2")}

<h2>Сайт</h2>
{btn("site_resume", "Снова обновлять сайт автоматически", "b1") if s["site_auto"] != "да" else ""}
{btn("site_list", "Показать версии сайта (вернуть прошлую)", "b2")}
{('<div class="box">' + vers + '</div>') if vers else ""}

<h2>Сервер</h2>
{btn("web_restart", "Перезапустить веб-сервер (nginx)", "b2")}
{btn("mail_restart", "Перезапустить почту", "b2")}
{btn("reboot", "Перезагрузить сервер", "b3", "", "Да, перезагрузить (1–2 минуты ничего не работает)")}
<p class="d">Если и эта панель не открывается — кабинет FirstVDS → сервер → «Перезагрузить».</p>
<p class="d"><a href="/">Открыть CRM</a></p>
<form method="post" action="/rescue/logout"><button class="b2">Выйти из панели</button></form>
</main></body></html>"""


def sign_key() -> bytes:
    """Подпись входа из пароля: вход переживает перезапуск панели и сервера, а смена пароля выкидывает всех."""
    try:
        with open(PASS_FILE, "rb") as f:
            real = f.readline().strip()
    except OSError:
        real = b""
    return hashlib.sha256(b"rescue-session:" + real).digest() if real else KEY


def make_session() -> str:
    exp = str(int(time.time()) + SESSION_DAYS * 86400)
    return exp + "." + hmac.new(sign_key(), exp.encode(), hashlib.sha256).hexdigest()


def session_ok(cookie_header: str) -> bool:
    for part in (cookie_header or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE and "." in v:
            exp, sig = v.split(".", 1)
            if exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(sig, hmac.new(sign_key(), exp.encode(), hashlib.sha256).hexdigest()):
                return True
    return False


def password_ok(pw: str) -> bool:
    try:
        with open(PASS_FILE, encoding="utf-8") as f:
            real = f.readline().strip()
    except OSError:
        return False
    return bool(real) and hmac.compare_digest(pw.strip().encode(), real.encode())


def too_many(ip: str) -> bool:
    now = time.time()
    FAILS[ip] = [t for t in FAILS.get(ip, []) if now - t < 900]
    return len(FAILS[ip]) >= 10


def login_page(err: str = "") -> str:
    e = html.escape
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Аварийная">
<title>Аварийная панель · вход</title><style>{CSS}input{{font:inherit;width:100%;box-sizing:border-box;padding:12px;border:1px solid #C9CDD2;border-radius:10px;margin:6px 0}}</style></head>
<body><main><h1>🛟 Аварийная панель</h1>
<p class="d">Работает отдельно от CRM. Пароль — CRM → Ещё → Сервер → «показать пароль» (или в «Паролях» iPhone).</p>
{f'<div class="msg err">{e(err)}</div>' if err else ''}
<form method="post" action="/rescue/login"><input type="hidden" name="username" value="nashdekor" autocomplete="username">
<label class="d" for="pw">Пароль панели</label><input id="pw" type="password" name="pw" autocomplete="current-password" required autofocus>
<button class="b1">Войти</button></form></main></body></html>"""


class H(BaseHTTPRequestHandler):
    server_version = "rescue"
    sys_version = ""

    def log_message(self, fmt: str, *args: object) -> None:  # в журнал systemd — только действия
        pass

    def send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8", extra: dict[str, str] | None = None) -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def client_ip(self) -> str:
        return (self.headers.get("X-Real-IP") or self.client_address[0] or "?").strip()[:64]

    def authed(self) -> bool:
        return session_ok(self.headers.get("Cookie", ""))

    def redirect(self, cookie: str = "") -> None:
        self.send_response(303)
        self.send_header("Location", "/rescue/")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/rescue", "/rescue/"):
            if not self.authed():
                return self.send(200, login_page())
            with LOCK:
                self.send(200, page(status()))
        elif path == "/rescue/health":
            self.send(200, "ok", "text/plain; charset=utf-8")
        else:
            self.send(404, "нет такой страницы", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ("/rescue/act", "/rescue/login", "/rescue/logout"):
            return self.send(404, "нет", "text/plain; charset=utf-8")
        n = int(self.headers.get("Content-Length") or 0)
        if n > 4096:
            return self.send(413, "слишком много данных", "text/plain; charset=utf-8")
        f = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode("utf-8", "replace")).items()}
        origin = self.headers.get("Origin") or self.headers.get("Referer") or ""
        host = self.headers.get("Host") or ""
        if origin and origin != "null" and not origin.startswith(f"https://{host}"):
            return self.send(400, page_redirect("Запрос не с этой страницы."))
        if path == "/rescue/login":
            ip = self.client_ip()
            if too_many(ip):
                return self.send(429, login_page("Много неверных паролей — подождите 15 минут."))
            if not password_ok(f.get("pw", "")):
                FAILS.setdefault(ip, []).append(time.time())
                sh(["logger", "-t", "prostranstvo-rescue", f"неверный пароль панели с {ip}"], 5)
                return self.send(403, login_page("Неверный пароль. Скопируйте его со страницы CRM «Сервер» → «показать пароль»."))
            FAILS.pop(ip, None)
            return self.redirect(f"{COOKIE}={make_session()}; Path=/rescue/; Max-Age={SESSION_DAYS * 86400}; HttpOnly; Secure; SameSite=Strict")
        if path == "/rescue/logout":
            return self.redirect(f"{COOKIE}=; Path=/rescue/; Max-Age=0; HttpOnly; Secure; SameSite=Strict")
        if not self.authed():
            return self.send(403, login_page("Войдите заново."))
        if f.get("t") != TOKEN or not origin.startswith(f"https://{host}"):
            return self.send(400, page_redirect("Страница устарела — откройте панель заново."), extra=None)
        act = f.get("act", "")
        if act not in ACTIONS:
            return self.send(400, "нет такого действия", "text/plain; charset=utf-8")
        if act in CONFIRM and f.get("yes") != "1":
            LAST.update(msg="Отметьте галочку подтверждения рядом с кнопкой.", ok="0", at=time.strftime("%H:%M:%S"))
        else:
            with LOCK:
                try:
                    ok, msg = ACTIONS[act](f.get("arg", ""))
                except Exception as ex:  # noqa: BLE001 — панель не должна падать ни от чего
                    ok, msg = False, f"ошибка: {type(ex).__name__}: {ex}"
            LAST.update(msg=msg, ok="1" if ok else "0", at=time.strftime("%d.%m %H:%M:%S"))
            sh(["logger", "-t", "prostranstvo-rescue", f"{act}: {'ок' if ok else 'ошибка'} — {msg[:200]}"], 5)
        self.send_response(303)
        self.send_header("Location", "/rescue/")
        self.send_header("Content-Length", "0")
        self.end_headers()


def page_redirect(text: str) -> str:
    return f'<!doctype html><meta charset="utf-8"><p>{html.escape(text)}</p><p><a href="/rescue/">Открыть панель</a></p>'


def selftest() -> int:
    """Проверка перед установкой новой версии панели: страница строится, кнопки на месте."""
    global CRM_PORT
    s = {k: "работает" for k in ("crm", "site", "auto")} | {"crm_service": "active", "crm_ver": "x", "crm_prev": "y", "site_ver": "z",
                                                             "site_auto": "да", "disk": "1G 5%", "services": "веб: active"}
    p = page(s)
    need = ["crm_restart", "crm_rollback", "auto_off", "site_list", "reboot", TOKEN]
    if 'name="pw"' not in login_page() or not session_ok(f"{COOKIE}={make_session()}") or session_ok(f"{COOKIE}=1.bad"):
        print("вход не работает")
        return 1
    missing = [x for x in need if x not in p]
    if missing:
        print("нет в странице:", missing)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    srv.daemon_threads = True
    srv.serve_forever()

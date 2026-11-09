"""Тесты CRM: python3 -m unittest -v test_crm (из папки crm)."""

from __future__ import annotations

import os as _os
for _k in ("NOTIFY_EMAIL", "CRM_DB", "BOT_DB", "CATALOG_FILE", "SITE_ORIGINS", "SITE_LEADS", "SHOP_DOMAIN", "CRM_SECRET_FILE"):
    _os.environ.pop(_k, None)  # тесты никогда не трогают настоящую базу и почту сервера
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from werkzeug.security import generate_password_hash  # noqa: E402

import app as crm_app  # noqa: E402
from store import parse_catalog  # noqa: E402

CAT_HTML = """<html><script>const SHOP={};
const CAT=[{"a":"A912","c":"panel","n":"Рейка 912","w":120,"t":12,"l":2700,"b":6,"r":990},
{"a":"A116","c":"corner","n":"Уголок","w":20,"t":20,"l":2700,"b":20,"r":350},
{"a":"GS 1","c":"color","n":"Под дерево \\"дуб\\"","w":150,"t":10,"l":2800,"b":5,"r":1500}];
const X=[1,2];</script></html>"""


def bot_schema() -> str:
    sys.path.insert(0, os.path.join(HERE, "..", "bot"))
    try:
        import db as botdb  # type: ignore
        return botdb.SCHEMA_V2
    finally:
        sys.path.pop(0)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.cat = os.path.join(d, "index.html")
        with open(self.cat, "w", encoding="utf-8") as f:
            f.write(CAT_HTML)
        self.botdb = os.path.join(d, "bot.db")
        self.app = crm_app.create_app({"CRM_DB": os.path.join(d, "crm.db"), "BOT_DB": self.botdb,
                                       "CATALOG_FILE": self.cat, "SECRET_KEY": "x" * 40, "COOKIE_SECURE": "0",
                                       "SITE_ORIGINS": "https://nashdekor.ru", "SITE_LEADS": "1", "TESTING": True,
                                       "SHOP_DOMAIN": "nashdekor.ru", "NOTIFY_EMAIL": ""})
        self.store = self.app.extensions["store"]
        self.store.add_user("yulia", "Юлия", "admin", generate_password_hash("Secret-pass-1"))
        self.store.add_user("mikhail", "Михаил", "staff", generate_password_hash("Secret-pass-2"))
        self.c = self.app.test_client()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def csrf(self, client=None) -> str:
        client = client or self.c
        r = client.get("/login")
        with client.session_transaction() as s:
            return s["csrf"]

    def login(self, login="yulia", pw="Secret-pass-1", client=None):
        client = client or self.c
        tok = self.csrf(client)
        return client.post("/login", data={"login": login, "password": pw, "csrf": tok})

    def post(self, url, data=None, client=None):
        client = client or self.c
        with client.session_transaction() as s:
            tok = s.get("csrf", "")
        d = dict(data or {})
        d["csrf"] = tok
        return client.post(url, data=d)


class TestCatalog(unittest.TestCase):
    def test_parse(self) -> None:
        items = parse_catalog(CAT_HTML)
        self.assertEqual([p.article for p in items], ["A912", "A116", "GS 1"])
        self.assertEqual(items[0].price, 990)
        self.assertEqual(items[2].name, 'Под дерево "дуб"')


class TestAuth(Base):
    def test_login_flow(self) -> None:
        r = self.c.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])
        r = self.login(pw="wrong-password")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Неверный логин или пароль", r.get_data(as_text=True))
        r = self.login()
        self.assertEqual(r.status_code, 302)
        r = self.c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Сегодня", r.get_data(as_text=True))
        self.assertIn("Content-Security-Policy", r.headers)

    def test_csrf_required(self) -> None:
        self.login()
        r = self.c.post("/deals/new", data={"name": "Без токена"})
        self.assertEqual(r.status_code, 400)

    def test_login_rate_limit(self) -> None:
        for _ in range(10):
            self.login(pw="bad-bad-bad")
        r = self.login()  # даже верный пароль — после 10 ошибок ждём
        self.assertEqual(r.status_code, 401)
        self.assertIn("Слишком много попыток", r.get_data(as_text=True))

    def test_open_redirect_blocked(self) -> None:
        tok = self.csrf()
        r = self.c.post("/login", data={"login": "yulia", "password": "Secret-pass-1", "csrf": tok, "next": "//evil.example/x"})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("evil", r.headers["Location"])

    def test_password_change_logs_out_other_sessions(self) -> None:
        other = self.app.test_client()
        self.login(client=other)
        self.assertEqual(other.get("/").status_code, 200)
        self.login()
        r = self.post("/settings/password", {"old": "Secret-pass-1", "new": "New-pass-123", "new2": "New-pass-123"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/").status_code, 200)       # эта сессия остаётся
        self.assertEqual(other.get("/").status_code, 302)        # другая — выход

    def test_staff_cannot_admin(self) -> None:
        self.login("mikhail", "Secret-pass-2")
        did = self.store.create_deal("t", None, name="Клиент")
        r = self.post(f"/deals/{did}/delete", {"confirm": "1"})
        self.assertEqual(r.status_code, 403)
        r = self.post("/settings/users", {"login": "x1", "name": "X", "role": "admin", "password": "1234567890"})
        self.assertEqual(r.status_code, 403)


class TestDeals(Base):
    def setUp(self) -> None:
        super().setUp()
        self.login()

    def new_deal(self, **kw) -> int:
        data = {"name": "Анна", "phone": "8 (911) 123-45-67", "source": "avito", "want": "ТВ-зона", "kind": "p"}
        data.update(kw)
        r = self.post("/deals/new", data)
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:300])
        return int(re.search(r"/deals/(\d+)", r.headers["Location"]).group(1))

    def test_deal_lifecycle_and_stock(self) -> None:
        did = self.new_deal()
        d = self.store.deal(did)
        self.assertEqual(d["phone"], "+79111234567")
        self.assertEqual(d["source"], "avito")
        self.post(f"/deals/{did}/lines", {"article": "а912", "qty": "10"})   # кириллица + регистр
        lines = self.store.lines(did)
        self.assertEqual((lines[0]["article"], lines[0]["qty"], lines[0]["price"]), ("A912", 10, 990))
        self.post("/stock/A912", {"qty": "50", "price": "990"})
        self.post(f"/deals/{did}/stage", {"stage": "work"})
        row = {r["article"]: r for r in self.store.stock_rows()}["A912"]
        self.assertEqual((row["qty"], row["reserved"]), (50, 10))
        self.post(f"/deals/{did}/stage", {"stage": "shipped"})
        row = {r["article"]: r for r in self.store.stock_rows()}["A912"]
        self.assertEqual((row["qty"], row["reserved"]), (40, 0))
        # правка количества после отгрузки — склад на разницу
        lid = self.store.lines(did)[0]["id"]
        self.post(f"/lines/{lid}", {"deal": str(did), "qty": "12", "price": "990"})
        self.assertEqual({r["article"]: r for r in self.store.stock_rows()}["A912"]["qty"], 38)
        self.post(f"/deals/{did}/stage", {"stage": "paid"})   # вернули из «Отгружено»
        self.assertEqual({r["article"]: r for r in self.store.stock_rows()}["A912"]["qty"], 50)
        page = self.c.get(f"/deals/{did}").get_data(as_text=True)
        self.assertIn("11 880 ₽", page)
        self.assertIn("Этап: Отгружено → Оплачено", page)

    def test_next_stage_and_board(self) -> None:
        did = self.new_deal()
        self.post(f"/deals/{did}/stage", {"next": "1", "back": "/board"})
        self.assertEqual(self.store.deal(did)["stage"], "work")
        r = self.c.get("/board?q=Анна")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Анна", r.get_data(as_text=True))

    def test_designer_discount(self) -> None:
        did = self.new_deal(name="Студия «Линия»", kind="d", phone="+7 921 000 00 00")
        self.assertEqual(self.store.deal(did)["discount"], 10)
        self.post(f"/deals/{did}/lines", {"article": "A116", "qty": "4"})
        self.assertEqual(self.store.deal_total(did), (1400, 1260))

    def test_same_phone_same_client(self) -> None:
        a = self.new_deal()
        b = self.new_deal(name="Анна К.", phone="+7 911 123 45 67")
        self.assertEqual(self.store.deal(a)["client_id"], self.store.deal(b)["client_id"])

    def test_tasks(self) -> None:
        did = self.new_deal()
        self.post(f"/deals/{did}/tasks", {"title": "Перезвонить", "due": "2026-11-06"})
        t = self.store.tasks(deal_id=did)[0]
        self.post(f"/tasks/{t['id']}", {"done": "1", "back": f"/deals/{did}"})
        self.assertIsNotNone(self.store.tasks(deal_id=did, open_only=False)[0]["done_at"])
        self.assertEqual(self.c.get("/tasks").status_code, 200)

    def test_clients_and_edit(self) -> None:
        did = self.new_deal()
        cid = self.store.deal(did)["client_id"]
        r = self.c.get("/clients?q=911123")
        self.assertIn("Анна", r.get_data(as_text=True))
        self.post(f"/clients/{cid}", {"name": "Анна Колесова", "kind": "d", "phone": "89111234567", "email": "a@b.ru",
                                      "messenger": "", "company": "", "inn": "", "note": "второй раз"})
        cl = self.store.client(cid)
        self.assertEqual((cl["name"], cl["kind"]), ("Анна Колесова", "d"))
        self.assertEqual(self.store.deal(did)["discount"], 10)   # дизайнеру — скидка в открытой заявке

    def test_all_pages_render(self) -> None:
        did = self.new_deal()
        cid = self.store.deal(did)["client_id"]
        for url in ["/", "/board", "/board?all=1", "/deals/new", f"/deals/{did}", "/clients", f"/clients/{cid}",
                    "/stock", "/stock?kind=panel&q=a9&only=have", "/tasks", "/reports", "/settings", f"/deals/new?client={cid}"]:
            r = self.c.get(url)
            self.assertEqual(r.status_code, 200, url)
        self.assertEqual(self.c.get("/deals/9999").status_code, 404)

    def test_stock_price_override(self) -> None:
        self.post("/stock/A116", {"qty": "7", "price": "400"})
        self.assertEqual(self.store.price_of("A116"), 400)
        self.post("/stock/A116", {"qty": "7", "price": "350"})   # как на сайте — своя цена снимается
        row = {r["article"]: r for r in self.store.stock_rows()}["A116"]
        self.assertFalse(row["own_price"])
        r = self.post("/stock/GS%201", {"qty": "3", "price": ""})
        self.assertEqual(r.status_code, 302)
        self.assertEqual({r["article"]: r for r in self.store.stock_rows()}["GS 1"]["qty"], 3)

    def test_public_catalog_for_site(self) -> None:
        # цена из CRM и свободный остаток (минус отложенное) видны сайту; чужим сайтам — без CORS
        self.post("/stock/A912", {"qty": "50", "price": "1100"})
        did = self.new_deal()
        self.post(f"/deals/{did}/lines", {"article": "A912", "qty": "8"})
        self.post(f"/deals/{did}/stage", {"stage": "work"})
        anon = self.app.test_client()                            # покупатель на сайте — без входа в CRM
        r = anon.get("/api/catalog", headers={"Origin": "https://nashdekor.ru"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "https://nashdekor.ru")
        self.assertIn("max-age", r.headers["Cache-Control"])
        items = r.get_json()["items"]
        self.assertEqual(items["A912"], {"p": 1100, "q": 42})
        self.assertEqual(items["A116"], {"p": 350, "q": 0})      # своей цены нет — цена сайта, на складе 0
        self.assertEqual(set(items["GS 1"]), {"p", "q"})        # ничего лишнего (себестоимость, заявки) не отдаём
        r = anon.get("/api/catalog", headers={"Origin": "https://evil.example"})
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)
        r = anon.options("/api/catalog", headers={"Origin": "https://nashdekor.ru", "Access-Control-Request-Method": "GET"})
        self.assertEqual(r.status_code, 204)
        self.assertIn("GET", r.headers["Access-Control-Allow-Methods"])

    def test_admin_delete(self) -> None:
        did = self.new_deal()
        self.post(f"/deals/{did}/delete", {})
        self.assertIsNotNone(self.store.deal(did))
        self.post(f"/deals/{did}/delete", {"confirm": "1"})
        self.assertIsNone(self.store.deal(did))

    def test_admin_users(self) -> None:
        r = self.post("/settings/users", {"login": "anna", "name": "Анна", "role": "staff", "password": "short"})
        self.assertIsNone(self.store.user_by_login("anna"))
        self.post("/settings/users", {"login": "anna", "name": "Анна", "role": "staff", "password": "long-enough-1"})
        self.assertIsNotNone(self.store.user_by_login("anna"))
        me = self.store.user_by_login("yulia")
        self.post(f"/settings/users/{me['id']}", {"name": "Юлия", "role": "staff", "active": "1"})
        self.assertEqual(self.store.user_by_login("yulia")["role"], "admin")


class TestServerPage(Base):
    def test_server_page(self) -> None:
        sf = os.path.join(self.tmp.name, "server-status.txt")
        rq = os.path.join(self.tmp.name, "server-request")
        self.login()
        r = self.c.get("/server")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Отчёта ещё нет", r.get_data(as_text=True))
        with open(sf, "w", encoding="utf-8") as f:
            f.write("=== Сервер <тест> ===\nnginx: active\n")
        body = self.c.get("/server").get_data(as_text=True)
        self.assertIn("nginx: active", body)
        self.assertIn("&lt;тест&gt;", body)
        r = self.post("/server/refresh")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(os.path.exists(rq))
        self.assertIn("Обновляю", self.c.get("/server").get_data(as_text=True))

    def test_server_actions(self) -> None:
        rq = os.path.join(self.tmp.name, "server-request")
        af = os.path.join(self.tmp.name, "server-action.txt")
        self.login()
        t = self.c.get("/server").get_data(as_text=True)
        for s in ("Обновить CRM", "Копия баз", "Перезагрузить сервер", "Снять блокировки", "Выключить заявки с сайта"):
            self.assertIn(s, t)
        self.assertNotIn("Включить заявки с сайта", t)          # заявки уже включены — показываем только «выключить»
        self.assertEqual(self.post("/server/run", {"action": "rm -rf /"}).status_code, 400)
        self.assertFalse(os.path.exists(rq))
        self.post("/server/run", {"action": "reboot"})            # без галочки — не перезагружаем
        self.assertFalse(os.path.exists(rq))
        r = self.post("/server/run", {"action": "update"})
        self.assertEqual(r.status_code, 302)
        with open(rq, encoding="utf-8") as f:
            self.assertEqual(f.read(), "update yulia\n")
        self.post("/server/run", {"action": "backup"})            # пока первая не выполнена — вторую не берём
        with open(rq, encoding="utf-8") as f:
            self.assertEqual(f.read(), "update yulia\n")
        os.remove(rq)
        with open(af, "w", encoding="utf-8") as f:
            f.write("Действие: Обновить CRM из GitHub\nЗапросил: yulia, 09.11.2026 12:40\nСостояние: выполняется…\n")
        t = self.c.get("/server").get_data(as_text=True)
        self.assertIn("выполняется", t)
        self.assertIn('http-equiv="refresh"', t)
        self.assertIn("disabled", t)
        self.post("/server/run", {"action": "backup"})
        self.assertFalse(os.path.exists(rq))
        with open(af, "w", encoding="utf-8") as f:
            f.write("Действие: Обновить CRM из GitHub\nСостояние: готово\n\nCRM УСТАНОВЛЕНА\n")
        t = self.c.get("/server").get_data(as_text=True)
        self.assertIn("CRM УСТАНОВЛЕНА", t)
        self.assertNotIn('http-equiv="refresh"', t)
        self.post("/server/run", {"action": "reboot", "confirm": "1"})
        with open(rq, encoding="utf-8") as f:
            self.assertEqual(f.read(), "reboot yulia\n")

    def test_server_page_admin_only(self) -> None:
        self.login("mikhail", "Secret-pass-2")
        self.assertEqual(self.c.get("/server").status_code, 403)
        self.assertEqual(self.post("/server/refresh").status_code, 403)
        self.assertEqual(self.post("/server/run", {"action": "update"}).status_code, 403)
        self.assertNotIn("/server", self.c.get("/tasks").get_data(as_text=True))


IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1")
MAC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15"


class TestVisits(Base):
    def hit(self, events, ua=IPHONE, ip="203.0.113.7", origin="https://nashdekor.ru", client=None, **extra):
        body = {"e": events, "r": extra.pop("r", ""), "u": extra.pop("u", ""), "m": extra.pop("m", 1)}
        h = {"User-Agent": ua, "Content-Type": "text/plain;charset=UTF-8"}
        if origin:
            h["Origin"] = origin
        h.update(extra.pop("headers", {}))
        return (client or self.c).post("/api/hit", data=json.dumps(body, ensure_ascii=False), headers=h,
                                       environ_base={"REMOTE_ADDR": ip})

    def rows(self):
        return [dict(r) for r in self.store.c().execute("SELECT * FROM visits ORDER BY id").fetchall()]

    def test_hits_counted_and_report(self) -> None:
        r = self.hit([["view", "/"], ["sec", "catalog"], ["item", "A912", "use"], ["item", "A116", "ask"],
                      ["calcpanel", "A912"], ["3d", ""], ["form", ""], ["lead", ""], ["copy", "phone"]], r="yandex.ru")
        self.assertEqual(r.status_code, 204)
        self.assertNotIn("Set-Cookie", r.headers)          # посетителю сайта cookie не ставим
        self.hit([["view", "/"], ["item", "A912", "paint"]], ua=MAC, ip="198.51.100.9", r="www.avito.ru", m=0)
        self.hit([["view", "/privacy.html"]], ua=MAC, ip="198.51.100.9", r="nashdekor.ru", m=0)
        rows = self.rows()
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({x["vid"] for x in rows}), 2)
        blob = json.dumps(rows, ensure_ascii=False)
        for secret in ("203.0.113.7", "198.51.100.9", "iPhone OS", "Macintosh"):
            self.assertNotIn(secret, blob)                 # ни IP, ни строки браузера в базе
        rep = self.app.extensions["visits"].report(crm_app.today(), 7)
        self.assertEqual(rep["visitors"], 2)
        self.assertEqual(rep["views"], 3)
        self.assertEqual(rep["leads"], 1)
        self.assertEqual(dict(rep["sources"]), {"Яндекс": 1, "Авито": 1})
        self.assertEqual(dict(rep["devices"]), {"Телефон": 1, "Компьютер": 1})
        f = dict(rep["funnel"])
        self.assertEqual((f["Зашли на сайт"], f["Нажимали на товары"], f["Считали стену"], f["Отправили заявку"]), (2, 2, 1, 1))
        it = {x["article"]: x for x in rep["items"]}
        self.assertEqual((it["A912"]["visitors"], it["A912"]["use"], it["A912"]["calc"], it["A912"]["color"]), (2, 1, 1, 1))
        self.assertEqual(it["A116"]["ask"], 1)
        self.assertEqual(dict(rep["pages"]), {"Главная": 2, "Политика": 1})
        self.assertEqual(self.app.extensions["visits"].brief(crm_app.today()), {"today": 2, "yesterday": 0, "leads": 1})

    def test_rejects_junk_bots_strangers_and_staff(self) -> None:
        self.hit([["view", "/"]], origin="https://evil.example")
        self.hit([["view", "/"]], origin="")
        self.hit([["view", "/"]], ua="Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)")
        self.hit([["view", "/"]], ua=IPHONE.replace("Mobile", "HeadlessChrome Mobile"))
        self.hit([["view", "/"]], headers={"DNT": "1"})
        self.hit([["view", "/"]], headers={"Sec-GPC": "1"})
        self.assertEqual(self.rows(), [])
        self.hit([["drop", "x"], ["item", "NOPE1", "use"], ["item", "A912", "hack"], ["view", "/admin"],
                  ["search", "+7 911 123 45 67"], ["search", "дуб"], ["copy", "x"], ["sec", "zzz"], ["item", "a912", "ask"]])
        self.assertEqual([(x["kind"], x["key"], x["act"]) for x in self.rows()],
                         [("search", "дуб", ""), ("item", "A912", "ask")])
        staff = self.app.test_client()
        self.login(client=staff)
        self.hit([["view", "/"]], client=staff)              # вошли в CRM — свои визиты не считаем
        self.assertEqual(len(self.rows()), 2)

    def test_own_ips_not_counted_and_reset(self) -> None:
        self.hit([["view", "/"]], ip="89.126.192.214")
        self.assertEqual(len(self.rows()), 1)                 # пока адрес не в списке — считается
        self.login()
        r = self.post("/settings/hit-ips", {"ips": "89.126.192.214\n10.0.0.0/8\nне-адрес"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.store.setting("hit_ignore_ips"), "89.126.192.214\n10.0.0.0/8")   # мусор отброшен
        other = self.app.test_client()
        self.hit([["view", "/"]], ip="89.126.192.214", client=other)     # свой адрес
        self.hit([["view", "/"]], ip="10.20.30.40", client=other)        # своя сеть
        self.assertEqual(len(self.rows()), 1)
        self.hit([["view", "/"]], ip="203.0.113.9", client=other)        # чужой — считается
        self.assertEqual(len(self.rows()), 2)
        r = self.post("/settings/hit-ips", {"ips": "89.126.192.214", "add_mine": "1"})   # «добавить мой адрес» (тестовый клиент — 127.0.0.1)
        self.assertEqual(self.store.setting("hit_ignore_ips"), "89.126.192.214\n127.0.0.1")
        r = self.c.get("/settings")
        self.assertIn("89.126.192.214", r.get_data(as_text=True))
        self.assertIn("Обнулить статистику (2)", r.get_data(as_text=True))
        r = self.post("/settings/hit-ips", {"reset": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.app.extensions["visits"].count(), 0)

    def test_daily_key_rotates(self) -> None:
        v = self.app.extensions["visits"]
        a = v.visitor("2026-11-09", "1.2.3.4", IPHONE)
        self.assertEqual(a, v.visitor("2026-11-09", "1.2.3.4", IPHONE))
        b = v.visitor("2026-11-10", "1.2.3.4", IPHONE)
        self.assertNotEqual(a, b)
        salt = self.store.setting("visit_salt")
        self.assertTrue(salt.startswith("2026-11-10:"))      # ключ прошлых суток стёрт

    def test_site_page_and_today(self) -> None:
        self.hit([["view", "/"], ["item", "A912", "use"]], r="google.com")
        self.login()
        r = self.c.get("/site?d=30")
        self.assertEqual(r.status_code, 200)
        t = r.get_data(as_text=True)
        for s in ("Посещаемость сайта", "A912", "Рейка 912", "Google", "Телефон", "Путь по сайту"):
            self.assertIn(s, t)
        self.assertIn("Сайт</a>", self.c.get("/board").get_data(as_text=True))
        t = self.c.get("/").get_data(as_text=True)
        self.assertIn("На сайте сегодня: 1 человек", t)
        self.assertEqual(self.c.get("/site?d=abc").status_code, 200)

    def test_site_page_needs_login(self) -> None:
        r = self.c.get("/site")
        self.assertEqual(r.status_code, 302)


class TestApi(Base):
    def lead(self, origin="https://nashdekor.ru", **kw):
        body = {"name": "Елена", "contact": "+7 999 111-22-33", "consent": True, "message": "A907 в гостиную",
                "who": "designer", "consentVersion": "2026-10-29"}
        body.update(kw)
        h = {"Origin": origin} if origin else {}
        return self.c.post("/api/lead", data=json.dumps(body), content_type="application/json", headers=h)

    def test_lead_ok_and_cors(self) -> None:
        r = self.lead()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "https://nashdekor.ru")
        did = r.get_json()["id"]
        d = self.store.deal(did)
        self.assertEqual((d["source"], d["kind"], d["discount"], d["phone"]), ("site", "d", 10, "+79991112233"))
        self.assertTrue(d["consent_at"])

    def test_lead_with_email_and_send_calc(self) -> None:
        r = self.lead(email="elena@example.com", calc="Товар: A907 — 12 шт")
        did = r.get_json()["id"]
        d = self.store.deal(did)
        self.assertEqual((d["phone"], d["email"]), ("+79991112233", "elena@example.com"))   # телефон из контакта + почта отдельным полем
        self.login()
        r = self.post(f"/deals/{did}/send-calc", {"email": "elena@example.com"})
        self.assertEqual(r.status_code, 302)                   # позиций нет — отказ с подсказкой
        self.assertEqual(self.store.deal(did)["stage"], "new")
        self.post(f"/deals/{did}/lines", {"article": "A912", "qty": "10"})
        sent = {}
        def fake_mail(to, subject, body, sender="", reply_to=""):
            sent.update(to=to, subject=subject, body=body, sender=sender, reply_to=reply_to); return True
        orig = crm_app.send_mail; crm_app.send_mail = fake_mail
        try:
            r = self.post(f"/deals/{did}/send-calc", {"email": "new@example.com"})   # почту поменяли прямо в форме
        finally:
            crm_app.send_mail = orig
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sent["to"], "new@example.com")
        self.assertIn("A912", sent["body"]); self.assertIn("10 шт", sent["body"]); self.assertIn("Итого", sent["body"])
        self.assertIn("noreply@nashdekor.ru", sent["sender"]); self.assertEqual(sent["reply_to"], "zakaz@nashdekor.ru")
        d = self.store.deal(did)
        self.assertEqual((d["stage"], d["email"]), ("quote", "new@example.com"))
        page = self.c.get(f"/deals/{did}").get_data(as_text=True)
        self.assertIn("Отправить расчёт на почту", page); self.assertIn('id="calcText"', page)

    def test_preflight(self) -> None:
        r = self.c.options("/api/lead", headers={"Origin": "https://nashdekor.ru",
                                                 "Access-Control-Request-Method": "POST"})
        self.assertEqual(r.status_code, 204)
        self.assertIn("POST", r.headers["Access-Control-Allow-Methods"])

    def test_bad_requests(self) -> None:
        self.assertEqual(self.lead(origin="https://evil.example").status_code, 403)
        self.assertEqual(self.lead(consent=False).status_code, 400)
        self.assertEqual(self.lead(name="").status_code, 400)
        r = self.lead(website="spam")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.store.deals()), 0)

    def test_rate_limit(self) -> None:
        codes = [self.lead().status_code for _ in range(6)]
        self.assertEqual(codes, [200] * 5 + [429])

    def test_off(self) -> None:
        self.app.extensions["crm_conf"]["SITE_LEADS"] = False
        self.assertEqual(self.lead().status_code, 503)

    def test_health(self) -> None:
        self.assertEqual(self.c.get("/api/health").get_json(), {"ok": True})


class TestBot(Base):
    def make_bot_db(self) -> sqlite3.Connection:
        b = sqlite3.connect(self.botdb)
        b.executescript(bot_schema())
        b.execute("INSERT INTO settings(key, value) VALUES ('schema_version','2')")
        ts = int(time.time())
        b.execute("INSERT INTO clients(channel, user_id, username, name, created_ts, last_ts) VALUES ('max', 555, NULL, 'Игорь', ?, ?)", (ts, ts))
        b.execute("INSERT INTO leads(created_ts, created_at, user_id, username, name, contact, comment, calc, consent_at,"
                  " consent_version, status, channel, client_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (ts, "2026-11-06T10:00:00+03:00", 555, None, "Игорь", "+7 900 000-00-01", "Плинтус с подсветкой",
                   "A11-100 × 15", "2026-11-06T10:00:00+03:00", "2026-10-29", "new", "max", 1))
        b.execute("INSERT INTO messages(created_ts, created_at, user_id, direction, kind, text, channel, client_id)"
                  " VALUES (?,?,?,?,?,?,?,?)", (ts, "2026-11-06T10:01:00+03:00", 555, "in", "text", "Сколько будет?", "max", 1))
        b.execute("INSERT INTO persons(role, notify, deliver, created_at) VALUES ('manager','all','', 'x')")
        b.execute("INSERT INTO team(channel, user_id, person_id, added_at) VALUES ('max', 777, 1, 'x')")
        b.execute("INSERT INTO team(channel, user_id, person_id, added_at) VALUES ('tg', 888, 1, 'x')")
        b.commit()
        return b

    def test_import_and_notify(self) -> None:
        b = self.make_bot_db()
        self.login()
        page = self.c.get("/").get_data(as_text=True)
        self.assertIn("Игорь", page)
        deals = self.store.deals()
        self.assertEqual(len(deals), 1)
        d = self.store.deal(deals[0]["id"])
        self.assertEqual((d["source"], d["bot_lead_id"], d["phone"], d["messenger"]), ("max", 1, "+79000000001", "MAX"))
        self.assertIn("Сколько будет?", self.c.get(f"/deals/{d['id']}").get_data(as_text=True))
        self.assertEqual(self.store.import_bot_leads(force=True), 0)   # повторно не задваивает
        # уведомление о заявке с сайта — в очередь бота, в MAX (по умолчанию)
        self.c.post("/api/lead", data=json.dumps({"name": "Сайт", "contact": "a@b.ru", "consent": True}),
                    content_type="application/json", headers={"Origin": "https://nashdekor.ru"})
        rows = b.execute("SELECT channel, chat_id, item FROM outbox").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:2], ("max", 777))
        self.assertEqual(json.loads(rows[0][2])["t"], "text")
        self.assertEqual(self.c.get("/settings").status_code, 200)


if __name__ == "__main__":
    unittest.main()

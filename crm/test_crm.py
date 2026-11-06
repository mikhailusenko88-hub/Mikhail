"""Тесты CRM: python3 -m unittest -v test_crm (из папки crm)."""

from __future__ import annotations

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
                                       "SHOP_DOMAIN": "nashdekor.ru"})
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

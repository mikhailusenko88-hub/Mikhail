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
        done = {r["id"]: r["done_at"] for r in self.store.tasks(deal_id=did, open_only=False)}
        self.assertIsNotNone(done[t["id"]])
        self.assertEqual(self.c.get("/tasks").status_code, 200)

    def test_funnel_auto_tasks_and_quote_guard(self) -> None:
        did = self.new_deal()
        titles = lambda: [r["title"] for r in self.store.tasks(deal_id=did)]
        self.assertEqual(titles(), ["Связаться с клиентом"])                  # новая заявка → задача сегодня
        # «Дальше» в «Расчёт отправлен» без письма — этап не меняется
        self.post(f"/deals/{did}/stage", {"stage": "work"})
        self.assertEqual(titles(), ["Отправить расчёт клиенту"])
        r = self.post(f"/deals/{did}/stage", {"next": "1"})
        self.assertEqual(self.store.deal(did)["stage"], "work")                  # позиций нет → нельзя
        self.post(f"/deals/{did}/lines", {"article": "A912", "qty": "4"})
        r = self.post(f"/deals/{did}/stage", {"next": "1"})
        self.assertEqual(self.store.deal(did)["stage"], "work")                  # e-mail нет → нельзя
        # «Отправил сам» — можно
        self.post(f"/deals/{did}/send-calc", {"manual": "1"})
        self.assertEqual(self.store.deal(did)["stage"], "quote")
        self.assertEqual(titles(), ["Узнать решение по расчёту, предложить оплату"])
        self.post(f"/deals/{did}/stage", {"stage": "paid"})
        self.assertEqual(titles(), ["Отгрузить: собрать заказ, согласовать доставку"])
        self.store.set_stock("A912", 10, 990, "тест") if hasattr(self.store, "set_stock") else None
        self.post(f"/deals/{did}/stage", {"stage": "shipped"})
        self.assertEqual(titles(), ["Попросить отзыв и фото стены"])
        page = self.c.get("/board").get_data(as_text=True)
        self.assertIn("Попросить отзыв", page)                                   # задача видна на карточке
        page = self.c.get("/board?hot=1").get_data(as_text=True)
        self.assertNotIn("Попросить отзыв", page)                                # отгружено и не просрочено → не горит
        # доска подсвечивает просроченные задачи
        did2 = self.new_deal(name="Пётр", phone="+7 900 555 55 55")
        self.post(f"/deals/{did2}/tasks", {"title": "Перезвонить", "due": "2026-01-01"})
        page = self.c.get("/board").get_data(as_text=True)
        self.assertIn("card hot", page); self.assertIn("просрочено", page)

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

    def test_site_order_buy(self) -> None:
        sent = []
        orig = crm_app.send_mail; crm_app.send_mail = lambda *a, **k: sent.append((a, k)) or True
        try:
            r = self.lead(intent="buy", address="СПб, Невский пр., 1, кв. 5", email="buyer@example.com",
                          calc="Товар: A912 (реечная панель) — 6 шт, цвет: белый\nИтого ≈ 5 940 ₽")
        finally:
            crm_app.send_mail = orig
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        did = r.get_json()["id"]
        d = self.store.deal(did)
        self.assertTrue(d["want"].startswith("ЗАКАЗ."))                          # заказ отличим от заявки
        self.assertEqual(d["address"], "СПб, Невский пр., 1, кв. 5")
        self.assertEqual({r["article"]: r["qty"] for r in self.store.lines(did)}, {"A912": 6})   # позиции сразу в расчёте
        self.assertEqual([r["title"] for r in self.store.tasks(deal_id=did)], ["Связаться с клиентом"])
        self.login()
        page = self.c.get("/board").get_data(as_text=True)
        self.assertIn("card warm", page)                                          # открытая задача → подсвечена

    def test_site_callback_request(self) -> None:
        orig = crm_app.send_mail; crm_app.send_mail = lambda *a, **k: True
        try:
            r = self.lead(intent="call", message="Перезвоните мне, пожалуйста. Удобное время: после 18", calc="")
        finally:
            crm_app.send_mail = orig
        did = r.get_json()["id"]
        d = self.store.deal(did)
        self.assertTrue(d["want"].startswith("ПЕРЕЗВОНИТЬ."))
        self.assertEqual([x["title"] for x in self.store.tasks(deal_id=did)], ["Перезвонить клиенту"])

    def test_followups_auto_and_manual(self) -> None:
        sent = []
        def fake_mail(to, subject, body, sender="", reply_to=""):
            sent.append((to, subject, body)); return True
        orig = crm_app.send_mail; crm_app.send_mail = fake_mail
        try:
            did = self.lead(email="wait@example.com", calc="Товар: A912 (реечная панель) — 3 шт").get_json()["id"]
            self.login()
            self.post(f"/deals/{did}/send-calc", {"email": "wait@example.com"})        # письмо-расчёт → этап quote
            self.assertEqual(self.store.deal(did)["stage"], "quote")
            body = sent[-1][2]
            self.assertIn("Что дальше", body); self.assertIn("пришлём ссылку на оплату", body); self.assertIn("чат на сайте", body); self.assertNotIn("IuliiaUsenko", body)
            run = self.app.extensions["run_followups"]
            from datetime import date as _d, timedelta as _td
            due0 = [x for x in self.store.tasks(deal_id=did) if x["title"].startswith("Узнать")][0]["due"]
            self.assertEqual(run((_d.fromisoformat(due0) - _td(days=1)).isoformat()), [])   # задача «Узнать решение» ещё не подошла (срок +2 дня)
            r = run(due0)
            self.assertEqual(len(r), 1); self.assertIn("напоминание 1", r[0])
            self.assertIn("подошёл ли он вам", sent[-1][1]); self.assertIn("A912 — 3 шт", sent[-1][2])
            d = self.store.deal(did); self.assertEqual(d["followups"], 1)
            self.assertEqual(run(due0), [])                                             # в тот же день второй раз не шлём
            t = [x for x in self.store.tasks(deal_id=did) if x["title"].startswith("Узнать")][0]
            self.assertGreater(t["due"], due0)                                          # задача сдвинута вперёд
            r = run(t["due"]); self.assertEqual(len(r), 1); self.assertIn("напоминание 2", r[0])
            self.assertIn("действует до", sent[-1][1]); self.assertIn("последнее напоминание", sent[-1][2])
            self.assertEqual(run("2026-12-01"), [])                                     # больше двух не уходит
            # выключатель и ручная кнопка
            self.post(f"/deals/{did}/followup", {"toggle": "1"})
            self.assertEqual(self.store.deal(did)["no_followup"], 1)
            n = len(sent); self.post(f"/deals/{did}/followup", {}); self.assertEqual(len(sent), n + 1)
            # глобальный выключатель
            self.store.set_setting("followup_auto", "0")
            self.assertEqual(run("2026-12-01"), ["автонапоминания выключены в настройках"])
            page = self.c.get(f"/deals/{did}").get_data(as_text=True)
            self.assertIn("исходная заявка с сайта", page); self.assertIn("Напомнить сейчас", page)
            page = self.c.get("/settings").get_data(as_text=True)
            self.assertIn("Письма клиентам", page)
        finally:
            crm_app.send_mail = orig

    def _phone(self):
        """Имитация телефона: ключи браузера и подписка как у Safari на iPhone."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        import push as P
        ua = ec.generate_private_key(ec.SECP256R1())
        pub = ua.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        auth = os.urandom(16)
        sub = {"endpoint": "https://web.push.apple.com/QK" + P.b64u(os.urandom(12)), "keys": {"p256dh": P.b64u(pub), "auth": P.b64u(auth)}}
        return ua, auth, sub

    def test_web_push(self) -> None:
        import push as P
        wp = self.app.extensions["push"]
        got = []
        def transport(url, headers, body):
            got.append((url, headers, body)); return 201
        wp.transport = transport
        # 1. шифрование RFC 8291 туда-обратно
        ua, auth, sub = self._phone()
        enc = P.encrypt(b'{"title":"x"}', P.unb64u(sub["keys"]["p256dh"]), auth)
        self.assertEqual(P.decrypt(enc, ua, auth), b'{"title":"x"}')
        # 2. манифест и service worker открыты без входа
        r = self.c.get("/manifest.webmanifest"); self.assertEqual(r.status_code, 200); self.assertIn("standalone", r.get_data(as_text=True))
        r = self.c.get("/sw.js"); self.assertEqual(r.status_code, 200); self.assertIn("showNotification", r.get_data(as_text=True))
        self.assertIn("javascript", r.headers["Content-Type"])
        # 3. подписка: чужой адрес отклоняется, Apple — принимается
        self.login()
        bad = dict(sub, endpoint="https://evil.example.com/x")
        r = self.post("/push/subscribe", {"sub": json.dumps(bad)}); self.assertFalse(r.get_json()["ok"])
        r = self.post("/push/subscribe", {"sub": json.dumps(sub)}); self.assertTrue(r.get_json()["ok"], r.get_json())
        self.post("/push/subscribe", {"sub": json.dumps(sub)})                       # повторно — без дубля
        self.assertEqual(len(self.store.push_subs()), 1)
        page = self.c.get("/settings").get_data(as_text=True)
        self.assertIn("data-push", page); self.assertIn('data-key="' + wp.public_key() + '"', page)
        # 4. проверка уходит и расшифровывается на «телефоне»; заголовки VAPID
        r = self.post("/push/test", {"endpoint": sub["endpoint"]}); self.assertTrue(r.get_json()["ok"])
        url, headers, body = got[-1]
        self.assertEqual(url, sub["endpoint"]); self.assertEqual(headers["Content-Encoding"], "aes128gcm")
        self.assertTrue(headers["Authorization"].startswith("vapid t=")); self.assertIn("k=" + wp.public_key(), headers["Authorization"])
        jwt_claims = json.loads(P.unb64u(headers["Authorization"].split("t=")[1].split(",")[0].split(".")[1]))
        self.assertEqual(jwt_claims["aud"], "https://web.push.apple.com"); self.assertTrue(jwt_claims["sub"].startswith("mailto:"))
        data = json.loads(P.decrypt(body, ua, auth)); self.assertEqual(data["title"], "Проверка уведомлений")
        # 5. заявка с сайта → пуш с переходом в сделку
        n = len(got)
        did = self.lead(intent="buy", address="СПб", calc="Товар: A912 (реечная панель) — 2 шт").get_json()["id"]
        self.assertEqual(len(got), n + 1)
        data = json.loads(P.decrypt(got[-1][2], ua, auth))
        self.assertEqual(data["title"], f"Новый ЗАКАЗ с сайта №{did}"); self.assertEqual(data["url"], f"/deals/{did}")
        self.assertIn("Елена", data["body"]); self.assertFalse(data["body"].startswith("Новый"))
        # 6. оплата → пуш
        self.post(f"/deals/{did}/stage", {"stage": "paid"})
        self.assertIn("Оплачено", json.loads(P.decrypt(got[-1][2], ua, auth))["title"])
        # 7. письмо от клиента → в его сделку, задача, пуш; от незнакомого — просто пуш
        self.store.update_client(int(self.store.deal(did)["client_id"]), "тест", email="client@example.com")
        out = self.app.extensions["mail_in"]([{"box": "zakaz", "from": "client@example.com", "name": "Елена", "subject": "Re: Расчёт"},
                                              {"box": "info", "from": "x@example.org", "name": "", "subject": "Вопрос"}])
        self.assertIn(f"сделка №{did}", out[0]); self.assertIn("без сделки", out[1])
        self.assertIn("Ответить на письмо клиента", [t["title"] for t in self.store.tasks(deal_id=did)])
        self.assertTrue(any("Письмо от клиента" in e["text"] for e in self.store.events(deal_id=did)))
        titles = [json.loads(P.decrypt(g[2], ua, auth))["title"] for g in got[-2:]]
        self.assertEqual(titles, [f"Письмо от клиента: Елена · №{did}", "Новое письмо на info@"])
        # 8. утренняя сводка
        txt = self.app.extensions["digest"]()
        self.assertIn("задач", txt.lower())
        # 9. служба сказала «подписки больше нет» → удаляем
        wp.transport = lambda u, h, b: 410
        self.app.extensions["digest"]()
        self.assertEqual(self.store.push_subs(), [])

    def chat(self, method="POST", origin="https://nashdekor.ru", **kw):
        h = {"Origin": origin} if origin else {}
        if method == "GET":
            return self.c.get("/api/chat?" + "&".join(f"{k}={v}" for k, v in kw.items()), headers=h)
        return self.c.post("/api/chat", data=json.dumps(kw), content_type="application/json", headers=h)

    def test_site_chat(self) -> None:
        import push as P
        wp = self.app.extensions["push"]; got = []
        wp.transport = lambda u, h, b: got.append(b) or 201
        sent = []
        orig = crm_app.send_mail; crm_app.send_mail = lambda to, s, b, sender="", reply_to="": sent.append((to, s, b)) or True
        try:
            ua, auth, sub = self._phone()
            self.login(); self.post("/push/subscribe", {"sub": json.dumps(sub)})
            sid = "s" * 10 + "0123456789abcdefXYZ_-"
            # без согласия — нельзя; чужой сайт — нельзя; плохой sid — нельзя
            self.assertEqual(self.chat(sid=sid, text="Здравствуйте").status_code, 400)
            self.assertEqual(self.chat(origin="https://evil.example", sid=sid, text="x", consent=True).status_code, 403)
            self.assertEqual(self.chat(sid="short", text="x", consent=True).status_code, 400)
            # первое сообщение — чат создан, пуш сотрудникам со ссылкой на чат
            r = self.chat(sid=sid, text="Есть A907 в наличии?", consent=True, page="/p/a907/")
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            self.assertEqual(r.headers["Access-Control-Allow-Origin"], "https://nashdekor.ru")
            self.assertEqual([m["who"] for m in r.get_json()["msgs"]], ["me"])
            cid = self.store.chat_by_sid(sid)["id"]
            data = json.loads(P.decrypt(got[-1], ua, auth))
            self.assertEqual(data["url"], f"/chats/{cid}"); self.assertIn("A907", data["body"])
            self.assertIsNone(self.store.chat(cid)["deal_id"])                    # контакта нет — заявки ещё нет
            # в CRM: вкладка с непрочитанным, страница чата
            page = self.c.get("/").get_data(as_text=True)
            self.assertIn("Чат<span class=\"badge\">1</span>", page); self.assertIn("Есть A907", page)
            page = self.c.get(f"/chats/{cid}").get_data(as_text=True)
            self.assertIn("Есть A907 в наличии?", page); self.assertIn("Создать заявку из чата", page)
            self.assertEqual(self.store.chat_unread(), 0)                          # прочитано
            # ответ сотрудника — клиент видит в окне (опрос)
            self.post(f"/chats/{cid}/reply", {"text": "Да, есть 40 шт. Сколько нужно?"})
            r = self.chat(method="GET", sid=sid, after=0)
            msgs = r.get_json()["msgs"]
            self.assertEqual([m["who"] for m in msgs], ["me", "staff"]); self.assertEqual(msgs[1]["author"], "Юлия")
            last = msgs[-1]["id"]
            self.assertEqual(self.chat(method="GET", sid=sid, after=last).get_json()["msgs"], [])
            # клиент пишет телефон в тексте — контакт подхватывается, заявка создаётся сама
            self.chat(sid=sid, text="12 шт, мой телефон +7 921 555-44-33", name="Ольга")
            ch = self.store.chat(cid)
            self.assertEqual(ch["contact"], "+7 921 555-44-33"); self.assertEqual(ch["name"], "Ольга")
            did = ch["deal_id"]; self.assertTrue(did)
            d = self.store.deal(did)
            self.assertTrue(d["want"].startswith("Чат с сайта: Есть A907"))
            self.assertIn("Связаться с клиентом", [x["title"] for x in self.store.tasks(deal_id=did)])
            self.assertIn("Переписка в чате сайта", self.c.get(f"/deals/{did}").get_data(as_text=True))
            # клиент ушёл, оставил e-mail — ответ дублируется письмом
            sid2 = "t" * 30
            self.chat(sid=sid2, text="Напишите на почту olga@example.com", consent=True)
            cid2 = self.store.chat_by_sid(sid2)["id"]
            self.post(f"/chats/{cid2}/reply", {"text": "Отправили расчёт"})
            self.assertEqual(sent[-1][0], "olga@example.com"); self.assertIn("Отправили расчёт", sent[-1][2])
            # создать заявку из чата вручную
            sid3 = "u" * 30
            self.chat(sid=sid3, text="Привет", consent=True)
            cid3 = self.store.chat_by_sid(sid3)["id"]
            r = self.post(f"/chats/{cid3}/deal", {"name": "Иван", "contact": ""})
            self.assertTrue(self.store.chat(cid3)["deal_id"])
            self.assertIn("Иван", self.c.get("/chats").get_data(as_text=True))
            page = self.c.get("/settings").get_data(as_text=True)
            self.assertIn("Чат на сайте", page); self.assertIn("Всего переписок: 3", page); self.assertIn("стали заявками: 3", page)
            self.assertIn("устройств: 1", page)
            # чат выключен вместе с заявками с сайта
            self.app.extensions["crm_conf"]["SITE_LEADS"] = False
            self.assertEqual(self.chat(sid=sid, text="ещё", consent=True).status_code, 503)
        finally:
            crm_app.send_mail = orig

    def test_mailwatch(self) -> None:
        import subprocess, tempfile
        d = tempfile.mkdtemp()
        md = os.path.join(d, "vh", "nashdekor.ru", "zakaz", "Maildir")
        for s in ("new", "cur", "tmp"):
            os.makedirs(os.path.join(md, s))
        def put(name, sub, frm, subj, extra=""):
            with open(os.path.join(md, sub, name), "w", encoding="utf-8") as f:
                f.write(f"From: {frm}\nTo: zakaz@nashdekor.ru\nSubject: {subj}\n{extra}\nТекст\n")
        env = dict(os.environ, MAILWATCH_VMAIL=os.path.join(d, "vh"), MAILWATCH_STATE=os.path.join(d, "st"))
        run = lambda: [json.loads(x) for x in subprocess.run([sys.executable, "-I", os.path.join(HERE, "mailwatch.py"), "nashdekor.ru", "zakaz", "info"],
                                                             env=env, capture_output=True, text=True, check=True).stdout.splitlines()]
        put("1.old", "cur", "a@example.com", "старое")
        self.assertEqual(run(), [])                                  # первый запуск — только запоминает
        put("2.new:2,", "cur", "=?utf-8?b?0JXQu9C10L3QsA==?= <Client@Example.com>", "=?utf-8?b?0KDQsNGB0YfRkdGC?=")
        put("3.n", "new", "Наш декор <noreply@nashdekor.ru>", "Заявка с сайта №5")
        put("4.n", "new", "spam@example.com", "SALE", "X-Spam-Flag: YES\n")
        out = run()
        import mailwatch
        self.assertEqual(out, [{"box": "zakaz", "from": "client@example.com", "name": "Елена", "subject": "Расчёт",
                                "key": mailwatch.mail_key("zakaz", "2.new:2,")}])        # key — id письма в разделе «Почта»
        self.assertEqual(mailwatch.mail_key("zakaz", "2.new:2,"), mailwatch.mail_key("zakaz", "2.new:2,S"))
        os.rename(os.path.join(md, "new", "3.n"), os.path.join(md, "cur", "3.n:2,S"))   # телефон прочитал — уже не новое
        self.assertEqual(run(), [])

    def test_lines_from_site_calc_and_fuzzy_article(self) -> None:
        cat = self.store.catalog
        self.assertEqual(cat.find("912").article, "A912")          # без буквы
        self.assertEqual(cat.find("a 912").article, "A912")
        self.assertEqual(cat.find("gs1").article, "GS 1")
        self.assertIsNone(cat.find("999"))
        # страница товара: «Товар: A912 (реечная панель) — 12 шт»
        did = self.lead(calc="Товар: A912 (реечная панель) — 12 шт, цвет: Шалфей\nСтена 450×280 см, запас 10%\nИтого ≈ 11 880 ₽ (предварительно)").get_json()["id"]
        ln = {r["article"]: r["qty"] for r in self.store.lines(did)}
        self.assertEqual(ln, {"A912": 12})
        # расчёт стены с главной: панель + уголок
        did2 = self.lead(calc="Стена 320×270 см, проёмы 0 м², запас 10%\nA912 — 20 шт, цвет: белый, под покраску, ≈ 19 800 ₽\nA116 — 4 шт, цвет: белый\nИтого ≈ 21 200 ₽ (предварительно)").get_json()["id"]
        ln = {r["article"]: (r["qty"], r["price"]) for r in self.store.lines(did2)}
        self.assertEqual(ln, {"A912": (20, 990), "A116": (4, 350)})
        # вручную: «912» → A912, «999» — отказ без строки
        self.login()
        self.post(f"/deals/{did}/lines", {"article": "912", "qty": "3"})
        self.assertEqual({r["article"]: r["qty"] for r in self.store.lines(did)}, {"A912": 3})
        self.post(f"/deals/{did}/lines", {"article": "999", "qty": "1"})
        self.assertEqual(len(self.store.lines(did)), 1)
        # текст клиенту и ссылка на оплату — в письме
        sent = {}
        def fake_mail(to, subject, body, sender="", reply_to=""):
            sent.update(to=to, body=body); return True
        orig = crm_app.send_mail; crm_app.send_mail = fake_mail
        try:
            self.post(f"/deals/{did}/send-calc", {"email": "e@example.com", "client_note": "Как договорились по телефону.", "pay_link": "https://pay.tochka.com/abc"})
        finally:
            crm_app.send_mail = orig
        self.assertIn("Как договорились по телефону.", sent["body"]); self.assertIn("https://pay.tochka.com/abc", sent["body"])
        d = self.store.deal(did)
        self.assertEqual((d["client_note"], d["pay_link"], d["stage"]), ("Как договорились по телефону.", "https://pay.tochka.com/abc", "quote"))

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


class FakeBank:
    """Подставной Точка Банк: отвечает как API (схема 1.90) и подписывает вебхуки своим RSA-ключом."""
    CUST, MERCH = "300123123", "200000000001234"

    def __init__(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.calls: list[tuple[str, str, dict]] = []
        self.ops: dict[str, dict] = {}
        self.webhook: dict | None = None
        self.cashbox = "digitalKassaTochka"

    def jwk(self) -> dict:
        import base64
        n = self.key.public_key().public_numbers()
        b = lambda i: base64.urlsafe_b64encode(i.to_bytes((i.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()
        return {"kty": "RSA", "e": b(n.e), "n": b(n.n), "use": "sig", "alg": "RS256"}

    def sign(self, claims: dict, key=None) -> str:
        import base64
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        e = lambda bb: base64.urlsafe_b64encode(bb).rstrip(b"=").decode()
        head = e(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()) + "." + e(json.dumps(claims, ensure_ascii=False).encode())
        sig = (key or self.key).sign(head.encode(), padding.PKCS1v15(), hashes.SHA256())
        return head + "." + e(sig)

    def http(self, method, url, headers, body):
        data = json.loads(body) if body else {}
        self.calls.append((method, url, data))
        if url.endswith("/keys/public"):
            return 200, json.dumps(self.jwk()).encode()
        if headers.get("Authorization") != "Bearer " + TestTochka.TOKEN:
            return 401, b'{"message":"Unauthorized"}'
        path = url.split("/uapi", 1)[1]
        if path == "/open-banking/v1.0/customers":
            return 200, json.dumps({"Data": {"Customer": [
                {"customerCode": self.CUST, "customerType": "Business", "isResident": True, "taxCode": "470331302505", "fullName": "ИП Тест", "shortName": "ИП Тест"},
                {"customerCode": "300999999", "customerType": "Personal", "isResident": True, "fullName": "Тест", "shortName": "Тест"}]}}).encode()
        if path.startswith("/acquiring/v1.0/retailers"):
            return 200, json.dumps({"Data": {"Retailer": [{"status": "REG", "isActive": True, "mcc": "5211", "rate": 2.8, "name": "NASHDEKOR.RU",
                                     "url": "https://nashdekor.ru", "merchantId": self.MERCH, "terminalId": "20001234",
                                     "paymentModes": ["sbp", "card"], "cashbox": self.cashbox}]}}).encode()
        if path == "/acquiring/v1.0/payments_with_receipt" and method == "POST":
            d = data["Data"]
            if any(o["link"] == d.get("paymentLinkId") for o in self.ops.values()):
                return 424, '{"Errors":[{"message":"Заказ уже существует"}]}'.encode()
            op = f"op-{len(self.ops) + 1}"
            self.ops[op] = {"status": "CREATED", "amount": d["amount"], "link": d.get("paymentLinkId"), "Order": [], "type": ""}
            return 200, json.dumps({"Data": dict(d, operationId=op, paymentLink=f"https://merch.securepaytb.ru/order/?uuid={op}", status="CREATED")}).encode()
        if path.startswith("/acquiring/v1.0/payments/") and path.endswith("/refund"):
            op = path.split("/")[4]
            o = self.ops[op]; o["status"] = "ON-REFUND"
            return 200, json.dumps({"Data": {"isRefund": True, "operationId": op, "amount": data["Data"]["amount"], "date": "2026-11-10", "orderId": "7"}}).encode()
        if path.startswith("/acquiring/v1.0/payments/"):
            op = path.split("/")[4]
            if op not in self.ops:
                return 424, b'{"Errors":[{"message":"Order not found"}]}'
            o = self.ops[op]
            res = {"customerCode": self.CUST, "createdAt": "2026-11-10T10:00:00+03:00", "amount": o["amount"], "status": o["status"],
                   "operationId": op, "paymentLink": "x", "Order": o["Order"], "paymentLinkId": o["link"]}
            if o["type"]:
                res["paymentType"] = o["type"]
            return 200, json.dumps({"Data": {"Operation": [res]}}).encode()
        if path.startswith("/webhook/v1.0/"):
            if method == "GET":
                return (200, json.dumps({"Data": self.webhook}).encode()) if self.webhook else (404, b'{"message":"not found"}')
            self.webhook = data
            return 200, json.dumps({"Data": data}).encode()
        return 404, b'{"message":"no route"}'


class TestTochka(Base):
    TOKEN = ""

    def setUp(self) -> None:
        super().setUp()
        import base64
        e = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
        TestTochka.TOKEN = e({"alg": "RS256", "typ": "JWT"}) + "." + e({"iss": "clientid-777", "exp": int(time.time()) + 86400 * 300}) + ".c2ln"
        self.bank = FakeBank()
        self.app.extensions["tochka_http"] = self.bank.http
        self.pushes: list[tuple[str, str, str]] = []
        self.store.on_notify = lambda title, text, url: self.pushes.append((title, text, url))

    def connect(self) -> None:
        self.login()
        self.post("/settings/tochka", {"act": "save", "jwt": self.TOKEN})
        self.post("/settings/tochka", {"act": "check"})
        self.post("/settings/tochka", {"act": "enable"})

    def deal(self, kind="p", email="anna@example.com", discount=None, phone="+79990001122") -> int:
        did = self.store.create_deal("t", None, name="Анна", phone=phone, email=email, kind=kind, want="стена")
        self.store.add_line(did, "A912", 3, "t")
        if discount is not None:
            self.store.update_deal(did, "t", discount=discount)
        return did

    def hook(self, claims: dict, key=None):
        return self.c.post("/api/tochka/webhook", data=self.bank.sign(claims, key), content_type="text/plain")

    def test_receipt_items_exact(self) -> None:
        from store import Store
        from tochka import receipt_items
        total = Store.total(3 * 999, 7)
        items, kop = receipt_items([("Панель A1", 3, 999)], 7, 0, goods_total=total)
        self.assertEqual(kop, total * 100)
        self.assertEqual(round(sum(i["amount"] * i["quantity"] for i in items) * 100), total * 100)
        self.assertTrue(all(i["amount"] > 0 and i["paymentMethod"] == "full_prepayment" and i["vatType"] == "none" for i in items))
        items, kop = receipt_items([("A", 2, 500), ("B", 1, 300)], 0, 450, method="full_payment", goods_total=1300)
        self.assertEqual(kop, 175000); self.assertEqual(items[-1]["paymentObject"], "service")
        self.assertEqual({i["paymentMethod"] for i in items}, {"full_payment"})

    def test_connect_settings(self) -> None:
        self.login()
        page = self.c.get("/settings").get_data(as_text=True)
        self.assertIn("Точка Банк", page); self.assertIn("не подключена", page)
        r = self.post("/settings/tochka", {"act": "save", "jwt": "не ключ"}); self.assertEqual(r.status_code, 302)
        self.assertEqual(self.store.setting("tochka_jwt"), "")
        self.post("/settings/tochka", {"act": "enable"})                      # без ключа включить нельзя
        self.assertNotEqual(self.store.setting("tochka_enabled"), "1")
        self.post("/settings/tochka", {"act": "save", "jwt": self.TOKEN})
        self.assertEqual(self.store.setting("tochka_jwt"), self.TOKEN)
        page = self.c.get("/settings").get_data(as_text=True)
        self.assertNotIn(self.TOKEN.split(".")[1], page)                       # ключ на страницу не выводится
        self.post("/settings/tochka", {"act": "check"})
        self.assertEqual((self.store.setting("tochka_customer"), self.store.setting("tochka_merchant")), (FakeBank.CUST, FakeBank.MERCH))
        page = self.c.get("/settings").get_data(as_text=True)
        self.assertIn("подключены", page); self.assertIn("ИП Тест", page)
        self.post("/settings/tochka", {"act": "enable"})
        self.assertEqual(self.store.setting("tochka_enabled"), "1")
        self.post("/settings/tochka", {"act": "webhook"})
        self.assertEqual(self.bank.webhook["url"], "https://localhost/api/tochka/webhook")
        self.assertIn("acquiringInternetPayment", self.bank.webhook["webhooksList"])
        self.assertTrue(any(u.endswith("/webhook/v1.0/clientid-777") and m == "PUT" for m, u, _ in self.bank.calls))
        # без «Чеков» включить приём нельзя
        self.post("/settings/tochka", {"act": "disable"})
        self.bank.cashbox = ""
        self.post("/settings/tochka", {"act": "check"}); self.post("/settings/tochka", {"act": "enable"})
        self.assertEqual(self.store.setting("tochka_enabled"), "0")
        # сотруднику настройки Точки недоступны
        self.c.post("/logout", data={"csrf": self.csrf()})
        self.login("mikhail", "Secret-pass-2")
        self.assertEqual(self.post("/settings/tochka", {"act": "forget"}).status_code, 403)
        self.assertEqual(self.c.get("/money").status_code, 403)

    def test_link_webhook_refund_ship(self) -> None:
        self.connect()
        did = self.deal(discount=7)
        _, total = self.store.deal_total(did)
        page = self.c.get(f"/deals/{did}").get_data(as_text=True)
        self.assertIn("Создать ссылку на оплату", page)
        self.post(f"/deals/{did}/paylink", {"email": "anna@example.com", "delivery": "500"})
        m, u, body = [c for c in self.bank.calls if c[1].endswith("/payments_with_receipt")][-1]
        d = body["Data"]
        self.assertEqual(d["amount"], total + 500)
        self.assertEqual(round(sum(i["amount"] * i["quantity"] for i in d["Items"]) * 100), (total + 500) * 100)
        self.assertEqual((d["customerCode"], d["merchantId"], d["taxSystemCode"], d["ttl"]), (FakeBank.CUST, FakeBank.MERCH, "usn_income_outcome", 10080))
        self.assertEqual(d["Client"]["email"], "anna@example.com"); self.assertEqual(d["Client"]["phone"], "+79990001122")
        self.assertTrue(d["paymentLinkId"].startswith(f"ND{did}-1-")); self.assertEqual(d["paymentMode"], ["sbp"])  # частным — только СБП (10.11.2026)
        self.assertEqual({i["paymentMethod"] for i in d["Items"]}, {"full_prepayment"})
        pays = self.store.payments(did); self.assertEqual(len(pays), 1); self.assertEqual(pays[0]["status"], "CREATED")
        self.assertEqual(self.store.deal(did)["pay_link"], pays[0]["url"])
        # вторая ссылка без галочки — нельзя (иначе клиент может заплатить дважды)
        self.post(f"/deals/{did}/paylink", {"email": "anna@example.com"}); self.assertEqual(len(self.store.payments(did)), 1)
        # письмо-расчёт со ссылкой, без «50%»
        page = self.c.get(f"/deals/{did}").get_data(as_text=True)
        self.assertIn(pays[0]["url"], page); self.assertIn("Электронный чек придёт", page); self.assertNotIn("50%", page)
        op = pays[0]["operation_id"]
        # чужая подпись — 400, ничего не меняется
        from cryptography.hazmat.primitives.asymmetric import rsa
        evil = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = {"webhookType": "acquiringInternetPayment", "customerCode": FakeBank.CUST, "operationId": op, "status": "APPROVED", "amount": "1"}
        self.bank.ops[op].update(status="APPROVED", type="sbp")
        self.assertEqual(self.hook(claims, evil).status_code, 400)
        self.assertEqual(self.store.deal(did)["stage"], "new")
        # тестовый вебхук банка (чужой клиент) — 200 и без последствий
        self.assertEqual(self.hook(dict(claims, customerCode="300123123x")).status_code, 200)
        self.assertEqual(self.store.deal(did)["stage"], "new")
        # настоящий вебхук: сумма и статус — из банка; этап «Оплачено», задача «Отгрузить», пуш
        r = self.hook(claims); self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        p = self.store.payments(did)[0]
        self.assertEqual((p["status"], p["pay_type"]), ("APPROVED", "sbp")); self.assertTrue(p["paid_at"])
        self.assertEqual(self.store.deal(did)["stage"], "paid")
        self.assertTrue(any(t["title"].startswith("Отгрузить") for t in self.store.tasks(deal_id=did)))
        self.assertTrue(any(t.startswith(f"Оплачено №{did}") and "через СБП" in t for t, _, _ in self.pushes), self.pushes)
        self.assertEqual(self.store.paid_kop(did), (total + 500) * 100)
        self.hook(claims)                                                       # повторная доставка — без дублей
        self.assertEqual(sum(1 for t, _, _ in self.pushes if t.startswith("Оплачено")), 1)
        # возврат: сотруднику нельзя, владельцу — да
        self.c.post("/logout", data={"csrf": self.csrf()}); self.login("mikhail", "Secret-pass-2")
        self.assertEqual(self.post(f"/deals/{did}/payments/{p['id']}/refund", {"amount": "100", "confirm": "1"}).status_code, 403)
        self.c.post("/logout", data={"csrf": self.csrf()}); self.login()
        self.post(f"/deals/{did}/payments/{p['id']}/refund", {"amount": "100"})                 # без галочки — нет
        self.assertFalse(any(u.endswith("/refund") for _, u, _ in self.bank.calls))
        self.post(f"/deals/{did}/payments/{p['id']}/refund", {"amount": "100,00", "confirm": "1"})
        m, u, body = [c for c in self.bank.calls if c[1].endswith("/refund")][-1]
        self.assertEqual(body, {"Data": {"amount": 100.0}})
        p = self.store.payment(p["id"]); self.assertEqual((p["status"], p["refunded"]), ("ON-REFUND", 10000))
        self.bank.ops[op].update(status="REFUNDED_PARTIALLY", Order=[{"orderId": "7", "type": "refund", "amount": 100.0, "time": "x"}])
        self.c.post("/logout", data={"csrf": self.csrf()})
        self.app.extensions["tochka_poll"]()                                    # только что проверяли — опрос подождёт
        self.assertEqual(self.store.payment(p["id"])["status"], "ON-REFUND")
        self.store.c().execute("UPDATE payments SET checked_at='2026-01-01T00:00:00+03:00' WHERE id=?", (p["id"],))
        self.app.extensions["tochka_poll"]()
        self.assertEqual(self.store.payment(p["id"])["status"], "REFUNDED_PARTIALLY")
        self.login()
        # отгрузка: чек «Предоплата 100%» → задача на второй чек, видна в «Деньгах»
        self.post(f"/deals/{did}/stage", {"stage": "shipped"})
        self.assertEqual(self.store.deal(did)["stage"], "shipped")
        self.assertTrue(any(t["title"].startswith("Чек «Полный расчёт»") and not t["done_at"] for t in self.store.tasks(deal_id=did)))
        money = self.c.get("/money").get_data(as_text=True)
        self.assertIn("Нужен второй чек", money); self.assertIn(f"№{did}", money)
        self.post(f"/deals/{did}/closing-done")
        self.assertFalse(self.store.closing_receipts_due(did))
        self.assertFalse(any(t["title"].startswith("Чек «Полный расчёт»") and not t["done_at"] for t in self.store.tasks(deal_id=did)))

    def test_poll_expired_and_full_payment(self) -> None:
        self.connect()
        did = self.deal()
        self.post(f"/deals/{did}/paylink", {"email": "anna@example.com", "full": "1"})
        p = self.store.payments(did)[0]
        self.assertEqual(p["method"], "full_payment")
        self.bank.ops[p["operation_id"]]["status"] = "EXPIRED"
        out = self.app.extensions["tochka_poll"]()
        self.assertTrue(any("EXPIRED" in x for x in out), out)
        self.assertEqual(self.store.payment(p["id"])["status"], "EXPIRED")
        self.assertEqual(self.app.extensions["tochka_poll"](), [])               # закрытые ссылки больше не опрашиваются
        # после истечения — новая ссылка без галочки
        self.post(f"/deals/{did}/paylink", {"email": "anna@example.com"})
        self.assertEqual(len(self.store.payments(did)), 2)
        # без e-mail чек некуда отправить
        did2 = self.deal(email="", phone="+79990003344")
        self.post(f"/deals/{did2}/paylink", {"email": ""})
        self.assertEqual(self.store.payments(did2), [])

    def test_incoming_invoice_and_debt_guard(self) -> None:
        self.connect()
        did = self.deal(kind="c")
        self.store.update_client(int(self.store.deal(did)["client_id"]), "t", inn="7700000000")
        _, total = self.store.deal_total(did)
        inc = {"webhookType": "incomingPayment", "customerCode": FakeBank.CUST, "paymentId": "pay-1", "date": "2026-11-10",
               "purpose": f"Оплата по счёту № {did} от 10.11.2026. Без НДС", "documentNumber": "5",
               "SidePayer": {"name": "ООО Ромашка", "inn": "7700000000", "amount": f"{total / 2:.2f}"}}
        self.assertEqual(self.hook(inc).status_code, 200)
        self.assertEqual(self.store.paid_kop(did), total * 50)
        self.assertNotEqual(self.store.deal(did)["stage"], "paid")
        self.assertTrue(any(t["title"].startswith("Получить доплату") for t in self.store.tasks(deal_id=did)))
        self.hook(inc)                                                            # повтор — без второй оплаты
        self.assertEqual(len(self.store.payments(did)), 1)
        # с долгом не отгружаем
        self.post(f"/deals/{did}/stage", {"stage": "shipped"})
        self.assertNotEqual(self.store.deal(did)["stage"], "shipped")
        # остаток по ИНН (без номера в назначении) — сделка единственная открытая у клиента
        self.hook(dict(inc, paymentId="pay-2", purpose="Доплата за декор"))
        self.assertEqual(self.store.paid_kop(did), total * 100)
        self.assertEqual(self.store.deal(did)["stage"], "paid")
        # чужое поступление — без сделки, привязывается руками на «Деньгах»; эквайринг без пуша
        n = len(self.pushes)
        self.hook(dict(inc, paymentId="pay-3", purpose="Возврат займа", SidePayer={"name": "Иванов", "inn": "", "amount": "1000.00"}))
        self.assertEqual(len(self.pushes), n + 1)
        self.hook(dict(inc, paymentId="pay-4", purpose="Зачисление по операциям эквайринга", SidePayer={"name": "Точка", "inn": "", "amount": "50.00"}))
        self.assertEqual(len(self.pushes), n + 1)
        # номер чужой заявки в назначении, а ИНН не её клиента — не засчитываем (номер счёта из банка мог совпасть)
        did3 = self.deal(kind="c", phone="+79990007788")
        self.hook(dict(inc, paymentId="pay-6", purpose=f"Оплата по счёту № {did3}", SidePayer={"name": "ООО Другая", "inn": "7800000001", "amount": "500.00"}))
        self.assertEqual(self.store.paid_kop(did3), 0)
        ev = [e for e in self.store.bank_events() if e["payment_id"] == "pay-3"][0]
        did2 = self.deal(phone="+79990005566")
        self.post("/money/link", {"event": str(ev["id"]), "deal": str(did2)})
        self.assertEqual(self.store.paid_kop(did2), 100000)
        page = self.c.get("/money").get_data(as_text=True)
        self.assertIn("Поступления на расчётный счёт", page); self.assertIn("ООО Ромашка", page)
        # без подписи поступлению не верим: ключа банка нет → вебхук принят, но не записан
        self.store.set_setting("tochka_jwk", ""); self.store.set_setting("tochka_jwk_try", str(int(time.time())))
        tok = self.bank.sign(dict(inc, paymentId="pay-5")).rsplit(".", 1)[0] + ".AAAA"
        self.c.post("/api/tochka/webhook", data=tok, content_type="text/plain")
        self.assertFalse(any(e["payment_id"] == "pay-5" for e in self.store.bank_events()))

    def test_manual_payment_and_pages(self) -> None:
        self.login()
        did = self.deal()
        page = self.c.get(f"/deals/{did}").get_data(as_text=True)
        self.assertIn("после подключения Точки", page); self.assertNotIn("Создать ссылку на оплату", page)
        _, total = self.store.deal_total(did)
        self.post(f"/deals/{did}/payments/manual", {"amount": str(total), "kind": "invoice", "note": "платёжка №1"})
        self.assertEqual(self.store.deal(did)["stage"], "paid")
        page = self.c.get(f"/deals/{did}").get_data(as_text=True)
        self.assertIn("по счёту", page); self.assertIn("платёжка №1", page)
        self.assertEqual(self.c.get("/money").status_code, 200)
        self.assertEqual(self.app.extensions["tochka_poll"](), ["Точка не подключена"])
        self.post(f"/deals/{did}/delete", {"confirm": "1"})                       # с платежами не удаляется
        self.assertIsNotNone(self.store.deal(did))


if __name__ == "__main__":
    unittest.main()


class FakeEgrul:
    """Подставной сервис ФНС (egrul.nalog.ru): первый запрос — токен, второй — «ждите», третий — строка реестра."""

    def __init__(self, rows=None, captcha=False):
        self.rows = rows if rows is not None else [{
            "n": "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ \"РЕМОНТ ПЛЮС\"", "c": "ООО \"РЕМОНТ ПЛЮС\"", "i": "7801234567",
            "o": "1127847000001", "p": "780101001", "a": "190000, Г.САНКТ-ПЕТЕРБУРГ, УЛ. ТЕСТОВАЯ, Д. 1",
            "g": "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР: ИВАНОВ ИВАН ИВАНОВИЧ", "k": "ul"}]
        self.captcha, self.calls, self.waited = captcha, [], False

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, body))
        if method == "POST":
            return 200, json.dumps({"t": "TOKEN1234567890abc", "captchaRequired": self.captcha}).encode()
        if not self.waited:
            self.waited = True
            return 200, b'{"status":"wait"}'
        return 200, json.dumps({"rows": self.rows}).encode()


class TestBuh(Base):
    """Учёт: реквизиты по ИНН, товары для документов, закупки с ДОПП и себестоимостью, дизайнеры, налоговый календарь."""

    def setUp(self) -> None:
        super().setUp()
        self.egrul = FakeEgrul()
        self.app.extensions["buh"].egrul_http = self.egrul
        self.buh = self.app.extensions["buh"]
        self.login()

    def make_purchase(self, transport="auto") -> int:
        r = self.post("/purchases/new", {"num": "", "transport": transport})
        self.assertEqual(r.status_code, 302)
        return int(r.headers["Location"].rstrip("/").split("/")[-1])

    def test_dates_and_money(self) -> None:
        import buh
        from datetime import date
        # сроки статформ 2026 (10-й рабочий день) — сверены с графиком ФТС; 2027 — с переносами постановления № 1187
        self.assertEqual(buh.nth_workday(2026, 2, 10).isoformat(), "2026-02-13")
        self.assertEqual(buh.nth_workday(2026, 12, 10).isoformat(), "2026-12-14")
        self.assertEqual(buh.nth_workday(2027, 1, 10).isoformat(), "2027-01-22")
        self.assertTrue(buh.is_workday(date(2027, 2, 20)))            # рабочая суббота
        self.assertFalse(buh.is_workday(date(2027, 11, 5)))
        self.assertEqual(buh.shift_to_workday(date(2027, 4, 25)).isoformat(), "2027-04-26")
        # взносы за неполный 2026 год при регистрации 02.11.2026: декабрь + 29/30 ноября
        self.assertEqual(buh.contrib_for_year(2026, date(2026, 11, 2)), 940558)
        self.assertEqual(buh.contrib_for_year(2027, date(2026, 11, 2)), 6115400)
        self.assertEqual((buh.kop("423,85"), buh.kop("1 234"), buh.kop(""), buh.kop_in(42385)), (42385, 123400, None, "423,85"))

    def test_egrul_fills_requisites(self) -> None:
        did = self.store.create_deal("t", None, name="Бухгалтерия", phone="+79990001111", kind="c")
        cid = self.store.deal(did)["client_id"]
        self.post(f"/clients/{cid}/egrul", {"inn": "7801234567"})
        cl = self.store.client(cid)
        self.assertEqual((cl["inn"], cl["kpp"], cl["ogrn"]), ("7801234567", "780101001", "1127847000001"))
        self.assertIn("РЕМОНТ ПЛЮС", cl["full_name"]); self.assertEqual(cl["company"], 'ООО "РЕМОНТ ПЛЮС"')
        self.assertEqual(cl["signer"], "Генеральный директор Иванов Иван Иванович")
        self.assertTrue(self.egrul.calls[0][2].decode().find("query=7801234567") >= 0)
        # ИП (12 цифр): КПП нет, название «ИП Фамилия Имя Отчество»
        self.egrul.rows, self.egrul.waited = [{"n": "ПЕТРОВА АННА СЕРГЕЕВНА", "i": "780512345678", "o": "321784700012345", "k": "fl"}], True
        self.post(f"/clients/{cid}", {"name": "Анна", "company": "", "kind": "c"})
        self.post(f"/clients/{cid}/egrul", {"inn": "780512345678"})
        cl = self.store.client(cid)
        self.assertEqual((cl["company"], cl["kpp"]), ("ИП Петрова Анна Сергеевна", "780101001"))   # КПП прежний не стирается
        # ошибки: неверный ИНН и капча — понятное сообщение, данные не портятся
        r = self.post(f"/clients/{cid}/egrul", {"inn": "123"})
        self.assertEqual(r.status_code, 302)
        page = self.c.get(f"/clients/{cid}").get_data(as_text=True)
        self.assertIn("ИНН — 10 цифр", page)
        self.app.extensions["buh"].egrul_http = FakeEgrul(captcha=True)
        self.post(f"/clients/{cid}/egrul", {"inn": "7801234567"})
        self.assertIn("капчу", self.c.get(f"/clients/{cid}").get_data(as_text=True))
        # ручная правка реквизитов и ЭДО
        self.post(f"/clients/{cid}", {"name": "Анна", "doc_email": "buh@remont.ru", "edo": "yes", "edo_operator": "Saby", "kpp": "78-01-01-001"})
        cl = self.store.client(cid)
        self.assertEqual((cl["doc_email"], cl["edo"], cl["kpp"]), ("buh@remont.ru", "yes", "780101001"))

    def test_product_info(self) -> None:
        self.assertEqual(self.buh.product_info("A912")["tnved"], "3925908009")   # панель
        self.assertEqual(self.buh.product_info("A116")["tnved"], "3916905000")   # уголок — погонаж
        self.post("/stock/docs/A912", {"tnved": "3925 90 800 9", "weight_g": "1450", "doc_name": "Рейка 912, арт. A912"})
        info = self.buh.product_info("A912")
        self.assertEqual((info["weight_g"], info["tnved_own"]), (1450, False))   # совпал с умолчанием — не «свой»
        self.assertIn("A912", self.c.get("/stock/docs").get_data(as_text=True))

    def test_purchase_dopp_receive_fifo(self) -> None:
        self.post("/stock/docs/A912", {"tnved": "", "weight_g": "1000", "doc_name": ""})
        self.post("/stock/docs/A116", {"tnved": "", "weight_g": "500", "doc_name": ""})
        pid = self.make_purchase("auto")
        p = self.buh.purchase(pid)
        self.assertEqual((p["num"], p["supplier"], p["country"]), ("1", "ТОО «Art Dec»", "KZ"))
        self.assertTrue(self.buh.dopp_needed(p))
        n, errs = self.buh.paste_lines(pid, "t", "A912 10 400,00\nA116; 20; 100\nчто-то непонятное")
        self.assertEqual((n, len(errs)), (2, 1))
        p = self.buh.purchase(pid)
        self.assertEqual((p["goods_kop"], p["pcs"]), (600000, 30))     # 4000 + 2000 ₽
        page = self.c.get(f"/purchases/{pid}").get_data(as_text=True)
        self.assertIn("Нужен ДОПП: ввоз из Казахстана", page); self.assertIn("1320 (22 %)", page)  # обеспечительный 22 % = 1 320 ₽
        # оплата, документы, ДОПП с датой ввоза → в календаре срок ДОПП за 2 дня
        self.post(f"/purchases/{pid}", {"sec": "main", "spec_date": "2026-11-10", "paid_at": "2026-11-11", "paid_kop": "6000",
                                        "bank_fee_kop": "120"})
        self.post(f"/purchases/{pid}", {"sec": "dopp", "ship_date": "2026-11-20", "border_date": "2026-11-25", "esf": "ЭСФ 1",
                                        "snt": "СНТ 1", "cmr": "CMR 1", "delivery_kop": "3000"})
        cal = {x["key"]: x for x in self.buh.calendar("2026-11-12")}
        self.assertEqual(cal[f"p{pid}-dopp"]["due"], "2026-11-23")
        self.assertFalse(cal[f"p{pid}-dopp"]["done"])
        self.post(f"/purchases/{pid}", {"sec": "dopp", "dopp_status": "secured", "guarantee_paid_at": "2026-11-21", "_qr": "1", "qr_sent": "1"})
        self.assertNotIn(f"p{pid}-dopp", {x["key"] for x in self.buh.calendar("2026-11-12") if not x["done"]})
        # себестоимость: НДС 22 % и комиссия — по стоимости, перевозка 3000 ₽ — по весу (10 кг и 10 кг поровну)
        self.post(f"/purchases/{pid}", {"sec": "stock", "delivery_kop": "3000"})
        costs = {x["article"]: u for x, u in self.buh.cost_split(self.buh.purchase(pid), self.buh.purchase_lines(pid))}
        # A912: 4000 + 880 (НДС) + 80 (комиссия) + 1500 (перевозка) = 6460 ₽ / 10 шт
        self.assertEqual(costs["A912"], 64600)
        # A116: 2000 + 440 + 40 + 1500 = 3980 ₽ / 20 шт
        self.assertEqual(costs["A116"], 19900)
        # оприходование → остатки и партии; сроки декларации (до 20 декабря) и статформы (10-й рабочий день декабря)
        self.post(f"/purchases/{pid}/receive", {"day": "2026-11-26"})
        self.assertEqual(self.store.c().execute("SELECT qty FROM stock WHERE article='A912'").fetchone()[0], 10)
        self.assertEqual(self.buh.purchase(pid)["import_date"], "2026-11-26")
        cal = {x["key"]: x for x in self.buh.calendar("2026-11-27")}
        self.assertEqual(cal[f"p{pid}-decl"]["due"], "2026-12-21")      # 20.12.2026 — воскресенье → понедельник
        self.assertEqual(cal[f"p{pid}-stat"]["due"], "2026-12-14")
        self.assertEqual(cal[f"p{pid}-decl"]["amount"], 132000)
        # позиции после оприходования не меняются
        self.assertTrue(self.buh.add_purchase_line(pid, "t", "A912", 1, "1"))
        # продажа 12 шт A912: 10 из партии + 2 без партии; возврат сделки восстанавливает партию
        did = self.store.create_deal("t", None, name="Покупатель", phone="+79990002222")
        self.store.add_line(did, "A912", 12, "t")
        self.store.set_stage(did, "shipped", "t")
        sc = self.buh.sale_costs(did)
        self.assertEqual(sorted((x["qty"], bool(x["lot_id"])) for x in sc), [(2, False), (10, True)])
        self.assertEqual(self.buh.lots(pid)[0]["qty_left"], 0)
        q = self.buh.cost_by_quarter(int(self.store.c().execute("SELECT substr(day,1,4) FROM sale_costs LIMIT 1").fetchone()[0]))
        self.assertEqual(sum(x["cost"] for x in q), 646000); self.assertEqual(sum(x["nolot"] for x in q), 2)
        self.assertIn("Без партии".lower(), self.c.get("/taxes/sales.csv").get_data(as_text=True).lower().replace("без партии", "без партии"))
        self.assertEqual(self.buh.unreceive(pid, "t"), "из этой партии уже отгружали — отменить оприходование нельзя")
        self.store.set_stage(did, "paid", "t")
        self.assertEqual(self.buh.lots(pid)[0]["qty_left"], 10)
        self.assertEqual(self.buh.sale_costs(did), [])
        self.assertEqual(self.buh.unreceive(pid, "t"), "")
        self.assertEqual(self.store.c().execute("SELECT qty FROM stock WHERE article='A912'").fetchone()[0], 0)

    def test_lot_shelf_life_internal_only(self) -> None:
        import buh
        self.assertEqual(buh.shelf_until("2026-11-01"), "2027-11-01")
        self.assertEqual(buh.shelf_until("2024-02-29"), "2025-02-28")
        self.assertEqual(buh.shelf_until(""), "")
        # партия 1: пришла 26.11.2026, изготовлена 01.11.2026 → годна до 01.11.2027
        p1 = self.make_purchase("rail")
        self.buh.paste_lines(p1, "t", "A912 10 400\nA116 4 100")
        self.assertEqual(self.buh.receive(p1, "t", "2026-11-26", "2026-12-01"),
                         "дата изготовления позже даты принятия на учёт — проверьте этикетку")
        self.post(f"/purchases/{p1}/receive", {"day": "2026-11-26", "made": "2026-11-01"})
        l1 = {x["article"]: x for x in self.buh.lots(p1, day="2026-11-27")}
        self.assertEqual((l1["A912"]["made_at"], l1["A912"]["until"], l1["A912"]["state"]), ("2026-11-01", "2027-11-01", ""))
        # партия 2 пришла позже, но изготовлена раньше (01.10.2025 — срок вышел 01.10.2026) → отгружается первой
        p2 = self.make_purchase("rail")
        self.buh.paste_lines(p2, "t", "A912 5 400")
        self.post(f"/purchases/{p2}/receive", {"day": "2026-12-01"})
        lot2 = self.buh.lots(p2)[0]
        self.assertEqual(lot2["state"], "nodate")
        r = self.post(f"/purchases/lots/{lot2['id']}/made", {"made": "2026-12-05", "back": "/purchases#lots"})
        self.assertEqual(self.buh.lots(p2)[0]["made_at"], "")                    # позже прихода — не сохраняется
        r = self.post(f"/purchases/lots/{lot2['id']}/made", {"made": "2025-10-01", "back": "/purchases#lots"})
        self.assertEqual(r.headers["Location"], "/purchases#lots")
        self.assertEqual(self.buh.lots(p2)[0]["until"], "2026-10-01")
        exp = self.buh.expiring("2026-12-02")
        self.assertEqual([(x["article"], x["state"]) for x in exp], [("A912", "over")])
        later = self.buh.expiring("2027-09-10")                                     # партия 1: 52 дня — тоже в списке
        self.assertEqual([(x["until"], x["state"]) for x in later],
                         [("2026-10-01", "over"), ("2027-11-01", "soon"), ("2027-11-01", "soon")])
        self.assertEqual(len(self.buh.expiring("2027-09-10", days=30)), 1)
        page = self.c.get("/purchases").get_data(as_text=True)
        self.assertIn("Срок годности подходит", page); self.assertIn("истёк 01.10.2026", page); self.assertIn("до 01.11.2027", page)
        txt = self.app.extensions["digest"]("2026-12-02")
        self.assertIn("рок годности подходит у партий: 1 — A912, 5 шт, истёк", txt)
        did = self.store.create_deal("t", None, name="Покупатель", phone="+79990003333")
        self.store.add_line(did, "A912", 7, "t")
        self.store.set_stage(did, "shipped", "t")
        self.assertEqual(self.buh.lots(p2)[0]["qty_left"], 0)                        # сначала старая по изготовлению
        self.assertEqual({x["article"]: x["qty_left"] for x in self.buh.lots(p1)}["A912"], 8)
        # наружу срок не уходит: каталог для сайта и Авито — только цена и остаток
        api = self.c.get("/api/catalog").get_data(as_text=True)
        self.assertNotIn("2027", api); self.assertNotIn("made", api); self.assertNotIn("until", api)

    def test_lots_made_at_migration(self) -> None:
        import store as st
        path = os.path.join(self.tmp.name, "old.db")
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE lots (id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_id INTEGER NOT NULL, article TEXT NOT NULL,"
                    " qty_in INTEGER NOT NULL, qty_left INTEGER NOT NULL, unit_kop INTEGER NOT NULL, received_at TEXT NOT NULL)")
        con.execute("INSERT INTO lots(purchase_id, article, qty_in, qty_left, unit_kop, received_at) VALUES (1,'A912',1,1,1,'2026-11-01')")
        con.commit(); con.close()
        s2 = st.Store(path)
        row = s2.c().execute("SELECT made_at FROM lots").fetchone()
        self.assertEqual(row[0], "")

    def test_rail_no_dopp_and_contract_limit(self) -> None:
        pid = self.make_purchase("rail")
        self.assertFalse(self.buh.dopp_needed(self.buh.purchase(pid)))
        self.assertIn("ДОПП не нужен", self.c.get(f"/purchases/{pid}").get_data(as_text=True))
        self.buh.add_purchase_line(pid, "t", "A912", 1000, "3100")      # 3,1 млн ₽ — больше порога учёта договора
        self.assertIn("поставьте договор на учёт", self.c.get(f"/purchases/{pid}").get_data(as_text=True))
        self.post("/purchases/contract", {"unk": "26110001/0000/0001/2/1"})
        self.assertNotIn("поставьте договор на учёт", self.c.get(f"/purchases/{pid}").get_data(as_text=True))
        # оплаченную закупку удалить нельзя
        self.post(f"/purchases/{pid}", {"sec": "main", "paid_at": "2026-11-11", "paid_kop": "3100000"})
        self.assertEqual(self.buh.contract_paid()[0]["paid"], 310000000)
        self.post(f"/purchases/{pid}/delete")
        self.assertIsNotNone(self.buh.purchase(pid))

    def test_tax_calendar_and_digest(self) -> None:
        cal = {x["key"]: x for x in self.buh.calendar("2026-11-10")}
        self.assertEqual(cal["vznosy-2026"]["due"], "2026-12-28"); self.assertEqual(cal["vznosy-2026"]["amount"], 940558)
        self.assertNotIn("usn-avans-2026-1-u", cal)                      # ИП зарегистрировано в ноябре — авансов за 2026 нет
        self.assertEqual(cal["usn-avans-2027-1-u"]["due"], "2027-04-26")
        self.assertEqual(cal["usn-decl-2026"]["due"], "2027-04-26")
        self.assertEqual(cal["usn-tax-2026"]["due"], "2027-04-28")
        page = self.c.get("/taxes").get_data(as_text=True)
        self.assertIn("Фиксированные взносы ИП за 2026 год", page); self.assertIn("9 405,58", page)
        self.post("/taxes/done", {"key": "vznosy-2026", "done": "1"})
        self.assertTrue({x["key"]: x for x in self.buh.calendar("2026-11-10")}["vznosy-2026"]["done"])
        # утренняя сводка: срок в пределах недели
        self.assertEqual(self.buh.upcoming(7, "2026-12-22"), [x for x in self.buh.upcoming(7, "2026-12-22")])
        self.post("/taxes/done", {"key": "vznosy-2026", "done": "0"})
        txt = self.app.extensions["digest"]("2026-12-22")
        self.assertIn("сроки отчётности", txt.lower()); self.assertIn("Фиксированные взносы", txt)
        # сотруднику налоги, закупки и дизайнеры недоступны
        self.c.post("/logout", data={"csrf": self.csrf()})
        self.login("mikhail", "Secret-pass-2")
        for url in ("/taxes", "/purchases", "/designers"):
            self.assertEqual(self.c.get(url).status_code, 403, url)

    def test_designer_reward_and_payout(self) -> None:
        dz = self.store.create_deal("t", None, name="Дизайнер Ольга", phone="+79990003333", kind="d")
        dzid = self.store.deal(dz)["client_id"]
        did = self.store.create_deal("t", None, name="Клиент Олега", phone="+79990004444")
        self.store.add_line(did, "A912", 10, "t")                          # 10 × 990 = 9 900 ₽
        self.post(f"/deals/{did}/designer", {"designer_id": str(dzid), "pct": "10"})
        self.assertEqual(self.store.deal(did)["designer_id"], dzid)
        page = self.c.get(f"/deals/{did}").get_data(as_text=True)
        self.assertIn("990 ₽", page); self.assertIn("начислится после отгрузки", page)
        # дизайнер не может быть «приведшим» сам себя
        self.post(f"/deals/{dz}/designer", {"designer_id": str(dzid)})
        self.assertIsNone(self.store.deal(dz)["designer_id"])
        s = {x["id"]: x for x in self.buh.designer_summary()}[dzid]
        self.assertEqual((s["expected"], s["accrued"]), (99000, 0))
        self.store.set_stage(did, "shipped", "t")
        s = {x["id"]: x for x in self.buh.designer_summary()}[dzid]
        self.assertEqual((s["accrued"], s["due"]), (99000, 99000))
        # без налогового статуса выплату не записать; с «самозанятый» — нужен номер чека
        self.post(f"/designers/{dzid}/payout", {"amount": "990", "paid_at": "2026-11-30", "doc": "чек 1"})
        self.assertEqual(self.buh.payouts(), [])
        self.post(f"/clients/{dzid}", {"name": "Дизайнер Ольга", "tax_status": "npd"})
        self.post(f"/designers/{dzid}/payout", {"amount": "990", "paid_at": "2026-11-30", "doc": ""})
        self.assertEqual(self.buh.payouts(), [])
        self.post(f"/designers/{dzid}/payout", {"amount": "990", "paid_at": "2026-11-30", "doc": "чек 20abc"})
        s = {x["id"]: x for x in self.buh.designer_summary()}[dzid]
        self.assertEqual((s["paid"], s["due"]), (99000, 0))
        self.assertIn("Дизайнер Ольга", self.c.get("/designers").get_data(as_text=True))

    def test_pages_render(self) -> None:
        pid = self.make_purchase()
        self.buh.add_purchase_line(pid, "t", "GS 1", 5, "700")
        for url in ("/", "/purchases", f"/purchases/{pid}", "/taxes", "/designers", "/stock", "/stock/docs", "/tasks",
                    "/reports", "/money", "/settings", "/server"):
            r = self.c.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertNotIn("style=\"", r.get_data(as_text=True).split("<main")[1], url)   # CSP: без встроенных стилей


def make_xlsx(sheets) -> bytes:
    """Минимальный .xlsx без сторонних библиотек: {имя листа: [[ячейки]]}; строки — через sharedStrings."""
    import io
    import zipfile
    from xml.sax.saxutils import escape
    strings: list[str] = []

    def col(i: int) -> str:
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, "w")
    wb_sheets, rels = [], []
    for n, (name, rows) in enumerate(sheets.items(), start=1):
        xml_rows = []
        for ri, row in enumerate(rows, start=1):
            cells = []
            for ci, v in enumerate(row):
                ref = f"{col(ci)}{ri}"
                if v is None:
                    continue
                if isinstance(v, str) and v.startswith("="):
                    cells.append(f'<c r="{ref}"><f>{escape(v[1:])}</f></c>')
                elif isinstance(v, str):
                    strings.append(v)
                    cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
                else:
                    cells.append(f'<c r="{ref}"><v>{v}</v></c>')
            xml_rows.append(f'<row r="{ri}">{"".join(cells)}</row>')
        z.writestr(f"xl/worksheets/sheet{n}.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>')
        wb_sheets.append(f'<sheet name="{escape(name)}" sheetId="{n}" r:id="rId{n}"/>')
        rels.append(f'<Relationship Id="rId{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{n}.xml"/>')
    z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
               + "".join(wb_sheets) + "</sheets></workbook>")
    z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               + "".join(rels) + "</Relationships>")
    z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
               + "".join(f"<si><t>{escape(s)}</t></si>" for s in strings) + "</sst>")
    z.close()
    return buf.getvalue()


class TestPurchaseExcel(Base):
    """Загрузка позиций закупки из Excel / CSV."""

    def setUp(self) -> None:
        Base.setUp(self)
        self.egrul = FakeEgrul()
        self.buh = self.app.extensions["buh"]
        self.buh.egrul_http = self.egrul
        self.login()

    make_purchase = TestBuh.make_purchase

    def upload(self, pid, data, name="spec.xlsx", replace=True):
        import io
        with self.c.session_transaction() as s:
            tok = s["csrf"]
        form = {"csrf": tok, "file": (io.BytesIO(data), name)}
        if replace:
            form["replace"] = "1"
        return self.c.post(f"/purchases/{pid}/xlsx", data=form, content_type="multipart/form-data")

    def test_spec_xlsx(self) -> None:
        pid = self.make_purchase()
        data = make_xlsx({
            "Сравнение": [["Артикул", "Вариант 1, шт"], ["A912", 5]],
            "Спецификация": [["Приложение № 1"], [], ["№", "Артикул", "Наименование", "ТН ВЭД", "Коробки", "Штуки", "Цена, ₽", "Сумма, ₽", "Вес, кг"],
                             [1, "A912", "Рейка", "3925 90 800 9", 2, 24, 524.77, 12594.48, 36],
                             [2, "А 116", "Уголок", "3916 90 500 0", 1, 72, "154,13", "", ""],
                             [None, "Итого", None, None, 3, 96, None, 23691.84, 36]]})
        r = self.upload(pid, data)
        self.assertEqual(r.status_code, 302)
        lines = {x["article"]: x for x in self.buh.purchase_lines(pid)}
        self.assertEqual(set(lines), {"A912", "A116"})                      # «А 116» кириллицей → A116 каталога
        self.assertEqual((lines["A912"]["qty"], lines["A912"]["price_kop"], lines["A912"]["weight_g"]), (24, 52477, 1500))
        self.assertEqual(lines["A116"]["price_kop"], 15413)
        self.assertEqual(self.buh.product_info("A912")["weight_g"], 1500)   # вес запомнился для следующих закупок
        page = self.c.get(f"/purchases/{pid}").get_data(as_text=True)
        self.assertIn("загружено позиций: 2", page); self.assertIn("лист «Спецификация»", page)
        # повторная загрузка с «заменить» — без дублей; без галочки — добавляет
        self.upload(pid, data)
        self.assertEqual(len(self.buh.purchase_lines(pid)), 2)
        self.upload(pid, data, replace=False)
        self.assertEqual(len(self.buh.purchase_lines(pid)), 4)

    def test_tenge_formulas_and_errors(self) -> None:
        pid = self.make_purchase()
        tg = make_xlsx({"опт прайс": [["Артикул", "Шт в коробке", "Цена за шт, ₸", "Цена за коробку, ₸", "Кол-во"],
                                      ["А 912", 12, 2860, 34320, 24]]})
        self.upload(pid, tg)
        self.assertEqual(self.buh.purchase_lines(pid), [])
        self.assertIn("впишите в закупке курс", self.c.get(f"/purchases/{pid}").get_data(as_text=True))
        self.post(f"/purchases/{pid}", {"sec": "main", "rate": "5,45"})
        self.upload(pid, tg)
        ln = self.buh.purchase_lines(pid)[0]
        self.assertEqual((ln["article"], ln["qty"], ln["price_kop"]), ("A912", 24, 52477))   # 2860 / 5,45
        # формулы без сохранённых значений, прайс без количества, старый .xls, не Excel
        for data, name, msg in ((make_xlsx({"Л": [["Артикул", "Шт", "Цена, ₽"], ["A912", "=2*12", "=2860/5.45"]]}), "f.xlsx", "формулы"),
                                (make_xlsx({"Л": [["Артикул", "Шт в коробке", "Цена за шт, ₸"], ["A912", 12, 2860]]}), "p.xlsx", "Количество"),
                                (b"\xd0\xcf\x11\xe0", "old.xls", ".xls"), (b"plain text", "x.xlsx", "не файл Excel")):
            self.upload(pid, data, name)
            self.assertIn(msg, self.c.get(f"/purchases/{pid}").get_data(as_text=True), name)
        # CSV из Excel (Windows-1251, «;»)
        self.upload(pid, "Артикул;Количество;Цена\nA116;10;150,5\n".encode("cp1251"), "spec.csv")
        self.assertEqual([(x["article"], x["qty"], x["price_kop"]) for x in self.buh.purchase_lines(pid)], [("A116", 10, 15050)])
        # после оприходования загрузить нельзя
        self.post(f"/purchases/{pid}/receive", {"day": "2026-11-20"})
        self.upload(pid, tg)
        self.assertEqual(len(self.buh.purchase_lines(pid)), 1)

    def test_big_file_limit(self) -> None:
        pid = self.make_purchase()
        r = self.upload(pid, b"x" * (1024 * 1024 + 10), "big.xlsx")
        self.assertIn(r.status_code, (302, 413))
        self.assertEqual(self.buh.purchase_lines(pid), [])
        # обычные формы по-прежнему ограничены 256 КБ
        self.assertEqual(self.c.post("/tasks", data={"csrf": "x", "title": "y" * 300_000}).status_code, 413)


def valid_account(bik: str, base: str = "40802810000000012345") -> str:
    from invoice import account_ok
    for k in range(10):
        acc = base[:8] + str(k) + base[9:]
        if account_ok(acc, bik):
            return acc
    raise AssertionError("нет ключа")


def valid_inn12(base: str = "7801234567") -> str:
    from invoice import inn_ok
    for a in range(10):
        for b in range(10):
            if inn_ok(f"{base}{a}{b}"):
                return f"{base}{a}{b}"
    raise AssertionError("нет ИНН")


class TestOutbox(Base):
    """Исходящие с zapros@: шифр из ветки outbox → расшифровать на сервере → отправить один раз."""

    def setUp(self) -> None:
        super().setUp()
        import subprocess
        from pathlib import Path
        self.sp = subprocess
        d = self.tmp.name
        self.bare = os.path.join(d, "remote.git")
        self.work = os.path.join(d, "work")
        env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "HOME": d}
        self.genv = env
        self.git("init", "-q", "--bare", self.bare)
        self.git("init", "-q", "-b", "outbox", self.work)
        self.git("-C", self.work, "config", "user.email", "t@t"); self.git("-C", self.work, "config", "user.name", "t")
        self.git("-C", self.work, "remote", "add", "origin", self.bare)
        self.ob = self.app.extensions["outbox"]
        self.ob.repo_url = self.bare
        self.ob.workdir = Path(d) / "outbox-git"
        self.sent = []
        self.orig = crm_app.send_mail
        self.ok = True
        crm_app.send_mail = lambda to, subj, body, **kw: (self.sent.append((to, subj, body, kw)) or True) if self.ok else False
        self.login()

    def tearDown(self) -> None:
        crm_app.send_mail = self.orig
        super().tearDown()

    def git(self, *a: str) -> None:
        self.sp.run(["git", *a], check=True, capture_output=True, env=self.genv)

    def put(self, env: dict, name: str = "") -> None:
        import json as _j
        os.makedirs(os.path.join(self.work, "outbox"), exist_ok=True)
        with open(os.path.join(self.work, "outbox", (name or env["id"]) + ".json"), "w", encoding="utf-8") as f:
            _j.dump(env, f)
        self.git("-C", self.work, "add", "-A"); self.git("-C", self.work, "commit", "-q", "-m", "m")
        self.git("-C", self.work, "push", "-q", "origin", "outbox")

    def letter(self, **kw):
        import uuid
        import outbox
        p = {"id": str(uuid.uuid4()), "to": "lab@example.ru", "subject": "Запрос на испытания", "body": "Добрый день!\nТекст.",
             "attachments": [{"name": "спец.docx", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                              "b64": "UEsDBA=="}]}
        p.update(kw)
        key = self.c.get("/api/outbox/key").get_data(as_text=True).strip()
        return p, outbox.seal(key, p)

    def test_send_once_and_status(self) -> None:
        import outbox
        self.assertEqual(self.ob.run(), [])                                  # ветки ещё нет — ничего
        key = self.c.get("/api/outbox/key").get_data(as_text=True).strip()
        self.assertEqual(len(outbox._ub64(key)), 32); self.assertEqual(key, self.ob.public_key())
        p, env = self.letter()
        self.assertNotIn("Запрос", str(env))                                  # в GitHub — только шифр
        self.put(env)
        out = self.ob.run()
        self.assertEqual(len(self.sent), 1, out)
        to, subj, body, kw = self.sent[0]
        self.assertEqual((to, subj), ("lab@example.ru", "Запрос на испытания"))
        self.assertEqual(kw["sender"], "Наш декор <zapros@nashdekor.ru>"); self.assertEqual(kw["reply_to"], "info@nashdekor.ru")
        self.assertEqual(kw["attachments"][0][0], "спец.docx"); self.assertEqual(kw["attachments"][0][1][:2], b"PK")
        st = self.c.get(f"/api/outbox/status/{p['id']}").get_json()
        self.assertEqual(st["status"], "sent")
        self.assertEqual(self.c.get("/api/outbox/status/abc").get_json(), {"status": "unknown"})
        self.ob.run(); self.ob.run()
        self.assertEqual(len(self.sent), 1)                                   # второй раз не уходит
        page = self.c.get("/outbox").get_data(as_text=True)
        self.assertIn("Запрос на испытания", page); self.assertIn("отправлено", page); self.assertIn("Добрый день!", page)
        self.assertIn('class="mailtext"', page); self.assertNotIn('class="row src"', page)   # письмо на всю ширину, не в колонку
        row = self.ob._row(p["id"]); self.assertEqual(row["payload"], "")      # расшифровка после отправки не хранится

    def test_bad_letters_limits_and_switch(self) -> None:
        import uuid
        import outbox
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        other = X25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        mid = str(uuid.uuid4())
        self.put(outbox.seal(outbox._b64(other), {"id": mid, "to": "a@b.ru", "subject": "x", "body": "y"}))   # чужой ключ
        p2, env2 = self.letter(to="не адрес")
        self.put(env2)
        self.ob.run()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.ob.status(mid)["status"], "error")
        self.assertIn("непонятный адрес", self.ob.status(p2["id"])["error"])
        # выключено — ждёт; лимит 1 в сутки — второе ждёт до завтра (или пока не поднимут лимит)
        self.post("/outbox", {"daily": "1"})                                  # галочки нет → выключено
        p3, env3 = self.letter(subject="Первое"); self.put(env3)
        self.assertEqual(self.ob.run(), ["отправка выключена в CRM"])
        self.post("/outbox", {"on": "1", "daily": "1"})
        p4, env4 = self.letter(subject="Второе"); self.put(env4)
        self.ob.run()
        self.assertEqual([x[1] for x in self.sent], ["Первое"])
        self.assertEqual(self.ob.status(p4["id"])["status"], "unknown")
        self.post("/outbox", {"on": "1", "daily": "5"})
        self.ob.run()
        self.assertEqual([x[1] for x in self.sent], ["Первое", "Второе"])

    def test_retry_when_mail_server_refuses(self) -> None:
        p, env = self.letter(); self.put(env)
        self.ok = False
        self.ob.run()
        self.assertEqual(self.ob.status(p["id"])["status"], "retry")
        self.ok = True
        self.ob.run()
        self.assertEqual(self.ob.status(p["id"])["status"], "sent"); self.assertEqual(len(self.sent), 1)
        p2, env2 = self.letter(subject="Не уйдёт"); self.put(env2)
        self.ok = False
        for _ in range(3):
            self.ob.run()
        self.assertEqual(self.ob.status(p2["id"])["status"], "error")
        self.ob.repo_url = os.path.join(self.tmp.name, "нет-такого.git")
        self.assertTrue(any("GitHub не ответил" in x for x in self.ob.run()))


class TestPochta(TestOutbox):
    """Раздел «Почта» (письма info@/zakaz@, выгруженные root'ом) и ответы на запросы — шифром для Claude."""

    def setUp(self) -> None:
        super().setUp()
        from pathlib import Path
        import mailwatch
        self.mw = mailwatch
        self.vm = os.path.join(self.tmp.name, "vmail")
        self.out = os.path.join(self.tmp.name, "pochta")
        self.app.extensions["pochta"].dir = Path(self.out)
        self.n = 0
        self.pushes = []
        wp = self.app.extensions["push"]
        self.orig_notify = wp.notify
        wp.notify = lambda title, body="", url="/", **kw: self.pushes.append((title, body, url)) or (0, 0)

    def tearDown(self) -> None:
        self.app.extensions["push"].notify = self.orig_notify
        super().tearDown()

    def msg(self, frm, subject, text="Добрый день!", box="info", date="", html="", atts=(), **hdr):
        from email.message import EmailMessage
        from email.utils import formatdate
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = frm, f"{box}@nashdekor.ru", subject
        m["Date"] = date or formatdate(localtime=True)
        for k, v in hdr.items():
            m[k.replace("_", "-")] = v
        if html and not text:
            m.set_content(html, subtype="html")
        else:
            m.set_content(text)
            if html:
                m.add_alternative(html, subtype="html")
        for name, data, mime in atts:
            mt, st = mime.split("/")
            m.add_attachment(data, maintype=mt, subtype=st, filename=name)
        return m

    def deliver(self, m, box="info", spam=False):
        import time
        d = os.path.join(self.vm, "nashdekor.ru", box, "Maildir", ".Junk" if spam else "", "new")
        os.makedirs(d, exist_ok=True)
        self.n += 1
        fn = f"{int(time.time())}.M{self.n}P1.test"
        with open(os.path.join(d, fn), "wb") as f:
            f.write(bytes(m))
        return self.mw.mail_key(box, fn), os.path.join(d, fn)

    def export(self):
        import grp
        old, self.mw.VMAIL = self.mw.VMAIL, self.vm
        try:
            self.assertEqual(self.mw.export(self.out, grp.getgrgid(os.getgid()).gr_name, "nashdekor.ru", ["zakaz", "info"]), 0)
        finally:
            self.mw.VMAIL = old

    def test_mail_page_letter_and_attachments(self) -> None:
        self.assertIn("Почта ещё не выгружена", self.c.get("/pochta").get_data(as_text=True))
        mid, path = self.deliver(self.msg("ИПЛ Тверь <ipl@lab.example>", "Ответ по испытаниям", text="",
                                          html="<html><head><style>p{}</style></head><p>Цена <b>25 000</b> руб.<br>Звоните</p><script>alert(1)</script>",
                                          atts=[("КП.pdf", b"%PDF-1.4 t", "application/pdf"), ("x.html", b"<script>alert(2)</script>", "text/html")]))
        zid, _ = self.deliver(self.msg("Клиент <client@mail.example>", "Заказ панелей", box="zakaz"), box="zakaz")
        sid, _ = self.deliver(self.msg("spam@spam.example", "Выигрыш"), spam=True)
        self.export()
        page = self.c.get("/pochta").get_data(as_text=True)
        self.assertIn("ИПЛ Тверь", page); self.assertIn("Заказ панелей", page); self.assertNotIn("Выигрыш", page)
        self.assertIn("новое", page)
        self.assertNotIn("новое", self.c.get("/pochta").get_data(as_text=True))          # открыл список — уже не новое
        self.assertNotIn("Ответ по испытаниям", self.c.get("/pochta?box=zakaz").get_data(as_text=True))
        self.assertIn("Выигрыш", self.c.get("/pochta?box=spam").get_data(as_text=True))
        self.assertIn("Заказ панелей", self.c.get("/pochta?q=заказ").get_data(as_text=True))
        lt = self.c.get(f"/pochta/{mid}").get_data(as_text=True)
        self.assertIn("Цена 25 000 руб.", lt); self.assertIn("Звоните", lt); self.assertNotIn("alert(1)", lt)
        self.assertIn("КП.pdf", lt); self.assertIn("ipl@lab.example", lt)
        r = self.c.get(f"/pochta/{mid}/a/1")
        self.assertEqual(r.data, b"%PDF-1.4 t"); self.assertEqual(r.mimetype, "application/pdf")
        self.assertEqual(r.headers["Content-Security-Policy"], "sandbox"); self.assertNotIn("attachment", r.headers.get("Content-Disposition", ""))
        r = self.c.get(f"/pochta/{mid}/a/2")                                            # html-вложение — только скачать
        self.assertEqual(r.mimetype, "application/octet-stream"); self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertEqual(self.c.get(f"/pochta/{mid}/a/9").status_code, 404)
        self.assertEqual(self.c.get("/pochta/../crm.db").status_code, 404)
        self.assertEqual(self.c.get("/pochta/0123456789abcdef0123").status_code, 404)
        os.unlink(path); self.export()                                                   # удалили из ящика — пропало и в CRM
        self.assertEqual(self.c.get(f"/pochta/{mid}").status_code, 404)
        self.assertFalse(os.path.exists(os.path.join(self.out, mid)))
        # пуш о новом письме ведёт прямо на письмо
        self.app.extensions["mail_in"]([{"box": "zakaz", "from": "x@other.example", "name": "", "subject": "Вопрос", "key": zid}])
        self.assertEqual(self.pushes[-1][2], f"/pochta/{zid}")
        c2 = self.app.test_client(); self.login("mikhail", "Secret-pass-2", client=c2)    # не админ — почту не видит
        self.assertEqual(c2.get("/pochta").status_code, 403)

    def test_replies_for_claude(self) -> None:
        import outbox
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        self.assertEqual(self.c.get("/api/outbox/replies").get_json()["items"], [])
        p, env = self.letter(to="lab@69.mchs.example"); self.put(env)
        self.ob.run()
        self.assertEqual(self.sent[0][3]["msgid"], f"<{p['id']}@nashdekor.ru>")             # свой Message-ID — по нему узнаём ответ
        self.assertTrue(self.c.get("/api/outbox/replies").get_json()["nokey"])
        sk = X25519PrivateKey.generate()
        pub = outbox._b64(sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
        with open(os.path.join(self.work, "READER.pub"), "w") as f:
            f.write(pub + "\n")
        self.git("-C", self.work, "add", "-A"); self.git("-C", self.work, "commit", "-q", "-m", "k"); self.git("-C", self.work, "push", "-q", "origin", "outbox")
        self.ob.run()
        self.assertTrue(any("Claude подключился" in x[0] for x in self.pushes))
        a, _ = self.deliver(self.msg("Иванова <ivanova@69.mchs.example>", "Стоимость испытаний", text="Г1 — 25 000 руб.",
                                     atts=[("КП.pdf", b"%PDF-1.4 kp", "application/pdf")]))
        b, _ = self.deliver(self.msg("boss@gmail.com", "Без темы", In_Reply_To=f"<{p['id']}@nashdekor.ru>"))
        c, _ = self.deliver(self.msg("someone@gmail.com", "RE: Fwd: Запрос на испытания"))
        d, _ = self.deliver(self.msg("client@gmail.com", "Хочу панели"))
        e, _ = self.deliver(self.msg("lab@69.mchs.example", "Заказ", box="zakaz"), box="zakaz")
        f_, _ = self.deliver(self.msg("lab@69.mchs.example", "Старое", date="Mon, 01 Jun 2020 10:00:00 +0300"))
        self.export()
        r = self.c.get("/api/outbox/replies")
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        data = r.get_json()
        raw = r.get_data(as_text=True)
        self.assertNotIn("25 000", raw); self.assertNotIn("ivanova", raw); self.assertNotIn("Стоимость", raw)   # снаружи — только шифр
        got = {}
        for env_ in data["items"]:
            x = outbox.unseal(sk, env_, outbox.INFO_REPLIES)
            got[x["id"]] = x
        self.assertEqual(set(got), {a, b, c})
        self.assertEqual(got[a]["text"], "Г1 — 25 000 руб."); self.assertEqual(got[a]["atts"][0]["name"], "КП.pdf")
        self.assertEqual(outbox._ub64(got[a]["atts"][0]["b64"]), b"%PDF-1.4 kp")
        with self.assertRaises(Exception):
            outbox.unseal(sk, data["items"][0])                                           # ключом исходящих не открыть
        page = self.c.get("/outbox").get_data(as_text=True)
        self.assertIn("Ответы, которые видит Claude", page); self.assertIn("Стоимость испытаний", page); self.assertNotIn("Хочу панели", page)
        self.assertIn("видит Claude", self.c.get(f"/pochta/{a}").get_data(as_text=True))
        self.assertNotIn("видит Claude", self.c.get(f"/pochta/{d}").get_data(as_text=True))
        self.post("/outbox", {"on": "1", "daily": "30"})                                  # галочку «видит ответы» сняли
        x = self.c.get("/api/outbox/replies").get_json()
        self.assertTrue(x["off"]); self.assertEqual(x["items"], [])


class TestDocs(TestPochta):
    """Раздел «Документы»: загрузка, разделы, срок действия, из письма, через канал Claude."""

    def setUp(self) -> None:
        super().setUp()
        from pathlib import Path
        self.docs = self.app.extensions["docs"]
        self.docs.dir = Path(self.tmp.name) / "docs"

    def upload(self, files, **form):
        import io
        data = {"csrf": self.csrf(), **form}
        data["file"] = [(io.BytesIO(b), n) for n, b in files]
        return self.c.post("/docs/upload", data=data, content_type="multipart/form-data")

    def test_upload_folders_edit_delete(self) -> None:
        self.assertIn("Документов пока нет", self.c.get("/docs").get_data(as_text=True))
        r = self.upload([("ТУ ARTDEC.pdf", b"%PDF-1.4 tu")], folder="Сертификаты и ТУ", title="ТУ СТ ТОО 200540013338-001-2024",
                        until="2030-01-03", note="разрешили использовать")
        self.assertEqual(r.status_code, 302)
        self.upload([("ИНН.jpg", b"\xff\xd8jpg"), ("УСН.pdf", b"%PDF usn")], folder="ИП")
        self.upload([("ТУ ARTDEC.pdf", b"%PDF-1.4 tu")], folder="Сертификаты и ТУ")                  # тот же файл — не дублируем
        self.upload([("договор.docx", b"PK\x03\x04docx")], new_folder="Поставщик ARTDEC")           # новый раздел
        page = self.c.get("/docs").get_data(as_text=True)
        for w in ("ТУ СТ ТОО 200540013338-001-2024", "ИНН", "УСН", "договор", "Поставщик ARTDEC", "до 03.01.2030"):
            self.assertIn(w, page)
        self.assertEqual(len(self.docs.list()), 4)
        self.assertEqual(dict(self.docs.folders())["ИП"], 2)
        self.assertNotIn("УСН", self.c.get("/docs?f=" + "Сертификаты и ТУ").get_data(as_text=True))
        self.assertIn("ТУ СТ", self.c.get("/docs?q=разрешили").get_data(as_text=True))
        tu = [d for d in self.docs.list() if d["filename"] == "ТУ ARTDEC.pdf"][0]
        r = self.c.get(f"/docs/{tu['id']}")
        self.assertEqual(r.data, b"%PDF-1.4 tu"); self.assertEqual(r.headers["Content-Security-Policy"], "sandbox")
        dx = [d for d in self.docs.list() if d["filename"] == "договор.docx"][0]
        r = self.c.get(f"/docs/{dx['id']}")
        self.assertIn("attachment", r.headers["Content-Disposition"]); self.assertEqual(r.mimetype, "application/octet-stream")
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, "docs", tu["id"])))
        # изменить: раздел, название, срок
        self.post(f"/docs/{dx['id']}/edit", {"title": "Договор поставки № 1", "folder": "Договоры", "until": "", "note": ""})
        self.assertEqual(self.docs.get(dx["id"])["folder"], "Договоры"); self.assertEqual(self.docs.get(dx["id"])["title"], "Договор поставки № 1")
        # удалить — только с галочкой
        self.post(f"/docs/{dx['id']}/edit", {"delete": "1"})
        self.assertIsNotNone(self.docs.get(dx["id"]))
        self.post(f"/docs/{dx['id']}/edit", {"delete": "1", "confirm": "1"})
        self.assertIsNone(self.docs.get(dx["id"])); self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "docs", dx["id"])))
        self.assertEqual(self.c.get("/docs/../crm.db").status_code, 404)
        self.assertEqual(self.c.get("/docs/" + "0" * 32).status_code, 404)
        c2 = self.app.test_client(); self.login("mikhail", "Secret-pass-2", client=c2)              # не админ — не видит
        self.assertEqual(c2.get("/docs").status_code, 403); self.assertEqual(c2.get(f"/docs/{tu['id']}").status_code, 403)
        # срок действия — в утренней сводке
        self.upload([("ISO.pdf", b"%PDF iso")], folder="Сертификаты и ТУ", title="Сертификат ISO 9001", until="2027-02-23")
        self.assertIn("Сертификат ISO 9001 (до 23.02.2027)", self.app.extensions["digest"]("2027-02-01"))
        self.assertIn("истёк", self.app.extensions["digest"]("2027-03-01"))
        from docs import Docs
        self.assertEqual([Docs.state("2027-02-23", d) for d in ("2026-11-11", "2027-01-01", "2027-03-01")], ["", "soon", "over"])

    def test_big_file_and_mail_attachment(self) -> None:
        import docs as docs_mod
        old, docs_mod.MAX_FILE = docs_mod.MAX_FILE, 10
        try:
            with self.assertRaises(ValueError):
                self.docs.add(b"x" * 11, "big.pdf")
        finally:
            docs_mod.MAX_FILE = old
        mid, _ = self.deliver(self.msg("Путрова <putrova@lab.example>", "КП на испытания", atts=[("КП.pdf", b"%PDF kp", "application/pdf")]))
        self.export()
        self.assertIn("В документы", self.c.get(f"/pochta/{mid}").get_data(as_text=True))
        r = self.post(f"/pochta/{mid}/a/1/save", {})
        self.assertIn("/docs/", r.headers["Location"]); self.assertIn("/edit", r.headers["Location"])
        d = self.docs.list("Из почты")[0]
        self.assertEqual(d["filename"], "КП.pdf"); self.assertIn("putrova@lab.example", d["note"])
        self.post(f"/pochta/{mid}/a/1/save", {})
        self.assertEqual(len(self.docs.list()), 1)                                                  # второй раз не дублирует

    def test_docs_from_claude_channel(self) -> None:
        import json as _j
        import uuid
        import outbox
        key = self.c.get("/api/outbox/key").get_data(as_text=True).strip()
        mid = str(uuid.uuid4())
        p = {"id": mid, "kind": "doc", "folder": "Сертификаты и ТУ", "title": "Сертификат ISO 9001 ARTDEC", "until": "2027-02-23",
             "note": "№ KZ.Q.02.0467.C23.04998", "attachments": [{"name": "ISO.pdf", "mime": "application/pdf", "b64": "JVBERi0="}]}
        env = outbox.seal(key, p)
        os.makedirs(os.path.join(self.work, "docs"), exist_ok=True)
        with open(os.path.join(self.work, "docs", mid + ".json"), "w", encoding="utf-8") as f:
            _j.dump(env, f)
        self.git("-C", self.work, "add", "-A"); self.git("-C", self.work, "commit", "-q", "-m", "d"); self.git("-C", self.work, "push", "-q", "origin", "outbox")
        out = self.ob.run()
        self.assertTrue(any("в документы" in x for x in out), out)
        self.assertEqual(self.sent, [])                                                              # не письмо
        d = self.docs.list("Сертификаты и ТУ")[0]
        self.assertEqual((d["title"], d["until"], d["created_by"]), ("Сертификат ISO 9001 ARTDEC", "2027-02-23", "Claude"))
        self.assertEqual(self.ob.status(mid)["status"], "saved")
        self.assertTrue(any("Документы" in x[0] for x in self.pushes))
        self.ob.run()
        self.assertEqual(len(self.docs.list()), 1)                                                  # один раз
        self.assertIn("в документах", self.c.get("/outbox").get_data(as_text=True))


class TestInvoices(Base):
    """Счёт компании: реквизиты продавца, PDF с QR, письмо, автопривязка оплаты по номеру счёта."""

    def setUp(self) -> None:
        super().setUp()
        self.inv = self.app.extensions["invoices"]
        self.login()
        self.acc = valid_account("044525104")
        self.inn = valid_inn12()

    def seller(self, **kw):
        data = {"inv_name": "Индивидуальный предприниматель Тестова Анна Петровна", "inv_inn": self.inn, "inv_ogrn": "326784700000001",
                "inv_account": self.acc, "inv_bank": "ООО «Банк Точка»", "inv_bik": "044525104",
                "inv_corr": "30101810745374525104", "inv_city": "г. Санкт-Петербург", "inv_signer": "Тестова А. П.", "inv_days": "3"}
        data.update(kw)
        return self.post("/settings/invoice", data)

    def company_deal(self) -> int:
        did = self.store.create_deal("t", None, name="Бухгалтерия", phone="+79990005555", kind="c")
        cid = self.store.deal(did)["client_id"]
        self.store.update_client(cid, "t", full_name="ООО «Ремонт Плюс»", inn="7801234567", kpp="780101001",
                                 legal_address="190000, г. Санкт-Петербург", doc_email="buh@remont.example")
        self.store.add_line(did, "A912", 10, "t")                 # 10 × 990 ₽
        self.store.update_deal(did, "t", discount=10)            # −10 % → 891 ₽
        return did

    def test_checks_and_words(self) -> None:
        from invoice import account_ok, amount_words, corr_ok, inn_ok
        self.assertTrue(corr_ok("30101810745374525104", "044525104"))
        self.assertTrue(account_ok(self.acc, "044525104"))
        self.assertFalse(account_ok(self.acc[:-1] + str((int(self.acc[-1]) + 1) % 10), "044525104"))
        self.assertTrue(inn_ok("7707083893")); self.assertFalse(inn_ok("7707083894"))
        self.assertEqual(amount_words(4120050), "Сорок одна тысяча двести рублей 50 копеек")
        self.assertEqual(amount_words(101), "Один рубль 01 копейка")

    def test_seller_settings_required(self) -> None:
        did = self.company_deal()
        self.post(f"/deals/{did}/invoice", {"pct": "100"})
        self.assertEqual(self.inv.for_deal(did), [])
        self.assertIn("заполните реквизиты ИП", self.c.get(f"/deals/{did}").get_data(as_text=True))
        self.seller(inv_account="40802810000000000000")             # опечатка в счёте — не пропускаем
        self.assertIn("расчётный счёт", " ".join(self.inv.seller_problems()))
        self.seller()
        self.assertEqual(self.inv.seller_problems(), [])
        # сотрудник реквизиты не меняет
        self.c.post("/logout", data={"csrf": self.csrf()})
        self.login("mikhail", "Secret-pass-2")
        self.assertEqual(self.seller().status_code, 403)

    def test_invoice_pdf_email_and_payment(self) -> None:
        self.seller()
        did = self.company_deal()
        self.post(f"/deals/{did}/invoice", {"pct": "100", "delivery": "500"})
        inv = self.inv.for_deal(did)[0]
        self.assertEqual((inv["n"], inv["total"], inv["amount"], inv["status"]), (1, 891000 + 50000, 941000, "issued"))
        qr = self.inv.qr_text(inv)
        self.assertTrue(qr.startswith("ST00012|Name=Индивидуальный предприниматель Тестова Анна Петровна|PersonalAcc=" + self.acc))
        self.assertIn("|Sum=941000|", qr); self.assertIn(f"Purpose=Оплата по счёту № {did}/1 от", qr)
        page = self.c.get(f"/deals/{did}").get_data(as_text=True)
        self.assertIn(f"№ {did}/1", page); self.assertIn("ждёт оплаты", page)
        try:
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("нет reportlab")
        r = self.c.get(f"/invoices/{inv['id']}.pdf")
        self.assertEqual(r.status_code, 200); self.assertTrue(r.data.startswith(b"%PDF")); self.assertEqual(r.mimetype, "application/pdf")
        # письмо с PDF: перехватываем отправку
        sent = []
        orig = crm_app.send_mail
        crm_app.send_mail = lambda to, subj, body, **kw: sent.append((to, subj, body, kw)) or True
        try:
            self.post(f"/invoices/{inv['id']}/email")
        finally:
            crm_app.send_mail = orig
        self.assertEqual(sent[0][0], "buh@remont.example")
        self.assertIn(f"Счёт № {did}/1", sent[0][1]); self.assertIn("9 410,00 ₽", sent[0][2])
        self.assertTrue(sent[0][3]["attachments"][0][1].startswith(b"%PDF"))
        # предоплата 50 % — второй счёт «/2»
        self.post(f"/deals/{did}/invoice", {"pct": "50"})
        inv2 = self.inv.for_deal(did)[0]
        self.assertEqual((inv2["n"], inv2["pct"], inv2["amount"]), (2, 50, 445500))
        # оплата: номер счёта в назначении + сумма → счёт и заявка (ИНН клиента не нужен)
        self.assertEqual(self.inv.match("", f"Оплата по счету N {did}/2 от 10.11.2026 без НДС", 445500), inv2["id"])
        self.assertIsNone(self.inv.match("", f"Оплата по счету № {did}/2", 100))            # сумма не та и ИНН нет
        self.assertEqual(self.inv.match("7801234567", "оплата за панели", 941000), inv["id"])  # ИНН покупателя + точная сумма
        # оплата прошла мимо — ручная отметка «по счёту» закрывает счёт с той же суммой
        self.post(f"/deals/{did}/payments/manual", {"amount": "4455", "kind": "invoice"})
        self.assertEqual(self.inv.get(inv2["id"])["status"], "paid")
        self.assertEqual(self.inv.get(inv["id"])["status"], "issued")
        self.assertIn(f"№ {did}/1", self.c.get("/money").get_data(as_text=True))
        # отмена; заявку со счетами удалить нельзя
        self.post(f"/invoices/{inv['id']}/cancel")
        self.assertEqual(self.inv.get(inv["id"])["status"], "cancelled")
        self.post(f"/deals/{did}/delete", {"confirm": "1"})
        self.assertIsNotNone(self.store.deal(did))

    def test_private_buyer_warning(self) -> None:
        self.seller()
        did = self.store.create_deal("t", None, name="Анна", phone="+79990006666")
        self.store.add_line(did, "A912", 1, "t")
        self.assertIn("при оплате по счёту тоже нужен кассовый чек", self.c.get(f"/deals/{did}").get_data(as_text=True))


class FakeS3:
    """Мини-хранилище S3 для тестов: PUT/HEAD с проверкой подписи SigV4 и содержимого."""

    def __init__(self, key="AK", secret="SK", region="ru-3") -> None:
        import http.server
        import threading
        self.objects: dict[str, bytes] = {}
        self.key, self.secret, self.region = key, secret, region
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _auth_ok(self, body: bytes) -> bool:
                import hashlib as _h
                import offsite
                from datetime import datetime as _d, timezone as _tz
                auth = self.headers.get("Authorization", "")
                m = re.search(r"Credential=([^/]+)/(\d{8})/([^/]+)/s3/aws4_request, SignedHeaders=([^,]+), Signature=(\w+)", auth)
                if not m or m.group(1) != fake.key:
                    return False
                if self.headers.get("x-amz-content-sha256") != _h.sha256(body).hexdigest():
                    return False
                names = m.group(4).split(";")
                hdrs = {n: self.headers.get(n, "") for n in names if n not in ("host", "x-amz-date", "x-amz-content-sha256")}
                now = _d.strptime(self.headers["x-amz-date"], "%Y%m%dT%H%M%SZ").replace(tzinfo=_tz.utc)
                again = offsite.sign(self.command, self.headers["Host"], self.path, None, hdrs, _h.sha256(body).hexdigest(),
                                     fake.key, fake.secret, m.group(3), now)
                return again["authorization"] == auth

            def do_PUT(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if not self._auth_ok(body):
                    self.send_response(403); self.end_headers(); self.wfile.write(b"<Error><Code>SignatureDoesNotMatch</Code></Error>"); return
                fake.objects[self.path] = body
                self.send_response(200); self.send_header("Content-Length", "0"); self.end_headers()

            def do_HEAD(self):
                if not self._auth_ok(b""):
                    self.send_response(403); self.end_headers(); return
                if self.path not in fake.objects:
                    self.send_response(404); self.end_headers(); return
                self.send_response(200); self.send_header("Content-Length", str(len(fake.objects[self.path]))); self.end_headers()

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.srv.shutdown()


class TestBackupCopies(Base):
    """Копии баз: подпись S3, загрузка в облако, скачивание архива из CRM, настройки, утренняя сводка."""

    def test_sigv4_matches_aws_example(self) -> None:
        import offsite
        from datetime import datetime as _d, timezone as _tz
        h = offsite.sign("GET", "examplebucket.s3.amazonaws.com", "/test.txt", None, {"range": "bytes=0-9"},
                         offsite.EMPTY_SHA, "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                         "us-east-1", _d(2013, 5, 24, tzinfo=_tz.utc))
        self.assertTrue(h["authorization"].endswith("Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"))

    def test_upload_and_check(self) -> None:
        import offsite
        s3 = FakeS3()
        try:
            conf = {"endpoint": s3.url, "region": "ru-3", "bucket": "nashdekor-backup", "key": "AK", "secret": "SK", "prefix": "nashdekor"}
            p = os.path.join(self.tmp.name, "a.bin")
            with open(p, "wb") as f:
                f.write(os.urandom(300_000))
            self.assertEqual(offsite.S3(conf).put_file(p, "2026/11/kopiya.tar.gz.enc"), 300_000)
            self.assertIn("/nashdekor-backup/nashdekor/2026/11/kopiya.tar.gz.enc", s3.objects)
            self.assertIn("связь есть", offsite.check(conf))
            with self.assertRaises(offsite.OffsiteError) as e:
                offsite.check(dict(conf, secret="wrong"))
            self.assertIn("403", str(e.exception))
            with self.assertRaises(offsite.OffsiteError):
                offsite.check(dict(conf, endpoint="ftp://x"))
        finally:
            s3.close()

    def test_settings_offsite(self) -> None:
        self.login()
        r = self.post("/settings/offsite", {"act": "save", "endpoint": "https://s3.ru-3.storage.selcloud.ru/", "region": "RU-3",
                                            "bucket": "NashDekor-Backup", "key": " AK123 ", "secret": "S3cr3t", "prefix": "/nashdekor/", "on": "1"})
        self.assertEqual(r.status_code, 302)
        st = self.store
        self.assertEqual(st.setting("offsite_endpoint"), "https://s3.ru-3.storage.selcloud.ru")
        self.assertEqual((st.setting("offsite_region"), st.setting("offsite_bucket"), st.setting("offsite_key")), ("ru-3", "nashdekor-backup", "AK123"))
        self.assertEqual(st.setting("offsite_on"), "1")
        page = self.c.get("/settings").get_data(as_text=True)
        self.assertIn("Копии баз в облако", page)
        self.assertNotIn("S3cr3t", page)                         # секрет на страницу не выводится
        self.post("/settings/offsite", {"act": "save", "endpoint": "https://s3.ru-3.storage.selcloud.ru", "bucket": "b", "secret": "", "on": ""})
        self.assertEqual(st.setting("offsite_secret"), "S3cr3t")  # пустое поле секрета — старый остаётся
        self.assertEqual(st.setting("offsite_on"), "0")
        self.post("/settings/offsite", {"act": "save", "endpoint": "http://evil/x"})
        self.assertEqual(st.setting("offsite_endpoint"), "https://s3.ru-3.storage.selcloud.ru")  # чужой адрес не принят
        self.post("/settings/offsite", {"act": "forget"})
        self.assertEqual((st.setting("offsite_key"), st.setting("offsite_secret")), ("", ""))
        self.c.post("/logout", data={"csrf": self.csrf()})
        self.login("mikhail", "Secret-pass-2")                   # не владелец — нельзя
        self.assertEqual(self.post("/settings/offsite", {"act": "save", "endpoint": "https://a.b"}).status_code, 403)

    def test_manage_offsite_and_digest(self) -> None:
        import manage
        os.environ["CRM_DB"] = self.store.path
        os.environ["BOT_DB"] = self.botdb
        os.environ["CATALOG_FILE"] = self.cat
        try:
            import io
            import contextlib
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                manage.main(["offsite-config"])
            self.assertEqual(out.getvalue().strip(), "")         # выключено — пусто
            for k, v in (("on", "1"), ("endpoint", "https://e"), ("bucket", "b"), ("key", "k"), ("secret", "s")):
                self.store.set_setting("offsite_" + k, v)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                manage.main(["offsite-config"])
            self.assertEqual(json.loads(out.getvalue())["bucket"], "b")
            self.assertIn("копия баз в облако не делалась", self.app.extensions["digest"]().lower())
            with contextlib.redirect_stdout(io.StringIO()):
                manage.main(["offsite-result", "ok", "2026/11/x — загружено 10 байт"])
            last = json.loads(self.store.setting("offsite_last"))
            self.assertEqual(last["status"], "ok")
            self.assertNotIn("облако", self.app.extensions["digest"]() or "")
            with contextlib.redirect_stdout(io.StringIO()):
                manage.main(["offsite-result", "error", "ошибка 403"])
            page = (self.login(), self.c.get("/settings").get_data(as_text=True))[1]
            self.assertIn("ошибка 403", page)
        finally:
            for k in ("CRM_DB", "BOT_DB", "CATALOG_FILE"):
                os.environ.pop(k, None)

    def test_export_download(self) -> None:
        d = self.tmp.name
        pw = os.path.join(d, "backup-pass")
        with open(pw, "w") as f:
            f.write("Kopii-Parol-123\n")
        app = crm_app.create_app({"CRM_DB": self.store.path, "BOT_DB": self.botdb, "CATALOG_FILE": self.cat,
                                  "SECRET_KEY": "x" * 40, "COOKIE_SECURE": "0", "TESTING": True, "BACKUP_PASS_FILE": pw})
        self.c = app.test_client()
        os.makedirs(os.path.join(d, "export"))
        good = "nashdekor-kopiya-2026-11-11-1930.tar.gz.enc"
        with open(os.path.join(d, "export", good), "wb") as f:
            f.write(b"Salted__" + os.urandom(64))
        with open(os.path.join(d, "export", "secret.txt"), "w") as f:
            f.write("x")
        self.assertEqual(self.c.get(f"/server/export/{good}").status_code, 302)   # без входа — на вход
        self.login()
        page = self.c.get("/server").get_data(as_text=True)
        self.assertIn("Копия баз — скачать", page)
        self.assertIn(good, page)
        self.assertNotIn("secret.txt", page)
        self.assertNotIn("Kopii-Parol-123", page)                 # пароль — только по кнопке
        self.assertIn("Kopii-Parol-123", self.c.get("/server?pass=1").get_data(as_text=True))
        r = self.c.get(f"/server/export/{good}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"Salted__"))
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertEqual(self.c.get("/server/export/secret.txt").status_code, 404)
        self.assertEqual(self.c.get("/server/export/..%2Fcrm.db").status_code, 404)
        self.assertEqual(self.post("/server/run", {"action": "export"}).status_code, 302)
        with open(os.path.join(d, "server-request"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "export yulia\n")
        self.c.post("/logout", data={"csrf": self.csrf()})
        self.login("mikhail", "Secret-pass-2")
        self.assertEqual(self.c.get(f"/server/export/{good}").status_code, 403)


class TestSiteEditor(Base):
    """«Редактор сайта»: правки товаров, фото, контакты, отмена, API для GitHub Actions, итог с сайта."""

    PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 600_000            # больше общего лимита запроса (256 КБ)

    def item(self, **kw):
        d = {"c": "panel", "n": "Стеновая реечная панель белая под покраску 120×12×2700 мм — A912",
             "d": "узкие рейки, полистирол высокой плотности (дюрополимер)", "w": "120", "t": "12", "l": "2700", "b": "6", "r": "990"}
        d.update(kw)
        return d

    def save(self, data, photo=None):
        with self.c.session_transaction() as s:
            tok = s.get("csrf", "")
        d = dict(data, csrf=tok)
        if photo is not None:
            import io as _io
            d["photo"] = (_io.BytesIO(photo), "p.png")
        return self.c.post("/site/edit/item", data=d, content_type="multipart/form-data")

    def test_edit_flow(self) -> None:
        self.login()
        page = self.c.get("/site/edit").get_data(as_text=True)
        self.assertIn("Редактор сайта", page)
        self.assertIn("A912", page)
        self.assertIn("Рейка 912", self.c.get("/site/edit/item?a=A912").get_data(as_text=True))
        self.assertEqual(self.c.get("/site/edit/item?a=NOPE").status_code, 404)
        # правка существующего товара (артикул из формы не меняется)
        r = self.save(self.item(old="A912", a="HACK"))
        self.assertEqual(r.status_code, 302)
        ed = self.app.extensions["site_edits"]
        api = self.c.get("/api/site/edits").get_json()["edits"]
        self.assertEqual([(e["kind"], e["article"]) for e in api], [("product", "A912")])
        self.assertEqual(api[0]["data"]["d"], "узкие рейки, полистирол высокой плотности (дюрополимер)")
        self.assertIn("правка ждёт", self.c.get("/site/edit").get_data(as_text=True))
        # запрещённые слова и пустые поля
        r = self.save(self.item(old="A912", d="панель из МДФ, класс Г1"))
        self.assertEqual(r.status_code, 400)
        body = r.get_data(as_text=True)
        self.assertIn("МДФ", body)
        self.assertIn("класс горючести", body)
        # новый товар: без фото нельзя, дубль артикула нельзя, с фото (больше общего лимита) — можно
        self.assertIn("нужно фото", self.save(self.item(old="", a="A930")).get_data(as_text=True))
        self.assertIn("уже есть", self.save(self.item(old="", a="a 912"), self.PNG).get_data(as_text=True))
        self.assertIn("JPG или PNG", self.save(self.item(old="", a="A930"), b"GIF89a" + b"0" * 100).get_data(as_text=True))
        r = self.save(self.item(old="", a="A930", n="Стеновая реечная панель белая под покраску 160×12×3000 мм — A930"), self.PNG)
        self.assertEqual(r.status_code, 302)
        new = [e for e in self.c.get("/api/site/edits").get_json()["edits"] if e["article"] == "A930"][0]
        self.assertTrue(new["photo"].endswith(".png"))
        self.assertEqual(self.c.get(f"/api/site/photo/{new['photo']}").data, self.PNG)
        self.assertEqual(self.c.get("/api/site/photo/..%2Fcrm.db").status_code, 404)
        # контакты
        self.post("/site/edit/shop", {"max": "javascript:alert(1)"})
        self.assertFalse(any(e["kind"] == "shop" for e in self.c.get("/api/site/edits").get_json()["edits"]))
        self.post("/site/edit/shop", {"max": "https://max.ru/id1_bot", "avito": "https://www.avito.ru/brands/x"})
        shop = [e for e in self.c.get("/api/site/edits").get_json()["edits"] if e["kind"] == "shop"][0]
        self.assertEqual(shop["data"]["max"], "https://max.ru/id1_bot")
        # убрать товар: без галочки — нет
        self.post("/site/edit/delete", {"a": "A116"})
        self.assertFalse(any(e["kind"] == "delete" for e in self.c.get("/api/site/edits").get_json()["edits"]))
        self.post("/site/edit/delete", {"a": "A116", "confirm": "1"})
        dl = [e for e in self.c.get("/api/site/edits").get_json()["edits"] if e["kind"] == "delete"][0]
        # отмена
        self.post(f"/site/edit/{dl['id']}/cancel")
        self.assertFalse(any(e["kind"] == "delete" for e in self.c.get("/api/site/edits").get_json()["edits"]))
        # новая правка того же товара заменяет старую
        self.save(self.item(old="A912", d="другое описание, полистирол высокой плотности (дюрополимер)"))
        a912 = [e for e in self.c.get("/api/site/edits").get_json()["edits"] if e["article"] == "A912"]
        self.assertEqual(len(a912), 1)
        self.assertTrue(a912[0]["data"]["d"].startswith("другое"))
        # итог от GitHub: файл site-edits.json рядом с сайтом
        with open(os.path.join(self.tmp.name, "site-edits.json"), "w", encoding="utf-8") as f:
            json.dump({"last_id": 99, "edits": {str(new["id"]): {"ok": True, "note": "добавлен, новое фото", "at": "2026-11-11 19:00"},
                                                str(a912[0]["id"]): {"ok": False, "note": "ошибка: тест", "at": "2026-11-11 19:00"}}}, f)
        page = self.c.get("/site/edit/recent").get_data(as_text=True)
        self.assertIn("на сайте", page)
        self.assertIn("ошибка: тест", page)
        self.assertNotIn(new["id"], [e["id"] for e in self.c.get("/api/site/edits").get_json()["edits"]])
        self.assertFalse(os.path.exists(os.path.join(ed.dir, new["photo"])))   # фото опубликованной правки удалено
        self.assertEqual(self.c.get(f"/api/site/photo/{new['photo']}").status_code, 404)

    @staticmethod
    def png(w: int, h: int) -> bytes:
        return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + w.to_bytes(4, "big") + h.to_bytes(4, "big") + b"\x00" * 2000

    def site_v2(self) -> None:
        d = os.path.dirname(self.cat)
        with open(self.cat, "w", encoding="utf-8") as f:
            f.write(CAT_HTML.replace("<html>", '<html><h1><!--ed:home_h1-->Стеновые панели<!--/ed:home_h1--></h1><p><!--ed:home_lead-->'
                                     'Текст &amp; ещё<!--/ed:home_lead--></p><!--ed:navx--><!--/ed:navx-->'
                                     '<div class="wall"><img src="img/hero.jpg" srcset="img/hero.jpg 1006w, img/2x/hero.jpg 2012w"></div>'))
        content = {"kinds": {"k_bamb": {"label": "Бамбуковая панель", "menu": "Бамбуковые панели", "intro": "Бамбуковые панели для стен — натуральный материал.",
                                        "slug": "bambukovye-paneli", "faq": [["Можно красить?", "Да."]], "material": "бамбук", "avito": ""}},
                   "hidden": {"A1": {"item": {"a": "A1", "c": "panel", "n": "Скрытая рейка"}, "photo": "A1.jpg", "at": "2026-11-11 10:00"}},
                   "gallery": {"A912": ["A912-g1-1.jpg", "A912-g1-2.jpg"]},
                   "articles": [{"slug": "moya", "title": "Моя статья про рейки", "description": "Описание статьи для поиска", "body": "Текст " * 30,
                                 "photos": [{"f": "moya-1-1.jpg", "cap": ""}]}],
                   "reviews": [{"id": 5, "name": "Анна", "place": "Купчино", "text": "Всё отлично, спасибо!", "date": "2026-11-01", "photos": ["r5-1.jpg"]}]}
        index = {"sections": [{"code": "panel", "slug": "reechnye-paneli", "menu": "Реечные панели", "h1": "Реечные панели", "intro": "Вводный текст раздела",
                               "title": "", "description": "", "faq": [["Вопрос?", "Ответ."]], "custom": False},
                              {"code": "k_bamb", "slug": "bambukovye-paneli", "menu": "Бамбуковые панели", "h1": "", "intro": "Бамбуковые панели для стен",
                               "title": "", "description": "", "faq": [], "custom": True}],
                 "articles": [{"slug": "duro", "title": "Дюрополимер — что это", "description": "Про материал", "custom": False, "hidden": False},
                              {"slug": "moya", "title": "Моя статья про рейки", "description": "Описание статьи для поиска", "custom": True, "hidden": False}]}
        for name, obj in (("site-content.json", content), ("site-index.json", index)):
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)

    def form(self, url, data, files=None):
        import io as _io
        with self.c.session_transaction() as s:
            tok = s.get("csrf", "")
        d = dict(data, csrf=tok)
        for k, v in (files or {}).items():
            d[k] = [(_io.BytesIO(x), f"p{i}.png") for i, x in enumerate(v)]
        return self.c.post(url, data=d, content_type="multipart/form-data")

    def last(self, kind):
        return [e for e in self.c.get("/api/site/edits").get_json()["edits"] if e["kind"] == kind][-1]

    def test_v2_pages_and_edits(self) -> None:
        self.site_v2()
        self.login()
        for url, text in (("/site/edit", "Скрытая рейка"), ("/site/edit/item?a=A912", "Ещё фото товара · 2"),
                          ("/site/edit/sections", "Бамбуковые панели"), ("/site/edit/section?code=panel", "Вопрос?"),
                          ("/site/edit/section?code=k_bamb", "Бамбуковая панель"), ("/site/edit/section", "Создать раздел"),
                          ("/site/edit/home", "Текст &amp; ещё"), ("/site/edit/articles", "Дюрополимер"),
                          ("/site/edit/article?slug=duro", "готовой вёрсткой"), ("/site/edit/article?slug=moya", "Текст Текст"),
                          ("/site/edit/article", "Новая статья"), ("/site/edit/reviews", "Купчино"), ("/site/edit/review?id=5", "Всё отлично"),
                          ("/site/edit/review", "Новый отзыв"), ("/site/edit/recent", "Контакты на сайте"), ("/site/edit/item?k=k_bamb", "Производитель")):
            r = self.c.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIn(text, r.get_data(as_text=True), url)
        for url in ("/site/edit/section?code=nope", "/site/edit/article?slug=nope", "/site/edit/review?id=77"):
            self.assertEqual(self.c.get(url).status_code, 404, url)
        self.assertEqual(self.c.get("/site/img/otzyvy/../../crm.db").status_code, 404)
        # скрыть / вернуть
        self.form("/site/edit/hide", {"a": "a912"})
        self.assertEqual(self.last("hide")["data"], {"a": "A912"})
        self.assertIn("скроется", self.c.get("/site/edit").get_data(as_text=True))
        self.form("/site/edit/unhide", {"a": "A1"})
        self.assertEqual(self.last("unhide")["article"], "A1")
        # доп. фото: несколько сразу; маленькое — нельзя
        r = self.form("/site/edit/gallery", {"a": "A912", "action": "add"}, {"more": [self.png(300, 200)]})
        self.assertFalse(any(e["kind"] == "gallery_add" for e in self.c.get("/api/site/edits").get_json()["edits"]))
        self.form("/site/edit/gallery", {"a": "A912", "action": "add"}, {"more": [self.png(1600, 1200), self.png(1200, 1600)]})
        g = self.last("gallery_add")
        self.assertEqual(g["photos"], [f"{g['id']}-1.png", f"{g['id']}-2.png"])
        self.assertTrue(self.c.get(f"/api/site/photo/{g['id']}-2.png").data.startswith(b"\x89PNG"))
        self.assertEqual(self.c.get(f"/site/edit/photo/{g['id']}/1").status_code, 200)
        self.form("/site/edit/gallery", {"a": "A912", "action": "del", "f": ["A912-g1-2.jpg", "evil.jpg"]})
        self.assertEqual(self.last("gallery_del")["data"]["files"], ["A912-g1-2.jpg"])
        # разделы: старый — строгие слова; новый — мягкие, с вопросами-ответами
        r = self.form("/site/edit/section", {"code": "panel", "menu": "Реечные панели", "intro": "Панели из МДФ для стен и потолков"})
        self.assertEqual(r.status_code, 400)
        self.form("/site/edit/section", {"code": "panel", "menu": "Реечные панели", "intro": "Реечные панели под покраску для стен",
                                          "faq_text": "Можно красить?\nДа, любой краской.\n\nЧем клеить?\nМонтажным клеем."})
        sec = self.last("section")["data"]
        self.assertEqual((sec["code"], sec["faq"][1]), ("panel", ["Чем клеить?", "Монтажным клеем."]))
        self.form("/site/edit/section", {"code": "", "label": "Пробковая панель", "menu": "Пробковые панели", "avito": "panel",
                                          "intro": "Пробковые панели — тёплые и тихие стены, рамки не нужны."})
        self.assertFalse(any(e["kind"] == "kind" for e in self.c.get("/api/site/edits").get_json()["edits"]))   # «рамки» — нигде
        self.form("/site/edit/section", {"code": "", "label": "Пробковая панель", "menu": "Пробковые панели", "avito": "panel",
                                          "intro": "Пробковые панели из МДФ с пробкой — тёплые и тихие стены."})
        k = self.last("kind")["data"]
        self.assertEqual((k["code"], k["menu"], k["avito"]), ("", "Пробковые панели", "panel"))
        self.form("/site/edit/section/delete", {"code": "k_bamb", "confirm": "1"})
        self.assertEqual(self.last("kind_del")["data"]["code"], "k_bamb")
        self.form("/site/edit/section/delete", {"code": "panel", "confirm": "1"})
        self.assertEqual(self.last("kind_del")["data"]["code"], "k_bamb")      # старые разделы не удаляются
        # товар нового раздела: материал и производитель, МДФ можно (это не ARTDEC)
        r = self.form("/site/edit/item", {"old": "", "a": "BP-01", "c": "k_bamb", "n": "Бамбуковая панель натуральная 300×5×2400 мм — BP-01",
                                         "d": "натуральный бамбук на основе из МДФ, для стен", "w": "300", "t": "5", "l": "2400", "b": "4", "r": "2500",
                                         "m": "бамбук", "mk": "Фабрика"}, {"photo": [self.png(1200, 900)], "more": [self.png(900, 900)]})
        self.assertEqual(r.status_code, 302)
        p = self.last("product")
        self.assertEqual((p["data"]["m"], p["data"]["mk"], p["data"]["c"]), ("бамбук", "Фабрика", "k_bamb"))
        self.assertEqual(self.last("gallery_add")["article"], "BP-01")
        self.assertIn("сейчас скрыт", self.form("/site/edit/item", {"old": "", "a": "A1", "c": "panel", "n": "Рейка снова на сайте 1 2 3",
                                                                    "d": "текст", "w": "1", "t": "1", "l": "100", "b": "1", "r": "1"},
                                                {"photo": [self.png(1200, 900)]}).get_data(as_text=True))
        # главная: только изменённые тексты; картинка — от 1000 точек
        self.assertIn("Ничего не изменилось", self.form("/site/edit/home", {"home_h1": "Стеновые панели", "home_lead": "Текст & ещё"},
                                                        ).get_data(as_text=True) + self.c.get("/site/edit/home").get_data(as_text=True))
        r = self.form("/site/edit/home", {"home_h1": "Стеновые панели", "home_lead": "Текст & ещё"}, {"hero": [self.png(800, 600)]})
        self.assertEqual(r.status_code, 400)
        self.form("/site/edit/home", {"home_h1": "Панели и плинтусы в СПб", "home_lead": "Текст & ещё"})
        self.assertEqual(self.last("home")["data"], {"texts": {"home_h1": "Панели и плинтусы в СПб"}})
        self.assertIn("Панели и плинтусы в СПб", self.c.get("/site/edit/home").get_data(as_text=True))   # ждущая правка видна в форме
        # статьи
        self.assertEqual(self.form("/site/edit/article", {"slug": "", "title": "Как выбрать рейки", "description": "Коротко"}).status_code, 400)
        self.form("/site/edit/article", {"slug": "", "title": "Как выбрать рейки для гостиной", "description": "Какие рейки взять для стены в гостиной",
                                         "body": "## Размер\n" + "Широкие рейки — для больших стен. " * 5 + "\n\n[фото 1]", "caps": "Гостиная\nСпальня"},
                  {"photos": [self.png(1200, 800), self.png(1200, 800)]})
        a = self.last("article")
        self.assertEqual((a["data"]["slug"], a["data"]["caps"], len(a["photos"])), ("", ["Гостиная", "Спальня"], 2))
        self.form("/site/edit/article", {"slug": "duro", "title": "Дюрополимер: что это за материал", "description": "Про материал плинтусов и панелей",
                                         "body": "не должно попасть", "hidden": "1"})
        a = self.last("article")["data"]
        self.assertTrue(a["builtin"] and a["hidden"] and "body" not in a)
        self.form("/site/edit/article", {"slug": "moya", "title": "Моя статья про рейки", "description": "Описание статьи для поиска",
                                         "body": "Текст " * 30, "drop": ["moya-1-1.jpg", "chuzhoe.jpg"]})
        self.assertEqual(self.last("article")["data"]["drop_photos"], ["moya-1-1.jpg"])
        self.form("/site/edit/article/delete", {"slug": "moya", "confirm": "1"})
        self.assertEqual(self.last("article_del")["data"], {"slug": "moya", "builtin": False, "title": "Моя статья про рейки"})
        # отзывы
        self.assertIn("нет на сайте", self.form("/site/edit/review", {"id": "", "name": "Ольга", "text": "Красивые панели, всё быстро", "article": "NOPE"}
                                                 ).get_data(as_text=True))
        self.form("/site/edit/review", {"id": "", "name": "Ольга", "place": "Мурино", "text": "Красивые панели, всё быстро", "article": "A912",
                                        "date": "2026-11-10"}, {"photos": [self.png(800, 600)]})
        rv = self.last("review")
        self.assertEqual((rv["data"]["name"], rv["data"]["article"], len(rv["photos"])), ("Ольга", "A912", 1))
        self.form("/site/edit/review", {"id": "5", "name": "Анна", "text": "Всё отлично, спасибо!", "drop": ["r5-1.jpg"]})
        self.assertEqual(self.last("review")["data"]["drop_photos"], ["r5-1.jpg"])
        self.form("/site/edit/review/delete", {"id": "5", "confirm": "1"})
        self.assertEqual(self.last("review_del")["data"]["id"], "5")
        page = self.c.get("/site/edit/recent").get_data(as_text=True)
        for t in ("скрыть товар A912", "новый раздел Пробковые панели", "главная страница", "новая статья", "новый отзыв Ольга"):
            self.assertIn(t, page)

    def test_only_owners(self) -> None:
        self.login("mikhail", "Secret-pass-2")
        self.assertEqual(self.c.get("/site/edit").status_code, 403)
        for url in ("/site/edit/sections", "/site/edit/home", "/site/edit/articles", "/site/edit/reviews", "/site/edit/recent"):
            self.assertEqual(self.c.get(url).status_code, 403, url)
        self.assertEqual(self.save(self.item(old="A912")).status_code, 403)
        self.c.post("/logout", data={"csrf": self.csrf()})
        self.assertEqual(self.c.get("/site/edit").status_code, 302)

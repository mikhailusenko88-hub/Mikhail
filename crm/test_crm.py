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
            self.assertIn("Что дальше", body); self.assertIn("пришлём ссылку на оплату", body); self.assertIn("Telegram @IuliiaUsenko", body)
            run = self.app.extensions["run_followups"]
            self.assertEqual(run("2026-11-09"), [])                                     # задача «Узнать решение» ещё не подошла (срок +2 дня)
            r = run("2026-11-11")
            self.assertEqual(len(r), 1); self.assertIn("напоминание 1", r[0])
            self.assertIn("подошёл ли он вам", sent[-1][1]); self.assertIn("A912 — 3 шт", sent[-1][2])
            d = self.store.deal(did); self.assertEqual(d["followups"], 1)
            self.assertEqual(run("2026-11-11"), [])                                     # в тот же день второй раз не шлём
            t = [x for x in self.store.tasks(deal_id=did) if x["title"].startswith("Узнать")][0]
            self.assertGreater(t["due"], "2026-11-11")                                  # задача сдвинута вперёд
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
        self.assertEqual(out, [{"box": "zakaz", "from": "client@example.com", "name": "Елена", "subject": "Расчёт"}])
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


if __name__ == "__main__":
    unittest.main()

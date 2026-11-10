"""Учёт и отчётность ИП в CRM «Наш декор» (10.11.2026).

- Реквизиты компании по ИНН — из открытого ЕГРЮЛ/ЕГРИП ФНС (egrul.nalog.ru).
- Товар для документов: ТН ВЭД, вес, единица — для УПД, ДОПП, декларации по косвенным налогам.
- Закупки (спецификации к договору поставки): ДОПП или нет (СПОТ — ввоз из ЕАЭС автомобилем), обеспечительный платёж,
  оприходование, себестоимость партии (товар + НДС при ввозе + перевозка + комиссии), списание партий FIFO при отгрузке,
  счётчик оплат по договору до 3 млн ₽ (постановка на учёт в банке).
- Вознаграждения дизайнерам (10 % от оплаченной суммы; платим только ИП и самозанятым).
- Налоговый календарь ИП на УСН «доходы минус расходы»: взносы, авансы, декларация, НДС при ввозе из ЕАЭС
  (декларация + заявление о ввозе до 20-го), статформа в ФТС (до 10-го рабочего дня), заявление с отметкой — поставщику.

Сроки — по НК РФ (перенос на рабочий день, ст. 6.1), Постановлению Правительства № 891 (статформа), 101-ФЗ (СПОТ, ДОПП).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from store import Store, iso_now, today

log = logging.getLogger("crm.buh")

# ------------------------------------------------------------------ константы
EAEU = {"KZ": "Казахстан", "BY": "Беларусь", "AM": "Армения", "KG": "Киргизия"}
EAEU_FROM = {"KZ": "Казахстана", "BY": "Беларуси", "AM": "Армении", "KG": "Киргизии"}
TRANSPORTS = [("auto", "автомобилем"), ("rail", "железной дорогой"), ("air", "самолётом"), ("post", "почтой / курьером"),
              ("other", "другое")]
VAT_RATE = 22                         # НДС при ввозе (и обеспечительный платёж СПОТ), %
CONTRACT_LIMIT_KOP = 3_000_000 * 100  # импортный контракт ставится на учёт в банке с 3 млн ₽ (Инструкция ЦБ 181-И)
VAT_FREE_LIMIT_KOP = 20_000_000 * 100  # порог освобождения от НДС на УСН (сохранён на 2027–2029, 228-ФЗ)
FIXED_CONTRIB = {2026: 57_390, 2027: 61_154}   # фиксированные взносы ИП за полный год, ₽ (ст. 430 НК)
DESIGNER_PCT = 10
SUPPLIER_DEFAULT = {"supplier": "ТОО «Art Dec»", "supplier_bin": "200540013338", "contract": "№ 1 от 10.11.2026",
                    "country": "KZ", "transport": "auto"}
TNVED_DEFAULT = {"panel": "3925908009", "color": "3925908009"}   # панели; погонаж (молдинги, плинтусы, карнизы, уголки) — 3916905000
TNVED_PROFILE = "3916905000"
DOPP_STATUS = {"": "не подан", "sent": "подан, ждём статус", "secured": "«Обеспечен», есть QR", "refused": "отказ"}

# Нерабочие дни сверх суббот и воскресений. 2026 — сверено со сроками статформ ФТС на 2026 г.;
# 2027 — постановление Правительства от 17.09.2026 № 1187. Другие годы — праздники ст. 112 ТК без переносов (ориентир).
_HOL = {
    2026: ["01-01", "01-02", "01-05", "01-06", "01-07", "01-08", "01-09", "02-23", "03-09", "05-01", "05-11", "06-12",
           "11-04", "12-31"],
    2027: ["01-01", "01-04", "01-05", "01-06", "01-07", "01-08", "02-22", "02-23", "03-08", "05-03", "05-10", "06-14",
           "11-04", "11-05", "12-31"],
}
_WORK_SAT = {2027: ["02-20"]}
_FIXED_HOL = ["01-01", "01-02", "01-03", "01-04", "01-05", "01-06", "01-07", "01-08", "02-23", "03-08", "05-01", "05-09",
              "06-12", "11-04"]


def is_workday(d: date) -> bool:
    md = d.strftime("%m-%d")
    if md in _WORK_SAT.get(d.year, []):
        return True
    if d.weekday() >= 5:
        return False
    return md not in _HOL.get(d.year, _FIXED_HOL)


def calendar_known(year: int) -> bool:
    return year in _HOL


def shift_to_workday(d: date) -> date:
    """Срок, выпавший на выходной или праздник, переносится на ближайший рабочий день (ст. 6.1 НК)."""
    while not is_workday(d):
        d += timedelta(days=1)
    return d


def nth_workday(year: int, month: int, n: int) -> date:
    d, k = date(year, month, 1), 0
    while True:
        if is_workday(d):
            k += 1
            if k == n:
                return d
        d += timedelta(days=1)


def next_month(d: date) -> tuple[int, int]:
    return (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)


def kop(v: Any) -> int | None:
    """«1 234,56» → 123456 копеек; пусто — None."""
    s = re.sub(r"[\s ₽]", "", str(v if v is not None else "")).replace(",", ".")
    if not s:
        return None
    try:
        return int((Decimal(s) * 100).quantize(Decimal("1")))
    except InvalidOperation:
        return None


def kop_in(k: int | None) -> str:
    """Копейки → значение для поля ввода: 123456 → «1234,56», 100 → «1»."""
    if k is None:
        return ""
    r, c = divmod(abs(int(k)), 100)
    return ("-" if k < 0 else "") + (f"{r},{c:02d}" if c else str(r))


def iso(v: Any) -> str:
    v = (str(v or "")).strip()
    return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else ""


def dmy(s: str) -> str:
    return f"{s[8:10]}.{s[5:7]}.{s[:4]}" if iso(s[:10]) else ""


def contrib_for_year(year: int, reg: date | None) -> int | None:
    """Фиксированные взносы за год в копейках, за неполный год — пропорционально (п. 3 ст. 430 НК)."""
    full = FIXED_CONTRIB.get(year)
    if full is None:
        return None
    if not reg or reg.year < year:
        return full * 100
    if reg.year > year:
        return 0
    months = 12 - reg.month                                 # полные месяцы после месяца регистрации
    dim = ((date(reg.year + (reg.month == 12), reg.month % 12 + 1, 1)) - date(reg.year, reg.month, 1)).days
    days = dim - reg.day + 1                                 # дни месяца регистрации, начиная с дня регистрации
    return int((Decimal(full * 100) / 12 * months + Decimal(full * 100) / 12 * days / dim).quantize(Decimal("1")))


# ------------------------------------------------------------------ ЕГРЮЛ / ЕГРИП
EGRUL = "https://egrul.nalog.ru"


def _egrul_http(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    if not url.startswith(EGRUL + "/"):
        raise ValueError("только egrul.nalog.ru")
    from tochka import ssl_context  # системные корни + корень Минцифры
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_context()) as r:
            return r.status, r.read(1_000_000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001 — сеть, DNS, сертификат
        log.warning("ЕГРЮЛ не ответил: %s %s", type(e).__name__, str(e)[:120])
        return 0, b""


def egrul_lookup(inn: str, http: Callable[..., tuple[int, bytes]] | None = None, pause: float = 0.6) -> dict[str, str]:
    """Сведения о компании или ИП по ИНН из открытого сервиса ФНС. Ошибка — ValueError с понятным текстом."""
    inn = re.sub(r"\D", "", inn or "")
    if len(inn) not in (10, 12):
        raise ValueError("ИНН — 10 цифр у компании или 12 у ИП")
    http = http or _egrul_http
    hdr = {"User-Agent": "Mozilla/5.0 (CRM Nash Dekor)", "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
    body = urllib.parse.urlencode({"vyp3CaptchaToken": "", "page": "", "query": inn, "region": "",
                                   "PreventChromeAutocomplete": ""}).encode()
    st, raw = http("POST", EGRUL + "/", {**hdr, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}, body)
    if st != 200:
        raise ValueError("сервис ФНС не ответил — попробуйте позже или заполните вручную")
    try:
        first = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise ValueError("сервис ФНС ответил непонятно — заполните вручную") from None
    if first.get("captchaRequired"):
        raise ValueError("сервис ФНС просит капчу — заполните вручную или попробуйте позже")
    tok = str(first.get("t") or "")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{10,200}", tok):
        raise ValueError("сервис ФНС не дал ответа — заполните вручную")
    rows: list[dict[str, Any]] = []
    for _ in range(6):
        st, raw = http("GET", f"{EGRUL}/search-result/{tok}?r={int(time.time() * 1000)}", hdr, None)
        if st != 200:
            raise ValueError("сервис ФНС не ответил — попробуйте позже")
        try:
            res = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ValueError("сервис ФНС ответил непонятно — заполните вручную") from None
        if res.get("status") == "wait":
            time.sleep(pause)
            continue
        rows = [r for r in res.get("rows") or [] if isinstance(r, dict)]
        break
    rows = [r for r in rows if str(r.get("i") or "") == inn] or rows
    if not rows:
        raise ValueError(f"по ИНН {inn} в ЕГРЮЛ/ЕГРИП ничего не найдено")
    r = rows[0]
    ip = (r.get("k") == "fl") or len(inn) == 12
    name = str(r.get("n") or "").strip()
    short = str(r.get("c") or "").strip()
    out = {"inn": inn, "ogrn": str(r.get("o") or ""), "kpp": "" if ip else str(r.get("p") or ""),
           "legal_address": str(r.get("a") or "").strip(), "closed": str(r.get("e") or "").strip()}
    if ip:
        fio = " ".join(w.capitalize() for w in name.split())
        out["full_name"] = f"Индивидуальный предприниматель {fio}".strip()
        out["company"] = f"ИП {fio}".strip()
        out["signer"] = fio
    else:
        out["full_name"] = name
        out["company"] = short or name
        g = str(r.get("g") or "").strip()            # «ГЕНЕРАЛЬНЫЙ ДИРЕКТОР: ИВАНОВ ИВАН ИВАНОВИЧ»
        if ":" in g:
            pos, fio = g.split(":", 1)
            out["signer"] = f"{pos.strip().capitalize()} {' '.join(w.capitalize() for w in fio.split())}".strip()
        else:
            out["signer"] = g
    return out


# ------------------------------------------------------------------ логика
class Buh:
    def __init__(self, store: Store, egrul_http: Callable[..., tuple[int, bytes]] | None = None) -> None:
        self.s = store
        self.egrul_http = egrul_http
        store.stock_hooks.append(self._lots_on_move)

    def c(self) -> sqlite3.Connection:
        return self.s.c()

    # ---------------------------------------------------------------- товары для документов
    def default_tnved(self, article: str) -> str:
        p = self.s.catalog.get(article)
        return TNVED_DEFAULT.get(p.kind, TNVED_PROFILE) if p else ""

    def product_info(self, article: str) -> dict[str, Any]:
        p = self.s.catalog.get(article)
        art = p.article if p else (article or "").strip().upper()
        row = self.c().execute("SELECT * FROM product_info WHERE article=?", (art,)).fetchone()
        return {"article": art, "name": p.name if p else "", "kind": p.kind if p else "",
                "tnved": (row["tnved"] if row and row["tnved"] else self.default_tnved(art)),
                "tnved_own": bool(row and row["tnved"]), "weight_g": int(row["weight_g"]) if row else 0,
                "unit": (row["unit"] if row and row["unit"] else "шт"),
                "doc_name": (row["doc_name"] if row and row["doc_name"] else (f"{p.name}, арт. {art}" if p else art))}

    def products(self) -> list[dict[str, Any]]:
        return [self.product_info(p.article) for p in self.s.catalog.all()]

    def set_product_info(self, article: str, user: str, tnved: str, weight_g: Any, doc_name: str) -> None:
        info = self.product_info(article)
        art = info["article"]
        tn = re.sub(r"\D", "", tnved or "")[:10]
        if tn == self.default_tnved(art):
            tn = ""
        wv = str(weight_g if weight_g is not None else "").strip().replace(",", ".")
        w = int(round(float(wv))) if re.fullmatch(r"\d{1,6}(?:\.\d+)?", wv) else (0 if not wv else info["weight_g"])
        p = self.s.catalog.get(art)
        dn = (doc_name or "").strip()[:200]
        if p and dn == f"{p.name}, арт. {art}":
            dn = ""
        with self.s.tx() as c:
            c.execute("INSERT INTO product_info(article, tnved, weight_g, doc_name, updated_at) VALUES (?,?,?,?,?)"
                      " ON CONFLICT(article) DO UPDATE SET tnved=excluded.tnved, weight_g=excluded.weight_g,"
                      " doc_name=excluded.doc_name, updated_at=excluded.updated_at", (art, tn, w, dn, iso_now()))
            self.s.log(c, f"Товар {art} для документов: ТН ВЭД {tn or self.default_tnved(art)}, вес {w} г", user)

    # ---------------------------------------------------------------- закупки
    def purchases(self) -> list[sqlite3.Row]:
        return self.c().execute(
            "SELECT p.*, (SELECT COALESCE(SUM(qty*price_kop),0) FROM purchase_lines l WHERE l.purchase_id=p.id) AS goods_kop,"
            " (SELECT COALESCE(SUM(qty),0) FROM purchase_lines l WHERE l.purchase_id=p.id) AS pcs"
            " FROM purchases p ORDER BY p.id DESC").fetchall()

    def purchase(self, pid: int) -> sqlite3.Row | None:
        return self.c().execute(
            "SELECT p.*, (SELECT COALESCE(SUM(qty*price_kop),0) FROM purchase_lines l WHERE l.purchase_id=p.id) AS goods_kop,"
            " (SELECT COALESCE(SUM(qty),0) FROM purchase_lines l WHERE l.purchase_id=p.id) AS pcs,"
            " (SELECT COALESCE(SUM(qty*weight_g),0) FROM purchase_lines l WHERE l.purchase_id=p.id) AS weight_total"
            " FROM purchases p WHERE p.id=?", (pid,)).fetchone()

    def purchase_lines(self, pid: int) -> list[sqlite3.Row]:
        return self.c().execute("SELECT * FROM purchase_lines WHERE purchase_id=? ORDER BY id", (pid,)).fetchall()

    def create_purchase(self, user: str, num: str = "", transport: str = "auto") -> int:
        last = self.c().execute("SELECT * FROM purchases ORDER BY id DESC LIMIT 1").fetchone()
        base = dict(SUPPLIER_DEFAULT)
        if last:
            base.update({k: last[k] for k in ("supplier", "supplier_bin", "contract", "country")})
        if not num:
            nums = [int(r[0]) for r in self.c().execute("SELECT num FROM purchases").fetchall() if str(r[0]).isdigit()]
            num = str(max(nums) + 1 if nums else 1)
        ts = iso_now()
        with self.s.tx() as c:
            cur = c.execute("INSERT INTO purchases(num, supplier, supplier_bin, contract, country, transport, created_at, updated_at)"
                            " VALUES (?,?,?,?,?,?,?,?)", (num.strip()[:20], base["supplier"], base["supplier_bin"],
                                                          base["contract"], base["country"],
                                                          transport if transport in dict(TRANSPORTS) else "auto", ts, ts))
            pid = int(cur.lastrowid)
            self.s.log(c, f"Закупка: создана спецификация № {num}", user)
        return pid

    TEXT_FIELDS = ("num", "supplier", "supplier_bin", "contract", "rate", "carrier", "vehicle", "esf", "snt", "cmr", "dopp_no",
                   "note")
    DATE_FIELDS = ("spec_date", "paid_at", "ship_date", "border_date", "dopp_at", "guarantee_paid_at", "import_date", "decl_at",
                   "vat_paid_at", "statform_at", "decl_mark_at", "supplier_sent_at")
    KOP_FIELDS = ("paid_kop", "bank_fee_kop", "delivery_kop", "other_kop")
    KOP_NULL_FIELDS = ("guarantee_kop", "vat_kop")

    def update_purchase(self, pid: int, user: str, form: dict[str, Any]) -> list[str]:
        p = self.purchase(pid)
        if not p:
            return []
        sets: dict[str, Any] = {}
        for k in self.TEXT_FIELDS:
            if k in form:
                sets[k] = str(form[k] or "").strip()[:300]
        for k in self.DATE_FIELDS:
            if k in form:
                sets[k] = iso(form[k])
        for k in self.KOP_FIELDS:
            if k in form:
                sets[k] = max(kop(form[k]) or 0, 0)
        for k in self.KOP_NULL_FIELDS:
            if k in form:
                v = kop(form[k])
                sets[k] = None if v is None else max(v, 0)
        if "country" in form and form["country"] in EAEU:
            sets["country"] = form["country"]
        if "transport" in form and form["transport"] in dict(TRANSPORTS):
            sets["transport"] = form["transport"]
        if "dopp_status" in form and form["dopp_status"] in DOPP_STATUS:
            sets["dopp_status"] = form["dopp_status"]
        if "qr_sent" in form or "_qr" in form:
            sets["qr_sent"] = 1 if form.get("qr_sent") else 0
        if p["received_at"] and "import_date" in sets and sets["import_date"] != p["import_date"] and not sets["import_date"]:
            sets.pop("import_date")
        changed = [k for k, v in sets.items() if p[k] != v]
        if not changed:
            return []
        with self.s.tx() as c:
            c.execute(f"UPDATE purchases SET {', '.join(k + '=?' for k in changed)}, updated_at=? WHERE id=?",
                      (*[sets[k] for k in changed], iso_now(), pid))
            self.s.log(c, f"Закупка № {p['num']}: изменено {len(changed)} пол.", user)
        return changed

    def delete_purchase(self, pid: int, user: str) -> str:
        p = self.purchase(pid)
        if not p:
            return "нет такой закупки"
        if p["received_at"]:
            return "закупка уже оприходована — сначала отмените оприходование"
        if p["paid_at"]:
            return "по закупке есть оплата поставщику — удалить нельзя"
        with self.s.tx() as c:
            c.execute("DELETE FROM purchases WHERE id=?", (pid,))
            self.s.log(c, f"Закупка № {p['num']} удалена", user)
        return ""

    def add_purchase_line(self, pid: int, user: str, article: str, qty: Any, price: Any) -> str:
        p = self.purchase(pid)
        if not p:
            return "нет такой закупки"
        if p["received_at"]:
            return "закупка оприходована — позиции не меняются"
        info = self.product_info(article)
        art = info["article"]
        if not art:
            return "не указан артикул"
        try:
            q = int(str(qty).strip())
        except ValueError:
            return f"{art}: количество — целое число штук"
        pr = kop(price)
        if q <= 0 or pr is None or pr < 0:
            return f"{art}: укажите количество и цену за штуку"
        with self.s.tx() as c:
            c.execute("INSERT INTO purchase_lines(purchase_id, article, qty, price_kop, tnved, weight_g) VALUES (?,?,?,?,?,?)",
                      (pid, art, q, pr, info["tnved"], info["weight_g"]))
            c.execute("UPDATE purchases SET updated_at=? WHERE id=?", (iso_now(), pid))
        return ""

    def paste_lines(self, pid: int, user: str, text: str) -> tuple[int, list[str]]:
        """Строки «артикул количество цена» (разделители — пробел, таб, «;»): A902 18 423,85."""
        n, errs = 0, []
        for raw in (text or "").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            m = re.match(r"^(.+?)[\s;\t]+(\d+)[\s;\t]+([\d\s ]*\d(?:[.,]\d{1,2})?)\s*(?:₽|руб\.?)?$", raw)
            if not m:
                errs.append(f"не понял строку: «{raw[:40]}»")
                continue
            err = self.add_purchase_line(pid, user, m.group(1).strip(), m.group(2), m.group(3))
            if err:
                errs.append(err)
            else:
                n += 1
        return n, errs

    def del_purchase_line(self, pid: int, lid: int, user: str) -> str:
        p = self.purchase(pid)
        if not p or p["received_at"]:
            return "закупка оприходована — позиции не меняются"
        with self.s.tx() as c:
            c.execute("DELETE FROM purchase_lines WHERE id=? AND purchase_id=?", (lid, pid))
        return ""

    def dopp_needed(self, p: Any) -> bool:
        """СПОТ: ДОПП обязателен при ввозе из Беларуси, Казахстана, Армении, Киргизии автомобильным транспортом
        (иные виды транспорта — не ранее 2027 г. по решению Правительства)."""
        return p["country"] in EAEU and p["transport"] == "auto"

    def vat_kop(self, p: Any) -> int:
        return int(p["vat_kop"]) if p["vat_kop"] is not None else round(int(p["goods_kop"]) * VAT_RATE / 100)

    def guarantee_kop(self, p: Any) -> int:
        return int(p["guarantee_kop"]) if p["guarantee_kop"] is not None else round(int(p["goods_kop"]) * VAT_RATE / 100)

    def cost_split(self, p: Any, lines: list[Any]) -> list[tuple[Any, int]]:
        """Себестоимость штуки по каждой строке: товар + НДС при ввозе и комиссии банка (по стоимости)
        + перевозка (по весу, если у всех строк есть вес, иначе по стоимости) + прочее (по стоимости)."""
        goods = sum(int(x["qty"]) * int(x["price_kop"]) for x in lines)
        weights = [int(x["qty"]) * int(x["weight_g"]) for x in lines]
        by_w = all(w > 0 for w in weights) and sum(weights) > 0
        vat = int(p["vat_kop"]) if p["vat_kop"] is not None else round(goods * VAT_RATE / 100)
        extra_v = vat + int(p["bank_fee_kop"] or 0) + int(p["other_kop"] or 0)
        deliv = int(p["delivery_kop"] or 0)
        out = []
        for x, w in zip(lines, weights):
            val = int(x["qty"]) * int(x["price_kop"])
            share_v = Decimal(val) / goods if goods else Decimal(0)
            share_d = (Decimal(w) / sum(weights)) if by_w else share_v
            total = Decimal(val) + extra_v * share_v + deliv * share_d
            out.append((x, int((total / int(x["qty"])).quantize(Decimal("1")))))
        return out

    def receive(self, pid: int, user: str, day: str = "") -> str:
        """Оприходовать партию: остатки на склад, партии с себестоимостью. День — дата принятия на учёт."""
        p = self.purchase(pid)
        if not p:
            return "нет такой закупки"
        if p["received_at"]:
            return "уже оприходовано"
        lines = self.purchase_lines(pid)
        if not lines:
            return "добавьте позиции спецификации"
        day = iso(day) or p["import_date"] or today()
        ts = iso_now()
        with self.s.tx() as c:
            parts = []
            for x, unit in self.cost_split(p, lines):
                c.execute("INSERT INTO stock(article, qty, updated_at, updated_by) VALUES (?,0,?,?) ON CONFLICT(article) DO NOTHING",
                          (x["article"], ts, user))
                c.execute("UPDATE stock SET qty=qty+?, updated_at=?, updated_by=? WHERE article=?", (int(x["qty"]), ts, user, x["article"]))
                c.execute("INSERT INTO lots(purchase_id, article, qty_in, qty_left, unit_kop, received_at) VALUES (?,?,?,?,?,?)",
                          (pid, x["article"], int(x["qty"]), int(x["qty"]), unit, day))
                parts.append(f"{x['article']} +{x['qty']}")
            c.execute("UPDATE purchases SET received_at=?, import_date=CASE WHEN import_date='' THEN ? ELSE import_date END,"
                      " updated_at=? WHERE id=?", (day, day, ts, pid))
            self.s.log(c, f"Закупка № {p['num']} оприходована {dmy(day)}: " + ", ".join(parts), user)
        return ""

    def unreceive(self, pid: int, user: str) -> str:
        p = self.purchase(pid)
        if not p or not p["received_at"]:
            return "закупка не оприходована"
        lots = self.c().execute("SELECT * FROM lots WHERE purchase_id=?", (pid,)).fetchall()
        if any(int(x["qty_left"]) != int(x["qty_in"]) for x in lots):
            return "из этой партии уже отгружали — отменить оприходование нельзя"
        ts = iso_now()
        with self.s.tx() as c:
            for x in lots:
                c.execute("UPDATE stock SET qty=MAX(qty-?,0), updated_at=?, updated_by=? WHERE article=?",
                          (int(x["qty_in"]), ts, user, x["article"]))
            c.execute("DELETE FROM lots WHERE purchase_id=?", (pid,))
            c.execute("UPDATE purchases SET received_at='', updated_at=? WHERE id=?", (ts, pid))
            self.s.log(c, f"Закупка № {p['num']}: оприходование отменено", user)
        return ""

    def lots(self, pid: int | None = None) -> list[sqlite3.Row]:
        if pid:
            return self.c().execute("SELECT * FROM lots WHERE purchase_id=? ORDER BY id", (pid,)).fetchall()
        return self.c().execute("SELECT l.*, p.num FROM lots l JOIN purchases p ON p.id=l.purchase_id WHERE l.qty_left>0"
                                " ORDER BY l.article, l.received_at, l.id").fetchall()

    def _lots_on_move(self, c: sqlite3.Connection, did: int, sign: int, user: str) -> None:
        if sign > 0:   # возврат на склад (сделка вернулась из «Отгружено» или удалена) — партии восстанавливаются
            for sc in c.execute("SELECT * FROM sale_costs WHERE deal_id=?", (did,)).fetchall():
                if sc["lot_id"]:
                    c.execute("UPDATE lots SET qty_left=qty_left+? WHERE id=?", (int(sc["qty"]), sc["lot_id"]))
            c.execute("DELETE FROM sale_costs WHERE deal_id=?", (did,))
            return
        day = today()
        for r in c.execute("SELECT article, SUM(qty) q FROM lines WHERE deal_id=? GROUP BY article", (did,)).fetchall():
            need = int(r["q"] or 0)
            if need <= 0:
                continue
            for lot in c.execute("SELECT * FROM lots WHERE article=? AND qty_left>0 ORDER BY received_at, id", (r["article"],)).fetchall():
                take = min(need, int(lot["qty_left"]))
                c.execute("UPDATE lots SET qty_left=qty_left-? WHERE id=?", (take, lot["id"]))
                c.execute("INSERT INTO sale_costs(deal_id, lot_id, article, qty, unit_kop, day) VALUES (?,?,?,?,?,?)",
                          (did, lot["id"], r["article"], take, int(lot["unit_kop"]), day))
                need -= take
                if need == 0:
                    break
            if need > 0:
                c.execute("INSERT INTO sale_costs(deal_id, lot_id, article, qty, unit_kop, day) VALUES (?,NULL,?,?,0,?)",
                          (did, r["article"], need, day))

    def sale_costs(self, did: int) -> list[sqlite3.Row]:
        return self.c().execute("SELECT sc.*, p.num, p.paid_at FROM sale_costs sc LEFT JOIN lots l ON l.id=sc.lot_id"
                                " LEFT JOIN purchases p ON p.id=l.purchase_id WHERE sc.deal_id=? ORDER BY sc.id", (did,)).fetchall()

    def contract_paid(self) -> list[dict[str, Any]]:
        """Сколько оплачено поставщику по каждому договору — для постановки на учёт в банке с 3 млн ₽."""
        rows = self.c().execute("SELECT contract, supplier, COALESCE(SUM(paid_kop),0) s, COUNT(*) n FROM purchases"
                                " WHERE paid_at!='' GROUP BY contract, supplier ORDER BY s DESC").fetchall()
        unk = self.s.setting("contract_unk", "")
        return [{"contract": r["contract"], "supplier": r["supplier"], "paid": int(r["s"]), "n": int(r["n"]),
                 "pct": min(100, int(int(r["s"]) * 100 / CONTRACT_LIMIT_KOP)), "unk": unk} for r in rows]

    def steps(self, p: Any) -> list[dict[str, Any]]:
        """Чек-лист ввоза по закупке: что сделано, что дальше, до какого числа."""
        need = self.dopp_needed(p)
        st: list[dict[str, Any]] = []

        def add(title: str, done: bool, due: str = "", hint: str = "") -> None:
            st.append({"title": title, "done": done, "due": due, "hint": hint})

        add("Спецификация и счёт поставщика", bool(p["spec_date"] and int(p["goods_kop"])),
            hint="позиции, цены в рублях, дата спецификации")
        add("Оплата поставщику", bool(p["paid_at"] and p["paid_kop"]), hint="дата и сумма платежа с расчётного счёта")
        add("Документы от поставщика: ЭСФ, СНТ, транспортная накладная", bool(p["esf"] and p["cmr"] and (p["snt"] or not need)),
            hint="номера понадобятся в ДОПП и декларации")
        if need:
            due = ""
            if p["border_date"]:
                due = (date.fromisoformat(p["border_date"]) - timedelta(days=2)).isoformat()
            add("ДОПП и обеспечительный платёж (СПОТ)", p["dopp_status"] == "secured" and bool(p["guarantee_paid_at"]), due,
                f"не позднее чем за 2 дня до ввоза; платёж {VAT_RATE} % — на КБК 182 1 04 03000 01 1000 110, не ЕНП")
            add("QR-код передан водителю", bool(p["qr_sent"]), due)
        else:
            add("ДОПП не нужен", True, hint="СПОТ сейчас — только для ввоза из ЕАЭС автомобилем")
        add("Ввоз в Россию", bool(p["import_date"]), p["border_date"])
        add("Оприходовано на склад", bool(p["received_at"]), hint="дата принятия на учёт — от неё сроки декларации")
        if p["received_at"]:
            y, m = next_month(date.fromisoformat(p["received_at"]))
            add("Декларация по косвенным налогам + заявление о ввозе, НДС", bool(p["decl_at"] and p["vat_paid_at"]),
                shift_to_workday(date(y, m, 20)).isoformat(), "через Saby с подписью ИП; обеспечительный платёж засчитывается в НДС")
        else:
            add("Декларация по косвенным налогам + заявление о ввозе, НДС", False, hint="до 20-го числа месяца после оприходования")
        base = p["import_date"] or p["received_at"]
        if base:
            y, m = next_month(date.fromisoformat(base))
            add("Статформа в таможню (ФТС)", bool(p["statform_at"]), nth_workday(y, m, 10).isoformat(),
                "личный кабинет участника ВЭД на сайте ФТС, подпись ИП")
        else:
            add("Статформа в таможню (ФТС)", False, hint="до 10-го рабочего дня месяца после ввоза")
        sup_due = ""
        if p["ship_date"]:
            sup_due = (date.fromisoformat(p["ship_date"]) + timedelta(days=180)).isoformat()
        add("Заявление с отметкой налоговой — поставщику", bool(p["decl_mark_at"] and p["supplier_sent_at"]), sup_due,
            "без него поставщик не подтвердит НДС 0 % и заплатит НДС Казахстана; срок у него — 180 дней с отгрузки")
        return st

    def status(self, p: Any) -> tuple[str, str]:
        steps = self.steps(p)
        nxt = next((x for x in steps if not x["done"]), None)
        if not nxt:
            return "закрыта", "good"
        if p["received_at"]:
            return "на складе · " + nxt["title"].split(":")[0].split(" (")[0].lower(), "warn"
        return nxt["title"].split(":")[0].split(" (")[0], ""

    # ---------------------------------------------------------------- дизайнеры
    def designers(self) -> list[sqlite3.Row]:
        return self.c().execute("SELECT * FROM clients WHERE kind='d' ORDER BY name").fetchall()

    def set_deal_designer(self, did: int, user: str, designer_id: Any, pct: Any) -> str:
        d = self.s.deal(did)
        if not d:
            return "нет такой заявки"
        try:
            dz = int(designer_id) if str(designer_id or "").strip() else None
        except ValueError:
            dz = None
        if dz is not None:
            row = self.c().execute("SELECT * FROM clients WHERE id=? AND kind='d'", (dz,)).fetchone()
            if not row:
                return "это не дизайнер — отметьте в карточке клиента «Кто это: Дизайнер»"
            if dz == d["client_id"]:
                return "дизайнер сам покупатель — ему скидка, вознаграждение не начисляется"
        try:
            p = max(0, min(int(str(pct or DESIGNER_PCT).strip()), 30))
        except ValueError:
            p = DESIGNER_PCT
        with self.s.tx() as c:
            c.execute("UPDATE deals SET designer_id=?, designer_pct=?, updated_at=? WHERE id=?", (dz, p, iso_now(), did))
            nm = self.c().execute("SELECT name FROM clients WHERE id=?", (dz,)).fetchone() if dz else None
            self.s.log(c, f"Дизайнер: {nm[0] + f', {p} %' if nm else 'не указан'}", user, deal_id=did, client_id=d["client_id"])
        return ""

    def deal_base_kop(self, did: int) -> tuple[int, str]:
        """База вознаграждения: оплачено клиентом (за вычетом возвратов), без оплат — сумма расчёта."""
        paid = self.s.paid_kop(did)
        if paid > 0:
            return paid, "оплачено"
        _, total = self.s.deal_total(did)
        return total * 100, "по расчёту"

    def rewards(self, designer_id: int | None = None) -> list[dict[str, Any]]:
        sql = ("SELECT d.id, d.stage, d.stage_at, d.designer_id, d.designer_pct, cl.name AS client_name, dz.name AS designer_name,"
               " dz.tax_status FROM deals d JOIN clients cl ON cl.id=d.client_id JOIN clients dz ON dz.id=d.designer_id"
               " WHERE d.designer_id IS NOT NULL AND d.stage!='lost'")
        args: list[Any] = []
        if designer_id:
            sql += " AND d.designer_id=?"
            args.append(designer_id)
        out = []
        for r in self.c().execute(sql + " ORDER BY d.id DESC", args).fetchall():
            base, how = self.deal_base_kop(int(r["id"]))
            out.append({**dict(r), "base": base, "how": how, "reward": round(base * int(r["designer_pct"]) / 100),
                        "accrued": r["stage"] == "shipped"})
        return out

    def designer_summary(self) -> list[dict[str, Any]]:
        rws = self.rewards()
        pays = self.c().execute("SELECT designer_id, COALESCE(SUM(amount_kop),0) s FROM designer_payouts GROUP BY designer_id").fetchall()
        paid = {int(r[0]): int(r[1]) for r in pays}
        out: dict[int, dict[str, Any]] = {}
        for d in self.designers():
            out[int(d["id"])] = {"id": int(d["id"]), "name": d["name"], "tax_status": d["tax_status"], "accrued": 0,
                                 "expected": 0, "paid": paid.get(int(d["id"]), 0), "deals": 0}
        for r in rws:
            x = out.get(int(r["designer_id"]))
            if not x:
                continue
            x["deals"] += 1
            x["accrued" if r["accrued"] else "expected"] += r["reward"]
        res = list(out.values())
        for x in res:
            x["due"] = x["accrued"] - x["paid"]
        return sorted(res, key=lambda x: (-x["due"], -x["expected"], x["name"]))

    def payouts(self, designer_id: int | None = None) -> list[sqlite3.Row]:
        sql = "SELECT p.*, c.name FROM designer_payouts p JOIN clients c ON c.id=p.designer_id"
        args: list[Any] = []
        if designer_id:
            sql += " WHERE p.designer_id=?"
            args.append(designer_id)
        return self.c().execute(sql + " ORDER BY p.paid_at DESC, p.id DESC LIMIT 200", args).fetchall()

    def add_payout(self, designer_id: int, user: str, amount: Any, paid_at: Any, doc: str) -> str:
        d = self.c().execute("SELECT * FROM clients WHERE id=? AND kind='d'", (designer_id,)).fetchone()
        if not d:
            return "нет такого дизайнера"
        if d["tax_status"] not in ("ip", "npd"):
            return "платим только ИП и самозанятым — укажите статус в карточке дизайнера"
        a = kop(amount)
        if not a or a <= 0:
            return "укажите сумму"
        day = iso(paid_at) or today()
        doc = (doc or "").strip()[:200]
        if not doc:
            return ("укажите документ: чек самозанятого (номер из «Мой налог»)" if d["tax_status"] == "npd"
                    else "укажите документ: акт ИП (номер и дата)")
        with self.s.tx() as c:
            c.execute("INSERT INTO designer_payouts(designer_id, amount_kop, paid_at, doc, created_at, created_by) VALUES (?,?,?,?,?,?)",
                      (designer_id, a, day, doc, iso_now(), user))
            self.s.log(c, f"Выплата дизайнеру {kop_in(a)} ₽ ({doc})", user, client_id=designer_id)
        return ""

    def del_payout(self, pid: int, user: str) -> None:
        with self.s.tx() as c:
            r = c.execute("SELECT * FROM designer_payouts WHERE id=?", (pid,)).fetchone()
            if r:
                c.execute("DELETE FROM designer_payouts WHERE id=?", (pid,))
                self.s.log(c, f"Удалена выплата дизайнеру {kop_in(r['amount_kop'])} ₽", user, client_id=r["designer_id"])

    # ---------------------------------------------------------------- деньги для налогов
    def income_year(self, year: int) -> dict[str, int]:
        c = self.c()
        pay = int(c.execute("SELECT COALESCE(SUM(amount-refunded),0) FROM payments WHERE paid_at!='' AND substr(paid_at,1,4)=?",
                            (str(year),)).fetchone()[0])
        free = int(c.execute("SELECT COALESCE(SUM(amount),0) FROM bank_events WHERE deal_id IS NULL AND substr(day,1,4)=?",
                             (str(year),)).fetchone()[0])
        return {"payments": pay, "unlinked": free, "total": pay + free,
                "pct": min(100, int((pay + free) * 100 / VAT_FREE_LIMIT_KOP))}

    def cost_by_quarter(self, year: int) -> list[dict[str, Any]]:
        """Себестоимость проданного (отгруженного) товара по кварталам — расход на товар для УСН «доходы минус расходы»:
        признаётся, когда товар и оплачен поставщику, и продан."""
        out = []
        for q in range(1, 5):
            a, b = f"{year}-{3 * q - 2:02d}-01", f"{year}-{3 * q:02d}-31"
            rows = self.c().execute(
                "SELECT sc.qty, sc.unit_kop, sc.lot_id, p.paid_at FROM sale_costs sc LEFT JOIN lots l ON l.id=sc.lot_id"
                " LEFT JOIN purchases p ON p.id=l.purchase_id WHERE sc.day BETWEEN ? AND ?", (a, b)).fetchall()
            ok = sum(int(r["qty"]) * int(r["unit_kop"]) for r in rows if r["lot_id"] and r["paid_at"] and r["paid_at"] <= b)
            unpaid = sum(int(r["qty"]) * int(r["unit_kop"]) for r in rows if r["lot_id"] and not (r["paid_at"] and r["paid_at"] <= b))
            nolot = sum(int(r["qty"]) for r in rows if not r["lot_id"])
            out.append({"q": q, "pcs": sum(int(r["qty"]) for r in rows), "cost": ok, "unpaid": unpaid, "nolot": nolot})
        return out

    def sales_csv(self, year: int) -> str:
        rows = self.c().execute(
            "SELECT sc.day, sc.deal_id, sc.article, sc.qty, sc.unit_kop, sc.lot_id, p.num, p.paid_at, cl.name"
            " FROM sale_costs sc LEFT JOIN lots l ON l.id=sc.lot_id LEFT JOIN purchases p ON p.id=l.purchase_id"
            " LEFT JOIN deals d ON d.id=sc.deal_id LEFT JOIN clients cl ON cl.id=d.client_id"
            " WHERE substr(sc.day,1,4)=? ORDER BY sc.day, sc.id", (str(year),)).fetchall()
        lines = ["Дата отгрузки;Заявка;Покупатель;Артикул;Кол-во;Себестоимость шт, ₽;Сумма, ₽;Спецификация;Оплачено поставщику"]
        for r in rows:
            nm = (r["name"] or "").replace(";", ",")
            lines.append(";".join([dmy(r["day"]), str(r["deal_id"]), nm, r["article"], str(r["qty"]), kop_in(r["unit_kop"]),
                                   kop_in(int(r["qty"]) * int(r["unit_kop"])), (r["num"] or "без партии"), dmy(r["paid_at"] or "")]))
        return "﻿" + "\r\n".join(lines) + "\r\n"

    # ---------------------------------------------------------------- налоговый календарь
    def reg_date(self) -> date | None:
        v = iso(self.s.setting("ip_reg_date", "2026-11-02"))
        return date.fromisoformat(v) if v else None

    def done_keys(self) -> dict[str, str]:
        return {r[0]: r[1] for r in self.c().execute("SELECT key, done_at FROM tax_done").fetchall()}

    def set_done(self, key: str, done: bool, user: str) -> None:
        key = (key or "").strip()[:80]
        if not re.fullmatch(r"[a-z0-9-]+", key):
            return
        with self.s.tx() as c:
            if done:
                c.execute("INSERT OR REPLACE INTO tax_done(key, done_at, by_user) VALUES (?,?,?)", (key, iso_now(), user))
            else:
                c.execute("DELETE FROM tax_done WHERE key=?", (key,))
            self.s.log(c, f"Налоговый календарь: {key} — {'сделано' if done else 'не сделано'}", user)

    def calendar(self, day: str | None = None, horizon_days: int = 400) -> list[dict[str, Any]]:
        """Сроки на ближайший год + всё просроченное и не отмеченное. Каждый пункт: key, due, title, how, kind, url, done."""
        t = date.fromisoformat(day or today())
        reg = self.reg_date()
        done = self.done_keys()
        items: list[dict[str, Any]] = []

        def add(key: str, due: date | None, title: str, how: str, kind: str = "tax", url: str = "/taxes",
                amount: int | None = None, is_done: bool | None = None) -> None:
            items.append({"key": key, "due": due.isoformat() if due else "", "title": title, "how": how, "kind": kind,
                          "url": url, "amount": amount, "done": (key in done) if is_done is None else is_done,
                          "exact": bool(due) and calendar_known(due.year)})

        y0 = reg.year if reg else t.year
        for y in range(y0, t.year + 2):
            # взносы за год
            amt = contrib_for_year(y, reg)
            add(f"vznosy-{y}", shift_to_workday(date(y, 12, 28)), f"Фиксированные взносы ИП за {y} год",
                "оплата в Точке: «Налоги» → взносы ИП за себя (на ЕНП); можно частями в течение года", amount=amt)
            add(f"vznosy1-{y}", shift_to_workday(date(y + 1, 7, 1)), f"Взнос 1 % с дохода свыше 300 000 ₽ за {y} год",
                "на УСН «доходы минус расходы» база — доходы минус расходы; если меньше 300 000 ₽ — платить не нужно")
            for q, (mon, label) in enumerate(((4, "I квартал"), (7, "полугодие"), (10, "9 месяцев")), start=1):
                end = date(y, 3 * q, 30 if q in (2, 3) else 31)
                if reg and end < reg:
                    continue
                add(f"usn-avans-{y}-{q}-u", shift_to_workday(date(y, mon, 25)), f"Уведомление об авансе УСН за {label} {y}",
                    "через Saby; если аванс 0 ₽ (расходы не меньше доходов) — уведомление не подаётся")
                add(f"usn-avans-{y}-{q}-p", shift_to_workday(date(y, mon, 28)), f"Аванс по УСН за {label} {y}",
                    "оплата на ЕНП из Точки")
            add(f"usn-decl-{y}", shift_to_workday(date(y + 1, 4, 25)), f"Декларация по УСН за {y} год",
                "через Saby; минимальный налог — 1 % от доходов, если он больше налога")
            add(f"usn-tax-{y}", shift_to_workday(date(y + 1, 4, 28)), f"Налог по УСН за {y} год", "оплата на ЕНП из Точки")

        for p in self.purchases():
            n, url = p["num"] or str(p["id"]), f"/purchases/{p['id']}"
            if self.dopp_needed(p) and (p["paid_at"] or p["border_date"] or p["ship_date"]):
                due = date.fromisoformat(p["border_date"]) - timedelta(days=2) if p["border_date"] else None
                add(f"p{p['id']}-dopp", due, f"ДОПП и обеспечительный платёж — закупка № {n}",
                    "через Saby; без статуса «Обеспечен» и QR-кода груз на границе развернут"
                    + ("" if due else " · впишите в закупке дату ввоза"), "import", url,
                    amount=self.guarantee_kop(p), is_done=p["dopp_status"] == "secured" and bool(p["guarantee_paid_at"]))
            if p["received_at"]:
                y, m = next_month(date.fromisoformat(p["received_at"]))
                add(f"p{p['id']}-decl", shift_to_workday(date(y, m, 20)),
                    f"Декларация по косвенным налогам + заявление о ввозе, НДС — закупка № {n}",
                    "через Saby; НДС при ввозе — с зачётом обеспечительного платежа", "import", url,
                    amount=self.vat_kop(p), is_done=bool(p["decl_at"] and p["vat_paid_at"]))
            base = p["import_date"] or p["received_at"]
            if base:
                y, m = next_month(date.fromisoformat(base))
                add(f"p{p['id']}-stat", nth_workday(y, m, 10), f"Статформа в таможню — закупка № {n}",
                    "личный кабинет участника ВЭД на сайте ФТС, с подписью ИП", "import", url, is_done=bool(p["statform_at"]))
            if p["decl_at"]:
                due = date.fromisoformat(p["decl_at"]) + timedelta(days=15)
                if p["ship_date"]:
                    due = min(due, date.fromisoformat(p["ship_date"]) + timedelta(days=170))
                add(f"p{p['id']}-sup", due, f"Заявление о ввозе с отметкой — поставщику, закупка № {n}",
                    "налоговая ставит отметку в течение 10 рабочих дней; поставщику — для подтверждения НДС 0 % (180 дней с отгрузки)",
                    "import", url, is_done=bool(p["decl_mark_at"] and p["supplier_sent_at"]))

        lim = (t + timedelta(days=horizon_days)).isoformat()
        out = [x for x in items if not x["done"] and (not x["due"] or x["due"] <= lim)]
        out += [x for x in items if x["done"] and x["due"] and x["due"] >= (t - timedelta(days=60)).isoformat()]
        out.sort(key=lambda x: (x["done"], x["due"] or "9999", x["title"]))
        return out

    def upcoming(self, days: int = 7, day: str | None = None) -> list[dict[str, Any]]:
        t = date.fromisoformat(day or today())
        lim = (t + timedelta(days=days)).isoformat()
        return [x for x in self.calendar(day) if not x["done"] and (not x["due"] or x["due"] <= lim)
                and (x["due"] or x["kind"] == "import")]

"""Счета на оплату компаниям и ИП (10.11.2026): номер «заявка/порядковый», PDF с реквизитами ИП и QR-кодом для оплаты
по ГОСТ Р 56042-2014, письмо с PDF, автоматическая привязка поступления на счёт к счёту и заявке.

Реквизиты продавца в код не пишем (репозиторий открытый) — их вводят в CRM: Настройки → «Реквизиты для счетов».
Счёт на оплату — не первичный документ; НДС не облагается (продавец на УСН).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date
from decimal import Decimal
from typing import Any

from store import Store, iso_now, today

SELLER_FIELDS = ("inv_name", "inv_short", "inv_inn", "inv_ogrn", "inv_account", "inv_bank", "inv_bik", "inv_corr", "inv_city",
                 "inv_signer", "inv_days")
SELLER_DEFAULTS = {"inv_bank": "ООО «Банк Точка»", "inv_bik": "044525104", "inv_corr": "30101810745374525104",
                   "inv_city": "г. Санкт-Петербург", "inv_days": "3"}
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF"]


# ------------------------------------------------------------------ проверки реквизитов
def _key_ok(digits23: str) -> bool:
    w = [7, 1, 3] * 8
    return sum((int(d) * w[i]) % 10 for i, d in enumerate(digits23)) % 10 == 0


def account_ok(account: str, bik: str) -> bool:
    """Контрольный ключ расчётного счёта по БИК (3 последние цифры БИК + 20 цифр счёта)."""
    return bool(re.fullmatch(r"\d{20}", account or "")) and bool(re.fullmatch(r"\d{9}", bik or "")) and _key_ok(bik[-3:] + account)


def corr_ok(corr: str, bik: str) -> bool:
    """Контрольный ключ корреспондентского счёта: «0» + 5–6 цифры БИК + 20 цифр корсчёта."""
    return bool(re.fullmatch(r"\d{20}", corr or "")) and bool(re.fullmatch(r"\d{9}", bik or "")) and _key_ok("0" + bik[4:6] + corr)


def inn_ok(inn: str) -> bool:
    d = [int(x) for x in re.sub(r"\D", "", inn or "")]

    def chk(ws: list[int], n: int) -> int:
        return sum(a * b for a, b in zip(ws, d[:n])) % 11 % 10
    if len(d) == 10:
        return chk([2, 4, 10, 3, 5, 9, 4, 6, 8], 9) == d[9]
    if len(d) == 12:
        return (chk([7, 2, 4, 10, 3, 5, 9, 4, 6, 8], 10) == d[10]
                and chk([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8], 11) == d[11])
    return False


# ------------------------------------------------------------------ сумма прописью
_U = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_UF = ["", "одна", "две"] + _U[3:]
_T = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать",
      "восемнадцать", "девятнадцать"]
_D = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_H = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def plural(n: int, forms: tuple[str, str, str]) -> str:
    n = abs(n) % 100
    if 11 <= n <= 19:
        return forms[2]
    return forms[0] if n % 10 == 1 else forms[1] if 2 <= n % 10 <= 4 else forms[2]


def _triad(n: int, female: bool) -> list[str]:
    out = [_H[n // 100]]
    t = n % 100
    if 10 <= t <= 19:
        out.append(_T[t - 10])
    else:
        out += [_D[t // 10], (_UF if female else _U)[t % 10]]
    return [w for w in out if w]


def num_words(n: int, female: bool = False) -> str:
    if n == 0:
        return "ноль"
    groups = [((1_000_000_000, ("миллиард", "миллиарда", "миллиардов")), False), ((1_000_000, ("миллион", "миллиона", "миллионов")), False),
              ((1000, ("тысяча", "тысячи", "тысяч")), True)]
    words: list[str] = []
    for (div, forms), fem in groups:
        g = n // div % 1000
        if g:
            words += _triad(g, fem) + [plural(g, forms)]
    words += _triad(n % 1000, female)
    return " ".join(words)


def amount_words(kop: int) -> str:
    r, k = divmod(int(kop), 100)
    s = f"{num_words(r)} {plural(r, ('рубль', 'рубля', 'рублей'))} {k:02d} {plural(k, ('копейка', 'копейки', 'копеек'))}"
    return s[:1].upper() + s[1:]


def rub_s(kop: int) -> str:
    r, k = divmod(abs(int(kop)), 100)
    return ("−" if kop < 0 else "") + f"{r:,}".replace(",", " ") + f",{k:02d}"


def day_words(d: str) -> str:
    x = date.fromisoformat(d[:10])
    return f"{x.day} {MONTHS_GEN[x.month - 1]} {x.year} г."


# ------------------------------------------------------------------ счета
class Invoices:
    def __init__(self, store: Store) -> None:
        self.s = store

    def seller(self) -> dict[str, str]:
        return {k: self.s.setting(k, SELLER_DEFAULTS.get(k, "")) for k in SELLER_FIELDS}

    def seller_problems(self, sl: dict[str, str] | None = None) -> list[str]:
        sl = sl or self.seller()
        p = []
        if not sl["inv_name"]:
            p.append("наименование продавца")
        if not inn_ok(sl["inv_inn"]):
            p.append("ИНН")
        if not account_ok(sl["inv_account"], sl["inv_bik"]):
            p.append("расчётный счёт (20 цифр, проверка по БИК)")
        if not corr_ok(sl["inv_corr"], sl["inv_bik"]):
            p.append("корреспондентский счёт и БИК")
        return p

    def save_seller(self, form: dict[str, Any], user: str) -> list[str]:
        vals = {}
        for k in SELLER_FIELDS:
            v = str(form.get(k, "") or "").strip()[:300]
            if k in ("inv_inn", "inv_ogrn", "inv_account", "inv_bik", "inv_corr", "inv_days"):
                v = re.sub(r"\D", "", v)
            vals[k] = v
        if not vals["inv_days"] or not (1 <= int(vals["inv_days"]) <= 30):
            vals["inv_days"] = "3"
        for k, v in vals.items():
            self.s.set_setting(k, v)
        c = self.s.c()
        self.s.log(c, "Реквизиты для счетов сохранены", user)
        c.commit()
        return self.seller_problems(vals)

    def for_deal(self, did: int) -> list[sqlite3.Row]:
        return self.s.c().execute("SELECT * FROM invoices WHERE deal_id=? ORDER BY id DESC", (did,)).fetchall()

    def get(self, iid: int) -> sqlite3.Row | None:
        return self.s.c().execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()

    def open_list(self) -> list[sqlite3.Row]:
        return self.s.c().execute("SELECT i.*, cl.name AS client_name FROM invoices i JOIN deals d ON d.id=i.deal_id"
                                  " JOIN clients cl ON cl.id=d.client_id WHERE i.status='issued' ORDER BY i.id DESC").fetchall()

    @staticmethod
    def number(inv: Any) -> str:
        return f"{inv['deal_id']}/{inv['n']}"

    @staticmethod
    def purpose(inv: Any) -> str:
        return f"Оплата по счёту № {inv['deal_id']}/{inv['n']} от {inv['day'][8:10]}.{inv['day'][5:7]}.{inv['day'][:4]}. Без НДС"

    def create(self, did: int, user: str, pct: Any = 100, delivery: Any = "") -> tuple[int | None, str]:
        d = self.s.deal(did)
        if not d:
            return None, "нет такой заявки"
        probs = self.seller_problems()
        if probs:
            return None, "сначала заполните в Настройках «Реквизиты для счетов»: " + ", ".join(probs)
        lines = self.s.lines(did)
        if not lines:
            return None, "в расчёте нет позиций"
        try:
            pct_i = max(1, min(int(str(pct or 100).strip()), 100))
        except ValueError:
            pct_i = 100
        disc = max(0, min(int(d["discount"] or 0), 90))
        items = []
        for ln in lines:
            p = self.s.catalog.get(ln["article"])
            name = p.name if p and ln["article"] in p.name else (f"{p.name}, арт. {ln['article']}" if p else ln["article"])
            unit = int((Decimal(int(ln["price"]) * 100) * (100 - disc) / 100).quantize(Decimal("1")))
            items.append({"name": name, "qty": int(ln["qty"]), "unit": "шт", "price": unit, "sum": unit * int(ln["qty"])})
        dkop = 0
        if str(delivery or "").strip():
            from buh import kop
            dkop = max(kop(delivery) or 0, 0)
            if dkop:
                items.append({"name": "Доставка заказа", "qty": 1, "unit": "усл.", "price": dkop, "sum": dkop})
        total = sum(x["sum"] for x in items)
        amount = total if pct_i == 100 else int((Decimal(total) * pct_i / 100).quantize(Decimal("1")))
        buyer = {"name": d["full_name"] or d["company"] or d["client_name"], "inn": d["inn"] or "", "kpp": d["kpp"] or "",
                 "address": d["legal_address"] or "", "kind": d["kind"]}
        sl = self.seller()
        with self.s.tx() as c:
            n = int(c.execute("SELECT COALESCE(MAX(n),0)+1 FROM invoices WHERE deal_id=?", (did,)).fetchone()[0])
            cur = c.execute("INSERT INTO invoices(deal_id, n, day, pct, total, amount, items, buyer, seller, status, created_at, created_by)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (did, n, today(), pct_i, total, amount, json.dumps(items, ensure_ascii=False),
                             json.dumps(buyer, ensure_ascii=False), json.dumps(sl, ensure_ascii=False), "issued", iso_now(), user))
            iid = int(cur.lastrowid)
            self.s.log(c, f"Выставлен счёт № {did}/{n} на {rub_s(amount)} ₽" + (f" (предоплата {pct_i} %)" if pct_i < 100 else ""),
                       user, deal_id=did, client_id=d["client_id"])
        return iid, ""

    def cancel(self, iid: int, user: str) -> str:
        inv = self.get(iid)
        if not inv or inv["status"] != "issued":
            return "счёт уже оплачен или отменён"
        with self.s.tx() as c:
            c.execute("UPDATE invoices SET status='cancelled' WHERE id=?", (iid,))
            self.s.log(c, f"Счёт № {self.number(inv)} отменён", user, deal_id=inv["deal_id"])
        return ""

    def mark_paid(self, iid: int, user: str, payment_id: int | None = None) -> None:
        with self.s.tx() as c:
            c.execute("UPDATE invoices SET status='paid', paid_at=?, payment_id=? WHERE id=? AND status='issued'",
                      (iso_now(), payment_id, iid))

    def settle(self, did: int, amount_kop: int, payment_id: int | None, user: str) -> str:
        """Оплата по заявке пришла другим путём (привязали вручную, отметили руками) — закрыть счёт с той же суммой."""
        rows = self.s.c().execute("SELECT * FROM invoices WHERE deal_id=? AND status='issued' AND amount=? ORDER BY id",
                                  (did, int(amount_kop))).fetchall()
        if not rows:
            return ""
        self.mark_paid(int(rows[0]["id"]), user, payment_id)
        return self.number(rows[0])

    def match(self, inn: str, purpose: str, amount_kop: int) -> int | None:
        """Какой наш счёт оплачен: номер «№ 15/1» в назначении (сумма или ИНН совпадают) или ИНН + точная сумма."""
        inn = re.sub(r"\D", "", inn or "")
        m = re.search(r"сч[её]т\w*\D{0,10}(\d{1,7})\s*/\s*(\d{1,3})", purpose or "", flags=re.I)
        if m:
            inv = self.s.c().execute("SELECT * FROM invoices WHERE deal_id=? AND n=? AND status='issued'",
                                     (int(m.group(1)), int(m.group(2)))).fetchone()
            if inv and (int(inv["amount"]) == int(amount_kop) or (inn and json.loads(inv["buyer"]).get("inn") == inn)):
                return int(inv["id"])
        if len(inn) in (10, 12):
            rows = [r for r in self.s.c().execute("SELECT * FROM invoices WHERE status='issued' AND amount=?", (int(amount_kop),)).fetchall()
                    if json.loads(r["buyer"]).get("inn") == inn]
            if len(rows) == 1:
                return int(rows[0]["id"])
        return None

    def qr_text(self, inv: Any) -> str:
        sl = json.loads(inv["seller"])

        def clean(s: str) -> str:
            return str(s).replace("|", " ").strip()
        return "|".join(["ST00012", f"Name={clean(sl['inv_name'])}", f"PersonalAcc={sl['inv_account']}",
                         f"BankName={clean(sl['inv_bank'])}", f"BIC={sl['inv_bik']}", f"CorrespAcc={sl['inv_corr']}",
                         f"PayeeINN={sl['inv_inn']}", f"Sum={int(inv['amount'])}", f"Purpose={clean(self.purpose(inv))}"])

    # ---------------------------------------------------------------- PDF
    def pdf(self, inv: Any) -> bytes:
        try:
            from reportlab.graphics.barcode.qr import QrCodeWidget
            from reportlab.graphics.shapes import Drawing
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            raise RuntimeError("на сервере нет программы для PDF (python3-reportlab) — нажмите «Обновить CRM»") from None
        font = next((d for d in FONT_DIRS if os.path.exists(os.path.join(d, "DejaVuSans.ttf"))), "")
        if not font:
            raise RuntimeError("на сервере нет шрифта DejaVu (fonts-dejavu-core) — нажмите «Обновить CRM»")
        if "ND" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ND", os.path.join(font, "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("NDB", os.path.join(font, "DejaVuSans-Bold.ttf")))
        sl, buyer, items = json.loads(inv["seller"]), json.loads(inv["buyer"]), json.loads(inv["items"])
        st = ParagraphStyle("n", fontName="ND", fontSize=9, leading=11.5)
        sm = ParagraphStyle("s", parent=st, fontSize=8, leading=10, textColor=colors.HexColor("#444444"))
        b = ParagraphStyle("b", parent=st, fontName="NDB")
        h = ParagraphStyle("h", parent=st, fontName="NDB", fontSize=14, leading=18)
        r = ParagraphStyle("r", parent=st, alignment=2)
        rb = ParagraphStyle("rb", parent=b, alignment=2)

        def esc(s: Any) -> str:
            return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        line = colors.HexColor("#333333")
        bank = Table([
            [Paragraph(esc(sl["inv_bank"]), st), Paragraph("БИК", st), Paragraph(sl["inv_bik"], st)],
            [Paragraph("Банк получателя", sm), Paragraph("Сч. №", st), Paragraph(sl["inv_corr"], st)],
            [Paragraph(f"ИНН {sl['inv_inn']}", st), Paragraph("Сч. №", st), Paragraph(sl["inv_account"], st)],
            [Paragraph(esc(sl["inv_name"]), st), "", ""],
            [Paragraph("Получатель", sm), "", ""],
        ], colWidths=[105 * mm, 15 * mm, 60 * mm])
        bank.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, line), ("SPAN", (1, 2), (1, 4)), ("SPAN", (2, 2), (2, 4)),
                                  ("LINEBELOW", (0, 0), (0, 0), 0, colors.white), ("LINEBELOW", (0, 3), (0, 3), 0, colors.white),
                                  ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        seller_line = esc(sl["inv_name"]) + f", ИНН {sl['inv_inn']}" + (f", ОГРНИП {sl['inv_ogrn']}" if sl.get("inv_ogrn") else "") \
            + (f", {esc(sl['inv_city'])}" if sl.get("inv_city") else "")
        buyer_line = esc(buyer["name"]) + (f", ИНН {buyer['inn']}" if buyer.get("inn") else "") \
            + (f", КПП {buyer['kpp']}" if buyer.get("kpp") else "") + (f", {esc(buyer['address'])}" if buyer.get("address") else "")
        parties = Table([[Paragraph("Поставщик:", st), Paragraph(seller_line, b)],
                         [Paragraph("Покупатель:", st), Paragraph(buyer_line, b)],
                         [Paragraph("Основание:", st), Paragraph(f"Заказ № {inv['deal_id']}", st)]], colWidths=[25 * mm, 155 * mm])
        parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        rows = [[Paragraph(x, b) for x in ("№", "Товар", "Кол-во", "Ед.", "Цена", "Сумма")]]
        for i, x in enumerate(items, 1):
            rows.append([Paragraph(str(i), st), Paragraph(esc(x["name"]), st), Paragraph(str(x["qty"]), r), Paragraph(x["unit"], st),
                         Paragraph(rub_s(x["price"]), r), Paragraph(rub_s(x["sum"]), r)])
        tbl = Table(rows, colWidths=[9 * mm, 88 * mm, 20 * mm, 12 * mm, 25 * mm, 26 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, line), ("BOX", (0, 0), (-1, -1), 1, line),
                                 ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        tot = [["", Paragraph("Итого:", rb), Paragraph(rub_s(inv["total"]), rb)],
               ["", Paragraph("Без налога (НДС):", rb), Paragraph("—", rb)]]
        if int(inv["pct"]) < 100:
            tot.append(["", Paragraph(f"К оплате — предоплата {inv['pct']} %:", rb), Paragraph(rub_s(inv["amount"]), rb)])
        else:
            tot.append(["", Paragraph("Всего к оплате:", rb), Paragraph(rub_s(inv["amount"]), rb)])
        tots = Table(tot, colWidths=[90 * mm, 64 * mm, 26 * mm])
        tots.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (2, 0), (2, -1), 6)]))
        words = f"Всего наименований {len(items)}, на сумму {rub_s(inv['total'])} руб."
        if int(inv["pct"]) < 100:
            words += f" К оплате (предоплата {inv['pct']} %): {rub_s(inv['amount'])} руб."
        terms = (f"Оплатить в течение {sl.get('inv_days') or 3} банковских дней. В назначении платежа укажите: «{esc(self.purpose(inv))}». "
                 "Товар отпускается после поступления денег на расчётный счёт. НДС не облагается: продавец применяет "
                 "упрощённую систему налогообложения.")
        qr = QrCodeWidget(self.qr_text(inv))
        bx = qr.getBounds()
        size = 34 * mm
        dr = Drawing(size, size, transform=[size / (bx[2] - bx[0]), 0, 0, size / (bx[3] - bx[1]), 0, 0])
        dr.add(qr)
        signer = esc(sl.get("inv_signer") or "")
        sign = Table([[Paragraph("Индивидуальный предприниматель", st), Paragraph("_________________________", st),
                       Paragraph(signer, st)]], colWidths=[68 * mm, 52 * mm, 60 * mm])
        sign.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
        bottom = Table([[dr, Paragraph("QR-код для оплаты: отсканируйте в приложении банка — реквизиты, сумма и назначение "
                                       "платежа заполнятся сами.", sm)]], colWidths=[38 * mm, 142 * mm])
        bottom.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story = [bank, Spacer(1, 7 * mm), Paragraph(f"Счёт на оплату № {self.number(inv)} от {day_words(inv['day'])}", h),
                 Table([[""]], colWidths=[180 * mm], style=[("LINEABOVE", (0, 0), (-1, -1), 1.5, line)]),
                 Spacer(1, 2 * mm), parties, Spacer(1, 4 * mm), tbl, Spacer(1, 2 * mm), tots, Spacer(1, 3 * mm),
                 Paragraph(words, st), Paragraph(amount_words(int(inv["amount"])), b), Spacer(1, 3 * mm),
                 Paragraph(terms, sm), Spacer(1, 2 * mm),
                 Table([[""]], colWidths=[180 * mm], style=[("LINEABOVE", (0, 0), (-1, -1), 1.5, line)]), Spacer(1, 8 * mm),
                 sign, Spacer(1, 10 * mm), bottom]
        import io
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                                title=f"Счёт № {self.number(inv)}", author=sl.get("inv_name", ""))
        doc.build(story)
        return buf.getvalue()

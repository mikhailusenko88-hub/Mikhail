"""Точка Банк для CRM «Наш декор»: ссылки на оплату с чеком (интернет-эквайринг + «Чеки» или облачная касса),
статус оплаты, возврат, вебхуки об оплате.

API: https://enter.tochka.com/uapi (схема Tochka.API 1.90). Вход — JWT-ключ из интернет-банка
(«Интеграции и API» → «Сгенерировать JWT-ключ»), заголовок Authorization: Bearer.
Ключ хранится только в базе CRM на сервере (settings.tochka_jwt), в журнал и на страницы не выводится.

Что важно знать про банк (проверено по схеме и по чужим рабочим интеграциям):
- Сумма — в рублях (число), не в копейках. Позиции чека: amount — цена за штуку, quantity — количество.
- Признак расчёта в чеке по ссылке — только «Полный расчёт» (full_payment) или «Предоплата 100%» (full_prepayment).
  Чека на частичную предоплату и второго чека («полный расчёт» с зачётом аванса) через API нет.
- paymentLinkId — наш номер, должен быть новым для каждой ссылки (повтор → 424 «заказ существует»).
- Вебхук — «голый» JWT (RS256), подписанный банком. Банк шлёт вебхук только об успешной оплате;
  отказы, истечение и возвраты узнаются опросом (manage.py tochka-poll). Сумму и статус берём только из ответа
  GET /payments/{operationId} по нашему ключу — тело вебхука лишь подсказка, поэтому подделка ничего не даст.
- Регистрация вебхука: банк сразу шлёт тестовые вебхуки (с чужим customerCode) — им нужно ответить 200.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Callable

log = logging.getLogger("crm.tochka")

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    HAVE_CRYPTO = True
except Exception:  # noqa: BLE001 — без cryptography подпись не проверяется, но оплата всё равно сверяется с банком
    HAVE_CRYPTO = False

API = "https://enter.tochka.com/uapi"
KEY_URL = "https://enter.tochka.com/doc/openapi/static/keys/public"   # открытый ключ банка для подписи вебхуков
WEBHOOK_TYPES = ["acquiringInternetPayment", "incomingPayment"]
FINAL = ("APPROVED", "REFUNDED", "REFUNDED_PARTIALLY", "EXPIRED")
STATUS_NAMES = {
    "CREATED": "ждёт оплаты", "APPROVED": "оплачено", "AUTHORIZED": "деньги заблокированы",
    "ON-REFUND": "идёт возврат", "REFUNDED": "возвращено", "REFUNDED_PARTIALLY": "частичный возврат",
    "EXPIRED": "ссылка истекла", "WAIT_FULL_PAYMENT": "ждёт полной оплаты", "ERROR": "ошибка",
}
PAY_TYPES = {"card": "картой", "sbp": "через СБП", "tinkoff": "через T-Pay", "dolyame": "Долями"}
TAX_SYSTEMS = [("usn_income_outcome", "УСН «доходы минус расходы»"), ("usn_income", "УСН «доходы»"),
               ("osn", "ОСН"), ("patent", "Патент")]

Http = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]

# У Точки сертификат от Минцифры (Russian Trusted Root CA) — его нет в системных хранилищах. Доверяем ему
# только в запросах к Точке: системные корни + russian_trusted_ca.pem рядом с этим файлом.
CA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "russian_trusted_ca.pem")


def ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if os.path.exists(CA_FILE):
        ctx.load_verify_locations(cafile=CA_FILE)
    return ctx


_SSL: ssl.SSLContext | None = None


def b64u_dec(s: str) -> bytes:
    s = s.strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jwt_claims(token: str) -> dict[str, Any]:
    """Полезная нагрузка JWT без проверки подписи (для ключа из интернет-банка — срок и client_id)."""
    try:
        return json.loads(b64u_dec(token.split(".")[1]))
    except Exception:  # noqa: BLE001
        return {}


def verify_rs256(token: str, jwk: dict[str, Any]) -> dict[str, Any]:
    """Проверить подпись RS256 открытым ключом банка (JWK: n, e). Возвращает claims или бросает ValueError."""
    if not HAVE_CRYPTO:
        raise ValueError("нет модуля cryptography")
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("не JWT")
    header = json.loads(b64u_dec(parts[0]))
    if header.get("alg") != "RS256":
        raise ValueError("алгоритм не RS256")
    n = int.from_bytes(b64u_dec(jwk["n"]), "big")
    e = int.from_bytes(b64u_dec(jwk["e"]), "big")
    if n.bit_length() < 2048:
        raise ValueError("ключ банка короче 2048 бит")
    pub = rsa.RSAPublicNumbers(e, n).public_key()
    try:
        pub.verify(b64u_dec(parts[2]), (parts[0] + "." + parts[1]).encode(), padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as ex:
        raise ValueError("подпись не совпадает с ключом банка") from ex
    return json.loads(b64u_dec(parts[1]))


def parse_jwk(text: str) -> list[dict[str, Any]]:
    """Ключ банка: один JWK, массив JWK или набор {"keys": [...]}; только RSA."""
    d = json.loads(text)
    keys = d.get("keys") if isinstance(d, dict) and "keys" in d else (d if isinstance(d, list) else [d])
    out = [k for k in keys if isinstance(k, dict) and k.get("kty") == "RSA" and k.get("n") and k.get("e")]
    if not out:
        raise ValueError("в ответе нет RSA-ключа")
    return out


def http_request(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    global _SSL
    if not url.startswith("https://enter.tochka.com/"):        # ключ доверия Минцифры — только для Точки
        raise ValueError("запросы только к enter.tochka.com")
    if _SSL is None:
        _SSL = ssl_context()
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25, context=_SSL) as r:
            return r.status, r.read(2_000_000)
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(200_000)
        except Exception:  # noqa: BLE001
            return e.code, b""
    except Exception as e:  # noqa: BLE001 — сеть, DNS, таймаут, сертификат
        log.warning("Точка не ответила: %s %s", type(e).__name__, str(e)[:120])
        return 0, b""


class TochkaError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status} {message}".strip())
        self.status = status
        self.message = message

    def human(self) -> str:
        if self.status == 0:
            return "банк не ответил (нет связи) — попробуйте через минуту"
        if self.status == 401:
            return "банк не принял ключ — он неверный или истёк; выпустите новый JWT-ключ в интернет-банке"
        if self.status == 403:
            return "у ключа нет нужного разрешения — выпустите ключ с разрешениями из инструкции (" + self.message[:120] + ")"
        if self.status == 424 and "сущ" in self.message.lower():
            return "такой номер ссылки уже был — нажмите ещё раз"
        if self.status in (404, 424):
            return "банк не нашёл операцию или торговую точку (" + self.message[:160] + ")"
        return f"банк ответил ошибкой {self.status}: {self.message[:200]}"


class Tochka:
    def __init__(self, token: str, customer_code: str = "", merchant_id: str = "", base: str = API,
                 http: Http | None = None) -> None:
        self.token = token.strip()
        self.customer = customer_code.strip()
        self.merchant = merchant_id.strip()
        self.base = base.rstrip("/")
        self.http: Http = http or http_request

    # ------------------------------------------------------------ транспорт
    def call(self, method: str, path: str, data: Any = None) -> Any:
        body = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        status, raw = self.http(method, self.base + path, headers, body)
        try:
            ans = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:  # noqa: BLE001
            ans = {}
        if not 200 <= status < 300:
            msg = ""
            if isinstance(ans, dict):
                errs = ans.get("Errors") or ans.get("errors") or []
                if isinstance(errs, list) and errs and isinstance(errs[0], dict):
                    msg = str(errs[0].get("message") or errs[0].get("errorCode") or "")
                msg = msg or str(ans.get("message") or ans.get("detail") or "")
            if not msg and raw:
                msg = raw[:200].decode("utf-8", "replace")
            raise TochkaError(status, msg)
        return ans

    # ------------------------------------------------------------ кто мы
    def client_id(self) -> str:
        c = jwt_claims(self.token)
        return str(c.get("client_id") or c.get("iss") or "")

    def expires(self) -> int:
        try:
            return int(jwt_claims(self.token).get("exp") or 0)
        except (TypeError, ValueError):
            return 0

    def customers(self) -> list[dict[str, Any]]:
        a = self.call("GET", "/open-banking/v1.0/customers")
        return list(((a.get("Data") or {}).get("Customer")) or [])

    def retailers(self, customer_code: str = "") -> list[dict[str, Any]]:
        code = customer_code or self.customer
        a = self.call("GET", "/acquiring/v1.0/retailers?customerCode=" + urllib.request.quote(code))
        return list(((a.get("Data") or {}).get("Retailer")) or [])

    # ------------------------------------------------------------ ссылки на оплату
    def create_link(self, data: dict[str, Any]) -> dict[str, Any]:
        """POST /acquiring/v1.0/payments_with_receipt — ссылка и чек по 54-ФЗ. Возвращает Data (operationId, paymentLink, status)."""
        d = dict(data)
        d.setdefault("customerCode", self.customer)
        if self.merchant:
            d.setdefault("merchantId", self.merchant)
        a = self.call("POST", "/acquiring/v1.0/payments_with_receipt", {"Data": d})
        out = a.get("Data") or {}
        if isinstance(out.get("Operation"), list) and out["Operation"]:   # на случай обёртки Operation[]
            out = out["Operation"][0]
        if not out.get("operationId") or not out.get("paymentLink"):
            raise TochkaError(200, "банк не вернул ссылку")
        return out

    def payment(self, operation_id: str) -> dict[str, Any] | None:
        """GET /acquiring/v1.0/payments/{operationId} → операция (status, amount, paymentType, paidAt, Order[]); None — не найдена."""
        try:
            a = self.call("GET", "/acquiring/v1.0/payments/" + urllib.request.quote(operation_id, safe=""))
        except TochkaError as e:
            if e.status in (404, 424) and "not found" in e.message.lower():
                return None
            raise
        ops = ((a.get("Data") or {}).get("Operation")) or []
        return ops[0] if ops else None

    def refund(self, operation_id: str, amount: float) -> dict[str, Any]:
        a = self.call("POST", "/acquiring/v1.0/payments/" + urllib.request.quote(operation_id, safe="") + "/refund",
                      {"Data": {"amount": round(float(amount), 2)}})
        return a.get("Data") or {}

    # ------------------------------------------------------------ вебхуки
    def get_webhook(self, client_id: str) -> dict[str, Any] | None:
        try:
            a = self.call("GET", "/webhook/v1.0/" + urllib.request.quote(client_id, safe=""))
        except TochkaError as e:
            if e.status in (404, 424):
                return None
            raise
        return a.get("Data") or None

    def set_webhook(self, client_id: str, url: str, types: list[str] | None = None) -> dict[str, Any]:
        """Создать (PUT) или изменить (POST) вебхук. Банк сразу шлёт тестовые вебхуки — CRM должна ответить 200."""
        if not url.startswith("https://"):
            raise TochkaError(400, "адрес вебхука должен быть https")
        body = {"webhooksList": types or WEBHOOK_TYPES, "url": url}
        path = "/webhook/v1.0/" + urllib.request.quote(client_id, safe="")
        cur = self.get_webhook(client_id)
        a = self.call("POST" if cur else "PUT", path, body)
        return a.get("Data") or body


def receipt_items(lines: list[tuple[str, int, int]], discount: int, delivery: int = 0,
                  method: str = "full_prepayment", goods_total: int | None = None) -> tuple[list[dict[str, Any]], int]:
    """Позиции чека из расчёта: (название, шт, цена ₽ без скидки) + скидка %, доставка ₽.
    Возвращает (Items, сумма в копейках). Строка = шт × цена × (100 − скидка) копеек; разница с «Итого» CRM
    (goods_total, ₽ — CRM округляет скидку до рубля) ложится на последнюю строку. Если на штуку выходит
    дробная копейка — строка делится на (шт−1) и 1 шт с остатком, поэтому сумма позиций всегда точная."""
    items: list[dict[str, Any]] = []
    disc = max(0, min(int(discount or 0), 90))
    rows = [(name, int(qty), int(price)) for name, qty, price in lines if int(qty) > 0 and int(price) > 0]
    kops = [q * p * (100 - disc) for _, q, p in rows]
    if rows and goods_total is not None:
        kops[-1] += int(goods_total) * 100 - sum(kops)
        if kops[-1] <= 0:
            raise ValueError("сумма расчёта не сходится с позициями")
    total = 0
    for (name, qty, _), line_kop in zip(rows, kops):
        unit = line_kop // qty
        rest = line_kop - unit * qty
        base = {"vatType": "none", "name": name[:256], "paymentMethod": method, "paymentObject": "goods", "measure": "шт."}
        if rest == 0:
            items.append(dict(base, amount=unit / 100, quantity=qty))
        else:
            if qty > 1:
                items.append(dict(base, amount=unit / 100, quantity=qty - 1))
            items.append(dict(base, amount=(unit + rest) / 100, quantity=1))
        total += line_kop
    if delivery and int(delivery) > 0:
        kop = int(delivery) * 100
        items.append({"vatType": "none", "name": "Доставка заказа", "paymentMethod": method, "paymentObject": "service",
                      "measure": "шт.", "amount": kop / 100, "quantity": 1})
        total += kop
    return items, total

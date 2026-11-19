"""ПЭК для CRM «Наш декор»: расчёт стоимости и срока доставки в другой город для сайта (с 19.11.2026).

API: https://kabinet.pecom.ru/api/v1/<группа>/<метод>/ — POST JSON, Basic-аутентификация:
логин — имя пользователя личного кабинета ПЭК, пароль — ключ из «Регистрационные данные» → «Ключи API».
Логин и ключ хранятся только в базе CRM на сервере (settings.pek_login / pek_key), в журнал и на страницы не выводятся.

Как считаем:
- забор груза у нас: ПЭК забирает со склада (адрес — в настройках CRM; пока не задан — «Санкт-Петербург», считается по городу),
  в цену покупателя входит забор (решение Михаила 19.11: сами на терминал не возим); склад отправления — основное отделение СПб;
- склад получения — основное отделение филиала, к которому ПЭК относит город/адрес покупателя (/branches/findzonebyaddress/);
- продукт 3 — «ПЭК:LTL Авто» (сборный груз, работа по оферте, договор не нужен);
- до терминала — без доставки; если покупатель ввёл адрес с улицей — второй расчёт «до двери» (isDelivery + delivery.address);
- грузоместа — заводские коробки (панели 3 м — 3000×185×125 мм, погонаж 2 м — 2000×200×150 мм) и остаток поштучно
  одной связкой на каждую длину; вес коробки — из настроек CRM (по умолчанию типовой).
Ограничение ПЭК — 100 запросов в минуту на ключ, поэтому зоны городов и расчёты кешируются в памяти процесса.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Callable

log = logging.getLogger("crm.pek")

API = "https://kabinet.pecom.ru/api/v1/"
PRODUCT_LTL = 3                       # «ПЭК:LTL Авто» — сборный груз, по оферте
SENDER_ADDRESS = "Россия, Санкт-Петербург"
LOCAL_BRANCHES = ("санкт-петербург",)  # по СПб и Ленобласти возим сами — ПЭК не считаем
BOX_3M = (3.0, 0.185, 0.125)          # заводская коробка панелей 3 м, м
BOX_2M = (2.0, 0.20, 0.15)            # заводская коробка погонажа 2 м, м
BOX_KG_DEFAULT = {3: 20.0, 2: 14.0}   # типовой вес коробки, кг (точнее — в настройках CRM)
ZONE_TTL = 30 * 86400
PRICE_TTL = 6 * 3600


class PekError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status} {message}".strip())
        self.status = status
        self.message = message

    def human(self) -> str:
        if self.status == 0:
            return "ПЭК не ответил (нет связи) — попробуйте через минуту"
        if self.status in (401, 403):
            return "ПЭК не принял логин или ключ — проверьте их в личном кабинете ПЭК («Ключи API»)"
        if self.status == 429:
            return "слишком много запросов к ПЭК — подождите минуту"
        return f"ПЭК ответил ошибкой {self.status}: {self.message[:200]}"


def http_post(url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
    if not url.startswith(API):
        raise ValueError("запросы только к kabinet.pecom.ru/api/v1/")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read(3_000_000)
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(200_000)
        except Exception:  # noqa: BLE001
            return e.code, b""
    except Exception as e:  # noqa: BLE001 — сеть, DNS, таймаут, сертификат
        log.warning("ПЭК не ответил: %s %s", type(e).__name__, str(e)[:120])
        return 0, b""


class Pek:
    def __init__(self, login: str, key: str, post: Callable[[str, dict[str, str], bytes], tuple[int, bytes]] | None = None) -> None:
        self.login = login
        self.key = key
        self.post = post or http_post

    def call(self, method: str, data: dict[str, Any]) -> Any:
        auth = base64.b64encode(f"{self.login}:{self.key}".encode()).decode()
        status, raw = self.post(API + method.strip("/") + "/",
                                {"Authorization": "Basic " + auth, "Content-Type": "application/json;charset=utf-8",
                                 "Accept": "application/json"},
                                json.dumps(data, ensure_ascii=False).encode())
        try:
            out = json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError):
            out = None
        if status != 200:
            msg = (out or {}).get("error", {}).get("title", "") if isinstance(out, dict) else ""
            raise PekError(status, msg or (raw[:160].decode("utf-8", "replace") if raw else ""))
        if isinstance(out, dict) and isinstance(out.get("error"), dict):
            e = out["error"]
            raise PekError(200, (e.get("title") or "") + (": " + e["message"] if e.get("message") else ""))
        return out

    def zone(self, address: str) -> dict[str, Any] | None:
        """Филиал и основной склад ПЭК для города/адреса. None — ПЭК туда не возит или адрес не понял."""
        z = self.call("branches/findzonebyaddress", {"address": address})
        if not isinstance(z, dict) or not z.get("mainWarehouseId"):
            return None
        geo = z.get("GeoData") or {}
        return {"warehouse": str(z["mainWarehouseId"]), "branch": str(z.get("branchTitle") or ""),
                "kind": str(geo.get("kind") or ""), "precision": str(geo.get("precision") or ""),
                "formatted": str((geo.get("Address") or {}).get("formatted") or "")}

    def price(self, sender_wh: str, receiver_wh: str, cargos: list[dict[str, Any]], insure: int = 0,
              door_address: str = "", pickup_address: str = "") -> dict[str, Any]:
        """Стоимость и срок «ПЭК:LTL Авто». Возвращает {"cost": ₽, "days": дней}."""
        planned = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        data: dict[str, Any] = {"types": [PRODUCT_LTL], "senderWarehouseId": sender_wh, "receiverWarehouseId": receiver_wh,
                                "isOpenCarSender": False, "isOpenCarReceiver": False, "isHyperMarket": False,
                                "plannedDateTime": planned.strftime("%Y-%m-%dT%H:%M:%S"),
                                "isInsurance": insure > 0, "isInsurancePrice": max(0, int(insure)),
                                "isPickUp": bool(pickup_address), "isDelivery": bool(door_address), "cargos": cargos}
        if pickup_address:                       # грузим сами — погрузку ПЭК не считаем
            data["pickup"] = {"address": pickup_address}
            data["pickupServices"] = {"isLoading": False, "floor": 0, "carryingDistance": 0, "isElevator": False}
        if door_address:
            data["delivery"] = {"address": door_address}
            data["deliveryServices"] = {"isLoading": False, "floor": 0, "carryingDistance": 0, "isElevator": False}
        out = self.call("calculator/calculateprice", data)
        if not isinstance(out, dict):
            raise PekError(200, "пустой ответ калькулятора")
        if out.get("hasError"):
            raise PekError(200, str(out.get("errorMessage") or "ошибка расчёта"))
        for t in out.get("transfers") or []:
            if int(t.get("type") or 0) == PRODUCT_LTL and not t.get("hasError"):
                cost = float(t.get("costTotal") or 0)
                if cost > 0:
                    return {"cost": int(round(cost)), "days": int(t.get("estDeliveryTime") or 0) or None}
        errs = [str(t.get("errorMessage")) for t in out.get("transfers") or [] if t.get("errorMessage")]
        raise PekError(200, "; ".join(errs) or "нет цены для «ПЭК:LTL Авто»")


# ---------------------------------------------------------------- грузоместа заказа
def _dims(size: str) -> tuple[int, int, int]:
    nums = [int(n) for n in re.findall(r"\d+", size or "")]
    return (nums + [0, 0, 0])[:3] if len(nums) >= 3 else (0, 0, 0)


def cargos_for(lines: list[tuple[Any, int]], box_kg: dict[int, float] | None = None) -> list[dict[str, Any]]:
    """lines: (товар из каталога CRM с .size «Ш×Т×Д» и .per_box, количество шт).
    Полные коробки — отдельные места; остаток поштучно — одна связка на каждую длину (по объёму доли коробки)."""
    kg = {**BOX_KG_DEFAULT, **(box_kg or {})}
    places: list[dict[str, Any]] = []
    rest: dict[int, list[float]] = {}           # длина 3/2 → [объём, вес]
    for p, qty in lines:
        qty = max(0, int(qty))
        if not qty:
            continue
        _w, _t, ln = _dims(getattr(p, "size", ""))
        meters = 3 if ln >= 2500 else 2
        box = BOX_3M if meters == 3 else BOX_2M
        per_box = max(1, int(getattr(p, "per_box", 0) or 1))
        full, part = divmod(qty, per_box)
        for _ in range(min(full, 200)):
            places.append({"length": box[0], "width": box[1], "height": box[2], "weight": round(kg[meters], 2)})
        if part:
            share = part / per_box
            r = rest.setdefault(meters, [0.0, 0.0])
            r[0] += box[0] * box[1] * box[2] * share
            r[1] += kg[meters] * share
    for meters, (vol, wt) in sorted(rest.items(), reverse=True):
        box = BOX_3M if meters == 3 else BOX_2M
        places.append({"volume": round(max(vol, box[0] * box[1] * box[2] * 0.25) + 0.005, 2), "maxSize": box[0],
                       "weight": round(max(wt, 1.0) + 0.005, 2)})
    return places


def is_local(branch: str) -> bool:
    return any(b in (branch or "").lower() for b in LOCAL_BRANCHES)


def has_street(text: str) -> bool:
    """Покупатель ввёл адрес, а не только город: есть улица/дом — тогда считаем и «до двери»."""
    t = (text or "").lower()
    return bool(re.search(r"\b(ул|улица|пр|просп|проспект|пер|переулок|ш|шоссе|наб|бульвар|б-р|пл|площадь|мкр|дом|д)\.?\s", t)
                or re.search(r",\s*\d+", t))


class Cache:
    """Кеш в памяти процесса: ключ → (до когда, значение)."""

    def __init__(self) -> None:
        self.d: dict[str, tuple[float, Any]] = {}

    def get(self, k: str) -> Any:
        v = self.d.get(k)
        if v and v[0] > time.time():
            return v[1]
        self.d.pop(k, None)
        return None

    def put(self, k: str, v: Any, ttl: float) -> None:
        if len(self.d) > 5000:
            self.d.clear()
        self.d[k] = (time.time() + ttl, v)

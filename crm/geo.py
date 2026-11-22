"""Город посетителя сайта по IP — только в момент прихода отметки, сам IP нигде не хранится.

База — DB-IP City Lite (https://db-ip.com, лицензия CC BY 4.0, «IP Geolocation by DB-IP»): файл .mmdb на сервере,
обновляет root раз в месяц (prostranstvo-crm geo). Читает модуль python3-maxminddb. Нет модуля или файла —
город просто не определяется, счётчик работает как раньше.

Названия в базе — по-английски; крупные города России и соседних стран переводим, остальное показываем как есть.
"""

from __future__ import annotations

import ipaddress
import re
import logging
import os
import threading
from typing import Any

log = logging.getLogger("crm.geo")

CITY_RU = {
    "Saint Petersburg": "Санкт-Петербург", "St Petersburg": "Санкт-Петербург", "Moscow": "Москва",
    "Novosibirsk": "Новосибирск", "Yekaterinburg": "Екатеринбург", "Kazan": "Казань", "Nizhniy Novgorod": "Нижний Новгород",
    "Nizhny Novgorod": "Нижний Новгород", "Chelyabinsk": "Челябинск", "Samara": "Самара", "Omsk": "Омск",
    "Rostov-on-Don": "Ростов-на-Дону", "Ufa": "Уфа", "Krasnoyarsk": "Красноярск", "Voronezh": "Воронеж", "Perm": "Пермь",
    "Volgograd": "Волгоград", "Krasnodar": "Краснодар", "Saratov": "Саратов", "Tyumen": "Тюмень", "Tolyatti": "Тольятти",
    "Izhevsk": "Ижевск", "Barnaul": "Барнаул", "Ulyanovsk": "Ульяновск", "Irkutsk": "Иркутск", "Khabarovsk": "Хабаровск",
    "Yaroslavl": "Ярославль", "Vladivostok": "Владивосток", "Makhachkala": "Махачкала", "Tomsk": "Томск", "Orenburg": "Оренбург",
    "Kemerovo": "Кемерово", "Novokuznetsk": "Новокузнецк", "Ryazan": "Рязань", "Astrakhan": "Астрахань",
    "Naberezhnye Chelny": "Набережные Челны", "Penza": "Пенза", "Kirov": "Киров", "Lipetsk": "Липецк", "Cheboksary": "Чебоксары",
    "Balashikha": "Балашиха", "Kaliningrad": "Калининград", "Tula": "Тула", "Kursk": "Курск", "Stavropol": "Ставрополь",
    "Sochi": "Сочи", "Tver": "Тверь", "Ivanovo": "Иваново", "Bryansk": "Брянск", "Belgorod": "Белгород", "Surgut": "Сургут",
    "Vladimir": "Владимир", "Arkhangelsk": "Архангельск", "Smolensk": "Смоленск", "Kaluga": "Калуга", "Murmansk": "Мурманск",
    "Petrozavodsk": "Петрозаводск", "Velikiy Novgorod": "Великий Новгород", "Veliky Novgorod": "Великий Новгород",
    "Pskov": "Псков", "Vologda": "Вологда", "Cherepovets": "Череповец", "Syktyvkar": "Сыктывкар", "Gatchina": "Гатчина",
    "Vsevolozhsk": "Всеволожск", "Kolpino": "Колпино", "Pushkin": "Пушкин", "Kudrovo": "Кудрово", "Murino": "Мурино",
    "Sestroretsk": "Сестрорецк", "Kronshtadt": "Кронштадт", "Peterhof": "Петергоф", "Lomonosov": "Ломоносов",
    "Vyborg": "Выборг", "Tosno": "Тосно", "Kirovsk": "Кировск", "Sertolovo": "Сертолово", "Sosnovyy Bor": "Сосновый Бор",
    "Krasnoye Selo": "Красное Село", "Shushary": "Шушары", "Zelenograd": "Зеленоград", "Khimki": "Химки",
    "Podolsk": "Подольск", "Mytishchi": "Мытищи", "Lyubertsy": "Люберцы", "Korolyov": "Королёв", "Krasnogorsk": "Красногорск",
    "Sevastopol": "Севастополь", "Simferopol": "Симферополь",
    "Almaty": "Алматы", "Astana": "Астана", "Nur-Sultan": "Астана", "Shymkent": "Шымкент", "Karaganda": "Караганда",
    "Minsk": "Минск", "Tashkent": "Ташкент", "Bishkek": "Бишкек", "Osh": "Ош", "Yerevan": "Ереван", "Tbilisi": "Тбилиси",
    "Baku": "Баку", "Dushanbe": "Душанбе", "Chisinau": "Кишинёв", "Kyiv": "Киев", "Kiev": "Киев", "Riga": "Рига",
    "Tallinn": "Таллин", "Vilnius": "Вильнюс", "Helsinki": "Хельсинки", "Stockholm": "Стокгольм", "Amsterdam": "Амстердам",
    "Frankfurt am Main": "Франкфурт-на-Майне", "Istanbul": "Стамбул", "Dubai": "Дубай",
}
COUNTRY_RU = {
    "RU": "Россия", "KZ": "Казахстан", "BY": "Беларусь", "UZ": "Узбекистан", "KG": "Киргизия", "AM": "Армения", "GE": "Грузия",
    "AZ": "Азербайджан", "TJ": "Таджикистан", "MD": "Молдова", "UA": "Украина", "LV": "Латвия", "LT": "Литва", "EE": "Эстония",
    "FI": "Финляндия", "SE": "Швеция", "NL": "Нидерланды", "DE": "Германия", "TR": "Турция", "AE": "ОАЭ", "US": "США",
    "GB": "Великобритания", "FR": "Франция", "PL": "Польша", "CN": "Китай", "TH": "Таиланд", "IL": "Израиль", "RS": "Сербия",
    "CY": "Кипр", "ME": "Черногория", "IN": "Индия", "VN": "Вьетнам", "ID": "Индонезия",
}


class Geo:
    """Ленивая загрузка базы; новый файл (раз в месяц) подхватывается сам — по времени изменения."""

    def __init__(self, path: str) -> None:
        self.path = path or ""
        self._db: Any = None
        self._mtime = 0.0
        self._lock = threading.Lock()
        self._warned = False

    def _reader(self) -> Any:
        if not self.path:
            return None
        try:
            mt = os.stat(self.path).st_mtime
        except OSError:
            return None
        if self._db is not None and mt == self._mtime:
            return self._db
        with self._lock:
            if self._db is not None and mt == self._mtime:
                return self._db
            try:
                import maxminddb  # type: ignore  # python3-maxminddb (необязательный)
            except ImportError:
                if not self._warned:
                    log.info("город посетителя не определяется: нет модуля python3-maxminddb")
                    self._warned = True
                return None
            try:
                old, self._db = self._db, maxminddb.open_database(self.path)
                self._mtime = mt
                if old is not None:
                    try:
                        old.close()
                    except Exception:  # noqa: BLE001
                        pass
            except Exception:  # noqa: BLE001 — битый или недокачанный файл: просто без города
                log.warning("база городов не открылась: %s", self.path)
                self._db = None
            return self._db

    def ready(self) -> bool:
        return self._reader() is not None

    def city(self, ip: str) -> str:
        """«Санкт-Петербург» / «Алматы, Казахстан» / «Россия» / «» (не знаем, свой или служебный адрес)."""
        try:
            a = ipaddress.ip_address((ip or "").strip())
        except ValueError:
            return ""
        if a.is_private or a.is_loopback or a.is_reserved or a.is_multicast or a.is_link_local:
            return ""
        db = self._reader()
        if db is None:
            return ""
        try:
            rec = db.get(str(a)) or {}
        except Exception:  # noqa: BLE001
            return ""
        return label(rec)


def label(rec: dict[str, Any]) -> str:
    def name(x: Any) -> str:
        n = x.get("names") if isinstance(x, dict) else None
        return str((n or {}).get("ru") or (n or {}).get("en") or "")[:40] if isinstance(n, dict) else ""
    city = name(rec.get("city"))
    cc = str((rec.get("country") or {}).get("iso_code") or "").upper()[:2] if isinstance(rec.get("country"), dict) else ""
    country = COUNTRY_RU.get(cc) or name(rec.get("country"))
    city = re.sub(r"\s*\(.*$", "", city).strip()    # DB-IP: «Moscow (Tsentralnyy administrativnyy okrug)» → «Moscow»
    city = CITY_RU.get(city, city)
    if city and cc and cc != "RU":
        return f"{city}, {country}"[:60]
    return (city or country)[:60]

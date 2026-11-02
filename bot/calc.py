"""Расчёт количества панелей и погонажа. Только чистые функции — без Telegram и сети.

Правила (как на сайте):
  * панели (реечные, под дерево/бетон) ставятся вертикально:
        штук = ceil(ширина_мм / ширина_панели) × ceil(высота_мм / длина_панели),
        затем + запас (по умолчанию 7 %), округление вверх;
  * погонаж (молдинг, плинтус, карниз, уголок):
        штук = ceil(длина_м × 1,07 / длина_планки_м).
Вся арифметика целочисленная, чтобы не было ошибок округления float
(например, 100 × 1,07 = 107,00000000000001 → 108).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DEFAULT_RESERVE_PERCENT = 7

# Ограничения ввода (в метрах)
MAX_WALL_WIDTH_M = 100
MAX_WALL_HEIGHT_M = 20
MAX_LINEAR_M = 500
MIN_SIZE_MM = 50  # меньше 5 см — почти наверняка опечатка


class InputError(ValueError):
    """Непонятный ввод. code: 'format' | 'zero' | 'too_small' | 'too_big'."""

    def __init__(self, code: str, max_m: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.max_m = max_m


def ceil_div(a: int, b: int) -> int:
    """Деление с округлением вверх для целых a ≥ 0, b > 0."""
    if b <= 0:
        raise ValueError("делитель должен быть больше нуля")
    return -(-a // b)


def add_reserve(pieces: int, reserve_percent: int = DEFAULT_RESERVE_PERCENT) -> int:
    """Количество с запасом, округление вверх: 17 шт + 7 % → 19 шт (17 × 1,07 = 18,19)."""
    return ceil_div(pieces * (100 + reserve_percent), 100)


# --------------------------------------------------------------------------- ввод
_UNITS: tuple[tuple[str, int], ...] = (
    # порядок важен: «мм» раньше «м»
    ("миллиметр", 1), ("мм", 1), ("mm", 1),
    ("сантиметр", 10), ("см", 10), ("cm", 10),
    ("метр", 1000), ("м", 1000), ("m", 1000),
)
_NUM = r"(\d+(?:\.\d+)?)"
_UNIT = r"(миллиметр\w*|мм|mm|сантиметр\w*|см|cm|метр\w*|м|m)?"
_ONE_RE = re.compile(rf"^{_NUM}\s*{_UNIT}\.?$")
_M_CM_RE = re.compile(r"^(\d+)\s*(?:м|m|метр\w*)\.?\s*(\d+)\s*(?:см|cm|сантиметр\w*)\.?$")
_PAIR_SPLIT_RE = re.compile(r"\s*(?:[xх×*]|на)\s*")


def _normalize(text: str) -> str:
    s = (text or "").strip().lower().replace("ё", "е")
    s = s.replace(",", ".")
    s = re.sub(r"(?<=\d)[\s\u00a0\u202f]+(?=\d{3}(?!\d))", "", s)  # «3 200 мм» → «3200 мм»
    return re.sub(r"\s+", " ", s)


def _unit_factor(unit: str | None) -> int | None:
    if not unit:
        return None
    for prefix, factor in _UNITS:
        if unit.startswith(prefix):
            return factor
    return None


def parse_length_mm(text: str, max_m: int) -> int:
    """Длина из текста пользователя → миллиметры (целое).

    Понимает: «3,2», «3.2», «3.2 м», «320 см», «3200 мм», «3 м 20 см».
    Без единиц: число до max_m — это метры; больше — сантиметры (если меньше 1000)
    или миллиметры (1000 и больше): «270» для высоты → 2,7 м, «2700» → 2,7 м.
    """
    s = _normalize(text)
    m = _M_CM_RE.match(s)
    if m:
        mm = int(m.group(1)) * 1000 + int(m.group(2)) * 10
    else:
        m = _ONE_RE.match(s)
        if not m:
            raise InputError("format")
        try:
            value = Decimal(m.group(1))
        except InvalidOperation as exc:  # pragma: no cover - regex уже проверил формат
            raise InputError("format") from exc
        factor = _unit_factor(m.group(2))
        if factor is None:
            if value <= max_m:
                factor = 1000
            elif value < 1000:
                factor = 10
            else:
                factor = 1
        mm = int((value * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if mm <= 0:
        raise InputError("zero")
    if mm < MIN_SIZE_MM:
        raise InputError("too_small")
    if mm > max_m * 1000:
        raise InputError("too_big", max_m)
    return mm


def parse_wall_pair(text: str) -> tuple[int, int] | None:
    """«3 x 2,7», «3х2.7», «300 на 270 см» → (ширина_мм, высота_мм) или None, если это не пара."""
    s = _normalize(text)
    parts = _PAIR_SPLIT_RE.split(s)
    if len(parts) != 2 or not all(parts):
        return None
    left, right = parts
    # «300 на 270 см»: единица только у второго числа — относится к обоим
    right_simple = _ONE_RE.match(right)
    if right_simple and right_simple.group(2) and re.fullmatch(_NUM, left):
        left = f"{left} {right_simple.group(2)}"
    width = parse_length_mm(left, MAX_WALL_WIDTH_M)
    height = parse_length_mm(right, MAX_WALL_HEIGHT_M)
    return width, height


# --------------------------------------------------------------------------- расчёт
@dataclass(frozen=True)
class AreaResult:
    """Расчёт панелей на стену."""

    width_mm: int
    height_mm: int
    panel_width_mm: int
    panel_length_mm: int
    columns: int          # панелей в ряд по ширине
    rows: int             # панелей по высоте (больше 1 — стена выше панели)
    base_pieces: int      # без запаса
    pieces: int           # с запасом
    reserve_percent: int
    per_box: int
    boxes: int            # полных коробок
    rest: int             # остаток поштучно
    price: int            # ₽ за штуку
    total_price: int

    @property
    def reserve_pieces(self) -> int:
        return self.pieces - self.base_pieces

    @property
    def area_m2(self) -> Decimal:
        return (Decimal(self.width_mm) * Decimal(self.height_mm) / Decimal(1_000_000)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


@dataclass(frozen=True)
class LinearResult:
    """Расчёт погонажа (молдинг, плинтус, карниз, уголок)."""

    length_mm: int
    piece_length_mm: int
    pieces: int
    reserve_percent: int
    per_box: int
    boxes: int
    rest: int
    price: int
    total_price: int

    @property
    def base_pieces(self) -> int:
        return ceil_div(self.length_mm, self.piece_length_mm)

    @property
    def reserve_pieces(self) -> int:
        return self.pieces - self.base_pieces

    @property
    def length_with_reserve_mm(self) -> int:
        return ceil_div(self.length_mm * (100 + self.reserve_percent), 100)

    @property
    def bought_length_mm(self) -> int:
        return self.pieces * self.piece_length_mm


def _split_boxes(pieces: int, per_box: int) -> tuple[int, int]:
    if per_box <= 0:
        return 0, pieces
    return divmod(pieces, per_box)


def _check_positive(**values: int) -> None:
    for name, value in values.items():
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} должно быть положительным целым, а не {value!r}")


def calc_area(
    width_mm: int,
    height_mm: int,
    panel_width_mm: int,
    panel_length_mm: int,
    per_box: int,
    price: int,
    reserve_percent: int = DEFAULT_RESERVE_PERCENT,
) -> AreaResult:
    """Сколько панелей нужно на стену width_mm × height_mm."""
    _check_positive(width_mm=width_mm, height_mm=height_mm,
                    panel_width_mm=panel_width_mm, panel_length_mm=panel_length_mm)
    columns = ceil_div(width_mm, panel_width_mm)
    rows = ceil_div(height_mm, panel_length_mm)
    base = columns * rows
    pieces = add_reserve(base, reserve_percent)
    boxes, rest = _split_boxes(pieces, per_box)
    return AreaResult(
        width_mm=width_mm, height_mm=height_mm,
        panel_width_mm=panel_width_mm, panel_length_mm=panel_length_mm,
        columns=columns, rows=rows, base_pieces=base, pieces=pieces,
        reserve_percent=reserve_percent, per_box=per_box, boxes=boxes, rest=rest,
        price=max(price, 0), total_price=pieces * max(price, 0),
    )


def calc_linear(
    length_mm: int,
    piece_length_mm: int,
    per_box: int,
    price: int,
    reserve_percent: int = DEFAULT_RESERVE_PERCENT,
) -> LinearResult:
    """Сколько планок длиной piece_length_mm нужно на length_mm погонных миллиметров."""
    _check_positive(length_mm=length_mm, piece_length_mm=piece_length_mm)
    # ceil(L × (100 + запас) / 100 / l) — одним целочисленным делением
    pieces = ceil_div(length_mm * (100 + reserve_percent), 100 * piece_length_mm)
    boxes, rest = _split_boxes(pieces, per_box)
    return LinearResult(
        length_mm=length_mm, piece_length_mm=piece_length_mm, pieces=pieces,
        reserve_percent=reserve_percent, per_box=per_box, boxes=boxes, rest=rest,
        price=max(price, 0), total_price=pieces * max(price, 0),
    )

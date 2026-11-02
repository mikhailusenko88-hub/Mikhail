import pytest

import calc
from calc import InputError, add_reserve, calc_area, calc_linear, parse_length_mm, parse_wall_pair


# ----------------------------------------------------------------- панели
def test_a907_wall_3_by_2_7():
    # A907: 180 мм × 3000 мм, в коробке 12, 950 ₽. Стена 3 × 2,7 м.
    r = calc_area(3000, 2700, 180, 3000, per_box=12, price=950)
    assert r.columns == 17          # ceil(3000 / 180) = 17
    assert r.rows == 1              # ceil(2700 / 3000) = 1
    assert r.base_pieces == 17
    assert r.pieces == 19           # 17 × 1,07 = 18,19 → 19
    assert r.reserve_pieces == 2
    assert (r.boxes, r.rest) == (1, 7)
    assert r.total_price == 19 * 950 == 18050
    assert str(r.area_m2) == "8.10"


def test_wall_higher_than_panel_needs_two_rows():
    # A201/2: 100 × 2400 мм. Стена 1 × 2,7 м → 10 в ряд × 2 по высоте = 20 → +7% = 22
    r = calc_area(1000, 2700, 100, 2400, per_box=18, price=760)
    assert (r.columns, r.rows, r.base_pieces, r.pieces) == (10, 2, 20, 22)
    assert (r.boxes, r.rest) == (1, 4)


def test_exact_fit_still_gets_reserve():
    r = calc_area(1800, 3000, 180, 3000, per_box=12, price=950)
    assert r.base_pieces == 10
    assert r.pieces == 11           # 10 × 1,07 = 10,7 → 11


def test_reserve_no_float_error():
    assert add_reserve(100) == 107  # 100 × 1,07 во float = 107,00000000000001
    assert add_reserve(17) == 19
    assert add_reserve(1) == 2
    assert add_reserve(0) == 0
    assert add_reserve(10, 0) == 10


def test_boxes_exact_and_zero_per_box():
    r = calc_area(2160, 3000, 180, 3000, per_box=12, price=1)  # 12 → 13
    assert (r.pieces, r.boxes, r.rest) == (13, 1, 1)
    r = calc_area(1000, 1000, 100, 1000, per_box=0, price=10)
    assert (r.boxes, r.rest) == (0, r.pieces)


def test_area_rejects_bad_numbers():
    with pytest.raises(ValueError):
        calc_area(0, 2700, 180, 3000, 12, 950)
    with pytest.raises(ValueError):
        calc_area(3000, 2700, 0, 3000, 12, 950)


# ----------------------------------------------------------------- погонаж
def test_plinth_a703_15m():
    # A703: планка 2 м, в коробке 28, 290 ₽. 15 м × 1,07 = 16,05 м / 2 = 8,025 → 9 шт
    r = calc_linear(15000, 2000, per_box=28, price=290)
    assert r.pieces == 9
    assert (r.boxes, r.rest) == (0, 9)
    assert r.total_price == 2610
    assert r.length_with_reserve_mm == 16050
    assert r.bought_length_mm == 18000
    assert r.base_pieces == 8
    assert r.reserve_pieces == 1


def test_plinth_a703_2m():
    # 2 м × 1,07 = 2,14 м / 2 м = 1,07 → 2 шт
    r = calc_linear(2000, 2000, per_box=28, price=290)
    assert r.pieces == 2
    assert r.total_price == 580


def test_linear_whole_boxes():
    # молдинг 2 м, коробка 48: 100 м × 1,07 = 107 м / 2 = 53,5 → 54 = 1 коробка + 6
    r = calc_linear(100000, 2000, per_box=48, price=180)
    assert (r.pieces, r.boxes, r.rest) == (54, 1, 6)


def test_linear_3m_piece():
    # A611/3: 3 м. 10 м × 1,07 = 10,7 / 3 = 3,57 → 4
    assert calc_linear(10000, 3000, 25, 580).pieces == 4


# ----------------------------------------------------------------- ввод
@pytest.mark.parametrize(
    "text,expected",
    [
        ("3,2", 3200), ("3.2", 3200), (" 3,2 ", 3200), ("3", 3000),
        ("3.2 м", 3200), ("3,2м", 3200), ("3.2 m", 3200), ("3,2 метра", 3200),
        ("320 см", 3200), ("320см", 3200), ("320 cm", 3200),
        ("3200 мм", 3200), ("3200мм", 3200), ("3 200 мм", 3200), ("3 200мм", 3200),
        ("3 м 20 см", 3200), ("2,75", 2750), ("2,755", 2755),
        ("320", 3200),   # без единиц и больше 100 м → сантиметры
        ("3200", 3200),  # 1000 и больше → миллиметры
    ],
)
def test_parse_width(text, expected):
    assert parse_length_mm(text, calc.MAX_WALL_WIDTH_M) == expected


@pytest.mark.parametrize("text,expected", [("2,7", 2700), ("270", 2700), ("2700", 2700), ("270 см", 2700)])
def test_parse_height(text, expected):
    assert parse_length_mm(text, calc.MAX_WALL_HEIGHT_M) == expected


@pytest.mark.parametrize("text,expected", [("15", 15000), ("15,5", 15500), ("120", 120000), ("1500 см", 15000)])
def test_parse_linear(text, expected):
    assert parse_length_mm(text, calc.MAX_LINEAR_M) == expected


@pytest.mark.parametrize(
    "text,code",
    [("", "format"), ("abc", "format"), ("три метра", "format"), ("-3", "format"), ("3,2,1", "format"),
     ("0", "zero"), ("0,0", "zero"), ("0,01", "too_small"), ("101 м", "too_big"), ("25 м", None)],
)
def test_parse_errors(text, code):
    if code is None:  # 25 м — для ширины нормально
        assert parse_length_mm(text, calc.MAX_WALL_WIDTH_M) == 25000
        return
    with pytest.raises(InputError) as exc:
        parse_length_mm(text, calc.MAX_WALL_WIDTH_M)
    assert exc.value.code == code


def test_height_limit():
    with pytest.raises(InputError) as exc:
        parse_length_mm("25 м", calc.MAX_WALL_HEIGHT_M)
    assert exc.value.code == "too_big"


@pytest.mark.parametrize(
    "text,expected",
    [("3 x 2,7", (3000, 2700)), ("3х2.7", (3000, 2700)), ("3×2,7", (3000, 2700)),
     ("3*2.7", (3000, 2700)), ("3,2 на 2,7", (3200, 2700)), ("300 на 270 см", (3000, 2700)),
     ("3 м x 270 см", (3000, 2700)), ("3,2", None), ("320 см", None), ("3 м 20 см", None)],
)
def test_parse_wall_pair(text, expected):
    assert parse_wall_pair(text) == expected


def test_parse_wall_pair_errors_propagate():
    with pytest.raises(InputError):
        parse_wall_pair("abc x 2,7")

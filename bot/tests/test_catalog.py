import json
import os
from collections import Counter

import pytest
from conftest import SAMPLE_HTML, site_sample_path

import catalog as cat
from catalog import Catalog, CatalogError, CatalogStore, load_catalog_sync, norm_article, parse_catalog


def test_parse_sample():
    products = parse_catalog(SAMPLE_HTML)
    assert [p.article for p in products] == [
        "A907", "GS 1", "A201/2", "2-3", "A703", "A11-80", "A38", "A116", "A002"]  # битые пропущены
    a907 = products[0]
    assert (a907.kind, a907.width, a907.thickness, a907.length, a907.per_box, a907.price) == (
        "panel", 180, 10, 3000, 12, 950)
    assert a907.is_area and a907.box_price == 11400
    assert a907.size_text == "180×10×3000 мм"
    assert a907.short_desc == "широкие ламели с тонкими швами"
    assert not products[4].is_area  # плинтус — погонаж
    assert products[4].short_desc == ""  # описание начинается с размеров


def test_bracket_inside_string_does_not_break_parsing():
    products = parse_catalog(SAMPLE_HTML)
    assert any("];" in p.desc for p in products)


def test_find_variants():
    c = Catalog(parse_catalog(SAMPLE_HTML))
    assert c.find("A907").article == "A907"
    assert c.find("a907").article == "A907"
    assert c.find("А907").article == "A907"      # русская «А»
    assert c.find(" a 907 ").article == "A907"
    assert c.find("gs1").article == "GS 1"
    assert c.find("GS 1").article == "GS 1"
    assert c.find("a201/2").article == "A201/2"
    assert c.find("2-3").article == "2-3"
    assert c.find("а11-80").article == "A11-80"
    assert c.find("A1180").article == "A11-80"   # без дефиса — тоже найдётся
    assert c.find("A999") is None
    assert c.find("") is None


def test_search_suggestions():
    c = Catalog(parse_catalog(SAMPLE_HTML))
    assert [p.article for p in c.search("A90")] == ["A907"]
    assert c.search("x") == []


def test_groups_order_and_members():
    c = Catalog(parse_catalog(SAMPLE_HTML))
    assert [code for code, _ in c.groups()] == ["panel", "color", "mold", "plinth", "cornice", "corner"]
    assert [p.article for p in c.in_group("plinth")] == ["A703", "A11-80"]


def test_unknown_kind_goes_to_other():
    html = 'const CAT=[{"a":"Z1","c":"glue","n":"Клей","w":1,"l":1000,"b":1,"r":100}];'
    c = Catalog(parse_catalog(html))
    assert c.groups() == [("other", "Другое")]
    assert not c.find("Z1").is_area


@pytest.mark.parametrize("html", ["", "<html>нет каталога</html>", "const CAT=[{oops}];", "const CAT=[];",
                                  'const CAT=[{"a":"X","w":0,"l":0}];'])
def test_bad_html(html):
    with pytest.raises(CatalogError):
        parse_catalog(html)


def test_norm_article():
    assert norm_article(" гs 1 ") == "ГS1"  # «г» не похожа на латиницу — не меняем
    assert norm_article("а907") == "A907"


def test_load_order_file_then_cache(tmp_path):
    site = tmp_path / "index.html"
    site.write_text(SAMPLE_HTML, encoding="utf-8")
    cache = tmp_path / "cache.json"
    c = load_catalog_sync(str(site), "", str(cache))
    assert c.source == "файл сайта" and len(c) == 9
    assert len(json.loads(cache.read_text(encoding="utf-8"))) == 9

    # сайта нет, GitHub недоступен → берём кеш
    os.remove(site)
    c2 = load_catalog_sync(str(site), "http://127.0.0.1:9/none", str(cache))
    assert c2.source == "кеш" and len(c2) == 9

    os.remove(cache)
    with pytest.raises(CatalogError):
        load_catalog_sync(str(site), "http://127.0.0.1:9/none", str(cache))


def test_store_keeps_old_catalog_on_error(tmp_path):
    import asyncio

    site = tmp_path / "index.html"
    site.write_text(SAMPLE_HTML, encoding="utf-8")
    store = CatalogStore(str(site), "", "", 60)
    first = asyncio.run(store.reload())
    assert first is not None and len(first) == 9
    site.write_text("сломано", encoding="utf-8")
    again = asyncio.run(store.reload())
    assert again is first and store.last_error


def test_real_site_catalog():
    path = site_sample_path()
    if not path:
        pytest.skip("нет index.html сайта (задайте CATALOG_SAMPLE=путь)")
    with open(path, encoding="utf-8") as fh:
        products = parse_catalog(fh.read())
    assert len(products) == 107
    kinds = Counter(p.kind for p in products)
    assert kinds == {"color": 28, "mold": 28, "plinth": 27, "panel": 18, "cornice": 4, "corner": 2}
    assert set(kinds) <= set(cat.GROUPS)
    c = Catalog(products)
    a907 = c.find("A907")
    assert (a907.width, a907.length, a907.per_box) == (180, 3000, 12)
    a703 = c.find("A703")
    assert (a703.length, a703.per_box) == (2000, 28)
    assert all(p.price > 0 and p.per_box > 0 for p in products)

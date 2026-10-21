from pathlib import Path

import pytest

from app.collector.parser import ParseError, parse_product

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_json_ld에서_가격과_판매처_평점을_읽는다():
    snap = parse_product(load("product_jsonld.html"))
    assert snap.name == "APPLE 에어팟 프로3 MFHP4KH/A (정품)"
    assert snap.lowest_price == 291200
    assert snap.offer_count == 176
    assert snap.rating == 4.8
    assert snap.review_count == 2002
    assert snap.source == "jsonld"


def test_json_ld가_없으면_화면_가격으로_대신_읽는다():
    snap = parse_product(load("product_html_only.html"))
    assert snap.lowest_price == 291200
    assert snap.name == "APPLE 에어팟 프로3 MFHP4KH/A (정품)"
    assert snap.source == "html"


def test_구조가_바뀌어_가격이_없으면_ParseError():
    with pytest.raises(ParseError):
        parse_product(load("product_broken.html"))


def test_json_ld가_깨져_있으면_화면_가격으로_넘어간다():
    html = load("product_html_only.html").replace(
        "</head>", '<script type="application/ld+json">{깨진 json</script></head>'
    )
    assert parse_product(html).source == "html"


def test_판매처별_offer_목록이면_가장_싼_가격을_쓴다():
    html = """<html><head><script type="application/ld+json">
    {"@type": "Product", "name": "테스트 상품",
     "offers": [{"price": "15000"}, {"price": "12,000"}, {"price": "13000"}]}
    </script></head></html>"""
    snap = parse_product(html)
    assert snap.lowest_price == 12000
    assert snap.offer_count == 3

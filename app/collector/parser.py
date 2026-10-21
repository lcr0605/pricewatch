"""다나와 상품 상세 페이지에서 가격 정보를 뽑는다.

1순위: 검색엔진용 구조화 데이터(JSON-LD). 화면 디자인이 바뀌어도 잘 안 바뀐다.
2순위: 화면의 최저가 표시(`em.prc_c`). JSON-LD가 없을 때만 쓴다.
"""

import json
from dataclasses import dataclass

from bs4 import BeautifulSoup


class ParseError(Exception):
    """페이지에서 가격을 찾지 못함. 대부분 사이트 구조 변경이 원인."""


@dataclass(frozen=True)
class ProductSnapshot:
    name: str
    lowest_price: int
    offer_count: int | None = None
    rating: float | None = None
    review_count: int | None = None
    source: str = "jsonld"  # 어느 경로로 뽑았는지 (jsonld | html)


def _to_int(value) -> int | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_product_jsonld(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    return None


def _from_jsonld(item: dict) -> ProductSnapshot | None:
    offers = item.get("offers") or {}
    if isinstance(offers, list):  # 판매처별 Offer 목록인 경우
        prices = [_to_int(o.get("price")) for o in offers if isinstance(o, dict)]
        prices = [p for p in prices if p]
        price = min(prices) if prices else None
        offer_count = len(prices) or None
    else:
        price = _to_int(offers.get("lowPrice") or offers.get("price"))
        offer_count = _to_int(offers.get("offerCount"))

    name = (item.get("name") or "").strip()
    if not name or not price:
        return None

    rating = item.get("aggregateRating") or {}
    return ProductSnapshot(
        name=name,
        lowest_price=price,
        offer_count=offer_count,
        rating=_to_float(rating.get("ratingValue")),
        review_count=_to_int(rating.get("reviewCount")),
        source="jsonld",
    )


def _from_html(soup: BeautifulSoup) -> ProductSnapshot | None:
    price_tag = soup.select_one("em.prc_c")
    name_tag = soup.select_one(".prod_tit .title") or soup.find("title")
    if not price_tag or not name_tag:
        return None

    price = _to_int(price_tag.get_text())
    name = name_tag.get_text(strip=True).split(" : 다나와")[0].strip()
    if not price or not name:
        return None
    return ProductSnapshot(name=name, lowest_price=price, source="html")


def parse_product(html: str) -> ProductSnapshot:
    soup = BeautifulSoup(html, "html.parser")

    item = _find_product_jsonld(soup)
    snapshot = _from_jsonld(item) if item else None
    if snapshot is None:
        snapshot = _from_html(soup)
    if snapshot is None:
        raise ParseError("가격 정보를 찾지 못했습니다 (JSON-LD, 화면 가격 모두 없음)")
    return snapshot


@dataclass(frozen=True)
class SearchResult:
    pcode: str
    name: str
    price: int | None


def parse_search(html: str) -> list[SearchResult]:
    """검색 결과 페이지에서 상품 목록을 뽑는다 (감시 상품 등록용)."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()
    for item in soup.select("li.prod_item"):
        link = item.select_one("p.prod_name a")
        if not link or "pcode=" not in link.get("href", ""):
            continue
        pcode = link["href"].split("pcode=")[1].split("&")[0]
        if not pcode.isdigit() or pcode in seen:
            continue
        seen.add(pcode)
        price_tag = item.select_one("p.price_sect strong")
        results.append(
            SearchResult(
                pcode=pcode,
                name=link.get_text(" ", strip=True),
                price=_to_int(price_tag.get_text()) if price_tag else None,
            )
        )
    return results

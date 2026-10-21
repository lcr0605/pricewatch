from datetime import date
from pathlib import Path

import pytest

from app import tracking
from app.collector.fetch import FetchError
from app.tracking import (
    TrackingError,
    display_name,
    is_tracking,
    preview,
    start_tracking,
    stop_tracking,
    suggest_target,
)

HTML = (Path(__file__).parent / "fixtures" / "product_jsonld.html").read_text(encoding="utf-8")
LINK = "https://prod.danawa.com/info/?pcode=97405013&cate=12237349"
TODAY = date(2026, 10, 22)


class FakeRepo:
    """repo 모듈 대신 쓰는 메모리 저장소."""

    def __init__(self):
        self.products: dict[str, dict] = {}
        self.snapshots: list[tuple] = []

    def find_product_by_pcode(self, conn, pcode):
        return self.products.get(pcode)

    def count_active(self, conn):
        return sum(p["is_active"] for p in self.products.values())

    def add_product(self, conn, pcode, name, target_price=None, category=None):
        old = self.products.get(pcode, {})
        self.products[pcode] = {
            "id": old.get("id", len(self.products) + 1), "pcode": pcode, "name": name,
            "category": category or old.get("category"),
            "target_price": target_price if target_price is not None else old.get("target_price"),
            "is_active": old.get("is_active", True),
        }

    def set_active(self, conn, pcode, active):
        if pcode not in self.products:
            return False
        self.products[pcode]["is_active"] = active
        return True

    def set_target_price(self, conn, pcode, target_price):
        self.products[pcode]["target_price"] = target_price

    def save_snapshot(self, conn, product_id, run_id, on, snap):
        self.snapshots.append((product_id, run_id, on, snap.lowest_price))


@pytest.fixture
def db(monkeypatch):
    fake = FakeRepo()
    monkeypatch.setattr(tracking, "repo", fake)
    return fake


def fetch_ok(pcode):
    return HTML


def fetch_should_not_be_called(pcode):
    raise AssertionError("다나와에 다시 요청하면 안 됨")


def test_목표가는_현재가보다_5퍼센트_낮게_100원_단위로_제안():
    assert suggest_target(291_200) == 276_600
    assert suggest_target(50) == 100


def test_목록용_이름에서는_묶음_표기를_뺀다():
    assert display_name("크리오 칫솔 (30개)") == "크리오 칫솔"
    assert display_name("APPLE 에어팟 프로3 (정품)") == "APPLE 에어팟 프로3 (정품)"


def test_미리보기는_이름_현재가_제안_목표가를_돌려준다():
    p = preview(LINK, fetch_ok)
    assert (p.pcode, p.price, p.suggested_target) == ("97405013", 291_200, 276_600)


def test_다나와_요청이_실패하면_사용자용_메시지():
    def fetch_fail(pcode):
        raise FetchError("timeout")
    with pytest.raises(TrackingError, match="잠시 후 다시 시도"):
        preview(LINK, fetch_fail)


def test_등록하면_오늘_가격도_바로_저장한다(db):
    result = start_tracking(None, LINK, 280_000, "이어폰", fetch=fetch_ok, today=TODAY)
    assert result.status == "added"
    assert db.products["97405013"]["target_price"] == 280_000
    assert db.snapshots == [(1, None, TODAY, 291_200)]


def test_미리보기_결과가_있으면_다나와에_다시_요청하지_않는다(db):
    previewed = preview(LINK, fetch_ok)
    start_tracking(None, LINK, previewed=previewed, fetch=fetch_should_not_be_called, today=TODAY)
    assert len(db.snapshots) == 1


def test_이미_추적_중이면_중복_등록하지_않고_목표가만_바꾼다(db):
    start_tracking(None, LINK, fetch=fetch_ok, today=TODAY)
    result = start_tracking(None, LINK, 270_000, fetch=fetch_should_not_be_called, today=TODAY)
    assert result.status == "already_tracking"
    assert db.products["97405013"]["target_price"] == 270_000
    assert len(db.snapshots) == 1


def test_50개가_차면_더_등록할_수_없다(db):
    for i in range(tracking.MAX_PRODUCTS):
        db.add_product(None, str(10_000 + i), f"상품{i}")
    with pytest.raises(TrackingError, match="가득 찼어요"):
        start_tracking(None, LINK, fetch=fetch_ok, today=TODAY)


def test_해제한_상품을_다시_추가하면_재개된다(db):
    start_tracking(None, LINK, fetch=fetch_ok, today=TODAY)
    stop_tracking(None, LINK)
    assert db.products["97405013"]["is_active"] is False
    result = start_tracking(None, LINK, fetch=fetch_ok, today=TODAY)
    assert result.status == "reactivated" and db.products["97405013"]["is_active"] is True


def test_다나와_링크가_아니면_등록하지_않는다(db):
    with pytest.raises(TrackingError, match="다나와 상품 페이지 링크가 아닙니다"):
        start_tracking(None, "https://www.coupang.com/vp/products/1", fetch=fetch_ok)
    assert db.products == {}


def test_목표가가_0_이하면_거절(db):
    with pytest.raises(TrackingError, match="0보다 커야"):
        start_tracking(None, LINK, 0, fetch=fetch_ok)


def test_등록되지_않은_상품은_해제할_수_없다(db):
    with pytest.raises(TrackingError, match="등록되지 않은 상품"):
        stop_tracking(None, "12345678")


def test_추적_중인지_다나와_요청_없이_확인한다(db):
    assert not is_tracking(None, LINK)
    start_tracking(None, LINK, fetch=fetch_ok, today=TODAY)
    assert is_tracking(None, "https://m.danawa.com/product/product.html?code=97405013")
    stop_tracking(None, LINK)
    assert not is_tracking(None, LINK)

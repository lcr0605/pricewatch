"""대시보드: 로그인·보안·화면 렌더링. DB 대신 가짜 데이터를 쓴다."""

import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.web import auth, main

HTML = (Path(__file__).parent / "fixtures" / "product_jsonld.html").read_text(encoding="utf-8")
PASSWORD = "test-password"
TODAY = date(2026, 10, 22)

PRODUCT = {
    "id": 1, "pcode": "97405013", "name": "APPLE 에어팟 프로3", "category": "이어폰",
    "target_price": 280_000, "our_price": None, "cost": None, "is_active": True,
    "collected_on": TODAY, "price": 259_000, "offer_count": 150, "prev_price": 291_200,
    "option_changed": False,
}


class FakeRepo:
    def __init__(self):
        self.products = {PRODUCT["pcode"]: dict(PRODUCT)}
        self.snapshots = []

    # 조회
    def latest_collected_on(self, conn): return TODAY
    def product_overview(self, conn): return [p for p in self.products.values() if p["is_active"]]
    def recent_runs(self, conn, limit=30):
        return [{"id": 1, "started_at": datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc),
                 "finished_at": None, "total": 41, "succeeded": 40, "failed": 1, "status": "partial",
                 "errors": [{"pcode": "123", "reason": "가격 정보를 찾지 못했습니다"}]}]
    def run_stats(self, conn):
        return {"runs": 2, "since": datetime(2026, 10, 21, 7, 0, tzinfo=timezone.utc),
                "collected": 80, "attempted": 81}
    def daily_comparison(self, conn, on):
        return [{**PRODUCT, "listed_name": "에어팟 (1개)", "prev_listed_name": "에어팟 (1개)",
                 "prev_offer_count": 150, "min_30d": None, "days_30d": 1}]
    def price_history(self, conn, pcode, days=90):
        return [{"collected_on": date(2026, 10, 21), "lowest_price": 291_200, "offer_count": 164, "listed_name": "에어팟"},
                {"collected_on": TODAY, "lowest_price": 259_000, "offer_count": 150, "listed_name": "에어팟"}]

    # 추적
    def find_product_by_pcode(self, conn, pcode): return self.products.get(pcode)
    def count_active(self, conn): return sum(p["is_active"] for p in self.products.values())
    def add_product(self, conn, pcode, name, target_price=None, category=None):
        self.products[pcode] = {**PRODUCT, "id": len(self.products) + 1, "pcode": pcode, "name": name,
                                "target_price": target_price, "category": category, "is_active": True}
    def set_active(self, conn, pcode, active):
        if pcode not in self.products:
            return False
        self.products[pcode]["is_active"] = active
        return True
    def set_target_price(self, conn, pcode, target): self.products[pcode]["target_price"] = target
    def save_snapshot(self, conn, product_id, run_id, on, snap): self.snapshots.append((product_id, snap.lowest_price))


@pytest.fixture
def fake(monkeypatch):
    repo = FakeRepo()
    monkeypatch.setattr(main, "repo", repo)
    monkeypatch.setattr("app.tracking.repo", repo)
    monkeypatch.setattr("app.tracking._default_fetch", lambda pcode: HTML)
    monkeypatch.setattr(main, "_last_preview_at", 0.0)
    monkeypatch.setenv("APP_PASSWORD", PASSWORD)
    main.app.dependency_overrides[main.get_conn] = lambda: None
    auth.reset_lock()
    yield repo
    main.app.dependency_overrides.clear()


@pytest.fixture
def client(fake):
    return TestClient(main.app)


def csrf_of(client, path="/login") -> str:
    return re.search(r'name="csrf" value="([^"]+)"', client.get(path).text).group(1)


def login(client) -> None:
    response = client.post("/login", data={"password": PASSWORD, "csrf": csrf_of(client)}, follow_redirects=False)
    assert response.status_code == 303


# ---- 보안 ----

@pytest.mark.parametrize("path", ["/", "/products", "/products/97405013", "/runs"])
def test_로그인하지_않으면_로그인_화면으로_보낸다(client, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/login"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_API_문서는_공개하지_않는다(client, path):
    assert client.get(path).status_code == 404


def test_비밀번호가_틀리면_로그인_실패(client):
    response = client.post("/login", data={"password": "wrong", "csrf": csrf_of(client)})
    assert "비밀번호가 맞지 않아요" in response.text
    assert client.get("/", follow_redirects=False).status_code == 303


def test_5번_틀리면_잠긴다(client):
    for _ in range(5):
        response = client.post("/login", data={"password": "wrong", "csrf": csrf_of(client)})
    assert "잠깁니다" in response.text
    response = client.post("/login", data={"password": PASSWORD, "csrf": csrf_of(client)})
    assert "너무 많아요" in response.text


def test_CSRF_토큰이_없으면_거절(client):
    login(client)
    assert client.post("/products/97405013/stop", data={}).status_code == 403
    assert client.post("/products/97405013/stop", data={"csrf": "가짜"}).status_code == 403


def test_비밀번호가_설정되지_않으면_아무도_로그인_못함(client, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD")
    response = client.post("/login", data={"password": "", "csrf": csrf_of(client)})
    assert "APP_PASSWORD가 설정되지 않았어요" in response.text


# ---- 화면 ----

def test_홈에_오늘의_변화와_목표가_이하_상품이_보인다(client):
    login(client)
    text = client.get("/").text
    assert "큰 폭 인하" in text and "-11.1%" in text
    assert "목표가 이하인 상품" in text and "259,000원" in text


def test_상품_목록과_상세_운영_기록이_열린다(client):
    login(client)
    assert "APPLE 에어팟 프로3" in client.get("/products").text
    detail = client.get("/products/97405013").text
    assert "어제보다 32,200원 내렸어요" in detail and "chart.js" in detail
    runs = client.get("/runs").text
    assert "98.8" in runs and "가격 정보를 찾지 못했습니다" in runs


# ---- 링크로 추가 ----

def test_링크_미리보기_후_추적_시작(client, fake):
    login(client)
    csrf = csrf_of(client, "/products")
    client.post("/products/preview", data={"link": "https://prod.danawa.com/info/?pcode=11111111", "csrf": csrf})
    page = client.get("/products").text
    assert "이 상품이 맞나요?" in page and "276,600" in page  # 제안 목표가

    response = client.post("/products/add", data={"target_price": "270,000", "category": "이어폰", "csrf": csrf})
    assert "추적을 시작했어요" in response.text
    assert fake.products["11111111"]["target_price"] == 270_000
    assert fake.snapshots == [(2, 291_200)]  # 미리보기 응답으로 오늘 가격 저장


def test_다나와_링크가_아니면_오류_메시지(client):
    login(client)
    csrf = csrf_of(client, "/products")
    response = client.post("/products/preview", data={"link": "https://www.coupang.com/vp/products/1", "csrf": csrf})
    assert "다나와 상품 페이지 링크가 아닙니다" in response.text


def test_미리보기는_5초_간격으로_제한(client):
    login(client)
    csrf = csrf_of(client, "/products")
    client.post("/products/preview", data={"link": "11111111", "csrf": csrf})
    client.post("/products/cancel-preview", data={"csrf": csrf})
    response = client.post("/products/preview", data={"link": "22222222", "csrf": csrf})
    assert "요청이 너무 잦아요" in response.text


def test_이미_추적_중이면_미리보기_없이_안내(client):
    login(client)
    response = client.post("/products/preview", data={"link": "97405013", "csrf": csrf_of(client, "/products")})
    assert "이미 추적 중인 상품이에요" in response.text


def test_목표가_수정과_추적_해제(client, fake):
    login(client)
    csrf = csrf_of(client, "/products")
    client.post("/products/97405013/target", data={"target_price": "250,000", "csrf": csrf})
    assert fake.products["97405013"]["target_price"] == 250_000
    response = client.post("/products/97405013/stop", data={"csrf": csrf})
    assert "추적을 해제했어요" in response.text
    assert fake.products["97405013"]["is_active"] is False


def test_COOKIE_SECURE가_켜지면_쿠키에_Secure가_붙는다(monkeypatch):
    import importlib
    monkeypatch.setenv("COOKIE_SECURE", "1")
    secure_main = importlib.reload(main)
    try:
        client = TestClient(secure_main.app, base_url="https://testserver")
        response = client.get("/login")
        assert "secure" in response.headers["set-cookie"].lower()
    finally:
        monkeypatch.setenv("COOKIE_SECURE", "0")
        importlib.reload(main)

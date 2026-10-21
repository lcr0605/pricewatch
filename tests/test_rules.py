from app.analysis.rules import evaluate, evaluate_all


def row(**kw) -> dict:
    base = {
        "id": 1, "name": "샴푸 A", "category": "샴푸", "price": 10_000, "prev_price": 10_000,
        "listed_name": "샴푸 A (1개)", "prev_listed_name": "샴푸 A (1개)",
        "offer_count": 20, "prev_offer_count": 20, "target_price": None,
        "our_price": None, "cost": None, "min_30d": None, "days_30d": 0,
    }
    return base | kw


def kinds(r) -> list[str]:
    return [e.kind for e in evaluate(r)]


def test_변동이_없으면_이벤트_없음():
    assert kinds(row()) == []


def test_10퍼센트_이상_인하는_큰_폭_인하():
    events = evaluate(row(price=8_900))
    assert [e.kind for e in events] == ["big_drop"]
    assert round(events[0].change_rate, 3) == -0.11


def test_10퍼센트_이상_인상은_큰_폭_인상():
    assert kinds(row(price=11_000)) == ["big_rise"]


def test_10퍼센트_미만은_소폭_변동():
    assert kinds(row(price=9_500)) == ["small_change"]


def test_첫_수집일은_비교하지_않음():
    assert kinds(row(prev_price=None, prev_listed_name=None, prev_offer_count=None)) == []


def test_묶음_옵션이_바뀌면_가격_비교_대신_옵션_변경만():
    assert kinds(row(price=3_000, listed_name="샴푸 A (3개)")) == ["option_changed"]


def test_목표가는_처음_도달한_날만_알림():
    assert "target_reached" in kinds(row(price=9_000, prev_price=10_000, target_price=9_500))
    # 어제도 이미 목표가 이하였다면 반복 알림하지 않음
    assert "target_reached" not in kinds(row(price=9_000, prev_price=9_200, target_price=9_500))


def test_7일_이상_쌓였을_때만_30일_최저가_판단():
    assert "new_low" in kinds(row(price=9_800, min_30d=9_900, days_30d=10))
    assert "new_low" not in kinds(row(price=9_800, min_30d=9_900, days_30d=3))


def test_판매처_30퍼센트_이상_감소는_품절_신호():
    assert "offer_drop" in kinds(row(offer_count=12, prev_offer_count=20))
    assert "offer_drop" not in kinds(row(offer_count=3, prev_offer_count=4))  # 원래 적은 상품


def test_우리_판매가가_5퍼센트_넘게_비싸면_조정_검토와_마진():
    events = evaluate(row(our_price=11_000, cost=7_000))
    gap = [e for e in events if e.kind == "price_gap"][0]
    assert "10% 비쌈" in gap.detail and "마진 30%" in gap.detail


def test_중요도_순으로_정렬():
    rows = [row(id=1, price=9_500), row(id=2, price=8_000, target_price=8_500)]
    assert [e.kind for e in evaluate_all(rows)] == ["target_reached", "big_drop", "small_change"]

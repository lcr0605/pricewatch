"""가격 변동 판정 규칙. DB 없이 동작하는 순수 함수만 둔다 (테스트하기 쉽게).

입력 한 줄(row) = repo.daily_comparison의 결과 한 행.
"""

from dataclasses import dataclass

BIG_CHANGE_RATE = 0.10        # ±10% 이상이면 급변
OFFER_DROP_RATE = 0.30        # 판매처가 30% 이상 줄면 품절 신호
MIN_OFFERS_FOR_DROP = 5       # 판매처가 원래 적은 상품은 판단하지 않음
MIN_DAYS_FOR_NEW_LOW = 7      # 7일 이상 쌓였을 때만 "30일 최저가" 판단
PRICE_GAP_RATE = 0.05         # 우리 판매가가 경쟁가보다 5% 넘게 비싸면 조정 검토

# 보고서 정렬용 중요도 (클수록 위로)
SCORES = {
    "target_reached": 100,
    "big_drop": 80,
    "big_rise": 70,
    "new_low": 60,
    "offer_drop": 50,
    "price_gap": 40,
    "small_change": 20,
    "option_changed": 10,
}
# 즉시 알림을 보낼 종류 (나머지는 일일 보고서에만)
INSTANT_KINDS = {"target_reached", "big_drop", "big_rise"}


@dataclass(frozen=True)
class Event:
    kind: str
    product_id: int
    name: str
    category: str | None
    price: int
    prev_price: int | None = None
    change_rate: float | None = None
    detail: str = ""

    @property
    def score(self) -> int:
        return SCORES[self.kind]

    @property
    def instant(self) -> bool:
        return self.kind in INSTANT_KINDS


def _event(row: dict, kind: str, **extra) -> Event:
    return Event(
        kind=kind,
        product_id=row["id"],
        name=row["name"],
        category=row.get("category"),
        price=row["price"],
        prev_price=row.get("prev_price"),
        **extra,
    )


def evaluate(row: dict) -> list[Event]:
    """한 상품의 오늘 상황을 판정해 이벤트 목록을 돌려준다."""
    events: list[Event] = []
    price, prev = row["price"], row.get("prev_price")

    option_changed = (
        row.get("prev_listed_name") is not None
        and row.get("listed_name") is not None
        and row["prev_listed_name"] != row["listed_name"]
    )
    if option_changed:
        # 묶음 단위가 달라 가격을 비교하면 안 된다
        events.append(_event(row, "option_changed",
                             detail=f"{row['prev_listed_name']} → {row['listed_name']}"))
    elif prev:
        rate = (price - prev) / prev
        if rate <= -BIG_CHANGE_RATE:
            events.append(_event(row, "big_drop", change_rate=rate))
        elif rate >= BIG_CHANGE_RATE:
            events.append(_event(row, "big_rise", change_rate=rate))
        elif price != prev:
            events.append(_event(row, "small_change", change_rate=rate))

    # 목표가: 처음으로 목표가 이하가 된 날만 (매일 같은 알림 반복 방지)
    target = row.get("target_price")
    if target and price <= target and (prev is None or prev > target or option_changed):
        events.append(_event(row, "target_reached", detail=f"목표가 {target:,}원"))

    # 30일 최저가 갱신
    min_30d = row.get("min_30d")
    if (not option_changed and min_30d and row.get("days_30d", 0) >= MIN_DAYS_FOR_NEW_LOW
            and price < min_30d):
        events.append(_event(row, "new_low", detail=f"이전 30일 최저 {min_30d:,}원"))

    # 판매처 급감 (품절·재고 부족 신호)
    offers, prev_offers = row.get("offer_count"), row.get("prev_offer_count")
    if (offers is not None and prev_offers and prev_offers >= MIN_OFFERS_FOR_DROP
            and (prev_offers - offers) / prev_offers >= OFFER_DROP_RATE):
        events.append(_event(row, "offer_drop", detail=f"판매처 {prev_offers}곳 → {offers}곳"))

    # 우리 판매가가 경쟁 최저가보다 비싼 경우
    our_price = row.get("our_price")
    if our_price and price and our_price > price * (1 + PRICE_GAP_RATE):
        gap = (our_price - price) / price
        detail = f"우리 {our_price:,}원이 {gap:.0%} 비쌈"
        cost = row.get("cost")
        if cost:
            margin = (price - cost) / price
            detail += f", 경쟁가로 맞추면 마진 {margin:.0%}"
        events.append(_event(row, "price_gap", detail=detail))

    return events


def evaluate_all(rows: list[dict]) -> list[Event]:
    events = [event for row in rows for event in evaluate(row)]
    return sorted(events, key=lambda e: (-e.score, e.change_rate or 0))

"""수집한 값이 믿을 만한지 검사한다. 이상하면 저장하지 않고 실패로 기록한다."""

from app.collector.parser import ProductSnapshot

MIN_PRICE = 100
# 하루 만에 이만큼 넘게 바뀌면 잘못 읽었을 가능성이 크다 (다른 상품·옵션 가격 등)
MAX_DAILY_CHANGE_RATE = 0.7
# 하루 수집 중 이 비율을 넘게 실패하면 사이트 구조 변경을 의심한다
FAILURE_ALERT_RATE = 0.3


def check_snapshot(snapshot: ProductSnapshot, previous_price: int | None) -> list[str]:
    """문제 목록을 돌려준다. 빈 목록이면 정상."""
    problems = []
    if snapshot.lowest_price < MIN_PRICE:
        problems.append(f"가격이 너무 낮음: {snapshot.lowest_price}원")
    if previous_price:
        change = abs(snapshot.lowest_price - previous_price) / previous_price
        if change > MAX_DAILY_CHANGE_RATE:
            problems.append(
                f"전일 대비 변동이 비정상적으로 큼: {previous_price:,}원 → {snapshot.lowest_price:,}원"
            )
    return problems


def needs_inspection(total: int, failed: int) -> bool:
    """수집기 점검 알림을 보내야 하는지."""
    return total > 0 and failed / total > FAILURE_ALERT_RATE

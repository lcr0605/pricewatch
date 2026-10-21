"""규칙 기반 일일 보고서·즉시 알림 문장 만들기 (유료 API 없이 코드가 작성)."""

from datetime import date

from app.analysis.rules import Event

TELEGRAM_LIMIT = 4000  # 텔레그램 메시지 최대 4096자, 여유를 둠
MAX_LINES_PER_SECTION = 10

TITLES = {
    "target_reached": "🎯 목표가 도달",
    "big_drop": "📉 큰 폭 인하",
    "big_rise": "📈 큰 폭 인상",
    "new_low": "⭐ 30일 최저가",
    "offer_drop": "⚠️ 판매처 급감 (품절 신호)",
    "price_gap": "💡 가격 조정 검토",
    "small_change": "↕️ 소폭 변동",
    "option_changed": "🔁 기준 묶음 변경 (비교 제외)",
}
ADVICE = {
    "target_reached": "구매·가격 대응 검토",
    "big_drop": "경쟁사 할인 여부 확인",
    "big_rise": "가격 인상 여지 확인",
    "offer_drop": "재고 확보 기회",
}


def won(value: int) -> str:
    return f"{value:,}원"


def describe(event: Event) -> str:
    """이벤트 한 줄 설명."""
    text = f"{event.name} {won(event.price)}"
    if event.prev_price and event.change_rate is not None:
        text += f" ({event.change_rate:+.1%}, 전일 {won(event.prev_price)})"
    if event.detail:
        text += f" · {event.detail}"
    if event.kind in ADVICE:
        text += f" → {ADVICE[event.kind]}"
    return text


def headline(events: list[Event], total: int, compared: int) -> str:
    """보고서 첫 문장. compared = 어제 데이터가 있어 비교할 수 있는 상품 수."""
    if compared == 0:
        return f"첫 수집일이라 비교할 이전 데이터가 없습니다. 감시 상품 {total}개의 기준 가격을 저장했습니다."
    changed = {e.product_id for e in events if e.kind != "option_changed"}
    important = [e for e in events if e.score >= 50]
    if not changed:
        return f"오늘은 감시 상품 {total}개 모두 가격 변동이 없습니다."
    sentence = f"감시 상품 {total}개 중 {len(changed)}개에 변화가 있고, 주의할 항목은 {len(important)}건입니다."
    if important:
        sentence += f" 가장 중요한 건 {describe(important[0]).split(' → ')[0]}입니다."
    return sentence


def build_daily_report(on: date, events: list[Event], run: dict, compared: int) -> str:
    lines = [
        f"📊 PriceWatch 일일 보고서 · {on:%Y-%m-%d}",
        f"수집 {run['succeeded']}/{run['total']} 성공" + (f" · 실패 {run['failed']}건" if run["failed"] else ""),
        "",
        headline(events, run["total"], compared),
    ]
    for kind, title in TITLES.items():
        group = [e for e in events if e.kind == kind]
        if not group:
            continue
        lines += ["", f"{title} {len(group)}건"]
        lines += [f"• {describe(e)}" for e in group[:MAX_LINES_PER_SECTION]]
        if len(group) > MAX_LINES_PER_SECTION:
            lines.append(f"  외 {len(group) - MAX_LINES_PER_SECTION}건은 대시보드에서 확인")
    return fit(("\n".join(lines)).strip())


def build_instant_alert(event: Event) -> str:
    return f"{TITLES[event.kind]}\n{describe(event)}"


def build_inspection_alert(run: dict) -> str:
    reasons = "\n".join(f"• {e['pcode']}: {e['reason']}" for e in run["errors"][:5])
    return (
        "🛠 수집기 점검 필요\n"
        f"오늘 {run['total']}개 중 {run['failed']}개 수집 실패 (30% 초과). "
        "다나와 페이지 구조가 바뀌었을 수 있습니다.\n" + reasons
    )


def fit(text: str, limit: int = TELEGRAM_LIMIT) -> str:
    """텔레그램 길이 제한에 맞게 자른다."""
    if len(text) <= limit:
        return text
    return text[: limit - 30].rsplit("\n", 1)[0] + "\n… (이하 대시보드에서 확인)"

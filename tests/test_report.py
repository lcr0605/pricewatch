from datetime import date

from app.analysis.rules import Event
from app.report.daily import build_daily_report, build_inspection_alert, fit

RUN = {"total": 40, "succeeded": 40, "failed": 0, "errors": []}


def ev(kind, pid=1, price=9_000, prev=10_000, rate=-0.1, detail=""):
    return Event(kind=kind, product_id=pid, name=f"상품{pid}", category="샴푸",
                 price=price, prev_price=prev, change_rate=rate, detail=detail)


def test_변동이_없으면_없다고_말한다():
    text = build_daily_report(date(2026, 10, 22), [], RUN, compared=40)
    assert "40개 모두 가격 변동이 없습니다" in text
    assert "수집 40/40 성공" in text


def test_중요한_변동을_첫_문장과_섹션에_보여준다():
    events = [ev("big_drop", 1, 8_900, 10_000, -0.11), ev("small_change", 2, 9_800, 10_000, -0.02)]
    text = build_daily_report(date(2026, 10, 22), events, RUN, compared=40)
    assert "2개에 변화가 있고, 주의할 항목은 1건" in text
    assert "상품1 8,900원 (-11.0%, 전일 10,000원)" in text
    assert "→ 경쟁사 할인 여부 확인" in text
    assert text.index("큰 폭 인하") < text.index("소폭 변동")


def test_첫_수집일에는_변동_없음이_아니라_비교_불가라고_말한다():
    text = build_daily_report(date(2026, 10, 21), [], RUN, compared=0)
    assert "첫 수집일" in text and "변동이 없습니다" not in text


def test_수집기_점검_알림에_실패_원인을_담는다():
    run = {"total": 10, "failed": 4, "errors": [{"pcode": "1", "reason": "가격 정보를 찾지 못했습니다"}]}
    assert "가격 정보를 찾지 못했습니다" in build_inspection_alert(run)


def test_텔레그램_길이_제한에_맞게_자른다():
    text = "\n".join(f"줄 {i} " + "가" * 50 for i in range(200))
    assert len(fit(text)) <= 4000
    assert fit(text).endswith("(이하 대시보드에서 확인)")

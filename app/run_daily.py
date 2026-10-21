"""하루치 실행: 수집 → 분석 → 일일 보고서·알림. Railway Cron이 매일 09:00(KST)에 실행한다.

    python -m app.run_daily              # 수집부터 전부
    python -m app.run_daily --report     # 수집 없이 오늘 보고서만 다시 만들기

종료 코드: 0 = 정상, 1 = 실패율이 높아 점검 필요 (Railway에서 실패로 표시됨)
"""

import random
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.collector.fetch import FetchError, fetch_product_html, new_session
from app.collector.parser import ParseError, parse_product
from app.analysis.rules import evaluate_all
from app.collector.validate import check_snapshot, needs_inspection
from app.db import repo
from app.report import notify
from app.report.daily import build_daily_report, build_inspection_alert, build_instant_alert

KST = ZoneInfo("Asia/Seoul")
DELAY_SECONDS = (3, 5)  # 요청 사이 대기 (수집 정책)


def run() -> int:
    today = datetime.now(KST).date()
    conn = repo.connect()
    products = repo.active_products(conn)
    run_id = repo.start_run(conn)
    session = new_session()
    errors: list[dict] = []
    succeeded = 0

    for index, product in enumerate(products):
        if index:
            time.sleep(random.uniform(*DELAY_SECONDS))
        pcode = product["pcode"]
        try:
            snap = parse_product(fetch_product_html(session, pcode))
            prev = repo.previous_snapshot(conn, product["id"], today)
            problems = check_snapshot(
                snap,
                prev["lowest_price"] if prev else None,
                prev["listed_name"] if prev else None,
            )
            if problems:
                errors.append({"pcode": pcode, "reason": "; ".join(problems)})
                continue
            repo.save_snapshot(conn, product["id"], run_id, today, snap)
            succeeded += 1
            print(f"OK   {pcode} {snap.lowest_price:>10,}원  {snap.name}")
        except (FetchError, ParseError) as error:
            errors.append({"pcode": pcode, "reason": str(error)})
            print(f"FAIL {pcode} {error}")

    total = len(products)
    inspect = needs_inspection(total, len(errors))
    status = "failed" if inspect else ("partial" if errors else "success")
    repo.finish_run(conn, run_id, total, succeeded, errors, status)
    print(f"\n완료: {succeeded}/{total} 성공, 실패 {len(errors)}건, 상태 {status}")

    summary = {"total": total, "succeeded": succeeded, "failed": len(errors), "errors": errors}
    if inspect:
        message = build_inspection_alert(summary)
        notify.send(message)
        repo.save_alert(conn, run_id, "inspection", message)
    report(conn, run_id, today, summary)
    return 1 if inspect else 0


def report(conn, run_id: int | None, today, summary: dict) -> None:
    """분석 → 즉시 알림(중요 이벤트) → 일일 보고서."""
    rows = repo.daily_comparison(conn, today)
    events = evaluate_all(rows)
    compared = sum(1 for r in rows if r["prev_price"] is not None)
    for event in [e for e in events if e.instant]:
        message = build_instant_alert(event)
        notify.send(message)
        if run_id:
            repo.save_alert(conn, run_id, event.kind, message, event.product_id)
    notify.send(build_daily_report(today, events, summary, compared))


def report_only() -> None:
    today = datetime.now(KST).date()
    conn = repo.connect()
    total = len(repo.daily_comparison(conn, today))
    report(conn, None, today, {"total": total, "succeeded": total, "failed": 0, "errors": []})


if __name__ == "__main__":
    if "--report" in sys.argv:
        report_only()
        sys.exit(0)
    sys.exit(run())

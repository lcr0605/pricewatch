"""하루치 수집 실행. GitHub Actions가 매일 실행한다.

    python -m app.run_daily

종료 코드: 0 = 정상, 1 = 실패율이 높아 점검 필요 (GitHub Actions에서 실패로 표시됨)
"""

import random
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.collector.fetch import FetchError, fetch_product_html, new_session
from app.collector.parser import ParseError, parse_product
from app.collector.validate import check_snapshot, needs_inspection
from app.db import repo

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
    if inspect:
        print("실패율이 30%를 넘었습니다. 다나와 페이지 구조 변경 여부를 점검하세요.")
    return 1 if inspect else 0


if __name__ == "__main__":
    sys.exit(run())

"""감시 상품 관리 도구 (대시보드와 같은 app/tracking.py 로직 사용).

    python -m app.products search 에어팟                       # 다나와에서 상품 찾기
    python -m app.products add <다나와 링크|pcode> [목표가] [--category 샴푸]
    python -m app.products remove <다나와 링크|pcode>          # 추적 해제 (기록은 남김)
    python -m app.products list                                # 추적 중인 상품
    python -m app.products import seed/products.csv            # 목록 파일로 한 번에 등록
"""

import csv
import sys

from app.collector.fetch import SEARCH_URL, fetch_html, new_session
from app.collector.parser import parse_search
from app.tracking import TrackingError, is_tracking, preview, start_tracking, stop_tracking


def search(keyword: str) -> None:
    results = parse_search(fetch_html(new_session(), SEARCH_URL, params={"query": keyword}))
    for r in results[:15]:
        price = f"{r.price:,}원" if r.price else "-"
        print(f"{r.pcode:>12}  {price:>12}  {r.name}")


def add(link: str, target_price: int | None, category: str | None) -> None:
    from app.db import repo

    with repo.connect() as conn:
        # 이미 추적 중이면 다나와에 요청하지 않는다 (수집 정책: 요청 최소화)
        if not is_tracking(conn, link):
            info = preview(link)
            print(f"확인: {info.name} · 현재 최저가 {info.price:,}원 · 판매처 {info.snapshot.offer_count or '-'}곳")
            if target_price is None:
                print(f"      (목표가를 정하지 않았어요. 제안: {info.suggested_target:,}원)")
            print(start_tracking(conn, link, target_price, category, previewed=info).message)
        else:
            print(start_tracking(conn, link, target_price, category).message)


def remove(link: str) -> None:
    from app.db import repo

    with repo.connect() as conn:
        print(stop_tracking(conn, link))


def import_csv(path: str) -> None:
    """category,pcode,name 형식의 CSV로 등록. 다나와 요청 없이 DB에만 쓴다."""
    from app.db import repo

    with open(path, encoding="utf-8") as f, repo.connect() as conn:
        rows = list(csv.DictReader(f))
        for row in rows:
            repo.add_product(conn, row["pcode"], row["name"], category=row["category"])
    print(f"{len(rows)}개 등록")


def list_products() -> None:
    from app.db import repo

    with repo.connect() as conn:
        for p in repo.active_products(conn):
            print(f"{p['pcode']:>12}  {p['category'] or '-':<6}  {p['name']}")


def _parse_add_args(args: list[str]) -> tuple[str, int | None, str | None]:
    category = None
    if "--category" in args:
        i = args.index("--category")
        category = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    target = int(args[1].replace(",", "")) if len(args) > 1 else None
    return args[0], target, category


def main(argv: list[str]) -> int:
    command, *args = argv or ["help"]
    try:
        if command == "search" and args:
            search(" ".join(args))
        elif command == "add" and args:
            add(*_parse_add_args(args))
        elif command == "remove" and args:
            remove(args[0])
        elif command == "import" and args:
            import_csv(args[0])
        elif command == "list":
            list_products()
        else:
            print(__doc__)
    except TrackingError as error:
        print(f"⚠️  {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

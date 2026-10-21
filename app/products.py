"""감시 상품 관리 도구.

    python -m app.products search 에어팟          # 다나와에서 상품코드 찾기
    python -m app.products add 97405013 280000    # 상품 등록 (목표가는 선택)
    python -m app.products list                   # 등록된 상품 보기
    python -m app.products import seed/products.csv   # 목록 파일로 한 번에 등록
"""

import csv
import sys

from app.collector.fetch import SEARCH_URL, fetch_html, fetch_product_html, new_session
from app.collector.parser import parse_product, parse_search


def search(keyword: str) -> None:
    results = parse_search(fetch_html(new_session(), SEARCH_URL, params={"query": keyword}))
    for r in results[:15]:
        price = f"{r.price:,}원" if r.price else "-"
        print(f"{r.pcode:>12}  {price:>12}  {r.name}")


def add(pcode: str, target_price: str | None = None) -> None:
    from app.db import repo

    snap = parse_product(fetch_product_html(new_session(), pcode))
    with repo.connect() as conn:
        repo.add_product(conn, pcode, snap.name, int(target_price) if target_price else None)
    print(f"등록: {pcode} {snap.name} (현재 최저가 {snap.lowest_price:,}원)")


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


if __name__ == "__main__":
    command, *args = sys.argv[1:] or ["help"]
    if command == "search" and args:
        search(" ".join(args))
    elif command == "add" and args:
        add(*args[:2])
    elif command == "import" and args:
        import_csv(args[0])
    elif command == "list":
        list_products()
    else:
        print(__doc__)

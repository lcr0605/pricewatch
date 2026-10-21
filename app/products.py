"""감시 상품 관리 도구.

    python -m app.products search 에어팟          # 다나와에서 상품코드 찾기
    python -m app.products add 97405013 280000    # 상품 등록 (목표가는 선택)
    python -m app.products list                   # 등록된 상품 보기
"""

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


def list_products() -> None:
    from app.db import repo

    with repo.connect() as conn:
        for p in repo.active_products(conn):
            print(f"{p['pcode']:>12}  {p['name']}")


if __name__ == "__main__":
    command, *args = sys.argv[1:] or ["help"]
    if command == "search" and args:
        search(" ".join(args))
    elif command == "add" and args:
        add(*args[:2])
    elif command == "list":
        list_products()
    else:
        print(__doc__)

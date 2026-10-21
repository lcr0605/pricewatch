"""DB 읽기·쓰기. SQL은 이 파일에만 둔다."""

import json
import os
from datetime import date

import psycopg
from psycopg.rows import dict_row

from app.collector.parser import ProductSnapshot
from app.config import load_env


def connect() -> psycopg.Connection:
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 환경변수가 없습니다 (.env.example 참고)")
    return psycopg.connect(url, row_factory=dict_row, autocommit=True)


def active_products(conn) -> list[dict]:
    return conn.execute(
        "select id, pcode, name, category from products where is_active order by id"
    ).fetchall()


def previous_snapshot(conn, product_id: int, before: date) -> dict | None:
    """직전 수집값 (lowest_price, listed_name)."""
    return conn.execute(
        """select lowest_price, listed_name from price_snapshots
           where product_id = %s and collected_on < %s
           order by collected_on desc limit 1""",
        (product_id, before),
    ).fetchone()


def start_run(conn) -> int:
    return conn.execute("insert into runs default values returning id").fetchone()["id"]


def save_snapshot(
    conn, product_id: int, run_id: int | None, on: date, snap: ProductSnapshot
) -> None:
    """같은 날 다시 실행하면 그날 값을 덮어쓴다."""
    conn.execute(
        """insert into price_snapshots
             (product_id, run_id, collected_on, lowest_price, listed_name, offer_count, rating, review_count, source)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (product_id, collected_on) do update set
             run_id = excluded.run_id, lowest_price = excluded.lowest_price, listed_name = excluded.listed_name,
             offer_count = excluded.offer_count, rating = excluded.rating,
             review_count = excluded.review_count, source = excluded.source,
             collected_at = now()""",
        (product_id, run_id, on, snap.lowest_price, snap.name, snap.offer_count,
         snap.rating, snap.review_count, snap.source),
    )


def finish_run(conn, run_id: int, total: int, succeeded: int, errors: list[dict], status: str) -> None:
    conn.execute(
        """update runs set finished_at = now(), total = %s, succeeded = %s, failed = %s,
                  status = %s, errors = %s::jsonb
           where id = %s""",
        (total, succeeded, len(errors), status, json.dumps(errors, ensure_ascii=False), run_id),
    )


def add_product(
    conn, pcode: str, name: str, target_price: int | None = None, category: str | None = None
) -> None:
    conn.execute(
        """insert into products (pcode, name, target_price, category) values (%s, %s, %s, %s)
           on conflict (pcode) do update set name = excluded.name,
             target_price = coalesce(excluded.target_price, products.target_price),
             category = coalesce(excluded.category, products.category)""",
        (pcode, name, target_price, category),
    )


def count_active(conn) -> int:
    return conn.execute("select count(*) as n from products where is_active").fetchone()["n"]


def find_product_by_pcode(conn, pcode: str) -> dict | None:
    return conn.execute(
        "select id, pcode, name, category, target_price, is_active from products where pcode = %s",
        (pcode,),
    ).fetchone()


def set_active(conn, pcode: str, active: bool) -> bool:
    """추적 시작/해제. 가격 기록은 지우지 않는다. 해당 상품이 있으면 True."""
    row = conn.execute(
        "update products set is_active = %s where pcode = %s returning id", (active, pcode)
    ).fetchone()
    return row is not None


def set_target_price(conn, pcode: str, target_price: int | None) -> None:
    conn.execute("update products set target_price = %s where pcode = %s", (target_price, pcode))

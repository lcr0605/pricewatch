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
        "select id, pcode, name from products where is_active order by id"
    ).fetchall()


def previous_price(conn, product_id: int, before: date) -> int | None:
    row = conn.execute(
        """select lowest_price from price_snapshots
           where product_id = %s and collected_on < %s
           order by collected_on desc limit 1""",
        (product_id, before),
    ).fetchone()
    return row["lowest_price"] if row else None


def start_run(conn) -> int:
    return conn.execute("insert into runs default values returning id").fetchone()["id"]


def save_snapshot(conn, product_id: int, run_id: int, on: date, snap: ProductSnapshot) -> None:
    """같은 날 다시 실행하면 그날 값을 덮어쓴다."""
    conn.execute(
        """insert into price_snapshots
             (product_id, run_id, collected_on, lowest_price, offer_count, rating, review_count, source)
           values (%s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (product_id, collected_on) do update set
             run_id = excluded.run_id, lowest_price = excluded.lowest_price,
             offer_count = excluded.offer_count, rating = excluded.rating,
             review_count = excluded.review_count, source = excluded.source,
             collected_at = now()""",
        (product_id, run_id, on, snap.lowest_price, snap.offer_count,
         snap.rating, snap.review_count, snap.source),
    )


def finish_run(conn, run_id: int, total: int, succeeded: int, errors: list[dict], status: str) -> None:
    conn.execute(
        """update runs set finished_at = now(), total = %s, succeeded = %s, failed = %s,
                  status = %s, errors = %s::jsonb
           where id = %s""",
        (total, succeeded, len(errors), status, json.dumps(errors, ensure_ascii=False), run_id),
    )


def add_product(conn, pcode: str, name: str, target_price: int | None = None) -> None:
    conn.execute(
        """insert into products (pcode, name, target_price) values (%s, %s, %s)
           on conflict (pcode) do update set name = excluded.name,
             target_price = coalesce(excluded.target_price, products.target_price)""",
        (pcode, name, target_price),
    )

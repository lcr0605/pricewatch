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


def daily_comparison(conn, on: date) -> list[dict]:
    """감시 상품별 오늘 값과 직전 수집값, 최근 30일 최저가를 한 번에 가져온다."""
    return conn.execute(
        """
        with today as (
            select * from price_snapshots where collected_on = %(on)s
        ),
        prev as (
            select distinct on (product_id) product_id, lowest_price, listed_name, offer_count
            from price_snapshots
            where collected_on < %(on)s
            order by product_id, collected_on desc
        ),
        history as (
            select product_id,
                   min(lowest_price) as min_30d,
                   count(*)          as days_30d
            from price_snapshots
            where collected_on < %(on)s and collected_on >= %(on)s - 30
            group by product_id
        )
        select p.id, p.pcode, p.name, p.category, p.target_price, p.our_price, p.cost,
               t.lowest_price  as price,       t.listed_name as listed_name, t.offer_count,
               pv.lowest_price as prev_price,  pv.listed_name as prev_listed_name,
               pv.offer_count  as prev_offer_count,
               h.min_30d, coalesce(h.days_30d, 0) as days_30d
        from products p
        join today t      on t.product_id = p.id
        left join prev pv on pv.product_id = p.id
        left join history h on h.product_id = p.id
        where p.is_active
        order by p.category, p.name
        """,
        {"on": on},
    ).fetchall()


def save_alert(conn, run_id: int, kind: str, message: str, product_id: int | None = None) -> None:
    conn.execute(
        "insert into alerts (product_id, run_id, kind, message) values (%s, %s, %s, %s)",
        (product_id, run_id, kind, message),
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


# ---- 대시보드 조회 ----

def product_overview(conn) -> list[dict]:
    """추적 중인 상품별 최신 가격과 직전 가격."""
    return conn.execute(
        """
        with latest as (
            select distinct on (product_id) product_id, collected_on, lowest_price, offer_count, listed_name
            from price_snapshots
            order by product_id, collected_on desc
        ),
        prev as (
            select distinct on (s.product_id) s.product_id, s.lowest_price, s.listed_name
            from price_snapshots s
            join latest l on l.product_id = s.product_id and s.collected_on < l.collected_on
            order by s.product_id, s.collected_on desc
        )
        select p.id, p.pcode, p.name, p.category, p.target_price, p.our_price, p.cost,
               l.collected_on, l.lowest_price as price, l.offer_count,
               pv.lowest_price as prev_price,
               coalesce(pv.listed_name <> l.listed_name, false) as option_changed
        from products p
        left join latest l on l.product_id = p.id
        left join prev pv  on pv.product_id = p.id
        where p.is_active
        order by p.category nulls last, p.name
        """
    ).fetchall()


def price_history(conn, pcode: str, days: int = 90) -> list[dict]:
    return conn.execute(
        """select s.collected_on, s.lowest_price, s.offer_count, s.listed_name
           from price_snapshots s join products p on p.id = s.product_id
           where p.pcode = %s and s.collected_on >= current_date - %s
           order by s.collected_on""",
        (pcode, days),
    ).fetchall()


def latest_collected_on(conn) -> date | None:
    return conn.execute("select max(collected_on) as d from price_snapshots").fetchone()["d"]


def recent_runs(conn, limit: int = 30) -> list[dict]:
    return conn.execute(
        """select id, started_at, finished_at, total, succeeded, failed, status, errors
           from runs order by started_at desc limit %s""",
        (limit,),
    ).fetchall()


def run_stats(conn) -> dict:
    """운영 통계: 실행 일수, 누적 수집 건수, 평균 성공률."""
    return conn.execute(
        """select count(*) as runs,
                  min(started_at) as since,
                  coalesce(sum(succeeded), 0) as collected,
                  coalesce(sum(total), 0) as attempted
           from runs where status <> 'running'"""
    ).fetchone()


# ---- 중복 실행 방지 ----

RUN_LOCK_KEY = 20261021  # 하루치 실행 전용 잠금 번호 (아무 고정 숫자)


def try_run_lock(conn) -> bool:
    """다른 하루치 실행이 진행 중이면 False. 잠금은 연결이 끊기면 자동으로 풀린다."""
    return conn.execute("select pg_try_advisory_lock(%s) as ok", (RUN_LOCK_KEY,)).fetchone()["ok"]


def succeeded_today(conn, today: date) -> dict | None:
    """오늘(KST) 성공 또는 일부 성공한 실행이 있으면 그 기록. 실패(점검 필요)는 다시 실행 가능."""
    return conn.execute(
        """select id, started_at, succeeded, total from runs
           where status in ('success', 'partial')
             and (started_at at time zone 'Asia/Seoul')::date = %s
           order by started_at desc limit 1""",
        (today,),
    ).fetchone()

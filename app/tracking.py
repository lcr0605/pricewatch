"""감시 상품 등록·해제. 대시보드와 CLI가 함께 쓰는 핵심 로직.

흐름: 링크 붙여넣기 → preview(이름·현재가 확인) → start_tracking(등록 + 오늘 가격 저장)
오류는 화면에 그대로 보여줄 수 있는 한국어 메시지를 담은 TrackingError 하나로 통일한다.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

from app.collector.fetch import FetchError, extract_pcode, fetch_product_html, new_session
from app.collector.parser import ParseError, ProductSnapshot, parse_product
from app.db import repo

MAX_PRODUCTS = 50            # 수집 정책: 하루 50개 이하
TARGET_DISCOUNT = 0.05       # 목표가 제안: 현재가보다 5% 낮게
KST = ZoneInfo("Asia/Seoul")

# 상품명 끝의 묶음 표기. 목록에는 빼고 보여준다 (가격 기록의 listed_name에는 그대로 남음)
_BUNDLE_SUFFIX = re.compile(r"\s*\(\d+\s*(개|팩|롤|매|입|개입|세트|병|박스)\)\s*$")


class TrackingError(Exception):
    """사용자에게 그대로 보여줄 수 있는 오류."""


@dataclass(frozen=True)
class Preview:
    pcode: str
    name: str
    snapshot: ProductSnapshot
    suggested_target: int

    @property
    def price(self) -> int:
        return self.snapshot.lowest_price


@dataclass(frozen=True)
class TrackingResult:
    status: str        # added | reactivated | already_tracking
    preview: Preview | None
    message: str


Fetcher = Callable[[str], str]  # pcode -> 상품 페이지 HTML


def _default_fetch(pcode: str) -> str:
    return fetch_product_html(new_session(), pcode)


def display_name(listed_name: str) -> str:
    return _BUNDLE_SUFFIX.sub("", listed_name).strip()


def suggest_target(price: int) -> int:
    """현재가보다 5% 낮은 값을 100원 단위로 내림."""
    return max(100, int(price * (1 - TARGET_DISCOUNT)) // 100 * 100)


def _pcode(link: str) -> str:
    try:
        return extract_pcode(link)
    except ValueError as error:
        raise TrackingError(str(error)) from error


def preview(link: str, fetch: Fetcher | None = None) -> Preview:
    """다나와에서 상품 정보를 확인만 한다. DB에는 쓰지 않는다."""
    pcode = _pcode(link)
    # 기본값을 실행 시점에 찾는다 (정의 시점에 고정하면 테스트에서 바꿔 끼울 수 없음)
    fetch = fetch or _default_fetch
    try:
        snapshot = parse_product(fetch(pcode))
    except FetchError as error:
        raise TrackingError("다나와에서 상품 정보를 가져오지 못했어요. 잠시 후 다시 시도해 주세요") from error
    except ParseError as error:
        raise TrackingError("상품 가격을 찾지 못했어요. 판매가 종료된 상품인지 확인해 주세요") from error
    return Preview(
        pcode=pcode,
        name=display_name(snapshot.name),
        snapshot=snapshot,
        suggested_target=suggest_target(snapshot.lowest_price),
    )


def _check_target(target_price: int | None) -> None:
    if target_price is not None and target_price <= 0:
        raise TrackingError("목표가는 0보다 커야 해요")


def is_tracking(conn, link: str) -> bool:
    """이미 추적 중인 상품인지. 화면에서 미리보기 전에 확인해 다나와 요청을 아낀다."""
    product = repo.find_product_by_pcode(conn, _pcode(link))
    return bool(product and product["is_active"])


def start_tracking(
    conn,
    link: str,
    target_price: int | None = None,
    category: str | None = None,
    *,
    previewed: Preview | None = None,
    fetch: Fetcher | None = None,
    today: date | None = None,
) -> TrackingResult:
    """등록하고 오늘 가격을 바로 저장한다.

    previewed: 화면에서 미리보기로 받은 결과. 같은 상품이면 다나와에 다시 요청하지 않는다.
    """
    _check_target(target_price)
    pcode = _pcode(link)
    existing = repo.find_product_by_pcode(conn, pcode)

    if existing and existing["is_active"]:
        if target_price is not None:
            repo.set_target_price(conn, pcode, target_price)
        note = f" 목표가를 {target_price:,}원으로 바꿨어요." if target_price else ""
        return TrackingResult("already_tracking", None, f"이미 추적 중인 상품이에요.{note}")

    if repo.count_active(conn) >= MAX_PRODUCTS:
        raise TrackingError(f"추적 상품이 {MAX_PRODUCTS}개로 가득 찼어요. 하나를 해제한 뒤 추가해 주세요")

    info = previewed if previewed and previewed.pcode == pcode else preview(link, fetch)
    repo.add_product(conn, pcode, info.name, target_price, category)
    repo.set_active(conn, pcode, True)
    product = repo.find_product_by_pcode(conn, pcode)
    repo.save_snapshot(conn, product["id"], None, today or datetime.now(KST).date(), info.snapshot)

    status = "reactivated" if existing else "added"
    verb = "다시 추적을 시작했어요" if existing else "추적을 시작했어요"
    return TrackingResult(status, info, f"{info.name} {verb}. 오늘 가격 {info.price:,}원부터 기록해요.")


def stop_tracking(conn, link_or_pcode: str) -> str:
    """추적 해제. 가격 기록은 남긴다."""
    pcode = _pcode(link_or_pcode)
    if not repo.set_active(conn, pcode, False):
        raise TrackingError("등록되지 않은 상품이에요")
    return "추적을 해제했어요. 지난 가격 기록은 그대로 남아 있어요."

"""다나와 페이지 요청. 수집 정책은 app/collector/CLAUDE.md 참고."""

import re
import time
from urllib.parse import parse_qs, urlparse

import requests

PRODUCT_URL = "https://prod.danawa.com/info/?pcode={pcode}"
SEARCH_URL = "https://search.danawa.com/dsearch.php"

# robots.txt가 막아둔 경로. 이 경로로는 절대 요청하지 않는다.
FORBIDDEN_PATH_PREFIXES = ("/api/", "/bridge/", "/info/ajax/", "/list/ajax/", "/community/")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)
TIMEOUT_SECONDS = 15
MAX_RETRIES = 2


class FetchError(Exception):
    pass


def assert_allowed(url: str) -> None:
    path = urlparse(url).path
    if any(path.startswith(prefix) for prefix in FORBIDDEN_PATH_PREFIXES):
        raise ValueError(f"robots.txt 금지 경로입니다: {path}")


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"})
    return session


def fetch_html(session: requests.Session, url: str, params: dict | None = None) -> str:
    """실패하면 MAX_RETRIES번 다시 시도한다 (5초, 10초 대기)."""
    assert_allowed(url)
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt:
            time.sleep(5 * attempt)
        try:
            response = session.get(url, params=params, timeout=TIMEOUT_SECONDS)
            if response.status_code == 200 and response.text.strip():
                return response.text
            last_error = FetchError(f"HTTP {response.status_code}, 응답 길이 {len(response.text)}")
        except requests.RequestException as error:
            last_error = error
    raise FetchError(f"{url} 요청 실패: {last_error}")


def fetch_product_html(session: requests.Session, pcode: str) -> str:
    return fetch_html(session, PRODUCT_URL.format(pcode=pcode))


def extract_pcode(text: str) -> str:
    """다나와 상품 링크나 상품코드에서 상품코드(숫자)를 꺼낸다.

    PC: https://prod.danawa.com/info/?pcode=97405013&cate=...
    모바일: https://m.danawa.com/product/product.html?code=97405013
    숫자만: 97405013
    """
    text = (text or "").strip()
    if re.fullmatch(r"\d{4,12}", text):
        return text
    if not text:
        raise ValueError("다나와 상품 링크를 입력해 주세요")

    url = urlparse(text if "://" in text else f"https://{text}")
    host = (url.hostname or "").lower()
    if not (host == "danawa.com" or host.endswith(".danawa.com")):
        raise ValueError("다나와 상품 페이지 링크가 아닙니다")

    query = parse_qs(url.query)
    for key in ("pcode", "code"):
        value = (query.get(key) or [""])[0]
        if re.fullmatch(r"\d{4,12}", value):
            return value
    raise ValueError("링크에서 상품코드를 찾지 못했습니다. 다나와 상품 상세 페이지 링크인지 확인해 주세요")

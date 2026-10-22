"""토스 스타일 대시보드.

    uvicorn app.web.main:app --reload

화면: 홈 · 추적 상품(링크로 추가) · 상품 상세(가격 추이) · 운영 기록
"""

import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.analysis.rules import evaluate_all
from app.collector.parser import ProductSnapshot
from app.config import load_env
from app.db import repo
from app.tracking import Preview, TrackingError, is_tracking, preview, start_tracking, stop_tracking
from app.web import auth

load_env()
KST = ZoneInfo("Asia/Seoul")
PREVIEW_INTERVAL_SECONDS = 5  # 다나와 미리보기 요청 최소 간격 (수집 정책)
_last_preview_at = 0.0

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)  # API 문서 비공개
# 배포 서버(https)에서는 COOKIE_SECURE=1 → 쿠키를 https 연결에서만 전송. 로컬(http) 개발은 기본값 0
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
app.add_middleware(
    SessionMiddleware, secret_key=auth.session_secret(), same_site="lax",
    https_only=COOKIE_SECURE, max_age=60 * 60 * 12,
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


# ---- 표시용 필터 ----

def won(value) -> str:
    return "-" if value is None else f"{int(value):,}원"


def change_rate(price, prev):
    if not price or not prev:
        return None
    return (price - prev) / prev


def kst(value) -> str:
    return value.astimezone(KST).strftime("%m.%d %H:%M") if value else "-"


templates.env.filters.update(won=won, kst=kst)
templates.env.globals.update(change_rate=change_rate)


# ---- 공통 ----

class LoginRequired(Exception):
    pass


@app.exception_handler(LoginRequired)
async def _to_login(request: Request, exc: LoginRequired):
    return RedirectResponse("/login", status_code=303)


def require_login(request: Request) -> None:
    if not auth.is_logged_in(request):
        raise LoginRequired()


def get_conn():
    with repo.connect() as conn:
        yield conn


def render(request: Request, name: str, **context) -> HTMLResponse:
    context.update(
        request=request,
        csrf=auth.csrf_token(request),
        flash=request.session.pop("flash", None),
        nav=name.split(".")[0],
    )
    return templates.TemplateResponse(request, name, context)


def flash(request: Request, message: str, kind: str = "ok") -> None:
    request.session["flash"] = {"message": message, "kind": kind}


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


# ---- 로그인 ----

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html", error=None)


@app.post("/login")
def login(request: Request, password: str = Form(""), csrf: str = Form("")):
    auth.check_csrf(request, csrf)
    error = auth.try_login(request, password)
    if error:
        return render(request, "login.html", error=error)
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request, csrf: str = Form("")):
    auth.check_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---- 홈 ----

@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def home(request: Request, conn=Depends(get_conn)):
    latest = repo.latest_collected_on(conn)
    rows = repo.daily_comparison(conn, latest) if latest else []
    events = evaluate_all(rows)
    overview = repo.product_overview(conn)
    runs = repo.recent_runs(conn, 1)
    return render(
        request, "home.html",
        latest=latest,
        compared=sum(1 for r in rows if r["prev_price"] is not None),
        events=[e for e in events if e.kind != "small_change"][:8],
        small_changes=sum(1 for e in events if e.kind == "small_change"),
        below_target=[p for p in overview if p["target_price"] and p["price"] and p["price"] <= p["target_price"]],
        tracked=len(overview),
        last_run=runs[0] if runs else None,
        stats=repo.run_stats(conn),
    )


# ---- 추적 상품 ----

@app.get("/products", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def products_page(request: Request, conn=Depends(get_conn)):
    overview = repo.product_overview(conn)
    groups: dict[str, list] = {}
    for p in overview:
        groups.setdefault(p["category"] or "기타", []).append(p)
    return render(
        request, "products.html",
        groups=groups, tracked=len(overview),
        preview=request.session.get("preview"),
    )


def _snapshot_to_session(info: Preview) -> dict:
    s = info.snapshot
    return {
        "pcode": info.pcode, "name": info.name, "suggested_target": info.suggested_target,
        "snapshot": {"name": s.name, "lowest_price": s.lowest_price, "offer_count": s.offer_count,
                     "rating": s.rating, "review_count": s.review_count, "source": s.source},
    }


def _preview_from_session(data: dict) -> Preview:
    return Preview(pcode=data["pcode"], name=data["name"],
                   snapshot=ProductSnapshot(**data["snapshot"]),
                   suggested_target=data["suggested_target"])


@app.post("/products/preview", dependencies=[Depends(require_login)])
def product_preview(request: Request, link: str = Form(""), csrf: str = Form(""), conn=Depends(get_conn)):
    global _last_preview_at
    auth.check_csrf(request, csrf)
    request.session.pop("preview", None)
    try:
        if is_tracking(conn, link):
            flash(request, "이미 추적 중인 상품이에요", "info")
            return RedirectResponse("/products", status_code=303)
        wait = PREVIEW_INTERVAL_SECONDS - (time.monotonic() - _last_preview_at)
        if wait > 0:
            raise TrackingError(f"요청이 너무 잦아요. {int(wait) + 1}초 뒤에 다시 시도해 주세요")
        _last_preview_at = time.monotonic()
        request.session["preview"] = _snapshot_to_session(preview(link)) | {"link": link}
    except TrackingError as error:
        flash(request, str(error), "error")
    return RedirectResponse("/products#add", status_code=303)


@app.post("/products/add", dependencies=[Depends(require_login)])
def product_add(
    request: Request,
    target_price: str = Form(""),
    category: str = Form(""),
    csrf: str = Form(""),
    conn=Depends(get_conn),
):
    auth.check_csrf(request, csrf)
    data = request.session.pop("preview", None)
    if not data:
        flash(request, "먼저 다나와 링크를 확인해 주세요", "error")
        return RedirectResponse("/products#add", status_code=303)
    try:
        target = int(target_price.replace(",", "")) if target_price.strip() else None
        result = start_tracking(
            conn, data["link"], target, category.strip() or None,
            previewed=_preview_from_session(data),
        )
        flash(request, result.message)
    except ValueError:
        flash(request, "목표가는 숫자로 입력해 주세요", "error")
    except TrackingError as error:
        flash(request, str(error), "error")
    return RedirectResponse("/products", status_code=303)


@app.post("/products/cancel-preview", dependencies=[Depends(require_login)])
def cancel_preview(request: Request, csrf: str = Form("")):
    auth.check_csrf(request, csrf)
    request.session.pop("preview", None)
    return RedirectResponse("/products", status_code=303)


@app.post("/products/{pcode}/target", dependencies=[Depends(require_login)])
def update_target(request: Request, pcode: str, target_price: str = Form(""),
                  csrf: str = Form(""), conn=Depends(get_conn)):
    auth.check_csrf(request, csrf)
    try:
        target = int(target_price.replace(",", "")) if target_price.strip() else None
        if target is not None and target <= 0:
            raise ValueError
        repo.set_target_price(conn, pcode, target)
        flash(request, f"목표가를 {won(target)}으로 바꿨어요" if target else "목표가를 지웠어요")
    except ValueError:
        flash(request, "목표가는 0보다 큰 숫자로 입력해 주세요", "error")
    return RedirectResponse(f"/products/{pcode}", status_code=303)


@app.post("/products/{pcode}/stop", dependencies=[Depends(require_login)])
def stop(request: Request, pcode: str, csrf: str = Form(""), conn=Depends(get_conn)):
    auth.check_csrf(request, csrf)
    try:
        flash(request, stop_tracking(conn, pcode))
    except TrackingError as error:
        flash(request, str(error), "error")
    return RedirectResponse("/products", status_code=303)


@app.get("/products/{pcode}", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def product_detail(request: Request, pcode: str, conn=Depends(get_conn)):
    product = repo.find_product_by_pcode(conn, pcode)
    if not product:
        flash(request, "등록되지 않은 상품이에요", "error")
        return RedirectResponse("/products", status_code=303)
    history = repo.price_history(conn, pcode)
    prices = [h["lowest_price"] for h in history]
    return render(
        request, "product.html",
        product=product, history=history,
        latest=history[-1] if history else None,
        prev=history[-2] if len(history) > 1 else None,
        low=min(prices) if prices else None, high=max(prices) if prices else None,
        chart={
            "labels": [h["collected_on"].strftime("%m.%d") for h in history],
            "prices": prices,
            "offers": [h["offer_count"] for h in history],
        },
    )


# ---- 운영 기록 ----

@app.get("/runs", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def runs_page(request: Request, conn=Depends(get_conn)):
    runs = repo.recent_runs(conn, 60)
    stats = repo.run_stats(conn)
    rate = stats["collected"] / stats["attempted"] if stats["attempted"] else None
    since = stats["since"]
    days = (datetime.now(KST).date() - since.astimezone(KST).date()).days + 1 if since else 0
    return render(request, "runs.html", runs=runs, stats=stats, rate=rate, days=days)

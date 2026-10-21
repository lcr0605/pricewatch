"""로그인(비밀번호 1개)과 CSRF 방어.

- 비밀번호: 환경변수 APP_PASSWORD. 설정되지 않으면 아무도 로그인할 수 없다.
- 세션: 서명된 쿠키 (SESSION_SECRET). 없으면 실행할 때마다 새로 만들어 재시작 시 로그아웃된다.
- 로그인 5회 연속 실패 시 1분간 잠금 (무차별 대입 방지).
- 모든 POST 폼은 세션의 csrf 토큰과 일치해야 한다.
"""

import hmac
import os
import secrets
import time

from fastapi import HTTPException, Request

MAX_FAILURES = 5
LOCK_SECONDS = 60

_failures = 0
_locked_until = 0.0


def session_secret() -> str:
    return os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def csrf_token(request: Request) -> str:
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(24)
    return request.session["csrf"]


def check_csrf(request: Request, token: str) -> None:
    expected = request.session.get("csrf", "")
    if not expected or not hmac.compare_digest(expected, token or ""):
        raise HTTPException(status_code=403, detail="잘못된 요청입니다. 페이지를 새로고침해 주세요")


def try_login(request: Request, password: str) -> str | None:
    """성공하면 None, 실패하면 화면에 보여줄 메시지."""
    global _failures, _locked_until
    now = time.monotonic()
    if now < _locked_until:
        return f"로그인 시도가 너무 많아요. {int(_locked_until - now) + 1}초 뒤에 다시 시도해 주세요"

    expected = os.environ.get("APP_PASSWORD", "")
    if not expected:
        return "서버에 APP_PASSWORD가 설정되지 않았어요"
    if hmac.compare_digest(expected.encode(), (password or "").encode()):
        _failures = 0
        request.session.clear()
        request.session["user"] = "admin"
        return None

    _failures += 1
    if _failures >= MAX_FAILURES:
        _failures = 0
        _locked_until = now + LOCK_SECONDS
        return f"비밀번호가 {MAX_FAILURES}번 틀렸어요. {LOCK_SECONDS}초 동안 잠깁니다"
    return "비밀번호가 맞지 않아요"


def reset_lock() -> None:
    """테스트용."""
    global _failures, _locked_until
    _failures, _locked_until = 0, 0.0

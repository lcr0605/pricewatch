"""텔레그램 알림 (무료). 토큰이 없으면 보내지 않고 화면에만 출력한다."""

import os

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def is_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def send(text: str) -> bool:
    """성공하면 True. 설정이 없거나 실패하면 False (수집 자체는 멈추지 않는다)."""
    if not is_configured():
        print("[텔레그램 미설정: 아래 내용을 보내지 않음]\n" + text + "\n")
        return False
    try:
        response = requests.post(
            API.format(token=os.environ["TELEGRAM_BOT_TOKEN"], method="sendMessage"),
            json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text,
                  "disable_web_page_preview": True},
            timeout=15,
        )
        if response.ok:
            return True
        print(f"텔레그램 전송 실패: HTTP {response.status_code} {response.text[:200]}")
    except requests.RequestException as error:
        print(f"텔레그램 전송 실패: {error}")
    return False


def find_chat_id() -> str | None:
    """봇에게 메시지를 한 번 보낸 뒤 실행하면 대화방 ID를 찾아준다."""
    response = requests.get(
        API.format(token=os.environ["TELEGRAM_BOT_TOKEN"], method="getUpdates"), timeout=15
    )
    for update in reversed(response.json().get("result", [])):
        chat = (update.get("message") or {}).get("chat")
        if chat:
            return str(chat["id"])
    return None


if __name__ == "__main__":
    # python -m app.report.notify  → 봇에게 메시지를 보낸 대화방 ID 출력
    from app.config import load_env

    load_env()
    chat_id = find_chat_id()
    print(chat_id or "대화방을 찾지 못했습니다. 봇에게 아무 메시지나 먼저 보내주세요.")

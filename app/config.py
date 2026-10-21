"""환경변수 읽기. 로컬에서는 .env 파일을, 서버(GitHub Actions·Railway)에서는 실제 환경변수를 쓴다."""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env() -> None:
    """.env 값을 환경변수로 올린다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))

# PriceWatch
다나와 경쟁 상품 가격을 매일 수집·비교 → 텔레그램 알림 + 규칙 기반 일일 보고서 + 토스 스타일 대시보드.

## 명령 (가상환경: `source .venv/bin/activate`, Python 3.11)
- 설치: `pip install -r requirements.txt`
- 테스트: `pytest -q` (커밋 전 필수 통과)
- 하루치 실행(수집→분석→보고서·알림): `python -m app.run_daily` / 다시 수집: `--force` / 보고서만: `--report`
  - 오늘 이미 성공했거나 다른 실행 중(DB advisory lock)이면 다나와 요청 없이 건너뜀 → 실행 환경을 옮겨도 중복 실행 안전
- 텔레그램 대화방 ID 찾기: `python -m app.report.notify`
- 상품 관리: `python -m app.products search 키워드` / `add <다나와 링크|pcode> [목표가] [--category 분류]` / `remove` / `list`
- 상품 등록·해제 로직은 `app/tracking.py` 하나 (CLI·대시보드 공용)
- 대시보드: `uvicorn app.web.main:app --reload` (로그인 비밀번호 `APP_PASSWORD`)

## 구조
app/collector 수집 · app/analysis 판정 · app/report 보고서·알림 · app/web 화면 · app/db 스키마·SQL · tests/fixtures HTML 샘플

## 배포
- 매일 수집: GitHub Actions `daily.yml` (UTC 23:47 = KST 08:47, 정각 혼잡 회피, 수동 실행 시 mode=report로 보고서만)
- 대시보드: Railway 웹 서비스(`railway.json`)
- CI: GitHub Actions `ci.yml` (PR마다 테스트, 비밀값 없음)
- 비밀값은 GitHub Secrets·Railway 변수로만. 워크플로는 `permissions: contents: read`, 외부 Action은 커밋 해시 고정, 입력값은 env로 전달

## 절대 규칙
- 유료 API 호출 추가 금지 (운영 비용 0원)
- 비밀값은 환경변수로만. `.env` 커밋 금지, 새 변수는 `.env.example`에 추가
- 다나와 수집은 app/collector/CLAUDE.md를 따름
- 수집한 다나와 데이터를 저장소에 올리지 않음 (fixture는 최소 발췌만)
- 파서 수정 시 tests/fixtures로 테스트 추가
- 테스트는 외부 네트워크 요청 금지 (`tests/conftest.py`가 차단). 외부 호출은 함수 인자로 바꿔 끼울 수 있게 작성
- 작업은 브랜치 → PR. PR 본문: 요구사항 / AI 결과에서 고친 점 / 테스트 결과

# 수집 규칙 (다나와)
근거: docs/collection-policy.md

- 요청은 `fetch.py`의 `fetch_html`만 사용. 금지 경로(`/api/`, `/bridge/`, `/info/ajax/`, `/list/ajax/`, `/community/`)는 `assert_allowed`가 막음. 우회 금지
- 하루 1회, 상품 50개 이하, 요청 간 3~5초 대기 (`run_daily.DELAY_SECONDS`)
- 캡차·로그인·차단을 우회하는 코드 금지 (프록시, IP 변경, 헤더 위장 강화 등)
- 가격은 JSON-LD(`offers.lowPrice`) 우선, 없으면 `em.prc_c`. 둘 다 없으면 `ParseError`
- 값 검증은 `validate.py`: 100원 미만, 전일 대비 70% 초과 변동은 저장하지 않고 실패로 기록
- 최저가는 상품마다 "대표 묶음 옵션" 기준. 옵션 이름(`listed_name`)이 바뀐 날은 가격 비교 대상이 아님
- 하루 실패율 30% 초과 = 구조 변경 의심 → 종료 코드 1 + 점검 알림
- 구조가 바뀌면: 새 페이지에서 필요한 부분만 발췌해 `tests/fixtures/`에 추가 → 테스트 먼저 작성 → 파서 수정

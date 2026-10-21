# 대시보드 규칙 (FastAPI + Jinja + Tailwind CDN + Chart.js)
- 모든 화면은 로그인 필수 (`require_login`). 예외는 `/login`, `/healthz`뿐
- 모든 POST 폼에 `<input type="hidden" name="csrf" value="{{ csrf }}">` 필수, 핸들러 첫 줄에서 `auth.check_csrf`
- API 문서(`/docs`, `/redoc`, `/openapi.json`)는 비공개 유지
- 상품 추가·해제는 `app/tracking.py`만 호출. 여기서 다나와에 직접 요청하지 않음
- 다나와 미리보기는 최소 5초 간격 (`PREVIEW_INTERVAL_SECONDS`), 미리보기 결과는 세션에 저장해 등록 시 재요청 안 함

## 토스 디자인
- 폰트 Pretendard, 배경 `toss-bg #f2f4f6`, 본문 `toss-text #191f28`, 보조 `toss-sub #4e5968`
- 흰 카드(`.card`, rounded-3xl) + 큰 숫자(`.num`, tabular-nums), 한 화면 한 메시지, 제목은 말하듯이 ("오늘 주의할 변화가 3건 있어요")
- 가격 **인상 = 빨강(`.up`), 인하 = 파랑(`.down`)** (국내 관례)
- 주 버튼: `h-14 rounded-2xl bg-toss-blue`, 입력: `h-12 rounded-xl bg-toss-bg`
- 모바일 우선: 기본은 세로 배치, `sm:`부터 가로. 세로(flex-col) 안에서 `flex-1` 금지 (높이가 찌그러짐) → `w-full sm:flex-1`
- 모바일은 하단 탭, `sm:` 이상은 상단 메뉴

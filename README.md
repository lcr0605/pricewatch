# PriceWatch

경쟁 상품 가격을 매일 자동으로 수집·비교해서, 변동과 목표가 도달을 알려주는 가격 모니터링 자동화 시스템입니다.

> **데모:** https://pricewatch-ess2.onrender.com (로그인 필요 · 무료 서버라 한동안 접속이 없으면 첫 화면까지 1분 정도 걸려요)

## 자동화하는 업무
| | 내용 |
|---|---|
| **자동화 전** | 담당자가 매일 다나와에서 상품을 하나씩 검색 → 최저가·판매처 수를 엑셀에 옮겨 적고 어제와 비교 → 보고 (하루 1~2시간) |
| **자동화 후** | 매일 아침 8:47 자동 수집·비교 → 중요한 변동만 알림 + 일일 보고서. 담당자는 읽고 대응만 결정 |

## 구성
- **수집**: 다나와 상품 페이지의 구조화 데이터(JSON-LD) 우선, 없으면 화면 가격. 값 검증 후 저장
- **저장**: Supabase PostgreSQL (모든 테이블 RLS 적용)
- **실행**: GitHub Actions 예약 실행 (매일 08:47 KST, 정각 혼잡 회피, 무료·실행 기록 공개), 실패율 30% 초과 또는 실행 오류 시 텔레그램 알림
- **대시보드**: FastAPI + Tailwind, 토스 스타일. 다나와 링크 붙여넣기로 상품 추가, 가격 추이 차트, 운영 기록 (로그인·CSRF·로그인 잠금)
- **알림**: 텔레그램 즉시 알림(목표가 도달·±10% 급변) + 규칙 기반 일일 보고서
- **테스트**: pytest (외부 요청 차단), GitHub Actions에서 PR마다 실행
- **배포**: 대시보드 Render 무료 웹 서비스, 매일 수집 GitHub Actions, DB Supabase 무료
- **운영 비용**: 0원 (유료 API 미사용, 무료 인프라만 사용)

## 실행
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DATABASE_URL 입력
pytest -q
python -m app.products search 샴푸
python -m app.products add "https://prod.danawa.com/info/?pcode=97405013" 280000   # 링크로 추적 시작
python -m app.run_daily
uvicorn app.web.main:app --reload   # 대시보드 http://localhost:8000
```

## 수집 정책
비영리 포트폴리오 용도, 하루 1회·소량, robots.txt 금지 경로 미사용. 자세한 내용은 [docs/collection-policy.md](docs/collection-policy.md)

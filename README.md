# PriceWatch

경쟁 상품 가격을 매일 자동으로 수집·비교해서, 변동과 목표가 도달을 알려주는 가격 모니터링 자동화 시스템입니다.

> 🚧 개발 중 (1주차: 수집기·DB·매일 실행)

## 자동화하는 업무
| | 내용 |
|---|---|
| **자동화 전** | 담당자가 매일 다나와에서 상품을 하나씩 검색 → 최저가·판매처 수를 엑셀에 옮겨 적고 어제와 비교 → 보고 (하루 1~2시간) |
| **자동화 후** | 매일 09:00 자동 수집·비교 → 중요한 변동만 알림 + 일일 보고서. 담당자는 읽고 대응만 결정 |

## 구성
- **수집**: 다나와 상품 페이지의 구조화 데이터(JSON-LD) 우선, 없으면 화면 가격. 값 검증 후 저장
- **저장**: Supabase PostgreSQL (모든 테이블 RLS 적용)
- **실행**: Railway Cron (매일 09:00 KST), 실패율 30% 초과 시 점검 필요로 기록
- **테스트**: pytest, GitHub Actions에서 PR마다 실행
- **운영 비용**: 0원 (유료 API 미사용)

## 실행
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DATABASE_URL 입력
pytest -q
python -m app.products search 샴푸
python -m app.run_daily
```

## 수집 정책
비영리 포트폴리오 용도, 하루 1회·소량, robots.txt 금지 경로 미사용. 자세한 내용은 [docs/collection-policy.md](docs/collection-policy.md)

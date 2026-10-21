# 운영 기록

실제로 운영하며 발견한 문제와 대응을 기록합니다.

## 2026-10-21 · 첫 수집 (40/40 성공)
- 생활용품 10개 카테고리 × 4개 = 40개 등록 (`seed/products.csv`)
- **발견:** 다나와 상품 상세 페이지의 최저가는 상품마다 **대표 묶음 옵션** 기준이다.
  - 예: 크리오 칫솔은 검색 결과에서 1개 920원, 상세 페이지 최저가는 30개 묶음 10,390원
  - 다나와가 대표 옵션을 바꾸면(30개 → 10개), 실제 가격 변동이 없어도 "급락"으로 잘못 판단할 수 있음
- **대응:** 그날 가격이 어떤 옵션 기준인지(`price_snapshots.listed_name`)를 함께 저장하고, 옵션이 바뀐 날은 가격 급변 검사를 하지 않도록 수정 (`validate.check_snapshot`, 테스트 2개 추가)

## 2026-10-21 · Railway 장애로 매일 실행 환경을 GitHub Actions로 이전
- **상황:** Railway CLI 로그인·프로젝트 생성이 실패. 상태 페이지 확인 결과 Railway 전체 장애(Major Outage, 07:24 UTC~, "Dashboard and API unavailable, builds paused")
- **판단:** 복구 시점을 알 수 없고, 내일 09:00 수집이 빠지면 운영 기록에 구멍이 생김. 또 Railway의 기존 설정 파일 방식(`railway.json`)은 2026-12-01 지원 종료 예정인데, 새 방식(`.railway/railway.ts`) 문서에는 cron 설정이 없음
- **대응:** 매일 실행을 GitHub Actions(`daily.yml`)로 이전. Railway에는 대시보드만 배포 예정
  - 무료, 실행 기록이 저장소 Actions 탭에 공개로 남음
  - 비밀값은 GitHub Secrets로만 주입. `.env`에서 표준 입력으로 등록해 화면·명령어 기록에 남기지 않음
  - 최소 권한(`contents: read`), 외부 Action 커밋 해시 고정, 수동 실행 입력값은 환경변수로 전달(스크립트 주입 방지)
  - 실행 자체가 실패하면 텔레그램으로 실패 알림
- **남은 일:** Railway 복구 후 대시보드 배포, 2026-12-01 전에 `railway.json` → `.railway/railway.ts` 이전

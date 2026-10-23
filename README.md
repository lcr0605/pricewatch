# PriceWatch

다나와 경쟁 상품 가격을 매일 자동으로 수집·비교해서 중요한 변동만 알려주는 가격 모니터링 자동화입니다.

**데모:** https://web-production-b130ef.up.railway.app (로그인 필요)

<p>
  <img src="docs/images/desktop-home.png" alt="홈 화면" width="66%">
  <img src="docs/images/mobile-home.png" alt="모바일 홈 화면" width="30%">
</p>

## 자동화한 업무
- **전:** 매일 상품 40여 개를 직접 검색해 엑셀에 옮겨 적고 어제와 비교 (하루 1~2시간)
- **후:** 매일 아침 자동 수집·비교 → 중요한 변동만 알림, 담당자는 대응만 결정

## 운영 (2026-10-23 기준)
3일 운영 · 실행 3회 모두 성공 · 누적 수집 122건 · 테스트 79개 · 유료 API 0원

## 구성
- **수집:** Python, GitHub Actions 매일 실행 (중복 실행 방지)
- **판정:** 급변·목표가 도달·30일 최저가 등 규칙 7종
- **저장:** Supabase PostgreSQL
- **대시보드:** FastAPI, Railway 배포 (로그인·CSRF 보안)

## 더 보기
- [운영 기록](docs/ops-log.md): 운영 중 생긴 문제와 대응
- [AI 활용 기록](docs/ai-log.md): Claude Code에 맡긴 일과 직접 고친 점
- [수집 정책](docs/collection-policy.md): 비영리, 하루 1회·소량, robots.txt 준수

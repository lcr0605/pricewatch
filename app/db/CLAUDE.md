# DB 규칙 (Supabase PostgreSQL)
- 스키마 원본은 `schema.sql` 하나. 변경 시 `migrations/NNN_설명.sql`을 추가하고 `schema.sql`도 함께 고침
- SQL은 `repo.py`에만 작성. 다른 모듈은 repo 함수를 호출
- 모든 테이블은 RLS 활성화 + 정책 없음 (공개 키 접근 차단). 새 테이블도 동일하게
- 연결은 `DATABASE_URL`(Session pooler, 5432). Transaction pooler(6543)는 쓰지 않음
- 테이블: products(감시 상품) · price_snapshots(상품당 하루 1건) · runs(실행 기록) · alerts(보낸 알림)

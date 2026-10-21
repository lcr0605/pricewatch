-- 감시 상품에 카테고리 추가 (대시보드 그룹 표시용)
alter table products add column if not exists category text;

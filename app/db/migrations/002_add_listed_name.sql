-- 그날 가격이 어떤 묶음 옵션 기준인지 저장 (예: "... 칫솔 (30개)")
-- 대표 옵션이 바뀐 날은 가격 변동으로 보지 않기 위해 사용
alter table price_snapshots add column if not exists listed_name text;

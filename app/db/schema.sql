-- PriceWatch 스키마. Supabase SQL Editor에 그대로 붙여 넣어 실행한다.
-- 변경 규칙은 app/db/CLAUDE.md 참고.

-- 감시 상품
create table if not exists products (
    id             bigserial primary key,
    pcode          text not null unique,          -- 다나와 상품코드
    name           text not null,
    target_price   integer,                       -- 이 가격 이하로 내려가면 알림
    our_price      integer,                       -- 선택: 우리 판매가
    cost           integer,                       -- 선택: 원가 (마진 계산용)
    is_active      boolean not null default true,
    created_at     timestamptz not null default now()
);

-- 하루 실행 기록 (운영 로그)
create table if not exists runs (
    id             bigserial primary key,
    started_at     timestamptz not null default now(),
    finished_at    timestamptz,
    total          integer not null default 0,
    succeeded      integer not null default 0,
    failed         integer not null default 0,
    status         text not null default 'running', -- running | success | partial | failed
    errors         jsonb not null default '[]'::jsonb  -- [{pcode, reason}]
);

-- 날짜별 가격 (상품당 하루 1건)
create table if not exists price_snapshots (
    id             bigserial primary key,
    product_id     bigint not null references products(id) on delete cascade,
    run_id         bigint references runs(id) on delete set null,
    collected_on   date not null,
    lowest_price   integer not null check (lowest_price > 0),
    offer_count    integer,                       -- 판매처 수
    rating         numeric(2, 1),
    review_count   integer,
    source         text not null,                 -- jsonld | html
    collected_at   timestamptz not null default now(),
    unique (product_id, collected_on)
);
create index if not exists price_snapshots_product_date
    on price_snapshots (product_id, collected_on desc);

-- 보낸 알림 (2주차부터 사용)
create table if not exists alerts (
    id             bigserial primary key,
    product_id     bigint references products(id) on delete cascade,
    run_id         bigint references runs(id) on delete set null,
    kind           text not null,                 -- target_reached | big_change | inspection
    message        text not null,
    sent_at        timestamptz not null default now()
);

-- 보안: Supabase 공개 키(publishable key)로 테이블에 접근하지 못하게 막는다.
-- 정책(policy)을 만들지 않으면 공개 키로는 아무것도 읽고 쓸 수 없다.
-- 앱은 DB 직접 연결(DATABASE_URL)로 접근하므로 영향 없음.
alter table products        enable row level security;
alter table runs            enable row level security;
alter table price_snapshots enable row level security;
alter table alerts          enable row level security;

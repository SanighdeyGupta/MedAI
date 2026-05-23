-- MedAI Postgres schema (Day 2)
-- Run this in Supabase SQL Editor on a fresh project.
-- Idempotent: safe to re-run.

create extension if not exists pg_trgm;

------------------------------------------------------------------
-- Platforms (1mg, PharmEasy, Netmeds, Apollo)
------------------------------------------------------------------
create table if not exists platforms (
  id        text primary key,
  name      text not null,
  trust     numeric(3, 2) not null check (trust between 0 and 1),
  color     text not null,
  gradient  text not null,
  domain    text not null
);

------------------------------------------------------------------
-- Medicines (catalog)
------------------------------------------------------------------
create table if not exists medicines (
  id                text primary key,
  name              text not null,
  composition       text not null,
  manufacturer      text not null,
  pack              text not null,
  rx_required       boolean not null default false,
  nppa_ceiling_inr  numeric(10, 2),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  -- v2: provenance of the row.
  --   'seed'       — loaded from data/medicines.json by scripts/seed.ts
  --   'discovered' — created on the fly by /api/discover (user-driven)
  --   'manual'     — inserted by a maintainer via Supabase Table Editor
  created_via       text not null default 'seed' check (created_via in ('seed','discovered','manual'))
);

-- For existing tables (created before the v2 column landed), add it idempotently.
do $$ begin
  if not exists (
    select 1 from information_schema.columns
    where table_name = 'medicines' and column_name = 'created_via'
  ) then
    alter table medicines add column created_via text not null default 'seed'
      check (created_via in ('seed','discovered','manual'));
  end if;
end $$;

create index if not exists medicines_name_trgm
  on medicines using gin (name gin_trgm_ops);

create index if not exists medicines_composition_trgm
  on medicines using gin (composition gin_trgm_ops);

------------------------------------------------------------------
-- Prices (per-platform offers; one row per medicine × platform)
------------------------------------------------------------------
create table if not exists prices (
  id              bigserial primary key,
  medicine_id     text not null references medicines(id) on delete cascade,
  platform_id     text not null references platforms(id) on delete cascade,
  price           numeric(10, 2) not null,
  mrp             numeric(10, 2) not null,
  delivery_days   int not null check (delivery_days >= 0),
  in_stock        boolean not null default true,
  return_days     int not null default 7,
  url             text not null,
  fetched_at      timestamptz not null default now(),
  stale_after     timestamptz not null default (now() + interval '12 hours'),
  unique (medicine_id, platform_id)
);

create index if not exists prices_medicine_id_idx on prices (medicine_id);
create index if not exists prices_fetched_at_idx  on prices (fetched_at desc);

------------------------------------------------------------------
-- Scrape log (audit trail; debug + rate-limit telemetry)
------------------------------------------------------------------
create table if not exists scrape_log (
  id            bigserial primary key,
  platform_id   text references platforms(id),
  medicine_id   text references medicines(id),
  status        text not null check (status in ('success','blocked','not_found','error','rate_limited')),
  http_status   int,
  duration_ms   int,
  via           text,                 -- 'httpx', 'patchright', 'scraperapi', etc.
  error_message text,
  fetched_at    timestamptz not null default now()
);

create index if not exists scrape_log_fetched_at_idx on scrape_log (fetched_at desc);

------------------------------------------------------------------
-- Daily budget guard for the on-demand ScraperAPI route
------------------------------------------------------------------
create table if not exists daily_budget (
  date                date primary key,
  scraperapi_used     int not null default 0,
  scraperapi_budget   int not null default 25
);

------------------------------------------------------------------
-- Fuzzy search function (pg_trgm)
--
-- Called from the Next.js search API. Combines:
--   1. prefix match on name (very strong)
--   2. trigram similarity on name + composition
--
------------------------------------------------------------------
create or replace function search_medicines(q text, max_results int default 8)
returns setof medicines
language sql
stable
as $$
  with q_norm as (select lower(trim(q)) as q),
  scored as (
    select
      m.*,
      greatest(
        case when lower(m.name) = (select q from q_norm) then 1.0
             when lower(m.name) like (select q from q_norm) || '%' then 0.95
             else 0
        end,
        similarity(lower(m.name), (select q from q_norm)) * 0.9,
        similarity(lower(m.composition), (select q from q_norm)) * 0.7
      ) as match_score
    from medicines m
  )
  select id, name, composition, manufacturer, pack, rx_required, nppa_ceiling_inr, created_at, updated_at
  from scored
  where match_score > 0.18
  order by match_score desc, name asc
  limit max_results;
$$;

------------------------------------------------------------------
-- Helper view: latest offers joined with platform metadata
------------------------------------------------------------------
create or replace view v_medicine_offers as
select
  m.id            as medicine_id,
  m.name          as medicine_name,
  m.composition,
  m.pack,
  m.manufacturer,
  m.rx_required,
  m.nppa_ceiling_inr,
  p.platform_id,
  pl.name         as platform_name,
  pl.trust        as platform_trust,
  p.price,
  p.mrp,
  p.delivery_days,
  p.in_stock,
  p.return_days,
  p.url,
  p.fetched_at,
  p.stale_after
from medicines m
join prices p     on p.medicine_id = m.id
join platforms pl on pl.id = p.platform_id;

------------------------------------------------------------------
-- Row-Level Security
-- Public anon role: SELECT on medicines, platforms, prices, view.
-- Writes go via service_role from the seed script + GitHub Actions.
------------------------------------------------------------------
alter table medicines  enable row level security;
alter table platforms  enable row level security;
alter table prices     enable row level security;
alter table scrape_log enable row level security;
alter table daily_budget enable row level security;

drop policy if exists "public read medicines"  on medicines;
drop policy if exists "public read platforms"  on platforms;
drop policy if exists "public read prices"     on prices;

create policy "public read medicines" on medicines for select using (true);
create policy "public read platforms" on platforms for select using (true);
create policy "public read prices"    on prices    for select using (true);
-- scrape_log + daily_budget: no public policy = service role only.

------------------------------------------------------------------
-- v2: scheduled cleanup of scrape_log (>30 days deleted nightly)
--
-- pg_cron is available on Supabase out of the box. The job runs at
-- 02:30 UTC (08:00 IST) which is off-peak for Indian users.
------------------------------------------------------------------
create extension if not exists pg_cron;

-- Unschedule any previous version of the job to keep this block idempotent.
do $$
declare j record;
begin
  for j in select jobid from cron.job where jobname = 'scrape-log-cleanup' loop
    perform cron.unschedule(j.jobid);
  end loop;
end $$;

select cron.schedule(
  'scrape-log-cleanup',
  '30 2 * * *',
  $$ delete from scrape_log where fetched_at < now() - interval '30 days' $$
);

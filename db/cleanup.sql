-- v2 migration: scheduled cleanup + medicines.created_via column.
-- Idempotent: safe to re-run.
--
-- HOW TO APPLY:
--   1. Open Supabase Dashboard -> SQL Editor -> New query.
--   2. Paste this file's contents and click Run.
--   3. Verify with:
--        select * from cron.job where jobname = 'scrape-log-cleanup';
--        select column_name from information_schema.columns
--          where table_name = 'medicines' and column_name = 'created_via';
--
-- TO ROLLBACK the cron job (keep the column):
--   select cron.unschedule(jobid)
--     from cron.job where jobname = 'scrape-log-cleanup';

------------------------------------------------------------------
-- 1) medicines.created_via: track row provenance
------------------------------------------------------------------
do $$ begin
  if not exists (
    select 1 from information_schema.columns
    where table_name = 'medicines' and column_name = 'created_via'
  ) then
    alter table medicines add column created_via text not null default 'seed'
      check (created_via in ('seed','discovered','manual'));
  end if;
end $$;

------------------------------------------------------------------
-- 2) pg_cron: nightly scrape_log cleanup (rows > 30 days deleted)
------------------------------------------------------------------
create extension if not exists pg_cron;

-- Drop any previous version of the job, then schedule fresh.
do $$
declare j record;
begin
  for j in select jobid from cron.job where jobname = 'scrape-log-cleanup' loop
    perform cron.unschedule(j.jobid);
  end loop;
end $$;

select cron.schedule(
  'scrape-log-cleanup',
  '30 2 * * *',  -- 02:30 UTC = 08:00 IST, off-peak
  $$ delete from scrape_log where fetched_at < now() - interval '30 days' $$
);

------------------------------------------------------------------
-- 3) Verify
------------------------------------------------------------------
-- Confirm the job is scheduled:
select jobid, jobname, schedule, command
from cron.job
where jobname = 'scrape-log-cleanup';

-- Test the cleanup query (should affect 0 rows on a fresh DB):
-- explain (analyze, format text)
-- delete from scrape_log where fetched_at < now() - interval '30 days';

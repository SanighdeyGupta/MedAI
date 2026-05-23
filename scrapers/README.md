# Scrapers

Per-pharmacy scrapers that refresh the `prices` table in Supabase.

## Architecture
- Each pharmacy is a subclass of [`PharmacyScraper`](base.py). The base class centralises ToS hygiene: `robots.txt` check, 1 req/sec/domain rate limit, real-Chrome User-Agent.
- A scraper's `.scrape(medicine)` is **never allowed to raise** — errors become `ScrapeResult(status="error", error_message=...)` so one bad medicine doesn't kill the run.
- Every attempt (success or failure) is logged to the `scrape_log` table for telemetry.
- Successful results upsert into `prices` on the `(medicine_id, platform_id)` composite key. The website picks up the new values on the next request.

## Running locally

Prereqs: `.env.local` set up (see [../SETUP.md](../SETUP.md)).

```
py -3.11 -m pip install -r scrapers/requirements.txt
py -3.11 -m scrapers.run --site netmeds --limit 25
```

Useful flags:
- `--dry-run` — fetch + match, but don't write to DB. Good for selector tuning.
- `--limit N` — only scrape the first N medicines (default 25).

## Per-site notes

| Site | Technique | Endpoint | robots.txt |
|---|---|---|---|
| Netmeds | `httpx` against Fynd platform JSON API | `/ext/search/application/api/v1.0/products?q=…` | `/api/service/` allowed; `/ext/` not disallowed |
| PharmEasy *(Day 4)* | `httpx` + selectolax against SSR HTML | `/search/all?name=…` | TBD |
| Apollo *(Day 4)* | `httpx` against `__NEXT_DATA__` blob | `/medicine/{slug}` | TBD |
| 1mg *(Day 6)* | Patchright + ScraperAPI fallback | Cloudflare-gated | strict; ScraperAPI is the budget pressure-release |

## GitHub Actions

[`scrape-netmeds.yml`](../.github/workflows/scrape-netmeds.yml) runs every 6h on cron + manual dispatch. Public-repo Actions minutes are unlimited on standard runners.

Required repo secrets (Settings → Secrets and variables → Actions):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

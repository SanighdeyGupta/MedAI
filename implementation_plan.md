# Medicine Price Finder — Revised Implementation Plan

## Context

The first-draft plan for a medicine price comparison web app (1mg, PharmEasy, Netmeds, Apollo Pharmacy) had structural problems. Constraints: **strictly free tier**, public deployment as an open-source portfolio project, and the best possible data-acquisition strategy across scraping, APIs, and public datasets.

Deep research (web + 2025-2026 scraping benchmarks + Indian ToS/case-law survey) surfaced three structural problems in the draft:

1. **The scraper has no viable home on free tier.** Vercel functions cap at ~50 MB unzipped; full Chromium is ~280 MB. The plan never named where Playwright actually runs.
2. **`playwright-stealth` / `puppeteer-extra-plugin-stealth` was deprecated in Feb 2025** and is now beaten by Cloudflare. The community moved to Patchright, nodriver, and Camoufox.
3. **The four target sites have wildly different protection levels** — treating them with the same heavy Playwright tool wastes effort on the easy three and under-delivers on the hard one. Concretely:
   - **1mg** = Cloudflare Bot Management (hard).
   - **PharmEasy** = CloudFront + custom origin, returns full HTML to plain `curl` (trivial).
   - **Netmeds** = openresty, `robots.txt` *explicitly allows* `/api/service/` (officially scrapable).
   - **Apollo** = Next.js with prices embedded in `__NEXT_DATA__` JSON (trivial, no WAF).

Plus the draft skipped the always-on public data backbone (**NPPA DPCO ceiling prices**, **Jan Aushadhi generic MRPs**) — both free, legal, and usable as a fallback when every scraper is down.

The revised plan reshapes the architecture around: **public data as the backbone, GitHub Actions as the always-on scheduled scraper, Supabase Postgres as a single store, and ScraperAPI free credits as the on-demand pressure-release for 1mg.**

---

## Recommended Architecture

### One-line summary
Next.js on Vercel reads pre-scraped prices from Supabase Postgres. A scheduled GitHub Actions workflow runs Python scrapers every 6 hours (per-site, parallel, isolated failures) and writes prices into Postgres. NPPA + Jan Aushadhi public data ships as a static JSON seed so the app is useful even with every scraper down.

### Component map

| Layer | Choice | Free-tier limit | Why |
|---|---|---|---|
| Frontend + API routes | **Next.js 15 App Router** on **Vercel Hobby** | unlimited static, 100 GB bandwidth, 60s function timeout | No scraper lives here — fits comfortably |
| Database | **Supabase Postgres (free)** | 500 MB DB, 5 GB egress, pauses only after 1 week idle | Single store. `pg_trgm` for fuzzy medicine search. Replaces both Redis + Mongo from the draft |
| Scheduled scrapers | **Python on GitHub Actions** | 7 GB RAM runners, **unlimited minutes on public repos** | No cold start, no Vercel size limit, IPs rotate across runner pool |
| On-demand 1mg fetch | **ScraperAPI free** | 1,000 credits/month forever (~25 user-triggered 1mg fetches/day) | Handles Cloudflare so we don't have to |
| Public data seed | **NPPA DPCO** ceiling prices + **Jan Aushadhi** generic MRPs | one-time scrape, committed as JSON | Always-on baseline; zero ongoing cost; legally clean |
| Optional always-on fallback | **Oracle Cloud Always Free Ampere A1** (4 OCPU, 24 GB RAM, 200 GB) | mention in README only — not v1 dependency | Available if GitHub Actions ever restricts public-repo minutes |

### Stack decision (research-led)

**Frontend: Next.js 15 + Tailwind (TypeScript).** Tailwind ships less CSS than hand-rolled at this scope and is portfolio-expected. Glassmorphism look from the draft is fine — keep it.

**Scrapers: Python.** Per-site research:
- 1mg needs Patchright (Python implementation is the best-maintained; Node fork lags).
- `curl_cffi` (Python TLS fingerprint spoofing) is the most reliable curl variant.
- `selectolax` + `httpx` is the canonical fast-parse stack for the three easy sites.
- Python in GitHub Actions is one `actions/setup-python` line.

Two languages, single repo, communicate only through the Postgres row contract. Clean enough.

### Per-site scraping technique (this is the heart of the plan)

| Site | Technique | Why | Where it runs |
|---|---|---|---|
| **PharmEasy** | `httpx.get()` → `selectolax` HTML parse | Server-rendered HTML, no WAF, full content to plain curl | GitHub Actions, every 6h |
| **Netmeds** | `httpx.get()` against `/api/service/...` JSON | Officially allowed in `robots.txt`; two open-source repos document the endpoints | GitHub Actions, every 6h |
| **Apollo** | `httpx.get()` → extract `__NEXT_DATA__` JSON from HTML | Next.js SSR embeds full product data; no auth needed for read paths | GitHub Actions, every 6h |
| **1mg** | **Patchright** (Python, `channel="chrome"`) with **ScraperAPI** fallback when blocked | Cloudflare Bot Mgmt; vanilla Playwright fails | GitHub Actions, every 12h (lower freq to save ScraperAPI credits) |

Each scraper is **its own GitHub Actions workflow file** — one site failing or hitting CAPTCHA doesn't kill the others. Per-site retry with exponential backoff. Respect `robots.txt`. Rate-limit to ≤ 1 req/sec/domain. Real Chrome UA. Log every fetch to a `scrape_log` table for debugging and rate-limit telemetry.

### Data flow for a user search

1. User types "Dolo 650" → debounced fuzzy search via `pg_trgm` against `medicines` table.
2. Server Component renders **immediately** (no spinner) with:
   - **NPPA ceiling price** ("Max legal price under DPCO 2026") — always present for scheduled drugs.
   - **Jan Aushadhi generic equivalent** if it exists.
   - **Last-known cached prices** from each platform with `fetched_at` badge ("updated 3h ago").
3. Recommender card on top showing the winner + plain-English explanation.
4. Comparison grid below for transparency.
5. If a long-tail medicine has no cache row: show NPPA + a "Fetching live prices…" badge, trigger background on-demand fetch via `/api/refresh` (ScraperAPI-budgeted), client SWRs the result in.

### Failure-mode UX (what the draft completely lacked)

| Failure | User sees |
|---|---|
| All scrapers down for 24h | NPPA ceiling + Jan Aushadhi + "last updated yesterday" badge — app still useful |
| Single platform blocked | Other 3 platforms + "Apollo unavailable, retrying tonight" pill |
| Cloudflare challenge on 1mg | Cached value; background refresh queued; no user-visible spinner |
| ScraperAPI quota exhausted | Cached-only mode with explicit banner; counter resets monthly |
| Supabase paused (>1 week idle) | Static NPPA JSON shipped in the Next.js bundle keeps homepage alive |

### Ranking algorithm (deterministic, no LLM)

Pure functions, easy to unit-test, defensible to a reviewer.

For each offer of a given medicine, normalize features to [0,1] over the per-query set:

```python
f_price  = (max_price - o.effective_price) / (max_price - min_price)   # lower is better
f_eta    = (max_eta - o.delivery_days) / (max_eta - min_eta)           # lower is better
f_stock  = 1.0 if o.in_stock else 0.0
f_trust  = TRUST[o.pharmacy]              # static: {1mg:0.9, PharmEasy:0.85, Apollo:0.9, Netmeds:0.8}
f_rx     = 1.0 if not o.rx_required or user.has_rx else 0.6
f_return = (o.return_days - min_ret) / (max_ret - min_ret)

W = {price:0.45, eta:0.20, stock:0.15, trust:0.10, rx:0.05, return:0.05}
score = 100 * (W.price*f_price + W.eta*f_eta + W.stock*f_stock
             + W.trust*f_trust + W.rx*f_rx   + W.return*f_return)
```

Hard filters before ranking: drop offers with `in_stock == False` (still show greyed out), drop offers with `days_to_expiry < 90`.

**Explanation generation** — pick the top-2 weighted contributors and the weakest one, plug into templates:

```
"PharmEasy wins: ₹47 less than the costliest and available now, though delivered in 3 days."
"1mg wins: trusted and 7-day return window, though ₹12 more than the cheapest."
```

Weights live in a config file with sliders in the UI so a reviewer can see the model. **Skip the Gemini API** — for a medicine purchase with arithmetic price claims, a 1-in-1000 LLM hallucination is a worse product than a deterministic template.

### Legal posture (open-source means the ToS posture must be visible)

- `LEGAL.md` at repo root: data sources, robots.txt compliance, takedown contact, rate-limit policy.
- Every result row in the UI **deep-links to the source pharmacy product page** → effectively free referral traffic for them, weakens any damages argument.
- Footer: "Prices sourced from <pharmacy>. May be stale. Buy on the source site."
- Honour `robots.txt` in every scraper (`urllib.robotparser` check before fetch).
- Rate-limit ≤ 1 req/sec/domain, real Chrome UA, no aggressive parallelism per domain.
- **Do not** expose a downloadable dataset or public JSON API of prices (this is the most-litigable line).
- README mentions: takedown on first email; explore each pharmacy's affiliate program (1mg has one via Cuelinks) as a future move that converts adversary → revenue.

---

## Critical files to create (greenfield project)

The repo is empty — these are the files to add, grouped by purpose. Where two adjacent files follow the same pattern, the list is representative, not exhaustive.

**Frontend (Next.js 15 App Router):**
- `app/page.tsx` — homepage with search RSC, NPPA badge, recommender card, comparison grid
- `app/api/refresh/route.ts` — on-demand ScraperAPI fetch, budget-guarded against a `daily_budget` row
- `app/api/search/route.ts` — `pg_trgm` fuzzy lookup against `medicines`
- `components/RecommenderCard.tsx`, `components/ComparisonGrid.tsx`, `components/PriceBadge.tsx`
- `lib/db.ts` — Supabase client
- `lib/scoring/ranker.ts`, `lib/scoring/explainer.ts`, `lib/scoring/config.ts` — pure-function ranker mirroring the Python contract

**Database (Supabase):**
- `db/schema.sql` — tables: `medicines`, `prices` (with `fetched_at`, `stale_after`), `platforms`, `scrape_log`, `daily_budget`. `pg_trgm` index on `medicines.name`.
- `db/seed_nppa.sql` + `data/nppa-dpco-2026.json` — DPCO ceiling prices, ~907 formulations
- `data/jan-aushadhi-2025.json` — generic MRPs from the Jan Aushadhi PDF (one-time PDF→JSON extract)

**Scrapers (Python, run by GitHub Actions):**
- `scrapers/base.py` — abstract `PharmacyScraper` with robots.txt check + rate limit + UA centralised
- `scrapers/pharmeasy.py` — `httpx` + `selectolax`
- `scrapers/netmeds.py` — `httpx` against `/api/service/`
- `scrapers/apollo.py` — `httpx` + `__NEXT_DATA__` JSON extraction
- `scrapers/one_mg.py` — Patchright with ScraperAPI fallback when Cloudflare hits
- `scrapers/run.py` — single entrypoint: `python -m scrapers.run --site pharmeasy --top 50`
- `scrapers/pyproject.toml` with: `httpx`, `selectolax`, `patchright`, `curl_cffi`, `supabase-py`

**CI / scheduled jobs:**
- `.github/workflows/scrape-pharmeasy.yml` — cron `0 */6 * * *`
- `.github/workflows/scrape-netmeds.yml` — cron `0 */6 * * *`, offset 1h
- `.github/workflows/scrape-apollo.yml` — cron `0 */6 * * *`, offset 2h
- `.github/workflows/scrape-1mg.yml` — cron `0 */12 * * *`, conservative on ScraperAPI quota
- `.github/workflows/seed-nppa.yml` — manual `workflow_dispatch`, refreshes NPPA seed monthly

**Repo hygiene:**
- `README.md` — architecture diagram, screenshots, "deploy your own"
- `LEGAL.md` — data sources, ToS posture, takedown contact
- `.env.example` — `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SCRAPERAPI_KEY`

---

## Build order (MVP slice — what to do first)

1. **Day 1** — Next.js + Tailwind scaffold. Parse NPPA DPCO PDF → JSON. Build static search UI against the JSON. **You have a working demo today**, zero scrapers needed.
2. **Day 2** — Supabase schema, seed NPPA + Jan Aushadhi. Wire `pg_trgm` fuzzy search. Replace static JSON with DB.
3. **Day 3** — Write `scrapers/base.py` + `scrapers/netmeds.py` (easiest site, official API). One GitHub Actions workflow. Verify rows appear in Postgres.
4. **Day 4** — Add `pharmeasy.py` and `apollo.py` (both `httpx`-only, same pattern). Each its own workflow.
5. **Day 5** — Ranker + explainer in TypeScript (`lib/scoring/`). Recommender card UI.
6. **Day 6** — `scrapers/one_mg.py` with Patchright + ScraperAPI fallback. Daily budget guard.
7. **Day 7** — On-demand `/api/refresh` route for long-tail. Failure-mode UX polish. README + LEGAL.md.

Nice-to-have (not v1): price history charts (Recharts on the existing `prices` table), email alerts, generic-substitute suggestions, affiliate-link upgrade.

---

## Verification plan

1. **End-to-end correctness** — search for 5 medicines (Dolo 650, Crocin, Azithral 500, Atorva 10, Pan 40). For each, manually open 1mg / PharmEasy / Netmeds / Apollo in a real browser and confirm the price + delivery ETA captured in Postgres match within ±₹1 and ±1 day.
2. **NPPA baseline** — confirm the ceiling-price row exists for at least 3 of those 5 medicines and is shown in the UI.
3. **Scheduled scraper resilience** — manually trigger each GitHub Actions workflow; confirm rows in `scrape_log`. Force one workflow to fail (bad URL) and confirm the others still run.
4. **Cache hit speed** — repeat a search; second load should be <200ms (Postgres cache hit). Inspect Network panel.
5. **Failure-mode UX** — temporarily revoke the Supabase key in Vercel → confirm the static NPPA JSON fallback still renders the homepage usefully.
6. **Rate-limit / ToS hygiene** — `scrape_log` should show ≤ 1 req/sec/domain. `urllib.robotparser` check must pass before every fetch.
7. **Ranker math** — unit tests on `lib/scoring/ranker.ts` and `scrapers/scoring/ranker.py` (mirror contract). Golden cases: top-by-price, top-by-eta, tie-breaker via trust.
8. **Mobile responsiveness** — Chrome devtools mobile preset; recommender card and comparison grid usable at 360px width.

---

## Honest tradeoffs vs. the original draft

| Dimension | Original | Revised |
|---|---|---|
| Time to working demo | Week 2+ (scraper infra) | Day 1 (NPPA static data) |
| p95 latency | 5–20s (live scrape, 4 sites) | <200ms (cache hit) |
| Reviewer impression | "Built a scraper" | "Combined public regulatory data with respectful scraping under a budget" |
| Hidden cost risk | Mongo + Redis + Render + UptimeRobot all near limits | Single Postgres at 500 MB |
| Legal posture | Weak (no ToS thought) | Strong (NPPA-first, deep-linked, takedown-ready, LEGAL.md) |
| First failure mode | Render sleeps + Cloudflare blocks → broken demo | ScraperAPI quota exhausts → graceful cached-only banner |

The original plan **isn't salvageable with small fixes** — the scraper-on-Vercel hole and two-DB sprawl are structural. The revised shape is buildable end-to-end in roughly a week and degrades gracefully.

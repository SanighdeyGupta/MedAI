# MedAI — Medicine Price Comparison for India

A free, open-source web app that compares medicine prices across Indian pharmacies (**1mg, PharmEasy, Netmeds, Apollo**) and tells you in plain English which one is the best deal — and why.

**Stack:** Next.js 16 + TypeScript + Tailwind v4 + Supabase Postgres + Python scrapers in GitHub Actions. Built end-to-end for **$0/month** on free tiers.

> _Day 1 demo seed data is illustrative. Live scrapers come online once you finish the [setup](SETUP.md)._

---

## What it does

1. Search a medicine (autocomplete, fuzzy / typo-tolerant).
2. See a **recommendation card** — winner platform + plain-English reason ("PharmEasy wins: ₹47 less than the costliest option and available now, though delivered in 3 days").
3. See the **comparison grid** — every platform side-by-side with effective price, delivery ETA, stock, return window, composite score (0-100).
4. Every result deep-links to the source pharmacy so the user can verify & buy.
5. NPPA DPCO ceiling-price baseline shown alongside, so the user knows the max-legal price.

The ranker is a **deterministic weighted formula** (no LLM). Six features, normalised per-query, with explainable contributions: price (45%), delivery ETA (20%), stock (15%), platform trust (10%), Rx friction (5%), return policy (5%). The reasoning sentence is generated from the top-2 strongest contributors and the weakest one. See [lib/scoring/ranker.ts](lib/scoring/ranker.ts).

---

## Architecture

```
                      ┌───────────────────────────────────┐
                      │       Vercel Hobby (free)         │
                      │   ┌──────────────────────────┐    │
   browser ─────────► │   │   Next.js 16 App Router  │    │
                      │   │   - / (search)           │    │
                      │   │   - /m/[id] (compare)    │    │
                      │   │   - /api/search          │    │
                      │   └────────────┬─────────────┘    │
                      └────────────────┼──────────────────┘
                                       │ read-only (anon key)
                                       ▼
                      ┌───────────────────────────────────┐
                      │     Supabase Postgres (free)      │
                      │   medicines · prices · platforms  │
                      │   scrape_log · pg_trgm fuzzy idx  │
                      └─────────────────▲─────────────────┘
                                        │ writes (service role)
                                        │
                      ┌─────────────────┴─────────────────┐
                      │   GitHub Actions (free, public)   │
                      │   Python scrapers, cron every 6h: │
                      │   - Netmeds   (httpx → Fynd API)  │
                      │   - PharmEasy (httpx → __NEXT_DATA__) │
                      │   - 1mg       (httpx → API + page)│
                      │   - Apollo    (Patchright → DOM)  │
                      └───────────────────────────────────┘
```

When the DB is unconfigured, the app silently falls back to a static JSON seed (`data/medicines.json`) — so the homepage and search keep working even with zero infrastructure.

---

## Per-pharmacy scraper at a glance

| Pharmacy | Approach | Endpoint | Cost per scrape | Why this technique |
|---|---|---|---|---|
| **Netmeds** | `httpx` → JSON | `/ext/search/application/api/v1.0/products` (Fynd platform) | ~0.5s | robots-clean; no WAF; SPA's own API |
| **PharmEasy** | `httpx` → `__NEXT_DATA__` parse | `/search/all?name=…` (SSR React) | ~0.7s | Server-rendered; data fully embedded |
| **1mg** | `httpx` → API + product page | `/pharmacy_api_webservices/search` (match) → `/drugs/<slug>` (true price) | ~1.8s | API gives wholesale; product page has the page-promo price the user sees |
| **Apollo** | **Patchright** → DOM scrape | `/search-medicines/<q>` (RSC + GraphQL) | ~7s | Client-rendered React; auth-gated GraphQL; only renderable in a browser |

All four scrapers share a single base class ([`scrapers/base.py`](scrapers/base.py)) that enforces 1 req/sec/domain, robots.txt check, real Chrome UA, and writes every attempt (success or failure) to the `scrape_log` audit table.

See [scrapers/README.md](scrapers/README.md) for run instructions and [LEGAL.md](LEGAL.md) for the per-pharmacy ToS posture.

---

## Project structure

```
MedAI/
├── app/                       Next.js App Router
│   ├── page.tsx               Homepage (hero, search, popular chips)
│   ├── m/[id]/page.tsx        Medicine detail (winner card + grid)
│   ├── search/page.tsx        Listing for fuzzy queries
│   └── api/search/route.ts    Autocomplete API
├── components/                React server components
│   ├── SearchBar.tsx          Debounced fuzzy autocomplete
│   ├── RecommenderCard.tsx    Winner card with reasoning
│   ├── ComparisonGrid.tsx     Per-platform offer cards
│   └── PopularChips.tsx       Quick-launch popular medicines
├── lib/
│   ├── medicines.ts           Data access (Supabase or JSON fallback)
│   ├── db.ts                  Supabase client
│   ├── scoring/               Pure-function ranker + explainer
│   ├── format.ts              Stale-data formatting helpers
│   └── types.ts               Shared TS types
├── data/
│   ├── medicines.json         25-medicine seed (illustrative)
│   └── platforms.json         Platform metadata + trust scores
├── db/
│   └── schema.sql             Postgres schema (idempotent)
├── scrapers/                  Python package
│   ├── base.py                Abstract PharmacyScraper + rate limit
│   ├── match_helpers.py       Fuzzy + pack-aware matcher
│   ├── netmeds.py             httpx + Fynd JSON API
│   ├── pharmeasy.py           httpx + __NEXT_DATA__
│   ├── one_mg.py              httpx + product page price override
│   ├── apollo.py              Patchright DOM scrape
│   ├── db.py                  Supabase admin client
│   ├── run.py                 CLI entrypoint
│   └── requirements.txt
├── scripts/
│   ├── seed.ts                Loads data/*.json into Supabase
│   ├── verify_scrapers.py     Cross-platform health dashboard
│   └── probe_*.py             One-off DOM/API probes used during build
├── .github/workflows/
│   ├── scrape-netmeds.yml     cron 0 */6 * * *
│   ├── scrape-pharmeasy.yml   cron 0 1,7,13,19 * * *
│   ├── scrape-apollo.yml      cron 0 2,8,14,20 * * * (includes patchright install)
│   └── scrape-1mg.yml         cron 0 3,9,15,21 * * *
├── implementation_plan.md     The architectural plan (reviewed Day 0)
├── SETUP.md                   Local development setup
├── DEPLOY.md                  Production deployment (Vercel + GitHub)
├── LEGAL.md                   Per-pharmacy ToS posture + takedown contact
└── README.md                  ← you are here
```

---

## Quickstart

### Local dev with JSON seed (zero config)

```
npm install
npm run dev
# open http://localhost:3000
```

### Add live Supabase + scrapers

See [SETUP.md](SETUP.md) for the full step-by-step (~10 min).

### Run a scraper manually

```
py -3.11 -m pip install -r scrapers/requirements.txt
py -3.11 -m scrapers.run --site netmeds --limit 25
py -3.11 -m scrapers.run --site pharmeasy --limit 25 --dry-run
py -3.11 -m scrapers.run --site apollo  --limit 25
py -3.11 -m scrapers.run --site 1mg     --limit 25
```

### Deploy

- **[DEPLOY.md](DEPLOY.md)** — Vercel + GitHub deploy guide (~15 min).
- **[NETLIFY.md](NETLIFY.md)** — Netlify fallback if Vercel doesn't work for you (same architecture, same cost, ~10 min).

---

## Cost breakdown

| Layer | Service | Free-tier limit | What we use |
|---|---|---|---|
| Frontend hosting | Vercel Hobby | 100 GB bandwidth, 1M function invocations | well under |
| Database | Supabase Free | 500 MB DB, 5 GB egress | ~1 MB DB, tiny egress |
| Scrapers | GitHub Actions (public repo) | unlimited minutes on standard runners | ~3 hr/day of compute |
| Browser binary | Patchright (downloads Chromium) | open-source | only for Apollo workflow |
| Domain | `medai-*.vercel.app` | free | included |

**Recurring cost: $0/month.** No paid third-party APIs, no ScraperAPI, no proxy service.

---

## Roadmap (future enhancements)

These are deliberately *not* shipped in v1 to keep scope tight:

- **NPPA live ingest** — replace illustrative `nppa_ceiling_inr` with real DPCO ceiling prices from [nppaimis.nic.in](https://nppaimis.nic.in/) (ASP.NET form scrape; portal only resolves from Indian IPs).
- **Jan Aushadhi generic equivalents** — parse the official generic MRP PDF list and surface "available as generic for ₹X".
- **`/api/refresh` on-demand route** — per-medicine "Refresh now" button via GitHub Actions `workflow_dispatch`.
- **Coupon-applied price** for Netmeds / PharmEasy — would require a Patchright session that clicks "Unlock Coupon"; documented in [LEGAL.md](LEGAL.md) as a known limit.
- **Price history charts** — Recharts on the existing `prices.fetched_at` rows.
- **Price-drop email alerts** — Resend free tier + daily diff query.
- **PharmEasy sitemap URL discovery** — to scrape only robots-allowed product pages instead of `/search/all*`.
- **Affiliate program integration** — 1mg via Cuelinks/EarnKaro.

---

## Background reading

- [implementation_plan.md](implementation_plan.md) — the architectural plan and why the initial design was rejected.
- [LEGAL.md](LEGAL.md) — per-pharmacy ToS posture, data sources, known price-accuracy limits.
- [SETUP.md](SETUP.md) — local development setup (Supabase + scrapers).
- [DEPLOY.md](DEPLOY.md) — Vercel + GitHub Actions deployment, step-by-step.
- [scrapers/README.md](scrapers/README.md) — per-pharmacy scraping technique notes.

---

## License & takedown

MIT-licensed code. Pharmacy logos, brand names, and product images shown belong to their respective owners; we use them only as deep-link targets and do not redistribute their data as a dataset.

If you operate one of the pharmacies and want this project to stop scraping your site, email **gupta.sanighdey8@gmail.com** — response within 24h, scraper removed within 48h, no questions.

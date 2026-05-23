# Deploy MedAI to production

End-to-end Vercel + GitHub deploy in ~15 minutes. Everything stays on free tiers.

**Prereqs:** you've already finished [SETUP.md](SETUP.md) (Supabase project provisioned, schema applied, `npm run seed` succeeded, `npm run dev` works locally with live data).

---

## Step 1 — Push to a public GitHub repo

GitHub Actions cron minutes are **unlimited on public repos** and capped on private. We want unlimited, so the repo must be public. The code holds no secrets (`.env.local` is gitignored; `.env.example` only has placeholders).

> Use **gupta.sanighdey8@gmail.com** for the GitHub account (the project's chosen identity — see memory note).

```powershell
# from the project root
git init
git add .
git status         # sanity check: confirm .env.local is NOT listed
git commit -m "Initial commit — MedAI v1"
```

Verify `.env.local` is excluded:

```powershell
git check-ignore .env.local      # should print: .env.local
```

Then create the repo on GitHub (UI or `gh repo create`):

```powershell
# if you have the GitHub CLI installed:
gh auth login                    # browser-based login with gupta.sanighdey8@gmail.com
gh repo create medai --public --source=. --remote=origin --push

# OR manually:
# 1. https://github.com/new -> name = medai, public
# 2. then:
git branch -M main
git remote add origin https://github.com/<your-username>/medai.git
git push -u origin main
```

---

## Step 2 — Add GitHub repo secrets

The 4 scraper workflows need DB credentials. Settings → Secrets and variables → Actions → New repository secret.

| Secret name | Value |
|---|---|
| `SUPABASE_URL` | `https://<your-project-ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → Project Settings → API → **service_role** key |

Test:
1. Actions tab → Workflows → "Scrape Netmeds" → Run workflow → main → Run.
2. Wait ~30s. Confirm the job logs show `25/25 medicines scraped successfully.`
3. In Supabase Table Editor → `prices` → confirm fresh `fetched_at` timestamps for Netmeds.

Repeat for the other three workflows or just wait for the cron (every 6h, staggered by 1h per platform).

---

## Step 3 — Connect Vercel

1. Sign in at https://vercel.com using **gupta.sanighdey8@gmail.com** (GitHub OAuth is simplest).
2. **Add New → Project** → import the `medai` repo.
3. Framework preset: **Next.js** (auto-detected).
4. Build command: `npm run build` (default).
5. Output directory: `.next` (default).
6. Install command: `npm install` (default).

Don't click Deploy yet — env vars first.

---

## Step 4 — Add Vercel env vars

In the Project setup → **Environment Variables**, add:

| Name | Value | Environments |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://<your-project-ref>.supabase.co` | Production, Preview, Development |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Project Settings → API → **anon** (public) key | Production, Preview, Development |

The **service_role key is NOT added to Vercel** — the web app only reads with the anon key (RLS-protected). Service role lives only in GitHub Actions for scraper writes.

> **Do not also add `SUPABASE_URL`** (no `NEXT_PUBLIC_` prefix). The app's [`lib/db.ts`](lib/db.ts) reads `NEXT_PUBLIC_SUPABASE_URL` first.

Now click **Deploy**. First build takes ~2 minutes.

---

## Step 5 — Verify production

When Vercel shows ✅ Deployed:

1. Open the generated URL (`medai-<hash>.vercel.app`).
2. Homepage loads. Try the search — typing "azitral" should still find Azithral 500 via `pg_trgm`.
3. Click into a medicine. All 4 platform cards should render with their live cached prices.
4. Check the freshness badge under each card — should say `Xh ago`, not "demo data".

If any card says **"demo data"**, the production app isn't reading from Supabase. Most common causes:
- Env var name typo (must be exactly `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`)
- Vercel project deployed before env vars were saved — redeploy from the dashboard
- Supabase RLS policies missing — re-run [db/schema.sql](db/schema.sql) (idempotent; safe to repeat)

---

## Step 6 — Keep Supabase from pausing

Supabase Free pauses a project after **7 days of zero activity**. Two options:

**Option A — UptimeRobot (recommended; takes 2 minutes)**

1. Sign up at https://uptimerobot.com (with **gupta.sanighdey8@gmail.com**).
2. Add a new HTTP(s) monitor.
3. URL: your production Vercel URL (e.g. `https://medai-abc123.vercel.app`).
4. Monitoring Interval: **every 30 minutes** is enough.
5. Save.

UptimeRobot's hourly ping touches the homepage, which queries Supabase via `getPlatforms()`, keeping the project active.

**Option B — Weekly GitHub Actions cron**

Already covered: the four scraper workflows run every 6 hours and write to Supabase. As long as one cron fires per week, Supabase stays awake. No extra setup.

---

## Step 7 — (Optional) Custom domain

Vercel → Project → Settings → Domains → Add `medai.in` or whatever you've registered. Add the two DNS records Vercel shows.

Cost: ~₹800-1000/year for a `.in` domain (Namecheap, Hostinger). Skip if `medai-<hash>.vercel.app` is fine.

---

## Step 8 — Verify the cron is firing

48 hours after deploy, run:

```powershell
py -3.11 scripts/verify_scrapers.py
```

Expected output:

```
Platform   #log  #prices  success%   latest
Netmeds      >100  25   100.0%    today
PharmEasy    >100  25   100.0%    today
Apollo       >50   25   100.0%    today
1mg          >50   25   100.0%    today
```

If `success%` drops below 80% for any platform, check Actions tab → workflow run logs. Common causes:

| Symptom | Likely cause | Fix |
|---|---|---|
| Patchright timeout on Apollo | Chromium install step failed on runner | `patchright install chromium --no-shell` may be deprecated — drop the `--no-shell` flag |
| 1mg returns Cloudflare challenge | Runner IP got flagged (rare) | Add a retry with random sleep; or wait — Cloudflare blocks lift within hours |
| PharmEasy 0 results for known medicines | They changed slug pattern | Re-check the `__NEXT_DATA__` shape with `scripts/probe_data.py` |
| Netmeds returns 4xx | Fynd platform updated API | Re-probe `/ext/search/application/api/v1.0/products` |

---

## Cost ceiling (what would force you off free tier)

| Trigger | Free-tier limit | Action |
|---|---|---|
| > 100 GB Vercel bandwidth/month | Vercel Hobby exceeded | Move to Pro ($20/mo) or add caching headers |
| > 500 MB Supabase storage | DB full | Add a cleanup job; we currently use ~1 MB so this is years away |
| > 5 GB Supabase egress/month | Throttled | Add ISR (`revalidate: 3600`) on the medicine page to reduce DB hits |
| Repo set to private | GH Actions minutes metered | Set back to public (or accept the ~2k min/mo cap) |

For a portfolio project receiving < 1000 visits/month, none of these will hit. The architecture is engineered to scale to ~100k visits/month at $0.

---

## Rollback

If a deploy breaks something:

1. Vercel → Project → Deployments → find the last green deployment → **⋯ → Promote to Production**.
2. The previous build comes back instantly. Vercel keeps the last ~100 deploys.

If a scraper breaks the DB (bad upsert):

1. Actions tab → cancel any in-flight workflow.
2. Supabase Dashboard → SQL Editor → re-run the seed:
   ```sql
   -- on the local machine
   npm run seed
   ```
3. Fix the scraper, push, re-trigger.

---

## What we did NOT deploy

- **NPPA + Jan Aushadhi ingestion** — illustrative values in the seed remain. Future work.
- **`/api/refresh` on-demand route** — scheduled crawl is enough for v1.
- **Custom domain** — `vercel.app` subdomain is fine for portfolio.
- **Analytics** — Vercel's basic analytics is on by default and free.

See [README.md#roadmap](README.md#roadmap-future-enhancements) for the future-work list.

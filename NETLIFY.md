# Deploy MedAI to Netlify

End-to-end Netlify deploy in ~10 minutes. Free tier. Same architecture as the Vercel path, just a different host. **Use this if Vercel won't load** (some users hit 404s on the Vercel dashboard from certain Indian networks).

**Prereqs:**
- [SETUP.md](SETUP.md) done (Supabase live, `npm run seed` succeeded, `npm run dev` works locally).
- The MedAI repo is already pushed to a **public GitHub repo** (you confirmed this).

The repo already contains [`netlify.toml`](netlify.toml) with explicit Next.js plugin config, so the build is deterministic.

---

## Step 1 — Sign in to Netlify

1. Open https://app.netlify.com in an **incognito window** (skips any cached Vercel/Google cookie weirdness).
2. Click **Sign up** (or **Log in** if you already have a Netlify account).
3. Choose **GitHub** — this is the cleanest path because Netlify imports projects directly from GitHub.
4. Authorise Netlify to read your repositories. Use **gupta.sanighdey8@gmail.com** for the GitHub identity (per project memory).

If the GitHub OAuth popup is blocked, allow popups for `app.netlify.com` in your browser and retry.

---

## Step 2 — Import the GitHub repo

1. After login, click **Add new site → Import an existing project**.
2. **Deploy with GitHub** → choose your `medai` repo from the list.
3. If the repo doesn't appear: click **Configure the Netlify app on GitHub** → grant access to the `medai` repo specifically, then come back.

---

## Step 3 — Configure build settings

Netlify should auto-detect Next.js. The values come from `netlify.toml` automatically, but verify the dialog shows:

| Field | Value |
|---|---|
| Branch to deploy | `main` |
| Build command | `npm run build` |
| Publish directory | `.next` |
| Functions directory | (leave blank — auto) |

If any field is empty, fill it in. Don't click Deploy yet — env vars first.

---

## Step 4 — Add environment variables

Click **Show advanced** → **New variable** and add these two:

| Key | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://<your-project-ref>.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | (anon public key from Supabase → Project Settings → API) |

**Do NOT add `SUPABASE_SERVICE_ROLE_KEY` here.** That secret only goes to GitHub Actions (for scrapers), never to the public-facing web app.

You can find these values in your local `.env.local` file (the values you already have working).

---

## Step 5 — Deploy

Click **Deploy `medai`**. First build takes ~3 minutes (npm install + Next.js compile + Netlify plugin processing).

When the build is green, Netlify gives you a URL like:
```
https://medai-<hash>.netlify.app
```

Open it. You should see the same homepage you see at `localhost:3000`.

---

## Step 6 — Verify production

1. **Homepage** loads. Search "azitral" → finds Azithral 500 (proves `pg_trgm` is connected via Supabase).
2. **Click into Dolo 650**. All 4 platform cards render with prices from the DB. Freshness badge says "Xh ago", not "demo data".
3. **Open the browser console**. Should be empty / no errors. If you see "Supabase URL is not defined" → env vars didn't save; redeploy from the Netlify dashboard.

Common gotchas:

| Symptom | Fix |
|---|---|
| Build fails on `@netlify/plugin-nextjs` install | Site settings → Build & deploy → Clear cache and retry deploy |
| Site loads but every medicine page shows "demo data" | Env var name typo — must be exactly `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (case-sensitive) |
| 502 on `/m/[id]` | Plugin not active — open `netlify.toml`, confirm `[[plugins]] package = "@netlify/plugin-nextjs"` is present, push, redeploy |
| Slow first hit | Netlify cold starts — second request is fast. Add `revalidate: 3600` on the medicine page if you want ISR caching |

---

## Step 7 — Keep Supabase awake (same as Vercel path)

Supabase Free pauses after **7 days of zero activity**. Add a free UptimeRobot monitor:

1. https://uptimerobot.com → sign up with **gupta.sanighdey8@gmail.com**.
2. New monitor → HTTP(s) → paste your Netlify URL.
3. Interval: 30 minutes.

Done. The hourly ping touches the homepage, which queries Supabase, keeping the project active.

---

## Step 8 — GitHub Actions scraper secrets (independent of Netlify)

This part is the **same as the Vercel guide** — the scrapers run on GitHub, not Netlify. If you haven't done it yet:

1. GitHub → your `medai` repo → **Settings → Secrets and variables → Actions → New repository secret**.
2. Add:
   - `SUPABASE_URL` = `https://<your-project-ref>.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY` = (service_role key — different from anon key)
3. Test: **Actions** tab → "Scrape Netmeds" → **Run workflow** → main.
4. After ~30s the workflow shows green; check Supabase → `prices` table → rows have a fresh `fetched_at`.

The other three workflows (PharmEasy, Apollo, 1mg) use the same two secrets — no extra setup needed.

---

## Custom domain (optional)

Netlify → Domain management → Add a domain you own. They auto-issue a free Let's Encrypt cert. Cost = whatever your registrar charged (~₹800/year for `.in`).

You can also use a Netlify subdomain — Domain management → Options → Edit site name → e.g. `medai-india` → `https://medai-india.netlify.app` is free.

---

## Differences from the Vercel path

| Aspect | Vercel | Netlify |
|---|---|---|
| Next.js support | First-party (Vercel made Next.js) | Excellent via `@netlify/plugin-nextjs` |
| Free bandwidth | 100 GB / month | 100 GB / month |
| Free build minutes | unlimited | 300 / month |
| Free function invocations | 1M / month | 125k / month |
| Cold start | ~50 ms | ~200 ms |
| Indian PoP | Mumbai (CDN) | Mumbai (CDN) |
| Auto-preview deploys for PRs | yes | yes |

For our traffic shape (portfolio, <1k visits/mo), every Netlify limit is well out of reach. Same cost = **$0/month**.

---

## Rollback

Netlify → Deploys tab → find the last green deploy → **⋯ → Publish deploy**. Previous build comes back instantly. Netlify keeps the last 100 deploys.

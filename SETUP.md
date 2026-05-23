# Setup guide

The app works in two modes:

- **JSON mode (zero config)** — reads `data/medicines.json`. Day 1 default. `npm run dev` and you have a working demo.
- **Supabase mode** — reads from Postgres with `pg_trgm` fuzzy search. Needed for Day 3+ (scrapers).

The code detects which mode to use based on environment variables.

---

## Supabase setup (Day 2)

### 1. Create a Supabase project

1. Sign up at https://supabase.com using **gupta.sanighdey8@gmail.com**.
2. Click **New project**.
3. Project name: `medai`. Pick the **Mumbai** region (closest to Indian users / pharmacy sites).
4. Generate a strong DB password — save it in your password manager. The seed script doesn't need this; it uses the service-role key.
5. Wait ~2 min for the project to provision.

### 2. Run the schema

1. In the Supabase dashboard, open **SQL Editor** → **New query**.
2. Paste the contents of [`db/schema.sql`](db/schema.sql) and click **Run**.
3. You should see "Success. No rows returned." It creates: `platforms`, `medicines`, `prices`, `scrape_log`, `daily_budget`, the `search_medicines()` function, the `v_medicine_offers` view, and `pg_trgm` indexes.

### 3. Wire credentials

1. In Supabase → **Project Settings** → **API**, copy:
   - **Project URL** → `NEXT_PUBLIC_SUPABASE_URL`
   - **anon public key** → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - **service_role key** → `SUPABASE_SERVICE_ROLE_KEY` *(server-only, never commit)*
2. Copy this file:
   ```
   copy .env.example .env.local
   ```
3. Paste the three values into `.env.local`.

### 4. Seed the database

```
npm run seed
```

Expected output:
```
→ Seeding 4 platforms...
→ Seeding 25 medicines...
→ Seeding 100 price rows...
✓ search_medicines('dolo') returned 1 rows (expected ≥1)
✓ Seed complete.
```

### 5. Restart the dev server

```
npm run dev
```

The app now reads from Postgres. Search uses `pg_trgm` so typos and partial matches work better than the JSON substring search:

- Try **"dolo"**, **"paracetamol"**, **"pantop"** — all match.
- Try **"azitral"** (typo) — should still find Azithral 500 via trigram similarity.

Verify it's hitting the DB by adding a `console.log` in `lib/medicines.ts` or watching the Supabase **Logs** → **Postgres** tab.

---

## Falling back to JSON

Delete or comment out the `NEXT_PUBLIC_SUPABASE_URL` line in `.env.local` and restart. The app reverts to JSON mode immediately — useful for offline development or if your Supabase project is paused.

---

## Free-tier limits to know about

| Limit | Value |
|---|---|
| Database storage | 500 MB (we use <1 MB) |
| Egress | 5 GB/month |
| Project pausing | After **7 days** with zero activity. UptimeRobot weekly ping prevents this. |
| Concurrent connections | 60 (way more than needed) |
| Backup | 7 days of point-in-time |

If the project ever pauses, the app silently falls back to the JSON seed (because `getSupabase()` queries will fail and we catch them) — so the homepage keeps working.

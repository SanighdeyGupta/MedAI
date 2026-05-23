/**
 * POST /api/discover?q=<query>
 *
 * Live-fetches a medicine across Netmeds + PharmEasy + 1mg, creates the
 * `medicines` + `prices` rows, and returns the new ID so the client can
 * navigate to /m/{id}.
 *
 * Apollo is deliberately excluded from this path — Patchright can't run
 * inside a Netlify Function. The next scheduled `scrape-apollo` cron run
 * picks up the new row automatically.
 *
 * Dedup: before scraping, we check if the existing `medicines` table
 * already has a strong fuzzy match. If yes, return that ID instead of
 * re-scraping (idempotent for the same query).
 */
import { NextRequest, NextResponse } from "next/server";

import { getSupabase, getSupabaseAdmin } from "@/lib/db";
import { findMedicineById, searchMedicines } from "@/lib/medicines";
import { nameScore, slugify } from "@/lib/scrapers/match";
import { discoverMedicine } from "@/lib/scrapers/discover";

export const runtime = "nodejs"; // need full Node fetch for the 3 scrapers
export const dynamic = "force-dynamic";
export const maxDuration = 30; // seconds (Netlify caps at 30s on free tier)

const DEDUP_THRESHOLD = 0.85;

export async function POST(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim() ?? "";
  if (q.length < 2) {
    return NextResponse.json({ error: "query too short" }, { status: 400 });
  }

  // 1. Dedup, attempt A: cheap slug-prefix lookup. If the user has
  // previously discovered the same medicine, the existing row's id starts
  // with the slugified query. Survives trigram-search weakness when the
  // canonical name has punctuation/spacing that differs from the query
  // (e.g. user types "Glycomet GP1" → 1mg returns "Glycomet-GP 1 Tablet PR"
  // → row id "glycometgp1tabletpr" — pg_trgm doesn't rank that #1).
  const querySlug = slugify(q);
  if (querySlug.length >= 4) {
    const sb = getSupabase();
    if (sb) {
      try {
        const { data, error } = await sb
          .from("medicines")
          .select("id,name")
          .like("id", `${querySlug}%`)
          .limit(1);
        if (!error && data && data.length > 0) {
          const existing = await findMedicineById(data[0].id);
          if (existing) {
            return NextResponse.json({
              medicine_id: existing.id,
              reused_existing: true,
              offer_count: existing.offers.length,
              scrape_results: [],
              matched_via: "slug_prefix",
            });
          }
        }
      } catch (err) {
        console.warn("[discover] slug-prefix dedup failed:", err);
      }
    }
  }

  // 1b. Dedup, attempt B: pg_trgm fuzzy match across all medicines, then
  // a strong-similarity nameScore check.
  try {
    const existing = await searchMedicines(q, 3);
    for (const m of existing) {
      if (nameScore(q, m.name) >= DEDUP_THRESHOLD) {
        return NextResponse.json({
          medicine_id: m.id,
          reused_existing: true,
          offer_count: m.offers.length,
          scrape_results: [],
          matched_via: "name_score",
        });
      }
    }
  } catch (err) {
    console.warn("[discover] pg_trgm dedup failed, continuing:", err);
  }

  // 2. Run the three live scrapers.
  const result = await discoverMedicine(q);
  if (!result || result.offers.length === 0) {
    return NextResponse.json(
      {
        error: "no_match",
        message: `Couldn't find prices for "${q}" on any pharmacy. Try a brand name.`,
        scrape_results: result?.scrape_results ?? [],
      },
      { status: 404 },
    );
  }

  // 3. Persist. Without an admin client we can't write — but we can still
  // return the live result so the user sees prices (just no caching).
  const sb = getSupabaseAdmin();
  if (!sb) {
    return NextResponse.json({
      medicine_id: null,
      reused_existing: false,
      offer_count: result.offers.length,
      scrape_results: result.scrape_results,
      live_only: result,
      warning: "SUPABASE_SERVICE_ROLE_KEY not configured — results not cached.",
    });
  }

  // Upsert medicine row. We INSERT with conflict-do-update so a parallel
  // request that already created the row doesn't error out.
  const { error: medErr } = await sb
    .from("medicines")
    .upsert(
      {
        id: result.medicine.id,
        name: result.medicine.name,
        composition: result.medicine.composition,
        manufacturer: result.medicine.manufacturer,
        pack: result.medicine.pack,
        rx_required: result.medicine.rx_required,
        nppa_ceiling_inr: result.medicine.nppa_ceiling_inr,
        created_via: "discovered",
      },
      { onConflict: "id" },
    );
  if (medErr) {
    return NextResponse.json(
      { error: "db_insert_failed", message: medErr.message },
      { status: 500 },
    );
  }

  // Upsert prices.
  const priceRows = result.offers.map((o) => ({
    medicine_id: o.medicine_id,
    platform_id: o.pharmacy,
    price: o.price,
    mrp: o.mrp,
    delivery_days: o.delivery_days,
    in_stock: o.in_stock,
    return_days: o.return_days,
    url: o.url,
  }));
  const { error: priceErr } = await sb
    .from("prices")
    .upsert(priceRows, { onConflict: "medicine_id,platform_id" });
  if (priceErr) {
    return NextResponse.json(
      { error: "db_price_failed", message: priceErr.message },
      { status: 500 },
    );
  }

  // Best-effort: log the discovery for telemetry; ignore failures.
  for (const r of result.scrape_results) {
    sb.from("scrape_log")
      .insert({
        platform_id: r.pharmacy,
        medicine_id: result.medicine.id,
        status: r.status,
        duration_ms: r.duration_ms,
        via: "discover-ts",
        error_message: r.error_message,
      })
      .then(() => {}, () => {});
  }

  return NextResponse.json({
    medicine_id: result.medicine.id,
    reused_existing: false,
    offer_count: result.offers.length,
    scrape_results: result.scrape_results.map((r) => ({
      pharmacy: r.pharmacy,
      status: r.status,
      duration_ms: r.duration_ms,
      error_message: r.error_message,
    })),
  });
}

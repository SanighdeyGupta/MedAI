/**
 * Seeds the Supabase database from data/medicines.json + data/platforms.json.
 *
 * Usage:
 *   1. Copy .env.example -> .env.local and fill in Supabase URL + service role key.
 *   2. Run db/schema.sql in Supabase SQL Editor first.
 *   3. npm run seed
 *
 * Idempotent: uses upsert on (id) / (medicine_id, platform_id).
 */
import { config as loadEnv } from "dotenv";
loadEnv({ path: ".env.local" });
loadEnv({ path: ".env" });
import { createClient } from "@supabase/supabase-js";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SUPABASE_URL = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error(
    "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY. Copy .env.example to .env.local and fill them in."
  );
  process.exit(1);
}

const sb = createClient(SUPABASE_URL, SERVICE_KEY, {
  auth: { persistSession: false },
});

const root = resolve(__dirname, "..");
const medicines = JSON.parse(
  readFileSync(resolve(root, "data/medicines.json"), "utf8")
) as { medicines: Array<Record<string, unknown> & { id: string; offers: Array<Record<string, unknown>> }> };
const platforms = JSON.parse(
  readFileSync(resolve(root, "data/platforms.json"), "utf8")
) as { platforms: Array<Record<string, unknown> & { id: string }> };

async function main() {
  console.log(`→ Seeding ${platforms.platforms.length} platforms...`);
  {
    const { error } = await sb.from("platforms").upsert(platforms.platforms, { onConflict: "id" });
    if (error) throw error;
  }

  console.log(`→ Seeding ${medicines.medicines.length} medicines...`);
  const medRows = medicines.medicines.map((m) => ({
    id: m.id,
    name: m.name,
    composition: m.composition,
    manufacturer: m.manufacturer,
    pack: m.pack,
    rx_required: m.rx_required,
    nppa_ceiling_inr: m.nppa_ceiling_inr,
  }));
  {
    const { error } = await sb.from("medicines").upsert(medRows, { onConflict: "id" });
    if (error) throw error;
  }

  const priceRows = medicines.medicines.flatMap((m) =>
    m.offers.map((o) => ({
      medicine_id: m.id,
      platform_id: o.pharmacy,
      price: o.price,
      mrp: o.mrp,
      delivery_days: o.delivery_days,
      in_stock: o.in_stock,
      return_days: o.return_days,
      url: o.url,
    }))
  );

  console.log(`→ Seeding ${priceRows.length} price rows...`);
  {
    const { error } = await sb
      .from("prices")
      .upsert(priceRows, { onConflict: "medicine_id,platform_id" });
    if (error) throw error;
  }

  // Sanity check: run the search RPC once
  const { data: probe, error: probeErr } = await sb.rpc("search_medicines", {
    q: "dolo",
    max_results: 3,
  });
  if (probeErr) {
    console.error("⚠  search_medicines RPC failed:", probeErr.message);
  } else {
    console.log(
      `✓ search_medicines('dolo') returned ${probe?.length ?? 0} rows (expected ≥1)`
    );
  }

  console.log("✓ Seed complete.");
}

main().catch((err) => {
  console.error("✗ Seed failed:", err);
  process.exit(1);
});

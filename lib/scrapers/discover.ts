/**
 * Discovery orchestrator: runs the three TypeScript scrapers in parallel
 * for a single user query, then chooses a canonical medicine record.
 *
 * Canonical-name precedence: 1mg > PharmEasy > Netmeds. The first
 * successful platform's name + composition + manufacturer + pack become
 * the medicine row's columns.
 */

import { scrapeNetmeds } from "./netmeds";
import { scrapeOneMg } from "./onemg";
import { scrapePharmEasy } from "./pharmeasy";
import { slugify } from "./match";
import type { CanonicalMedicine, DiscoverResult, Offer, ScrapeResult } from "./types";
import type { PharmacyId } from "@/lib/types";

/** A real product page URL has a path component beyond the bare domain
 *  (e.g. https://www.1mg.com/drugs/<slug>, https://pharmeasy.in/online-medicine-order/<slug>).
 *  Homepage-only URLs (e.g. https://www.1mg.com/) signal a category /
 *  search landing page, not a specific SKU. */
function isProductUrl(url: string): boolean {
  if (!url) return false;
  try {
    const u = new URL(url);
    // Must have at least one non-empty path segment that's not "/" alone.
    const segments = u.pathname.split("/").filter(Boolean);
    return segments.length >= 1 && u.pathname.length > 1;
  } catch {
    return false;
  }
}

/**
 * Run all 3 httpx-scrapers in parallel for a free-text query.
 * Apollo deliberately omitted — Patchright can't run in Netlify Functions;
 * it's filled in by the next scheduled cron.
 */
export async function discoverMedicine(query: string): Promise<DiscoverResult | null> {
  const trimmed = query.trim();
  if (!trimmed) return null;

  // No target_pack yet (we haven't matched anything; the user just typed a
  // free-text query). Pack-aware tiebreaker degrades gracefully — it only
  // kicks in when we DO have a pack hint.
  const settled = await Promise.allSettled([
    scrapeOneMg(trimmed),
    scrapePharmEasy(trimmed),
    scrapeNetmeds(trimmed),
  ]);

  const results: ScrapeResult[] = settled.map((s, idx) => {
    if (s.status === "fulfilled") return s.value;
    const pharmacy: PharmacyId = ["1mg", "PharmEasy", "Netmeds"][idx] as PharmacyId;
    return {
      pharmacy,
      status: "error",
      offer: null,
      error_message: s.reason instanceof Error ? s.reason.message : String(s.reason),
      duration_ms: 0,
    };
  });

  // Filter to "real" successes only. An offer counts as real iff:
  //   - mrp > 0 AND price > 0 (₹0 means the pharmacy returned a category
  //     landing page or generic placeholder, not an actual SKU); and
  //   - the URL points to a real product page, not just the homepage.
  // Without these guards, queries like "ibuprofen" or "paracetamol" (bare
  // molecule names with no brand) can produce garbage rows where one
  // pharmacy's API returns a generic listing.
  const successes = results.filter((r) => {
    if (r.status !== "success" || !r.offer) return false;
    if (r.offer.mrp <= 0 || r.offer.price <= 0) return false;
    if (!isProductUrl(r.offer.url)) return false;
    return true;
  });
  if (successes.length === 0) return null;

  // Pick canonical record. 1mg first if available, else PharmEasy, else Netmeds.
  const canonicalSource =
    successes.find((r) => r.pharmacy === "1mg") ??
    successes.find((r) => r.pharmacy === "PharmEasy") ??
    successes[0];
  const cand = canonicalSource.candidate;
  const canonicalName = cand?.name?.trim() || trimmed;

  const medicineId = slugify(canonicalName) || slugify(trimmed) || `med-${Date.now()}`;

  const medicine: CanonicalMedicine = {
    id: medicineId,
    name: canonicalName,
    composition: cand?.composition?.trim() || "Composition not available",
    manufacturer: cand?.manufacturer?.trim() || "Unknown manufacturer",
    pack: cand?.pack?.trim() || "See product page",
    rx_required: false, // best-effort default; per-scraper Rx detection is unreliable
    nppa_ceiling_inr: null,
  };

  // Stamp the medicine_id onto every successful offer so the caller can
  // UPSERT into the prices table without re-walking results.
  const offers: Offer[] = successes.map((r) => ({
    ...(r.offer as Offer),
    medicine_id: medicineId,
  }));

  return {
    medicine,
    offers,
    scrape_results: results,
    reused_existing: false,
  };
}

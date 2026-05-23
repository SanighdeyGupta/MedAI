/**
 * Tata 1mg TS scraper (mirrors `scrapers/one_mg.py`).
 *
 * Two-step pattern:
 *   1. /pharmacy_api_webservices/search?name=<query>  — JSON, robots-clean
 *   2. /drugs/<slug>                                  — HTML, parse the
 *      embedded `\"discountedPrice\":<num>` field for the website-displayed
 *      price (which includes 1mg's page-level promo, e.g. "11% off" vs the
 *      API's "5% off"). Falls back to the API price if the regex misses.
 */

import { pickBest } from "./match";
import type { Offer, ScrapeResult } from "./types";

const SEARCH_URL = "https://www.1mg.com/pharmacy_api_webservices/search";
const DISPLAYED_PRICE_RE = /\\"discountedPrice\\"\s*:\s*([\d.]+)/;
const CHROME_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

interface OneMgItem {
  name?: string;
  slug?: string;
  url?: string;
  mrp?: number;
  discounted_price?: number;
  available?: boolean;
  saleable?: boolean;
  uip?: number; // units in pack
  pForm?: string; // "Tablet" | "Capsule" | "Bottle" ...
  packSizeLabel?: string;
  manufacturer?: string;
  // 1mg sometimes returns this as a boolean, sometimes as the string "true"
  // (or, historically, as 1/0). We coerce in the consumer.
  prescriptionRequired?: boolean | string | number;
  drug_strength?: string;
}

const HEADERS = {
  "User-Agent": CHROME_UA,
  "Accept-Language": "en-IN,en;q=0.9",
  Referer: "https://www.1mg.com/",
};

export async function scrapeOneMg(query: string, pack?: string | null): Promise<ScrapeResult> {
  const start = Date.now();
  const url = `${SEARCH_URL}?name=${query.replace(/ /g, "+")}`;

  let resp: Response;
  try {
    resp = await fetch(url, {
      headers: { ...HEADERS, Accept: "application/json" },
      signal: AbortSignal.timeout(8_000),
    });
  } catch (err) {
    return {
      pharmacy: "1mg",
      status: "error",
      offer: null,
      error_message: err instanceof Error ? err.message : String(err),
      duration_ms: Date.now() - start,
    };
  }

  if (resp.status === 429) {
    return {
      pharmacy: "1mg",
      status: "rate_limited",
      offer: null,
      error_message: null,
      duration_ms: Date.now() - start,
    };
  }
  if (!resp.ok) {
    return {
      pharmacy: "1mg",
      status: "error",
      offer: null,
      error_message: `HTTP ${resp.status}`,
      duration_ms: Date.now() - start,
    };
  }

  let data: { result?: unknown[] };
  try {
    data = (await resp.json()) as { result?: unknown[] };
  } catch (err) {
    return {
      pharmacy: "1mg",
      status: "error",
      offer: null,
      error_message: `json decode: ${err instanceof Error ? err.message : err}`,
      duration_ms: Date.now() - start,
    };
  }

  const items = (data.result ?? []).filter(
    (it): it is OneMgItem => typeof it === "object" && it !== null && (it as OneMgItem).mrp !== undefined,
  );
  const { item, score } = pickBest<OneMgItem>({
    items,
    targetName: query,
    targetPack: pack,
    nameOf: (it) => it.name ?? "",
    packTextOf: (it) => `${it.packSizeLabel ?? ""} ${it.uip ?? ""} ${it.pForm ?? ""}`,
    threshold: 0.5,
  });
  if (!item) {
    return {
      pharmacy: "1mg",
      status: "not_found",
      offer: null,
      error_message: `no match >=0.50 (top=${score.toFixed(2)}, items=${items.length})`,
      duration_ms: Date.now() - start,
    };
  }

  const mrp = item.mrp;
  if (mrp === undefined) {
    return {
      pharmacy: "1mg",
      status: "error",
      offer: null,
      error_message: "missing mrp",
      duration_ms: Date.now() - start,
    };
  }
  let price = item.discounted_price ?? mrp;
  const mrpF = Number(mrp);

  // Step 2: fetch the product detail page for the website-displayed price.
  // 1mg's product page applies a dynamic page-level promo on top of the
  // search API's wholesale discount (~5% off vs the page's ~11% off).
  const path = item.url ?? "";
  if (path.startsWith("/")) {
    try {
      const detail = await fetch(`https://www.1mg.com${path}`, {
        headers: { ...HEADERS, Accept: "text/html" },
        signal: AbortSignal.timeout(6_000),
      });
      if (detail.ok) {
        const html = await detail.text();
        const m = DISPLAYED_PRICE_RE.exec(html);
        if (m) {
          const displayed = parseFloat(m[1]);
          // Sanity: must be <= MRP * 1.05 (allow small float drift).
          if (Number.isFinite(displayed) && displayed > 0 && displayed <= mrpF * 1.05) {
            price = displayed;
          }
        }
      }
    } catch {
      // Detail fetch is best-effort; fall back to API price.
    }
  }

  // 1mg sets `available=false` based on user pincode, not actual stock.
  // `saleable` is the truer warehouse-stock flag.
  const inStock = !(item.saleable === false && item.available === false);
  const rxRequired =
    item.prescriptionRequired === true || item.prescriptionRequired === "true" || item.prescriptionRequired === 1;

  const fullUrl = path.startsWith("/") ? `https://www.1mg.com${path}` : path || "https://www.1mg.com/";
  const offer: Offer = {
    pharmacy: "1mg",
    medicine_id: "",
    price: Number(price),
    mrp: mrpF,
    delivery_days: 2,
    in_stock: inStock,
    return_days: 7,
    url: fullUrl,
  };

  // Use 1mg's name as the canonical record (most consistent metadata).
  return {
    pharmacy: "1mg",
    status: "success",
    offer,
    candidate: {
      name: item.name ?? "",
      composition: item.drug_strength ?? null,
      manufacturer: item.manufacturer ?? null,
      pack: item.packSizeLabel ?? (item.uip ? `Pack of ${item.uip} ${item.pForm ?? ""}`.trim() : null),
    },
    error_message: null,
    duration_ms: Date.now() - start,
  };
}

// Re-export the rxRequired-from-1mg hint helper for the orchestrator.
export function rxFromOneMg(result: ScrapeResult): boolean | null {
  if (result.status !== "success") return null;
  // Best-effort: orchestrator already has the raw item via candidate.name;
  // we expose a hook here for future use without parsing again.
  return null;
}

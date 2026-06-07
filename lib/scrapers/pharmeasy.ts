/**
 * PharmEasy TS scraper (mirrors `scrapers/pharmeasy.py`).
 *
 * Fetches the SSR search page and parses `__NEXT_DATA__` for the
 * `props.pageProps.productList` array. (2026-06: PharmEasy renamed
 * `searchResults` -> `productList`, `manufacturerName` -> `manufacturer`,
 * `packShortName` -> `packform`.) See LEGAL.md for the robots.txt
 * posture on this endpoint.
 */

import { pickBest } from "./match";
import type { Offer, ScrapeResult } from "./types";

const SEARCH_URL = "https://pharmeasy.in/search/all";
const NEXT_DATA_RE = /<script id="__NEXT_DATA__"[^>]*>([\s\S]+?)<\/script>/;
const CHROME_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

interface PharmEasyItem {
  name?: string;
  slug?: string;
  packform?: string;
  manufacturer?: string;
  moleculeName?: string;
  salePriceDecimal?: string;
  mrpDecimal?: string;
  productAvailabilityFlags?: {
    isAvailable?: boolean;
  };
}

interface PharmEasyData {
  props?: {
    pageProps?: {
      productList?: PharmEasyItem[];
    };
  };
}

function toFloat(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const n = typeof v === "number" ? v : parseFloat(String(v));
  return Number.isFinite(n) ? n : null;
}

export async function scrapePharmEasy(query: string, pack?: string | null): Promise<ScrapeResult> {
  const start = Date.now();
  const url = `${SEARCH_URL}?name=${query.replace(/ /g, "+")}`;

  let resp: Response;
  try {
    resp = await fetch(url, {
      headers: {
        "User-Agent": CHROME_UA,
        Accept: "text/html,application/xhtml+xml",
        "Accept-Language": "en-IN,en;q=0.9",
        Referer: "https://pharmeasy.in/",
      },
      signal: AbortSignal.timeout(5_500),
    });
  } catch (err) {
    return {
      pharmacy: "PharmEasy",
      status: "error",
      offer: null,
      error_message: err instanceof Error ? err.message : String(err),
      duration_ms: Date.now() - start,
    };
  }

  if (resp.status === 429) {
    return {
      pharmacy: "PharmEasy",
      status: "rate_limited",
      offer: null,
      error_message: null,
      duration_ms: Date.now() - start,
    };
  }
  if (!resp.ok) {
    return {
      pharmacy: "PharmEasy",
      status: "error",
      offer: null,
      error_message: `HTTP ${resp.status}`,
      duration_ms: Date.now() - start,
    };
  }

  const html = await resp.text();
  const m = NEXT_DATA_RE.exec(html);
  if (!m) {
    return {
      pharmacy: "PharmEasy",
      status: "error",
      offer: null,
      error_message: "__NEXT_DATA__ not found",
      duration_ms: Date.now() - start,
    };
  }

  let data: PharmEasyData;
  try {
    data = JSON.parse(m[1]) as PharmEasyData;
  } catch (err) {
    return {
      pharmacy: "PharmEasy",
      status: "error",
      offer: null,
      error_message: `json decode: ${err instanceof Error ? err.message : err}`,
      duration_ms: Date.now() - start,
    };
  }

  const items = data.props?.pageProps?.productList ?? [];
  const { item, score } = pickBest<PharmEasyItem>({
    items,
    targetName: query,
    targetPack: pack,
    nameOf: (it) => it.name ?? "",
    packTextOf: (it) => `${it.packform ?? ""} ${it.manufacturer ?? ""}`,
    threshold: 0.5,
  });
  if (!item) {
    return {
      pharmacy: "PharmEasy",
      status: "not_found",
      offer: null,
      error_message: `no match >=0.50 (top=${score.toFixed(2)}, items=${items.length})`,
      duration_ms: Date.now() - start,
    };
  }

  const sale = toFloat(item.salePriceDecimal);
  const mrp = toFloat(item.mrpDecimal);
  if (sale === null || mrp === null) {
    return {
      pharmacy: "PharmEasy",
      status: "error",
      offer: null,
      error_message: "missing salePriceDecimal / mrpDecimal",
      duration_ms: Date.now() - start,
    };
  }

  const slug = item.slug ?? "";
  const offer: Offer = {
    pharmacy: "PharmEasy",
    medicine_id: "",
    price: sale,
    mrp,
    delivery_days: 3,
    in_stock: Boolean(item.productAvailabilityFlags?.isAvailable),
    return_days: 7,
    url: slug ? `https://pharmeasy.in/online-medicine-order/${slug}` : "https://pharmeasy.in/",
  };

  return {
    pharmacy: "PharmEasy",
    status: "success",
    offer,
    candidate: {
      name: item.name ?? "",
      composition: item.moleculeName ?? null,
      manufacturer: item.manufacturer ?? null,
      pack: item.packform ?? null,
    },
    error_message: null,
    duration_ms: Date.now() - start,
  };
}

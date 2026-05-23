/**
 * Netmeds TS scraper (mirrors `scrapers/netmeds.py`).
 *
 * Uses the official Fynd-platform search API. robots-clean (the /ext/
 * path is not in netmeds.com/robots.txt's Disallow list).
 */

import { pickBest } from "./match";
import type { Offer, ScrapeResult } from "./types";

const SEARCH_URL = "https://www.netmeds.com/ext/search/application/api/v1.0/products";
const CHROME_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

interface NetmedsItem {
  name?: string;
  slug?: string;
  sellable?: boolean;
  price?: {
    effective?: { min?: number };
    marked?: { min?: number };
  };
}

export async function scrapeNetmeds(query: string, pack?: string | null): Promise<ScrapeResult> {
  const start = Date.now();
  const url = `${SEARCH_URL}?q=${encodeURIComponent(query)}&page_size=5`;
  let resp: Response;
  try {
    resp = await fetch(url, {
      headers: {
        "User-Agent": CHROME_UA,
        Accept: "application/json",
        Referer: "https://www.netmeds.com/",
        "Accept-Language": "en-IN,en;q=0.9",
      },
      signal: AbortSignal.timeout(8_000),
    });
  } catch (err) {
    return {
      pharmacy: "Netmeds",
      status: "error",
      offer: null,
      error_message: err instanceof Error ? err.message : String(err),
      duration_ms: Date.now() - start,
    };
  }

  if (resp.status === 429) {
    return {
      pharmacy: "Netmeds",
      status: "rate_limited",
      offer: null,
      error_message: null,
      duration_ms: Date.now() - start,
    };
  }
  if (!resp.ok) {
    return {
      pharmacy: "Netmeds",
      status: "error",
      offer: null,
      error_message: `HTTP ${resp.status}`,
      duration_ms: Date.now() - start,
    };
  }

  let data: { items?: NetmedsItem[] };
  try {
    data = (await resp.json()) as { items?: NetmedsItem[] };
  } catch (err) {
    return {
      pharmacy: "Netmeds",
      status: "error",
      offer: null,
      error_message: `json decode: ${err instanceof Error ? err.message : err}`,
      duration_ms: Date.now() - start,
    };
  }

  const items = data.items ?? [];
  const { item, score } = pickBest<NetmedsItem>({
    items,
    targetName: query,
    targetPack: pack,
    nameOf: (it) => it.name ?? "",
    threshold: 0.55,
  });
  if (!item) {
    return {
      pharmacy: "Netmeds",
      status: "not_found",
      offer: null,
      error_message: `no match >=0.55 (top=${score.toFixed(2)})`,
      duration_ms: Date.now() - start,
    };
  }

  const price = item.price?.effective?.min;
  const mrp = item.price?.marked?.min;
  if (price === undefined || mrp === undefined) {
    return {
      pharmacy: "Netmeds",
      status: "error",
      offer: null,
      error_message: "missing price.effective.min / marked.min",
      duration_ms: Date.now() - start,
    };
  }

  const slug = item.slug ?? "";
  const offer: Offer = {
    pharmacy: "Netmeds",
    medicine_id: "", // filled in by orchestrator
    price: Number(price),
    mrp: Number(mrp),
    delivery_days: 4,
    in_stock: Boolean(item.sellable),
    return_days: 5,
    url: slug ? `https://www.netmeds.com/product/${slug}` : "https://www.netmeds.com/",
  };

  return {
    pharmacy: "Netmeds",
    status: "success",
    offer,
    candidate: {
      name: item.name ?? "",
      composition: null, // Netmeds Fynd payload doesn't expose composition cleanly
      manufacturer: null,
      pack: null,
    },
    error_message: null,
    duration_ms: Date.now() - start,
  };
}

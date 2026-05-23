/**
 * Shared types for the TypeScript scrapers that run inside Netlify
 * Functions (the on-demand `/api/discover` path).
 *
 * The wire contracts mirror the Python scrapers in `scrapers/*.py` so the
 * row shape we write into Supabase is identical between the scheduled
 * crawler and the live discoverer.
 */

import type { PharmacyId } from "@/lib/types";

export interface Offer {
  pharmacy: PharmacyId;
  medicine_id: string;
  price: number;
  mrp: number;
  delivery_days: number;
  in_stock: boolean;
  return_days: number;
  url: string;
}

export interface CanonicalMedicine {
  /** Slugified id, e.g. "glycomet-gp1" */
  id: string;
  name: string;
  composition: string;
  manufacturer: string;
  pack: string;
  rx_required: boolean;
  /** Optional NPPA ceiling from a future ingest; null for now. */
  nppa_ceiling_inr: number | null;
}

export type ScrapeStatus = "success" | "not_found" | "blocked" | "error" | "rate_limited";

export interface ScrapeResult {
  pharmacy: PharmacyId;
  status: ScrapeStatus;
  offer: Offer | null;
  /** When status === 'success', the pharmacy's own canonical name + slug,
   *  so the orchestrator can pick a master record. */
  candidate?: {
    name: string;
    composition: string | null;
    manufacturer: string | null;
    pack: string | null;
  };
  error_message: string | null;
  duration_ms: number;
}

export interface DiscoverResult {
  /** The canonical medicine record we INSERTed (or matched against existing). */
  medicine: CanonicalMedicine;
  /** Successful per-platform offers, ready to UPSERT into `prices`. */
  offers: Offer[];
  /** Per-platform status for telemetry / UI ("Apollo refreshes every 6h"). */
  scrape_results: ScrapeResult[];
  /** True when we matched an existing DB row instead of creating a new one. */
  reused_existing: boolean;
}

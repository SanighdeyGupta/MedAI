import medicinesData from "@/data/medicines.json";
import platformsData from "@/data/platforms.json";
import { getSupabase } from "@/lib/db";
import { nameScore, slugify } from "@/lib/scrapers/match";
import type { Medicine, Offer, PharmacyId, Platform } from "@/lib/types";

const JSON_MEDICINES: Medicine[] = (medicinesData as { medicines: Medicine[] }).medicines;
const JSON_PLATFORMS: Platform[] = (platformsData as { platforms: Platform[] }).platforms;

// ---------- helpers (DB row → app shape) ----------

interface DbPriceRow {
  medicine_id: string;
  platform_id: string;
  price: number | string;
  mrp: number | string;
  delivery_days: number;
  in_stock: boolean;
  return_days: number;
  url: string;
  fetched_at?: string;
}

function rowToOffer(p: DbPriceRow): Offer {
  return {
    pharmacy: p.platform_id as PharmacyId,
    price: Number(p.price),
    mrp: Number(p.mrp),
    delivery_days: p.delivery_days,
    in_stock: p.in_stock,
    return_days: p.return_days,
    url: p.url,
    fetched_at: p.fetched_at,
  };
}

// ---------- public API ----------

function findMedicineByIdJson(id: string): Medicine | undefined {
  return JSON_MEDICINES.find((m) => m.id === id);
}

export async function findMedicineById(id: string): Promise<Medicine | undefined> {
  const sb = getSupabase();
  if (!sb) return findMedicineByIdJson(id);

  try {
    const { data: m, error } = await sb
      .from("medicines")
      .select("*")
      .eq("id", id)
      .maybeSingle();
    if (error) throw error;
    if (!m) return findMedicineByIdJson(id); // unknown id even in DB; check JSON
    const { data: prices, error: pErr } = await sb
      .from("prices")
      .select("*")
      .eq("medicine_id", id);
    if (pErr) throw pErr;
    return {
      id: m.id,
      name: m.name,
      composition: m.composition,
      manufacturer: m.manufacturer,
      pack: m.pack,
      rx_required: m.rx_required,
      nppa_ceiling_inr:
        m.nppa_ceiling_inr === null ? null : Number(m.nppa_ceiling_inr),
      offers: (prices ?? []).map(rowToOffer),
    };
  } catch (err) {
    console.warn("[medicines] DB read failed, falling back to JSON:", (err as Error).message);
    return findMedicineByIdJson(id);
  }
}

// Bare-bones medicine row shape returned by the supabase client for the
// `medicines` table. Mirrors what we map to `Medicine` (offers added separately).
interface DbMedicineRow {
  id: string;
  name: string;
  composition: string;
  manufacturer: string;
  pack: string;
  rx_required: boolean;
  nppa_ceiling_inr: number | string | null;
}

export async function searchMedicines(query: string, limit = 8): Promise<Medicine[]> {
  const q = query.trim();
  if (!q) return [];

  const sb = getSupabase();
  if (sb) {
    try {
      // Run two queries in parallel:
      //   (a) pg_trgm RPC — catches semantic-similar fuzzy matches.
      //   (b) slug-prefix + name-substring lookup — catches the case where
      //       the DB row's canonical name has spacing/punctuation that
      //       breaks trigram (e.g. user types "Glycomet GP1" but the row is
      //       "Glycomet-GP 1 Tablet PR" → trigram doesn't see "gp1" as
      //       three consecutive chars in the candidate).
      const slug = slugify(q);
      const slugClauses = slug.length >= 3
        ? `id.ilike.${slug}%,id.ilike.%${slug}%`
        : "";
      const nameClause = `name.ilike.%${q}%,composition.ilike.%${q}%`;

      const [rpcRes, fallbackRes] = await Promise.all([
        sb.rpc("search_medicines", { q, max_results: limit }),
        sb
          .from("medicines")
          .select("id,name,composition,manufacturer,pack,rx_required,nppa_ceiling_inr")
          .or(slugClauses ? `${slugClauses},${nameClause}` : nameClause)
          .limit(limit * 2),
      ]);

      const combined = new Map<string, DbMedicineRow>();
      if (!rpcRes.error && rpcRes.data) {
        for (const m of rpcRes.data as DbMedicineRow[]) combined.set(m.id, m);
      }
      if (!fallbackRes.error && fallbackRes.data) {
        for (const m of fallbackRes.data as DbMedicineRow[]) {
          if (!combined.has(m.id)) combined.set(m.id, m);
        }
      }

      if (combined.size === 0) return [];

      // Re-rank by our own nameScore (handles slug/spacing variance correctly).
      const ranked = Array.from(combined.values())
        .map((m) => ({
          medicine: m,
          score: Math.max(nameScore(q, m.name), nameScore(q, m.id)),
        }))
        .filter((s) => s.score >= 0.18)
        .sort((a, b) => b.score - a.score)
        .slice(0, limit);

      const ids = ranked.map((r) => r.medicine.id);
      if (ids.length === 0) return [];
      const { data: prices } = await sb.from("prices").select("*").in("medicine_id", ids);
      const byMed = new Map<string, Offer[]>();
      (prices ?? []).forEach((p: DbPriceRow) => {
        const list = byMed.get(p.medicine_id) ?? [];
        list.push(rowToOffer(p));
        byMed.set(p.medicine_id, list);
      });

      return ranked.map(({ medicine: m }) => ({
        id: m.id,
        name: m.name,
        composition: m.composition,
        manufacturer: m.manufacturer,
        pack: m.pack,
        rx_required: m.rx_required,
        nppa_ceiling_inr: m.nppa_ceiling_inr === null ? null : Number(m.nppa_ceiling_inr),
        offers: byMed.get(m.id) ?? [],
      }));
    } catch (err) {
      console.warn("[medicines] search hybrid path failed, falling back to JSON:", (err as Error).message);
    }
  }

  // JSON fallback (Day 1 behavior)
  const ql = q.toLowerCase();
  const scored = JSON_MEDICINES.map((m) => {
    const name = m.name.toLowerCase();
    const comp = m.composition.toLowerCase();
    let score = 0;
    if (name === ql) score = 1000;
    else if (name.startsWith(ql)) score = 500;
    else if (name.includes(ql)) score = 200;
    else if (comp.includes(ql)) score = 50;
    else {
      const tokens = ql.split(/\s+/).filter(Boolean);
      const matched = tokens.filter((t) => name.includes(t) || comp.includes(t)).length;
      if (matched > 0) score = 10 * matched;
    }
    return { medicine: m, score };
  })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
  return scored.map((s) => s.medicine);
}

export async function getPlatforms(): Promise<Platform[]> {
  const sb = getSupabase();
  if (!sb) return JSON_PLATFORMS;
  try {
    const { data, error } = await sb.from("platforms").select("*");
    if (error) throw error;
    if (data && data.length > 0) return data as Platform[];
    return JSON_PLATFORMS;
  } catch (err) {
    console.warn("[platforms] DB read failed, falling back to JSON:", (err as Error).message);
    return JSON_PLATFORMS;
  }
}

export async function getPlatform(id: string): Promise<Platform | undefined> {
  const platforms = await getPlatforms();
  return platforms.find((p) => p.id === id);
}

export function getPopularMedicineIds(): string[] {
  return [
    "dolo-650",
    "crocin-advance-500",
    "pan-40",
    "azithral-500",
    "cetirizine-10",
    "combiflam",
    "saridon",
    "ecosprin-75",
  ];
}

export function isDbBacked(): boolean {
  return getSupabase() !== null;
}

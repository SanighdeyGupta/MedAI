export type PharmacyId = "1mg" | "PharmEasy" | "Netmeds" | "Apollo";

export interface Offer {
  pharmacy: PharmacyId;
  price: number;
  mrp: number;
  delivery_days: number;
  in_stock: boolean;
  return_days: number;
  url: string;
  fetched_at?: string;
}

export interface Medicine {
  id: string;
  name: string;
  composition: string;
  manufacturer: string;
  pack: string;
  rx_required: boolean;
  nppa_ceiling_inr: number | null;
  offers: Offer[];
}

export interface Platform {
  id: PharmacyId;
  name: string;
  trust: number;
  color: string;
  gradient: string;
  domain: string;
}

export interface ScoredOffer extends Offer {
  score: number;
  contributions: {
    price: number;
    eta: number;
    stock: number;
    trust: number;
    rx: number;
    return: number;
  };
  savingsVsWorst: number;
}

export interface RankResult {
  winner: ScoredOffer;
  ranked: ScoredOffer[];
  explanation: string;
}

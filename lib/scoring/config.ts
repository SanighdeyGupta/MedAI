import type { PharmacyId } from "@/lib/types";

export const WEIGHTS = {
  price: 0.45,
  eta: 0.20,
  stock: 0.15,
  trust: 0.10,
  rx: 0.05,
  return: 0.05,
} as const;

export const TRUST: Record<PharmacyId, number> = {
  "1mg": 0.90,
  PharmEasy: 0.85,
  Apollo: 0.90,
  Netmeds: 0.80,
};

export const FILTERS = {
  minDaysToExpiry: 90,
  dropOutOfStockFromRanking: true,
} as const;

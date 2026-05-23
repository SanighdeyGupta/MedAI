import type { Offer, RankResult, ScoredOffer } from "@/lib/types";
import { TRUST, WEIGHTS } from "./config";
import { explain } from "./explainer";

function normLowerBetter(x: number, xs: number[]): number {
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  if (hi === lo) return 1;
  return (hi - x) / (hi - lo);
}

function normHigherBetter(x: number, xs: number[]): number {
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  if (hi === lo) return 1;
  return (x - lo) / (hi - lo);
}

export function rankOffers(
  offers: Offer[],
  opts: { rxAvailable?: boolean } = {}
): RankResult | null {
  if (offers.length === 0) return null;

  const rxAvailable = opts.rxAvailable ?? false;
  const eligible = offers.filter((o) => o.in_stock);
  const pool = eligible.length > 0 ? eligible : offers;

  const prices = pool.map((o) => o.price);
  const etas = pool.map((o) => o.delivery_days);
  const returns = pool.map((o) => o.return_days);
  const maxPrice = Math.max(...prices);

  const scored: ScoredOffer[] = pool.map((o) => {
    const fPrice = normLowerBetter(o.price, prices);
    const fEta = normLowerBetter(o.delivery_days, etas);
    const fStock = o.in_stock ? 1 : 0;
    const fTrust = TRUST[o.pharmacy] ?? 0.5;
    const fRx = !rxAvailable ? 1 : 0.6;
    const fReturn = normHigherBetter(o.return_days, returns);

    const contributions = {
      price: WEIGHTS.price * fPrice,
      eta: WEIGHTS.eta * fEta,
      stock: WEIGHTS.stock * fStock,
      trust: WEIGHTS.trust * fTrust,
      rx: WEIGHTS.rx * fRx,
      return: WEIGHTS.return * fReturn,
    };

    const score =
      100 *
      (contributions.price +
        contributions.eta +
        contributions.stock +
        contributions.trust +
        contributions.rx +
        contributions.return);

    return {
      ...o,
      score,
      contributions,
      savingsVsWorst: Math.max(0, maxPrice - o.price),
    };
  });

  const ranked = [...scored].sort((a, b) => b.score - a.score);
  const winner = ranked[0];
  const second = ranked[1];

  return {
    winner,
    ranked,
    explanation: explain(winner, second),
  };
}

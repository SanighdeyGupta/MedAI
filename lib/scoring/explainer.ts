import type { ScoredOffer } from "@/lib/types";

const PHARMACY_LABEL: Record<string, string> = {
  "1mg": "Tata 1mg",
  PharmEasy: "PharmEasy",
  Netmeds: "Netmeds",
  Apollo: "Apollo Pharmacy",
};

interface Reason {
  key: string;
  weighted: number;
  text: string;
}

function reasonsFor(o: ScoredOffer): Reason[] {
  return [
    {
      key: "cheaper",
      weighted: o.contributions.price,
      text:
        o.savingsVsWorst > 0
          ? `₹${o.savingsVsWorst.toFixed(0)} less than the costliest option`
          : "competitively priced",
    },
    {
      key: "faster",
      weighted: o.contributions.eta,
      text:
        o.delivery_days <= 1
          ? "delivered next-day"
          : `delivered in ${o.delivery_days} days`,
    },
    {
      key: "stock",
      weighted: o.contributions.stock,
      text: o.in_stock ? "available now" : "currently out of stock",
    },
    {
      key: "trust",
      weighted: o.contributions.trust,
      text: `${PHARMACY_LABEL[o.pharmacy] ?? o.pharmacy} is a top-rated pharmacy`,
    },
    {
      key: "return",
      weighted: o.contributions.return,
      text: `${o.return_days}-day return window`,
    },
  ];
}

export function explain(winner: ScoredOffer, rival?: ScoredOffer): string {
  const sorted = reasonsFor(winner).sort((a, b) => b.weighted - a.weighted);
  const strengths = sorted.slice(0, 2);
  const weakness = sorted.filter((r) => r.weighted < 0.04).slice(-1)[0];

  const label = PHARMACY_LABEL[winner.pharmacy] ?? winner.pharmacy;
  const strengthsText = strengths.map((s) => s.text).join(" and ");
  const tradeOff = weakness ? `, though ${weakness.text}` : "";

  let comparative = "";
  if (rival && rival.pharmacy !== winner.pharmacy) {
    const priceDiff = rival.price - winner.price;
    const etaDiff = rival.delivery_days - winner.delivery_days;
    if (priceDiff > 0 && etaDiff >= 0) {
      comparative = ` Beats ${PHARMACY_LABEL[rival.pharmacy] ?? rival.pharmacy} by ₹${priceDiff.toFixed(0)}.`;
    } else if (priceDiff < 0 && etaDiff > 0) {
      comparative = ` Slightly pricier than ${PHARMACY_LABEL[rival.pharmacy] ?? rival.pharmacy} but arrives ${etaDiff} day(s) sooner.`;
    }
  }

  return `${label} wins — ${strengthsText}${tradeOff}.${comparative}`;
}

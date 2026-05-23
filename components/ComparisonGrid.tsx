import { getPlatforms } from "@/lib/medicines";
import { formatAgo, freshnessOf } from "@/lib/format";
import type { Platform, ScoredOffer } from "@/lib/types";

const FRESHNESS_COLOR = {
  fresh: "text-[#86efac]",
  ok: "text-white/60",
  stale: "text-[#fbbf24]",
  old: "text-[#fda4af]",
} as const;

interface Props {
  offers: ScoredOffer[];
  mrp: number;
  winnerId: string;
}

export default async function ComparisonGrid({ offers, mrp, winnerId }: Props) {
  const platforms = await getPlatforms();
  const byId = new Map<string, Platform>(platforms.map((p) => [p.id, p]));

  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {offers.map((o) => {
        const platform = byId.get(o.pharmacy);
        const isWinner = o.pharmacy === winnerId;
        const discountPct = mrp > 0 ? Math.round(((mrp - o.price) / mrp) * 100) : 0;

        return (
          <a
            key={o.pharmacy}
            href={o.url}
            target="_blank"
            rel="noreferrer noopener"
            className={`relative glass rounded-2xl p-5 lift overflow-hidden group ${
              isWinner ? "ring-1 ring-white/30" : ""
            }`}
          >
            <div
              className="absolute top-0 left-0 right-0 h-1 opacity-80"
              style={{ background: platform?.gradient ?? "transparent" }}
            />

            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ background: platform?.color }}
                />
                <span className="text-white font-medium">{platform?.name ?? o.pharmacy}</span>
              </div>
              {isWinner && (
                <span className="text-[10px] uppercase tracking-wider text-[#86efac] bg-[#22c55e]/15 px-2 py-0.5 rounded-full border border-[#22c55e]/25">
                  Winner
                </span>
              )}
            </div>

            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-2xl font-semibold text-white">₹{o.price.toFixed(2)}</span>
              {o.price < mrp && (
                <span className="text-white/40 line-through text-sm">₹{mrp.toFixed(2)}</span>
              )}
              {discountPct > 0 && (
                <span className="text-[#86efac] text-xs font-medium">{discountPct}% off</span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2 mt-4 text-xs">
              <Stat label="Delivery" value={o.delivery_days <= 1 ? "Next day" : `${o.delivery_days} days`} />
              <Stat
                label="Stock"
                value={o.in_stock ? "In stock" : "Out of stock"}
                tone={o.in_stock ? "good" : "bad"}
              />
              <Stat label="Return" value={`${o.return_days} days`} />
              <Stat label="Score" value={`${o.score.toFixed(0)}`} />
            </div>

            <div className="mt-4 flex items-center justify-between text-xs">
              <span className={FRESHNESS_COLOR[freshnessOf(o.fetched_at)]}>
                ● {formatAgo(o.fetched_at)}
              </span>
              <span className="text-white/70 group-hover:text-white transition-colors">
                Open ↗
              </span>
            </div>
          </a>
        );
      })}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "bad";
}) {
  const color =
    tone === "good" ? "text-[#86efac]" : tone === "bad" ? "text-[#fda4af]" : "text-white/85";
  return (
    <div className="rounded-lg bg-white/[0.03] border border-white/5 px-2.5 py-2">
      <div className="text-white/40 text-[10px] uppercase tracking-wider mb-0.5">{label}</div>
      <div className={`text-sm font-medium ${color}`}>{value}</div>
    </div>
  );
}

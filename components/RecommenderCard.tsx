import { getPlatform } from "@/lib/medicines";
import type { ScoredOffer } from "@/lib/types";

interface Props {
  winner: ScoredOffer;
  explanation: string;
  mrp: number;
}

export default async function RecommenderCard({ winner, explanation, mrp }: Props) {
  const platform = await getPlatform(winner.pharmacy);
  const discountPct = mrp > 0 ? Math.round(((mrp - winner.price) / mrp) * 100) : 0;

  return (
    <div className="relative glass-strong rounded-3xl p-7 sm:p-8 overflow-hidden glow float-in">
      <div
        className="absolute inset-0 opacity-30 pointer-events-none"
        style={{ background: platform?.gradient ?? "transparent" }}
      />
      <div className="absolute -top-12 -right-12 w-48 h-48 rounded-full blur-3xl opacity-40"
        style={{ background: platform?.color ?? "#7c5cff" }}
      />

      <div className="relative">
        <div className="flex items-center justify-between gap-4 flex-wrap mb-5">
          <div className="inline-flex items-center gap-2 glass rounded-full px-3 py-1 text-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e] animate-pulse" />
            <span className="text-white/80 uppercase tracking-wider font-medium">Best deal</span>
          </div>
          <div className="text-xs text-white/50">Match score · <span className="text-white/80 font-medium">{winner.score.toFixed(0)} / 100</span></div>
        </div>

        <div className="flex items-baseline gap-3 flex-wrap mb-2">
          <h2 className="text-3xl sm:text-4xl font-semibold text-white tracking-tight">
            {platform?.name ?? winner.pharmacy}
          </h2>
          {discountPct > 0 && (
            <span className="rounded-full bg-[#22c55e]/20 text-[#86efac] border border-[#22c55e]/30 text-xs font-medium px-2.5 py-1">
              {discountPct}% off
            </span>
          )}
        </div>

        <div className="flex items-baseline gap-3 flex-wrap mb-5">
          <span className="text-5xl font-semibold text-white tracking-tight">₹{winner.price.toFixed(2)}</span>
          {winner.price < mrp && (
            <span className="text-white/40 line-through text-lg">₹{mrp.toFixed(2)}</span>
          )}
          <span className="text-white/60 text-sm">
            · {winner.delivery_days <= 1 ? "delivered tomorrow" : `${winner.delivery_days} day delivery`}
          </span>
        </div>

        <p className="text-white/80 leading-relaxed text-base sm:text-lg mb-6 max-w-2xl">
          {explanation}
        </p>

        <a
          href={winner.url}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-2 rounded-full bg-white text-black font-medium px-6 py-3 hover:bg-white/90 transition-colors"
        >
          Buy on {platform?.name ?? winner.pharmacy}
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7-7 7M5 12h16" />
          </svg>
        </a>
      </div>
    </div>
  );
}

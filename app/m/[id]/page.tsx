import Link from "next/link";
import { notFound } from "next/navigation";
import SearchBar from "@/components/SearchBar";
import RecommenderCard from "@/components/RecommenderCard";
import ComparisonGrid from "@/components/ComparisonGrid";
import { findMedicineById } from "@/lib/medicines";
import { rankOffers } from "@/lib/scoring/ranker";
import { freshnessOf } from "@/lib/format";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function MedicinePage({ params }: PageProps) {
  const { id } = await params;
  const medicine = await findMedicineById(id);
  if (!medicine) notFound();

  const ranking = rankOffers(medicine.offers);
  if (!ranking) notFound();

  const mrp = Math.max(...medicine.offers.map((o) => o.mrp));

  // Worst-case freshness across all offers drives the banner.
  const freshnesses = medicine.offers.map((o) => freshnessOf(o.fetched_at));
  const hasOld = freshnesses.includes("old");
  const hasStale = hasOld || freshnesses.includes("stale");
  const allDemo = medicine.offers.every((o) => !o.fetched_at);

  return (
    <div className="flex flex-col flex-1">
      <header className="px-6 sm:px-10 py-6 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-white font-semibold tracking-tight">
          <span className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#22d3ee] flex items-center justify-center text-white shadow-lg shadow-[#7c5cff]/30">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-3-3v6m9-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </span>
          <span className="text-lg">MedAI</span>
        </Link>
        <Link href="/" className="text-sm text-white/60 hover:text-white transition-colors">
          ← Back to search
        </Link>
      </header>

      <main className="flex-1 px-6 pb-24 max-w-5xl w-full mx-auto">
        <div className="mb-8">
          <SearchBar size="md" />
        </div>

        <section className="mb-8 float-in">
          <div className="flex items-baseline gap-3 flex-wrap mb-2">
            <h1 className="text-3xl sm:text-4xl font-semibold text-white tracking-tight">
              {medicine.name}
            </h1>
            {medicine.rx_required && (
              <span className="text-xs uppercase tracking-wider rounded-full bg-[#f43f5e]/15 text-[#fda4af] border border-[#f43f5e]/30 px-2.5 py-1">
                Rx required
              </span>
            )}
          </div>
          <div className="text-white/60 text-sm">
            {medicine.composition} · {medicine.manufacturer} · {medicine.pack}
          </div>
          {medicine.nppa_ceiling_inr && (
            <div className="mt-3 inline-flex items-center gap-2 glass rounded-full px-3 py-1.5 text-xs">
              <span className="text-[#22d3ee]">●</span>
              <span className="text-white/80">
                NPPA ceiling price (DPCO 2026):{" "}
                <span className="font-semibold text-white">
                  ₹{medicine.nppa_ceiling_inr.toFixed(2)}
                </span>
              </span>
            </div>
          )}
        </section>

        {(allDemo || hasStale) && (
          <div
            className={`mb-6 rounded-2xl px-4 py-3 text-sm flex items-start gap-3 ${
              allDemo
                ? "bg-[#22d3ee]/10 border border-[#22d3ee]/25 text-[#a5f3fc]"
                : hasOld
                ? "bg-[#f43f5e]/10 border border-[#f43f5e]/25 text-[#fda4af]"
                : "bg-[#fbbf24]/10 border border-[#fbbf24]/25 text-[#fcd34d]"
            }`}
          >
            <span className="flex-shrink-0 mt-0.5">●</span>
            <div>
              {allDemo ? (
                <>
                  <span className="font-medium">Demo data.</span> Live prices flow in
                  via scheduled scrapers (every 6h). Run{" "}
                  <code className="text-xs bg-black/30 px-1.5 py-0.5 rounded">npm run seed</code>
                  {" "}then trigger a scraper to see real prices.
                </>
              ) : hasOld ? (
                <>
                  <span className="font-medium">Some prices are over 7 days old.</span>{" "}
                  The scheduled scraper may have failed — check{" "}
                  <code className="text-xs bg-black/30 px-1.5 py-0.5 rounded">scrape_log</code>
                  {" "}in Supabase. We&rsquo;re showing the last-known cache.
                </>
              ) : (
                <>
                  <span className="font-medium">Prices may be slightly stale.</span>{" "}
                  Scheduled refresh runs every 6 hours — next platform card with a yellow
                  dot is older than 24h.
                </>
              )}
            </div>
          </div>
        )}

        <section className="mb-10">
          <RecommenderCard
            winner={ranking.winner}
            explanation={ranking.explanation}
            mrp={mrp}
          />
        </section>

        <section>
          <div className="flex items-baseline justify-between mb-4">
            <h3 className="text-lg text-white font-medium">All platforms</h3>
            <span className="text-xs text-white/40">
              Ranked by composite score · price has 45% weight
            </span>
          </div>
          <ComparisonGrid
            offers={ranking.ranked}
            mrp={mrp}
            winnerId={ranking.winner.pharmacy}
          />
        </section>

        <section className="mt-12 glass rounded-2xl p-5 text-xs text-white/60 flex items-start gap-3">
          <span className="text-[#fbbf24] mt-0.5">●</span>
          <div>
            <span className="text-white/85 font-medium">Prices may vary by ~5-15%</span> based on
            session-specific coupons (Tata Neu / NMS Cash / unlock-coupon offers), pincode-based
            pricing, and time-limited promos. We capture the default page-displayed price from each
            pharmacy. Click through to verify the final cart total before paying.
          </div>
        </section>

        <section className="mt-6 glass rounded-2xl p-6 text-sm text-white/60">
          <div className="text-white font-medium mb-2">How the recommendation works</div>
          <p>
            We score every offer on six features — effective price (45%), delivery ETA (20%),
            stock availability (15%), platform trust (10%), prescription friction (5%), return
            window (5%) — normalized within this query. Out-of-stock offers and items expiring
            in &lt; 90 days are dropped before ranking.
          </p>
        </section>

        <section className="mt-6 text-center text-xs text-white/40">
          Day 1 demo · prices shown are illustrative seed data. Live scrapers come online from Day 3.
        </section>
      </main>
    </div>
  );
}

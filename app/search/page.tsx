import Link from "next/link";
import SearchBar from "@/components/SearchBar";
import { searchMedicines } from "@/lib/medicines";

interface PageProps {
  searchParams: Promise<{ q?: string }>;
}

export default async function SearchPage({ searchParams }: PageProps) {
  const { q = "" } = await searchParams;
  const results = q ? await searchMedicines(q, 20) : [];

  return (
    <div className="flex flex-col flex-1">
      <header className="px-6 sm:px-10 py-6 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-white font-semibold tracking-tight">
          <span className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#22d3ee] flex items-center justify-center" />
          <span className="text-lg">MedAI</span>
        </Link>
        <Link href="/" className="text-sm text-white/60 hover:text-white transition-colors">
          ← Home
        </Link>
      </header>

      <main className="flex-1 px-6 pb-24 max-w-3xl w-full mx-auto">
        <div className="mb-8">
          <SearchBar initialQuery={q} size="md" />
        </div>

        {q && (
          <div className="text-sm text-white/60 mb-5">
            {results.length} result{results.length === 1 ? "" : "s"} for{" "}
            <span className="text-white">&ldquo;{q}&rdquo;</span>
          </div>
        )}

        {results.length === 0 && q ? (
          <div className="glass rounded-2xl p-8 text-center">
            <div className="text-white text-lg mb-2">No matches found</div>
            <div className="text-white/60 text-sm">
              Try the brand name (e.g. &ldquo;Dolo&rdquo;) or the molecule (e.g. &ldquo;Paracetamol&rdquo;).
            </div>
          </div>
        ) : (
          <div className="space-y-3 float-in">
            {results.map((m) => {
              const bestPrice = Math.min(...m.offers.map((o) => o.price));
              const maxMrp = Math.max(...m.offers.map((o) => o.mrp));
              const discountPct =
                maxMrp > 0 ? Math.round(((maxMrp - bestPrice) / maxMrp) * 100) : 0;
              return (
                <Link
                  key={m.id}
                  href={`/m/${m.id}`}
                  className="glass rounded-2xl p-5 flex items-center justify-between gap-4 lift"
                >
                  <div className="min-w-0">
                    <div className="text-white font-medium text-lg truncate">{m.name}</div>
                    <div className="text-white/50 text-sm truncate">
                      {m.composition} · {m.pack}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-white text-xl font-semibold">₹{bestPrice.toFixed(2)}</div>
                    <div className="text-white/50 text-xs">
                      Best of 4 · {discountPct}% off MRP
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

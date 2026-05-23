import Link from "next/link";
import SearchBar from "@/components/SearchBar";
import PopularChips from "@/components/PopularChips";

export default function Home() {
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
        <nav className="hidden sm:flex gap-6 text-sm text-white/60">
          <a href="#how" className="hover:text-white transition-colors">How it works</a>
          <a href="#data" className="hover:text-white transition-colors">Data sources</a>
          <a
            href="https://github.com"
            className="hover:text-white transition-colors"
            target="_blank"
            rel="noreferrer"
          >
            GitHub ↗
          </a>
        </nav>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center px-6 pt-8 pb-24">
        <div className="w-full max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 text-xs text-white/70 mb-6 float-in">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22d3ee] animate-pulse" />
            Day 1 demo · live scrapers coming online soon
          </div>
          <h1 className="text-5xl sm:text-6xl font-semibold tracking-tight text-white leading-tight float-in">
            The <span className="gradient-text">cheapest, fastest</span> place
            <br /> to buy your medicine.
          </h1>
          <p className="mt-5 text-lg text-white/60 max-w-xl mx-auto float-in">
            We compare prices and delivery across 1mg, PharmEasy, Netmeds and Apollo —
            and tell you exactly why one wins.
          </p>

          <div className="mt-10 float-in">
            <SearchBar />
          </div>

          <div className="mt-8 float-in">
            <div className="text-xs uppercase tracking-wider text-white/40 mb-3">Popular right now</div>
            <PopularChips />
          </div>
        </div>

        <section id="how" className="mt-28 w-full max-w-5xl grid sm:grid-cols-3 gap-4">
          <FeatureCard
            color="from-[#7c5cff] to-[#a78bfa]"
            title="Compare 4 pharmacies"
            body="1mg, PharmEasy, Netmeds, and Apollo — side-by-side with discount, delivery ETA, and stock."
          />
          <FeatureCard
            color="from-[#22d3ee] to-[#06b6d4]"
            title="Plain-English reasoning"
            body="We don't just pick a winner. We tell you in one sentence why — and what you trade off."
          />
          <FeatureCard
            color="from-[#f43f5e] to-[#fb7185]"
            title="NPPA max-price baseline"
            body="Every result is checked against the Govt of India DPCO ceiling price. You'll never overpay."
          />
        </section>

        <section id="data" className="mt-16 w-full max-w-3xl text-center text-sm text-white/50">
          <p>
            Prices in this preview are illustrative. Live data pipelines (NPPA + per-pharmacy scrapers)
            arrive in the next release.
            See the <Link href="/about" className="underline hover:text-white">how-we-built-this</Link> page for the architecture.
          </p>
        </section>
      </main>

      <footer className="px-6 py-6 text-center text-xs text-white/40">
        MedAI is an independent price comparison demo. Not affiliated with any pharmacy.
        We deep-link to the source pharmacy for purchase.
      </footer>
    </div>
  );
}

function FeatureCard({
  color,
  title,
  body,
}: {
  color: string;
  title: string;
  body: string;
}) {
  return (
    <div className="glass rounded-2xl p-6 lift">
      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} mb-4 shadow-lg shadow-black/30`} />
      <div className="text-white font-medium mb-1.5">{title}</div>
      <div className="text-white/60 text-sm leading-relaxed">{body}</div>
    </div>
  );
}

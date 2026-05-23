"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { Medicine } from "@/lib/types";
import { nameScore } from "@/lib/scrapers/match";

interface Props {
  initialQuery?: string;
  size?: "lg" | "md";
}

interface DiscoverResponse {
  medicine_id: string | null;
  reused_existing: boolean;
  offer_count: number;
  error?: string;
  message?: string;
}

export default function SearchBar({ initialQuery = "", size = "lg" }: Props) {
  const router = useRouter();
  const [q, setQ] = useState(initialQuery);
  const [results, setResults] = useState<Medicine[]>([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  // v2: live-discover state
  const [discovering, setDiscovering] = useState(false);
  const [discoverError, setDiscoverError] = useState<string | null>(null);
  // True once we've actually fetched search results for the current `q`,
  // so the "no matches" CTA doesn't flash before the first fetch lands.
  const [searched, setSearched] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    if (!q.trim()) {
      setResults([]);
      setSearched(false);
      setDiscoverError(null);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
        if (!res.ok) return;
        const data: { results: Medicine[] } = await res.json();
        if (!cancelled) {
          setResults(data.results);
          setOpen(true);
          setHighlight(-1);
          setSearched(true);
        }
      } catch {
        /* swallow */
      }
    }, 120);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!wrapRef.current) return;
      if (!wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function submit(med?: Medicine) {
    const target = med ?? results[highlight] ?? results[0];
    if (target) {
      router.push(`/m/${target.id}`);
    } else if (q.trim()) {
      router.push(`/search?q=${encodeURIComponent(q.trim())}`);
    }
  }

  async function discover() {
    const query = q.trim();
    if (!query || discovering) return;
    setDiscovering(true);
    setDiscoverError(null);
    try {
      const res = await fetch(`/api/discover?q=${encodeURIComponent(query)}`, { method: "POST" });
      const data = (await res.json()) as DiscoverResponse;
      if (!res.ok || !data.medicine_id) {
        setDiscoverError(data.message ?? `No prices found for "${query}".`);
        setDiscovering(false);
        return;
      }
      router.push(`/m/${data.medicine_id}`);
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : "Network error. Try again.");
      setDiscovering(false);
    }
  }

  // Show the big "Search live" CTA when no fuzzy results came back.
  const showDiscoverCta = searched && results.length === 0 && q.trim().length >= 3 && !discovering;

  // Show a smaller "Not the right one?" footer when results EXIST but the
  // best one isn't a strong match for the query — common case: user typed
  // "Glycomet GP1" and pg_trgm returned "Glycomet 500" as the loose match.
  const topResultScore = results.length > 0 ? nameScore(q, results[0].name) : 0;
  const showWeakMatchFooter =
    !discovering && searched && results.length > 0 && q.trim().length >= 3 && topResultScore < 0.75;

  const isLg = size === "lg";
  const padding = isLg ? "px-6 py-5" : "px-4 py-3";
  const textSize = isLg ? "text-lg" : "text-base";

  return (
    <div ref={wrapRef} className="relative w-full">
      <div
        className={`glass-strong rounded-2xl flex items-center gap-3 ${padding} transition-shadow focus-within:glow`}
      >
        <svg
          className="w-5 h-5 text-white/60 flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z"
          />
        </svg>
        <input
          autoFocus={isLg}
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setHighlight((h) => Math.min(h + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setHighlight((h) => Math.max(h - 1, -1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              // If the user explicitly highlighted a row with arrow keys,
              // honour that selection.
              if (highlight >= 0 && results[highlight]) {
                submit(results[highlight]);
              } else if (showWeakMatchFooter) {
                // Top result is only a loose match for what they typed —
                // pressing Enter triggers live discovery instead of silently
                // opening the wrong medicine.
                discover();
              } else if (results.length > 0) {
                submit(results[0]);
              } else if (showDiscoverCta) {
                discover();
              }
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder="Search any medicine — Dolo 650, Glycomet GP1, Pantop DSR…"
          className={`search-input flex-1 bg-transparent outline-none ${textSize} text-white placeholder-white/40`}
          disabled={discovering}
        />
        {discovering && (
          <span className="text-xs text-white/70 flex items-center gap-2">
            <span className="w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            Searching pharmacies…
          </span>
        )}
        {!discovering && q && (
          <button
            onClick={() => {
              setQ("");
              setResults([]);
              setDiscoverError(null);
            }}
            className="text-white/40 hover:text-white/90 text-sm"
            aria-label="Clear"
          >
            ✕
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-20 left-0 right-0 mt-2 dropdown-panel rounded-2xl overflow-hidden float-in">
          {results.map((m, i) => (
            <button
              key={m.id}
              onMouseEnter={() => setHighlight(i)}
              onClick={() => submit(m)}
              className={`w-full text-left px-5 py-3 flex items-baseline justify-between gap-4 border-b border-white/5 last:border-0 transition-colors ${
                highlight === i ? "bg-white/8" : "hover:bg-white/5"
              }`}
            >
              <div className="min-w-0">
                <div className="text-white font-medium truncate">{m.name}</div>
                <div className="text-white/50 text-xs truncate">{m.composition}</div>
              </div>
              <div className="text-white/40 text-xs flex-shrink-0">{m.pack}</div>
            </button>
          ))}
          {showWeakMatchFooter && (
            <button
              onClick={discover}
              className="w-full text-left px-5 py-3 border-t border-white/10 bg-white/[0.02] hover:bg-white/5 transition-colors flex items-center justify-between gap-4"
            >
              <span className="text-white/70 text-sm">
                Not what you wanted? <span className="text-white">Search live for &ldquo;{q.trim()}&rdquo;</span>
              </span>
              <svg className="w-4 h-4 text-white/60" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7-7 7M5 12h16" />
              </svg>
            </button>
          )}
        </div>
      )}

      {showDiscoverCta && (
        <div className="absolute z-20 left-0 right-0 mt-2 dropdown-panel rounded-2xl p-4 float-in">
          <div className="text-white/70 text-sm mb-3">
            Not in our cache yet. We can search live across Netmeds, PharmEasy, and 1mg —
            takes ~3-6 seconds.
          </div>
          <button
            onClick={discover}
            className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-white text-black font-medium px-5 py-2.5 hover:bg-white/90 transition-colors"
          >
            Search live for &ldquo;{q.trim()}&rdquo;
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7-7 7M5 12h16" />
            </svg>
          </button>
          <div className="mt-3 text-xs text-white/40">
            Apollo data refreshes in the next scheduled run (every 6h).
          </div>
        </div>
      )}

      {discoverError && !discovering && (
        <div className="absolute z-20 left-0 right-0 mt-2 dropdown-panel rounded-2xl p-4 border border-[#f43f5e]/30 float-in">
          <div className="text-[#fda4af] text-sm">{discoverError}</div>
        </div>
      )}
    </div>
  );
}

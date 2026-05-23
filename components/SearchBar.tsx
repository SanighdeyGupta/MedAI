"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { Medicine } from "@/lib/types";

interface Props {
  initialQuery?: string;
  size?: "lg" | "md";
}

export default function SearchBar({ initialQuery = "", size = "lg" }: Props) {
  const router = useRouter();
  const [q, setQ] = useState(initialQuery);
  const [results, setResults] = useState<Medicine[]>([]);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    if (!q.trim()) {
      setResults([]);
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
              submit();
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder="Search a medicine, e.g. Dolo 650, Pantoprazole, Azithral…"
          className={`search-input flex-1 bg-transparent outline-none ${textSize} text-white placeholder-white/40`}
        />
        {q && (
          <button
            onClick={() => {
              setQ("");
              setResults([]);
            }}
            className="text-white/40 hover:text-white/90 text-sm"
            aria-label="Clear"
          >
            ✕
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-20 left-0 right-0 mt-2 glass-strong rounded-2xl overflow-hidden float-in">
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
        </div>
      )}
    </div>
  );
}

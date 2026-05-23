/** Relative-time formatting used in stale-data badges. */

export function formatAgo(iso: string | undefined | null): string {
  if (!iso) return "demo data";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "demo data";
  const now = Date.now();
  const seconds = Math.floor((now - then) / 1000);

  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  return new Date(then).toISOString().slice(0, 10);
}

/** Returns "stale" tier: 'fresh' (<6h), 'ok' (<24h), 'stale' (<7d), 'old' (>=7d or unknown). */
export type Freshness = "fresh" | "ok" | "stale" | "old";

export function freshnessOf(iso: string | undefined | null): Freshness {
  if (!iso) return "old";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "old";
  const hours = (Date.now() - then) / (1000 * 60 * 60);
  if (hours < 6) return "fresh";
  if (hours < 24) return "ok";
  if (hours < 24 * 7) return "stale";
  return "old";
}

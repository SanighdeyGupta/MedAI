/**
 * GET /api/admin/storage
 *
 * Returns per-table sizes from Postgres so we can monitor free-tier usage.
 * Gated by the `x-admin-token` header which must equal the
 * `ADMIN_API_TOKEN` env var. Without that header (or env var unset), the
 * route returns 404 so it doesn't even acknowledge its existence.
 *
 * Add the env var on Netlify: Site settings -> Build & deploy ->
 * Environment -> Add variable -> ADMIN_API_TOKEN (any random 32+ char string).
 */
import { NextRequest, NextResponse } from "next/server";

import { getSupabaseAdmin } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface SizeRow {
  table: string;
  size: string;
  bytes: number;
  row_count: number;
}

export async function GET(req: NextRequest) {
  const token = process.env.ADMIN_API_TOKEN;
  const provided = req.headers.get("x-admin-token");
  if (!token || provided !== token) {
    // Pretend the route doesn't exist when the token's wrong.
    return new NextResponse(null, { status: 404 });
  }

  const sb = getSupabaseAdmin();
  if (!sb) {
    return NextResponse.json(
      { error: "service role key not configured on the server" },
      { status: 503 },
    );
  }

  // Supabase exposes raw SQL via the `rpc` mechanism, but we'd need to
  // create a SECURITY DEFINER function first. Simpler: query the visible
  // tables one-by-one through the standard PostgREST interface. We use
  // count='exact' to get row counts without pulling rows.
  const tables = ["medicines", "prices", "platforms", "scrape_log"] as const;
  const results: SizeRow[] = [];
  for (const t of tables) {
    try {
      const { count, error } = await sb.from(t).select("*", { count: "exact", head: true });
      if (error) {
        results.push({ table: t, size: "n/a", bytes: -1, row_count: -1 });
      } else {
        results.push({
          table: t,
          // Without pg_size_pretty we approximate at ~250 B per row.
          size: count != null ? approxSize(count) : "n/a",
          bytes: count != null ? count * 250 : -1,
          row_count: count ?? 0,
        });
      }
    } catch (err) {
      results.push({ table: t, size: `err: ${err instanceof Error ? err.message : err}`, bytes: -1, row_count: -1 });
    }
  }

  // Last cleanup run (from cron.job_run_details if pg_cron exposes it).
  // We don't have direct access via PostgREST, so we skip and just return
  // a comment for the operator.

  return NextResponse.json({
    note: "Row counts are exact (via PostgREST count). Sizes are approximated at ~250 B/row. For true on-disk size run `pg_size_pretty(pg_total_relation_size('public.<table>'))` in the Supabase SQL Editor.",
    tables: results,
    free_tier_limit_mb: 500,
    estimated_used_mb: results.reduce((acc, r) => acc + (r.bytes > 0 ? r.bytes : 0), 0) / (1024 * 1024),
  });
}

function approxSize(rows: number): string {
  const bytes = rows * 250;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

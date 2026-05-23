"""Health check across all active pharmacy scrapers."""
import os
from collections import Counter
from dotenv import load_dotenv

load_dotenv(".env.local")

from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

print("=" * 60)
print(f"{'Platform':<12} {'#log':>6} {'#prices':>8} {'success%':>9} {'latest':>22}")
print("-" * 60)

for platform in ("Netmeds", "PharmEasy", "Apollo", "1mg"):
    log_rows = sb.table("scrape_log").select("status").eq("platform_id", platform).execute().data
    by_status = Counter(r["status"] for r in log_rows)
    price_count = sb.table("prices").select("medicine_id", count="exact").eq("platform_id", platform).execute().count
    latest = (
        sb.table("prices")
        .select("fetched_at")
        .eq("platform_id", platform)
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    success_pct = (
        f"{100 * by_status.get('success', 0) / max(1, len(log_rows)):>7.1f}%"
        if log_rows
        else "    n/a"
    )
    latest_at = latest[0]["fetched_at"][:19] if latest else "(never)"
    print(f"{platform:<12} {len(log_rows):>6} {price_count:>8} {success_pct} {latest_at:>22}")

print("=" * 60)
print("\nFailure breakdown by platform (last 100 scrapes each):")
for platform in ("Netmeds", "PharmEasy", "Apollo", "1mg"):
    bad = (
        sb.table("scrape_log")
        .select("status,error_message,medicine_id")
        .eq("platform_id", platform)
        .neq("status", "success")
        .order("fetched_at", desc=True)
        .limit(5)
        .execute()
        .data
    )
    if bad:
        print(f"\n  {platform}:")
        for b in bad:
            print(f"    {b['status']:<12} {b['medicine_id']:<28} {b.get('error_message') or ''}")

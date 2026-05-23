"""One-shot verification that Day 3 Netmeds scraper wrote correctly into Supabase."""
import os
from collections import Counter
from dotenv import load_dotenv

load_dotenv(".env.local")

from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

log = sb.table("scrape_log").select("status", count="exact").eq("platform_id", "Netmeds").execute()
print(f"scrape_log: {log.count} rows for Netmeds")
rows = sb.table("scrape_log").select("status").eq("platform_id", "Netmeds").execute().data
print("status breakdown:", dict(Counter(r["status"] for r in rows)))

prices = (
    sb.table("prices")
    .select("medicine_id,price,mrp,in_stock,fetched_at")
    .eq("platform_id", "Netmeds")
    .order("fetched_at", desc=True)
    .limit(5)
    .execute()
    .data
)
print(f"\nLatest 5 Netmeds price rows ({len(prices)} shown):")
for p in prices:
    flag = "OK" if p["in_stock"] else "OOS"
    print(f"  {p['medicine_id']:25s}  INR {float(p['price']):>7.2f}  ({flag})  fetched {p['fetched_at'][:19]}")

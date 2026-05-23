"""Find and (with --apply) delete medicines that look like garbage rows:
  - any price row with price=0 or mrp=0
  - any medicine row that has all-zero offers
  - any medicine row where every offer URL points only at the domain root
    (e.g. https://www.1mg.com/  — meaning we caught a category landing page)

Run without --apply first to see what would be deleted.
"""
import io, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv(".env.local")
from supabase import create_client

apply = "--apply" in sys.argv

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

# 1) Find price rows with zero price or zero mrp.
bad_prices = sb.table("prices").select("medicine_id,platform_id,price,mrp,url").or_("price.eq.0,mrp.eq.0").execute().data
print(f"Bad price rows (price=0 or mrp=0): {len(bad_prices)}")
for p in bad_prices[:20]:
    print(f"  {p['medicine_id']:30s}  {p['platform_id']:10s}  price={p['price']}  mrp={p['mrp']}")

# 2) Find prices whose URL is suspiciously short (homepage only, no product path).
all_prices = sb.table("prices").select("medicine_id,platform_id,url").execute().data
bad_urls = [p for p in all_prices if p["url"] and (p["url"].count("/") < 4 or p["url"].endswith(".com/") or p["url"].endswith(".in/"))]
print(f"\nPrice rows with suspicious URLs (homepage-only): {len(bad_urls)}")
for p in bad_urls[:20]:
    print(f"  {p['medicine_id']:30s}  {p['platform_id']:10s}  url={p['url']}")

# Combine bad medicines
bad_med_ids = set(p["medicine_id"] for p in bad_prices) | set(p["medicine_id"] for p in bad_urls)
print(f"\nBad medicines to clean up: {len(bad_med_ids)}")
for mid in sorted(bad_med_ids):
    print(f"  {mid}")

if not apply:
    print("\n[dry-run] Re-run with --apply to delete these rows.")
    sys.exit(0)

# 3) Delete cascading: scrape_log -> prices -> medicines.
for mid in bad_med_ids:
    sb.table("scrape_log").delete().eq("medicine_id", mid).execute()
    sb.table("prices").delete().eq("medicine_id", mid).execute()
    sb.table("medicines").delete().eq("id", mid).execute()
    print(f"  deleted {mid}")

print(f"\n✓ Cleaned up {len(bad_med_ids)} bad medicine(s).")

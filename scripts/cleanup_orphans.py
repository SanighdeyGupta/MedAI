"""Delete `medicines` rows that have zero `prices` rows AND were created via
on-demand discovery. These are orphans — the discovery insert succeeded but
the prices upsert failed (or the price rows were later removed). The
medicine page renders garbage for them (₹0.00 placeholder).

Safe to re-run; only acts on `created_via='discovered'` rows.
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(".env.local")
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
meds = sb.table("medicines").select("id,name,created_via").execute().data
prices = sb.table("prices").select("medicine_id").execute().data
have_prices = set(p["medicine_id"] for p in prices)

orphans = [m for m in meds if m["id"] not in have_prices and m.get("created_via") == "discovered"]
print(f"discovered orphans with no prices: {len(orphans)}")
for o in orphans:
    name = o["name"]
    mid = o["id"]
    print(f"  {mid:35s} :: {name}")
    sb.table("scrape_log").delete().eq("medicine_id", mid).execute()
    sb.table("medicines").delete().eq("id", mid).execute()

print(f"✓ cleaned {len(orphans)} orphan(s)")

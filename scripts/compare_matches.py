"""Show current PharmEasy URLs in DB to verify pack-aware matcher picks the right variants."""
import os
from dotenv import load_dotenv
load_dotenv(".env.local")
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

rows = (
    sb.table("prices")
    .select("medicine_id,price,mrp,url")
    .eq("platform_id", "PharmEasy")
    .order("medicine_id")
    .execute()
    .data
)
for r in rows:
    slug = r["url"].split("/")[-1]
    print(f"  {r['medicine_id']:25s}  {float(r['price']):>7.2f}  {slug}")

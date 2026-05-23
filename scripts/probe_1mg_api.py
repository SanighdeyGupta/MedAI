"""Inspect the full shape of 1mg's pharmacy_api_webservices/search endpoint."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx
import json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

c = httpx.Client(
    headers={"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.1mg.com/"},
    timeout=20.0,
)
r = c.get("https://www.1mg.com/pharmacy_api_webservices/search?name=dolo+650")
print(f"HTTP {r.status_code}, {len(r.content)//1024}KB")
d = r.json()
print("top-level keys:", list(d.keys()) if isinstance(d, dict) else type(d).__name__)
items = d.get("result") or d.get("data") or d.get("items") or []
print(f"items count: {len(items)}")
if items:
    print("\n=== first item ===")
    first = items[0]
    print(f"all keys ({len(first)}): {list(first.keys())}")
    print()
    interesting = ("name", "slug", "sku_id", "discounted_price", "cropped_price", "mrp", "pack_size",
                   "pack_size_label", "discount_percent", "in_stock", "available", "pForm", "pack_unit",
                   "manufacturer", "rx_required", "url", "composition", "form", "unit", "pack_quantity",
                   "id", "uip")
    for k in interesting:
        if k in first:
            print(f"  {k:25s} = {first[k]!r}"[:200])

    print("\n=== summary of first 5 items ===")
    for it in items[:5]:
        print(f"  - {it.get('name')!r:60s} mrp={it.get('mrp')}, disc={it.get('discounted_price')}, avail={it.get('available')}, slug/url={it.get('slug') or it.get('url')}")

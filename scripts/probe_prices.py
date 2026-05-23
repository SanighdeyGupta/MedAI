"""Dig into 1mg + Netmeds API responses for Dolo 650 — list EVERY price field.

User reported: website shows 1mg at ₹28.7 and Netmeds best-price at ₹23.71,
but our scrapers got ₹30.60 and ₹26.34. We need to find the actual fields
that hold the displayed/best-price values.
"""
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.1mg.com/"}, timeout=20.0)


def show_price_fields(label: str, item: dict) -> None:
    print(f"\n--- {label} ---")
    for k, v in item.items():
        if isinstance(v, (dict, list)):
            continue
        if any(tok in k.lower() for tok in ("price", "mrp", "discount", "cost", "rate", "amount", "off", "save", "best")):
            print(f"  {k:30s} = {v!r}")


print("===== 1mg search API =====")
r = c.get("https://www.1mg.com/pharmacy_api_webservices/search?name=Dolo+650")
items = r.json().get("result", [])
items = [it for it in items if isinstance(it, dict) and it.get("mrp") is not None]
if items:
    # full first item dump of price-related fields
    show_price_fields("first item (Dolo 650 expected)", items[0])
    # also try the explicit Tata 1mg style endpoints
    print(f"\n  full keys: {sorted(items[0].keys())}")


print("\n===== 1mg product detail JSON in HTML =====")
r2 = c.get("https://www.1mg.com/drugs/dolo-650-tablet-74467", headers={"Accept": "text/html"})
html = r2.text
# Find ALL JSON-shaped substrings that contain "mrp" so we can spot price-related blobs
import re
# Find numeric prices with INR / Rs / ₹ context
for m in re.finditer(r'"([a-zA-Z_]*price[a-zA-Z_]*)"\s*:\s*(\d+(?:\.\d+)?)', html):
    pass
seen = {}
for m in re.finditer(r'"([a-zA-Z_]*(?:price|mrp|discount|cost|save|off)[a-zA-Z_]*)"\s*:\s*(\d+(?:\.\d+)?)', html):
    key, val = m.group(1), m.group(2)
    if key not in seen:
        seen[key] = []
    if len(seen[key]) < 3:
        seen[key].append(val)
print("price-like keys in detail page HTML:")
for k, vs in sorted(seen.items()):
    print(f"  {k:30s} = {vs}")


print("\n===== Netmeds search API =====")
r3 = c.get("https://www.netmeds.com/ext/search/application/api/v1.0/products?q=dolo+650&page_size=3",
           headers={"Referer": "https://www.netmeds.com/"})
nm = r3.json().get("items", [])
if nm:
    first = nm[0]
    print(f"first item name: {first.get('name')}")
    print(f"keys: {sorted(first.keys())}")
    if "price" in first:
        print(f"\n  price dict: {json.dumps(first['price'], indent=2)}")
    if "discount" in first:
        print(f"  discount: {first['discount']!r}")
    if "_custom_json" in first:
        print(f"  _custom_json: {json.dumps(first['_custom_json'], indent=2)[:500]}")
    # find any other coupon / best-price fields
    for k, v in first.items():
        if isinstance(v, (str, int, float, bool)) and any(tok in k.lower() for tok in ("coupon", "best", "save", "deal", "offer")):
            print(f"  {k}: {v!r}")

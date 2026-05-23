"""Inspect Netmeds 'best_price' fields + extract 1mg's embedded discountedPrice."""
import io, sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "*/*"}, timeout=30.0, follow_redirects=True)

# === Netmeds: dump best_price fields ===
print("===== Netmeds best_price field analysis =====")
r = c.get("https://www.netmeds.com/ext/search/application/api/v1.0/products?q=dolo+650&page_size=3",
          headers={"Referer": "https://www.netmeds.com/", "Accept": "application/json"})
data = r.json()
items = data.get("items", [])
for it in items[:3]:
    name = it.get("name")
    eff = it["price"]["effective"]["min"]
    marked = it["price"]["marked"]["min"]
    print(f"\n  {name}")
    print(f"    price.effective.min = {eff}")
    print(f"    price.marked.min    = {marked}")
    # Walk for best_price-related keys
    def walk(o, prefix=""):
        if isinstance(o, dict):
            for k, v in o.items():
                p = f"{prefix}.{k}" if prefix else k
                if "best_price" in k.lower() or "bestprice" in k.lower() or "coupon" in k.lower():
                    if isinstance(v, (dict, list)):
                        print(f"    {p} = {json.dumps(v)[:300]}")
                    else:
                        print(f"    {p} = {v!r}")
                walk(v, p)
        elif isinstance(o, list):
            for i, v in enumerate(o[:3]):
                walk(v, f"{prefix}[{i}]")
    walk(it)


# === 1mg: extract discountedPrice from product page HTML ===
print("\n\n===== 1mg product page embedded JSON =====")
r2 = c.get("https://www.1mg.com/drugs/dolo-650-tablet-74467")
html = r2.text
# Find all discountedPrice occurrences and their context
for m in list(re.finditer(r'"discountedPrice"\s*[\\":]+\s*"?([\d.]+)"?', html))[:5]:
    print(f"  discountedPrice: {m.group(1)}  context: ...{html[max(0,m.start()-60):m.end()+30]}...")

# Try ALL forms of escaping: plain, \", \\", &quot;
patterns = [
    (r'"price"\s*:\s*([\d.]+)\s*,\s*"discountedPrice"\s*:\s*([\d.]+)', 'plain'),
    (r'\\"price\\"\s*:\s*([\d.]+)\s*,\s*\\"discountedPrice\\"\s*:\s*([\d.]+)', 'escaped'),
    (r'\\\\"price\\\\"\s*:\s*([\d.]+)\s*,\s*\\\\"discountedPrice\\\\"\s*:\s*([\d.]+)', 'doubly escaped'),
    (r'"parent_sku_price"\s*:\s*([\d.]+)\s*,\s*"parent_sku_discounted_price"\s*:\s*([\d.]+)', 'parent_sku plain'),
    (r'\\"parent_sku_price\\"\s*:\s*([\d.]+)\s*,\s*\\"parent_sku_discounted_price\\"\s*:\s*([\d.]+)', 'parent_sku escaped'),
]
for pat, label in patterns:
    matches = re.findall(pat, html)
    print(f"\n  {label}: {len(matches)} match(es)")
    for p, dp in matches[:3]:
        print(f"    price={p}, discountedPrice={dp}")

# Find ANY occurrence of discountedPrice followed by a number, however escaped
loose = re.findall(r'discountedPrice[\\\\":\s]*([\d]+\.[\d]+)', html)
print(f"\n  loose 'discountedPrice -> num' matches: {len(loose)}; uniq values: {sorted(set(loose))}")

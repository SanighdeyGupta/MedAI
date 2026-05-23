"""Find where the website-displayed ₹28.7 (1mg) and ₹23.71 (Netmeds) come from."""
import io, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20.0, follow_redirects=True)

print("===== 1mg: search for 28.7 in product page HTML =====")
r = c.get("https://www.1mg.com/drugs/dolo-650-tablet-74467")
html = r.text
print(f"  size: {len(html)//1024}KB")
print(f"  '28.7' occurrences: {html.count('28.7')}")
print(f"  '28.70' occurrences: {html.count('28.70')}")
for m in re.finditer(r'.{40}\b28\.7\b.{40}', html):
    print(f"    context: {m.group()!r}")

# Also look for "11% OFF" since that's the displayed discount
print(f"\n  '11%' occurrences: {html.count('11%')}")
for m in list(re.finditer(r'.{40}11%[^0-9].{40}', html))[:5]:
    print(f"    context: {m.group()!r}")

# Look for ANY discount higher than 5% in HTML
print("\n  large discount mentions in HTML:")
for m in re.finditer(r'"(discountPerc|discount_percent|discount)"\s*:\s*"?(\d+)', html):
    if int(m.group(2)) > 5:
        idx = m.start()
        print(f"    {html[max(0,idx-50):idx+80]!r}")

print("\n\n===== Netmeds: search for 23.71 and coupon fields =====")
r2 = c.get("https://www.netmeds.com/ext/search/application/api/v1.0/products?q=dolo+650",
           headers={"Accept": "application/json", "Referer": "https://www.netmeds.com/"})
import json
data = r2.json()
# Find any "23.71" anywhere
text = json.dumps(data)
print(f"  payload size: {len(text)//1024}KB")
print(f"  '23.71' occurrences: {text.count('23.71')}")
print(f"  '23.7'  occurrences: {text.count('23.7')}")
print(f"  'coupon' occurrences (lowercase): {text.lower().count('coupon')}")
print(f"  'best_price' / 'bestPrice' occurrences: {text.count('best_price') + text.count('bestPrice') + text.count('best price')}")
print(f"  'offer' occurrences: {text.lower().count('offer')}")

# Try the Netmeds product detail endpoint
print("\n===== Netmeds: product detail page =====")
r3 = c.get("https://www.netmeds.com/product/dolo-650-tablet-15s-lui1wb-8231049")
print(f"  size: {len(r3.text)//1024}KB")
print(f"  '23.71' occurrences in product page: {r3.text.count('23.71')}")
print(f"  '23.7' occurrences: {r3.text.count('23.7')}")
# What's the price-bearing JSON shape on Netmeds product page?
ld = re.findall(r'<script type="application/ld\+json"[^>]*>(.+?)</script>', r3.text, re.DOTALL)
print(f"  ld+json blocks: {len(ld)}")
for i, block in enumerate(ld):
    try:
        d = json.loads(block)
        if isinstance(d, dict) and d.get("@type") in ("Product", "Drug"):
            print(f"    [{i}] {d.get('@type')} offers: {d.get('offers')}")
    except Exception as e:
        print(f"    [{i}] parse err: {e}")

"""Get the full dataLayer blob from a 1mg product page and inspect it."""
import io, sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20.0, follow_redirects=True)

URLS = [
    ("Dolo 650", "https://www.1mg.com/drugs/dolo-650-tablet-74467"),
    ("Pan 40",   "https://www.1mg.com/drugs/pan-40-tablet-66170"),
    ("Crocin Advance 500", "https://www.1mg.com/drugs/crocin-advance-500mg-tablet-188562"),
]

for label, url in URLS:
    print(f"\n========== {label} ==========")
    r = c.get(url)
    html = r.text
    print(f"HTTP {r.status_code}, {len(html)//1024}KB, final URL: {r.url}")

    # The dataLayer blob is in the script tag whose body starts with `var dataLayer =`
    m = re.search(r'var\s+dataLayer\s*=\s*(\[.+?\])\s*;', html, re.DOTALL)
    if not m:
        print("dataLayer NOT found")
        continue
    blob = m.group(1)
    print(f"dataLayer blob: {len(blob)//1024}KB")
    try:
        data = json.loads(re.sub(r":\s*undefined", ":null", blob))
    except Exception as e:
        print(f"parse err: {e}")
        continue
    # dataLayer is a list; first element is the page push
    if not data:
        continue
    obj = data[0]
    keys = list(obj.keys())
    print(f"item keys ({len(keys)}): {keys[:60]}")
    # Inspect price-related keys
    for k in ("mrp", "discounted_price", "cropped_price", "discount", "price", "selling_price",
              "id", "skuType", "name", "drug_name", "SKU_availability_status",
              "in_stock", "available", "pack_size_label", "sku_quantity"):
        if k in obj:
            v = obj[k]
            if isinstance(v, (dict, list)):
                continue
            print(f"  {k:30s} = {v!r}")

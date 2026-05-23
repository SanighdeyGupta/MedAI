"""Probe Apollo product page ld+json structure."""
import json
import re
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
client = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20.0, follow_redirects=True)

urls = [
    "https://www.apollopharmacy.in/otc/dolo-650-tablet-15s",
    "https://www.apollopharmacy.in/medicine/dolo-650-tablet-15s",
    "https://www.apollopharmacy.in/medicine/dolo-650-tablet",  # wrong slug intentionally
    "https://www.apollopharmacy.in/medicine/pan-40-tablet",
    "https://www.apollopharmacy.in/medicine/azithral-500-tablet-3s",
]

for url in urls:
    print("\n=====", url)
    r = client.get(url)
    print(f"  HTTP {r.status_code}, {len(r.text)//1024}KB")
    matches = re.findall(r'<script type="application/ld\+json"[^>]*>(.+?)</script>', r.text, re.DOTALL)
    print(f"  ld+json blocks: {len(matches)}")
    for i, m in enumerate(matches):
        try:
            data = json.loads(m)
        except Exception as e:
            print(f"  [{i}] parse err: {e}")
            continue
        # Look for product schema
        if isinstance(data, dict) and data.get("@type") == "Product":
            print(f"  [{i}] Product schema:")
            for k in ["name", "sku", "url", "image", "offers", "brand", "description"]:
                v = data.get(k)
                if v is not None:
                    val_str = repr(v)[:200]
                    print(f"      {k}: {val_str}")
        else:
            t = data.get("@type") if isinstance(data, dict) else type(data).__name__
            print(f"  [{i}] @type={t}")

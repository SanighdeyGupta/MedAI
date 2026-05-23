"""One-shot HTML probe: pretty-print product fields from PharmEasy + Apollo __NEXT_DATA__."""
import json
import re
import sys
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
client = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20.0, follow_redirects=True)


def get_next_data(url: str) -> dict | None:
    r = client.get(url)
    print(f"  {r.status_code} {len(r.text)//1024}KB  {url}")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', r.text, re.DOTALL)
    if not m:
        return None
    return json.loads(m.group(1))


def walk_keys(obj, prefix="", max_depth=4, depth=0, hits=None, look_for=None):
    if hits is None:
        hits = []
    if depth > max_depth:
        return hits
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if look_for and any(kw in k.lower() for kw in look_for) and not isinstance(v, (dict, list)):
                hits.append((path, v))
            walk_keys(v, path, max_depth, depth + 1, hits, look_for)
    elif isinstance(obj, list) and obj and depth <= max_depth - 1:
        walk_keys(obj[0], f"{prefix}[0]", max_depth, depth + 1, hits, look_for)
    return hits


def probe(label, url, look_for):
    print(f"\n===== {label} =====")
    data = get_next_data(url)
    if data is None:
        print("  __NEXT_DATA__ not found")
        return
    hits = walk_keys(data, look_for=look_for, max_depth=8)
    # Dedup by leaf key; show first 30
    seen = set()
    for path, val in hits[:50]:
        leaf = path.split(".")[-1]
        if leaf in seen:
            continue
        seen.add(leaf)
        val_str = repr(val)[:120]
        print(f"  {path:80s}  =  {val_str}")


probe(
    "PharmEasy search 'dolo 650'",
    "https://pharmeasy.in/search/all?name=dolo%20650",
    look_for=["saleprice", "mrp", "price", "stock", "available", "deliv", "name", "slug"],
)

probe(
    "PharmEasy direct product page",
    "https://pharmeasy.in/online-medicine-order/dolo-650mg-strip-of-15-tablets-44140",
    look_for=["saleprice", "mrp", "price", "stock", "available", "deliv", "name", "slug"],
)

probe(
    "Apollo search 'dolo 650'",
    "https://www.apollopharmacy.in/search-medicines/dolo%20650",
    look_for=["price", "mrp", "stock", "available", "name", "url", "slug", "deliv"],
)

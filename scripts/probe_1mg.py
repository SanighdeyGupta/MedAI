"""Extract 1mg search page __INITIAL_STATE__ and find product data."""
import io, sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en-IN,en;q=0.9"}, timeout=20.0, follow_redirects=True)

print("===== 1mg search page =====")
r = c.get("https://www.1mg.com/search/all?name=dolo+650")
print(f"HTTP {r.status_code}, {len(r.text)//1024}KB")

# Find __INITIAL_STATE__
m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(.+?})\s*;\s*\n', r.text)
if not m:
    m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*;?\s*window', r.text, re.DOTALL)
if not m:
    print("__INITIAL_STATE__ NOT found via either pattern")
else:
    blob = m.group(1).strip()
    print(f"__INITIAL_STATE__ blob: {len(blob)//1024}KB")
    # Decode escaped HTML and pure-JSON-encoded blob
    try:
        data = json.loads(blob)
    except Exception as e:
        print(f"first-shot parse err: {e}")
        # Try undefined → null
        cleaned = re.sub(r":\s*undefined", ":null", blob)
        try:
            data = json.loads(cleaned)
        except Exception as e2:
            print(f"second-shot parse err: {e2}")
            print(f"first 500 chars of blob:")
            print(blob[:500])
            sys.exit(1)
    print(f"top-level keys: {list(data.keys())[:30]}")
    # Recursively look for product-like arrays
    def find_paths(obj, prefix="", depth=0):
        if depth > 6:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{prefix}.{k}" if prefix else k
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    first_keys = list(v[0].keys())
                    if any(k.lower() in ("name", "slug", "discounted_price", "cropped_price", "mrp", "sku") for k in first_keys):
                        print(f"  list at {p}: {len(v)} items, first keys = {first_keys[:15]}")
                find_paths(v, p, depth + 1)
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            find_paths(obj[0], prefix + "[0]", depth + 1)

    find_paths(data)

    # If found a search results path, dump first item
    print("\n===== sample item dump =====")
    def dump_first(obj, want_keys=("name", "slug", "discounted_price", "cropped_price", "mrp")):
        if isinstance(obj, dict):
            for k, v in obj.items():
                dump_first(v, want_keys)
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            it = obj[0]
            if any(k in it for k in want_keys):
                print(f"  found candidate: keys = {list(it.keys())[:25]}")
                for k in ("name", "slug", "discounted_price", "cropped_price", "mrp", "sku", "url", "in_stock"):
                    if k in it:
                        print(f"    {k}: {repr(it[k])[:120]}")
                print()
    dump_first(data)

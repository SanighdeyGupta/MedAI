"""Examine 1mg product detail page for embedded price + search API."""
import io, sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20.0, follow_redirects=True)

print("===== product detail page (Dolo 650) =====")
r = c.get("https://www.1mg.com/drugs/dolo-650-tablet-74467")
html = r.text
print(f"HTTP {r.status_code}, {len(html)//1024}KB")

# ld+json blocks
ldj = re.findall(r'<script type="application/ld\+json"[^>]*>(.+?)</script>', html, re.DOTALL)
print(f"ld+json blocks: {len(ldj)}")
for i, block in enumerate(ldj):
    try:
        d = json.loads(block)
        t = d.get("@type") if isinstance(d, dict) else "list"
        print(f"  [{i}] @type={t}")
        if t == "Product":
            print(f"      name: {d.get('name')!r}")
            print(f"      sku:  {d.get('sku')!r}")
            print(f"      offers: {d.get('offers')!r}")
            print(f"      url: {d.get('url')!r}")
    except Exception as e:
        print(f"  [{i}] err: {e}")

print()
# Check __INITIAL_STATE__ for richer product data
m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*;\s*window', html, re.DOTALL)
if m:
    blob = m.group(1)
    print(f"__INITIAL_STATE__ size: {len(blob)//1024}KB")
    try:
        data = json.loads(re.sub(r":\s*undefined", ":null", blob))
        print(f"top keys: {list(data.keys())[:30]}")
        # Look for product-detail-like data
        def find_keys(obj, want, depth=0, prefix=""):
            if depth > 8 or not isinstance(obj, (dict, list)):
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    p = f"{prefix}.{k}" if prefix else k
                    if k in want and not isinstance(v, (dict, list)):
                        print(f"   {p} = {v!r}")
                    find_keys(v, want, depth+1, p)
            else:
                for i, v in enumerate(obj[:3]):
                    find_keys(v, want, depth+1, f"{prefix}[{i}]")
        find_keys(data, {"name","slug","discounted_price","cropped_price","mrp","in_stock","sku_quantity","url","sku_id"})
    except Exception as e:
        print(f"parse err: {e}")

print()
print("===== look for search API endpoints in main JS bundles =====")
script_srcs = re.findall(r'<script src="([^"]+)"', html)
print(f"script tags: {len(script_srcs)}")
js_urls = [s for s in script_srcs if '.js' in s and '/static/' in s][:6]
for js in js_urls:
    url = js if js.startswith("http") else f"https://www.1mg.com{js}"
    try:
        jr = c.get(url)
    except Exception as e:
        print(f"  fetch err {url}: {e}")
        continue
    matches = re.findall(r'/api/[a-zA-Z0-9/_\-]+(?=[\'"`])', jr.text)
    if matches:
        unique = sorted(set(matches))[:15]
        print(f"  {url[-60:]:60s}  api paths: {len(unique)}")
        for u in unique[:8]:
            print(f"    {u}")

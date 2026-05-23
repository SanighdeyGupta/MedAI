"""Test if a real session (homepage visit first, cookies retained) yields
a different price from the 1mg search API."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

print("===== bare API call =====")
c1 = httpx.Client(headers={"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.1mg.com/"}, timeout=20.0)
r = c1.get("https://www.1mg.com/pharmacy_api_webservices/search?name=dolo+650")
items = r.json().get("result", [])
items = [it for it in items if isinstance(it, dict) and it.get("mrp") is not None]
if items:
    print(f"  bare result: mrp={items[0]['mrp']}, discounted_price={items[0].get('discounted_price')}, oPrice={items[0].get('oPrice')}")

print("\n===== with homepage visit (cookies set) =====")
c2 = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html,application/json", "Referer": "https://www.1mg.com/"}, timeout=20.0, follow_redirects=True)
c2.get("https://www.1mg.com/")  # populate cookies
print(f"  cookies after home: {dict(c2.cookies)}")
r2 = c2.get("https://www.1mg.com/pharmacy_api_webservices/search?name=dolo+650", headers={"Accept": "application/json"})
items2 = r2.json().get("result", [])
items2 = [it for it in items2 if isinstance(it, dict) and it.get("mrp") is not None]
if items2:
    print(f"  with-session result: mrp={items2[0]['mrp']}, discounted_price={items2[0].get('discounted_price')}, oPrice={items2[0].get('oPrice')}")

print("\n===== with explicit city/pincode cookies =====")
c3 = httpx.Client(headers={"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.1mg.com/"}, timeout=20.0)
# Try common 1mg city cookies — Delhi, Mumbai, etc.
for pincode, city in [("110001", "Delhi"), ("400001", "Mumbai"), ("122001", "Gurgaon"), ("560001", "Bangalore")]:
    c3.cookies.clear()
    c3.cookies.set("city", city, domain=".1mg.com")
    c3.cookies.set("__pincode", pincode, domain=".1mg.com")
    c3.cookies.set("pincode", pincode, domain=".1mg.com")
    r3 = c3.get("https://www.1mg.com/pharmacy_api_webservices/search?name=dolo+650")
    items3 = r3.json().get("result", [])
    items3 = [it for it in items3 if isinstance(it, dict) and it.get("mrp") is not None]
    if items3:
        print(f"  city={city:10s} pincode={pincode}: discounted_price={items3[0].get('discounted_price')}")

print("\n===== try /pharmacy_api_webservices/v1/details endpoint =====")
sku_id = 74467
for url in [
    f"https://www.1mg.com/pharmacy_api_webservices/v1/drugs/{sku_id}",
    f"https://www.1mg.com/pharmacy_api_webservices/drugs/{sku_id}",
    f"https://www.1mg.com/pharmacy_api_webservices/marketplace/v3/products/{sku_id}",
    f"https://www.1mg.com/pharmacy_api_webservices/dynamic-pricing/v3/skus/{sku_id}",
    f"https://www.1mg.com/pharmacy_api_webservices/v1/items?sku_id={sku_id}",
]:
    try:
        rr = c1.get(url)
        ct = rr.headers.get("content-type", "")
        if "json" in ct and rr.status_code == 200:
            print(f"  {rr.status_code} {url}")
            print(f"    head: {rr.text[:300]}")
        else:
            print(f"  {rr.status_code} {url}  (not json)")
    except Exception as e:
        print(f"  err: {url}: {e}")

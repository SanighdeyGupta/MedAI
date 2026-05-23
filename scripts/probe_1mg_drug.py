"""Inspect the richer 1mg drug-detail endpoint for the website-displayed price."""
import io, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.1mg.com/"}, timeout=30.0)

r = c.get("https://www.1mg.com/pharmacy_api_webservices/drugs/74467")
print(f"HTTP {r.status_code}, {len(r.content)//1024}KB")
data = r.json()
result = data.get("result", {})
print(f"top-level keys ({len(result)}): {sorted(result.keys())[:40]}")
print()

# Walk for all price-like fields
def walk(obj, depth=0, prefix=""):
    if depth > 6: return
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            kl = k.lower()
            if not isinstance(v, (dict, list)) and v is not None:
                if any(tok in kl for tok in ("price", "mrp", "discount", "off", "save", "cost", "best", "deal", "rate", "amount")):
                    print(f"  {p:55s} = {v!r}")
            walk(v, depth+1, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:3]):
            walk(v, depth+1, f"{prefix}[{i}]")

walk(result)

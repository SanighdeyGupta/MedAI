"""Trace the Volini Gel match on 1mg."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx
from scrapers.match_helpers import name_score, extract_pack_hint

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.1mg.com/"}, timeout=20.0)

r = c.get("https://www.1mg.com/pharmacy_api_webservices/search?name=Volini+Gel")
items = [it for it in r.json().get("result", []) if isinstance(it, dict) and it.get("mrp") is not None]
print(f"items: {len(items)}")
target_pack = "Tube of 30g"
target_hint = extract_pack_hint(target_pack)
print(f"target pack hint: {target_hint}")
for it in items:
    name = it.get("name") or ""
    pack_label = it.get("packSizeLabel") or ""
    uip = it.get("uip")
    pForm = it.get("pForm") or ""
    score = name_score("Volini Gel", name)
    hint = extract_pack_hint(name, pack_label, f"{uip} {pForm}")
    print(f"  {score:.2f}  {name!r}  pack={pack_label!r}/uip={uip}/pForm={pForm!r}  hint={hint}  mrp={it.get('mrp')}, disc={it.get('discounted_price')}")

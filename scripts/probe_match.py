"""Spot-test the new pack-aware matcher on tricky medicines."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dotenv import load_dotenv
load_dotenv(".env.local")

from scrapers.pharmeasy import PharmEasyScraper

tests = [
    {"id": "volini-gel", "name": "Volini Gel", "pack": "Tube of 30g", "composition": "Diclofenac diethylamine 1.16% w/w"},
    {"id": "dolo-650", "name": "Dolo 650", "pack": "Strip of 15 tablets", "composition": "Paracetamol 650mg"},
    {"id": "cetirizine-10", "name": "Cetirizine 10", "pack": "Strip of 10 tablets", "composition": "Cetirizine 10mg"},
    {"id": "electral", "name": "Electral Powder", "pack": "Sachet of 21.8g", "composition": "Oral Rehydration Salts"},
]

s = PharmEasyScraper()
for m in tests:
    r = s.scrape(m)
    if r.offer:
        print(f"  {m['name']:25s} -> INR {r.offer.price:>7.2f} (MRP {r.offer.mrp:>7.2f})  {r.offer.url}")
    else:
        print(f"  {m['name']:25s} -> {r.status} {r.error_message}")
s.close()

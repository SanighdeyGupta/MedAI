"""Locate the JSON blob containing the actual mrp/price on 1mg product pages."""
import io, sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
c = httpx.Client(headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20.0, follow_redirects=True)

r = c.get("https://www.1mg.com/drugs/dolo-650-tablet-74467")
html = r.text

# Find position of "mrp":32.13 substring
idx = html.find('"mrp":32.13')
print(f"'mrp' field position: {idx}")
print(f"context ±400 chars:")
print(repr(html[max(0, idx-400):idx+500]))
print()

# Check all <script> contents for the mrp value
scripts = re.findall(r'<script[^>]*>([^<]+)</script>', html, re.DOTALL)
print(f"\nscripts with content: {len(scripts)}")
for i, s in enumerate(scripts):
    if '"mrp":' in s:
        print(f"  [{i}] contains 'mrp', size = {len(s)//1024}KB")
        # Find the prefix to see what kind of blob it is
        first_part = s[:200]
        print(f"      first 200: {first_part!r}")

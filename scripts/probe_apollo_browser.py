"""Render Apollo's search page in Patchright and inspect what we can extract."""
import io
import re
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from patchright.sync_api import sync_playwright

QUERY = sys.argv[1] if len(sys.argv) > 1 else "dolo 650"
URL = f"https://www.apollopharmacy.in/search-medicines/{QUERY.replace(' ', '%20')}"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="chrome")
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        locale="en-IN",
        viewport={"width": 1366, "height": 900},
    )
    page = ctx.new_page()
    print(f"[goto] {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    print(f"[loaded] DOM ready")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception as e:
        print(f"[notice] networkidle timeout: {e}")
    page.wait_for_timeout(2500)  # give React a moment to hydrate

    html = page.content()
    print(f"[content] {len(html)//1024}KB rendered HTML")

    # Look for rupee / price patterns in rendered DOM
    inr_matches = re.findall(r"₹\s*[\d,]+(?:\.\d+)?", html)
    print(f"[inr] {len(inr_matches)} '₹' matches; first 10: {inr_matches[:10]}")

    # Look for product-card anchors
    prod_links = re.findall(r'href="(/(?:otc|medicine)/[^"]+)"', html)
    print(f"[product links] {len(prod_links)} unique anchors; first 5: {list(dict.fromkeys(prod_links))[:5]}")

    # Try common selectors
    selectors = [
        ('div[class*="ProductCard"]', "product cards"),
        ('div[class*="product-card"]', "product cards alt"),
        ('a[href^="/otc/"]', "OTC links"),
        ('a[href^="/medicine/"]', "Rx links"),
        ('[class*="price"]', "price class"),
        ('[class*="Price"]', "Price class"),
        ('[data-testid*="price"]', "price test id"),
    ]
    for sel, label in selectors:
        try:
            n = len(page.query_selector_all(sel))
            print(f"  {label:25s} ({sel:35s})  count={n}")
        except Exception as e:
            print(f"  {label:25s}  err={e}")

    # Dump first product card structure
    cards = page.query_selector_all('a[href^="/otc/"], a[href^="/medicine/"]')
    if cards:
        print(f"\n[first card HTML, truncated]")
        print(cards[0].inner_html()[:1200])

    browser.close()

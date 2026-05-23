"""Dig into a single Apollo product card to find price + MRP structure."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import re
from patchright.sync_api import sync_playwright

URL = "https://www.apollopharmacy.in/search-medicines/dolo%20650"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="chrome")
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        locale="en-IN",
        viewport={"width": 1366, "height": 900},
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(2000)

    cards = page.query_selector_all('div[class*="ProductCard"]')
    print(f"cards: {len(cards)}")

    for i, card in enumerate(cards[:3]):
        print(f"\n========== CARD #{i} ==========")
        # Extract anchor
        anchor = card.query_selector("a[href]")
        print(f"  href:  {anchor.get_attribute('href') if anchor else 'NONE'}")
        # Extract image alt
        img = card.query_selector("img[alt]")
        print(f"  alt:   {img.get_attribute('alt') if img else 'NONE'}")
        # Inner text full
        text = card.inner_text()
        print(f"  text:  {repr(text[:300])}")
        # Find rupee-prefixed amounts
        prices = re.findall(r"₹\s*[\d,]+(?:\.\d+)?", text)
        print(f"  rupee values in text: {prices}")
        # Look for "MRP" label
        mrp_search = re.findall(r"MRP[^₹]*₹\s*[\d,]+(?:\.\d+)?", text, re.IGNORECASE)
        print(f"  MRP-labeled: {mrp_search}")
        # Out of stock / stock indicator
        oos = ("Out of Stock" in text) or ("out of stock" in text.lower())
        print(f"  out_of_stock: {oos}")

    browser.close()

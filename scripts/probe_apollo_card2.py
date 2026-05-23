"""Find the smallest-bounding card element around each Apollo product anchor."""
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

    # For each product anchor, find its closest ancestor that ALSO contains a rupee symbol.
    anchors = page.query_selector_all('a[href^="/otc/"], a[href^="/medicine/"]')
    print(f"product anchors: {len(anchors)}")

    for i, a in enumerate(anchors[:5]):
        href = a.get_attribute("href")
        # Walk up until we find a parent whose innerText contains ₹ and is reasonably small
        info = a.evaluate(
            """
            (el) => {
              let cur = el;
              for (let i=0; i<8; i++) {
                cur = cur.parentElement;
                if (!cur) break;
                const t = cur.innerText || '';
                if (t.includes('₹') && t.length < 600) {
                  return { tag: cur.tagName, cls: cur.className.slice(0,40), text: t };
                }
              }
              return null;
            }
            """
        )
        print(f"\n[{i}] href={href}")
        if info:
            print(f"    tag={info['tag']}, class={info['cls']}")
            print(f"    text={info['text'][:400]}")
            prices = re.findall(r"₹\s*[\d,]+(?:\.\d+)?", info["text"])
            print(f"    prices in this slice: {prices}")
            # MRP detection
            mrp_match = re.search(r"MRP\s*₹\s*([\d,]+(?:\.\d+)?)", info["text"], re.IGNORECASE)
            print(f"    MRP: {mrp_match.group(1) if mrp_match else 'NONE'}")
        else:
            print("    no bounded ancestor found")

    browser.close()

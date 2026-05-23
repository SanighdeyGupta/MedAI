"""Apollo Pharmacy scraper.

Apollo's web app is fully client-rendered React (Next.js App Router), and
its GraphQL backend (api.apollo247.com) requires a bearer token that
isn't statically discoverable in their public JS bundles. We use a
headless browser (Patchright — anti-detection-patched Playwright) to
render the search results page and read the prices from the DOM.

Endpoint: https://www.apollopharmacy.in/search-medicines/<query>

DOM contract (discovered via DevTools probe; class names are obfuscated):
  - Each product card is a <div class="p"> (a single-letter obfuscated class).
  - Anchor:   <a href="/otc/<slug>" or "/medicine/<slug>">  → product URL
  - Image alt: <img alt="<product name>">                   → product name
  - Inner text always contains exactly ONE "₹N[.NN]" — the effective price.
  - When a discount applies, an "MRP ₹N[.NN]" line is also present.
  - Sponsored / generic alternates are prefixed with "Ad" or "Generic Alternate".

ToS posture (see ../LEGAL.md):
  Apollo's robots.txt is permissive (Allow: /). We rate-limit politely
  to <= 1 nav/sec, use a real Chrome User-Agent + viewport, do NOT bypass
  any WAF (Apollo doesn't have one), and deep-link every result to
  apollopharmacy.in for the user click.
"""
from __future__ import annotations

import re
import time

from .base import Offer, PharmacyScraper, ScrapeResult, ms_since
from .match_helpers import pick_best

SEARCH_URL_TEMPLATE = "https://www.apollopharmacy.in/search-medicines/{q}"
PAGE_LOAD_MS = 30_000
HYDRATE_WAIT_MS = 2_500
MATCH_THRESHOLD = 0.55


class ApolloScraper(PharmacyScraper):
    domain = "www.apollopharmacy.in"
    platform_id = "Apollo"
    default_delivery_days = 1
    default_return_days = 7

    def __init__(self, rate_limit_s: float = 1.0):
        super().__init__(rate_limit_s)
        # Lazy-init: only spin up Chromium when the first scrape() is called.
        # Saves cold-start time if list_medicines returns 0 rows.
        self._pw = None
        self._browser = None
        self._page = None

    # -- lifecycle ----------------------------------------------------------

    def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        # Imported lazily so Netmeds/PharmEasy users don't pay the patchright
        # import + chromium boot cost.
        from patchright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            channel="chrome",
        )
        ctx = self._browser.new_context(
            user_agent=self.ua,
            locale="en-IN",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
        )
        # Block heavy resources (images, fonts, third-party telemetry) to
        # keep each page load under a few seconds.
        def _route_block(route):  # noqa: ANN001
            req = route.request
            if req.resource_type in {"image", "media", "font"}:
                return route.abort()
            return route.continue_()

        ctx.route("**/*", _route_block)
        self._page = ctx.new_page()
        # Disable webdriver detection breadcrumbs (Patchright already patches
        # most, but this is a belt-and-braces add).
        self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        super().close()

    # -- scrape ------------------------------------------------------------

    def _fetch_cards(self, medicine_name: str) -> tuple[list[dict], int | None, str | None]:
        """Return (cards, http_status_or_None, error_or_None)."""
        self._ensure_browser()
        assert self._page is not None

        url = SEARCH_URL_TEMPLATE.format(q=medicine_name.replace(" ", "%20"))
        if not self.can_fetch(url):
            return [], None, f"robots.txt disallows {url}"

        self.rate_limiter.wait()
        try:
            resp = self._page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_MS)
        except Exception as e:
            return [], None, f"goto error: {e}"

        status = resp.status if resp else None
        if status and status >= 400:
            return [], status, f"HTTP {status}"

        # Let React hydrate + initial GraphQL fetch settle.
        try:
            self._page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass  # networkidle can flake on Apollo; we add a fixed wait below
        self._page.wait_for_timeout(HYDRATE_WAIT_MS)

        # Extract card info from each product anchor.
        cards: list[dict] = self._page.evaluate(
            r"""
            () => {
              const anchors = Array.from(document.querySelectorAll(
                'a[href^="/otc/"], a[href^="/medicine/"]'
              ));
              return anchors.map(a => {
                // Find the smallest ancestor whose innerText contains ₹.
                let cur = a;
                let card = null;
                for (let i = 0; i < 8; i++) {
                  cur = cur.parentElement;
                  if (!cur) break;
                  const t = cur.innerText || '';
                  if (t.includes('₹') && t.length < 600) {
                    card = cur;
                    break;
                  }
                }
                if (!card) return null;
                const text = card.innerText || '';
                const img = a.querySelector('img[alt]');
                const name = (img && img.getAttribute('alt')) || (card.querySelector('h3') ? card.querySelector('h3').innerText : '');
                return {
                  href: a.getAttribute('href'),
                  name: name,
                  text: text,
                  isAd: text.startsWith('Ad\n') || text.startsWith('Sponsored'),
                  isGeneric: text.includes('Generic Alternate'),
                };
              }).filter(x => x);
            }
            """
        )
        return cards, status, None

    def scrape(self, medicine: dict) -> ScrapeResult:
        start = time.monotonic()
        try:
            cards, status, err = self._fetch_cards(medicine["name"])
        except Exception as e:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message=f"{type(e).__name__}: {e}",
                http_status=None,
                duration_ms=ms_since(start),
                via="patchright",
            )

        if err:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error" if "robots" not in err else "blocked",
                offer=None,
                error_message=err,
                http_status=status,
                duration_ms=ms_since(start),
                via="patchright",
            )

        if not cards:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="not_found",
                offer=None,
                error_message="no product anchors in DOM",
                http_status=status,
                duration_ms=ms_since(start),
                via="patchright",
            )

        # Prefer non-sponsored, non-generic-alternate cards
        eligible = [c for c in cards if not c["isAd"] and not c["isGeneric"]]
        pool = eligible if eligible else cards

        best, score = pick_best(
            pool,
            target_name=medicine["name"],
            target_pack=medicine.get("pack"),
            name_of=lambda c: c.get("name") or "",
            # Apollo's card text contains the pack hint ("15 Tablet", "30g").
            pack_text_of=lambda c: c.get("text") or "",
            threshold=MATCH_THRESHOLD,
        )
        if best is None:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="not_found",
                offer=None,
                error_message=f"no match >={MATCH_THRESHOLD} (top={score:.2f}, cards={len(cards)})",
                http_status=status,
                duration_ms=ms_since(start),
                via="patchright",
            )

        # Parse price + MRP from the card's text.
        # Effective price is the FIRST '₹X[.YY]' in the card text.
        # If 'MRP ₹X[.YY]' is present, that's MRP; otherwise MRP == price.
        text: str = best["text"]
        first_inr = re.search(r"₹\s*([\d,]+(?:\.\d+)?)", text)
        if not first_inr:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message="no rupee value in matched card",
                http_status=status,
                duration_ms=ms_since(start),
                via="patchright",
            )
        price = float(first_inr.group(1).replace(",", ""))
        mrp_match = re.search(r"MRP\s*₹\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
        mrp = float(mrp_match.group(1).replace(",", "")) if mrp_match else price

        # Apollo hides out-of-stock items from search by default. If "Notify
        # Me" or "Out of Stock" appears, mark accordingly.
        in_stock = ("Notify Me" not in text) and ("Out of Stock" not in text)

        href = best["href"] or "/"
        offer = Offer(
            pharmacy=self.platform_id,
            medicine_id=medicine["id"],
            price=price,
            mrp=mrp,
            delivery_days=self.default_delivery_days,
            in_stock=in_stock,
            return_days=self.default_return_days,
            url=f"https://{self.domain}{href}",
        )
        return ScrapeResult(
            medicine_id=medicine["id"],
            status="success",
            offer=offer,
            error_message=None,
            http_status=status,
            duration_ms=ms_since(start),
            via="patchright",
        )

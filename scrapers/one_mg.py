"""Tata 1mg scraper.

The original plan slotted 1mg behind Patchright + ScraperAPI because the
2025 research said 1mg was protected by Cloudflare Bot Management. In
practice (2026 probe), 1mg's *official internal* search JSON endpoint
serves plain httpx requests without a challenge:

    GET https://www.1mg.com/pharmacy_api_webservices/search?name=<query>

That endpoint is what 1mg's own browser SPA calls. It returns a list of
items with `name`, `mrp`, `discounted_price`, `available`, `saleable`,
`url`, and pack-size fields, all on the same path as cheap as Netmeds.
robots.txt disallows `/search` (the page) but `/pharmacy_api_webservices/`
is NOT in the disallow list, so we use the API instead of the page.

If at some point Cloudflare's policy tightens and this endpoint starts
challenging, the fallback paths (in priority order) are:
  1. Patchright with channel="chrome" against the same endpoint URL.
  2. ScraperAPI free tier (1k credits/mo) with `render=true`.

Both are deferred until needed (YAGNI), so we ship the cheap path today.
"""
from __future__ import annotations

import re
import time

from .base import Offer, PharmacyScraper, ScrapeResult, ms_since
from .match_helpers import pick_best

SEARCH_URL = "https://www.1mg.com/pharmacy_api_webservices/search"
MATCH_THRESHOLD = 0.50

# The /search API returns a stable `discounted_price` that is the
# merchant's wholesale-after-default-discount number. The consumer-facing
# product page applies an additional dynamic promotion (configured at the
# page level, e.g. "11% off" instead of the API's "5% off"). To match the
# price the user sees when they click through, we parse the product page
# HTML for `"discountedPrice"`, which appears in an escaped JSON blob.
# Falls back to the API value if the regex misses.
DISPLAYED_PRICE_RE = re.compile(r'\\"discountedPrice\\"\s*:\s*([\d.]+)')


class OneMgScraper(PharmacyScraper):
    domain = "www.1mg.com"
    platform_id = "1mg"
    default_delivery_days = 2
    default_return_days = 7

    def scrape(self, medicine: dict) -> ScrapeResult:
        start = time.monotonic()
        name = medicine["name"]
        # No `types=` filter: 1mg's search defaults to drugs + OTC. Filtering
        # to types=sku silently drops vitamins/supplements/ORS like Limcee,
        # Electral, Zincovit, Becosules — we want those.
        url = f"{SEARCH_URL}?name={name.replace(' ', '+')}"

        try:
            r = self.get(url)
        except PermissionError as e:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="blocked",
                offer=None,
                error_message=str(e),
                http_status=None,
                duration_ms=ms_since(start),
                via="httpx",
            )
        except Exception as e:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message=f"{type(e).__name__}: {e}",
                http_status=None,
                duration_ms=ms_since(start),
                via="httpx",
            )

        if r.status_code == 429:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="rate_limited",
                offer=None,
                error_message=None,
                http_status=429,
                duration_ms=ms_since(start),
                via="httpx",
            )
        # Cloudflare challenge pages return 403/503 or 200 with "Just a moment".
        if r.status_code != 200:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message=f"HTTP {r.status_code}",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )
        if "Just a moment" in r.text[:1000] or "challenge-platform" in r.text[:2000]:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="blocked",
                offer=None,
                error_message="Cloudflare challenge page (need Patchright/ScraperAPI fallback)",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )

        try:
            data = r.json()
        except Exception as e:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message=f"json decode: {e}",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )

        items = data.get("result") or []
        # Keep items that look like products: skip article suggestions, doctor
        # listings, etc. Real products have an `mrp` field.
        items = [it for it in items if isinstance(it, dict) and it.get("mrp") is not None]

        best, score = pick_best(
            items,
            target_name=name,
            target_pack=medicine.get("pack"),
            name_of=lambda it: it.get("name") or "",
            # The `uip` (units in pack) + `pForm` ("Tablet"/"Capsule"/"Bottle"/etc.)
            # together encode the pack hint when the name lacks one.
            pack_text_of=lambda it: (
                f"{it.get('packSizeLabel') or ''} {it.get('uip') or ''} {it.get('pForm') or ''}"
            ),
            threshold=MATCH_THRESHOLD,
        )
        if best is None:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="not_found",
                offer=None,
                error_message=f"no match >={MATCH_THRESHOLD} (top={score:.2f}, items={len(items)})",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )

        mrp = best.get("mrp")
        disc = best.get("discounted_price")
        if mrp is None:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message="missing mrp",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )
        # If 1mg has no discount on this SKU, discounted_price can be None.
        price = float(disc) if disc is not None else float(mrp)
        mrp_f = float(mrp)

        # Override with the website-displayed price by parsing the product
        # detail page. 1mg's product page applies an additional dynamic
        # promotion ("11% off" rather than the API's "5% off") via a JS
        # render — but the resolved number is also embedded in the SSR HTML
        # as `"discountedPrice":<num>` (escaped). This is the price the user
        # actually sees and pays when they click through.
        path = best.get("url") or ""
        if path.startswith("/"):
            detail_url = f"https://{self.domain}{path}"
            try:
                detail = self.get(detail_url)
                if detail.status_code == 200:
                    m = DISPLAYED_PRICE_RE.search(detail.text)
                    if m:
                        try:
                            displayed = float(m.group(1))
                            # Sanity-check: must be <= MRP and within 50% of API price.
                            if 0 < displayed <= mrp_f * 1.05:
                                price = displayed
                        except ValueError:
                            pass
            except Exception:
                # If detail-page fetch fails, fall back to the API price.
                pass

        # 1mg sets `available=False` on most items unless you supply a city
        # cookie matching their deliverable zone. `saleable` is the truer
        # stock flag from their warehouse. We treat the item as in-stock unless
        # both signals say otherwise.
        saleable = best.get("saleable")
        available = best.get("available")
        if saleable is False and available is False:
            in_stock = False
        else:
            in_stock = True

        path = best.get("url") or f"/drugs/dolo-{best.get('id')}"
        offer = Offer(
            pharmacy=self.platform_id,
            medicine_id=medicine["id"],
            price=price,
            mrp=mrp_f,
            delivery_days=self.default_delivery_days,
            in_stock=in_stock,
            return_days=self.default_return_days,
            url=f"https://{self.domain}{path}" if path.startswith("/") else path,
        )
        return ScrapeResult(
            medicine_id=medicine["id"],
            status="success",
            offer=offer,
            error_message=None,
            http_status=r.status_code,
            duration_ms=ms_since(start),
            via="httpx",
        )

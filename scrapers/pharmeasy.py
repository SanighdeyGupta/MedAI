"""PharmEasy scraper.

PharmEasy's search results page is server-rendered as a Next.js app:
the full product list lives in `props.pageProps.searchResults[]` inside
the `<script id="__NEXT_DATA__">` blob. No browser execution needed.

The endpoint pattern is:
  https://pharmeasy.in/search/all?name=<query>

Item shape (relevant fields from props.pageProps.searchResults[i]):
    name:                              "Dolo 650Mg Strip Of 15 Tablets"
    slug:                              "dolo-650mg-strip-of-15-tablets-44140"
    salePriceDecimal:                  "24.09"   (effective)
    mrpDecimal:                        "32.12"   (MRP)
    productAvailabilityFlags.isAvailable: bool
    moleculeName:                      "PARACETAMOL / ACETAMINOPHEN"

Product URL: https://pharmeasy.in/online-medicine-order/<slug>

ToS posture (see ../LEGAL.md):
  PharmEasy's robots.txt disallows /search/all*. We rate-limit to
  <= 1 req/sec, fetch only public price data, never republish a downloadable
  dataset, and deep-link every result to the source PharmEasy page so they
  receive the user click. This trade-off is documented and a takedown email
  results in immediate removal.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .base import Offer, PharmacyScraper, ScrapeResult, ms_since
from .match_helpers import pick_best

SEARCH_URL = "https://pharmeasy.in/search/all"
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>',
    re.DOTALL,
)
def _extract_next_data(html: str) -> dict | None:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class PharmEasyScraper(PharmacyScraper):
    domain = "pharmeasy.in"
    platform_id = "PharmEasy"
    default_delivery_days = 3
    default_return_days = 7

    def scrape(self, medicine: dict) -> ScrapeResult:
        start = time.monotonic()
        url = f"{SEARCH_URL}?name={medicine['name'].replace(' ', '+')}"

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

        data = _extract_next_data(r.text)
        if data is None:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message="__NEXT_DATA__ not found / invalid JSON",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )

        items = (
            data.get("props", {})
            .get("pageProps", {})
            .get("searchResults")
            or []
        )

        best, score = pick_best(
            items,
            target_name=medicine["name"],
            target_pack=medicine.get("pack"),
            name_of=lambda it: it.get("name") or "",
            # PharmEasy's `manufacturerName` + `packShortName` sometimes contain
            # the pack hint when `name` does not.
            pack_text_of=lambda it: " ".join(
                [
                    it.get("packShortName") or "",
                    it.get("manufacturerName") or "",
                ]
            ),
            threshold=0.50,
        )
        if best is None:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="not_found",
                offer=None,
                error_message=f"no match >=0.50 (top={score:.2f}, items={len(items)})",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )

        sale = _to_float(best.get("salePriceDecimal"))
        mrp = _to_float(best.get("mrpDecimal"))
        if sale is None or mrp is None:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message="missing salePriceDecimal or mrpDecimal",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )

        availability = (best.get("productAvailabilityFlags") or {}).get("isAvailable", False)
        slug = best.get("slug") or ""

        offer = Offer(
            pharmacy=self.platform_id,
            medicine_id=medicine["id"],
            price=sale,
            mrp=mrp,
            delivery_days=self.default_delivery_days,
            in_stock=bool(availability),
            return_days=self.default_return_days,
            url=(
                f"https://{self.domain}/online-medicine-order/{slug}"
                if slug
                else f"https://{self.domain}/"
            ),
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

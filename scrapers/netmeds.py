"""Netmeds scraper.

Uses the official Fynd-platform search API discovered at:
  https://www.netmeds.com/ext/search/application/api/v1.0/products?q=<query>

This endpoint is reachable from datacenter IPs with no WAF challenge, and
Netmeds' robots.txt does not disallow the /ext/ path. We rate-limit to
≤ 1 req/sec/domain as a courtesy.

Item shape (relevant fields):
    name:       "Dolo 650 Tablet 15's"
    slug:       "dolo-650-tablet-15s-lui1wb-8231049"
    sellable:   bool (= in_stock)
    price.effective.min: float (INR, after discount)
    price.marked.min:    float (INR, MRP)
    discount:   "18% OFF" string

Product URL: https://www.netmeds.com/product/<slug>
"""
from __future__ import annotations

import time

from .base import Offer, PharmacyScraper, ScrapeResult, ms_since
from .match_helpers import pick_best

SEARCH_URL = "https://www.netmeds.com/ext/search/application/api/v1.0/products"


class NetmedsScraper(PharmacyScraper):
    domain = "www.netmeds.com"
    platform_id = "Netmeds"
    default_delivery_days = 4
    default_return_days = 5

    def scrape(self, medicine: dict) -> ScrapeResult:
        start = time.monotonic()
        url = f"{SEARCH_URL}?q={medicine['name']}&page_size=5"
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

        items = data.get("items") or []
        best, score = pick_best(
            items,
            target_name=medicine["name"],
            target_pack=medicine.get("pack"),
            name_of=lambda it: it.get("name") or "",
            threshold=0.55,
        )
        if best is None:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="not_found",
                offer=None,
                error_message=f"no match >=0.55 (top={score:.2f})",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )

        price = (best.get("price") or {}).get("effective", {}).get("min")
        mrp = (best.get("price") or {}).get("marked", {}).get("min")
        if price is None or mrp is None:
            return ScrapeResult(
                medicine_id=medicine["id"],
                status="error",
                offer=None,
                error_message="missing price.effective.min or price.marked.min",
                http_status=r.status_code,
                duration_ms=ms_since(start),
                via="httpx",
            )

        slug = best.get("slug") or ""
        offer = Offer(
            pharmacy=self.platform_id,
            medicine_id=medicine["id"],
            price=float(price),
            mrp=float(mrp),
            delivery_days=self.default_delivery_days,
            in_stock=bool(best.get("sellable", False)),
            return_days=self.default_return_days,
            url=f"https://{self.domain}/product/{slug}" if slug else f"https://{self.domain}/",
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

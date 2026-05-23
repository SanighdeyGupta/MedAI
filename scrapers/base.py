"""Abstract pharmacy scraper. Centralises ToS hygiene: robots.txt check,
per-domain rate limiting, real-Chrome UA, structured ScrapeResult.

Each concrete scraper (Netmeds, PharmEasy, Apollo, 1mg) subclasses
PharmacyScraper and implements `scrape(medicine) -> ScrapeResult`.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal
from urllib.robotparser import RobotFileParser

import httpx

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

ScrapeStatus = Literal["success", "not_found", "blocked", "error", "rate_limited"]


@dataclass
class Offer:
    pharmacy: str
    medicine_id: str
    price: float
    mrp: float
    delivery_days: int
    in_stock: bool
    return_days: int
    url: str


@dataclass
class ScrapeResult:
    medicine_id: str
    status: ScrapeStatus
    offer: Offer | None
    error_message: str | None
    http_status: int | None
    duration_ms: int
    via: str  # 'httpx', 'patchright', 'scraperapi'


class RateLimiter:
    """Polite minimum interval between requests to a single domain."""

    def __init__(self, min_interval_s: float = 1.0):
        self.min_interval = min_interval_s
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()


class PharmacyScraper(ABC):
    """Subclass and set the four class vars + implement `scrape()`."""

    domain: str
    platform_id: str
    default_delivery_days: int = 4
    default_return_days: int = 7
    ua: str = CHROME_UA

    def __init__(self, rate_limit_s: float = 1.0):
        self.rate_limiter = RateLimiter(rate_limit_s)
        self.robots = RobotFileParser()
        self.robots.set_url(f"https://{self.domain}/robots.txt")
        try:
            self.robots.read()
        except Exception:
            # If robots.txt fails to load, default-allow (with a note in logs)
            pass
        self.client = httpx.Client(
            headers={
                "User-Agent": self.ua,
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-IN,en;q=0.9",
                "Referer": f"https://{self.domain}/",
            },
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            http2=False,
        )

    def can_fetch(self, url: str) -> bool:
        try:
            return self.robots.can_fetch(self.ua, url)
        except Exception:
            return True

    def get(self, url: str) -> httpx.Response:
        if not self.can_fetch(url):
            raise PermissionError(f"robots.txt disallows GET {url}")
        self.rate_limiter.wait()
        return self.client.get(url)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    @abstractmethod
    def scrape(self, medicine: dict) -> ScrapeResult:
        """Look up a single medicine on this pharmacy. Always return a
        ScrapeResult — never raise. Errors become status='error' with
        error_message set, so the run loop can keep going."""
        ...


def ms_since(start: float) -> int:
    return int((time.monotonic() - start) * 1000)

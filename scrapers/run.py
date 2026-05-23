"""CLI entrypoint: `python -m scrapers.run --site netmeds --limit 25`

Loads .env.local from project root (mirrors Next.js behaviour), then
fetches medicines from Supabase, runs the chosen scraper against each,
upserts successful results into the prices table, logs every attempt
into scrape_log.

Exit code 0 if at least one medicine succeeded; 1 if all failed
(so GitHub Actions shows a red X when the platform is completely down).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env.local")
load_dotenv(ROOT / ".env")  # fall back to .env if present

# Imports that depend on env vars must come AFTER load_dotenv:
from .apollo import ApolloScraper  # noqa: E402
from .db import get_admin_client, list_medicines, log_scrape, upsert_price  # noqa: E402
from .netmeds import NetmedsScraper  # noqa: E402
from .one_mg import OneMgScraper  # noqa: E402
from .pharmeasy import PharmEasyScraper  # noqa: E402

SCRAPERS: dict[str, type] = {
    "netmeds": NetmedsScraper,
    "pharmeasy": PharmEasyScraper,
    "apollo": ApolloScraper,
    "1mg": OneMgScraper,
}

STATUS_GLYPH = {
    "success": "[OK]",
    "not_found": "[?]",
    "blocked": "[X]",
    "error": "[!]",
    "rate_limited": "[~]",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a pharmacy scraper against Supabase.")
    parser.add_argument("--site", required=True, choices=list(SCRAPERS))
    parser.add_argument("--limit", type=int, default=25, help="Max medicines to scrape.")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB; just print.")
    args = parser.parse_args()

    sb = get_admin_client()
    medicines = list_medicines(sb, args.limit)
    if not medicines:
        print("No medicines in database. Did you run `npm run seed` first?")
        return 1

    scraper_cls = SCRAPERS[args.site]
    scraper = scraper_cls()

    print(f"Scraping {args.site} for {len(medicines)} medicines (rate limit ~1 req/s)...")

    success = 0
    by_status: dict[str, int] = {}

    try:
        for med in medicines:
            result = scraper.scrape(med)
            glyph = STATUS_GLYPH.get(result.status, "?")
            by_status[result.status] = by_status.get(result.status, 0) + 1

            if result.status == "success" and result.offer:
                if not args.dry_run:
                    upsert_price(sb, result.offer)
                success += 1
                print(
                    f"  {glyph} {med['name']:<28s}  "
                    f"INR {result.offer.price:>8.2f}  "
                    f"(MRP {result.offer.mrp:>7.2f})  "
                    f"{result.duration_ms}ms"
                )
            else:
                print(
                    f"  {glyph} {med['name']:<28s}  {result.status}"
                    f"  {result.error_message or ''}  ({result.duration_ms}ms)"
                )

            if not args.dry_run:
                try:
                    log_scrape(sb, result, scraper.platform_id)
                except Exception as e:
                    print(f"  (log write failed: {e})")
    finally:
        scraper.close()

    print("\nSummary:", ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
    print(f"{success}/{len(medicines)} medicines scraped successfully.")
    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

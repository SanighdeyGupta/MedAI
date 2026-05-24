"""Supabase admin client wrapper for scrapers.

The scrapers run with the service-role key (RLS-bypass), since they need
to insert into scrape_log and upsert prices server-side. Service role
must NEVER be exposed to a browser — these scripts run only in GitHub
Actions or on the developer's machine.
"""
from __future__ import annotations

import os
from typing import Any

from supabase import Client, create_client

from .base import Offer, ScrapeResult


def get_admin_client() -> Client:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY. "
            "Put them in .env.local (local) or repo Secrets (GitHub Actions)."
        )
    return create_client(url, key)


def list_medicines(sb: Client, limit: int = 25) -> list[dict[str, Any]]:
    # Order by created_at desc so freshly-discovered medicines get scraped
    # FIRST. Without an order, Postgres returns rows in arbitrary order and
    # the limit can permanently exclude on-demand-discovered medicines
    # (which then show "1d ago" prices forever because the cron never picks
    # them up). Discovered rows have the newest created_at, so DESC puts
    # them at the front.
    res = (
        sb.table("medicines")
        .select("id,name,composition,manufacturer,pack,rx_required")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def upsert_price(sb: Client, offer: Offer) -> None:
    sb.table("prices").upsert(
        {
            "medicine_id": offer.medicine_id,
            "platform_id": offer.pharmacy,
            "price": offer.price,
            "mrp": offer.mrp,
            "delivery_days": offer.delivery_days,
            "in_stock": offer.in_stock,
            "return_days": offer.return_days,
            "url": offer.url,
            # fetched_at + stale_after use DB defaults (now() / now() + 12h)
        },
        on_conflict="medicine_id,platform_id",
    ).execute()


def log_scrape(sb: Client, result: ScrapeResult, platform_id: str) -> None:
    sb.table("scrape_log").insert(
        {
            "platform_id": platform_id,
            "medicine_id": result.medicine_id,
            "status": result.status,
            "http_status": result.http_status,
            "duration_ms": result.duration_ms,
            "via": result.via,
            "error_message": result.error_message,
        }
    ).execute()

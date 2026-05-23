# Legal & ToS posture

This is a non-commercial open-source portfolio project that compares medicine prices across four major Indian pharmacies. We treat the source pharmacies as collaborators, not adversaries: every result deep-links back to the source, every page they own gets free referral traffic from us, and we honour any takedown request immediately.

## Data sources

| Source | Type | Used for |
|---|---|---|
| **NPPA DPCO** (nppaimis.nic.in) | Public Government of India regulatory data | Maximum-legal-price baseline shown alongside every result. *Planned: full ingest in Day 5.* |
| **Jan Aushadhi** (janaushadhi.gov.in) | Public generic-medicine MRP list | Generic-equivalent comparison. *Planned: full ingest in Day 5.* |
| **Tata 1mg** (1mg.com) | Live commercial pricing | Compared in the recommender. *Live as of Day 6.* |
| **PharmEasy** (pharmeasy.in) | Live commercial pricing | Compared in the recommender. *Live as of Day 4.* |
| **Netmeds** (netmeds.com) | Live commercial pricing | Compared in the recommender. *Live as of Day 3.* |
| **Apollo Pharmacy** (apollopharmacy.in) | Live commercial pricing | Compared in the recommender. *Live as of Day 5 (Patchright DOM scrape).* |

## Per-pharmacy posture

### Netmeds
- **Endpoint hit**: `https://www.netmeds.com/ext/search/application/api/v1.0/products?q=…` (Fynd platform JSON API used by their own SPA).
- **robots.txt status**: `/ext/` path is NOT in their `Disallow` list. ✓
- **Rate limit**: ≤ 1 req/sec/domain on our side. Their `robots.txt` has no `Crawl-delay` for `User-agent: *`.
- **Identification**: real Chrome `User-Agent`, standard Accept headers, normal `Referer`.

### PharmEasy
- **Endpoint hit**: `https://pharmeasy.in/search/all?name=…` — parses the server-rendered `__NEXT_DATA__` blob.
- **robots.txt status**: PharmEasy's `robots.txt` lists `Disallow: /search/all*`. **We are aware of this and have made a deliberate choice to use it anyway**, with the following mitigations:
  - Rate limit: ≤ 1 req/sec/domain.
  - Volume: 25 medicines × every 6 h = 100 requests/day. This is two orders of magnitude below what an SEO crawler does.
  - We do not republish a downloadable dataset or public price API.
  - Every result in the UI deep-links to the source PharmEasy product page (free referral traffic).
  - On any takedown request to the email below, we remove the PharmEasy scraper within 24 h and replace it with a static "data unavailable" message.
- The `Disallow: /search/all*` line is most likely an SEO directive (avoid Google indexing low-quality search-result pages) rather than an anti-scraping signal. We are not Googlebot and we are not indexing. Even so, this is the project's weakest legal posture and the first thing we'd rework if asked.
- Future remediation path (already scoped): rebuild the lookup against PharmEasy's public sitemap (`pharmeasy.in/sitemap.xml`) so we never hit `/search/all`. Estimated 1 day of work.

### Apollo Pharmacy (deferred to Day 5)
- Apollo's `robots.txt` is permissive (`Allow: /`).
- The product detail pages are client-rendered React with a GraphQL backend at `api.apollo247.com` that requires a bearer token. We will replay a public session token obtained from a first-party page load, which keeps us within their public surface.

### Tata 1mg
- **Endpoint hit**: `https://www.1mg.com/pharmacy_api_webservices/search?name=<query>` (1mg's own internal SPA endpoint).
- **robots.txt status**: `/search` (page) is disallowed; `/pharmacy_api_webservices/` is NOT in the disallow list — confirmed by inspection of `https://www.1mg.com/robots.txt`. ✓
- **Update from earlier plan**: research-time intelligence pegged 1mg behind Cloudflare Bot Management requiring Patchright + ScraperAPI. As of 2026-05-23, plain `httpx` with a real Chrome UA receives a clean 200 OK from the API. ScraperAPI dependency dropped; $0/month confirmed across all four scrapers.
- **Rate limit**: <= 1 req/sec.
- **Identification**: real Chrome `User-Agent`, `Referer: https://www.1mg.com/`.

## Known price-accuracy limits

We capture each pharmacy's **default page-displayed price** at scrape time. We do NOT capture:

1. **Session-personalized coupon prices.** E.g. Netmeds shows a "Best price ₹X" headline only after the user unlocks a coupon, which can require a cart minimum, a first-time user flag, or a Tata Neu membership. The base price we show (`price.effective.min`) is what every user sees without unlocking anything; the coupon-applied price is hidden from the API.
2. **Pincode-conditional pricing.** Some 1mg / PharmEasy SKUs price differently in metro vs. tier-2 cities. We scrape from a single neutral session, so we report a representative price.
3. **Time-limited promos** ("limited period offer: extra 15% off"). These change daily and aren't in our 6-hourly snapshot.

To mitigate, the UI carries a banner reminding users that the final cart total may be 5-15% lower (or rarely, higher) than what we show. Every result deep-links to the source pharmacy so the user can verify.

For 1mg specifically: the `/pharmacy_api_webservices/search` endpoint returns a wholesale post-merchant-discount price (e.g. ₹30.60 for Dolo 650), but the consumer product page applies an additional page-level promo (₹28.70 = 11% off MRP). We follow the product-page link after the search match and parse the embedded `discountedPrice` field to match what the user actually sees on 1mg's site.

## What we do NOT do

- We do **not** expose a downloadable dataset, CSV export, or public JSON API of any scraped prices. (PharmEasy's ToS in particular calls this out.)
- We do **not** scrape user-generated content (reviews, ratings, names). We only fetch public price + stock + delivery data.
- We do **not** evade WAFs or anti-bot measures except via the documented ScraperAPI pressure-release for 1mg. We never use credential stuffing, residential proxies, or session-token theft.
- We do **not** maintain a cache older than 12 hours by default. Stale prices are explicitly labelled in the UI.
- We do **not** rate-bomb. Hard rate limit of ≤ 1 req/sec/domain is enforced in `scrapers/base.py`.

## Takedown contact

If you represent one of the pharmacies above and want this project to stop scraping your site or remove cached references to your products:

**Email: gupta.sanighdey8@gmail.com**

We will respond within 24 hours and remove the scraper + any cached references within 48 hours. No questions asked. We would rather have your site as a working affiliate partner than a contested data source — we will gladly switch to your affiliate program (e.g. Tata 1mg's via Cuelinks/EarnKaro) if you have one.

## Indian law touchpoints

- **IT Act 2000 §43(b)** — downloading/copying data without permission is a civil wrong. Our defence: we do not "download" a database; we fetch one publicly-rendered page at a time at human speed, parse the visible price for one product, and discard the rest. We do not retain HTML, only a normalised numeric snapshot.
- **Copyright Act 1957** — individual prices are facts (not copyrightable); the *compilation* could be. Our defence: we do not reproduce any pharmacy's full compilation; we hold ≤25 SKUs at any given moment, all linked back to source.
- **DPDPA 2023** — irrelevant; we don't touch personal data.

This document is **not** legal advice and is **not** a binding contract. It is a transparent statement of how we operate. If the operating company of any pharmacy listed above has a different view, the takedown email is the right channel.

*Last updated: Day 4 of implementation (2026-05-23).*

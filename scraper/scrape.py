"""Google Maps scraper for pest-control businesses.

Usage:
    python scraper/scrape.py                  # scrape every category x city
    python scraper/scrape.py --limit 5        # only first 5 jobs (smoke test)
    python scraper/scrape.py --headful        # watch the browser
    python scraper/scrape.py --proxy http://user:pass@host:port

Grey-hat notes:
  - Datacenter IPs get blocked fast. Pass --proxy with a residential/mobile
    rotating endpoint for any real volume.
  - Human-ish delays + stealth are on by default. Don't crank concurrency.
  - Data is stored in data/pestcontrol.db (SQLite). Resumable: dedups on CID.
"""
import argparse
import asyncio
import json
import os
import random
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

from playwright.async_api import async_playwright  # noqa: E402

try:
    from playwright_stealth import stealth_async
except Exception:  # optional dependency
    async def stealth_async(page):  # type: ignore
        return None

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def human_pause(a=0.8, b=2.2):
    await asyncio.sleep(random.uniform(a, b))


def parse_latlng(url: str):
    # detail urls embed !3d<lat>!4d<lng>
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url or "")
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url or "")
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def parse_cid(url: str):
    m = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", url or "")
    return m.group(1) if m else None


async def scrape_detail(page, category, city, state):
    """Pull fields from the currently-open place detail panel."""
    async def txt(sel):
        el = await page.query_selector(sel)
        return (await el.inner_text()).strip() if el else None

    async def attr(sel, a):
        el = await page.query_selector(sel)
        return await el.get_attribute(a) if el else None

    name = await txt("h1.DUwDvf") or await txt("h1")
    if not name:
        return None

    rating_raw = await txt('div.F7nice span[aria-hidden="true"]')
    reviews_raw = await attr('div.F7nice span[aria-label*="review"]', "aria-label") \
        or await txt('div.F7nice span[aria-label*="review"]')
    address = await attr('button[data-item-id="address"]', "aria-label")
    phone = await attr('button[data-item-id^="phone"]', "aria-label")
    website = await attr('a[data-item-id="authority"]', "href")
    url = page.url
    lat, lng = parse_latlng(url)

    def num(s, cast=float):
        if not s:
            return None
        m = re.search(r"[\d.,]+", s.replace(",", ""))
        try:
            return cast(m.group()) if m else None
        except ValueError:
            return None

    return {
        "name": name,
        "category": category,
        "city": city,
        "state": state,
        "address": (address or "").replace("Address: ", "") or None,
        "phone": (phone or "").replace("Phone: ", "") or None,
        "website": website,
        "lat": lat,
        "lng": lng,
        "rating": num(rating_raw, float),
        "reviews": num(reviews_raw, int),
        "hours": None,
        "maps_url": url,
        "cid": parse_cid(url),
    }


async def scrape_query(page, query, category, city, state, conn, max_results=20):
    url = "https://www.google.com/maps/search/" + urllib.parse.quote(query)
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await human_pause(2, 4)

    # consent wall (EU/sometimes US)
    for sel in ['button[aria-label*="Accept"]', 'form[action*="consent"] button']:
        btn = await page.query_selector(sel)
        if btn:
            await btn.click()
            await human_pause()

    feed = await page.query_selector('div[role="feed"]')
    if not feed:
        # single result -> Maps jumped straight to a detail panel
        row = await scrape_detail(page, category, city, state)
        if row and db.upsert(conn, row):
            return 1
        return 0

    # scroll the results column to load more
    links = []
    for _ in range(12):
        cards = await page.query_selector_all('div[role="feed"] a.hfpxzc')
        found = [l for l in [await c.get_attribute("href") for c in cards] if l]
        prev = len(links)
        links = found
        if len(links) >= max_results or len(links) == prev:
            break
        await page.evaluate(
            'document.querySelector(`div[role="feed"]`).scrollBy(0, 2500)'
        )
        await human_pause(1.0, 2.0)

    added = 0
    for link in links[:max_results]:
        try:
            await page.goto(link, wait_until="domcontentloaded", timeout=45000)
            await human_pause(1.2, 2.6)
            row = await scrape_detail(page, category, city, state)
            if row and db.upsert(conn, row):
                added += 1
        except Exception as e:
            print(f"    ! detail fail: {e}")
            continue
    return added


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap number of jobs")
    ap.add_argument("--max-results", type=int, default=20, help="per query")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--proxy", default=None, help="single proxy URL")
    ap.add_argument("--proxy-file", default=None,
                    help="file with one proxy URL per line; rotated per query")
    ap.add_argument("--rotate-every", type=int, default=8,
                    help="new proxy + fresh browser context every N queries")
    ap.add_argument("--allow-bare-ip", action="store_true",
                    help="DANGER: scrape from your real IP with no proxy")
    ap.add_argument("--offset", type=int, default=0,
                    help="skip the first N jobs (for sharding across CI runs)")
    args = ap.parse_args()

    # In cloud CI the runner's IP is disposable (not your home IP), so bare-IP
    # is acceptable there. The guard still protects a laptop run.
    cloud_ci = os.environ.get("PCD_CLOUD_CI") == "1"

    # ---- IP-safety guard: never blast Google from the home IP by accident ----
    proxies = []
    if args.proxy_file and Path(args.proxy_file).exists():
        proxies = [l.strip() for l in Path(args.proxy_file).read_text().splitlines()
                   if l.strip() and not l.startswith("#")]
    elif args.proxy:
        proxies = [args.proxy]

    if not proxies and not args.allow_bare_ip and not cloud_ci:
        print(
            "REFUSING TO RUN: no proxy configured.\n"
            "  Scraping Google from your home IP risks a ban on that IP.\n"
            "  Fix one of these ways:\n"
            "    --proxy http://user:pass@host:port        (single rotating endpoint)\n"
            "    --proxy-file proxies.txt                   (pool, rotated per query)\n"
            "  Or, if you truly accept the risk on THIS machine's IP:\n"
            "    --allow-bare-ip\n"
            "  Safest of all: don't run this at all — use Apify's cloud scraper "
            "(your IP never touches Google). See README."
        )
        sys.exit(2)

    import targets
    conn = db.connect()
    job_list = list(targets.jobs())
    total_all = len(job_list)
    if args.offset:
        job_list = job_list[args.offset:]
    if args.limit:
        job_list = job_list[: args.limit]

    print(f"DB: {db.DB_PATH}")
    print(f"Jobs: {len(job_list)} of {total_all}  "
          f"(offset {args.offset}, start count: {db.count(conn)})")
    print(f"Proxies: {len(proxies) or 'NONE (bare IP!)'}  "
          f"rotate every {args.rotate_every} queries")

    async with async_playwright() as p:
        browser = None
        ctx = None
        page = None
        pidx = -1

        async def new_session(force_proxy_advance=True):
            nonlocal browser, ctx, page, pidx
            if ctx:
                await ctx.close()
            launch_kw = {"headless": not args.headful}
            if proxies:
                if force_proxy_advance:
                    pidx = (pidx + 1) % len(proxies)
                launch_kw["proxy"] = {"server": proxies[pidx]}
                print(f"  -> proxy [{pidx}] {proxies[pidx].split('@')[-1]}")
            if browser is None:
                browser = await p.chromium.launch(**launch_kw) if not proxies \
                    else await p.chromium.launch(**launch_kw)
            # relaunch browser so proxy actually changes (proxy is per-launch)
            else:
                await browser.close()
                browser = await p.chromium.launch(**launch_kw)
            ctx = await browser.new_context(
                user_agent=UA, viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            page = await ctx.new_page()
            await stealth_async(page)

        await new_session(force_proxy_advance=True)

        for i, (query, category, city, state) in enumerate(job_list, 1):
            if i > 1 and (i - 1) % args.rotate_every == 0 and proxies:
                await new_session(force_proxy_advance=True)
            try:
                n = await scrape_query(
                    page, query, category, city, state, conn, args.max_results
                )
                print(f"[{i}/{len(job_list)}] +{n:<3} {query}  (total={db.count(conn)})")
            except Exception as e:
                print(f"[{i}/{len(job_list)}] FAIL {query}: {e}")
                # an error mid-run often means a soft block -> rotate IP
                if proxies:
                    await new_session(force_proxy_advance=True)
            await human_pause(1.5, 3.5)

        if browser:
            await browser.close()

    print(f"\nDone. Total listings: {db.count(conn)}")


if __name__ == "__main__":
    asyncio.run(main())

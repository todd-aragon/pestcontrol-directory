# Pest Control Directory

A pest-control business directory — same playbook as mobiledetailing.io:
scrape Google Maps → store in DB → render thousands of SEO pages with Flask.

## Project layout

```
pestcontrol-directory/
├── scraper/            # data harvester (BUILT)
│   ├── scrape.py       # Playwright Google Maps scraper -> SQLite
│   ├── db.py           # schema + slugify + dedup upsert
│   ├── targets.py      # categories x cities to search
│   └── export.py       # dump DB to CSV/JSON
├── data/               # pestcontrol.db lives here (gitignored)
└── web/                # Flask app (NEXT step, not built yet)
```

## 1. Setup

```bash
cd pestcontrol-directory
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt
python -m playwright install chromium
```

## 2. Smoke test (5 queries, watch it run)

```bash
python scraper/scrape.py --limit 5 --headful
```

## 3. Full harvest

```bash
python scraper/scrape.py --max-results 20
# with a residential proxy (recommended for volume):
python scraper/scrape.py --proxy http://user:pass@host:port
```

Resumable — dedups on Google place CID, so re-running tops up the DB.

## 4. Export

```bash
python scraper/export.py     # writes data/listings.csv + listings.json
```

## Categories scraped
General Pest Control · Exterminators · Termite Control · Bed Bug Removal ·
Rodent Control · Mosquito Control · Wildlife Removal

## Cities — NATIONWIDE
Top 1,000 US cities by population, loaded from `data/us-cities.csv`.
1,000 cities × 7 categories = **7,000 search jobs**. CID dedup collapses the
metro overlap → tens of thousands of unique businesses, near-complete US coverage.

Tune scope with env vars:
```bash
PCD_MIN_POP=100000 python scraper/scrape.py     # only cities >100k (293 cities)
PCD_MAX_CITIES=300 python scraper/scrape.py      # largest 300 cities only
```

## Next steps
- [ ] Build `web/` Flask app (homepage, /listing/<slug>, /cities, /categories, sitemap.xml)
- [ ] Tailwind + Font Awesome theme (clone of the reference site)
- [ ] Lead-capture quote form + AdSense slots
- [ ] Deploy behind Cloudflare

## Protecting your IP (READ THIS)

The scraper **refuses to run without a proxy** — it will not let you blast
Google from your home IP. Three safe paths:

### Safest: don't scrape yourself — use a cloud scraper
Your IP never touches Google at all.
- **Apify "Google Maps Scraper"** actor — runs on Apify's IPs. ~$5 free credit,
  then ~$0.50–$4 / 1,000 results. Full nationwide ≈ $30–80 one-time.
- **Outscraper / SerpApi** — same model, pay per result.

### Proxy pool (run this scraper, home IP hidden)
Put one proxy per line in `proxies.txt`, then:
```bash
python scraper/scrape.py --proxy-file proxies.txt --rotate-every 8
```
The script relaunches the browser through a new proxy every 8 queries, and
rotates immediately on any error (a soft block). Google only ever sees proxy
IPs; your home IP stays clean. Cheap residential providers: IPRoyal, Webshare,
Bright Data, Smartproxy. **Use residential/mobile** — datacenter proxies get
blocked almost as fast as a bare IP.

### Single rotating endpoint
Most providers give one "gateway" URL that rotates IP per request:
```bash
python scraper/scrape.py --proxy http://user:pass@gateway.provider.com:7777
```

### Last resort (NOT recommended)
```bash
python scraper/scrape.py --allow-bare-ip    # uses YOUR ip — ban risk
```

## Notes
Scraping Google Maps violates their ToS. Use rotating residential proxies,
keep concurrency low, and don't republish Google review *text* verbatim.

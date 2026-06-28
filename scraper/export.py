"""Export the scraped DB to CSV / JSON for inspection or import into the web app."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db

COLS = ["id", "name", "slug", "category", "city", "state", "address",
        "phone", "website", "lat", "lng", "rating", "reviews", "maps_url", "cid"]


def main():
    conn = db.connect()
    rows = conn.execute(f"SELECT {','.join(COLS)} FROM listings").fetchall()
    out = Path(__file__).resolve().parent.parent / "data"

    with open(out / "listings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)

    with open(out / "listings.json", "w", encoding="utf-8") as f:
        json.dump([dict(zip(COLS, r)) for r in rows], f, indent=2)

    print(f"Exported {len(rows)} listings -> {out/'listings.csv'} / listings.json")


if __name__ == "__main__":
    main()

"""Search targets: pest-control categories x US cities (NATIONWIDE).

Cities load from data/us-cities.csv (top ~1,000 US cities by population).
1,000 cities x 7 categories = 7,000 search jobs. With CID dedup collapsing the
metro overlap, that yields tens of thousands of unique businesses covering
essentially every real pest-control company in the country.

Widen or narrow with env vars:
    PCD_MIN_POP=50000   only cities above this population
    PCD_MAX_CITIES=300  cap number of cities (largest first)
"""
import csv
import os
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "us-cities.csv"

# Google Maps search phrases -> display category label.
CATEGORIES = [
    ("pest control",        "General Pest Control"),
    ("exterminator",        "Exterminators"),
    ("termite control",     "Termite Control"),
    ("bed bug treatment",   "Bed Bug Removal"),
    ("rodent control",      "Rodent Control"),
    ("mosquito control",    "Mosquito Control"),
    ("wildlife removal",    "Wildlife Removal"),
]

STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


def load_cities():
    """Return [(city, state_abbr, population)] sorted largest-first, filtered."""
    min_pop = int(os.environ.get("PCD_MIN_POP", "0"))
    max_cities = int(os.environ.get("PCD_MAX_CITIES", "0"))
    rows = []
    with open(DATA, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pop = int(r["Population"])
            if pop < min_pop:
                continue
            st = STATE_ABBR.get(r["State"], r["State"])
            rows.append((r["City"], st, pop))
    rows.sort(key=lambda x: x[2], reverse=True)
    if max_cities:
        rows = rows[:max_cities]
    return rows


def jobs():
    """Yield (query, category_label, city, state) for every combo."""
    for city, st, _pop in load_cities():
        for phrase, label in CATEGORIES:
            yield (f"{phrase} in {city}, {st}", label, city, st)

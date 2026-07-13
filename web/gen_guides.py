"""Generate long-form pest-control guides with Groq, stored in the `guides`
table. Top-of-funnel SEO content that pulls informational search traffic and
funnels readers to the directory listings.

    set GROQ_API_KEY=...
    python web/gen_guides.py            # generate all missing guides
    python web/gen_guides.py --force    # regenerate all
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "web"))
import db as dbmod          # noqa: E402
import gen_content as gc    # noqa: E402  (reuse the LLM caller + backoff)

# (slug, title, related category) — high-volume informational queries.
TOPICS = [
    ("how-to-get-rid-of-ants", "How to Get Rid of Ants", "General Pest Control"),
    ("how-to-get-rid-of-cockroaches", "How to Get Rid of Cockroaches", "General Pest Control"),
    ("how-to-get-rid-of-bed-bugs", "How to Get Rid of Bed Bugs", "Bed Bug Removal"),
    ("how-to-get-rid-of-mice-and-rats", "How to Get Rid of Mice and Rats", "Rodent Control"),
    ("how-to-get-rid-of-mosquitoes", "How to Get Rid of Mosquitoes", "Mosquito Control"),
    ("how-to-get-rid-of-wasps", "How to Get Rid of Wasps and Hornets", "General Pest Control"),
    ("how-to-get-rid-of-spiders", "How to Get Rid of Spiders", "General Pest Control"),
    ("how-to-get-rid-of-fleas", "How to Get Rid of Fleas", "General Pest Control"),
    ("signs-of-a-termite-infestation", "Signs of a Termite Infestation", "Termite Control"),
    ("how-much-does-pest-control-cost", "How Much Does Pest Control Cost?", "General Pest Control"),
    ("diy-vs-professional-pest-control", "DIY vs Professional Pest Control", "General Pest Control"),
    ("how-to-choose-a-pest-control-company", "How to Choose a Pest Control Company", "General Pest Control"),
    ("how-often-should-you-get-pest-control", "How Often Should You Get Pest Control?", "General Pest Control"),
    ("is-pest-control-safe-for-pets", "Is Pest Control Safe for Pets and Kids?", "General Pest Control"),
    ("how-to-prevent-pests-in-your-home", "How to Prevent Pests in Your Home", "General Pest Control"),
]


def prompt(title):
    return (
        f"Write a helpful, accurate guide titled '{title}' for a pest-control "
        "directory. Return JSON with keys: "
        "\"description\" (a 150-char meta description), "
        "\"intro\" (80-120 word opening paragraph), "
        "\"sections\" (4-6 items of {\"heading\":..., \"content\":<90-140 word "
        "paragraph>}), "
        "\"faq\" (3 items of {\"q\":..., \"a\":<40-70 words>}). "
        "Practical and specific. When professional help is warranted, say so "
        "plainly without naming any company or inventing prices/statistics.")


def run(force):
    conn = dbmod.connect()
    cur = conn.cursor()
    done = 0
    for slug, title, cat in TOPICS:
        if not force and cur.execute("SELECT 1 FROM guides WHERE slug=?",
                                     (slug,)).fetchone():
            print("skip", slug); continue
        try:
            data = gc.gemini(prompt(title))
            cur.execute(
                "INSERT OR REPLACE INTO guides(slug,title,description,category,"
                "body,generated_at) VALUES (?,?,?,?,?,datetime('now'))",
                (slug, title, data.get("description", ""), cat, json.dumps(data)))
            conn.commit()
            done += 1
            print("ok  ", slug)
        except Exception as e:
            print("FAIL", slug, e)
        time.sleep(1.0)
    print(f"\nGenerated {done} guides.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    run(ap.parse_args().force)

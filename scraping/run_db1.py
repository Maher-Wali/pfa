"""
Runner: DB1 — Clinical Knowledge Corpus
========================================
Runs DB1 scrapers in sequence and prints a summary.

Usage (from the project root):
    .venv\\Scripts\\python.exe scraping/run_db1.py

Scraper status
--------------
ACTIVE — modified/new (run these):
    Mental Health Foundation  — added awareness-week articles + PDF support
    Beyond Blue               — updated to new /mental-health/ URL structure
    CAMH                      — added mental-health-101 + guides-and-publications crawler
    Rethink Mental Illness    — new source
    Cleveland Clinic          — new source

SKIPPED — re-scraped separately / data already good:
    NHS    — re-scraped manually after single-page layout fix
    NICE, NIMH, WHO, CCI, MedlinePlus, Better Health, RCPsych, Mayo Clinic, Mind UK
"""
import sys
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_db1")

from db1_clinical.mental_health_foundation import MentalHealthFoundationScraper
from db1_clinical.beyond_blue              import BeyondBlueScraper
from db1_clinical.camh                     import CAMHScraper
from db1_clinical.rethink                  import RethinkScraper
from db1_clinical.cleveland_clinic         import ClevelandClinicScraper

SCRAPERS = [
    ("Mental Health Foundation", MentalHealthFoundationScraper),
    ("Beyond Blue",              BeyondBlueScraper),
    ("CAMH",                     CAMHScraper),
    ("Rethink Mental Illness",   RethinkScraper),
    ("Cleveland Clinic",         ClevelandClinicScraper),
]


def main():
    totals = {}
    for name, ScraperClass in SCRAPERS:
        log.info("=" * 60)
        log.info("Starting: %s", name)
        log.info("=" * 60)
        try:
            records = ScraperClass().run()
            totals[name] = len(records)
        except Exception as exc:
            log.error("Scraper %s failed: %s", name, exc, exc_info=True)
            totals[name] = 0

    print("\n" + "=" * 60)
    print("DB1 SCRAPING SUMMARY")
    print("=" * 60)
    total = 0
    for name, count in totals.items():
        status = "OK" if count > 0 else "EMPTY"
        print(f"  [{status}] {name:<35} {count:>4} records")
        total += count
    print("-" * 60)
    print(f"  {'TOTAL':<40} {total:>4} records")
    print("=" * 60)
    print(f"\nRaw JSON saved under: {ROOT / 'data' / 'raw' / 'db1_clinical'}/")


if __name__ == "__main__":
    main()

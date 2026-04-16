"""
Runner: DB1 — Clinical Knowledge Corpus
Runs all DB1 scrapers in sequence and prints a summary.

Usage (from the scraping/ directory):
    python run_db1.py

CCI removed — site times out consistently.
HelpGuide added as replacement.
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db1_clinical.nhs                      import NHSScraper
from db1_clinical.nice                     import NICEScraper
from db1_clinical.nimh                     import NIMHScraper
from db1_clinical.who_mhgap               import WHOMhGAPScraper
from db1_clinical.mind_uk                  import MindUKScraper
from db1_clinical.mental_health_foundation import MentalHealthFoundationScraper
from db1_clinical.beyond_blue              import BeyondBlueScraper
from db1_clinical.mayo_clinic              import MayoClinicScraper

log = logging.getLogger("run_db1")

SCRAPERS = [
    ("NHS",                        NHSScraper),
    ("NICE",                       NICEScraper),
    ("NIMH",                       NIMHScraper),
    ("WHO mhGAP",                  WHOMhGAPScraper),
    ("Mind UK",                    MindUKScraper),
    ("Mental Health Foundation",   MentalHealthFoundationScraper),
    ("Beyond Blue",                BeyondBlueScraper),
    ("Mayo Clinic",                MayoClinicScraper),
]


def main():
    totals = {}
    for name, ScraperClass in SCRAPERS:
        log.info("=" * 60)
        log.info("Starting scraper: %s", name)
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
    total_records = 0
    for name, count in totals.items():
        print(f"  {name:<30} {count:>5} records")
        total_records += count
    print("-" * 60)
    print(f"  {'TOTAL':<30} {total_records:>5} records")
    print("=" * 60)
    print(f"\nRaw data saved to: data/raw/db1_clinical/")


if __name__ == "__main__":
    main()

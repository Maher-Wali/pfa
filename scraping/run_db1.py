"""
Runner: DB1 — Clinical Knowledge Corpus
========================================
Runs DB1 scrapers in sequence and prints a summary.

Usage (from the project root):
    .venv\\Scripts\\python.exe scraping/run_db1.py

Source status
-------------
SKIPPED — already in DB with good data (re-scraping would overwrite clean data):
    NHS, NICE, NIMH, WHO

SKIPPED — blocked (0 records returned, not re-tested):
    Mind UK, HelpGuide

ACTIVE — re-scraped (brotli fix applied, previously 100% garbage):
    Beyond Blue, Mental Health Foundation

ACTIVE — new sources (all confirmed PASS in test_scraper.py):
    MedlinePlus, Better Health Channel, Royal College of Psychiatrists, CAMH

To re-enable skipped sources, uncomment their entries in SCRAPERS below.
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# --- Active: re-scraped with brotli fix ---
from db1_clinical.mental_health_foundation import MentalHealthFoundationScraper
from db1_clinical.beyond_blue              import BeyondBlueScraper

# --- Active: new sources ---
from db1_clinical.medlineplus              import MedlinePlusScraper
from db1_clinical.better_health            import BetterHealthScraper
from db1_clinical.rcpsych                  import RCPsychScraper
from db1_clinical.camh                     import CAMHScraper

# --- Skipped: already have good data in DB ---
# from db1_clinical.nhs        import NHSScraper
# from db1_clinical.nice       import NICEScraper
# from db1_clinical.nimh       import NIMHScraper
# from db1_clinical.who_mhgap  import WHOMhGAPScraper

# --- Skipped: blocked / 0 records ---
# from db1_clinical.mind_uk    import MindUKScraper
# from db1_clinical.helpguide  import HelpGuideScraper

log = logging.getLogger("run_db1")

SCRAPERS = [
    # Re-scraped (brotli fix)
    ("Mental Health Foundation",            MentalHealthFoundationScraper),
    ("Beyond Blue",                         BeyondBlueScraper),
    # New sources
    ("MedlinePlus",                         MedlinePlusScraper),
    ("Better Health Channel",               BetterHealthScraper),
    ("Royal College of Psychiatrists",      RCPsychScraper),
    ("CAMH",                                CAMHScraper),
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
    total_records = 0
    for name, count in totals.items():
        print(f"  {name:<35} {count:>5} records")
        total_records += count
    print("-" * 60)
    print(f"  {'TOTAL':<35} {total_records:>5} records")
    print("=" * 60)
    print(f"\nRaw data saved to: data/raw/db1_clinical/")


if __name__ == "__main__":
    main()

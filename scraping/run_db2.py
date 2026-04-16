"""
Runner: DB2 — Therapy Techniques Corpus
=========================================
Runs DB2 scrapers in sequence and prints a summary.

Usage (from the project root):
    .venv\\Scripts\\python.exe scraping/run_db2.py

Source status
-------------
SKIPPED — already in DB with good data (re-scraping would overwrite clean data):
    Anxiety Canada, ACT Mindfully, NHS IAPT

SKIPPED — blocked (WAF / JS-rendered, 0 readable records):
    Therapist Aid, Self-Compassion.org, Positive Psychology,
    Simply Psychology, DBT Self Help

ACTIVE — HTML confirmed PASS in test_scraper.py:
    GetSelfHelp  (HTML pages work; PDF links will gracefully 404 if URLs changed)

ACTIVE — new source, confirmed PASS in test_scraper.py:
    CCI WA  (previously timed out — retry now)

To re-enable skipped sources, uncomment their entries in SCRAPERS below.
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# --- Active ---
from db2_therapy.getselfhelp  import GetSelfHelpScraper
from db2_therapy.cci_wa       import CCIWAScraper

# --- Skipped: already have good data in DB ---
# from db2_therapy.anxiety_canada    import AnxietyCanadaScraper
# from db2_therapy.act_mindfully     import ACTMindfullycraper
# from db2_therapy.iapt              import IAPTScraper

# --- Skipped: blocked / JS-rendered / 0 readable records ---
# from db2_therapy.therapist_aid     import TherapistAidScraper
# from db2_therapy.self_compassion   import SelfCompassionScraper
# from db2_therapy.positive_psychology import PositivePsychologyScraper
# from db2_therapy.simply_psychology import SimplyPsychologyScraper
# from db2_therapy.dbt_selfhelp      import DBTSelfHelpScraper

log = logging.getLogger("run_db2")

SCRAPERS = [
    # HTML confirmed PASS
    ("GetSelfHelp",  GetSelfHelpScraper),
    # New source — gov.au, no bot protection
    ("CCI WA",       CCIWAScraper),
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
    print("DB2 SCRAPING SUMMARY")
    print("=" * 60)
    total_records = 0
    for name, count in totals.items():
        print(f"  {name:<35} {count:>5} records")
        total_records += count
    print("-" * 60)
    print(f"  {'TOTAL':<35} {total_records:>5} records")
    print("=" * 60)
    print(f"\nRaw data saved to: data/raw/db2_therapy/")


if __name__ == "__main__":
    main()

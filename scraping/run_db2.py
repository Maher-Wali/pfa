"""
Runner: DB2 — Therapy Techniques Corpus
Runs all DB2 scrapers in sequence and prints a summary.

Usage (from the scraping/ directory):
    python run_db2.py

CCI Therapy removed — site times out consistently.
Simply Psychology added as replacement.
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db2_therapy.therapist_aid        import TherapistAidScraper
from db2_therapy.getselfhelp          import GetSelfHelpScraper
from db2_therapy.anxiety_canada       import AnxietyCanadaScraper
from db2_therapy.act_mindfully        import ACTMindfullycraper
from db2_therapy.self_compassion      import SelfCompassionScraper
from db2_therapy.positive_psychology  import PositivePsychologyScraper
from db2_therapy.dbt_selfhelp         import DBTSelfHelpScraper
from db2_therapy.iapt                 import IAPTScraper
from db2_therapy.simply_psychology    import SimplyPsychologyScraper

log = logging.getLogger("run_db2")

SCRAPERS = [
    ("Therapist Aid",       TherapistAidScraper),
    ("GetSelfHelp",         GetSelfHelpScraper),
    ("Anxiety Canada",      AnxietyCanadaScraper),
    ("ACT Mindfully",       ACTMindfullycraper),
    ("Self-Compassion.org", SelfCompassionScraper),
    ("Positive Psychology", PositivePsychologyScraper),
    ("DBT Self Help",       DBTSelfHelpScraper),
    ("NHS IAPT",            IAPTScraper),
    ("Simply Psychology",   SimplyPsychologyScraper),
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
    print("DB2 SCRAPING SUMMARY")
    print("=" * 60)
    total_records = 0
    for name, count in totals.items():
        print(f"  {name:<24} {count:>5} records")
        total_records += count
    print("-" * 60)
    print(f"  {'TOTAL':<24} {total_records:>5} records")
    print("=" * 60)
    print(f"\nRaw data saved to: data/raw/db2_therapy/")


if __name__ == "__main__":
    main()

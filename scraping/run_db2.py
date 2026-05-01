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

SKIPPED — network blocked (connection timeout from this host, no workaround):
    CCI WA        (cci.health.wa.gov.au — TCP timeout on all attempts)
    CCI Therapy   (same domain, same issue)

SKIPPED — WAF-blocked / site closed — JSON files zeroed, data was binary garbage:
    Therapist Aid, Self-Compassion.org, Positive Psychology, Simply Psychology
    Anxiety Canada (site shut down April 2025)
    (Mind UK was Cloudflare-blocked but is now handled via cloudscraper)

ACTIVE — HTML / __NEXT_DATA__ confirmed working:
    GetSelfHelp, NHS Therapy, Mental Health Foundation, CAMH,
    Beyond Blue (migrated to Next.js; now parsed via __NEXT_DATA__ JSON),
    DBT Self Help (blog scraper confirmed 38 articles accessible)

To re-enable skipped sources, uncomment their entries in SCRAPERS below.
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# --- Active ---
from db2_therapy.cci_wa             import CCIWAScraper
from db2_therapy.compassionate_mind import CompassionateMindscraper
from db2_therapy.getselfhelp                       import GetSelfHelpScraper
from db2_therapy.nhs_therapy                       import NHSTherapyScraper
from db2_therapy.mental_health_foundation_therapy  import MHFTherapyScraper
from db2_therapy.camh_therapy                      import CAMHTherapyScraper
from db2_therapy.beyond_blue_therapy               import BeyondBlueTherapyScraper
from db2_therapy.dbt_selfhelp                      import DBTSelfHelpScraper
from db2_therapy.helpguide                         import HelpGuideScraper
from db2_therapy.mind_uk_therapy                   import MindUKTherapyScraper

# --- Skipped: already have good data in DB ---
# from db2_therapy.anxiety_canada    import AnxietyCanadaScraper
# from db2_therapy.act_mindfully     import ACTMindfullycraper
# from db2_therapy.iapt              import IAPTScraper

# --- Skipped: network blocked (TCP timeout on cci.health.wa.gov.au) ---
# from db2_therapy.cci_wa       import CCIWAScraper
# from db2_therapy.cci_therapy  import CCITherapyScraper

# --- Skipped: WAF-blocked ---
# from db2_therapy.therapist_aid       import TherapistAidScraper
# from db2_therapy.self_compassion     import SelfCompassionScraper
# from db2_therapy.positive_psychology import PositivePsychologyScraper
# from db2_therapy.simply_psychology   import SimplyPsychologyScraper

log = logging.getLogger("run_db2")

SCRAPERS = [
    # New source — gov.au, no bot protection
    ("CCI WA",               CCIWAScraper),
    # CFT publications 2023 — bibliography + abstracts
    ("Compassionate Mind",   CompassionateMindscraper),
    ("GetSelfHelp",              GetSelfHelpScraper),
    ("NHS Therapy",              NHSTherapyScraper),
    ("Mental Health Foundation", MHFTherapyScraper),
    ("CAMH",                     CAMHTherapyScraper),
    ("Beyond Blue",              BeyondBlueTherapyScraper),
    ("DBT Self Help",            DBTSelfHelpScraper),
    ("HelpGuide",                HelpGuideScraper),
    ("Mind UK",                  MindUKTherapyScraper),
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

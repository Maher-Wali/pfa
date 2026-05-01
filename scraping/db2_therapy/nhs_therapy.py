"""
Scraper: NHS — Therapy Technique Pages (DB2)
URL   : https://www.nhs.uk
License: Open Government Licence v3.0

Targets NHS treatment/therapy technique pages, distinct from the clinical
condition pages scraped in db1_clinical/nhs.py. Pages share the same
nhsuk-* CSS class structure, so the same boilerplate selectors apply.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.nhs.uk"

# (technique_name, url_path, modality, target_conditions)
TARGETS = [
    # /tests-and-treatments/ — confirmed from scraper2 seeds
    ("Cognitive Behavioural Therapy (CBT)",
     "/tests-and-treatments/cognitive-behavioural-therapy-cbt/",
     "CBT", ["depression", "anxiety", "OCD", "PTSD", "phobias"]),

    ("Talking Therapies Overview",
     "/tests-and-treatments/talking-therapies/",
     "CBT", ["depression", "anxiety"]),

    # /mental-health/talking-therapies-medicine-treatments/ section
    ("Types of Talking Therapies",
     "/mental-health/talking-therapies-medicine-treatments/talking-therapies-and-counselling/types-of-talking-therapies/",
     "CBT", ["depression", "anxiety"]),

    ("CBT — Overview",
     "/mental-health/talking-therapies-medicine-treatments/talking-therapies-and-counselling/cognitive-behavioural-therapy-cbt/overview/",
     "CBT", ["depression", "anxiety", "OCD", "PTSD"]),

    ("CBT — How It Works",
     "/mental-health/talking-therapies-medicine-treatments/talking-therapies-and-counselling/cognitive-behavioural-therapy-cbt/how-it-works/",
     "CBT", ["depression", "anxiety", "OCD", "PTSD"]),

    ("Counselling",
     "/mental-health/talking-therapies-medicine-treatments/talking-therapies-and-counselling/counselling/",
     "CBT", ["depression", "anxiety", "grief"]),

    ("EMDR",
     "/mental-health/talking-therapies-medicine-treatments/talking-therapies-and-counselling/eye-movement-desensitisation-and-reprocessing-emdr/",
     "EMDR", ["PTSD", "trauma"]),

    ("Interpersonal Therapy (IPT)",
     "/mental-health/talking-therapies-medicine-treatments/talking-therapies-and-counselling/interpersonal-therapy-ipt/",
     "interpersonal", ["depression"]),

    ("Dialectical Behaviour Therapy (DBT)",
     "/mental-health/talking-therapies-medicine-treatments/talking-therapies-and-counselling/dialectical-behaviour-therapy-dbt/",
     "DBT", ["BPD", "emotional dysregulation"]),

    ("Psychodynamic Psychotherapy",
     "/mental-health/talking-therapies-medicine-treatments/talking-therapies-and-counselling/psychodynamic-psychotherapy/",
     "psychodynamic", ["depression", "anxiety"]),

    ("Mindfulness",
     "/mental-health/self-help/tips-and-support/mindfulness/",
     "MBSR", ["depression", "anxiety", "stress"]),

    ("Raising Low Self-Esteem",
     "/mental-health/self-help/tips-and-support/raise-low-self-esteem/",
     "CBT", ["low self-esteem", "depression", "social anxiety"]),

    ("Coping with Depression — Self-Help",
     "/mental-health/self-help/tips-and-support/cope-with-depression/",
     "behavioural activation", ["depression"]),

    ("Understanding Stress",
     "/mental-health/feelings-symptoms-behaviours/feelings-and-symptoms/stress/",
     "CBT", ["stress", "anxiety", "burnout"]),
]

# Same boilerplate selectors as db1_clinical/nhs.py — pages share nhsuk-* structure
BOILERPLATE_SELECTORS = [
    "nav",
    ".nhsuk-breadcrumb",
    "footer",
    ".nhsuk-pagination",
    ".nhsuk-care-card",
    ".nhsuk-warning-callout",
    ".nhsuk-inset-text",
    "script",
    "style",
    "noscript",
]


class NHSTherapyScraper(BaseScraper):
    def __init__(self):
        super().__init__("nhs_therapy", "db2_therapy")

    def run(self) -> list:
        records = []
        for technique_name, path, modality, conditions in TARGETS:
            url = BASE + path
            self.log.info("Scraping: %s", technique_name)
            soup = self.get(url)
            if soup is None:
                continue

            h1 = soup.find("h1")
            if h1 and "page not found" in h1.get_text().lower():
                self.log.warning("  Soft 404: %s", url)
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)

            content_node = None
            for sel in ["article", "main", "#maincontent", "div.nhsuk-main-wrapper"]:
                content_node = soup.select_one(sel)
                if content_node:
                    break

            if content_node is None:
                self.log.warning("  No content node: %s", url)
                continue

            content = self.clean(content_node.get_text(separator=" "))
            if not content or len(content.split()) < 40:
                self.log.info("  -> too short, skipping")
                continue

            records.append({
                "technique_name":    technique_name,
                "aliases":           [],
                "modality":          modality,
                "target_conditions": conditions,
                "target_problem":    None,
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       content,
                "source":            "NHS",
                "source_url":        url,
                "last_scraped":      self.today(),
            })
            self.log.info("  -> saved [%s]", modality)

        self.save(records, "nhs_therapy.json")
        return records


if __name__ == "__main__":
    NHSTherapyScraper().run()

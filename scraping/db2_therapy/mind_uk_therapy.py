"""
Scraper: Mind UK — Therapy Techniques & Everyday Living Tips (DB2)
URL   : https://www.mind.org.uk
License: Mind (UK charity) — non-commercial educational use.

Mind UK is behind Cloudflare JS challenge. Uses cloudscraper to bypass it.
Content is in div.umb-grid#main (Umbraco CMS). All other scrapers use the
BaseScraper requests session; this one swaps it for a cloudscraper session.
"""
import sys
import time
from pathlib import Path

import cloudscraper
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.mind.org.uk"

# (technique_name, url_path, modality, target_conditions)
TARGETS = [
    # --- Therapy types ---
    ("Talking Therapy and Counselling — Overview",
     "/information-support/drugs-and-treatments/talking-therapy-and-counselling/",
     "CBT", ["depression", "anxiety", "PTSD", "OCD"]),

    ("Cognitive Behavioural Therapy (CBT)",
     "/information-support/drugs-and-treatments/talking-therapy-and-counselling/cognitive-behavioural-therapy-cbt/",
     "CBT", ["depression", "anxiety", "OCD", "PTSD", "phobias"]),

    ("Dialectical Behaviour Therapy (DBT)",
     "/information-support/drugs-and-treatments/talking-therapy-and-counselling/dialectical-behaviour-therapy-dbt/",
     "DBT", ["BPD", "emotional dysregulation", "self-harm"]),

    ("Arts and Creative Therapies",
     "/information-support/drugs-and-treatments/talking-therapy-and-counselling/arts-and-creative-therapies/",
     "arts therapy", ["depression", "anxiety", "trauma", "PTSD"]),

    ("Ecotherapy",
     "/information-support/drugs-and-treatments/talking-therapy-and-counselling/ecotherapy/",
     "ecotherapy", ["depression", "anxiety", "stress"]),

    # Mindfulness sub-pages (overview is too short)
    ("Mindfulness — About",
     "/information-support/drugs-and-treatments/mindfulness/about-mindfulness/",
     "MBSR", ["depression", "anxiety", "stress"]),

    ("Mindfulness Exercises and Tips",
     "/information-support/drugs-and-treatments/mindfulness/mindfulness-exercises-and-tips/",
     "MBSR", ["depression", "anxiety", "stress"]),

    # --- Tips for everyday living ---
    ("Relaxation",
     "/information-support/tips-for-everyday-living/relaxation/",
     "relaxation", ["anxiety", "stress", "insomnia"]),

    ("Wellbeing",
     "/information-support/tips-for-everyday-living/wellbeing/",
     "positive psychology", ["depression", "anxiety", "stress"]),

    # Physical activity sub-pages (overview is too short)
    ("Physical Activity — How It Helps Mental Health",
     "/information-support/tips-for-everyday-living/physical-activity-exercise-and-mental-health/how-are-physical-activity-and-mental-health-connected/",
     "behavioural activation", ["depression", "anxiety", "stress"]),

    ("Physical Activity — Tips for Getting Active",
     "/information-support/tips-for-everyday-living/physical-activity-exercise-and-mental-health/tips-for-getting-physically-active/",
     "behavioural activation", ["depression", "anxiety", "stress"]),

    ("Loneliness",
     "/information-support/tips-for-everyday-living/loneliness/",
     "interpersonal", ["depression", "social anxiety", "loneliness"]),

    ("Food and Mental Health",
     "/information-support/tips-for-everyday-living/food-and-mental-health/",
     "behavioural activation", ["depression", "anxiety", "eating disorders"]),

    ("Nature and Mental Health",
     "/information-support/tips-for-everyday-living/nature-and-mental-health/",
     "ecotherapy", ["depression", "anxiety", "stress"]),

    ("Mentally Healthy at Work",
     "/information-support/tips-for-everyday-living/how-to-be-mentally-healthy-at-work/",
     "CBT", ["burnout", "stress", "anxiety", "depression"]),

    # Stress sub-pages (overview is too short)
    ("Stress — Managing and Building Resilience",
     "/information-support/types-of-mental-health-problems/stress/managing-stress-and-building-resilience/",
     "CBT", ["stress", "anxiety", "burnout"]),

    ("Stress — Treatment",
     "/information-support/types-of-mental-health-problems/stress/treatment-for-stress/",
     "CBT", ["stress", "anxiety"]),
]

BOILERPLATE_SELECTORS = [
    "header", "footer", ".header", ".footer", ".c-breadcrumb",
    ".c-feedback", ".c-survey", "script", "style", "noscript",
    ".site-navigation", ".container.nav", ".utility-container",
]


class MindUKTherapyScraper(BaseScraper):
    def __init__(self):
        super().__init__("mind_uk_therapy", "db2_therapy", delay_range=(2.0, 4.0))
        # Replace the plain requests session with a cloudscraper session
        self._cs = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )

    def run(self) -> list:
        records = []
        for technique_name, path, modality, conditions in TARGETS:
            url = BASE + path
            self.log.info("Page: %s", technique_name)
            content = self._fetch(url)
            if not content or len(content.split()) < 80:
                self.log.warning("  -> too short or failed: %s", url)
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
                "source":            "Mind UK",
                "source_url":        url,
                "last_scraped":      self.today(),
            })
            self.log.info("  -> %d words [%s]", len(content.split()), modality)

        self.save(records, "mind_uk_therapy.json")
        return records

    def _fetch(self, url: str) -> str:
        try:
            r = self._cs.get(url, timeout=25)
            r.raise_for_status()
            time.sleep(self.delay[0] + (self.delay[1] - self.delay[0]) * 0.5)
        except Exception as exc:
            self.log.warning("  Request failed: %s", exc)
            return ""

        soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "lxml")
        self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)

        # Primary content container: Umbraco grid div with id="main"
        node = soup.select_one("div#main, div.umb-grid")
        if node is None:
            node = soup.find("body")

        return self.clean(node.get_text(separator=" ")) if node else ""


if __name__ == "__main__":
    MindUKTherapyScraper().run()

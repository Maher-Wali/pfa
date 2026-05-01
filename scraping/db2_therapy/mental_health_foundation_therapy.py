"""
Scraper: Mental Health Foundation — Self-Help & Technique Pages (DB2)
URL   : https://www.mentalhealth.org.uk
License: Standard charity website terms — non-commercial educational use.

Targets MHF's practical self-help and technique pages (sleep, mindfulness,
coping strategies) rather than the clinical condition overview pages scraped
in db1_clinical/mental_health_foundation.py. Uses the same boilerplate
stripping and section extraction since pages share the same site structure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text

BASE = "https://www.mentalhealth.org.uk"

# (technique_name, url_path, modality, target_conditions)
TARGETS = [
    # Dedicated self-help guide (not on A-Z — richer step-by-step content)
    ("Sleep Hygiene",
     "/how-sleep-better",
     "behavioral", ["insomnia", "sleep problems", "depression", "anxiety"]),

    # Therapy technique A-Z topics
    ("Cognitive Behavioural Therapy (CBT)",
     "/explore-mental-health/a-z-topics/cognitive-behavioural-therapy-cbt",
     "CBT", ["depression", "anxiety", "OCD", "PTSD"]),

    ("Mindfulness",
     "/explore-mental-health/a-z-topics/mindfulness",
     "MBSR", ["depression", "anxiety", "stress"]),

    ("Talking Therapies",
     "/explore-mental-health/a-z-topics/talking-therapies",
     "CBT", ["depression", "anxiety"]),

    # Self-help / behavioural technique topics
    ("Physical Activity and Mental Health",
     "/explore-mental-health/a-z-topics/physical-activity-and-mental-health",
     "behavioral", ["depression", "anxiety", "stress"]),

    ("Sleep and Mental Health",
     "/explore-mental-health/a-z-topics/sleep-and-mental-health",
     "behavioral", ["insomnia", "depression", "anxiety"]),

    ("Diet and Mental Health",
     "/explore-mental-health/a-z-topics/diet-and-mental-health",
     "behavioral", ["depression", "anxiety"]),

    ("Nature and Mental Health",
     "/explore-mental-health/a-z-topics/nature-and-mental-health",
     "behavioral", ["depression", "anxiety", "stress"]),

    ("Stress",
     "/explore-mental-health/a-z-topics/stress",
     "CBT", ["stress", "anxiety"]),

    ("Recovery",
     "/explore-mental-health/a-z-topics/recovery",
     "CBT", ["depression", "anxiety"]),

    ("Self-Management of Mental Health",
     "/explore-mental-health/a-z-topics/self-management-mental-ill-health",
     "CBT", ["depression", "anxiety"]),

    ("Kindness",
     "/explore-mental-health/a-z-topics/kindness",
     "PPT", []),

    ("Loneliness",
     "/explore-mental-health/a-z-topics/loneliness",
     "interpersonal", ["depression", "social anxiety"]),

    # Awareness week articles — practical coping content
    ("Coping with Anxiety",
     "/our-work/public-engagement/mental-health-awareness-week/what-can-we-do-cope-feelings-anxiety",
     "CBT", ["anxiety", "worry"]),

    ("Taking Action for Good Mental Health",
     "/our-work/public-engagement/mental-health-awareness-week/take-action-good-mental-health",
     "CBT", []),
]

# PDF: plain-language self-help guide — confirmed URL from scraper2
PDF_TARGETS = [
    ("Managing Fear and Anxiety",
     "https://www.mentalhealth.org.uk/sites/default/files/2025-02/MHF%20How%20to%20manage%20fear%20and%20anxiety%20SINGLE%20PAGES.pdf",
     "CBT", ["anxiety", "fear", "worry"]),
]

# Same as db1_clinical/mental_health_foundation.py
BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
    ".newsletter", ".donate", ".social-share",
]


class MHFTherapyScraper(BaseScraper):
    def __init__(self):
        super().__init__("mental_health_foundation_therapy", "db2_therapy")

    def run(self) -> list:
        records = []
        records.extend(self._scrape_html())
        records.extend(self._scrape_pdfs())
        self.save(records, "mental_health_foundation_therapy.json")
        return records

    def _scrape_html(self) -> list:
        records = []
        for technique_name, path, modality, conditions in TARGETS:
            url = BASE + path
            self.log.info("Page: %s", technique_name)
            soup = self.get(url)
            if soup is None:
                continue

            h1 = soup.find("h1")
            if h1 and "not found" in h1.get_text().lower():
                self.log.warning("  404: %s", url)
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            content = self._extract_content(soup)
            if not content or len(content.split()) < 40:
                self.log.info("  -> too short, skipping")
                continue

            records.append(self._make_record(technique_name, modality, conditions, content, url))
            self.log.info("  -> saved [%s]", modality)

        return records

    def _scrape_pdfs(self) -> list:
        records = []
        for technique_name, url, modality, conditions in PDF_TARGETS:
            self.log.info("PDF: %s", technique_name)
            raw = self.download_bytes(url, referer=BASE)
            if raw is None:
                self.log.warning("  Failed to download: %s", url)
                continue
            text = extract_text(raw)
            if not text or len(text.split()) < 40:
                self.log.warning("  No usable text: %s", url)
                continue
            records.append(self._make_record(technique_name, modality, conditions, self.clean(text), url))
            self.log.info("  -> saved PDF [%s]", modality)

        return records

    def _extract_content(self, soup) -> str:
        # Same selector priority as db1 mental_health_foundation.py
        main = soup.select_one("main, article, .page-content, #content")
        if main is None:
            main = soup.find("body") or soup
        parts = []
        for el in main.find_all(["h2", "h3", "p", "ul", "ol"]):
            chunk = el.get_text(separator=" ", strip=True)
            if chunk:
                parts.append(chunk)
        return self.clean(" ".join(parts))

    def _make_record(self, technique_name, modality, conditions, content, url) -> dict:
        return {
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
            "source":            "Mental Health Foundation",
            "source_url":        url,
            "last_scraped":      self.today(),
        }


if __name__ == "__main__":
    MHFTherapyScraper().run()

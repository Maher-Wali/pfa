"""
Scraper: Better Health Channel — Victorian Government (Australia)
URL   : https://www.betterhealth.vic.gov.au
License: Victorian Government — freely accessible, educational use.

Static HTML, no bot protection. Well-structured condition pages with
clear sections (summary, symptoms, causes, treatment, self-help).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.betterhealth.vic.gov.au"

# (condition_name, url_path, icd11_code)
TARGETS = [
    ("Depression",
     "/health/conditionsandtreatments/depression",                           "6A70"),
    ("Anxiety",
     "/health/conditionsandtreatments/anxiety",                              "6B0Z"),
    ("Panic Attacks",
     "/health/conditionsandtreatments/panic-attacks-and-panic-disorder",     "6B01"),
    ("Phobias",
     "/health/conditionsandtreatments/phobias",                              "6B03"),
    ("OCD",
     "/health/conditionsandtreatments/obsessive-compulsive-disorder-ocd",    "6B20"),
    ("PTSD",
     "/health/conditionsandtreatments/post-traumatic-stress-disorder-ptsd",  "6B40"),
    ("Bipolar Disorder",
     "/health/conditionsandtreatments/bipolar-disorder",                     "6A60"),
    ("Schizophrenia",
     "/health/conditionsandtreatments/schizophrenia",                        "6A20"),
    ("Eating Disorders",
     "/health/conditionsandtreatments/eating-disorders",                     "6B8Z"),
    ("ADHD",
     "/health/conditionsandtreatments/attention-deficit-hyperactivity-disorder-adhd", "6A05"),
    ("Borderline Personality Disorder",
     "/health/conditionsandtreatments/borderline-personality-disorder",      "6D11"),
    ("Seasonal Affective Disorder",
     "/health/conditionsandtreatments/seasonal-affective-disorder-sad",      "6A70"),
    ("Self-Harm",
     "/health/conditionsandtreatments/self-harm",                            None),
    ("Stress",
     "/health/healthy-living/stress",                                        None),
    ("Grief",
     "/health/conditionsandtreatments/grief",                                None),
    ("Sleep Problems",
     "/health/conditionsandtreatments/sleep-problems",                       None),
    ("Postnatal Depression",
     "/health/conditionsandtreatments/postnatal-depression",                 "6A70"),
    ("Anger",
     "/health/healthy-living/anger",                                         None),
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "about", "overview"],
    "symptoms":          ["symptom", "sign"],
    "causes":            ["cause", "risk", "factor"],
    "diagnosis":         ["diagnos", "test"],
    "treatment":         ["treat", "therap", "medication", "help"],
    "self_help":         ["self-help", "self help", "coping", "manage", "tips"],
    "when_to_seek_help": ["seek help", "when to", "see a doctor"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
    ".related-articles", ".share", ".feedback",
]


class BetterHealthScraper(BaseScraper):
    def __init__(self):
        super().__init__("better_health", "db1_clinical")

    def run(self) -> list:
        records = []
        for condition_name, path, icd11 in TARGETS:
            url = BASE + path
            self.log.info("Page: %s", condition_name)
            soup = self.get(url)
            if soup is None:
                continue

            h1 = soup.find("h1")
            if h1 and "page not found" in h1.get_text().lower():
                self.log.warning("  404: %s", url)
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            sections = self._extract_sections(soup)

            for heading, content in sections.items():
                if not content or len(content.split()) < 30:
                    continue
                records.append({
                    "condition":    condition_name,
                    "aliases":      [],
                    "source":       "Better Health Channel",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

        self.log.info("Total: %d records", len(records))
        self.save(records, "better_health_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        main = soup.select_one("main, article, .page-content, #content, .content")
        if main is None:
            main = soup.find("body") or soup

        sections: dict = {}
        current_heading = "overview"
        current_chunks: list = []

        for el in main.find_all(["h2", "h3", "p", "ul", "ol"]):
            if el.name in ("h2", "h3"):
                text = el.get_text(strip=True)
                if text:
                    if current_chunks:
                        sections[current_heading] = self.clean(
                            " ".join(current_chunks)
                        )
                    current_heading = text.lower()
                    current_chunks = []
            else:
                chunk = el.get_text(separator=" ", strip=True)
                if chunk:
                    current_chunks.append(chunk)

        if current_chunks:
            sections[current_heading] = self.clean(" ".join(current_chunks))

        return sections

    def _classify_section(self, heading: str) -> str:
        h = heading.lower()
        for key, keywords in SECTION_KEYWORDS.items():
            if any(kw in h for kw in keywords):
                return key
        return "other"


if __name__ == "__main__":
    BetterHealthScraper().run()

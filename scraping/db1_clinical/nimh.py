"""
Scraper: NIMH — National Institute of Mental Health Health Topics
URL   : https://www.nimh.nih.gov/health/topics
License: US Federal Government — Public Domain
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.nimh.nih.gov"

# path → (condition display name, icd11_code)
TOPIC_PAGES = {
    "/health/topics/depression":                          ("Depression",                        "6A70"),
    "/health/topics/anxiety-disorders":                   ("Anxiety Disorders",                 "6B0Z"),
    "/health/topics/generalized-anxiety-disorder":        ("Generalised Anxiety Disorder",       "6B00"),
    "/health/topics/panic-disorder":                      ("Panic Disorder",                    "6B01"),
    "/health/topics/social-anxiety-disorder":             ("Social Anxiety Disorder",            "6B04"),
    "/health/topics/post-traumatic-stress-disorder-ptsd": ("PTSD",                              "6B40"),
    "/health/topics/obsessive-compulsive-disorder-ocd":   ("OCD",                               "6B20"),
    "/health/topics/bipolar-disorder":                    ("Bipolar Disorder",                  "6A60"),
    "/health/topics/schizophrenia":                       ("Schizophrenia",                     "6A20"),
    "/health/topics/eating-disorders":                    ("Eating Disorders",                  "6B8Z"),
    "/health/topics/attention-deficit-hyperactivity-disorder-adhd": ("ADHD",                   "6A05"),
    "/health/topics/autism-spectrum-disorder-asd":        ("Autism Spectrum Disorder",          "6A02"),
    "/health/topics/borderline-personality-disorder":     ("Borderline Personality Disorder",   "6D11"),
    "/health/topics/seasonal-affective-disorder":         ("Seasonal Affective Disorder",       "6A70"),
    "/health/topics/postpartum-depression":               ("Postpartum Depression",             "6A70"),
    "/health/topics/suicide-prevention":                  ("Suicide Prevention",               None),
    "/health/topics/self-harm":                           ("Self-Harm",                         None),
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".breadcrumb", ".utility-nav",
    ".page-tools", "script", "style", "#header", "#nav", "#footer",
    ".related-links", ".social-share",
]

SECTION_KEYWORDS = {
    "overview":          ["overview", "what is", "about", "introduction", "basics"],
    "symptoms":          ["sign", "symptom", "how does"],
    "causes":            ["cause", "risk factor"],
    "diagnosis":         ["diagnos"],
    "treatment":         ["treat", "therap", "medication", "help"],
    "self_help":         ["self-help", "coping", "what can i do", "tips"],
    "when_to_seek_help": ["seek", "where can i", "talk to", "find help"],
    "living_with":       ["living", "manage", "day-to-day"],
}


class NIMHScraper(BaseScraper):
    def __init__(self):
        super().__init__("nimh", "db1_clinical")

    def run(self) -> list:
        records = []
        for path, (condition, icd11) in TOPIC_PAGES.items():
            url = BASE + path
            self.log.info("Topic: %s", condition)
            soup = self.get(url)
            if soup is None:
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            sections = self._extract_sections(soup)

            for heading, content in sections.items():
                if not content or len(content) < 80:
                    continue
                records.append({
                    "condition":    condition,
                    "aliases":      [],
                    "source":       "NIMH",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })
            self.log.info("  %d sections extracted", len(sections))

        self.save(records, "nimh_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        """
        NIMH topic pages divide content with h2/h3 headings inside a main
        content area. We walk those elements and split on heading boundaries.
        """
        main = soup.select_one(
            "main, #main-content, .main-content, "
            "[class*='main'], article, #content"
        )
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
    NIMHScraper().run()

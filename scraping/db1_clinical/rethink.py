"""
Scraper: Rethink Mental Illness (UK)
URL   : https://www.rethink.org/advice-and-information/
License: Charity website — non-commercial educational use.

Rethink publishes practical, peer-informed condition guides written for
people living with severe mental illness and their carers. Their register
is distinct from NHS clinical language — more lived-experience focused.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.rethink.org"

# (condition_name, url_path, icd11_code)
TARGETS = [
    ("Schizophrenia",
     "/advice-and-information/about-mental-illness/mental-health-conditions/schizophrenia/", "6A20"),
    ("Bipolar Disorder",
     "/advice-and-information/about-mental-illness/mental-health-conditions/bipolar-disorder/", "6A60"),
    ("Depression",
     "/advice-and-information/about-mental-illness/mental-health-conditions/depression/", "6A70"),
    ("OCD",
     "/advice-and-information/about-mental-illness/mental-health-conditions/ocd/", "6B20"),
    ("PTSD",
     "/advice-and-information/about-mental-illness/mental-health-conditions/post-traumatic-stress-disorder-ptsd/", "6B40"),
    ("Borderline Personality Disorder",
     "/advice-and-information/about-mental-illness/mental-health-conditions/borderline-personality-disorder-bpd/", "6D11"),
    ("Schizoaffective Disorder",
     "/advice-and-information/about-mental-illness/mental-health-conditions/schizoaffective-disorder/", "6A21"),
    ("Anxiety",
     "/advice-and-information/about-mental-illness/mental-health-conditions/anxiety-disorders/", "6B0Z"),
    ("Psychosis",
     "/advice-and-information/about-mental-illness/mental-health-conditions/psychosis/", "6A2Z"),
    ("Eating Disorders",
     "/advice-and-information/about-mental-illness/mental-health-conditions/eating-disorders/", "6B8Z"),

    # Commonly asked questions section — practical Q&A format
    ("Mental Health — Commonly Asked Questions",
     "/news-and-stories/commonly-asked-mental-health-questions/", None),
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "about", "overview", "introduction"],
    "symptoms":          ["symptom", "sign", "experience", "how does it feel"],
    "causes":            ["cause", "risk", "why"],
    "diagnosis":         ["diagnos", "assessment", "getting a"],
    "treatment":         ["treat", "therap", "medication", "recovery", "help"],
    "self_help":         ["self-help", "coping", "self-management", "what can i"],
    "living_with":       ["living with", "day to day", "manage", "carer"],
    "when_to_seek_help": ["seek help", "getting help", "support", "crisis"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumbs", "script", "style", ".sidebar",
    ".related-content", ".social-share", ".donation-cta",
    ".cookie-banner", ".newsletter-signup",
]


class RethinkScraper(BaseScraper):
    def __init__(self):
        super().__init__("rethink", "db1_clinical")

    def run(self) -> list:
        records = []
        for condition_name, path, icd11 in TARGETS:
            url = BASE + path
            self.log.info("Page: %s", condition_name)
            soup = self.get(url)
            if soup is None:
                continue

            h1 = soup.find("h1")
            if h1 and any(p in h1.get_text().lower() for p in ["not found", "404"]):
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
                    "source":       "Rethink Mental Illness",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

        self.log.info("Total: %d records", len(records))
        self.save(records, "rethink_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        main = soup.select_one(
            "main, article, .page-content, .entry-content, #content, .content-area"
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
    RethinkScraper().run()

"""
Scraper: Beyond Blue (Australia)
URL   : https://www.beyondblue.org.au
License: Australian government-backed charity — content freely accessible,
         non-commercial educational use.

Beyond Blue has excellent plain-language condition guides and self-help
articles. The writing register is close to what we want for the LLM's
clinical knowledge base — empathetic, accessible, evidence-based.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.beyondblue.org.au"

# (condition_name, url_path, icd11_code)
TARGETS = [
    # Conditions
    ("Depression",
     "/the-facts/depression", "6A70"),
    ("Anxiety Disorders",
     "/the-facts/anxiety", "6B0Z"),
    ("OCD",
     "/the-facts/anxiety/types-of-anxiety/ocd", "6B20"),
    ("PTSD",
     "/the-facts/anxiety/types-of-anxiety/ptsd", "6B40"),
    ("Panic Disorder",
     "/the-facts/anxiety/types-of-anxiety/panic-disorder", "6B01"),
    ("Social Anxiety",
     "/the-facts/anxiety/types-of-anxiety/social-anxiety", "6B04"),
    ("Phobias",
     "/the-facts/anxiety/types-of-anxiety/phobias", "6B03"),
    ("Bipolar Disorder",
     "/the-facts/bipolar-disorder", "6A60"),
    ("Eating Disorders",
     "/the-facts/eating-disorders", "6B8Z"),
    ("Psychosis",
     "/the-facts/psychosis", "6A2Z"),
    ("Postnatal Depression",
     "/the-facts/postnatal-depression", "6A70"),
    ("Grief and Loss",
     "/the-facts/grief-and-loss", None),
    ("Suicide — Understanding and Prevention",
     "/the-facts/suicide-prevention", None),
    ("Anger",
     "/the-facts/anger", None),

    # Self-help and coping articles
    ("Managing Depression — Self-Help",
     "/get-support/managing-depression-and-anxiety", "6A70"),
    ("Managing Anxiety — Self-Help",
     "/get-support/managing-depression-and-anxiety/managing-anxiety", "6B0Z"),
    ("Exercise and Mental Health",
     "/the-facts/physical-health-and-wellbeing", None),
    ("Sleep and Mental Health",
     "/the-facts/sleep-and-mental-health", None),
    ("Mindfulness",
     "/get-support/managing-depression-and-anxiety/mindfulness", None),
    ("Social Connections and Mental Health",
     "/the-facts/social-connections-and-mental-health", None),
    ("Loneliness",
     "/the-facts/loneliness", None),
    ("Stress",
     "/the-facts/stress", None),

    # Specific demographics
    ("Young People and Mental Health",
     "/the-facts/young-people", None),
    ("Men and Mental Health",
     "/the-facts/men-and-mental-health", None),
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "about", "overview", "key fact"],
    "symptoms":          ["sign", "symptom", "how does it feel"],
    "causes":            ["cause", "risk factor"],
    "treatment":         ["treat", "therap", "help", "support"],
    "self_help":         ["self-help", "coping", "what can i", "manage"],
    "when_to_seek_help": ["seek help", "when to", "getting help"],
    "living_with":       ["living", "day-to-day"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
    ".newsletter", ".donate-cta", ".social-share",
    ".emergency-help-widget",
]


class BeyondBlueScraper(BaseScraper):
    def __init__(self):
        super().__init__("beyond_blue", "db1_clinical")

    def run(self) -> list:
        records = []
        for condition_name, path, icd11 in TARGETS:
            url = BASE + path
            self.log.info("Page: %s", condition_name)
            soup = self.get(url)
            if soup is None:
                continue

            h1 = soup.find("h1")
            if h1 and "not found" in h1.get_text().lower():
                self.log.warning("  404: %s", url)
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            sections = self._extract_sections(soup)

            for heading, content in sections.items():
                if not content or len(content) < 80:
                    continue
                records.append({
                    "condition":    condition_name,
                    "aliases":      [],
                    "source":       "Beyond Blue",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

        self.log.info("Total: %d records", len(records))
        self.save(records, "beyond_blue_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        main = soup.select_one(
            "main, article, .page-content, .content-area, #content"
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
    BeyondBlueScraper().run()

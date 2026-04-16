"""
Scraper: Royal College of Psychiatrists — Patient Information Leaflets
URL   : https://www.rcpsych.ac.uk/mental-health
License: © Royal College of Psychiatrists — free for personal/educational use.

RC Psych publishes peer-reviewed plain-language patient leaflets covering
mental health conditions, treatments, and medications. UK clinical register —
complements NHS with more detailed disorder-specific information.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.rcpsych.ac.uk"

# (condition_name, url_path, icd11_code)
TARGETS = [
    ("Depression",
     "/mental-health/problems-disorders/depression",                         "6A70"),
    ("Anxiety, Panic and Phobias",
     "/mental-health/problems-disorders/anxiety-panic-and-phobias",          "6B0Z"),
    ("Generalised Anxiety Disorder",
     "/mental-health/problems-disorders/generalised-anxiety-disorder",       "6B00"),
    ("OCD",
     "/mental-health/problems-disorders/obsessive-compulsive-disorder",      "6B20"),
    ("PTSD",
     "/mental-health/problems-disorders/post-traumatic-stress-disorder-ptsd","6B40"),
    ("Bipolar Disorder",
     "/mental-health/problems-disorders/bipolar-disorder",                   "6A60"),
    ("Schizophrenia",
     "/mental-health/problems-disorders/schizophrenia",                      "6A20"),
    ("Eating Disorders",
     "/mental-health/problems-disorders/eating-disorders",                   "6B8Z"),
    ("Borderline Personality Disorder",
     "/mental-health/problems-disorders/borderline-personality-disorder-bpd","6D11"),
    ("Self-Harm",
     "/mental-health/problems-disorders/self-harm",                          None),
    ("ADHD in Adults",
     "/mental-health/problems-disorders/adhd-in-adults",                     "6A05"),
    ("Postnatal Depression",
     "/mental-health/problems-disorders/postnatal-depression",               "6A70"),
    ("Seasonal Affective Disorder",
     "/mental-health/problems-disorders/seasonal-affective-disorder",        "6A70"),
    ("Phobias",
     "/mental-health/problems-disorders/phobias",                            "6B03"),
    ("Social Anxiety",
     "/mental-health/problems-disorders/social-anxiety-disorder",            "6B04"),
    # Treatments
    ("Cognitive Behavioural Therapy",
     "/mental-health/treatments-and-wellbeing/cognitive-behavioural-therapy-cbt", None),
    ("Antidepressants",
     "/mental-health/treatments-and-wellbeing/antidepressants",              None),
    ("Mindfulness",
     "/mental-health/treatments-and-wellbeing/mindfulness",                  None),
    ("Talking Therapies",
     "/mental-health/treatments-and-wellbeing/talking-therapies",            None),
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "about", "overview", "introduction"],
    "symptoms":          ["symptom", "sign", "how does it feel", "experience"],
    "causes":            ["cause", "risk", "factor", "why"],
    "diagnosis":         ["diagnos", "assessed", "test"],
    "treatment":         ["treat", "therap", "medication", "recovery", "help"],
    "self_help":         ["self-help", "self help", "coping", "can i do", "yourself"],
    "when_to_seek_help": ["seek help", "when to", "getting help", "support"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
    ".related-content", ".social-share", ".feedback-widget",
    ".alert", ".cookie-banner",
]


class RCPsychScraper(BaseScraper):
    def __init__(self):
        super().__init__("rcpsych", "db1_clinical")

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
                    "source":       "Royal College of Psychiatrists",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

        self.log.info("Total: %d records", len(records))
        self.save(records, "rcpsych_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        main = soup.select_one(
            "main, article, .wysiwyg-content, .rich-text, "
            ".page-content, #content, .content-area"
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
    RCPsychScraper().run()

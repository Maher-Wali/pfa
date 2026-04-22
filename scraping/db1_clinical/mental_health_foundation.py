"""
Scraper: Mental Health Foundation (UK)
URL   : https://www.mentalhealth.org.uk
License: Standard charity website terms — non-commercial educational use.

MHF publishes well-written plain-language condition guides and thematic
articles (loneliness, stress, sleep, physical activity and mental health).
Their register is warmer and more accessible than NHS clinical pages.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text

BASE = "https://www.mentalhealth.org.uk"

# (condition_name, url_path, icd11_code)
TARGETS = [
    # Condition-specific pages
    ("Depression",
     "/explore-mental-health/a-z-topics/depression", "6A70"),
    ("Anxiety",
     "/explore-mental-health/a-z-topics/anxiety", "6B0Z"),
    ("Panic Attacks",
     "/explore-mental-health/a-z-topics/panic-attacks", "6B01"),
    ("Phobias",
     "/explore-mental-health/a-z-topics/phobias", "6B03"),
    ("OCD",
     "/explore-mental-health/a-z-topics/obsessive-compulsive-disorder-ocd", "6B20"),
    ("PTSD",
     "/explore-mental-health/a-z-topics/post-traumatic-stress-disorder-ptsd", "6B40"),
    ("Bipolar Disorder",
     "/explore-mental-health/a-z-topics/bipolar-disorder", "6A60"),
    ("Schizophrenia",
     "/explore-mental-health/a-z-topics/schizophrenia", "6A20"),
    ("Eating Disorders",
     "/explore-mental-health/a-z-topics/eating-disorders", "6B8Z"),
    ("Borderline Personality Disorder",
     "/explore-mental-health/a-z-topics/borderline-personality-disorder", "6D11"),
    ("Self-Harm",
     "/explore-mental-health/a-z-topics/self-harm", None),
    ("Suicide",
     "/explore-mental-health/a-z-topics/suicide", None),
    ("Postnatal Depression",
     "/explore-mental-health/a-z-topics/postnatal-depression", "6A70"),
    ("Seasonal Affective Disorder",
     "/explore-mental-health/a-z-topics/seasonal-affective-disorder-sad", "6A70"),
    ("Body Image",
     "/explore-mental-health/a-z-topics/body-image", None),
    ("Dementia",
     "/explore-mental-health/a-z-topics/dementia", None),
    ("ADHD",
     "/explore-mental-health/a-z-topics/attention-deficit-hyperactivity-disorder-adhd", "6A05"),
    ("Autism",
     "/explore-mental-health/a-z-topics/autism", "6A02"),
    ("Psychosis",
     "/explore-mental-health/a-z-topics/psychosis", "6A2Z"),

    # Thematic wellbeing articles
    ("Loneliness and Mental Health",
     "/explore-mental-health/a-z-topics/loneliness", None),
    ("Stress",
     "/explore-mental-health/a-z-topics/stress", None),
    ("Sleep and Mental Health",
     "/explore-mental-health/a-z-topics/sleep", None),
    ("Physical Activity and Mental Health",
     "/explore-mental-health/a-z-topics/physical-activity-and-mental-health", None),
    ("Relationships and Mental Health",
     "/explore-mental-health/a-z-topics/relationships", None),
    ("Work and Mental Health",
     "/explore-mental-health/a-z-topics/work-and-mental-health", None),
    ("Grief",
     "/explore-mental-health/a-z-topics/grief", None),
    ("Alcohol and Mental Health",
     "/explore-mental-health/a-z-topics/alcohol-and-mental-health", None),

    # Awareness week articles — substantive coping/clinical content
    ("Anxiety — Coping Strategies",
     "/our-work/public-engagement/mental-health-awareness-week/what-can-we-do-cope-feelings-anxiety", None),
    ("Take Action for Good Mental Health",
     "/our-work/public-engagement/mental-health-awareness-week/take-action-good-mental-health", None),
]

# Known MHF PDF guides — plain-language self-help content
PDF_TARGETS = [
    ("Managing Fear and Anxiety",
     "https://www.mentalhealth.org.uk/sites/default/files/2025-02/MHF%20How%20to%20manage%20fear%20and%20anxiety%20SINGLE%20PAGES.pdf",
     "Anxiety", "6B0Z"),
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "about", "overview"],
    "symptoms":          ["sign", "symptom"],
    "causes":            ["cause", "risk"],
    "treatment":         ["treat", "therap", "help"],
    "self_help":         ["self-help", "self help", "coping", "what can i do"],
    "when_to_seek_help": ["seek help", "support", "get help"],
    "living_with":       ["living", "manage"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
    ".newsletter", ".donate", ".social-share",
]


class MentalHealthFoundationScraper(BaseScraper):
    def __init__(self):
        super().__init__("mental_health_foundation", "db1_clinical")

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
                    "source":       "Mental Health Foundation",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

        records.extend(self._scrape_pdfs())

        self.log.info("Total: %d records", len(records))
        self.save(records, "mental_health_foundation_clinical.json")
        return records

    def _scrape_pdfs(self) -> list:
        records = []
        for title, url, condition, icd11 in PDF_TARGETS:
            self.log.info("PDF: %s", title)
            raw = self.download_bytes(url, referer=BASE)
            if raw is None:
                self.log.warning("  Failed to download: %s", url)
                continue
            text = extract_text(raw)
            if not text or len(text.split()) < 40:
                self.log.warning("  No usable text in: %s", url)
                continue
            records.append({
                "condition":    condition,
                "aliases":      [],
                "source":       "Mental Health Foundation",
                "source_url":   url,
                "section":      "self_help",
                "content":      self.clean(text),
                "icd11_code":   icd11,
                "last_scraped": self.today(),
            })
        self.log.info("PDFs: %d records", len(records))
        return records

    def _extract_sections(self, soup) -> dict:
        main = soup.select_one("main, article, .page-content, #content")
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
    MentalHealthFoundationScraper().run()

"""
Scraper: Cleveland Clinic — Health Library
URL   : https://my.clevelandclinic.org/health
License: Standard terms — non-commercial educational use.

Cleveland Clinic's health library pages are written by medical staff and
reviewed regularly. Good coverage of DSM/ICD conditions with symptoms,
causes, diagnosis and treatment sections in accessible language.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://my.clevelandclinic.org"

# (condition_name, url_path, icd11_code)
TARGETS = [
    ("Depression",
     "/health/diseases/9290-depression", "6A70"),
    ("Generalised Anxiety Disorder",
     "/health/diseases/9536-anxiety-disorders", "6B00"),
    ("Panic Disorder",
     "/health/diseases/4451-panic-disorder", "6B01"),
    ("Social Anxiety Disorder",
     "/health/diseases/17811-social-anxiety-disorder", "6B04"),
    ("Phobias",
     "/health/diseases/9830-phobias", "6B03"),
    ("OCD",
     "/health/diseases/9490-obsessive-compulsive-disorder-ocd", "6B20"),
    ("PTSD",
     "/health/diseases/9347-post-traumatic-stress-disorder-ptsd", "6B40"),
    ("Bipolar Disorder",
     "/health/diseases/9294-bipolar-disorder", "6A60"),
    ("Schizophrenia",
     "/health/diseases/4568-schizophrenia", "6A20"),
    ("Borderline Personality Disorder",
     "/health/diseases/9762-borderline-personality-disorder-bpd", "6D11"),
    ("Eating Disorders",
     "/health/diseases/9833-eating-disorders", "6B8Z"),
    ("Anorexia Nervosa",
     "/health/diseases/9794-anorexia-nervosa", "6B80"),
    ("Bulimia Nervosa",
     "/health/diseases/9795-bulimia-nervosa", "6B81"),
    ("ADHD",
     "/health/diseases/4784-attention-deficithyperactivity-disorder-adhd", "6A05"),
    ("Autism Spectrum Disorder",
     "/health/diseases/9518-autism", "6A02"),
    ("Seasonal Affective Disorder",
     "/health/diseases/9293-seasonal-affective-disorder", "6A70"),
    ("Health Anxiety",
     "/health/diseases/21156-health-anxiety", "6B23"),
    ("Insomnia",
     "/health/diseases/12119-insomnia", None),
    ("Suicide and Suicidal Ideation",
     "/health/diseases/9182-suicidal-ideation", None),
    ("Self-Harm",
     "/health/diseases/22521-non-suicidal-self-injury", None),
    ("Grief",
     "/health/diseases/17491-complicated-grief", None),
    ("Psychosis",
     "/health/diseases/9576-psychosis", "6A2Z"),
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "overview", "about", "definition"],
    "symptoms":          ["symptom", "sign", "how does it feel", "what are the"],
    "causes":            ["cause", "risk factor", "risk", "why"],
    "diagnosis":         ["diagnos", "test", "evaluat", "how is it"],
    "treatment":         ["treat", "therap", "medication", "management", "how is it managed"],
    "self_help":         ["self-help", "coping", "outlook", "self-care", "what can i"],
    "living_with":       ["living with", "prognosis", "outlook", "prevention"],
    "when_to_seek_help": ["when to call", "when should", "seek help", "see a doctor"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
    ".related-articles", ".social-share", ".feedback",
    ".ad-slot", ".cookie-notice", "[data-component='RelatedContent']",
]


class ClevelandClinicScraper(BaseScraper):
    def __init__(self):
        super().__init__("cleveland_clinic", "db1_clinical")

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
                    "source":       "Cleveland Clinic",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

        self.log.info("Total: %d records", len(records))
        self.save(records, "cleveland_clinic_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        # Cleveland Clinic wraps each accordion/section in elements with
        # data attributes; fall back to standard heading-walk if not found.
        main = soup.select_one(
            "main, article, .health-article, #main-content, "
            "[class*='Article'], [class*='article-body']"
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
                if chunk and len(chunk) > 20:
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
    ClevelandClinicScraper().run()

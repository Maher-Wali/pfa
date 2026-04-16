"""
Scraper: NICE — Information for the Public pages
URL   : https://www.nice.org.uk/guidance/{ID}/informationforpublic
License: Open Government Licence v3.0
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.nice.org.uk"

# guideline_id → (condition display name, icd11_code)
GUIDELINES = {
    "CG90":   ("Depression",                         "6A70"),
    "CG113":  ("Generalised Anxiety Disorder",        "6B00"),
    "NG116":  ("PTSD",                               "6B40"),
    "CG26":   ("PTSD (older guideline)",             "6B40"),
    "CG31":   ("OCD",                               "6B20"),
    "CG178":  ("Psychosis and Schizophrenia",        "6A20"),
    "NG53":   ("Eating Disorders",                   "6B8Z"),
    "CG9":    ("Eating Disorders (older guideline)", "6B8Z"),
    "CG38":   ("Bipolar Disorder",                   "6A60"),
    "CG133":  ("Autism in Adults",                   "6A02"),
    "NG87":   ("ADHD",                              "6A05"),
    "CG159":  ("Social Anxiety Disorder",            "6B04"),
    "CG123":  ("Common Mental Health Problems",      None),
    "CG192":  ("Perinatal Mental Health",            None),
    "NG185":  ("Depression in Adults",               "6A70"),
}

# NICE uses two different URL patterns for their public info pages
SECTION_URL_PATTERNS = [
    "{base}/guidance/{gid}/informationforpublic",
    "{base}/guidance/{gid}/chapter/information-for-the-public",
]

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".breadcrumb", ".feedback-panel",
    ".in-page-nav", "script", "style", "#header", "#footer",
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "about", "overview", "introduction"],
    "symptoms":          ["sign", "symptom", "how does it feel", "experience"],
    "causes":            ["cause", "risk factor", "why"],
    "diagnosis":         ["diagnos", "assessment", "how is it identified"],
    "treatment":         ["treat", "therap", "medication", "care", "intervention"],
    "self_help":         ["self", "help yourself", "coping", "what you can do"],
    "living_with":       ["living", "day-to-day", "manage"],
    "when_to_seek_help": ["seek help", "when to", "support", "contact"],
}


class NICEScraper(BaseScraper):
    def __init__(self):
        super().__init__("nice", "db1_clinical")

    def run(self) -> list:
        records = []
        for gid, (condition, icd11) in GUIDELINES.items():
            self.log.info("Guideline: %s — %s", gid, condition)
            soup = self._fetch_guideline(gid)
            if soup is None:
                self.log.warning("  Could not fetch %s — skipping", gid)
                continue

            sections = self._extract_sections(soup)
            for heading, content in sections.items():
                if not content or len(content) < 80:
                    continue
                records.append({
                    "condition":    condition,
                    "aliases":      [],
                    "source":       "NICE",
                    "source_url":   self._resolved_url(gid),
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })
            self.log.info("  %d sections extracted", len(sections))

        self.save(records, "nice_clinical.json")
        return records

    def _fetch_guideline(self, gid: str):
        """Try both URL patterns; return the first that succeeds."""
        for pattern in SECTION_URL_PATTERNS:
            url = pattern.format(base=BASE, gid=gid)
            soup = self.get(url)
            if soup is None:
                continue
            # Check for NICE's 404 page indicator
            if soup.find("h1") and "page not found" in soup.find("h1").get_text().lower():
                continue
            return soup
        return None

    def _resolved_url(self, gid: str) -> str:
        return f"{BASE}/guidance/{gid}/informationforpublic"

    def _extract_sections(self, soup) -> dict:
        """
        NICE info-for-public pages use h2/h3 headings to divide the content.
        We split on those headings and collect the text that follows each one.
        """
        self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)

        main = soup.select_one("main, #main-content, .main-content, article")
        if main is None:
            main = soup

        sections: dict = {}
        current_heading = "overview"
        current_chunks: list = []

        for el in main.find_all(["h1", "h2", "h3", "p", "ul", "ol", "li"]):
            if el.name in ("h1", "h2", "h3"):
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
        for section_key, keywords in SECTION_KEYWORDS.items():
            if any(kw in h for kw in keywords):
                return section_key
        return "other"


if __name__ == "__main__":
    NICEScraper().run()

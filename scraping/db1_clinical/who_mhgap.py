"""
Scraper: WHO mhGAP — Mental Health Gap Action Programme
URL   : https://www.who.int/teams/mental-health-and-substance-use/
        treatment-care/mental-health-gap-action-programme
License: Creative Commons Attribution-NonCommercial-ShareAlike 3.0
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.who.int"

# WHO mhGAP web pages — direct condition/topic pages under who.int
# These are the web-accessible versions of the mhGAP Intervention Guide content
PAGES = {
    "/news-room/fact-sheets/detail/depression": (
        "Depression", "6A70"
    ),
    "/news-room/fact-sheets/detail/anxiety-disorders": (
        "Anxiety Disorders", "6B0Z"
    ),
    "/news-room/fact-sheets/detail/mental-disorders": (
        "Mental Disorders Overview", None
    ),
    "/news-room/fact-sheets/detail/schizophrenia": (
        "Schizophrenia", "6A20"
    ),
    "/news-room/fact-sheets/detail/bipolar-disorder": (
        "Bipolar Disorder", "6A60"
    ),
    "/news-room/fact-sheets/detail/eating-disorders": (
        "Eating Disorders", "6B8Z"
    ),
    "/news-room/fact-sheets/detail/autism-spectrum-disorders": (
        "Autism Spectrum Disorder", "6A02"
    ),
    "/news-room/fact-sheets/detail/attention-deficit-hyperactivity-disorder-(adhd)-in-children": (
        "ADHD", "6A05"
    ),
    "/news-room/fact-sheets/detail/dementia": (
        "Dementia", None
    ),
    "/news-room/fact-sheets/detail/suicide": (
        "Suicide Prevention", None
    ),
    "/news-room/fact-sheets/detail/post-traumatic-stress-disorder-(ptsd)": (
        "PTSD", "6B40"
    ),
    "/news-room/fact-sheets/detail/obsessive-compulsive-disorder": (
        "OCD", "6B20"
    ),
}

# mhGAP programme overview pages
PROGRAMME_PAGES = {
    "/teams/mental-health-and-substance-use/treatment-care/"
    "mental-health-gap-action-programme/mhgap-intervention-guide": (
        "mhGAP Overview", None
    ),
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".sf-header", ".sf-footer",
    ".breadcrumb", ".share-this", "script", "style",
    ".contextual-links", ".social-media-links",
]

SECTION_KEYWORDS = {
    "overview":          ["overview", "what is", "key fact", "introduction", "about"],
    "symptoms":          ["sign", "symptom", "manifestation"],
    "causes":            ["cause", "risk factor", "risk group"],
    "diagnosis":         ["diagnos", "assessment"],
    "treatment":         ["treat", "therap", "management", "intervention"],
    "self_help":         ["self-help", "coping", "self-care"],
    "when_to_seek_help": ["seek help", "support", "where to"],
}


class WHOMhGAPScraper(BaseScraper):
    def __init__(self):
        super().__init__("who_mhgap", "db1_clinical")

    def run(self) -> list:
        records = []
        all_pages = {**PAGES, **PROGRAMME_PAGES}

        for path, (condition, icd11) in all_pages.items():
            url = BASE + path
            self.log.info("WHO page: %s", condition)
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
                    "source":       "WHO",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })
            self.log.info("  %d sections extracted", len(sections))

        self.save(records, "who_mhgap_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        """
        WHO fact sheets have a consistent structure: key facts at the top,
        then h2 sections. We walk h2/h3 and collect everything between them.
        """
        main = soup.select_one(
            "main, #main-content, article, "
            ".sf-content-block, [class*='content-block']"
        )
        if main is None:
            main = soup.find("body") or soup

        sections: dict = {}
        current_heading = "overview"
        current_chunks: list = []

        for el in main.find_all(["h2", "h3", "h4", "p", "ul", "ol", "li"]):
            if el.name in ("h2", "h3", "h4"):
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
    WHOMhGAPScraper().run()

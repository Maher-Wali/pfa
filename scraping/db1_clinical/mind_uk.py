"""
Scraper: Mind UK — Mental Health A-Z
URL   : https://www.mind.org.uk/information-support/types-of-mental-health-problems/
License: Standard web terms — non-commercial educational use.

URL structure (confirmed):
  - Root condition page redirects to about-{slug}/ rather than listing nav links
  - Sub-pages are: about-{slug}/, symptoms/, causes/, treatments/,
                   self-care/, for-friends-and-family/
  - Only a sequential "next >" button exists on each page — no sidebar nav index

Strategy: build sub-page URLs from a hardcoded slug map + the known fixed
sub-pages, rather than relying on link discovery from the root page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.mind.org.uk"

# Full Chromium browser fingerprint — Mind UK blocks requests without these
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "DNT": "1",
}
CONDITIONS_ROOT = f"{BASE}/information-support/types-of-mental-health-problems/"

# condition_slug → (display_name, icd11_code)
CONDITIONS = {
    "depression":                              ("Depression",                      "6A70"),
    "anxiety-and-panic-attacks":               ("Anxiety and Panic Attacks",       "6B0Z"),
    "post-traumatic-stress-disorder-ptsd":     ("PTSD",                           "6B40"),
    "complex-ptsd-cptsd":                      ("Complex PTSD",                   "6B41"),
    "obsessive-compulsive-disorder-ocd":       ("OCD",                            "6B20"),
    "bipolar-disorder":                        ("Bipolar Disorder",               "6A60"),
    "borderline-personality-disorder-bpd":     ("Borderline Personality Disorder","6D11"),
    "schizophrenia":                           ("Schizophrenia",                  "6A20"),
    "eating-problems":                         ("Eating Disorders",               "6B8Z"),
    "self-harm":                               ("Self-Harm",                      None),
    "sleep-problems":                          ("Sleep Problems",                  None),
    "stress":                                  ("Stress",                          None),
    "loneliness":                              ("Loneliness",                      None),
    "seasonal-affective-disorder-sad":         ("Seasonal Affective Disorder",    "6A70"),
    "body-dysmorphic-disorder-bdd":            ("Body Dysmorphic Disorder",       "6B21"),
    "postnatal-depression":                    ("Postnatal Depression",           "6A70"),
    "phobias":                                 ("Phobias",                        "6B03"),
    "paranoia":                                ("Paranoia",                        None),
    "psychosis":                               ("Psychosis",                      "6A2Z"),
    "hoarding":                                ("Hoarding Disorder",              "6B25"),
}

# The "about" sub-page slug varies per condition — listed explicitly
ABOUT_SLUGS = {
    "depression":                          "about-depression",
    "anxiety-and-panic-attacks":           "about-anxiety",
    "post-traumatic-stress-disorder-ptsd": "about-ptsd",
    "complex-ptsd-cptsd":                  "about-complex-ptsd-cptsd",
    "obsessive-compulsive-disorder-ocd":   "about-ocd",
    "bipolar-disorder":                    "about-bipolar-disorder",
    "borderline-personality-disorder-bpd": "about-bpd",
    "schizophrenia":                       "about-schizophrenia",
    "eating-problems":                     "about-eating-problems",
    "self-harm":                           "about-self-harm",
    "sleep-problems":                      "about-sleep-problems",
    "stress":                              "what-is-stress",
    "loneliness":                          "about-loneliness",
    "seasonal-affective-disorder-sad":     "about-sad",
    "body-dysmorphic-disorder-bdd":        "about-bdd",
    "postnatal-depression":                "about-postnatal-depression",
    "phobias":                             "about-phobias",
    "paranoia":                            "about-paranoia",
    "psychosis":                           "about-psychosis",
    "hoarding":                            "about-hoarding-disorder",
}

# These slugs are consistent across all conditions
STANDARD_SUBPAGES = [
    "symptoms",
    "causes",
    "treatments",
    "self-care",
    "for-friends-and-family",
]

# URL slug fragment → schema section key
SECTION_MAP = {
    "about":          "overview",
    "what-is":        "overview",
    "types":          "overview",
    "symptoms":       "symptoms",
    "causes":         "causes",
    "treatments":     "treatment",
    "treatment":      "treatment",
    "diagnosis":      "diagnosis",
    "self-care":      "self_help",
    "self-help":      "self_help",
    "for-friends":    "when_to_seek_help",
    "for-family":     "when_to_seek_help",
    "getting-help":   "when_to_seek_help",
    "recovery":       "living_with",
    "living-with":    "living_with",
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".mind-header", ".mind-footer",
    ".breadcrumb", ".related-information", ".mind-cta",
    ".share", "script", "style", ".cookie-banner",
]


class MindUKScraper(BaseScraper):
    def __init__(self):
        super().__init__("mind_uk", "db1_clinical")

    def _headers(self) -> dict:
        return _BROWSER_HEADERS

    def run(self) -> list:
        records = []
        for slug, (name, icd11) in CONDITIONS.items():
            self.log.info("Condition: %s", name)
            sub_urls = self._build_sub_urls(slug)

            for url in sub_urls:
                soup = self.get(url)
                if soup is None:
                    continue

                # Detect soft 404
                h1 = soup.find("h1")
                if h1 and any(p in h1.get_text().lower()
                              for p in ["page not found", "404", "not found"]):
                    continue

                self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
                content = self._extract_content(soup)
                if not content or len(content) < 100:
                    continue

                records.append({
                    "condition":    name,
                    "aliases":      [],
                    "source":       "Mind UK",
                    "source_url":   url,
                    "section":      self._classify_url(url),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

            scraped = sum(1 for r in records if r["condition"] == name)
            self.log.info("  %d sub-pages scraped for %s", scraped, name)

        self.save(records, "mind_uk_clinical.json")
        return records

    def _build_sub_urls(self, slug: str) -> list:
        """Build all sub-page URLs for a condition from the known slug map."""
        base = f"{CONDITIONS_ROOT}{slug}"
        urls = []

        # About page (varies per condition)
        about = ABOUT_SLUGS.get(slug, f"about-{slug.split('-')[0]}")
        urls.append(f"{base}/{about}/")

        # Fixed sub-pages (consistent across all conditions)
        for sub in STANDARD_SUBPAGES:
            urls.append(f"{base}/{sub}/")

        return urls

    def _classify_url(self, url: str) -> str:
        slug = url.rstrip("/").split("/")[-1].lower()
        for fragment, section in SECTION_MAP.items():
            if slug.startswith(fragment):
                return section
        return "other"

    def _extract_content(self, soup) -> str:
        for sel in ["main", "article", ".mind-content",
                    "#content", ".page-content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""


if __name__ == "__main__":
    MindUKScraper().run()

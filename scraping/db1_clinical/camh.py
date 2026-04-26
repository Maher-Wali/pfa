"""
Scraper: CAMH — Centre for Addiction and Mental Health (Canada)
URL   : https://www.camh.ca/en/health-info
License: CAMH — free for personal and educational use.

CAMH is Canada's leading mental health hospital and research centre.
Their public health-info pages cover conditions and treatments in clear,
evidence-based language. Static HTML, minimal bot protection.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.camh.ca"

# (condition_name, url_path, icd11_code)
TARGETS = [
    ("Depression",
     "/en/health-info/mental-illness-and-addiction-index/depression",                "6A70"),
    ("Anxiety Disorders",
     "/en/health-info/mental-illness-and-addiction-index/anxiety-disorders",         "6B0Z"),
    ("Bipolar Disorder",
     "/en/health-info/mental-illness-and-addiction-index/bipolar-disorder",          "6A60"),
    ("PTSD",
     "/en/health-info/mental-illness-and-addiction-index/post-traumatic-stress-disorder", "6B40"),
    ("OCD",
     "/en/health-info/mental-illness-and-addiction-index/obsessive-compulsive-disorder",  "6B20"),
    ("Schizophrenia",
     "/en/health-info/mental-illness-and-addiction-index/schizophrenia",             "6A20"),
    ("Eating Disorders",
     "/en/health-info/mental-illness-and-addiction-index/eating-disorders",          "6B8Z"),
    ("ADHD",
     "/en/health-info/mental-illness-and-addiction-index/attention-deficit-hyperactivity-disorder", "6A05"),
    ("Borderline Personality Disorder",
     "/en/health-info/mental-illness-and-addiction-index/borderline-personality-disorder", "6D11"),
    ("Phobia",
     "/en/health-info/mental-illness-and-addiction-index/phobia",                   "6B03"),
    ("Seasonal Affective Disorder",
     "/en/health-info/mental-illness-and-addiction-index/seasonal-affective-disorder", "6A70"),
    ("Self-Harm",
     "/en/health-info/mental-illness-and-addiction-index/self-harm",                None),
    ("Suicide",
     "/en/health-info/mental-illness-and-addiction-index/suicide",                  None),
    ("Concurrent Disorders",
     "/en/health-info/mental-illness-and-addiction-index/concurrent-disorders",     None),
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "about", "overview"],
    "symptoms":          ["symptom", "sign", "experience"],
    "causes":            ["cause", "risk", "factor"],
    "diagnosis":         ["diagnos", "assessed"],
    "treatment":         ["treat", "therap", "medication", "recovery"],
    "self_help":         ["self-help", "coping", "support yourself"],
    "when_to_seek_help": ["seek help", "getting help", "when to"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
    ".related", ".social-links", ".feedback",
    ".alert-bar", ".cookie-notice",
]

# Additional paths to crawl for supplementary content
EXTRA_PATHS = [
    "/en/health-info/mental-health-101",
    "/en/health-info/guides-and-publications",
]
EXTRA_ALLOWED_DOMAINS = ["www.camh.ca", "camh.ca"]
EXTRA_MAX_PAGES = 40


class CAMHScraper(BaseScraper):
    def __init__(self):
        super().__init__("camh", "db1_clinical")

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
                    "source":       "CAMH",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

        records.extend(self._scrape_extra_paths())

        self.log.info("Total: %d records", len(records))
        self.save(records, "camh_clinical.json")
        return records

    def _scrape_extra_paths(self) -> list:
        """Crawl mental-health-101 and guides-and-publications for additional content."""
        from urllib.parse import urljoin, urlparse, urldefrag

        records = []
        seen: set = set()

        for root_path in EXTRA_PATHS:
            queue = [BASE + root_path]
            path_prefix = root_path.lower()

            while queue and len(seen) < EXTRA_MAX_PAGES:
                raw_url = queue.pop(0)
                url, _ = urldefrag(raw_url)
                if url in seen:
                    continue
                seen.add(url)

                parsed = urlparse(url)
                if parsed.netloc.lower() not in EXTRA_ALLOWED_DOMAINS:
                    continue
                if not parsed.path.lower().startswith(path_prefix):
                    continue

                soup = self.get(url)
                if soup is None:
                    continue

                h1 = soup.find("h1")
                if h1 and any(p in h1.get_text().lower() for p in ["not found", "404"]):
                    continue

                self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
                sections = self._extract_sections(soup)

                for heading, content in sections.items():
                    if not content or len(content.split()) < 30:
                        continue
                    records.append({
                        "condition":    self._infer_condition(url, soup),
                        "aliases":      [],
                        "source":       "CAMH",
                        "source_url":   url,
                        "section":      self._classify_section(heading),
                        "content":      content,
                        "icd11_code":   None,
                        "last_scraped": self.today(),
                    })

                # Harvest links within the same path prefix
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if not href or href.startswith(("#", "mailto:", "javascript:")):
                        continue
                    abs_url, _ = urldefrag(urljoin(url, href))
                    if abs_url not in seen:
                        queue.append(abs_url)

        self.log.info("Extra paths: %d records", len(records))
        return records

    def _infer_condition(self, url: str, soup) -> str:
        """Infer condition name from page h1, falling back to URL slug."""
        h1 = soup.find("h1")
        if h1:
            return self.clean(h1.get_text())
        slug = url.rstrip("/").split("/")[-1].replace("-", " ").title()
        return slug or "General Mental Health"

    def _extract_sections(self, soup) -> dict:
        main = soup.select_one(
            "main, article, .contentArea, .page-content, "
            "#main-content, .field--type-text-with-summary, #content"
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
    CAMHScraper().run()

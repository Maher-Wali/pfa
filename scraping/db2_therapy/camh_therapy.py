"""
Scraper: CAMH — Guides & Publications (DB2)
URL   : https://www.camh.ca/en/health-info/guides-and-publications
License: CAMH — free for personal and educational use.

Crawls CAMH's guides-and-publications section (individual guide pages with
therapy and coping content). mental-health-101 was tried but all its sublinks
point to external platforms (globallearningacademy.ca / camhx.ca) making it
unusable for BFS. Distinct from db1_clinical/camh.py which targets condition
index pages. Uses the same boilerplate stripping and section extraction.
"""
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.camh.ca"

# mental-health-101 links entirely to external platforms (globallearningacademy.ca /
# camhx.ca) — the BFS finds no internal subpages there.
# guides-and-publications has many internal guide pages within the same path prefix.
CRAWL_ROOTS = [
    "/en/health-info/guides-and-publications",
]
ALLOWED_DOMAINS = {"www.camh.ca", "camh.ca"}
MAX_PAGES = 50

# Same as db1_clinical/camh.py — site structure is identical
BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
    ".related", ".social-links", ".feedback",
    ".alert-bar", ".cookie-notice",
]


class CAMHTherapyScraper(BaseScraper):
    def __init__(self):
        super().__init__("camh_therapy", "db2_therapy")

    def run(self) -> list:
        records = []
        seen: set = set()

        for root_path in CRAWL_ROOTS:
            queue = [BASE + root_path]
            path_prefix = root_path.lower()

            while queue and len(seen) < MAX_PAGES:
                raw_url = queue.pop(0)
                url, _ = urldefrag(raw_url)
                if url in seen:
                    continue
                seen.add(url)

                parsed = urlparse(url)
                if parsed.netloc.lower() not in ALLOWED_DOMAINS:
                    continue
                if not parsed.path.lower().startswith(path_prefix):
                    continue

                self.log.info("Fetching: %s", url)
                soup = self.get(url)
                if soup is None:
                    continue

                h1 = soup.find("h1")
                if h1 and any(p in h1.get_text().lower() for p in ["not found", "404"]):
                    continue

                technique_name = self.clean(h1.get_text()) if h1 else self._slug_to_name(url)
                if not technique_name:
                    continue

                self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
                content = self._extract_content(soup)
                if not content or len(content.split()) < 40:
                    continue

                records.append({
                    "technique_name":    technique_name,
                    "aliases":           [],
                    "modality":          self._infer_modality(technique_name, content),
                    "target_conditions": [],
                    "target_problem":    None,
                    "steps":             None,
                    "worked_example":    None,
                    "when_to_use":       None,
                    "estimated_time":    None,
                    "difficulty":        None,
                    "raw_content":       content,
                    "source":            "CAMH",
                    "source_url":        url,
                    "last_scraped":      self.today(),
                })
                self.log.info("  -> saved [%s]", records[-1]["modality"])

                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if not href or href.startswith(("#", "mailto:", "javascript:")):
                        continue
                    abs_url, _ = urldefrag(urljoin(url, href))
                    if abs_url not in seen:
                        queue.append(abs_url)

        self.log.info("Total: %d records", len(records))
        self.save(records, "camh_therapy.json")
        return records

    def _extract_content(self, soup) -> str:
        # Same selector priority as db1_clinical/camh.py
        main = soup.select_one(
            "main, article, .contentArea, .page-content, "
            "#main-content, .field--type-text-with-summary, #content"
        )
        if main is None:
            main = soup.find("body") or soup
        parts = []
        for el in main.find_all(["h2", "h3", "p", "ul", "ol"]):
            chunk = el.get_text(separator=" ", strip=True)
            if chunk:
                parts.append(chunk)
        return self.clean(" ".join(parts))

    def _infer_modality(self, name: str, content: str) -> str:
        blob = f"{name} {content[:3000]}".lower()
        if any(k in blob for k in ["dialectical", "dbt", "wise mind", "distress tolerance"]):
            return "DBT"
        if any(k in blob for k in ["acceptance and commitment", "act ", "defusion", "values"]):
            return "ACT"
        if any(k in blob for k in ["mindful", "meditation", "body scan"]):
            return "MBSR"
        if any(k in blob for k in ["self-compassion", "compassion", "self compassion"]):
            return "MSC"
        if any(k in blob for k in ["cognitive behav", "thought record", "cognitive restructur"]):
            return "CBT"
        return "CBT"

    def _slug_to_name(self, url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        return slug.replace("-", " ").title()


if __name__ == "__main__":
    CAMHTherapyScraper().run()

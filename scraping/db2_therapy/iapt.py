"""
Scraper: NHS Inform Scotland — Mental Health Self-Help Guides
URL   : https://www.nhsinform.scot/symptoms-and-self-help/self-help-guides/
License: Open Government Licence (NHS Scotland)

Structure (confirmed):
  - Index at /symptoms-and-self-help/self-help-guides/
    Contains sections: "Mental health self-help guides" and "Mental wellbeing"
  - Each guide at /illnesses-and-conditions/mental-health/mental-health-self-help-guides/{slug}/
  - Each guide page has a left nav for steps — each step is a separate URL
  - Each guide also has a "Download PDF of self-help guide" button (direct PDF link)

Strategy: for each guide, find the PDF download link and extract it.
If no PDF link is found, crawl step pages via the left navigation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text, split_by_headings

BASE = "https://www.nhsinform.scot"
GUIDES_INDEX = f"{BASE}/symptoms-and-self-help/self-help-guides/"

# NHS Inform also has condition overview pages — scrape these for DB2 context
CONDITION_PAGES = {
    "/illnesses-and-conditions/mental-health/depression/":
        ("Depression", ["depression", "low mood"]),
    "/illnesses-and-conditions/mental-health/anxiety/":
        ("Anxiety", ["anxiety"]),
    "/illnesses-and-conditions/mental-health/stress/":
        ("Stress", ["stress"]),
    "/illnesses-and-conditions/mental-health/ptsd/":
        ("PTSD", ["PTSD"]),
    "/illnesses-and-conditions/mental-health/ocd/":
        ("OCD", ["OCD"]),
    "/illnesses-and-conditions/mental-health/panic-disorder/":
        ("Panic Disorder", ["panic"]),
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".breadcrumb", "script", "style",
    ".nhsinform-header", ".nhsinform-footer", ".feedback",
    ".cookie-notice", ".related-links", ".print-page",
]

# Sections of the index we care about
TARGET_SECTIONS = [
    "mental health self-help guides",
    "mental wellbeing",
]


class IAPTScraper(BaseScraper):
    def __init__(self):
        super().__init__("iapt", "db2_therapy")

    def run(self) -> list:
        records = []
        records.extend(self._scrape_guide_index())
        self.save(records, "iapt_therapy.json")
        return records

    # ------------------------------------------------------------------
    # Guide index → find all self-help guide URLs
    # ------------------------------------------------------------------

    def _scrape_guide_index(self) -> list:
        self.log.info("Fetching self-help guides index")
        soup = self.get(GUIDES_INDEX)
        if soup is None:
            self.log.error("Could not load guides index")
            return []

        guide_urls = self._extract_guide_links(soup)
        self.log.info("Found %d guide URLs", len(guide_urls))

        records = []
        for url in guide_urls:
            batch = self._scrape_single_guide(url)
            records.extend(batch)

        return records

    def _extract_guide_links(self, soup) -> list:
        """
        Find links in the mental health and mental wellbeing sections
        of the self-help guides index.
        """
        links = []
        seen = set()

        # NHS Inform uses h2/h3 headings to label each section of the index.
        # We walk headings and collect links until we hit a section we don't want.
        in_target_section = False

        for el in soup.find_all(["h2", "h3", "a"]):
            if el.name in ("h2", "h3"):
                heading_text = el.get_text(strip=True).lower()
                in_target_section = any(
                    section in heading_text for section in TARGET_SECTIONS
                )
                continue

            if in_target_section and el.name == "a":
                href = el.get("href", "")
                if not href:
                    continue
                full_url = href if href.startswith("http") else BASE + href
                # Only include mental health guide pages, not external links
                if "nhsinform.scot" in full_url and full_url not in seen:
                    seen.add(full_url)
                    links.append(full_url)

        # Fallback: grab all self-help-guide links from the page regardless of section
        if not links:
            self.log.warning("Section-based extraction found nothing — using fallback")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "self-help-guide" in href or "mental-health" in href:
                    full_url = href if href.startswith("http") else BASE + href
                    if full_url not in seen:
                        seen.add(full_url)
                        links.append(full_url)

        return links

    # ------------------------------------------------------------------
    # Individual guide: try PDF first, fall back to step pages
    # ------------------------------------------------------------------

    def _scrape_single_guide(self, guide_url: str) -> list:
        self.log.info("Guide: %s", guide_url)
        soup = self.get(guide_url)
        if soup is None:
            return []

        # Infer guide name from h1
        h1 = soup.find("h1")
        guide_name = h1.get_text(strip=True) if h1 else guide_url.rstrip("/").split("/")[-1]
        conditions = self._infer_conditions(guide_name)
        modality = self._infer_modality(guide_name)

        # --- Strategy A: download the PDF ---
        pdf_url = self._find_pdf_url(soup, guide_url)
        if pdf_url:
            self.log.info("  PDF found: %s", pdf_url)
            raw = self.download_bytes(pdf_url)
            if raw:
                text = extract_text(raw)
                if text and len(text) > 200:
                    sections = split_by_headings(text)
                    records = []
                    for heading, content in sections.items():
                        if not content or len(content) < 80:
                            continue
                        records.append(
                            self._make_record(guide_name, modality, conditions,
                                              self.clean(content), pdf_url)
                        )
                    self.log.info("  Extracted %d sections from PDF", len(records))
                    return records

        # --- Strategy B: crawl step pages from left navigation ---
        self.log.info("  No PDF — crawling step pages")
        return self._scrape_step_pages(soup, guide_url, guide_name,
                                       modality, conditions)

    def _find_pdf_url(self, soup, base_url: str) -> str:
        """
        Look for the "Download PDF of self-help guide" link.
        It's typically an <a> whose text contains "download" and "pdf",
        or whose href ends in .pdf.
        """
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            if href.lower().endswith(".pdf"):
                return href if href.startswith("http") else BASE + href
            if "download" in text and "pdf" in text:
                return href if href.startswith("http") else BASE + href
        return ""

    def _scrape_step_pages(self, index_soup, guide_url, guide_name,
                           modality, conditions) -> list:
        """
        Walk step links from the left navigation and scrape each one.
        Step links are siblings of the current page within the same guide path.
        """
        step_urls = self._extract_step_urls(index_soup, guide_url)
        self.log.info("  Found %d step links", len(step_urls))

        records = []
        for step_url in step_urls:
            soup = self.get(step_url)
            if soup is None:
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            content = self._extract_page_content(soup)
            if not content or len(content) < 80:
                continue

            records.append(
                self._make_record(guide_name, modality, conditions,
                                  content, step_url)
            )

        # Also capture the index page itself
        self.strip_boilerplate(index_soup, BOILERPLATE_SELECTORS)
        index_content = self._extract_page_content(index_soup)
        if index_content and len(index_content) > 80:
            records.append(
                self._make_record(guide_name, modality, conditions,
                                  index_content, guide_url)
            )

        return records

    def _extract_step_urls(self, soup, guide_url: str) -> list:
        """
        NHS Inform guide step URLs are siblings in the left navigation.
        They share the same base path as the guide URL.
        """
        base_path = guide_url.rstrip("/")
        urls = []
        seen = {guide_url}

        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = href if href.startswith("http") else BASE + href
            full = full.rstrip("/")

            # Step pages are children of the guide URL one level deep
            if not full.startswith(base_path + "/"):
                continue
            remainder = full[len(base_path) + 1:]
            if "/" in remainder:
                continue
            if full + "/" not in seen and full not in seen:
                seen.add(full + "/")
                urls.append(full + "/")

        return urls

    def _extract_page_content(self, soup) -> str:
        for sel in ["main", "article", ".nhsinform-content",
                    ".page-content", "#content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""

    def _make_record(self, technique_name, modality, conditions,
                     content, url) -> dict:
        return {
            "technique_name":    technique_name,
            "aliases":           [],
            "modality":          modality,
            "target_conditions": conditions,
            "target_problem":    None,
            "steps":             None,
            "worked_example":    None,
            "when_to_use":       None,
            "estimated_time":    None,
            "difficulty":        None,
            "raw_content":       content,
            "source":            "NHS Inform / IAPT",
            "source_url":        url,
            "last_scraped":      self.today(),
        }

    def _infer_conditions(self, name: str) -> list:
        n = name.lower()
        mapping = {
            "depress":   ["depression", "low mood"],
            "anxiety":   ["anxiety", "GAD"],
            "panic":     ["panic disorder"],
            "ocd":       ["OCD"],
            "social":    ["social anxiety"],
            "health anx": ["health anxiety"],
            "phobia":    ["phobias"],
            "sleep":     ["insomnia", "sleep problems"],
            "anger":     ["anger"],
            "ptsd":      ["PTSD"],
            "worry":     ["anxiety", "GAD"],
            "stress":    ["stress"],
            "wellbeing": [],
        }
        for key, conditions in mapping.items():
            if key in n:
                return conditions
        return []

    def _infer_modality(self, name: str) -> str:
        n = name.lower()
        if any(w in n for w in ["mindful", "meditation"]):
            return "MBSR"
        if any(w in n for w in ["acceptance", "act "]):
            return "ACT"
        return "CBT"


if __name__ == "__main__":
    IAPTScraper().run()

"""
Scraper: Beyond Blue — Self-Help & Technique Pages (DB2)
URL   : https://www.beyondblue.org.au
License: Australian government-backed charity — non-commercial educational use.

Beyond Blue migrated to Next.js (Sitecore SXA headless) in 2024. Page HTML is
a JS shell — content is embedded in the __NEXT_DATA__ <script> tag as JSON.
We extract text from the nested placeholder/fields structure without a browser.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text

BASE = "https://www.beyondblue.org.au"

# (technique_name, url_path, modality, target_conditions)
TARGETS = [
    ("Treatments for Anxiety",
     "/mental-health/anxiety/treatments-for-anxiety",
     "CBT", ["anxiety", "GAD", "panic disorder", "social anxiety"]),

    ("Treatments for Depression",
     "/mental-health/depression/treatments-for-depression",
     "CBT", ["depression"]),

    ("Anxiety — Types",
     "/mental-health/anxiety/types-of-anxiety",
     "CBT", ["anxiety"]),

    ("Panic Disorder",
     "/mental-health/anxiety/types-of-anxiety/panic-disorder",
     "CBT", ["panic disorder"]),

    ("Social Anxiety Disorder",
     "/mental-health/anxiety/types-of-anxiety/social-anxiety-disorder",
     "CBT", ["social anxiety"]),

    ("Suicide Prevention",
     "/mental-health/suicide-prevention",
     "CBT", ["suicidal ideation"]),

    ("Wellbeing — Sleep",
     "/mental-health/wellbeing/sleep",
     "CBT", ["insomnia", "depression", "anxiety"]),
]

PDF_TARGETS = [
    ("What Works for Mental Wellbeing",
     "https://www.beyondblue.org.au/docs/default-source/resources/bb-guide-to-what-works-for-mental-wellbeing-final.pdf?sfvrsn=5ca0e3c_2",
     "CBT", []),
]

# Fields that carry body text in the Sitecore headless schema
_TEXT_FIELD_NAMES = {"MainText", "Text", "Body", "Content", "Description",
                     "IntroText", "Summary"}
# Placeholder keys that are navigation / footer boilerplate — skip them
_SKIP_PLACEHOLDER_PREFIXES = ("headless-footer", "headless-head",
                               "headless-main-after", "sxa-footer",
                               "sxa-head")


class BeyondBlueTherapyScraper(BaseScraper):
    def __init__(self):
        super().__init__("beyond_blue_therapy", "db2_therapy")

    def run(self) -> list:
        records = []
        records.extend(self._scrape_pages())
        records.extend(self._scrape_pdfs())
        self.save(records, "beyond_blue_therapy.json")
        return records

    # ------------------------------------------------------------------
    # HTML pages — parse __NEXT_DATA__ JSON instead of rendered DOM
    # ------------------------------------------------------------------

    def _scrape_pages(self) -> list:
        records = []
        for technique_name, path, modality, conditions in TARGETS:
            url = BASE + path
            self.log.info("Page: %s", technique_name)
            content = self._fetch_nextjs_text(url)
            if not content or len(content.split()) < 40:
                self.log.warning("  -> no content: %s", url)
                continue
            records.append(self._make_record(technique_name, modality, conditions, content, url))
            self.log.info("  -> %d words", len(content.split()))
        return records

    def _fetch_nextjs_text(self, url: str) -> str:
        """Fetch a Beyond Blue page and extract body text from __NEXT_DATA__."""
        try:
            resp = self.session.get(url, headers=self._headers(), timeout=20)
            resp.raise_for_status()
            self._wait()
            html = resp.content.decode(resp.encoding or "utf-8", errors="replace")
        except Exception as exc:
            self.log.warning("  Request failed: %s", exc)
            return ""

        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            self.log.warning("  __NEXT_DATA__ not found")
            return ""

        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            self.log.warning("  JSON parse error: %s", exc)
            return ""

        route = (data.get("props", {})
                     .get("pageProps", {})
                     .get("layoutData", {})
                     .get("sitecore", {})
                     .get("route", {}))
        parts: list[str] = []
        self._walk_placeholders(route.get("placeholders", {}), parts)
        raw = " ".join(parts)
        # Strip residual HTML tags from rich-text values
        raw = re.sub(r"<[^>]+>", " ", raw)
        return self.clean(raw)

    def _walk_placeholders(self, placeholders: dict, parts: list) -> None:
        for key, components in placeholders.items():
            if any(key.startswith(p) for p in _SKIP_PLACEHOLDER_PREFIXES):
                continue
            if not isinstance(components, list):
                continue
            for component in components:
                if not isinstance(component, dict):
                    continue
                # Extract text fields from this component
                for fname, fval in component.get("fields", {}).items():
                    if fname not in _TEXT_FIELD_NAMES:
                        continue
                    text = fval.get("value", "") if isinstance(fval, dict) else ""
                    if isinstance(text, str) and len(text.strip()) > 30:
                        parts.append(text.strip())
                # Recurse into nested placeholders
                self._walk_placeholders(component.get("placeholders", {}), parts)

    # ------------------------------------------------------------------
    # PDFs
    # ------------------------------------------------------------------

    def _scrape_pdfs(self) -> list:
        records = []
        for technique_name, url, modality, conditions in PDF_TARGETS:
            self.log.info("PDF: %s", technique_name)
            raw = self.download_bytes(url, referer=BASE)
            if raw is None:
                self.log.warning("  Failed to download: %s", url)
                continue
            text = extract_text(raw)
            if not text or len(text.split()) < 40:
                self.log.warning("  No usable text: %s", url)
                continue
            records.append(self._make_record(technique_name, modality, conditions,
                                             self.clean(text), url))
            self.log.info("  -> saved PDF")
        return records

    def _make_record(self, technique_name, modality, conditions, content, url) -> dict:
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
            "source":            "Beyond Blue",
            "source_url":        url,
            "last_scraped":      self.today(),
        }


if __name__ == "__main__":
    BeyondBlueTherapyScraper().run()

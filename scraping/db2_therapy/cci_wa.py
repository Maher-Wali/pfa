"""
Scraper: Centre for Clinical Interventions (CCI) — WA Health, Australia
URL   : https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself
License: WA Department of Health — free for personal and clinical use.

CCI produces evidence-based self-help modules (CBT, DBT, ACT, mindfulness)
used widely by therapists and patients. Each topic page links to numbered
PDF modules — these are the primary content. The scraper:
  1. Fetches each topic overview page (HTML intro + module list)
  2. Discovers PDF links on the page and downloads them
  3. Extracts text from each PDF with pdfplumber

This is a .gov.au site with no bot protection. PDF URLs embed spaces and
special characters — the scraper resolves them via BeautifulSoup href attrs.
"""
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text

BASE = "https://www.cci.health.wa.gov.au"

# (technique_name, url_path, modality, target_conditions)
TARGETS = [
    ("CBT for Depression",
     "/Resources/Looking-After-Yourself/Depression",
     "CBT", ["depression"]),

    ("CBT for Panic and Agoraphobia",
     "/Resources/Looking-After-Yourself/Panic",
     "CBT", ["panic disorder", "agoraphobia"]),

    ("CBT for Social Anxiety",
     "/Resources/Looking-After-Yourself/Social-Fear",
     "CBT", ["social anxiety"]),

    ("CBT for Worry and Rumination",
     "/Resources/Looking-After-Yourself/Worry-and-Rumination",
     "CBT", ["generalised anxiety disorder", "worry"]),

    ("CBT for Perfectionism",
     "/Resources/Looking-After-Yourself/Perfectionism",
     "CBT", ["perfectionism", "anxiety", "depression"]),

    ("CBT for Health Anxiety",
     "/Resources/Looking-After-Yourself/Health-Anxiety",
     "CBT", ["health anxiety"]),

    ("CBT for Disordered Eating",
     "/Resources/Looking-After-Yourself/Disordered-Eating",
     "CBT", ["eating disorders"]),

    ("CBT for OCD",
     "/Resources/Looking-After-Yourself/OCD",
     "CBT", ["ocd"]),

    ("Self-Compassion",
     "/Resources/Looking-After-Yourself/Self-Compassion",
     "MSC", ["depression", "anxiety", "shame"]),

    ("Assertiveness and Self-Esteem",
     "/Resources/Looking-After-Yourself/Assert-Yourself",
     "CBT", ["low self-esteem", "social anxiety"]),

    ("Tolerating Distress (DBT)",
     "/Resources/Looking-After-Yourself/Tolerating-Distress",
     "DBT", ["bpd", "emotional dysregulation"]),

    ("Emotion Regulation (DBT)",
     "/Resources/Looking-After-Yourself/Emotion-Regulation",
     "DBT", ["bpd", "emotional dysregulation"]),

    ("Mindfulness",
     "/Resources/Looking-After-Yourself/Mindfulness",
     "MBSR", ["depression", "anxiety", "stress"]),

    ("Overcoming Grief and Loss",
     "/Resources/Looking-After-Yourself/Grief-and-Loss",
     "CBT", ["grief", "bereavement"]),

    ("Bipolar — Living Well",
     "/Resources/Looking-After-Yourself/Bipolar",
     "CBT", ["bipolar disorder"]),

    ("Psychosis — Recovery",
     "/Resources/Looking-After-Yourself/Psychosis",
     "CBT", ["schizophrenia", "psychosis"]),
]

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".topnav", "#top-nav",
    "script", "style", ".breadcrumb", ".footer",
]


class CCIWAScraper(BaseScraper):
    def __init__(self):
        super().__init__("cci_wa", "db2_therapy", delay_range=(1.5, 3.0))

    def run(self) -> list:
        records = []
        for technique_name, path, modality, targets in TARGETS:
            url = BASE + path
            self.log.info("Topic: %s", technique_name)
            soup = self.get(url)
            if soup is None:
                continue

            # 1. Extract HTML intro / overview text
            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            intro = self._extract_intro(soup)

            if intro and len(intro.split()) >= 40:
                records.append(self._make_record(
                    technique_name, modality, targets, url,
                    intro, chunk_type="overview",
                ))

            # 2. Find and download all PDF module links on the page
            pdf_links = self._find_pdf_links(soup, url)
            self.log.info("  Found %d PDF(s)", len(pdf_links))

            for pdf_url, pdf_label in pdf_links:
                self.log.info("  PDF: %s", pdf_label)
                raw = self.download_bytes(pdf_url, referer=url)
                if raw is None:
                    continue
                text = self.clean(extract_text(raw))
                if not text or len(text.split()) < 40:
                    continue
                label = f"{technique_name} — {pdf_label}"
                records.append(self._make_record(
                    label, modality, targets, pdf_url,
                    text, chunk_type="module_pdf",
                ))

        self.log.info("Total: %d records", len(records))
        self.save(records, "cci_wa_therapy.json")
        return records

    def _extract_intro(self, soup) -> str:
        for sel in ["main", ".content", "#content", ".page-content", "article", "body"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        return ""

    def _find_pdf_links(self, soup, page_url: str) -> list[tuple[str, str]]:
        """Return (absolute_pdf_url, link_text) for all PDF hrefs on the page."""
        results = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.lower().endswith(".pdf"):
                continue
            abs_url = urljoin(page_url, href)
            if abs_url in seen:
                continue
            seen.add(abs_url)
            # Use link text as label, fall back to filename
            label = a.get_text(strip=True) or unquote(href.split("/")[-1])
            label = re.sub(r"\.pdf$", "", label, flags=re.IGNORECASE).strip()
            results.append((abs_url, label))
        return results

    @staticmethod
    def _make_record(technique_name, modality, targets, url, content, chunk_type):
        return {
            "technique_name":    technique_name,
            "aliases":           [],
            "modality":          modality,
            "target_conditions": targets,
            "target_problem":    None,
            "steps":             None,
            "worked_example":    None,
            "when_to_use":       None,
            "estimated_time":    None,
            "difficulty":        None,
            "raw_content":       content,
            "source":            "CCI WA",
            "source_url":        url,
            "chunk_type":        chunk_type,
            "last_scraped":      __import__("datetime").date.today().isoformat(),
        }


if __name__ == "__main__":
    CCIWAScraper().run()

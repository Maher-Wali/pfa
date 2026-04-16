"""
Scraper: Centre for Clinical Interventions (CCI) — Psychoeducation modules
URL   : https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself
License: Free for non-commercial use — explicitly stated on site
Notes  : CCI content is primarily in PDFs. This scraper downloads each PDF
         and extracts text via pdf_extractor. Web HTML pages are also scraped
         where available.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text, split_by_headings

BASE = "https://www.cci.health.wa.gov.au"
RESOURCES_INDEX = f"{BASE}/Resources/Looking-After-Yourself"

# Direct links to CCI psychoeducation module PDFs
# These are the "Info Sheets" — single-sheet clinical psychoeducation documents
CCI_PSYCHOEDUCATION_PDFS = {
    # Depression modules
    f"{BASE}/Resources/For-Clients/Depressed-Mood": {
        "condition": "Depression", "icd11_code": "6A70",
        "pdfs": [
            "/CCI_Client_Info_Depression_01_What_is_Depression.pdf",
            "/CCI_Client_Info_Depression_02_The_Vicious_Cycle.pdf",
            "/CCI_Client_Info_Depression_03_Treatment.pdf",
        ]
    },
    # Anxiety modules
    f"{BASE}/Resources/For-Clients/Anxiety": {
        "condition": "Anxiety", "icd11_code": "6B0Z",
        "pdfs": [
            "/CCI_Client_Info_Anxiety_01_What_is_Anxiety.pdf",
            "/CCI_Client_Info_Anxiety_02_The_Fight_or_Flight_Response.pdf",
            "/CCI_Client_Info_Anxiety_03_The_Role_of_Avoidance.pdf",
        ]
    },
    # Panic modules
    f"{BASE}/Resources/For-Clients/Panic": {
        "condition": "Panic Disorder", "icd11_code": "6B01",
        "pdfs": [
            "/CCI_Client_Info_Panic_01_What_is_Panic.pdf",
            "/CCI_Client_Info_Panic_02_Treatment.pdf",
        ]
    },
    # OCD modules
    f"{BASE}/Resources/For-Clients/OCD": {
        "condition": "OCD", "icd11_code": "6B20",
        "pdfs": [
            "/CCI_Client_Info_OCD_01_What_is_OCD.pdf",
            "/CCI_Client_Info_OCD_02_Treatment.pdf",
        ]
    },
    # Health Anxiety
    f"{BASE}/Resources/For-Clients/Health-Anxiety": {
        "condition": "Health Anxiety", "icd11_code": "6B23",
        "pdfs": [
            "/CCI_Client_Info_HealthAnxiety_01_What_is_Health_Anxiety.pdf",
            "/CCI_Client_Info_HealthAnxiety_02_Treatment.pdf",
        ]
    },
    # Social Anxiety
    f"{BASE}/Resources/For-Clients/Social-Anxiety": {
        "condition": "Social Anxiety Disorder", "icd11_code": "6B04",
        "pdfs": [
            "/CCI_Client_Info_SocialAnxiety_01_What_is_Social_Anxiety.pdf",
            "/CCI_Client_Info_SocialAnxiety_02_Treatment.pdf",
        ]
    },
    # Low self-esteem
    f"{BASE}/Resources/For-Clients/Low-Self-Esteem": {
        "condition": "Low Self-Esteem", "icd11_code": None,
        "pdfs": [
            "/CCI_Client_Info_LowSelfEsteem_01_What_is_Low_Self_Esteem.pdf",
        ]
    },
    # Eating disorders
    f"{BASE}/Resources/For-Clients/Eating-Disorders": {
        "condition": "Eating Disorders", "icd11_code": "6B8Z",
        "pdfs": [
            "/CCI_Client_Info_EatingDisorders_01_What_are_Eating_Disorders.pdf",
        ]
    },
}

SECTION_KEYWORDS = {
    "overview":    ["what is", "about", "introduction", "overview"],
    "symptoms":    ["symptom", "sign", "how does it feel"],
    "causes":      ["cause", "why", "risk", "maintenance cycle", "vicious cycle"],
    "treatment":   ["treat", "therap", "help", "recovery"],
    "self_help":   ["self-help", "self help", "coping", "what you can do"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".breadcrumb", "script", "style",
]


class CCIClinicalScraper(BaseScraper):
    def __init__(self):
        super().__init__("cci", "db1_clinical")

    def run(self) -> list:
        records = []

        # 1. Scrape web pages from the index
        records.extend(self._scrape_web_pages())

        # 2. Download and extract PDFs
        records.extend(self._scrape_pdfs())

        self.save(records, "cci_clinical.json")
        return records

    def _scrape_web_pages(self) -> list:
        """Scrape the HTML landing pages for each condition module."""
        records = []
        soup = self.get(RESOURCES_INDEX)
        if soup is None:
            self.log.warning("Could not load CCI resources index")
            return records

        # The index lists modules — scrape each module's landing page
        module_links = soup.select("a[href*='/Resources/For-Clients/']")
        seen_urls = set()

        for link in module_links:
            href = link.get("href", "")
            url = href if href.startswith("http") else BASE + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            page_soup = self.get(url)
            if page_soup is None:
                continue

            self.strip_boilerplate(page_soup, BOILERPLATE_SELECTORS)
            content = self._extract_content(page_soup)
            condition = self._infer_condition(url)

            if content and len(content) > 100:
                records.append({
                    "condition":    condition,
                    "aliases":      [],
                    "source":       "CCI",
                    "source_url":   url,
                    "section":      "overview",
                    "content":      content,
                    "icd11_code":   None,
                    "last_scraped": self.today(),
                })

        self.log.info("Web pages: %d records", len(records))
        return records

    def _scrape_pdfs(self) -> list:
        """Download CCI PDFs and extract text into section records."""
        records = []

        for module_url, meta in CCI_PSYCHOEDUCATION_PDFS.items():
            condition = meta["condition"]
            icd11 = meta["icd11_code"]

            for pdf_path in meta["pdfs"]:
                pdf_url = module_url + pdf_path
                self.log.info("Downloading PDF: %s", pdf_url)
                raw = self.download_bytes(pdf_url)

                if raw is None:
                    self.log.warning("  Failed to download %s", pdf_url)
                    continue

                text = extract_text(raw)
                if not text:
                    self.log.warning("  No text extracted from %s", pdf_url)
                    continue

                sections = split_by_headings(text)
                for heading, content in sections.items():
                    if not content or len(content) < 80:
                        continue
                    records.append({
                        "condition":    condition,
                        "aliases":      [],
                        "source":       "CCI",
                        "source_url":   pdf_url,
                        "section":      self._classify_section(heading),
                        "content":      self.clean(content),
                        "icd11_code":   icd11,
                        "last_scraped": self.today(),
                    })
                self.log.info("  Extracted %d sections from PDF", len(sections))

        self.log.info("PDFs total: %d records", len(records))
        return records

    def _extract_content(self, soup) -> str:
        for sel in ["main", "article", "#content", ".content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""

    def _classify_section(self, heading: str) -> str:
        h = heading.lower()
        for key, keywords in SECTION_KEYWORDS.items():
            if any(kw in h for kw in keywords):
                return key
        return "other"

    def _infer_condition(self, url: str) -> str:
        url_lower = url.lower()
        mapping = {
            "depress": "Depression",
            "anxiety": "Anxiety",
            "panic": "Panic Disorder",
            "ocd": "OCD",
            "health-anx": "Health Anxiety",
            "social": "Social Anxiety Disorder",
            "self-esteem": "Low Self-Esteem",
            "eating": "Eating Disorders",
            "sleep": "Sleep Problems",
            "worry": "Anxiety",
            "anger": "Anger",
            "trauma": "Trauma",
        }
        for key, name in mapping.items():
            if key in url_lower:
                return name
        return "General Mental Health"


if __name__ == "__main__":
    CCIClinicalScraper().run()

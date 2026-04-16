"""
Scraper: Mayo Clinic — Diseases & Conditions
URL   : https://www.mayoclinic.org/diseases-conditions
License: © Mayo Foundation for Medical Education and Research — educational/non-commercial use

Each condition has two sub-pages on Mayo Clinic:
  • symptoms-causes      → overview, symptoms, causes, risk factors
  • diagnosis-treatment  → diagnosis, treatment, coping/support

Both URLs are hardcoded because Mayo Clinic appends opaque numeric IDs
(e.g. syc-20356007, drc-20356013) that differ per condition.

NOTE: Mayo Clinic uses Cloudflare WAF which blocks standard requests based on
TLS fingerprint. This scraper uses curl_cffi to impersonate Chrome at the
TLS level, bypassing the 403 block.

Install:  pip install curl_cffi
"""
import random
import sys
import time
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.mayoclinic.org"

# condition display name → {icd11, aliases, pages{tab: url}}
CONDITION_PAGES = {
    "Depression": {
        "icd11": "6A70",
        "aliases": ["MDD", "major depressive disorder", "clinical depression"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/depression/symptoms-causes/syc-20356007",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/depression/diagnosis-treatment/drc-20356013",
        },
    },
    "Generalised Anxiety Disorder": {
        "icd11": "6B00",
        "aliases": ["GAD", "generalised anxiety", "generalized anxiety disorder"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/generalized-anxiety-disorder/symptoms-causes/syc-20360803",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/generalized-anxiety-disorder/diagnosis-treatment/drc-20361045",
        },
    },
    "Panic Disorder": {
        "icd11": "6B01",
        "aliases": ["panic attacks", "panic attack disorder"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/panic-attacks/symptoms-causes/syc-20376021",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/panic-attacks/diagnosis-treatment/drc-20376027",
        },
    },
    "Social Anxiety Disorder": {
        "icd11": "6B04",
        "aliases": ["social phobia", "social anxiety"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/social-anxiety-disorder/symptoms-causes/syc-20353561",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/social-anxiety-disorder/diagnosis-treatment/drc-20353561",
        },
    },
    "PTSD": {
        "icd11": "6B40",
        "aliases": ["post-traumatic stress disorder", "post traumatic stress"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/post-traumatic-stress-disorder/symptoms-causes/syc-20355967",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/post-traumatic-stress-disorder/diagnosis-treatment/drc-20355969",
        },
    },
    "OCD": {
        "icd11": "6B20",
        "aliases": ["obsessive-compulsive disorder", "obsessive compulsive disorder"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/obsessive-compulsive-disorder/symptoms-causes/syc-20354432",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/obsessive-compulsive-disorder/diagnosis-treatment/drc-20354438",
        },
    },
    "Bipolar Disorder": {
        "icd11": "6A60",
        "aliases": ["bipolar", "manic depression", "manic-depressive illness"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/bipolar-disorder/symptoms-causes/syc-20355955",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/bipolar-disorder/diagnosis-treatment/drc-20355961",
        },
    },
    "Schizophrenia": {
        "icd11": "6A20",
        "aliases": [],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/schizophrenia/symptoms-causes/syc-20354443",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/schizophrenia/diagnosis-treatment/drc-20354449",
        },
    },
    "Anorexia Nervosa": {
        "icd11": "6B80",
        "aliases": ["anorexia", "AN"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/anorexia-nervosa/symptoms-causes/syc-20353591",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/anorexia-nervosa/diagnosis-treatment/drc-20353597",
        },
    },
    "Bulimia Nervosa": {
        "icd11": "6B81",
        "aliases": ["bulimia", "BN"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/bulimia/symptoms-causes/syc-20353615",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/bulimia/diagnosis-treatment/drc-20353621",
        },
    },
    "Binge Eating Disorder": {
        "icd11": "6B82",
        "aliases": ["BED", "compulsive overeating"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/binge-eating-disorder/symptoms-causes/syc-20353627",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/binge-eating-disorder/diagnosis-treatment/drc-20353633",
        },
    },
    "ADHD": {
        "icd11": "6A05",
        "aliases": ["attention deficit hyperactivity disorder", "ADD", "attention deficit disorder"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/adhd/symptoms-causes/syc-20350889",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/adhd/diagnosis-treatment/drc-20350891",
        },
    },
    "Autism Spectrum Disorder": {
        "icd11": "6A02",
        "aliases": ["ASD", "autism", "Asperger's"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/autism-spectrum-disorder/symptoms-causes/syc-20352928",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/autism-spectrum-disorder/diagnosis-treatment/drc-20352934",
        },
    },
    "Borderline Personality Disorder": {
        "icd11": "6D11",
        "aliases": ["BPD", "EUPD", "emotionally unstable personality disorder"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/borderline-personality-disorder/symptoms-causes/syc-20370237",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/borderline-personality-disorder/diagnosis-treatment/drc-20370242",
        },
    },
    "Seasonal Affective Disorder": {
        "icd11": "6A70",
        "aliases": ["SAD", "seasonal depression", "winter depression"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/seasonal-affective-disorder/symptoms-causes/syc-20364651",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/seasonal-affective-disorder/diagnosis-treatment/drc-20364794",
        },
    },
    "Postpartum Depression": {
        "icd11": "6A70",
        "aliases": ["postnatal depression", "PND", "PPD"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/postpartum-depression/symptoms-causes/syc-20376617",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/postpartum-depression/diagnosis-treatment/drc-20376623",
        },
    },
    "Specific Phobias": {
        "icd11": "6B03",
        "aliases": ["phobia", "specific phobia"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/specific-phobias/symptoms-causes/syc-20355067",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/specific-phobias/diagnosis-treatment/drc-20355073",
        },
    },
    "Insomnia": {
        "icd11": "7A00",
        "aliases": ["sleep disorder", "sleeplessness"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/insomnia/symptoms-causes/syc-20355167",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/insomnia/diagnosis-treatment/drc-20355173",
        },
    },
    "Burnout": {
        "icd11": None,
        "aliases": ["occupational burnout", "work burnout"],
        "pages": {
            "symptoms_causes":     f"{BASE}/diseases-conditions/burnout/symptoms-causes/syc-20456627",
            "diagnosis_treatment": f"{BASE}/diseases-conditions/burnout/diagnosis-treatment/drc-20456634",
        },
    },
}

# Keyword → section label for "symptoms-causes" tab
SYMPTOMS_CAUSES_KEYWORDS = {
    "overview":      ["overview", "what is", "about"],
    "symptoms":      ["symptom", "sign", "when to see"],
    "causes":        ["cause", "what causes"],
    "risk_factors":  ["risk factor", "who is at risk"],
}

# Keyword → section label for "diagnosis-treatment" tab
DIAGNOSIS_TREATMENT_KEYWORDS = {
    "diagnosis":        ["diagnos", "how is", "tests"],
    "treatment":        ["treat", "therap", "medication", "help", "option"],
    "self_help":        ["self-care", "coping", "lifestyle", "alternative", "home remedy"],
    "when_to_seek_help": ["prepare", "what you can do", "questions to ask"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer",
    ".main-navigation", ".utility-navigation",
    ".breadcrumb", ".breadcrumbs",
    ".related-links", ".related-content",
    ".social-share", ".share-bar",
    ".patient-tools", ".tools-bar",
    ".ads-area", ".advertisement",
    "script", "style", "noscript",
    "#header", "#footer", "#nav",
    "[class*='sidebar']",
]


class MayoClinicScraper(BaseScraper):
    """
    Scraper for Mayo Clinic diseases-conditions pages.

    Uses curl_cffi instead of the requests-based BaseScraper.get() because
    Mayo Clinic's Cloudflare WAF rejects requests whose TLS fingerprint does
    not match a real browser.  curl_cffi impersonates Chrome at the TLS
    handshake level, which resolves the 403.
    """

    def __init__(self):
        super().__init__("mayo_clinic", "db1_clinical")
        # curl_cffi session shared across all requests
        self._cffi_session = cffi_requests.Session()

    # ------------------------------------------------------------------
    # Override HTTP fetch to use curl_cffi
    # ------------------------------------------------------------------

    def get(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        for attempt in range(retries):
            try:
                resp = self._cffi_session.get(
                    url,
                    impersonate="chrome124",
                    timeout=20,
                )
                resp.raise_for_status()
                time.sleep(random.uniform(*self.delay))
                return BeautifulSoup(resp.text, "lxml")
            except Exception as exc:
                self.log.warning(
                    "Attempt %d/%d failed for %s: %s", attempt + 1, retries, url, exc
                )
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))
        self.log.error("All retries exhausted for %s", url)
        return None

    KEEP_SECTIONS = {
        "symptoms", "causes", "risk_factors",
        "diagnosis", "treatment", "self_help",
    }

    # ------------------------------------------------------------------
    # Main scrape loop
    # ------------------------------------------------------------------

    def run(self) -> list:
        records = []
        for condition, meta in CONDITION_PAGES.items():
            self.log.info("Condition: %s", condition)
            for tab, url in meta["pages"].items():
                self.log.info("  Tab: %s", tab)
                soup = self.get(url)
                if soup is None:
                    continue

                # Detect soft 404s — Mayo returns HTTP 200 with "Page not found" title
                title_tag = soup.find("title")
                if title_tag and "not found" in title_tag.get_text().lower():
                    self.log.warning("  Soft 404 — skipping: %s", url)
                    continue

                self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)

                keywords = (
                    SYMPTOMS_CAUSES_KEYWORDS
                    if tab == "symptoms_causes"
                    else DIAGNOSIS_TREATMENT_KEYWORDS
                )
                sections = self._extract_sections(soup)

                for heading, content in sections.items():
                    if not content or len(content) < 80:
                        continue
                    section_label = self._classify_section(heading, keywords)
                    if section_label not in self.KEEP_SECTIONS:
                        continue
                    records.append({
                        "condition":    condition,
                        "aliases":      meta["aliases"],
                        "source":       "Mayo Clinic",
                        "source_url":   url,
                        "section":      section_label,
                        "content":      content,
                        "icd11_code":   meta["icd11"],
                        "last_scraped": self.today(),
                    })

            self.log.info("  Running total: %d records", len(records))

        self.save(records, "mayo_clinic_clinical.json")
        return records

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _extract_sections(self, soup) -> dict:
        """
        Mayo Clinic pages divide content with h2/h3 headings inside a main
        content area.  We accumulate text between heading boundaries.
        """
        main = soup.select_one(
            "#main-content, .main-content, "
            "article, [class*='content-body'], "
            "[class*='article-body'], main"
        )
        if main is None:
            main = soup.find("body") or soup

        sections: dict = {}
        current_heading = "overview"
        current_chunks: list = []

        for el in main.find_all(["h2", "h3", "p", "ul", "ol", "dl"]):
            if el.name in ("h2", "h3"):
                heading_text = el.get_text(strip=True)
                if heading_text:
                    if current_chunks:
                        body = self.clean(" ".join(current_chunks))
                        if body:
                            sections[current_heading] = body
                    current_heading = heading_text.lower()
                    current_chunks = []
            else:
                chunk = el.get_text(separator=" ", strip=True)
                if chunk:
                    current_chunks.append(chunk)

        if current_chunks:
            body = self.clean(" ".join(current_chunks))
            if body:
                sections[current_heading] = body

        return sections

    def _classify_section(self, heading: str, keywords: dict) -> str:
        h = heading.lower()
        for label, kws in keywords.items():
            if any(kw in h for kw in kws):
                return label
        return "other"


if __name__ == "__main__":
    MayoClinicScraper().run()

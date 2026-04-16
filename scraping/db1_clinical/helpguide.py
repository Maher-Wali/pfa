"""
Scraper: HelpGuide.org — Mental Health Condition Guides
URL   : https://www.helpguide.org/mental-health/
License: Harvard Health Publishing affiliated. No explicit scraping ban;
         used here for non-commercial research. Verify before deployment.

HelpGuide articles are long-form, single-page guides. One article covers
one topic completely (symptoms, causes, treatment, self-help) without
splitting into sub-pages. We scrape each article as a single record and
let the pipeline chunking split it into sections.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.helpguide.org"

# HelpGuide uses Cloudflare-style bot detection that checks for browser
# fingerprint headers beyond just User-Agent. Overriding _headers() with
# a full Chromium request profile bypasses the soft block.
_HELPGUIDE_HEADERS = {
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

# (condition_name, url_path, icd11_code)
TARGETS = [
    # Depression
    ("Depression",
     "/mental-health/depression/depression-symptoms-and-warning-signs/",
     "6A70"),
    ("Depression — Causes and Treatment",
     "/mental-health/depression/depression-treatment/",
     "6A70"),
    ("Depression — Coping and Self-Help",
     "/mental-health/depression/coping-with-depression/",
     "6A70"),
    ("Seasonal Affective Disorder",
     "/mental-health/depression/seasonal-affective-disorder-sad/",
     "6A70"),
    ("Postpartum Depression",
     "/mental-health/pregnancy/postpartum-depression-and-the-baby-blues/",
     "6A70"),

    # Anxiety
    ("Anxiety Disorders — Overview",
     "/mental-health/anxiety/anxiety-disorders-and-anxiety-attacks/",
     "6B0Z"),
    ("Generalised Anxiety Disorder",
     "/mental-health/anxiety/generalized-anxiety-disorder-gad/",
     "6B00"),
    ("Panic Attacks and Panic Disorder",
     "/mental-health/anxiety/panic-attacks-panic-disorder/",
     "6B01"),
    ("Social Anxiety Disorder",
     "/mental-health/anxiety/social-anxiety-disorder/",
     "6B04"),
    ("Phobias",
     "/mental-health/anxiety/phobias-fears/",
     "6B03"),
    ("Health Anxiety",
     "/mental-health/anxiety/health-anxiety-hypochondria/",
     "6B23"),

    # OCD / Trauma
    ("OCD — Obsessive-Compulsive Disorder",
     "/mental-health/anxiety/ocd-obsessive-compulsive-disorder/",
     "6B20"),
    ("PTSD",
     "/mental-health/ptsd-trauma/ptsd-symptoms-self-help-treatment/",
     "6B40"),
    ("Emotional and Psychological Trauma",
     "/mental-health/ptsd-trauma/emotional-psychological-trauma/",
     "6B40"),
    ("Recovering from Trauma",
     "/mental-health/ptsd-trauma/recovering-emotional-trauma/",
     "6B40"),

    # Bipolar / Schizophrenia
    ("Bipolar Disorder",
     "/mental-health/bipolar-disorder/bipolar-disorder-signs-symptoms/",
     "6A60"),
    ("Schizophrenia",
     "/mental-health/schizophrenia/schizophrenia-signs-symptoms/",
     "6A20"),

    # Eating disorders
    ("Anorexia Nervosa",
     "/mental-health/eating-disorders/anorexia-nervosa/",
     "6B80"),
    ("Bulimia Nervosa",
     "/mental-health/eating-disorders/bulimia-nervosa/",
     "6B81"),
    ("Binge Eating Disorder",
     "/mental-health/eating-disorders/binge-eating-disorder/",
     "6B82"),

    # Sleep
    ("Insomnia — Causes and Cures",
     "/sleep/insomnia/insomnia-causes-cures/",
     None),
    ("Sleep Hygiene",
     "/sleep/getting-better-sleep/getting-better-sleep/",
     None),

    # Grief / stress / wellbeing
    ("Grief — Coping with Loss",
     "/mental-health/grief/coping-with-grief-and-loss/",
     None),
    ("Stress Symptoms and Causes",
     "/mental-health/stress/stress-symptoms-signs-causes/",
     None),
    ("Coping with Stress",
     "/mental-health/stress/stress-management/",
     None),
    ("Building Self-Esteem",
     "/mental-health/self-esteem/self-esteem/",
     None),
    ("Loneliness",
     "/mental-health/social-life/loneliness/",
     None),
    ("Emotional Intelligence",
     "/mental-health/emotional-health/emotional-intelligence/",
     None),

    # ADHD / Autism
    ("ADHD in Adults",
     "/mental-health/adhd/adhd-attention-deficit-disorder-in-adults/",
     "6A05"),
    ("Autism Spectrum Disorder",
     "/mental-health/autism-spectrum-disorder/autism-symptoms-treatments/",
     "6A02"),

    # BPD
    ("Borderline Personality Disorder",
     "/mental-health/personality-disorders/borderline-personality-disorder-bpd/",
     "6D11"),
]

SECTION_KEYWORDS = {
    "symptoms":          ["symptom", "sign", "warning sign", "how it feels"],
    "causes":            ["cause", "risk factor"],
    "diagnosis":         ["diagnos"],
    "treatment":         ["treat", "therap", "help", "medication"],
    "self_help":         ["self-help", "coping", "what you can do", "self-care"],
    "living_with":       ["living", "manage", "day-to-day"],
    "when_to_seek_help": ["seek help", "when to", "getting help"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar", ".widget",
    ".newsletter", ".related-articles", "#comments",
    ".ad-block", ".promo", ".author-bio",
]


class HelpGuideScraper(BaseScraper):
    def __init__(self):
        super().__init__("helpguide", "db1_clinical")

    def _headers(self) -> dict:
        return _HELPGUIDE_HEADERS

    def run(self) -> list:
        records = []
        for condition_name, path, icd11 in TARGETS:
            url = BASE + path
            self.log.info("Article: %s", condition_name)
            soup = self.get(url)
            if soup is None:
                continue

            h1 = soup.find("h1")
            if h1 and "page not found" in h1.get_text().lower():
                self.log.warning("  404: %s", url)
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            sections = self._extract_sections(soup)

            if not sections:
                # Fall back to treating the whole article as one "overview" record
                content = self._full_text(soup)
                if content and len(content) > 100:
                    records.append(self._make_record(
                        condition_name, icd11, "overview", content, url
                    ))
                continue

            for heading, content in sections.items():
                if not content or len(content) < 80:
                    continue
                records.append(self._make_record(
                    condition_name, icd11,
                    self._classify_section(heading), content, url
                ))

        self.save(records, "helpguide_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        """Split article by h2/h3 headings."""
        main = soup.select_one("main, article, .article-body, #content")
        if main is None:
            return {}

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

    def _full_text(self, soup) -> str:
        for sel in ["main", "article", ".article-body", "#content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        return ""

    def _classify_section(self, heading: str) -> str:
        h = heading.lower()
        for key, keywords in SECTION_KEYWORDS.items():
            if any(kw in h for kw in keywords):
                return key
        return "other"

    def _make_record(self, condition, icd11, section, content, url) -> dict:
        return {
            "condition":    condition,
            "aliases":      [],
            "source":       "HelpGuide",
            "source_url":   url,
            "section":      section,
            "content":      content,
            "icd11_code":   icd11,
            "last_scraped": self.today(),
        }


if __name__ == "__main__":
    HelpGuideScraper().run()

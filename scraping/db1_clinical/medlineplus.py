"""
Scraper: MedlinePlus — US National Library of Medicine
URL   : https://medlineplus.gov
License: US government work — public domain.

MedlinePlus health topic pages give plain-language condition overviews
(symptoms, causes, diagnosis, treatment) compiled by the NLM from
authoritative sources. No bot protection — .gov domain, static HTML.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://medlineplus.gov"

# (condition_name, url_slug, icd11_code)
TARGETS = [
    ("Depression",                      "/depression.html",                  "6A70"),
    ("Anxiety",                         "/anxiety.html",                     "6B0Z"),
    ("Generalised Anxiety Disorder",    "/generalizedanxietydisorder.html",  "6B00"),
    ("Panic Disorder",                  "/panicdisorder.html",               "6B01"),
    ("Social Anxiety Disorder",         "/socialanxietydisorder.html",       "6B04"),
    ("Phobias",                         "/phobias.html",                     "6B03"),
    ("OCD",                             "/obsessivecompulsivedisorder.html", "6B20"),
    ("PTSD",                            "/post-traumaticstressdisorder.html","6B40"),
    ("Bipolar Disorder",                "/bipolardisorder.html",             "6A60"),
    ("Schizophrenia",                   "/schizophrenia.html",               "6A20"),
    ("Eating Disorders",                "/eatingdisorders.html",             "6B8Z"),
    ("ADHD",                            "/attentiondeficithyperactivitydisorder.html", "6A05"),
    ("Borderline Personality Disorder", "/borderlinepersonalitydisorder.html","6D11"),
    ("Seasonal Affective Disorder",     "/seasonalaffectivedisorder.html",   "6A70"),
    ("Self-Harm",                       "/selfharm.html",                    None),
    ("Suicide Prevention",              "/suicideprevention.html",           None),
    ("Stress",                          "/stress.html",                      None),
    ("Sleep Disorders",                 "/sleepdisorders.html",              None),
]

SECTION_KEYWORDS = {
    "overview":          ["what is", "about", "overview", "summary"],
    "symptoms":          ["symptom", "sign", "how does it feel", "experience"],
    "causes":            ["cause", "risk", "factor", "why"],
    "diagnosis":         ["diagnos", "test", "evaluat"],
    "treatment":         ["treat", "therap", "medication", "help", "manage"],
    "self_help":         ["self-help", "coping", "what can", "lifestyle"],
    "when_to_seek_help": ["seek help", "when to", "call", "emergency"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", "#footer", "#header",
    ".breadcrumb", "script", "style", "#side-nav",
    ".section-related-topics", "#also-called",
]


class MedlinePlusScraper(BaseScraper):
    def __init__(self):
        super().__init__("medlineplus", "db1_clinical")

    def run(self) -> list:
        records = []
        for condition_name, slug, icd11 in TARGETS:
            url = BASE + slug
            self.log.info("Page: %s", condition_name)
            soup = self.get(url)
            if soup is None:
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            sections = self._extract_sections(soup)

            for heading, content in sections.items():
                if not content or len(content.split()) < 30:
                    continue
                records.append({
                    "condition":    condition_name,
                    "aliases":      [],
                    "source":       "MedlinePlus",
                    "source_url":   url,
                    "section":      self._classify_section(heading),
                    "content":      content,
                    "icd11_code":   icd11,
                    "last_scraped": self.today(),
                })

        self.log.info("Total: %d records", len(records))
        self.save(records, "medlineplus_clinical.json")
        return records

    def _extract_sections(self, soup) -> dict:
        # MedlinePlus wraps each topic section in <div class="section">
        # with an <h2> heading and prose in <p> / <ul> tags below.
        sections: dict = {}

        for section_div in soup.select("div.section, section"):
            h = section_div.find(["h2", "h3"])
            heading = h.get_text(strip=True).lower() if h else "overview"
            paras = [
                el.get_text(separator=" ", strip=True)
                for el in section_div.find_all(["p", "li"])
                if el.get_text(strip=True)
            ]
            content = self.clean(" ".join(paras))
            if content:
                sections[heading] = sections.get(heading, "") + " " + content

        # Fallback: grab the summary block
        if not sections:
            summary = soup.select_one("#ency-summary, .health-topic-summary, main")
            if summary:
                sections["overview"] = self.clean(
                    summary.get_text(separator=" ", strip=True)
                )

        return sections

    def _classify_section(self, heading: str) -> str:
        h = heading.lower()
        for key, keywords in SECTION_KEYWORDS.items():
            if any(kw in h for kw in keywords):
                return key
        return "other"


if __name__ == "__main__":
    MedlinePlusScraper().run()

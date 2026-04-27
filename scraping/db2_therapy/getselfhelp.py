"""
Scraper: GetSelfHelp — CBT Self-Help Resources
URL   : https://www.getselfhelp.co.uk
License: Free for personal and clinical use (Carol Kennerley / BABCP)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text

BASE = "https://www.getselfhelp.co.uk"

# HTML pages — CBT technique explanations
HTML_PAGES = [
    ("CBT Overview",                  "/cbt.htm",                          "CBT"),
    ("Thought Records — Overview",    "/thoughtrecords.htm",               "CBT"),
    ("Cognitive Distortions",         "/unhelpfulthinking.htm",            "CBT"),
    ("Behavioural Activation",        "/behaviouralactivation.htm",        "CBT"),
    ("Graded Exposure",               "/exposure.htm",                     "CBT"),
    ("Problem Solving",               "/problemsolving.htm",               "CBT"),
    ("Sleep Hygiene",                 "/sleep.htm",                        "behavioral"),
    ("Worry — Overview",              "/worry.htm",                        "CBT"),
    ("Worry Time",                    "/worrytime.htm",                    "CBT"),
    ("Relaxation Overview",           "/relax.htm",                        "relaxation"),
    ("Breathing Exercises",           "/breathe.htm",                      "relaxation"),
    ("Progressive Muscle Relaxation", "/pmr.htm",                          "relaxation"),
    ("Grounding Techniques",          "/grounding.htm",                    "relaxation"),
    ("Mindfulness Introduction",      "/mindfulness.htm",                  "MBSR"),
    ("Assertiveness",                 "/assertive.htm",                    "interpersonal"),
    ("Self-Esteem",                   "/self-esteem.htm",                  "CBT"),
    ("Anger Management",              "/anger.htm",                        "CBT"),
    ("Grief and Loss",                "/grief.htm",                        "CBT"),
    ("Flashbacks — Managing PTSD",    "/flashbacks.htm",                   "CBT"),
    ("Panic — Understanding and Managing", "/panic.htm",                   "CBT"),
    ("Social Anxiety — Self-Help",    "/socialanxiety.htm",                "CBT"),
    ("OCD — Self-Help Overview",      "/ocd.htm",                          "CBT"),
    ("Depression — Self-Help",        "/depression.htm",                   "CBT"),
]

# PDF worksheets — /docs/ path was removed in 2025 site restructure, all 404
PDF_WORKSHEETS = []

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".menu", "#menu",
    "script", "style", ".copyright",
]


class GetSelfHelpScraper(BaseScraper):
    def __init__(self):
        super().__init__("getselfhelp", "db2_therapy")

    def run(self) -> list:
        records = []
        records.extend(self._scrape_html())
        records.extend(self._scrape_pdfs())
        self.save(records, "getselfhelp_therapy.json")
        return records

    def _scrape_html(self) -> list:
        records = []
        for technique_name, path, modality in HTML_PAGES:
            url = BASE + path
            self.log.info("HTML: %s", technique_name)
            soup = self.get(url)
            if soup is None:
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)

            # GetSelfHelp is an older site — content is mostly in the body
            # with minimal structural markup
            main = soup.find("body")
            if main is None:
                continue

            content = self.clean(main.get_text(separator=" "))
            if not content or len(content) < 100:
                continue

            records.append({
                "technique_name":    technique_name,
                "aliases":           [],
                "modality":          modality,
                "target_conditions": [],
                "target_problem":    None,
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       content,
                "source":            "GetSelfHelp",
                "source_url":        url,
                "last_scraped":      self.today(),
            })
        return records

    def _scrape_pdfs(self) -> list:
        records = []
        for technique_name, path, modality in PDF_WORKSHEETS:
            url = BASE + path
            self.log.info("PDF: %s", technique_name)
            raw = self.download_bytes(url)
            if raw is None:
                continue

            text = extract_text(raw)
            if not text or len(text) < 50:
                continue

            records.append({
                "technique_name":    technique_name,
                "aliases":           [],
                "modality":          modality,
                "target_conditions": [],
                "target_problem":    None,
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       self.clean(text),
                "source":            "GetSelfHelp",
                "source_url":        url,
                "last_scraped":      self.today(),
            })
        return records


if __name__ == "__main__":
    GetSelfHelpScraper().run()

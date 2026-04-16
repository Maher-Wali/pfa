"""
Scraper: Positive Psychology — Technique Articles
URL   : https://positivepsychology.com
License: Free articles (standard web terms — educational/research use)
Notes  : We target specific high-quality technique articles rather than
         bulk-crawling the site. Only evidence-based PPT tools are included.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://positivepsychology.com"

# Curated list: technique-focused articles only.
# Each tuple: (technique_name, url_path, modality)
TARGETS = [
    # Gratitude
    ("Three Good Things",
     "/three-good-things/",                                     "PPT"),
    ("Gratitude Journal",
     "/gratitude-journal/",                                     "PPT"),
    ("Gratitude Letter",
     "/gratitude-letter/",                                      "PPT"),

    # Savoring
    ("Savoring",
     "/savoring/",                                              "PPT"),

    # Best Possible Self
    ("Best Possible Self",
     "/best-possible-self/",                                    "PPT"),

    # Strengths
    ("Character Strengths and VIA",
     "/via-character-strengths/",                               "PPT"),
    ("Strengths-Based Interventions",
     "/strengths-based-interventions/",                         "PPT"),

    # Acts of kindness
    ("Acts of Kindness",
     "/random-acts-of-kindness/",                               "PPT"),

    # Mindfulness / positive
    ("Mindfulness-Based Cognitive Therapy (MBCT)",
     "/mindfulness-based-cognitive-therapy/",                   "MBSR"),
    ("Mindfulness Exercises",
     "/mindfulness-exercises/",                                 "MBSR"),
    ("Body Scan Meditation",
     "/body-scan-meditation/",                                  "MBSR"),
    ("STOP Technique",
     "/stop-technique-mindfulness/",                            "MBSR"),
    ("3-Minute Breathing Space",
     "/3-minute-breathing-space/",                              "MBSR"),

    # Flourishing / wellbeing
    ("PERMA Model",
     "/perma-model/",                                           "PPT"),
    ("Flourishing",
     "/flourishing/",                                           "PPT"),
    ("Hedonic vs Eudaimonic Wellbeing",
     "/hedonic-eudaimonic-well-being/",                         "PPT"),

    # Self-compassion
    ("Self-Compassion Exercises",
     "/self-compassion-exercises/",                             "MSC"),

    # Positive CBT
    ("Behavioural Activation",
     "/behavioral-activation/",                                 "CBT"),
    ("Activity Scheduling",
     "/activity-scheduling/",                                   "CBT"),
    ("Expressive Writing (Pennebaker)",
     "/expressive-writing/",                                    "behavioral"),
]

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar", ".widget",
    ".newsletter-form", ".related-posts", "#comments",
    ".author-bio", ".share-buttons",
]


class PositivePsychologyScraper(BaseScraper):
    def __init__(self):
        # positivepsychology.com can be slow — use a longer timeout via delay
        super().__init__("positive_psychology", "db2_therapy", delay_range=(2.0, 4.0))

    def run(self) -> list:
        records = []
        for technique_name, path, modality in TARGETS:
            url = BASE + path
            self.log.info("Scraping: %s", technique_name)
            soup = self.get(url)
            if soup is None:
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            content = self._extract_content(soup)
            if not content or len(content) < 150:
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
                "source":            "Positive Psychology",
                "source_url":        url,
                "last_scraped":      self.today(),
            })

        self.save(records, "positive_psychology_therapy.json")
        return records

    def _extract_content(self, soup) -> str:
        # positivepsychology.com uses article tags and .entry-content divs
        for sel in ["article", ".entry-content", "main",
                    ".post-content", "#content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""


if __name__ == "__main__":
    PositivePsychologyScraper().run()

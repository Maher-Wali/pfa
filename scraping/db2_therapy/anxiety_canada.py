"""
Scraper: Anxiety Canada — Technique Guides
URL   : https://www.anxietycanada.com
License: Free non-commercial educational use
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.anxietycanada.com"

TARGETS = [
    # Anxiety-specific CBT tools
    ("Facing Fears — Graded Exposure",
     "/articles/facing-your-fears-graded-exposure/", "CBT"),
    ("Building an Exposure Ladder",
     "/articles/building-an-exposure-ladder/", "CBT"),
    ("Relaxation — Slow Breathing",
     "/articles/slow-breathing/", "relaxation"),
    ("Relaxation — Progressive Muscle Relaxation",
     "/articles/progressive-muscle-relaxation/", "relaxation"),
    ("Worry Time",
     "/articles/worry-time/", "CBT"),
    ("Problem Solving for Anxiety",
     "/articles/problem-solving/", "CBT"),
    ("Challenging Anxious Thoughts",
     "/articles/challenging-anxious-thoughts/", "CBT"),
    ("Safety Behaviours — What They Are and Why to Reduce Them",
     "/articles/safety-behaviours/", "CBT"),
    ("Sleep and Anxiety",
     "/articles/sleep-and-anxiety/", "behavioral"),
    ("Mindfulness for Anxiety",
     "/articles/mindfulness/", "MBSR"),
    ("Acceptance of Uncertainty",
     "/articles/accepting-uncertainty/", "ACT"),
    ("Self-Care for Anxiety",
     "/articles/self-care-for-anxiety/", "behavioral"),

    # Condition-specific guides
    ("Managing GAD",
     "/learn-about-anxiety/generalized-anxiety-disorder/", "CBT"),
    ("Managing Panic",
     "/learn-about-anxiety/panic-disorder/", "CBT"),
    ("Managing Social Anxiety",
     "/learn-about-anxiety/social-anxiety-disorder/", "CBT"),
    ("Managing OCD",
     "/learn-about-anxiety/ocd/", "CBT"),
    ("Managing Health Anxiety",
     "/learn-about-anxiety/illness-anxiety/", "CBT"),
    ("Managing Specific Phobias",
     "/learn-about-anxiety/specific-phobia/", "CBT"),
    ("Managing PTSD",
     "/learn-about-anxiety/post-traumatic-stress-disorder-ptsd/", "CBT"),
]

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".widget", ".sidebar",
    ".newsletter", ".cta-block",
]


class AnxietyCanadaScraper(BaseScraper):
    def __init__(self):
        super().__init__("anxiety_canada", "db2_therapy")

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
            if not content or len(content) < 100:
                continue

            records.append({
                "technique_name":    technique_name,
                "aliases":           [],
                "modality":          modality,
                "target_conditions": ["anxiety"],
                "target_problem":    None,
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       content,
                "source":            "Anxiety Canada",
                "source_url":        url,
                "last_scraped":      self.today(),
            })

        self.save(records, "anxiety_canada_therapy.json")
        return records

    def _extract_content(self, soup) -> str:
        for sel in ["main", "article", ".entry-content",
                    ".page-content", "#content", ".content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""


if __name__ == "__main__":
    AnxietyCanadaScraper().run()

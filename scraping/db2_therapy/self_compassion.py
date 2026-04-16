"""
Scraper: Self-Compassion.org — Kristin Neff's Exercises
URL   : https://self-compassion.org
License: Exercises available for free use (stated on site)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://self-compassion.org"

TARGETS = [
    # Core MSC exercises
    ("Self-Compassion Break",
     "/self-compassion-exercises-and-meditations/", "MSC"),
    ("Loving-Kindness Meditation (Metta)",
     "/exercise-6-loving-kindness-meditation/",     "MSC"),
    ("Soften-Soothe-Allow",
     "/exercise-soften-soothe-allow/",              "MSC"),
    ("Affectionate Breathing",
     "/exercise-affectionate-breathing/",           "MSC"),
    ("Compassionate Body Scan",
     "/exercise-compassionate-body-scan/",          "MSC"),
    ("Self-Compassionate Letter",
     "/exercise-3-exploring-self-compassion-writing/", "MSC"),
    ("Common Humanity — Writing Exercise",
     "/exercise-8-finding-self-compassion-in-difficult-emotions/", "MSC"),
    ("Changing Your Critical Self-Talk",
     "/exercise-2-critical-self-talk/",             "MSC"),
    ("Taking Care of the Caregiver",
     "/exercise-4-caregiver-compassion-fatigue/",   "MSC"),
    ("Self-Compassion Journal",
     "/self-compassion-journal/",                   "MSC"),
    # Informational pages
    ("What is Self-Compassion?",
     "/the-three-elements-of-self-compassion-2/",   "MSC"),
    ("Self-Compassion vs Self-Esteem",
     "/self-compassion-versus-self-esteem/",        "MSC"),
    ("Research Summary",
     "/category/relevant-research-2/",             "MSC"),
]

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".widget-area", ".sidebar",
    ".related-posts", "#comments",
]


class SelfCompassionScraper(BaseScraper):
    def __init__(self):
        super().__init__("self_compassion", "db2_therapy")

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
                "aliases":           self._get_aliases(technique_name),
                "modality":          modality,
                "target_conditions": ["depression", "low self-esteem", "shame", "anxiety"],
                "target_problem":    None,
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       content,
                "source":            "Self-Compassion.org",
                "source_url":        url,
                "last_scraped":      self.today(),
            })

        self.save(records, "self_compassion_therapy.json")
        return records

    def _extract_content(self, soup) -> str:
        for sel in ["main", "article", ".entry-content",
                    ".page-content", "#content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""

    def _get_aliases(self, name: str) -> list:
        alias_map = {
            "Loving-Kindness Meditation (Metta)": ["Metta", "LKM", "loving kindness"],
            "Self-Compassion Break":              ["MSC break", "Neff break"],
            "Self-Compassionate Letter":          ["compassion letter writing"],
        }
        return alias_map.get(name, [])


if __name__ == "__main__":
    SelfCompassionScraper().run()

"""
Scraper: Simply Psychology — Therapy Technique Articles
URL   : https://www.simplypsychology.org
License: Standard web terms — educational/research use

URL structure change (confirmed): old .html URLs return soft 404.
All paths are now clean slugs without extension.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.simplypsychology.org"

# All paths are clean slugs — no .html extension
TARGETS = [
    # CBT core
    ("Cognitive Behavioural Therapy — Overview",
     "/cognitive-behavioral-therapy",  "CBT"),
    ("Cognitive Restructuring",
     "/cognitive-restructuring",       "CBT"),
    ("Cognitive Distortions",
     "/cognitive-distortions",         "CBT"),
    ("Behavioural Activation",
     "/behavioral-activation",         "CBT"),
    ("Exposure Therapy",
     "/exposure-therapy",              "CBT"),
    ("Systematic Desensitisation",
     "/systematic-desensitization",    "CBT"),
    ("Graded Exposure",
     "/graded-exposure",               "CBT"),
    ("Psychoeducation",
     "/psychoeducation",               "CBT"),
    ("Problem-Solving Therapy",
     "/problem-solving-therapy",       "CBT"),
    ("Thought Record",
     "/thought-record",                "CBT"),
    ("ABC Model",
     "/abc-model",                     "CBT"),
    ("Behavioural Experiment",
     "/behavioral-experiments",        "CBT"),
    ("Motivational Interviewing",
     "/motivational-interviewing",     "CBT"),

    # DBT
    ("Dialectical Behaviour Therapy — Overview",
     "/dbt",                           "DBT"),
    ("Radical Acceptance",
     "/radical-acceptance",            "DBT"),
    ("Distress Tolerance",
     "/distress-tolerance",            "DBT"),
    ("Emotion Regulation (DBT)",
     "/emotion-regulation",            "DBT"),
    ("Interpersonal Effectiveness (DBT)",
     "/interpersonal-effectiveness",   "DBT"),

    # ACT
    ("Acceptance and Commitment Therapy — Overview",
     "/act-therapy",                   "ACT"),
    ("Cognitive Defusion",
     "/cognitive-defusion",            "ACT"),
    ("Psychological Flexibility",
     "/psychological-flexibility",     "ACT"),

    # Mindfulness / MBSR
    ("Mindfulness-Based Cognitive Therapy",
     "/mbct",                          "MBSR"),
    ("Mindfulness-Based Stress Reduction",
     "/mindfulness-based-stress-reduction-mbsr", "MBSR"),
    ("Body Scan Meditation",
     "/body-scan-meditation",          "MBSR"),
    ("Mindfulness",
     "/mindfulness",                   "MBSR"),

    # Relaxation / grounding
    ("Progressive Muscle Relaxation",
     "/progressive-muscle-relaxation", "relaxation"),
    ("Diaphragmatic Breathing",
     "/diaphragmatic-breathing",       "relaxation"),
    ("Grounding Techniques",
     "/grounding-techniques",          "relaxation"),
    ("Guided Imagery",
     "/guided-imagery",                "relaxation"),

    # Self-compassion / PPT
    ("Self-Compassion",
     "/self-compassion",               "MSC"),
    ("Loving-Kindness Meditation",
     "/loving-kindness-meditation",    "MSC"),
    ("Positive Psychology — Overview",
     "/positive-psychology",           "PPT"),
    ("Gratitude Interventions",
     "/gratitude",                     "PPT"),
    ("Character Strengths",
     "/character-strengths-viacharacter", "PPT"),
    ("Savoring",
     "/savoring",                      "PPT"),

    # Interpersonal
    ("Assertiveness Training",
     "/assertiveness-training",        "interpersonal"),
    ("Interpersonal Therapy",
     "/interpersonal-therapy",         "interpersonal"),

    # Behavioural
    ("Sleep Hygiene",
     "/sleep-hygiene",                 "behavioral"),
    ("Exercise and Mental Health",
     "/exercise-mental-health",        "behavioral"),
    ("Expressive Writing",
     "/expressive-writing",            "behavioral"),
    ("Worry and Rumination",
     "/rumination",                    "CBT"),
]

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar", ".widget",
    "#comments", ".references", ".author", ".social-share",
    ".newsletter", "[id*='google_ads']",
]


class SimplyPsychologyScraper(BaseScraper):
    def __init__(self):
        super().__init__("simply_psychology", "db2_therapy")

    def _fetch(self, path: str):
        """Try clean slug first, fall back to .html extension. Returns (soup, url) or (None, None)."""
        candidates = [BASE + path, BASE + path + ".html"]
        for url in candidates:
            soup = self.get(url)
            if soup is None:
                continue
            h1 = soup.find("h1")
            title_tag = soup.find("title")
            page_text = (h1.get_text() if h1 else "") + (title_tag.get_text() if title_tag else "")
            if any(p in page_text.lower() for p in ["page not found", "404", "not found"]):
                self.log.warning("  Soft 404: %s", url)
                continue
            return soup, url
        return None, None

    def run(self) -> list:
        records = []
        for technique_name, path, modality in TARGETS:
            self.log.info("Scraping: %s", technique_name)
            soup, url = self._fetch(path)
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
                "source":            "Simply Psychology",
                "source_url":        url,
                "last_scraped":      self.today(),
            })

        self.save(records, "simply_psychology_therapy.json")
        return records

    def _extract_content(self, soup) -> str:
        for sel in ["article", "main", ".entry-content",
                    "#main-content", ".post-content", "#content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""


if __name__ == "__main__":
    SimplyPsychologyScraper().run()

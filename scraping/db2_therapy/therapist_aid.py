"""
Scraper: Therapist Aid — Worksheets and Articles
URL   : https://www.therapistaid.com
License: Free for clinical and educational use (per their Terms of Service)
Notes  : Therapist Aid may serve 403 responses to known bot user agents.
         If blocked, the delay range can be increased and a browser-like
         Accept header added. The scraper targets article/worksheet pages
         directly rather than crawling the full site.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.therapistaid.com"

# Targeted worksheet and article pages — grouped by modality
# Format: (technique_name, url_path, modality)
TARGETS = [
    # CBT
    ("Cognitive Restructuring",         "/therapy-worksheet/cognitive-restructuring", "CBT"),
    ("ABC Model (CBT)",                 "/therapy-worksheet/abc-model",               "CBT"),
    ("Thought Record",                  "/therapy-worksheet/thought-record",          "CBT"),
    ("Cognitive Distortions",           "/therapy-article/cognitive-distortions",     "CBT"),
    ("Behavioural Activation",          "/therapy-worksheet/behavioral-activation",   "CBT"),
    ("Activity Monitoring",             "/therapy-worksheet/activity-monitoring",     "CBT"),
    ("Exposure Therapy",                "/therapy-article/exposure-therapy",          "CBT"),
    ("SMART Goals",                     "/therapy-worksheet/smart-goals",             "CBT"),
    ("Problem Solving",                 "/therapy-worksheet/problem-solving",         "CBT"),
    ("Safety Behaviours",               "/therapy-article/safety-behaviors",          "CBT"),
    ("Behavioural Experiments",         "/therapy-article/behavioral-experiments",    "CBT"),

    # DBT
    ("DBT Overview",                    "/therapy-article/dbt",                       "DBT"),
    ("DBT Diary Card",                  "/therapy-worksheet/dbt-diary-card",          "DBT"),
    ("TIPP Skill",                      "/therapy-worksheet/tipp",                    "DBT"),
    ("ACCEPTS Distress Tolerance",      "/therapy-worksheet/accepts",                 "DBT"),
    ("Radical Acceptance",              "/therapy-article/radical-acceptance",        "DBT"),
    ("DEAR MAN",                        "/therapy-worksheet/dear-man",                "DBT"),
    ("Opposite Action",                 "/therapy-worksheet/opposite-action",         "DBT"),
    ("Emotion Regulation",              "/therapy-article/emotion-regulation",        "DBT"),
    ("Wise Mind",                       "/therapy-article/wise-mind",                 "DBT"),

    # ACT
    ("Acceptance and Commitment Therapy Overview", "/therapy-article/act",            "ACT"),
    ("ACT Values Clarification",        "/therapy-worksheet/values-clarification",    "ACT"),
    ("ACT Defusion",                    "/therapy-article/defusion",                  "ACT"),
    ("ACT Matrix",                      "/therapy-worksheet/act-matrix",              "ACT"),
    ("Psychological Flexibility",       "/therapy-article/psychological-flexibility", "ACT"),

    # Mindfulness
    ("Mindfulness Overview",            "/therapy-article/mindfulness",               "MBSR"),
    ("Body Scan",                       "/therapy-worksheet/body-scan-meditation",    "MBSR"),
    ("Mindful Breathing",               "/therapy-worksheet/mindful-breathing",       "MBSR"),
    ("5-4-3-2-1 Grounding",            "/therapy-worksheet/grounding-exercise",       "relaxation"),

    # Relaxation
    ("Progressive Muscle Relaxation",   "/therapy-worksheet/progressive-muscle-relaxation", "relaxation"),
    ("Diaphragmatic Breathing",         "/therapy-worksheet/diaphragmatic-breathing", "relaxation"),
    ("Guided Imagery",                  "/therapy-worksheet/guided-imagery",          "relaxation"),

    # Self-compassion / Positive psychology
    ("Self-Compassion",                 "/therapy-article/self-compassion",           "MSC"),
    ("Gratitude Journal",               "/therapy-worksheet/gratitude-journal",       "PPT"),
    ("Three Good Things",               "/therapy-worksheet/three-good-things",       "PPT"),
    ("Strengths Exploration",           "/therapy-worksheet/strengths-exploration",   "PPT"),

    # Interpersonal / Assertiveness
    ("Assertiveness",                   "/therapy-article/assertiveness",             "interpersonal"),
    ("Communication Styles",            "/therapy-article/communication-styles",      "interpersonal"),
    ("I-Statements",                    "/therapy-worksheet/i-statements",            "interpersonal"),
    ("Setting Boundaries",              "/therapy-article/boundaries",                "interpersonal"),

    # Grief / loss
    ("Grief",                           "/therapy-article/grief",                     "CBT"),
    ("Stages of Grief",                 "/therapy-article/stages-of-grief",           "CBT"),

    # Anger
    ("Anger Management",                "/therapy-article/anger",                     "CBT"),
    ("Anger Iceberg",                   "/therapy-worksheet/anger-iceberg",           "CBT"),
]

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".related-worksheets", ".download-button", "script", "style",
    ".breadcrumb", ".comments", ".advertisement",
]


class TherapistAidScraper(BaseScraper):
    def __init__(self):
        # Slightly longer delays — Therapist Aid is more likely to rate-limit
        super().__init__("therapist_aid", "db2_therapy", delay_range=(2.0, 4.5))

    def run(self) -> list:
        records = []
        for technique_name, path, modality in TARGETS:
            url = BASE + path
            self.log.info("Scraping: %s", technique_name)
            soup = self.get(url)
            if soup is None:
                continue

            h1 = soup.find("h1")
            if h1 and "page not found" in h1.get_text().lower():
                self.log.warning("  404: %s", url)
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            content = self._extract_content(soup)
            if not content or len(content) < 80:
                continue

            records.append({
                "technique_name":    technique_name,
                "aliases":           [],
                "modality":          modality,
                "target_conditions": [],   # enriched at pipeline stage
                "target_problem":    None,
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       content,
                "source":            "Therapist Aid",
                "source_url":        url,
                "last_scraped":      self.today(),
            })

        self.save(records, "therapist_aid_therapy.json")
        return records

    def _extract_content(self, soup) -> str:
        # Therapist Aid puts article body in <article> or a content div
        for sel in ["article", ".article-content", ".worksheet-content",
                    "main", "#content"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""


if __name__ == "__main__":
    TherapistAidScraper().run()

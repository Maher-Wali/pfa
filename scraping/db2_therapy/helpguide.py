"""
Scraper: HelpGuide.org — Therapy Technique & Coping Skill Articles (DB2)
URL   : https://www.helpguide.org
License: HelpGuide is a non-profit educational resource — non-commercial use.

Targets curated therapy technique and coping skill pages across HelpGuide's
mental health sections. Articles average 3000–4700 words of structured, evidence-
based content. Content lives in <main>; site does not use JS rendering.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.helpguide.org"

# (technique_name, url_path, modality, target_conditions)
TARGETS = [
    # --- Therapy techniques ---
    ("Cognitive Behavioural Therapy (CBT)",
     "/mental-health/treatment/cognitive-behavioral-therapy-cbt",
     "CBT", ["depression", "anxiety", "OCD", "PTSD", "phobias"]),

    ("Exposure Therapy",
     "/mental-health/treatment/exposure-therapy",
     "CBT", ["phobias", "OCD", "PTSD", "anxiety"]),

    ("EMDR Therapy",
     "/mental-health/treatment/emdr-therapy",
     "EMDR", ["PTSD", "trauma"]),

    # --- Anxiety coping ---
    ("How to Stop Worrying",
     "/mental-health/anxiety/how-to-stop-worrying",
     "CBT", ["GAD", "anxiety", "worry"]),

    ("Cognitive Distortions",
     "/mental-health/anxiety/cognitive-distortions-put-an-end-to-distorted-thinking",
     "CBT", ["anxiety", "depression", "OCD"]),

    ("Intrusive Thoughts",
     "/mental-health/anxiety/intrusive-thoughts-why-you-have-them-and-how-to-stop",
     "CBT", ["OCD", "anxiety", "PTSD"]),

    ("Panic Attacks and Panic Disorder",
     "/mental-health/anxiety/panic-attacks-and-panic-disorders",
     "CBT", ["panic disorder", "agoraphobia", "anxiety"]),

    ("Social Anxiety Disorder",
     "/mental-health/anxiety/social-anxiety-disorder",
     "CBT", ["social anxiety"]),

    ("Phobias and Irrational Fears",
     "/mental-health/anxiety/phobias-and-irrational-fears",
     "CBT", ["phobias", "anxiety"]),

    ("Generalised Anxiety Disorder (GAD)",
     "/mental-health/anxiety/generalized-anxiety-disorder-gad",
     "CBT", ["GAD", "anxiety", "worry"]),

    ("OCD — Obsessive Compulsive Disorder",
     "/mental-health/anxiety/obssessive-compulsive-disorder-ocd",
     "CBT", ["OCD", "anxiety"]),

    # --- Depression coping ---
    ("Coping with Depression",
     "/mental-health/depression/coping-with-depression",
     "CBT", ["depression"]),

    ("Depression Treatment",
     "/mental-health/depression/depression-treatment",
     "CBT", ["depression"]),

    ("Ways to Fight Depression",
     "/mental-health/depression/i-feel-depressed",
     "behavioural activation", ["depression"]),

    # --- Grief ---
    ("Coping with Grief and Loss",
     "/mental-health/grief/coping-with-grief-and-loss",
     "grief therapy", ["grief", "bereavement", "loss"]),

    ("Coping with a Breakup or Divorce",
     "/mental-health/grief/dealing-with-a-breakup-or-divorce",
     "CBT", ["grief", "depression", "anxiety"]),

    # --- PTSD and trauma ---
    ("Coping with PTSD and Trauma",
     "/mental-health/ptsd-trauma/ptsd-symptoms-self-help-treatment",
     "trauma-focused CBT", ["PTSD", "trauma"]),

    ("Emotional and Psychological Trauma",
     "/mental-health/ptsd-trauma/coping-with-emotional-and-psychological-trauma",
     "trauma-focused CBT", ["PTSD", "trauma", "acute stress"]),

    # --- Stress and relaxation ---
    ("Stress Management",
     "/mental-health/stress/stress-management",
     "CBT", ["stress", "anxiety", "burnout"]),

    ("Relaxation Techniques for Stress Relief",
     "/mental-health/stress/relaxation-techniques-for-stress-relief",
     "relaxation", ["anxiety", "stress", "insomnia"]),

    ("Quick Stress Relief",
     "/mental-health/stress/quick-stress-relief",
     "relaxation", ["stress", "anxiety"]),

    ("Benefits of Mindfulness",
     "/mental-health/stress/benefits-of-mindfulness",
     "MBSR", ["anxiety", "depression", "stress"]),

    ("Burnout Prevention and Recovery",
     "/mental-health/stress/burnout-prevention-and-recovery",
     "CBT", ["burnout", "stress", "depression"]),

    # --- Suicide and self-harm ---
    ("Coping with Suicidal Thoughts",
     "/mental-health/suicide-self-harm/are-you-feeling-suicidal",
     "CBT", ["suicidal ideation", "depression"]),

    ("Cutting and Self-Harm",
     "/mental-health/suicide-self-harm/cutting-and-self-harm",
     "DBT", ["self-harm", "BPD", "depression"]),

    # --- Wellbeing and self-improvement ---
    ("Building Better Mental Health",
     "/mental-health/wellbeing/building-better-mental-health",
     "positive psychology", ["depression", "anxiety", "stress"]),

    ("Improving Emotional Intelligence",
     "/mental-health/wellbeing/emotional-intelligence-eq",
     "interpersonal", ["depression", "anxiety", "social anxiety"]),

    ("Self-Esteem",
     "/mental-health/wellbeing/self-esteem",
     "CBT", ["low self-esteem", "depression", "social anxiety"]),

    ("How to Build Confidence",
     "/mental-health/wellbeing/how-to-build-confidence",
     "CBT", ["low self-esteem", "social anxiety"]),

    ("Journaling for Mental Health",
     "/mental-health/wellbeing/journaling-for-mental-health-and-wellness",
     "CBT", ["depression", "anxiety", "stress"]),

    ("Laughter and Mental Health",
     "/mental-health/wellbeing/laughter-is-the-best-medicine",
     "positive psychology", ["depression", "stress", "anxiety"]),

    # --- Interpersonal and communication ---
    ("Anger Management",
     "/relationships/communication/anger-management",
     "CBT", ["anger", "depression", "anxiety", "BPD"]),

    ("Effective Communication Skills",
     "/relationships/communication/effective-communication",
     "interpersonal", ["social anxiety", "depression", "relationship issues"]),

    ("Active Listening",
     "/relationships/communication/active-listening",
     "interpersonal", ["social anxiety", "relationship issues"]),

    ("Setting Healthy Boundaries",
     "/relationships/social-connection/setting-healthy-boundaries-in-relationships",
     "DBT", ["BPD", "relationship issues", "codependency"]),

    ("Loneliness and Social Isolation",
     "/relationships/social-connection/loneliness-and-social-isolation",
     "interpersonal", ["depression", "anxiety", "social anxiety"]),

    # --- Sleep ---
    ("Insomnia — Causes and Self-Help",
     "/wellness/sleep/insomnia-causes-and-cures",
     "CBT", ["insomnia", "depression", "anxiety"]),
]

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".related-posts", ".post-share-submenu",
    ".post-meta-item", ".loading-spinner", "script", "style", "noscript",
    "[class*='ad-']", "[id*='ad-']", ".newsletter", ".donate",
]


class HelpGuideScraper(BaseScraper):
    def __init__(self):
        super().__init__("helpguide", "db2_therapy")

    def run(self) -> list:
        records = []
        for technique_name, path, modality, conditions in TARGETS:
            url = BASE + path
            self.log.info("Page: %s", technique_name)
            soup = self.get(url)
            if soup is None:
                continue

            h1 = soup.find("h1")
            if h1 and "not found" in h1.get_text().lower():
                self.log.warning("  Soft 404: %s", url)
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)

            main = soup.select_one("main")
            if main is None:
                self.log.warning("  No <main> found: %s", url)
                continue

            content = self.clean(main.get_text(separator=" "))
            if not content or len(content.split()) < 100:
                self.log.warning("  Too short (%d words): %s",
                                 len(content.split()), url)
                continue

            records.append({
                "technique_name":    technique_name,
                "aliases":           [],
                "modality":          modality,
                "target_conditions": conditions,
                "target_problem":    None,
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       content,
                "source":            "HelpGuide",
                "source_url":        url,
                "last_scraped":      self.today(),
            })
            self.log.info("  -> %d words [%s]", len(content.split()), modality)

        self.save(records, "helpguide_therapy.json")
        return records


if __name__ == "__main__":
    HelpGuideScraper().run()

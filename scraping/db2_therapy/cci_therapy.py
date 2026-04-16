"""
Scraper: CCI — Therapy Technique Workbooks (DB2)
URL   : https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself
License: Free for non-commercial use
Notes  : Scrapes the CCI therapy workbooks (CBT, behavioural activation,
         worry management, etc.) as opposed to the psychoeducation info
         sheets handled in db1_clinical/cci.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text

BASE = "https://www.cci.health.wa.gov.au"

# CCI therapy workbooks — each is a multi-module PDF series
# modality → list of (display_name, pdf_url)
CCI_THERAPY_PDFS = {
    "CBT": [
        ("What? Me Worry — Module 1: What is Worry?",
         f"{BASE}/Resources/For-Clients/Worry-and-Generalised-Anxiety-Disorder"
         "/CCI_Client_Info_Worry_01_What_is_Worry.pdf"),
        ("What? Me Worry — Module 2: Challenging Worrying Thoughts",
         f"{BASE}/Resources/For-Clients/Worry-and-Generalised-Anxiety-Disorder"
         "/CCI_Client_Info_Worry_02_Challenging_Worrying_Thoughts.pdf"),
        ("What? Me Worry — Module 3: Problem Solving",
         f"{BASE}/Resources/For-Clients/Worry-and-Generalised-Anxiety-Disorder"
         "/CCI_Client_Info_Worry_03_Problem_Solving.pdf"),
        ("Thought Challenging — Identifying Unhelpful Thinking Styles",
         f"{BASE}/Resources/For-Clients/Depressed-Mood"
         "/CCI_Client_Info_Depression_04_Unhelpful_Thinking_Styles.pdf"),
        ("Thought Challenging — Changing Unhelpful Thoughts",
         f"{BASE}/Resources/For-Clients/Depressed-Mood"
         "/CCI_Client_Info_Depression_05_Changing_Unhelpful_Thoughts.pdf"),
        ("Behavioural Activation — Module 1: What is BA?",
         f"{BASE}/Resources/For-Clients/Depressed-Mood"
         "/CCI_Client_Info_Depression_06_Behavioural_Activation.pdf"),
        ("Problem Solving for Depression",
         f"{BASE}/Resources/For-Clients/Depressed-Mood"
         "/CCI_Client_Info_Depression_07_Problem_Solving.pdf"),
        ("Graded Exposure — Facing Your Fears",
         f"{BASE}/Resources/For-Clients/Anxiety"
         "/CCI_Client_Info_Anxiety_04_Graded_Exposure.pdf"),
        ("Behavioural Experiments",
         f"{BASE}/Resources/For-Clients/Anxiety"
         "/CCI_Client_Info_Anxiety_05_Behavioural_Experiments.pdf"),
    ],
    "relaxation": [
        ("Controlled Breathing",
         f"{BASE}/Resources/For-Clients/Anxiety"
         "/CCI_Client_Info_Anxiety_06_Controlled_Breathing.pdf"),
        ("Progressive Muscle Relaxation",
         f"{BASE}/Resources/For-Clients/Anxiety"
         "/CCI_Client_Info_Anxiety_07_Progressive_Muscle_Relaxation.pdf"),
    ],
    "interpersonal": [
        ("Assertiveness — Module 1: Introduction to Assertiveness",
         f"{BASE}/Resources/For-Clients/Assertiveness"
         "/CCI_Client_Info_Assertiveness_01_Introduction.pdf"),
        ("Assertiveness — Module 2: Assertive Communication",
         f"{BASE}/Resources/For-Clients/Assertiveness"
         "/CCI_Client_Info_Assertiveness_02_Assertive_Communication.pdf"),
    ],
    "MSC": [
        ("Self-Compassion — Module 1: What is Self-Compassion?",
         f"{BASE}/Resources/For-Clients/Self-Compassion"
         "/CCI_Client_Info_SelfCompassion_01_What_is_Self_Compassion.pdf"),
    ],
}

MODALITY_CONDITIONS = {
    "CBT": ["depression", "anxiety", "OCD", "panic disorder", "social anxiety"],
    "relaxation": ["anxiety", "panic disorder", "stress", "PTSD"],
    "interpersonal": ["social anxiety", "depression", "low self-esteem"],
    "MSC": ["depression", "low self-esteem", "shame"],
}


class CCITherapyScraper(BaseScraper):
    def __init__(self):
        super().__init__("cci_therapy", "db2_therapy")

    def run(self) -> list:
        records = []
        for modality, workbooks in CCI_THERAPY_PDFS.items():
            for technique_name, pdf_url in workbooks:
                self.log.info("Downloading: %s", technique_name)
                raw = self.download_bytes(pdf_url)
                if raw is None:
                    self.log.warning("  Failed: %s", pdf_url)
                    continue

                text = extract_text(raw)
                if not text:
                    self.log.warning("  No text extracted from %s", pdf_url)
                    continue

                records.append({
                    "technique_name":     technique_name,
                    "aliases":            [],
                    "modality":           modality,
                    "target_conditions":  MODALITY_CONDITIONS.get(modality, []),
                    "target_problem":     None,   # enriched at pipeline stage
                    "steps":              None,   # enriched at pipeline stage
                    "worked_example":     None,   # enriched at pipeline stage
                    "when_to_use":        None,   # enriched at pipeline stage
                    "estimated_time":     None,
                    "difficulty":         None,
                    "raw_content":        self.clean(text),
                    "source":             "CCI",
                    "source_url":         pdf_url,
                    "last_scraped":       self.today(),
                })

        self.save(records, "cci_therapy.json")
        return records


if __name__ == "__main__":
    CCITherapyScraper().run()

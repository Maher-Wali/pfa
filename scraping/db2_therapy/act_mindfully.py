"""
Scraper: ACT Mindfully — Free ACT Resources (Russ Harris)
URL   : https://www.actmindfully.com.au/free-stuff/articles-papers/
License: Free resources section — explicitly available for use

Only practitioner-facing and technique-explanation PDFs are included.
Academic RCT papers (schizophrenia, chronic pain, component analyses) are
excluded — wrong register for our use case (see data_sources.txt).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper
from utils.pdf_extractor import extract_text

# Verified URLs from actmindfully.com.au/free-stuff/articles-papers/
# Only content useful for a therapy techniques corpus
PDF_RESOURCES = [
    (
        "ACT — Non-Technical Overview",
        "https://actmindfully.com.au/upimages/Dr_Russ_Harris_-_A_Non-technical_Overview_of_ACT.pdf",
        "ACT",
    ),
    (
        "Acceptance and Commitment Therapy — Overview",
        "https://actmindfully.com.au/upimages/acceptance_and_commitment_therapy_-_an_overview.pdf",
        "ACT",
    ),
    (
        "Experiential Avoidance — The Core ACT Target",
        "https://actmindfully.com.au/upimages/experiential_avoidance.pdf",
        "ACT",
    ),
    (
        "ACT Model — Processes and Outcomes",
        "https://actmindfully.com.au/upimages/act_model_processes_outcomes.pdf",
        "ACT",
    ),
    (
        "ACT Pack — Exercises and Worksheets",
        "https://actmindfully.com.au/upimages/act_pack.pdf",
        "ACT",
    ),
    (
        "The ACT Hexaflex — Psychological Flexibility Model",
        "https://actmindfully.com.au/upimages/hexaflex.pdf",
        "ACT",
    ),
    (
        "Mindfulness — Overview and Application",
        "https://actmindfully.com.au/upimages/mindfulness.pdf",
        "ACT",
    ),
    (
        "Values-Centred Interventions in ACT (Kelly Wilson)",
        "https://www.actmindfully.com.au/wp-content/uploads/2021/04/Values-centred-Interventions-In-ACT-by-Kelly-Wilson.pdf",
        "ACT",
    ),
]


class ACTMindfullycraper(BaseScraper):
    def __init__(self):
        super().__init__("act_mindfully", "db2_therapy")

    def run(self) -> list:
        records = []
        for technique_name, url, modality in PDF_RESOURCES:
            self.log.info("Downloading: %s", technique_name)
            raw = self.download_bytes(url)
            if raw is None:
                self.log.warning("  Failed: %s", url)
                continue

            text = extract_text(raw)
            if not text or len(text) < 100:
                self.log.warning("  No usable text from: %s", url)
                continue

            self.log.info("  Extracted %d chars", len(text))
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
                "source":            "ACT Mindfully",
                "source_url":        url,
                "last_scraped":      self.today(),
            })

        self.save(records, "act_mindfully_therapy.json")
        return records


if __name__ == "__main__":
    ACTMindfullycraper().run()

"""
Scraper: NHS Mental Health Conditions
URL   : https://www.nhs.uk/mental-health/conditions/
License: Open Government Licence v3.0
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE = "https://www.nhs.uk"

# slug → display name
CONDITION_SLUGS = {
    "depression-in-adults":                        "Depression",
    "generalised-anxiety-disorder":                "Generalised Anxiety Disorder",
    "panic-disorder":                              "Panic Disorder",
    "social-anxiety":                              "Social Anxiety Disorder",
    "phobias":                                     "Phobias",
    "obsessive-compulsive-disorder-ocd":           "OCD",
    "post-traumatic-stress-disorder-ptsd":         "PTSD",
    "complex-ptsd":                                "Complex PTSD",
    "bipolar-disorder":                            "Bipolar Disorder",
    "schizophrenia":                               "Schizophrenia",
    "psychosis":                                   "Psychosis",
    "eating-disorders":                            "Eating Disorders",
    "anorexia":                                    "Anorexia Nervosa",
    "bulimia":                                     "Bulimia Nervosa",
    "binge-eating-disorder":                       "Binge Eating Disorder",
    "borderline-personality-disorder-bpd":         "Borderline Personality Disorder",
    "attention-deficit-hyperactivity-disorder-adhd": "ADHD",
    "autism-spectrum-disorder-asd":                "Autism Spectrum Disorder",
    "post-natal-depression":                       "Postnatal Depression",
    "seasonal-affective-disorder-sad":             "Seasonal Affective Disorder",
    "health-anxiety":                              "Health Anxiety",
    "body-dysmorphic-disorder-bdd":                "Body Dysmorphic Disorder",
    "hoarding-disorder":                           "Hoarding Disorder",
    "trichotillomania":                            "Trichotillomania",
}

# Sections NHS uses — we try each; 404-equivalent pages are skipped
SECTION_SLUGS = [
    "overview",
    "symptoms",
    "causes",
    "diagnosis",
    "treatment",
    "self-help",
    "living-with",
    "getting-help",
    "recovery",
    "support",
]

ICD11_MAP = {
    "depression-in-adults":                  "6A70",
    "generalised-anxiety-disorder":          "6B00",
    "panic-disorder":                        "6B01",
    "social-anxiety":                        "6B04",
    "phobias":                               "6B03",
    "obsessive-compulsive-disorder-ocd":     "6B20",
    "post-traumatic-stress-disorder-ptsd":   "6B40",
    "complex-ptsd":                          "6B41",
    "bipolar-disorder":                      "6A60",
    "schizophrenia":                         "6A20",
    "psychosis":                             "6A2Z",
    "eating-disorders":                      "6B8Z",
    "anorexia":                              "6B80",
    "bulimia":                               "6B81",
    "binge-eating-disorder":                 "6B82",
    "borderline-personality-disorder-bpd":   "6D11",
    "attention-deficit-hyperactivity-disorder-adhd": "6A05",
    "autism-spectrum-disorder-asd":          "6A02",
    "post-natal-depression":                 "6A70",
    "seasonal-affective-disorder-sad":       "6A70",
    "health-anxiety":                        "6B23",
    "body-dysmorphic-disorder-bdd":          "6B21",
}

ALIASES = {
    "depression-in-adults":                  ["depression", "MDD", "major depressive disorder"],
    "generalised-anxiety-disorder":          ["GAD", "generalised anxiety", "generalized anxiety disorder"],
    "post-traumatic-stress-disorder-ptsd":   ["PTSD", "post-traumatic stress"],
    "complex-ptsd":                          ["CPTSD", "C-PTSD", "complex trauma"],
    "borderline-personality-disorder-bpd":   ["BPD", "emotionally unstable personality disorder", "EUPD"],
    "attention-deficit-hyperactivity-disorder-adhd": ["ADHD", "ADD", "attention deficit"],
    "autism-spectrum-disorder-asd":          ["ASD", "autism", "Asperger's"],
    "seasonal-affective-disorder-sad":       ["SAD", "winter depression", "seasonal depression"],
    "obsessive-compulsive-disorder-ocd":     ["OCD", "obsessive compulsive"],
}

SECTION_NORMALISE = {
    "self-help":    "self_help",
    "living-with":  "living_with",
    "getting-help": "when_to_seek_help",
    "support":      "when_to_seek_help",
    "recovery":     "living_with",
}

BOILERPLATE_SELECTORS = [
    "nav", ".nhsuk-breadcrumb", "footer", ".nhsuk-pagination",
    ".nhsuk-care-card", "script", "style", "noscript",
]


class NHSScraper(BaseScraper):
    def __init__(self):
        super().__init__("nhs", "db1_clinical")

    def run(self) -> list:
        records = []
        for slug, name in CONDITION_SLUGS.items():
            self.log.info("Condition: %s", name)
            batch = self._scrape_condition(slug, name)
            self.log.info("  %d sections scraped", len(batch))
            records.extend(batch)

        self.save(records, "nhs_clinical.json")
        return records

    def _scrape_condition(self, slug: str, name: str) -> list:
        records = []
        for section in SECTION_SLUGS:
            url = f"{BASE}/mental-health/conditions/{slug}/{section}/"
            soup = self.get(url)
            if soup is None:
                continue

            # NHS serves a styled 404 as HTTP 200 — detect it by h1 text
            h1 = soup.find("h1")
            if h1 and "page not found" in h1.get_text().lower():
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            content = self._extract_content(soup)
            if not content or len(content) < 100:
                continue

            records.append({
                "condition":    name,
                "aliases":      ALIASES.get(slug, []),
                "source":       "NHS",
                "source_url":   url,
                "section":      SECTION_NORMALISE.get(section, section),
                "content":      content,
                "icd11_code":   ICD11_MAP.get(slug),
                "last_scraped": self.today(),
            })
        return records

    def _extract_content(self, soup) -> str:
        for sel in ["article", "main", "div.nhsuk-main-wrapper", "#maincontent"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        # Fallback: body text with boilerplate already stripped
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""


if __name__ == "__main__":
    NHSScraper().run()

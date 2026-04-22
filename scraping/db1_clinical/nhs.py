"""
Scraper: NHS Mental Health Conditions
URL   : https://www.nhs.uk/mental-health/conditions/
License: Open Government Licence v3.0

NHS migrated to a single-page layout per condition. Each condition now lives at
  /mental-health/conditions/<slug>/
with all sections (symptoms, diagnosis, treatment, etc.) under H2 headings on
that one page. The old /symptoms/, /diagnosis/ sub-URLs return the same full
page, so we fetch once and split by heading.
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

# Elements stripped before text extraction. Includes both legacy care-card class
# and the newer warning-callout / inset-text classes NHS uses for crisis banners
# and "Information:" / "Non-urgent advice:" boxes that repeat on every page.
BOILERPLATE_SELECTORS = [
    "nav",
    ".nhsuk-breadcrumb",
    "footer",
    ".nhsuk-pagination",
    ".nhsuk-care-card",
    ".nhsuk-warning-callout",
    ".nhsuk-inset-text",
    "script",
    "style",
    "noscript",
]

# Ordered keyword sets mapped to our canonical section names.
# First match wins, so put more specific phrases earlier.
_HEADING_RULES = [
    (["symptom"],                                        "symptoms"),
    (["diagnos"],                                        "diagnosis"),
    (["treatment", "treating"],                          "treatment"),
    (["self-help", "self help", "things you can try"],   "self_help"),
    (["living with", "recovery"],                        "living_with"),
    (["cause", "what causes"],                           "causes"),
    (["help and support", "getting help", "where to get", "find support"],
                                                         "when_to_seek_help"),
    (["overview", "about", "what is", "what are"],       "overview"),
]

# Leaf-level HTML tags whose text we collect (avoids double-counting
# when a <div> wraps a <p> — we only grab the <p>).
_LEAF_TAGS = {"p", "li", "dt", "dd", "h3", "h4", "h5", "td", "th"}

MIN_WORDS = 40


def _heading_to_section(heading_text: str) -> str | None:
    h = heading_text.lower()
    for keywords, section in _HEADING_RULES:
        if any(k in h for k in keywords):
            return section
    return None


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
        # Fetch the single condition page (NHS migrated to single-page layout)
        url = f"{BASE}/mental-health/conditions/{slug}/"
        soup = self.get(url)

        if soup is None:
            self.log.warning("No response for %s", url)
            return []

        h1 = soup.find("h1")
        if h1 and "page not found" in h1.get_text().lower():
            self.log.warning("Page not found: %s", url)
            return []

        self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)

        content_node = None
        for sel in ["article", "main", "#maincontent", "div.nhsuk-main-wrapper"]:
            content_node = soup.select_one(sel)
            if content_node:
                break

        if content_node is None:
            self.log.warning("No content node found for %s", name)
            return []

        return self._extract_sections(content_node, name, slug, url)

    def _extract_sections(self, node, name: str, slug: str, url: str) -> list:
        """Split the page into per-section records using H2 headings."""
        icd11   = ICD11_MAP.get(slug)
        aliases = ALIASES.get(slug, [])

        h2s = node.find_all("h2")
        if not h2s:
            # No headings — store the whole page as overview
            text = self.clean(node.get_text(separator=" "))
            if len(text.split()) >= MIN_WORDS:
                return [self._record(name, aliases, url, "overview", text, icd11)]
            return []

        records = []
        for i, h2 in enumerate(h2s):
            heading_text = h2.get_text(strip=True)
            section = _heading_to_section(heading_text)
            if section is None:
                # Heading doesn't match any known section — treat the first
                # unrecognised heading as overview (usually the condition title)
                if i == 0:
                    section = "overview"
                else:
                    self.log.debug("Skipping unrecognised heading: %s", heading_text)
                    continue

            next_h2 = h2s[i + 1] if i + 1 < len(h2s) else None
            text = self._text_under_heading(h2, next_h2)

            if len(text.split()) < MIN_WORDS:
                continue

            records.append(self._record(name, aliases, url, section, text, icd11))

        return records

    def _text_under_heading(self, h2, next_h2) -> str:
        """
        Collect text from all leaf elements that follow h2 in document order
        and precede next_h2 (or end of document).

        Using find_all_next() traverses the full DOM in document order so this
        works even when h2s live inside different container divs.
        Only _LEAF_TAGS are collected to avoid duplicating text from parent
        wrappers (e.g. a <div> containing a <p> — we only take the <p>).
        """
        parts = []
        for el in h2.find_all_next():
            if next_h2 is not None and el is next_h2:
                break
            if getattr(el, "name", None) in _LEAF_TAGS:
                text = el.get_text(separator=" ").strip()
                if text:
                    parts.append(text)
        return self.clean(" ".join(parts))

    @staticmethod
    def _record(name, aliases, url, section, content, icd11) -> dict:
        from datetime import date
        return {
            "condition":    name,
            "aliases":      aliases,
            "source":       "NHS",
            "source_url":   url,
            "section":      section,
            "content":      content,
            "icd11_code":   icd11,
            "last_scraped": date.today().isoformat(),
        }


if __name__ == "__main__":
    NHSScraper().run()

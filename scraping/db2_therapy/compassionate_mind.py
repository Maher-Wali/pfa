"""
Scraper: Compassionate Mind Foundation — CFT Publications 2023
URL   : https://www.compassionatemind.co.uk/cft-publications-2023
License: Publicly accessible research bibliography.

The page lists ~75 Compassion Focused Therapy (CFT) publications from 2023,
each with authors, title (hyperlinked to the paper), journal, and hashtags
indicating topic/population/country.

The scraper:
  1. Parses all publication entries from the bibliography page
  2. Follows each link to attempt fetching the abstract or full text
     (many are open-access; paywalled papers yield only the abstract)
  3. Falls back to the citation text if the link is inaccessible

Page structure (as of 2026-05):
  - January-May entries: individual <p> tags inside a <div class="w-richtext">
  - June-December entries: single large <p> with <br/>-separated entries
  Both sections are handled by _parse_entries / _split_br_paragraph.
"""
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE_URL = "https://www.compassionatemind.co.uk"
PAGE_PATH = "/cft-publications-2023"

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", "script", "style",
    ".cookie-banner", ".social-links", ".site-footer",
    ".site-header", ".nav-wrapper",
]

HASHTAG_CONDITIONS = {
    "anxiety": ["anxiety"],
    "depression": ["depression"],
    "ocd": ["ocd"],
    "ptsd": ["ptsd"],
    "trauma": ["ptsd", "trauma"],
    "psychosis": ["psychosis"],
    "bipolar": ["bipolar disorder"],
    "eatingdisorder": ["eating disorders"],
    "eatingdisorders": ["eating disorders"],
    "pain": ["chronic pain"],
    "chronic_pain": ["chronic pain"],
    "chronicpain": ["chronic pain"],
    "cancer": ["cancer distress"],
    "selfharm": ["self-harm"],
    "selfharmandsuicide": ["self-harm"],
    "shame": ["shame"],
    "selfcriticism": ["self-criticism"],
    "selfcriticsm": ["self-criticism"],
    "anger": ["anger"],
    "stress": ["stress"],
    "burnout": ["burnout"],
    "grief": ["grief"],
    "bdd": ["body dysmorphic disorder"],
    "autism": ["autism"],
    "adhd": ["adhd"],
    "substance": ["substance use"],
    "neurological": ["neurological conditions"],
    "socialanxiety": ["social anxiety"],
    "personalitydisorderdiagnosis": ["personality disorders"],
    "intellectualdifficulties": ["intellectual disabilities"],
    "psychosexual": ["sexual difficulties"],
    "perinatal": ["perinatal mental health"],
    "adoptionandfostercare": ["attachment difficulties"],
}

_BOOKSTORE_HOSTS = ("amazon.co.uk", "amazon.com", "amazon.")


class CompassionateMindscraper(BaseScraper):
    def __init__(self):
        super().__init__("compassionate_mind", "db2_therapy")

    def run(self) -> list:
        records = []

        soup = self.get(BASE_URL + PAGE_PATH)
        if soup is None:
            self.log.error("Failed to fetch publications page")
            return records

        self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)

        entries = self._parse_entries(soup)
        self.log.info("Parsed %d publication entries", len(entries))

        for entry in entries:
            self.log.info("Processing: %s", entry["title"][:80])

            content = None
            if entry["url"]:
                content = self._fetch_paper_content(entry["url"])

            if content and len(content.split()) >= 30:
                raw = (
                    f"Title: {entry['title']}\n"
                    f"Authors: {entry['authors']}\n"
                    f"Journal: {entry['journal']}\n\n"
                    f"{content}"
                )
            else:
                raw = (
                    f"Title: {entry['title']}\n"
                    f"Authors: {entry['authors']}\n"
                    f"Journal: {entry['journal']}\n"
                )

            if len(raw.split()) < 20:
                continue

            conditions = self._hashtags_to_conditions(entry["hashtags"])

            records.append({
                "technique_name":    f"CFT — {entry['title'][:100]}",
                "aliases":           [],
                "modality":          "CFT",
                "target_conditions": conditions,
                "target_problem":    None,
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       raw,
                "source":            "Compassionate Mind Foundation",
                "source_url":        (
                    entry["url"]
                    if entry["url"] and not any(h in entry["url"] for h in _BOOKSTORE_HOSTS)
                    else BASE_URL + PAGE_PATH
                ),
                "hashtags":          entry["hashtags"],
                "last_scraped":      self.today(),
            })

        self.log.info("Total: %d records", len(records))
        self.save(records, "compassionate_mind_therapy.json")
        return records

    def _parse_entries(self, soup) -> list:
        """Extract publication entries from the bibliography page."""
        main = soup.select_one("main") or soup.select_one("article") or soup.find("body")
        if main is None:
            return []

        entries = []
        for p in main.find_all("p"):
            # Skip <p> tags that nest other <p> tags (section wrappers).
            if p.find("p"):
                continue

            text = p.get_text(separator=" ", strip=True)
            if not text or "(2023)" not in text:
                continue

            # A <p> with multiple (2023) occurrences is a <br/>-delimited block
            # (the June-December section). Split into per-entry chunks.
            if text.count("(2023)") > 1:
                for sub_p in self._split_br_paragraph(p):
                    entry = self._extract_entry(sub_p)
                    if entry:
                        entries.append(entry)
            else:
                raw_tags = re.findall(r"#(\w+)", text)
                if len(raw_tags) > 10:
                    self.log.warning(
                        "Skipping oversized paragraph (%d hashtags) — likely a section wrapper",
                        len(raw_tags),
                    )
                    continue
                entry = self._extract_entry(p)
                if entry:
                    entries.append(entry)

        return entries

    def _split_br_paragraph(self, p) -> list:
        """Split a <p> with <br/>-separated entries into individual sub-paragraphs."""
        chunks, current = [], []
        for child in p.children:
            if getattr(child, "name", None) == "br":
                if current:
                    chunks.append(current[:])
                    current = []
            else:
                current.append(str(child))
        if current:
            chunks.append(current)

        result = []
        for parts in chunks:
            html = "".join(parts).strip()
            if "(2023)" in html:
                sub = BeautifulSoup(f"<p>{html}</p>", "html.parser").find("p")
                if sub:
                    result.append(sub)
        return result

    def _extract_entry(self, p) -> dict | None:
        """Parse one publication <p> node into an entry dict, or None if invalid."""
        text = p.get_text(separator=" ", strip=True)

        link = p.find("a", href=True)
        title = ""
        url = ""
        if link:
            title = link.get_text(strip=True)
            # Some entries render the first char (e.g. "T") as a text sibling outside
            # the <a> tag, separated by a space from BeautifulSoup's separator=" ".
            # Recover it by scanning the 4 chars before the link text in the paragraph.
            if title and title[0].islower():
                idx = text.find(title)
                if idx > 0:
                    preceding = text[max(0, idx - 4):idx]
                    m = re.search(r"([A-Z])", preceding)
                    if m:
                        title = m.group(1) + title
            href = link["href"]
            # Reject hrefs that are citation strings (contain spaces)
            if href.startswith("http") and " " not in href:
                url = href
            elif href.startswith("/"):
                url = urljoin(BASE_URL, href)

        authors_match = re.match(r"^(.+?)\(2023\)", text)
        authors = authors_match.group(1).strip().rstrip(",. ") if authors_match else ""

        if not title:
            title_match = re.search(r'\(2023\)\.\s*["“]?(.+?)["”]?\.', text)
            title = title_match.group(1).strip() if title_match else ""

        if not title:
            return None

        # The page occasionally writes "#two words" with a space between hashtag words.
        # Normalise to "#two_words" before extraction so both words are captured.
        hashtag_text = re.sub(r"#(\w+) (\w+)", r"#\1_\2", text)
        hashtags = re.findall(r"#(\w+)", hashtag_text)

        journal = ""
        if title in text:
            after_title = text.split(title, 1)[-1]
            journal_part = re.split(r"\s*#\w+", after_title)[0]
            journal_part = re.sub(r"^\.\s*", "", journal_part)
            journal_part = re.sub(r"\s{2,}\w+$", "", journal_part)
            journal_part = journal_part.strip(" .,;")
            journal = journal_part if len(journal_part) > 3 else ""

        return {"title": title, "authors": authors, "journal": journal,
                "url": url, "hashtags": hashtags}

    def _fetch_paper_content(self, url: str) -> str:
        """Attempt to fetch abstract or full text from a paper URL."""
        if any(host in url for host in _BOOKSTORE_HOSTS):
            return ""
        try:
            soup = self.get(url, retries=1)
            if soup is None:
                return ""

            abstract_selectors = [
                "div.abstract", "section.abstract", "#abstract",
                ".abstractSection", ".article-section__abstract",
                "div[role='doc-abstract']", ".abstract-content",
                ".JournalAbstract", ".hlFld-Abstract",
                "section[id*='abstract']", "div[id*='abstract']",
                ".c-article-section__content",  # Springer
                "#abstracts",                   # Wiley
            ]

            for sel in abstract_selectors:
                node = soup.select_one(sel)
                if node:
                    text = self.clean(node.get_text(separator=" "))
                    if len(text.split()) >= 20:
                        return text

            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                desc = meta["content"].strip()
                if len(desc.split()) >= 15:
                    return desc

            meta_dc = soup.find("meta", attrs={"name": "DC.description"})
            if meta_dc and meta_dc.get("content"):
                return meta_dc["content"].strip()

        except Exception as exc:
            self.log.debug("Could not fetch content from %s: %s", url, exc)

        return ""

    def _hashtags_to_conditions(self, hashtags: list) -> list:
        """Map hashtags to standardized target conditions."""
        conditions = set()
        for tag in hashtags:
            tag_lower = tag.lower()
            if tag_lower in HASHTAG_CONDITIONS:
                conditions.update(HASHTAG_CONDITIONS[tag_lower])
        return sorted(conditions) if conditions else []


if __name__ == "__main__":
    CompassionateMindscraper().run()

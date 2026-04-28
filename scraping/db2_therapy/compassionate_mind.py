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


  ⏺ The scraper is working. Here's a summary:
                                                                                                                                                           
  Results:                                                                                                                                                 
  - 52 records scraped from the CFT Publications 2023 page                                                                                               
  - 19 records with full abstracts (from open-access journals)                                                                                             
  - 33 records with citation data only (journal sites returned 403)                                                                                      
                                                                                                                                                           
                                                                                                                               
  - scraping/db2_therapy/compassionate_mind.py — new scraper                                                                                               
  - scraping/run_db2.py — registered the new scraper                                                                                                       
                                                                                                                                                         
  To integrate into the pipeline, run:                                                                                                                     
  # 1. Re-run preprocessing (chunks the raw data)                                                                                                        
  python pipeline/prepare_db2.py                                                                                                                           
                                                                                                                                                           
  # 2. Re-index into Pinecone                                                                                                                              
  python pipeline/build_vectors.py --db db2                                                                                                                
                                                                                                                                                           
  Note: many academic publishers (Wiley, Sage, Elsevier, Taylor & Francis) block scraping with 403s. The 19 records with abstracts came from open-access   
  journals (LIDSEN, Brieflands, Springer, etc.). If you want richer content, the site also has a /resource/audio page with guided CFT practices that would 
  provide more actionable therapy content for the RAG system.   
"""
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

BASE_URL = "https://www.compassionatemind.co.uk"
PAGE_PATH = "/cft-publications-2023"

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", "script", "style",
    ".cookie-banner", ".social-links", ".site-footer",
    ".site-header", ".nav-wrapper",
]

# Hashtag → target_conditions mapping
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
    "chronicpain": ["chronic pain"],
    "cancer": ["cancer distress"],
    "selfharm": ["self-harm"],
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
}


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

            # Try to fetch abstract/content from the linked paper
            content = None
            if entry["url"]:
                content = self._fetch_paper_content(entry["url"])

            # Build raw_content: abstract if available, otherwise citation
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
                "source_url":        entry["url"] or BASE_URL + PAGE_PATH,
                "hashtags":          entry["hashtags"],
                "last_scraped":      self.today(),
            })

        self.log.info("Total: %d records", len(records))
        self.save(records, "compassionate_mind_therapy.json")
        return records

    def _parse_entries(self, soup) -> list:
        """Extract publication entries from the bibliography page."""
        entries = []

        # Find all paragraphs in the main content area
        main = soup.select_one("main") or soup.select_one("article") or soup.find("body")
        if main is None:
            return entries

        for p in main.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if not text:
                continue

            # A valid entry has: author (year). "Title". Journal. #hashtag
            # Minimum: must contain (2023) and a hashtag
            if "(2023)" not in text:
                continue

            # Extract the linked title
            link = p.find("a", href=True)
            title = ""
            url = ""
            if link:
                title = link.get_text(strip=True)
                href = link["href"]
                if href.startswith("http"):
                    url = href
                elif href.startswith("/"):
                    url = urljoin(BASE_URL, href)
                else:
                    url = href

            # Extract authors (everything before "(2023)")
            authors_match = re.match(r"^(.+?)\(2023\)", text)
            authors = authors_match.group(1).strip().rstrip(",. ") if authors_match else ""

            # If no link title, try to extract title from quotes or after (2023).
            if not title:
                title_match = re.search(r'\(2023\)\.\s*["\u201c]?(.+?)["\u201d]?\.', text)
                title = title_match.group(1).strip() if title_match else ""

            if not title:
                continue

            # Extract hashtags
            hashtags = re.findall(r"#(\w+)", text)

            # Extract journal: text after title, before hashtags
            journal = ""
            if title in text:
                after_title = text.split(title, 1)[-1]
                # Remove hashtags from the tail
                journal_part = re.sub(r"#\w+", "", after_title).strip(" .,;")
                # Clean up
                journal_part = re.sub(r"^\.\s*", "", journal_part)
                journal = journal_part.strip() if len(journal_part) > 3 else ""

            entries.append({
                "title":    title,
                "authors":  authors,
                "journal":  journal,
                "url":      url,
                "hashtags": hashtags,
            })

        return entries

    def _fetch_paper_content(self, url: str) -> str:
        """Attempt to fetch abstract or full text from a paper URL."""
        try:
            soup = self.get(url, retries=1)
            if soup is None:
                return ""

            # Try common abstract selectors used by journal sites
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

            # Fallback: look for meta description (most papers have it)
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                desc = meta["content"].strip()
                if len(desc.split()) >= 15:
                    return desc

            # Fallback: DC.description (used by some publishers)
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

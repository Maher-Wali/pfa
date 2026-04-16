"""
Scraper: DBT Self Help — Blog Articles
URL   : https://dbtselfhelp.com/blog/
License: Public resource site — free to use

The old /html/ static skill pages are gone. Content is now in blog articles,
paginated at /blog/page/{n}/?et_blog.

Confirmed from inspection:
  - Article links are at https://dbtselfhelp.com/... (no www)
  - Article titles are in <h2 class="entry-title"><a href="...">
  - Articles are wrapped in <article class="et_pb_post ...">
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.common import BaseScraper

# No www — confirmed from inspecting actual article href attributes
BASE = "https://dbtselfhelp.com"
BLOG_ROOT = f"{BASE}/blog/"
MAX_PAGES = 30

MODULE_KEYWORDS = {
    "mindfulness":                 ["mindful", "wise mind", "observe", "describe",
                                    "participate", "non-judg", "one-mindful"],
    "distress tolerance":          ["distress", "tipp", "accepts", "self-soothe",
                                    "improve", "radical accept", "crisis",
                                    "willingness", "turning the mind"],
    "emotion regulation":          ["emotion", "please", "opposite action",
                                    "check the facts", "cope ahead", "mastery",
                                    "positive experience", "abc skill"],
    "interpersonal effectiveness": ["dear man", "give skill", "fast skill",
                                    "interpersonal", "relationship",
                                    "assertive", "boundary"],
}

BOILERPLATE_SELECTORS = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    "#sidebar", ".sidebar", ".widget", ".comments", "#comments",
    "script", "style", ".breadcrumb", ".post-navigation",
    ".related", ".author-box",
]


class DBTSelfHelpScraper(BaseScraper):
    def __init__(self):
        super().__init__("dbt_selfhelp", "db2_therapy")

    def run(self) -> list:
        article_urls = self._collect_article_urls()
        self.log.info("Found %d article URLs", len(article_urls))

        records = []
        for url in article_urls:
            soup = self.get(url)
            if soup is None:
                continue

            title = self._extract_title(soup)
            if not title:
                continue

            self.strip_boilerplate(soup, BOILERPLATE_SELECTORS)
            content = self._extract_content(soup)
            if not content or len(content) < 100:
                continue

            records.append({
                "technique_name":    title,
                "aliases":           [],
                "modality":          "DBT",
                "target_conditions": ["BPD", "emotion dysregulation",
                                      "depression", "anxiety", "PTSD"],
                "target_problem":    self._infer_module(title),
                "steps":             None,
                "worked_example":    None,
                "when_to_use":       None,
                "estimated_time":    None,
                "difficulty":        None,
                "raw_content":       content,
                "source":            "DBT Self Help",
                "source_url":        url,
                "last_scraped":      self.today(),
            })
            self.log.info("  Scraped: %s", title)

        self.save(records, "dbt_selfhelp_therapy.json")
        return records

    def _collect_article_urls(self) -> list:
        article_urls = []
        seen = set()

        for page_num in range(1, MAX_PAGES + 1):
            url = BLOG_ROOT if page_num == 1 else f"{BASE}/blog/page/{page_num}/?et_blog"
            self.log.info("Blog index page %d", page_num)
            soup = self.get(url)
            if soup is None:
                break

            links = self._extract_article_links(soup)
            if not links:
                self.log.info("  No articles on page %d — stopping", page_num)
                break

            new = [l for l in links if l not in seen]
            if not new:
                break

            for link in new:
                seen.add(link)
                article_urls.append(link)

            self.log.info("  +%d articles (total %d)", len(new), len(article_urls))

        return article_urls

    def _extract_article_links(self, soup) -> list:
        links = []

        # Primary: confirmed selector from HTML inspection
        for a in soup.select("h2.entry-title a"):
            href = a.get("href", "").strip()
            if href and href not in links:
                links.append(href)

        # Fallback 1: article heading anchors (Divi / other themes)
        if not links:
            for a in soup.select("article h2 a, article h1 a"):
                href = a.get("href", "").strip()
                if href and href not in links:
                    links.append(href)

        # Fallback 2: any internal link that looks like a post permalink
        # (has dbtselfhelp.com domain, is not a category/tag/page/blog index)
        if not links:
            skip = {"/blog/", "/category/", "/tag/", "/page/", "?et_blog",
                    "/author/", "/wp-content/", "#"}
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if BASE not in href:
                    continue
                if any(s in href for s in skip):
                    continue
                # must be longer than the base domain itself
                path = href.replace(BASE, "")
                if len(path) > 1 and href not in links:
                    links.append(href)

        return links

    def _extract_title(self, soup) -> str:
        for sel in ["h1.entry-title", "h1.post-title", "h1"]:
            node = soup.select_one(sel)
            if node:
                return node.get_text(strip=True)
        return ""

    def _extract_content(self, soup) -> str:
        for sel in [".entry-content", ".post-content", "article", "main"]:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""

    def _infer_module(self, title: str) -> str:
        t = title.lower()
        for module, keywords in MODULE_KEYWORDS.items():
            if any(kw in t for kw in keywords):
                return module
        return "general DBT"


if __name__ == "__main__":
    DBTSelfHelpScraper().run()

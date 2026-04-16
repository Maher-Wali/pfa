"""
test_scraper.py — one-page smoke test for every scraper
========================================================
Fetches ONE representative URL from each source (HTML or PDF) and reports
PASS / FAIL / BLOCKED without writing anything to disk.

Run from the project root:
    .venv\\Scripts\\python.exe scraping/test_scraper.py

Sections
--------
  A — Previously confirmed PASS (re-verified each run)
  B — Previously broken sources with targeted fixes applied
  C — New sources (MedlinePlus, Better Health, RC Psych, CAMH, CCI WA)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.common import BaseScraper
from utils.pdf_extractor import extract_text

SEP = "-" * 70

# Extra headers for WAF-protected sites
_BOT_GUARD = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_readable(text: str) -> bool:
    if not text or len(text) < 30:
        return False
    letter_ratio = sum(c.isalpha() for c in text) / len(text)
    words = text.split()
    avg_word_len = sum(len(w) for w in words) / max(len(words), 1)
    return letter_ratio >= 0.50 and avg_word_len >= 2.5


results: list[tuple[str, str]] = []   # (source_name, status)


def report(source: str, url: str, content: str):
    print(f"\n{SEP}")
    print(f"SOURCE : {source}")
    print(f"URL    : {url}")

    if not content:
        print("RESULT : BLOCKED / EMPTY")
        results.append((source, "BLOCKED"))
        return

    readable = is_readable(content)
    letters = sum(c.isalpha() for c in content) / max(len(content), 1)
    words = content.split()
    avg_wl = sum(len(w) for w in words) / max(len(words), 1)
    status = "PASS" if readable else "FAIL"
    results.append((source, status))
    print(f"RESULT : {status}  (letter_ratio={letters:.2f}, avg_word_len={avg_wl:.1f}, len={len(content)})")
    preview = "".join(c if c.isprintable() else "?" for c in content[:350])
    print(f"PREVIEW: {preview}")


class _Tester(BaseScraper):
    def __init__(self):
        super().__init__("test", "test", delay_range=(0.8, 1.5))

    def html(self, url: str, selectors: list[str],
             boilerplate: list[str], extra_headers: dict | None = None) -> str:
        soup = self.get(url, extra_headers=extra_headers)
        if soup is None:
            return ""
        self.strip_boilerplate(soup, boilerplate)
        for sel in selectors:
            node = soup.select_one(sel)
            if node:
                return self.clean(node.get_text(separator=" "))
        body = soup.find("body")
        return self.clean(body.get_text(separator=" ")) if body else ""

    def pdf(self, url: str, referer: str | None = None) -> str:
        raw = self.download_bytes(url, referer=referer)
        if raw is None:
            return ""
        return self.clean(extract_text(raw))


BP = [
    "nav", "header", "footer", ".site-header", ".site-footer",
    ".breadcrumb", "script", "style", ".sidebar",
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Smoke-testing all scrapers — one request each.\n")
    t = _Tester()

    # ===================================================================
    # SECTION A — Previously confirmed PASS (brotli fix)
    # ===================================================================
    print(f"\n{'='*70}")
    print("SECTION A — Previously PASS (regression check)")
    print(f"{'='*70}")

    report("Beyond Blue",
           "https://www.beyondblue.org.au/the-facts/depression",
           t.html("https://www.beyondblue.org.au/the-facts/depression",
                  ["main", "article", ".page-content", "#content"],
                  BP + [".emergency-help-widget", ".donate-cta"]))

    report("Mental Health Foundation",
           "https://www.mentalhealth.org.uk/explore-mental-health/a-z-topics/depression",
           t.html("https://www.mentalhealth.org.uk/explore-mental-health/a-z-topics/depression",
                  ["main", "article", ".page-content", "#content"],
                  BP + [".donate", ".newsletter"]))

    report("GetSelfHelp (HTML)",
           "https://www.getselfhelp.co.uk/cbt.htm",
           t.html("https://www.getselfhelp.co.uk/cbt.htm",
                  ["body"], BP + [".menu", "#menu", ".copyright"]))

    # ===================================================================
    # SECTION B — Previously broken, fixes applied
    # ===================================================================
    print(f"\n{'='*70}")
    print("SECTION B — Previously broken (fix: Referer / .html / headers)")
    print(f"{'='*70}")

    # GetSelfHelp PDF — fix: Referer header (was 403, now 404 — URL changed)
    report("GetSelfHelp (PDF) [Referer fix — may still 404 if URL moved]",
           "https://www.getselfhelp.co.uk/docs/ThoughtRecord7.pdf",
           t.pdf("https://www.getselfhelp.co.uk/docs/ThoughtRecord7.pdf",
                 referer="https://www.getselfhelp.co.uk/"))

    # Simply Psychology — fix: .html extension
    report("Simply Psychology (.html slug)",
           "https://www.simplypsychology.org/cognitive-behavioral-therapy.html",
           t.html("https://www.simplypsychology.org/cognitive-behavioral-therapy.html",
                  ["article", "main", ".entry-content", "#main-content"],
                  BP + ["#comments", ".references", ".author"]))

    # Self-Compassion.org — fix: different page + broader selectors
    report("Self-Compassion.org (exercise page)",
           "https://self-compassion.org/exercise-2-critical-self-talk/",
           t.html("https://self-compassion.org/exercise-2-critical-self-talk/",
                  [".entry-content", "article", ".post-content", "main"],
                  BP + [".widget-area", ".related-posts", "#comments"]))

    # Positive Psychology — fix: browser headers
    report("Positive Psychology (browser headers)",
           "https://positivepsychology.com/three-good-things/",
           t.html("https://positivepsychology.com/three-good-things/",
                  ["article", ".entry-content", "main", ".post-content"],
                  BP + [".newsletter-form", ".author-bio"],
                  extra_headers={**_BOT_GUARD,
                                  "Referer": "https://www.google.com/"}))

    # Therapist Aid — fix: browser headers
    report("Therapist Aid (browser headers)",
           "https://www.therapistaid.com/therapy-article/dbt",
           t.html("https://www.therapistaid.com/therapy-article/dbt",
                  ["article", ".article-content", "main"],
                  BP + [".related-worksheets", ".download-button"],
                  extra_headers={**_BOT_GUARD,
                                  "Referer": "https://www.google.com/"}))

    # ===================================================================
    # SECTION C — New sources
    # ===================================================================
    print(f"\n{'='*70}")
    print("SECTION C — New sources")
    print(f"{'='*70}")

    # MedlinePlus
    report("MedlinePlus",
           "https://medlineplus.gov/depression.html",
           t.html("https://medlineplus.gov/depression.html",
                  ["div.section", "section", "#ency-summary",
                   ".health-topic-summary", "main"],
                  BP + ["#side-nav", ".section-related-topics"]))

    # Better Health Channel
    report("Better Health Channel",
           "https://www.betterhealth.vic.gov.au/health/conditionsandtreatments/depression",
           t.html("https://www.betterhealth.vic.gov.au/health/conditionsandtreatments/depression",
                  ["main", "article", ".page-content", "#content", ".content"],
                  BP + [".related-articles", ".feedback"]))

    # Royal College of Psychiatrists
    report("Royal College of Psychiatrists",
           "https://www.rcpsych.ac.uk/mental-health/problems-disorders/depression",
           t.html("https://www.rcpsych.ac.uk/mental-health/problems-disorders/depression",
                  ["main", "article", ".wysiwyg-content", ".rich-text",
                   ".page-content", "#content"],
                  BP + [".related-content", ".social-share", ".alert"]))

    # CAMH
    report("CAMH",
           "https://www.camh.ca/en/health-info/mental-illness-and-addiction-index/depression",
           t.html("https://www.camh.ca/en/health-info/mental-illness-and-addiction-index/depression",
                  ["main", "article", ".contentArea", "#main-content",
                   ".field--type-text-with-summary"],
                  BP + [".related", ".social-links", ".alert-bar"]))

    # CCI WA — HTML overview
    cci_url = "https://www.cci.health.wa.gov.au/Resources/Looking-After-Yourself/Depression"
    report("CCI WA (HTML overview)",
           cci_url,
           t.html(cci_url,
                  ["main", ".content", "#content", ".page-content", "article", "body"],
                  BP + [".topnav", "#top-nav"]))

    # CCI WA — PDF module (discover first PDF link on the depression page)
    soup = t.get(cci_url)
    cci_pdf_url = ""
    cci_pdf_content = ""
    if soup:
        from urllib.parse import urljoin
        for a in soup.find_all("a", href=True):
            if a["href"].lower().endswith(".pdf"):
                cci_pdf_url = urljoin(cci_url, a["href"])
                break
    if cci_pdf_url:
        cci_pdf_content = t.pdf(cci_pdf_url, referer=cci_url)
    report("CCI WA (first PDF module)", cci_pdf_url or "no PDF found", cci_pdf_content)

    # ===================================================================
    # Summary
    # ===================================================================
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    pass_count  = sum(1 for _, s in results if s == "PASS")
    fail_count  = sum(1 for _, s in results if s == "FAIL")
    block_count = sum(1 for _, s in results if s == "BLOCKED")
    print(f"  PASS:    {pass_count}")
    print(f"  FAIL:    {fail_count}")
    print(f"  BLOCKED: {block_count}")
    print()
    for name, status in results:
        icon = {"PASS": "✓", "FAIL": "✗", "BLOCKED": "⊘"}.get(status, "?")
        print(f"  {icon} {status:<8}  {name}")
    print(f"\n{'='*70}")
    print("""
PASS    → ready for full scrape
FAIL    → fetched but unreadable — share the preview for diagnosis
BLOCKED → JS-rendered or hard WAF block — needs Playwright or skip
""")


if __name__ == "__main__":
    main()

"""
Shared base scraper and utility functions used by all source-specific scrapers.
"""
import json
import logging
import random
import re
import time
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# All raw output lands under scraping/../data/raw/
OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


class BaseScraper:
    """
    Handles session management, rate limiting, retries, and JSON persistence.
    Every source-specific scraper inherits from this and implements run().
    """

    def __init__(self, source_name: str, db: str, delay_range: tuple = (1.5, 3.5)):
        self.source_name = source_name
        self.out_dir = OUTPUT_ROOT / db / source_name
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay_range
        self.session = requests.Session()
        self.log = logging.getLogger(source_name)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def get(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """Fetch a URL and return a BeautifulSoup object, or None on failure."""
        for attempt in range(retries):
            try:
                resp = self.session.get(url, headers=self._headers(), timeout=20)
                resp.raise_for_status()
                self._wait()
                return BeautifulSoup(resp.text, "lxml")
            except requests.RequestException as exc:
                self.log.warning(
                    "Attempt %d/%d failed for %s: %s", attempt + 1, retries, url, exc
                )
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))  # exponential back-off
        self.log.error("All retries exhausted for %s", url)
        return None

    def download_bytes(self, url: str, retries: int = 3) -> Optional[bytes]:
        """Download raw bytes (for PDFs)."""
        for attempt in range(retries):
            try:
                resp = self.session.get(url, headers=self._headers(), timeout=40)
                resp.raise_for_status()
                self._wait()
                return resp.content
            except requests.RequestException as exc:
                self.log.warning(
                    "Download attempt %d/%d failed for %s: %s",
                    attempt + 1, retries, url, exc,
                )
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))
        self.log.error("Binary download failed for %s", url)
        return None

    def _wait(self):
        time.sleep(random.uniform(*self.delay))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, records: list, filename: str):
        path = self.out_dir / filename
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False, default=str)
        self.log.info("Saved %d records → %s", len(records), path)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def today() -> str:
        return date.today().isoformat()

    @staticmethod
    def clean(text: str) -> str:
        """Collapse whitespace, remove wiki-style edit markers."""
        text = re.sub(r"\[edit\]|\[citation needed\]|\[.*?\]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def strip_boilerplate(soup: BeautifulSoup, selectors: list) -> BeautifulSoup:
        """Remove nav, footer, and other boilerplate elements in-place."""
        for sel in selectors:
            for tag in soup.select(sel):
                tag.decompose()
        return soup

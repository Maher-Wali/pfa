import os
import re
import time
import json
import hashlib
import requests
import pandas as pd
import trafilatura
import fitz  # PyMuPDF

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag

# =========================
# CONFIG
# =========================
SAVE_DIR = "/kaggle/working/db1_scrape"
os.makedirs(SAVE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MH-RAG-DB1/1.0; +https://example.com)"
}

MAX_PAGES_PER_SOURCE = 250
REQUEST_TIMEOUT = 30
SLEEP_SECONDS = 0.7

# Existing + expanded DB1 sources
DB1_SOURCES = {
    "NHS": {
        "seed_urls": [
            "https://www.nhs.uk/mental-health/conditions/"
        ],
        "allowed_domains": ["www.nhs.uk", "nhs.uk"],
        "allowed_path_keywords": [
            "/mental-health/conditions/"
        ]
    },
    "NICE": {
        "seed_urls": [
            "https://www.nice.org.uk/guidance/indevelopment/gid-hub10005",
            "https://www.nice.org.uk/guidance/conditions-and-diseases/mental-health-behavioural-and-neurodevelopmental-conditions"
        ],
        "allowed_domains": ["www.nice.org.uk", "nice.org.uk"],
        "allowed_path_keywords": [
            "/guidance/ng",
            "/guidance/cg",
            "/guidance/qs",
            "/guidance/conditions-and-diseases/mental-health",
            "/guidance/indevelopment/gid-hub10005"
        ]
    },
    "NIMH": {
        "seed_urls": [
            "https://www.nimh.nih.gov/health/topics",
            "https://www.nimh.nih.gov/health/publications"
        ],
        "allowed_domains": ["www.nimh.nih.gov", "nimh.nih.gov"],
        "allowed_path_keywords": [
            "/health/topics/",
            "/health/publications/"
        ]
    },
    "WHO": {
        "seed_urls": [
            "https://www.who.int/news-room/fact-sheets/detail/mental-disorders",
            "https://www.who.int/teams/mental-health-and-substance-use/treatment-care/mental-health-gap-action-programme"
        ],
        "allowed_domains": ["www.who.int", "who.int"],
        "allowed_path_keywords": [
            "/teams/mental-health-and-substance-use/",
            "/news-room/fact-sheets/detail/mental-disorders",
            "/publications/"
        ]
    },
    "Mental Health Foundation": {
        "seed_urls": [
            "https://www.mentalhealth.org.uk/explore-mental-health/a-z-topics/anxiety",
            "https://www.mentalhealth.org.uk/explore-mental-health/a-z-topics/stress",
            "https://www.mentalhealth.org.uk/explore-mental-health/a-z-topics/trauma",
            "https://www.mentalhealth.org.uk/explore-mental-health"
        ],
        "allowed_domains": ["www.mentalhealth.org.uk", "mentalhealth.org.uk"],
        "allowed_path_keywords": [
            "/explore-mental-health/",
            "/our-work/public-engagement/mental-health-awareness-week/",
            "/sites/default/files/"
        ]
    },
    "Beyond Blue": {
        "seed_urls": [
            "https://www.beyondblue.org.au/mental-health/conditions",
            "https://www.beyondblue.org.au/mental-health/resource-library",
            "https://www.beyondblue.org.au/mental-health/loneliness",
            "https://www.beyondblue.org.au/mental-health/mental-health-information-in-your-language"
        ],
        "allowed_domains": ["www.beyondblue.org.au", "beyondblue.org.au"],
        "allowed_path_keywords": [
            "/mental-health/conditions",
            "/mental-health/resource-library",
            "/mental-health/"
        ]
    },
    "CAMH": {
        "seed_urls": [
            "https://www.camh.ca/en/health-info/mental-illness-and-addiction-index",
            "https://www.camh.ca/en/health-info/mental-health-101"
        ],
        "allowed_domains": ["www.camh.ca", "camh.ca"],
        "allowed_path_keywords": [
            "/en/health-info/mental-illness-and-addiction-index",
            "/en/health-info/mental-health-101",
            "/en/health-info/guides-and-publications",
            "/en/health-info/"
        ]
    },
    "MedlinePlus": {
        "seed_urls": [
            "https://medlineplus.gov/mentaldisorders.html"
        ],
        "allowed_domains": ["medlineplus.gov", "www.nlm.nih.gov", "www.ncbi.nlm.nih.gov"],
        "allowed_path_keywords": [
            "/mentaldisorders",
            "/anxiety",
            "/depression",
            "/bipolardisorder",
            "/obsessivecompulsivedisorder",
            "/schizophrenia",
            "/posttraumaticstressdisorder",
            "/eatingdisorders",
            "/personalitydisorders"
        ]
    },
    "Rethink Mental Illness": {
        "seed_urls": [
            "https://www.rethink.org/advice-and-information/about-mental-illness/mental-health-conditions/",
            "https://www.rethink.org/advice-and-information/browse-all-topics/"
        ],
        "allowed_domains": ["www.rethink.org", "rethink.org"],
        "allowed_path_keywords": [
            "/advice-and-information/about-mental-illness/mental-health-conditions/",
            "/advice-and-information/browse-all-topics/",
            "/news-and-stories/commonly-asked-mental-health-questions/"
        ]
    },
    "Cleveland Clinic": {
        "seed_urls": [
            "https://my.clevelandclinic.org/health/diseases/22295-mental-health-disorders",
            "https://my.clevelandclinic.org/health/diseases/9536-anxiety-disorders",
            "https://my.clevelandclinic.org/health/articles/mental-health"
        ],
        "allowed_domains": ["my.clevelandclinic.org", "clevelandclinic.org"],
        "allowed_path_keywords": [
            "/health/diseases/",
            "/health/articles/"
        ]
    }
}

SECTION_KEYWORDS = {
    "overview": ["overview", "about", "what is", "introduction"],
    "symptoms": ["symptom", "signs"],
    "causes": ["cause", "risk factor", "why it happens"],
    "diagnosis": ["diagnos", "assessment", "tests"],
    "treatment": ["treat", "therapy", "medication", "management"],
    "self_help": ["self-help", "coping", "help yourself", "lifestyle", "support yourself"],
    "living_with": ["living with", "recovery", "day to day", "wellbeing"],
    "when_to_seek_help": ["urgent help", "when to get help", "seek help", "emergency"]
}

CONDITION_TERMS = [
    "depression", "anxiety", "panic", "ocd", "obsessive compulsive",
    "ptsd", "post-traumatic stress", "bipolar", "psychosis", "schizophrenia",
    "eating disorder", "anorexia", "bulimia", "binge eating",
    "autism", "adhd", "personality disorder", "borderline personality",
    "self-harm", "suicide", "stress", "trauma", "phobia", "social anxiety",
    "body dysmorphic", "seasonal affective", "loneliness", "grief"
]

# =========================
# HELPERS
# =========================
def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    return url.strip()

def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()

def is_pdf_url(url: str) -> bool:
    return url.lower().endswith(".pdf")

def make_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def fetch(url: str):
    r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r

def extract_title_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.title:
        return clean_text(soup.title.get_text(" ", strip=True))
    return ""

def extract_html_text(html: str, url: str) -> str:
    text = trafilatura.extract(
        html,
        include_tables=True,
        include_comments=False,
        favor_precision=True,
        url=url
    )
    return clean_text(text)

def extract_pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    return clean_text("\n".join(pages))

def classify_section(title: str, text: str) -> str:
    blob = f"{title} {text[:1500]}".lower()
    scores = {}
    for sec, kws in SECTION_KEYWORDS.items():
        scores[sec] = sum(kw in blob for kw in kws)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"

def detect_conditions(title: str, text: str):
    blob = f"{title} {text[:5000]}".lower()
    found = sorted({term for term in CONDITION_TERMS if term in blob})
    return found

def is_allowed(url: str, source_cfg: dict) -> bool:
    dom = get_domain(url)
    if dom not in [d.lower() for d in source_cfg["allowed_domains"]]:
        return False
    path = urlparse(url).path.lower()
    if is_pdf_url(url):
        return True
    return any(k.lower() in path for k in source_cfg["allowed_path_keywords"])

def harvest_links(html: str, base_url: str, source_cfg: dict):
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = normalize_url(urljoin(base_url, a["href"]))
        if href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        if is_allowed(href, source_cfg):
            links.add(href)
    return links

def extract_document(url: str):
    try:
        r = fetch(url)
        ctype = r.headers.get("Content-Type", "").lower()

        if "pdf" in ctype or is_pdf_url(url):
            title = os.path.basename(urlparse(url).path) or "document.pdf"
            text = extract_pdf_text(r.content)
            source_type = "pdf"
            links = set()
        else:
            html = r.text
            title = extract_title_from_html(html)
            text = extract_html_text(html, url)
            source_type = "html"
            links = set()

        return {
            "ok": True,
            "url": url,
            "title": title,
            "text": text,
            "source_type": source_type,
            "links": links
        }
    except Exception as e:
        return {
            "ok": False,
            "url": url,
            "title": "",
            "text": "",
            "source_type": "error",
            "links": set(),
            "error": str(e)
        }

# =========================
# MAIN SCRAPER
# =========================
all_records = []
seen_urls = set()
seen_content_hashes = set()

for source_name, cfg in DB1_SOURCES.items():
    print(f"\n=== SOURCE: {source_name} ===")
    queue = list(cfg["seed_urls"])
    local_seen = set()
    saved = 0

    while queue and saved < MAX_PAGES_PER_SOURCE:
        url = normalize_url(queue.pop(0))
        if url in local_seen:
            continue
        local_seen.add(url)

        if not is_allowed(url, cfg):
            continue

        print("Fetching:", url)
        result = extract_document(url)
        time.sleep(SLEEP_SECONDS)

        if not result["ok"]:
            print("  -> failed:", result.get("error", "unknown error"))
            continue

        text = result["text"]
        title = result["title"]

        if len(text) < 700:
            print("  -> skipped: too short")
            continue

        content_hash = make_hash(text[:12000].lower())
        if content_hash in seen_content_hashes:
            print("  -> skipped: duplicate content")
            continue

        section = classify_section(title, text)
        conditions = detect_conditions(title, text)

        rec = {
            "condition": "; ".join(conditions) if conditions else "",
            "aliases": "",
            "source": source_name,
            "source_url": url,
            "section": section,
            "content": text,
            "icd11_code": "",
            "last_scraped": pd.Timestamp.utcnow().isoformat(),
            "title": title,
            "source_type": result["source_type"]
        }

        all_records.append(rec)
        seen_content_hashes.add(content_hash)
        seen_urls.add(url)
        saved += 1
        print(f"  -> saved ({saved}) [{section}]")

        # crawl only html pages
        if result["source_type"] == "html":
            try:
                html = fetch(url).text
                links = harvest_links(html, url, cfg)
                for link in links:
                    if link not in local_seen and link not in queue:
                        queue.append(link)
            except Exception:
                pass

print("\nTotal raw DB1 records:", len(all_records))

# =========================
# POSTPROCESS + SAVE
# =========================
df = pd.DataFrame(all_records)

if len(df):
    df["norm_key"] = (
        df["source"].fillna("").str.lower().str.strip() + "||" +
        df["source_url"].fillna("").str.lower().str.strip()
    )
    df = df.drop_duplicates(subset=["norm_key"]).drop(columns=["norm_key"]).reset_index(drop=True)

    # remove near-empty / nav-heavy text
    df = df[df["content"].str.len() >= 700].reset_index(drop=True)

csv_path = os.path.join(SAVE_DIR, "db1_clinical_records.csv")
jsonl_path = os.path.join(SAVE_DIR, "db1_clinical_records.jsonl")

df.to_csv(csv_path, index=False)

with open(jsonl_path, "w", encoding="utf-8") as f:
    for _, row in df.iterrows():
        f.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")

print(f"\nSaved CSV : {csv_path}")
print(f"Saved JSONL: {jsonl_path}")
print("\nSource counts:")
print(df["source"].value_counts())
print("\nSection counts:")
print(df["section"].value_counts())
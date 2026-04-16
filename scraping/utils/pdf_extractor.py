"""
PDF text extraction utilities used by scrapers that download workbooks/guides.
Uses pdfplumber, which handles multi-column layouts better than PyPDF2.
"""
import io
import logging
import re
from pathlib import Path
from typing import Union

import pdfplumber

log = logging.getLogger("pdf_extractor")


def extract_text(source: Union[bytes, Path, str]) -> str:
    """
    Extract plain text from a PDF.
    Accepts raw bytes (from an HTTP download) or a file path.
    Returns an empty string on failure — never raises.
    """
    try:
        if isinstance(source, (str, Path)):
            pdf_obj = pdfplumber.open(source)
        else:
            pdf_obj = pdfplumber.open(io.BytesIO(source))

        pages = []
        with pdf_obj:
            for page in pdf_obj.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=2)
                if text:
                    pages.append(text.strip())

        return "\n\n".join(pages)
    except Exception as exc:
        log.error("PDF extraction failed: %s", exc)
        return ""


def split_by_headings(text: str) -> dict:
    """
    Best-effort split of PDF text into named sections by detecting headings.
    Headings are identified as short lines (≤ 70 chars) in title or upper case
    that appear at the start of a line.

    Returns a dict of {heading_text: body_text}.
    Falls back to {"full_text": text} if no headings are detected.
    """
    # Heuristic: a heading is a line of 3–70 chars that is mostly capitalised
    pattern = re.compile(
        r"^([A-Z][A-Za-z0-9 \-:,/]{2,69})\n",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))

    if not matches:
        return {"full_text": text}

    sections: dict = {}
    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections[heading] = body

    return sections

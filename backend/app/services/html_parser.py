from __future__ import annotations

from typing import List, Tuple
from bs4 import BeautifulSoup

# Returns list of (page_number starting at 1, text) extracted from HTML
# Strategy: collect text from headings, paragraphs, and list items, then
# segment into ~1500-char "pages" for downstream chunking.

def extract_pages_from_html(html_bytes: bytes, target_chars: int = 1500) -> List[Tuple[int, str]]:
    soup = BeautifulSoup(html_bytes, "lxml")
    parts: List[str] = []

    # Prefer structured elements first
    for el in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        txt = el.get_text(separator=" ", strip=True)
        if not txt:
            continue
        if el.name in ("h1", "h2", "h3"):
            parts.append(txt.upper())
        elif el.name == "li":
            parts.append(f"• {txt}")
        else:
            parts.append(txt)

    # Fallback to full text if structured parse produced nothing
    if not parts:
        full = soup.get_text(separator="\n", strip=True)
        if full:
            parts = [full]

    joined = "\n\n".join(parts)

    pages: List[Tuple[int, str]] = []
    if not joined:
        return pages

    i = 0
    page_no = 1
    n = len(joined)
    while i < n:
        j = min(n, i + target_chars)
        # try to break on paragraph boundary if possible
        k = joined.rfind("\n\n", i, j)
        if k == -1 or (j - i) < 600:  # small slices: don't force boundary
            k = j
        else:
            k = k + 2  # include the delimiter
        pages.append((page_no, joined[i:k].strip()))
        page_no += 1
        i = k
    return pages

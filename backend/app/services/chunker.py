from typing import List, Tuple, Optional
import re
import uuid
from app.models.types import Chunk

# Naive chunking with lightweight section detection: group paragraphs ~1200 chars

COMMON_HEADINGS = [
    # Typical SEC / earnings headings
    r"Management[’']?s\s+Discussion\s+and\s+Analysis",
    r"MD&A",
    r"Risk\s+Factors",
    r"Business",
    r"Financial\s+Statements",
    r"Liquidity\s+and\s+Capital\s+Resources",
    r"Share\s+Repurchases|Stock\s+Repurchase|Share\s+Buybacks|Repurchase\s+Program",
    r"Cash\s+Flows|Free\s+Cash\s+Flow|FCF",
    r"Results\s+of\s+Operations",
    r"Overview",
    r"Forward[- ]Looking\s+Statements",
]
HEADINGS_RE = re.compile("|".join(COMMON_HEADINGS), re.IGNORECASE)


def _split_paragraphs(text: str) -> List[str]:
    # Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split on double newlines as paragraphs
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return parts if parts else ([text] if text.strip() else [])


def _is_heading(para: str) -> bool:
    # Heuristic: short line, few punctuation, either all/mostly caps or matches known headings
    if len(para) > 120:
        return False
    if HEADINGS_RE.search(para):
        return True
    # Check caps ratio on alphabetic chars
    letters = [c for c in para if c.isalpha()]
    if not letters:
        return False
    caps = sum(1 for c in letters if c.isupper())
    ratio = caps / max(1, len(letters))
    # Allow headings that are mostly uppercase
    return ratio >= 0.85


def chunk_pages(pages: List[Tuple[int, str]], target_chars: int = 1200, overlap_chars: int = 200) -> List[Chunk]:
    chunks: List[Chunk] = []
    buf: List[str] = []
    buf_len = 0
    current_start: Optional[int] = None
    current_section: Optional[str] = None
    for page_num, text in pages:
        paras = _split_paragraphs(text)
        for para in paras:
            # Update current section if we encounter a heading-like paragraph
            if _is_heading(para):
                # Flush any current buffer as a chunk before switching section
                if buf and current_start is not None:
                    chunk_text = "\n\n".join(buf)
                    chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        text=chunk_text,
                        section=current_section,
                        page_start=current_start,
                        page_end=page_num,
                    ))
                    # Start new buffer fresh after heading (no overlap to avoid mixing headers)
                    buf = []
                    buf_len = 0
                current_section = para.strip()[:80]
                # Do not include heading text itself in chunks; move on to next paragraph
                current_start = page_num if current_start is None else current_start
                continue

            if current_start is None:
                current_start = page_num

            # If adding exceeds target, flush current chunk
            if buf_len + len(para) + 1 > target_chars and buf:
                chunk_text = "\n\n".join(buf)
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    text=chunk_text,
                    section=current_section,
                    page_start=current_start,
                    page_end=page_num,
                ))
                # Start new buffer with overlap
                tail = chunk_text[-overlap_chars:] if overlap_chars > 0 else ""
                buf = [tail, para] if tail else [para]
                buf_len = len(para) + len(tail)
                current_start = page_num
            else:
                buf.append(para)
                buf_len += len(para) + 2
    # Flush remaining buffer
    if buf and current_start is not None:
        chunk_text = "\n\n".join(buf)
        last_page = pages[-1][0] if pages else 1
        chunks.append(Chunk(
            id=str(uuid.uuid4()),
            text=chunk_text,
            section=current_section,
            page_start=current_start,
            page_end=last_page,
        ))
    return chunks

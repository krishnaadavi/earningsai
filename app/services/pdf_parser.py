from typing import List, Tuple
import fitz  # PyMuPDF

# Returns list of (page_number starting at 1, text)
def extract_pages_from_pdf(file_bytes: bytes) -> List[Tuple[int, str]]:
    pages: List[Tuple[int, str]] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            pages.append((i + 1, text))
    return pages

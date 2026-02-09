import re
from typing import List, Tuple, Dict
from app.models.types import Chunk

# Very simple regex-based extractor for Phase 0
# Looks for patterns like: Q1 2024 ... $1.2B or 1.2 billion / 300 million

VAL_RE = re.compile(r"\$?([0-9][0-9,\.]*)(?:\s*(b|bn|billion|m|mm|million))?", re.I)


def _parse_val(s: str) -> float:
    m = VAL_RE.search(s)
    if not m:
        return None  # type: ignore
    num = m.group(1).replace(",", "")
    unit = (m.group(2) or '').lower()
    val = float(num)
    if unit in ("b", "bn", "billion"):
        val *= 1_000
    return val


def extract_series(chunks: List[Chunk]) -> Dict[str, list]:
    labels: List[str] = []
    values: List[float] = []
    # naive: scan top chunks for lines starting with Q1/Q2/Q3/Q4 or FY
    text = "\n".join(c.text for c in chunks)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(Q[1-4]|FY)\s*\d{4}", line, re.I):
            label = re.findall(r"^(Q[1-4]|FY)\s*\d{4}", line, re.I)[0]
            val = _parse_val(line)
            if val is not None:
                labels.append(label.upper())
                values.append(val)
        # stop when we have a small series
        if len(labels) >= 6:
            break
    return {"labels": labels, "values": values}

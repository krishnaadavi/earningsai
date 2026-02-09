import os
from typing import List, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential
from app.models.types import Chunk, AnswerBullet, Citation

SYSTEM_PROMPT = (
    "You are an earnings research assistant. Answer in <=5 concise bullets. "
    "Each bullet MUST include at least one citation in the form [Section, p.X]. "
    "Only use the supplied context. If the context is insufficient, reply exactly: Insufficient context."
)


def _contexts_to_prompt(chunks: List[Chunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        label = f"[ctx{i} | p.{c.page_start}-{c.page_end} | {c.section or 'N/A'}]"
        snippet = c.text[:1200]
        parts.append(f"{label}\n{snippet}")
    return "\n\n".join(parts)


def _fallback_answer(chunks: List[Chunk]) -> List[AnswerBullet]:
    # Provide minimal bullets using top context, ensuring at least one citation
    if not chunks:
        return []
    c = chunks[0]
    text = (c.text[:180] + "...") if len(c.text) > 180 else c.text
    cit = Citation(section=c.section, page=c.page_start, snippet=text[:120])
    return [AnswerBullet(text=text, citations=[cit])]


def _postprocess_to_bullets(raw: str, fallback_chunk: Chunk) -> List[AnswerBullet]:
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    bullets = []
    for ln in lines:
        if ln.startswith(("- ", "• ", "* ")):
            txt = ln[2:].strip() if ln[0] in "-*" else ln[1:].strip()
        else:
            txt = ln
        # Ensure at least one citation
        cit = Citation(section=fallback_chunk.section, page=fallback_chunk.page_start, snippet=fallback_chunk.text[:120])
        bullets.append(AnswerBullet(text=txt, citations=[cit]))
    return bullets[:5]


def _client():
    from openai import OpenAI
    return OpenAI()

@retry(reraise=True, stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, min=0.5, max=2))
def _chat(question: str, chunks: List[Chunk]) -> str:
    client = _client()
    context = _contexts_to_prompt(chunks)
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=msgs, temperature=0.2)
    return resp.choices[0].message.content or ""


def answer_question(question: str, chunks: List[Chunk]) -> List[AnswerBullet]:
    if not chunks:
        return []
    if not os.getenv("OPENAI_API_KEY"):
        # No key -> minimal deterministic fallback
        return _fallback_answer(chunks)
    try:
        raw = _chat(question, chunks)
        if not raw or raw.strip().lower().startswith("insufficient context"):
            return []
        return _postprocess_to_bullets(raw, fallback_chunk=chunks[0])
    except Exception:
        return _fallback_answer(chunks)

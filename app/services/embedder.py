import os
import hashlib
from typing import List
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential
from app.services.metrics import now, elapsed_ms, record_llm

EMBED_DIM = 1536  # text-embedding-3-small

# Fallback deterministic embedding when OPENAI_API_KEY is not set

def _fallback_embed(texts: List[str]) -> np.ndarray:
    vecs = []
    for t in texts:
        seed = int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        v = rng.random(EMBED_DIM, dtype=np.float32)
        # normalize
        v = v / (np.linalg.norm(v) + 1e-8)
        vecs.append(v)
    return np.stack(vecs, axis=0)


def _openai_client():
    from openai import OpenAI  # lazy import
    return OpenAI()

@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
def _embed_openai(texts: List[str]) -> np.ndarray:
    client = _openai_client()
    resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
    emb = [d.embedding for d in resp.data]
    return np.array(emb, dtype=np.float32)


def embed_texts(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)
    if os.getenv("OPENAI_API_KEY"):
        t0 = now()
        try:
            out = _embed_openai(texts)
            record_llm("openai", "text-embedding-3-small", latency_ms=elapsed_ms(t0), ok=True)
            return out
        except Exception:
            # record failure on OpenAI path
            record_llm("openai", "text-embedding-3-small", latency_ms=elapsed_ms(t0), ok=False)
            t1 = now()
            out = _fallback_embed(texts)
            record_llm("embedder-fallback", "deterministic", latency_ms=elapsed_ms(t1), ok=True)
            return out
    else:
        t1 = now()
        out = _fallback_embed(texts)
        record_llm("embedder-fallback", "deterministic", latency_ms=elapsed_ms(t1), ok=True)
        return out

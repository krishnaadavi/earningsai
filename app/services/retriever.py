from typing import List, Tuple, Dict, Any
import numpy as np
from app.models.types import Chunk

class Index:
    def __init__(self, embeddings: np.ndarray, chunks: List[Chunk]):
        self.embeddings = embeddings  # shape (N, D)
        self.chunks = chunks
        self.norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Tuple[Chunk, float]]:
        if query_vec.ndim == 1:
            q = query_vec[None, :]
        else:
            q = query_vec
        q = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-8)
        sims = (self.embeddings @ q.T) / self.norms  # (N,1)
        sims = sims.squeeze(-1)
        idx = np.argsort(-sims)[:top_k]
        return [(self.chunks[i], float(sims[i])) for i in idx]


def build_index(embeddings: np.ndarray, chunks: List[Chunk]) -> Index:
    return Index(embeddings, chunks)

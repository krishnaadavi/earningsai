from typing import Dict, Any

# In-memory store: doc_id -> {"chunks": List[Chunk], "embeddings": np.ndarray, "meta": {...}}
# Embeddings are stored server-side; we only return counts/ids to clients.
documents: Dict[str, Any] = {}

# Simple budget counters per process (Phase 0)
budget = {
    "queries": 0
}

import os
from fastapi import HTTPException
from app.memory import store


def _max_queries() -> int:
    try:
        return int(os.getenv("BUDGET_MAX_QUERIES", "50"))
    except Exception:
        return 50


def check_and_increment_query_budget() -> None:
    """Raises 429 if the per-process query cap is exceeded."""
    curr = int(store.budget.get("queries", 0))
    if curr >= _max_queries():
        raise HTTPException(status_code=429, detail="Query cap exceeded for this server session")
    store.budget["queries"] = curr + 1

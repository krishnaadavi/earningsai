from fastapi import APIRouter, Query
from typing import Optional
import os

from app.db.base import db_session
from app.db import base as db_base

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/db")
def health_db(doc_id: Optional[str] = Query(default=None, description="Optional doc_id to verify existence")):
    env_present = bool(os.getenv("DATABASE_URL", "").strip())
    engine_init = getattr(db_base, "engine", None) is not None
    session_init = getattr(db_base, "SessionLocal", None) is not None
    if not session_init:
        return {"db": "disabled", "env_present": env_present, "engine_initialized": engine_init, "session_initialized": session_init}
    try:
        # Import models lazily to avoid circular imports at module import time
        from app.db.models import Document, ChunkModel  # type: ignore
        counts = {}
        exists = None
        chunks_for_doc = None
        with db_session() as s:
            counts = {
                "documents": s.query(Document).count(),
                "chunks": s.query(ChunkModel).count(),
            }
            if doc_id:
                exists = s.query(Document).filter(Document.id == doc_id).first() is not None
                chunks_for_doc = s.query(ChunkModel).filter(ChunkModel.doc_id == doc_id).count()
        resp = {"db": "ok", "counts": counts, "env_present": env_present, "engine_initialized": engine_init, "session_initialized": session_init}
        if doc_id is not None:
            resp.update({
                "doc_id": doc_id,
                "doc_exists": exists,
                "chunks_for_doc": chunks_for_doc,
            })
        return resp
    except Exception as e:
        return {"db": "error", "error": str(e)}

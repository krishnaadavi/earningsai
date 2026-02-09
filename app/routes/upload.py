from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.types import UploadResponse, Chunk
from app.services.pdf_parser import extract_pages_from_pdf
from app.services.chunker import chunk_pages
from app.services.embedder import embed_texts
from app.services.retriever import build_index
from app.memory import store
from app.db.persistence import is_db_enabled, save_document
import numpy as np
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/x-pdf", "binary/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    data = await file.read()
    try:
        pages = extract_pages_from_pdf(data)
        chunks = chunk_pages(pages)
        texts = [c.text for c in chunks]
        embs = embed_texts(texts)  # (N, D)
        doc_id = str(uuid.uuid4())
        # store
        store.documents[doc_id] = {
            "chunks": chunks,
            "embeddings": embs,
        }
        # Persist to DB if configured
        try:
            if is_db_enabled():
                save_document(
                    doc_id,
                    file.filename,
                    chunks,
                    embs,
                    ingest_status="uploaded",
                )
        except Exception as pe:
            logger.warning("upload: db persist error for doc_id=%s: %s", doc_id, pe)
        logger.info("upload: stored doc_id=%s chunks=%d embs_shape=%s total_docs=%d",
                    doc_id, len(chunks), getattr(embs, 'shape', None), len(store.documents))
        return UploadResponse(doc_id=doc_id, chunk_count=len(chunks))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {e}")

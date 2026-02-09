from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import uuid
import logging
from typing import List, Optional, Dict
import os
import re
import time
from datetime import datetime
from sqlalchemy import func
import hashlib

from app.models.types import UploadResponse, Chunk
from app.services.pdf_parser import extract_pages_from_pdf
from app.services.html_parser import extract_pages_from_html
from app.services.chunker import chunk_pages
from app.services.embedder import embed_texts
from app.memory import store
from app.db.persistence import is_db_enabled, save_document
from app.db.base import db_session
from app.db.models import Document, ChunkModel
from app.services.highlights import create_highlight_and_event
from app.services.metrics import now, elapsed_ms, record_http, record_fallback

router = APIRouter()
logger = logging.getLogger(__name__)


class WeeklyItem(BaseModel):
    ticker: str
    company: str
    date: str  # ISO date or human readable e.g., "2025-09-11" or "Thu"


@router.get("/weekly", response_model=List[WeeklyItem])
async def weekly() -> List[WeeklyItem]:
    # Static curated sample for now; replace with a real calendar provider later.
    data: List[WeeklyItem] = [
        WeeklyItem(ticker="AAPL", company="Apple Inc.", date="Thu"),
        WeeklyItem(ticker="MSFT", company="Microsoft Corp.", date="Wed"),
        WeeklyItem(ticker="NVDA", company="NVIDIA Corp.", date="Tue"),
        WeeklyItem(ticker="AMZN", company="Amazon.com, Inc.", date="Thu"),
        WeeklyItem(ticker="TSLA", company="Tesla, Inc.", date="Mon"),
    ]
    return data


class IngestUrlRequest(BaseModel):
    url: str
    ticker: Optional[str] = None
    company: Optional[str] = None
    filename: Optional[str] = None


@router.post("/ingest_url", response_model=UploadResponse)
async def ingest_url(req: IngestUrlRequest) -> UploadResponse:
    if not req.url or not req.url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Provide a valid http(s) URL to a PDF")

    # Download PDF/HTML
    try:
        # Use SEC headers if downloading from sec.gov
        headers = _sec_download_headers() if _is_sec_url(req.url) else None
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            t0 = now()
            resp = await client.get(req.url)
            try:
                provider = "edgar" if _is_sec_url(req.url) else "generic"
                record_http(provider, "/download", resp.status_code, elapsed_ms(t0))
            except Exception:
                pass
            if resp.status_code >= 400:
                raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {resp.status_code}")
            ctype = resp.headers.get("content-type", "").lower()
            is_pdf = ("application/pdf" in ctype or "application/x-pdf" in ctype) or req.url.lower().endswith(".pdf")
            is_html = ("text/html" in ctype) or req.url.lower().endswith((".htm", ".html"))
            if not (is_pdf or is_html):
                raise HTTPException(status_code=400, detail=f"URL is not PDF/HTML (content-type={ctype})")
            data = resp.content
            if not data or len(data) < 1000:
                raise HTTPException(status_code=400, detail="Downloaded file seems too small to be a valid PDF")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching URL: {e}")

    # Parse + chunk + embed
    try:
        # Choose parser by content type or URL suffix
        is_html = ("text/html" in ctype) or (req.url.lower().endswith((".htm", ".html")))
        pages = extract_pages_from_html(data) if is_html else extract_pages_from_pdf(data)
        chunks = chunk_pages(pages)
        texts = [c.text for c in chunks]
        embs = embed_texts(texts)
        doc_id = str(uuid.uuid4())
        # provenance
        doc_hash = hashlib.sha256(data).hexdigest()
        page_count = len(pages)
        file_size_bytes = len(data)
        # store in memory
        store.documents[doc_id] = {
            "chunks": chunks,
            "embeddings": embs,
            "meta": {
                "ticker": req.ticker,
                "company": req.company,
                "source_url": req.url,
                "filename": req.filename,
                "is_sample": False,
                "doc_hash": doc_hash,
                "page_count": page_count,
                "file_size_bytes": file_size_bytes,
                "pdf_vs_html": ("html" if is_html else "pdf"),
            },
        }
        # Persist if DB configured
        try:
            if is_db_enabled():
                save_document(
                    doc_id,
                    req.filename or req.ticker or None,
                    chunks,
                    embs,
                    ticker=req.ticker,
                    company=req.company,
                    source_url=req.url,
                    ingest_status="ingested",
                )
        except Exception as pe:
            logger.warning("ingest_url: db persist error for doc_id=%s: %s", doc_id, pe)
        logger.info(
            "ingest_url: doc_id=%s chunks=%d embs_shape=%s ticker=%s url=%s",
            doc_id,
            len(chunks),
            getattr(embs, "shape", None),
            req.ticker,
            req.url,
        )
        return UploadResponse(doc_id=doc_id, chunk_count=len(chunks))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {e}")


class IngestSymbolRequest(BaseModel):
    ticker: str
    prefer: Optional[str] = None  # e.g., 'pr', 'transcript', '10q'


async def _try_fmp_pdf_url(ticker: str, prefer: Optional[str]) -> Optional[str]:
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return None
    t = ticker.upper()
    # 1) Try press releases
    try:
        url = f"https://financialmodelingprep.com/api/v3/press-releases/{t}?apikey={api_key}&limit=20"
        async with httpx.AsyncClient(timeout=20.0) as client:
            t0 = now()
            r = await client.get(url)
            try:
                record_http("fmp", "/press-releases", r.status_code, elapsed_ms(t0))
            except Exception:
                pass
            if r.status_code < 400:
                items = r.json() or []
                fallback_html: Optional[str] = None
                # Look for any link containing .pdf; else keep first HTML link as fallback
                for it in items:
                    link = (it or {}).get("link") or (it or {}).get("url") or ""
                    if isinstance(link, str) and link:
                        if link.lower().endswith('.pdf') or 'pdf' in link.lower():
                            return link
                        if fallback_html is None and link.lower().startswith(('http://', 'https://')):
                            # Prefer links with press/earnings keywords
                            if re.search(r"press|earnings|results|release", link, flags=re.I):
                                fallback_html = link
                            elif fallback_html is None:
                                fallback_html = link
                    content = (it or {}).get("content") or ""
                    if isinstance(content, str):
                        m = re.search(r"https?://[^\s\"]+\.pdf", content, flags=re.I)
                        if m:
                            return m.group(0)
                if fallback_html:
                    return fallback_html
    except Exception:
        pass
    # 2) Could try sec_filings endpoint but many are HTML; skipping for MVP
    return None


def _curated_fallback_pdf(ticker: str) -> Optional[str]:
    t = ticker.upper()
    curated: Dict[str, str] = {
        # Replace these with reliable public PDF links you prefer
        "NVDA": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "AAPL": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "MSFT": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "AMZN": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "TSLA": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
    }
    return curated.get(t)


_cik_cache: Dict[str, Dict[str, str]] = {}
_tickers_cache_fetched = False
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_CACHE_TTL_SECONDS = int(os.getenv("SEC_CACHE_TTL_SECONDS", "21600") or "21600")  # 6h default
SEC_HTML_CACHE_TTL_SECONDS = int(os.getenv("SEC_HTML_CACHE_TTL_SECONDS", "3600") or "3600")  # 1h default
SEC_MAX_FILINGS_SCAN = int(os.getenv("SEC_MAX_FILINGS_SCAN", "15") or "15")  # limit scanned filings

# simple in-process cache { key: (ts, ttl, data) }
_sec_resp_cache: Dict[str, tuple] = {}


def _cache_get(key: str):
    e = _sec_resp_cache.get(key)
    if not e:
        return None
    ts, ttl, data = e
    if time.time() - ts > ttl:
        try:
            _sec_resp_cache.pop(key, None)
        except Exception:
            pass
        return None
    return data


def _cache_set(key: str, ttl: int, data):
    _sec_resp_cache[key] = (time.time(), ttl, data)


def _sec_headers() -> Dict[str, str]:
    ua = os.getenv("SEC_USER_AGENT") or os.getenv("USER_AGENT") or "EarningsAI/1.0 (contact: devnull@example.com)"
    return {
        "User-Agent": ua,
        "Accept": "application/json, text/html;q=0.8",
    }


def _sec_download_headers() -> Dict[str, str]:
    ua = os.getenv("SEC_USER_AGENT") or os.getenv("USER_AGENT") or "EarningsAI/1.0 (contact: devnull@example.com)"
    return {
        "User-Agent": ua,
        "Accept": "application/pdf, application/octet-stream;q=0.9, */*;q=0.8",
    }


def _is_sec_url(url: str) -> bool:
    try:
        return "sec.gov" in (url or "").lower()
    except Exception:
        return False

async def _load_ticker_map() -> None:
    global _tickers_cache_fetched
    if _tickers_cache_fetched:
        return
    try:
        cached = _cache_get(SEC_TICKERS_URL)
        data = None
        if cached is None:
            async with httpx.AsyncClient(timeout=30.0, headers=_sec_headers()) as client:
                t0 = now()
                r = await client.get(SEC_TICKERS_URL)
                try:
                    record_http("edgar", "/files/company_tickers.json", r.status_code, elapsed_ms(t0))
                except Exception:
                    pass
                if r.status_code < 400:
                    data = r.json()
                    _cache_set(SEC_TICKERS_URL, SEC_CACHE_TTL_SECONDS, data)
        else:
            data = cached
        if data is not None:
                # Format: { "0": {"ticker":"A","cik_str":123, "title":"..."}, ... }
                for _, item in (data or {}).items():
                    tic = (item or {}).get("ticker")
                    if not tic:
                        continue
                    _cik_cache[tic.upper()] = {
                        "cik": str((item or {}).get("cik_str") or "").strip(),
                        "company": (item or {}).get("title") or None,
                    }
                _tickers_cache_fetched = True
    except Exception:
        # silent fail; we'll try on-demand resolution later if needed
        pass


async def _resolve_cik_and_company(ticker: str) -> Optional[Dict[str, str]]:
    await _load_ticker_map()
    info = _cik_cache.get(ticker.upper())
    return info


async def _edgar_pdf_url_for_ticker(ticker: str, prefer_forms: Optional[List[str]] = None) -> Optional[Dict[str, str]]:
    """Return a dict with {url, form_type, company} if a PDF is found in recent filings."""
    info = await _resolve_cik_and_company(ticker)
    if not info or not info.get("cik"):
        return None
    cik_str = info["cik"]
    try:
        cik10 = cik_str.zfill(10)
        sub_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
        # Reuse a single client and keep timeouts conservative
        async with httpx.AsyncClient(timeout=12.0, headers=_sec_headers(), follow_redirects=True) as client:
            j = _cache_get(sub_url)
            if j is None:
                t0 = now()
                r = await client.get(sub_url)
                try:
                    record_http("edgar", "/submissions", r.status_code, elapsed_ms(t0))
                except Exception:
                    pass
                if r.status_code >= 400:
                    return None
                j = r.json() or {}
                _cache_set(sub_url, SEC_CACHE_TTL_SECONDS, j)
            # Compute recent lists regardless of cache hit
            recent = (j.get("filings") or {}).get("recent") or {}
            forms = recent.get("form") or []
            accno = recent.get("accessionNumber") or []
            primary = recent.get("primaryDocument") or []
            filed = recent.get("filingDate") or []

        order = prefer_forms or ["8-K", "10-Q", "10-K"]
        # Build candidate indexes by form preference then recency
        indexes = list(range(len(forms)))
        # sort by order priority then by filing date desc
        def form_priority(f: str) -> int:
            try:
                return order.index((f or "").upper())
            except ValueError:
                return len(order) + 1

        try:
            # filed dates are strings, sort by (priority, filed desc)
            indexes.sort(key=lambda i: (form_priority((forms[i] or "").upper()), (filed[i] or "")), reverse=True)
        except Exception:
            # fallback: maintain original order
            pass

        cik_nozero = str(int(cik_str))  # remove leading zeros for path
        # Limit number of filings scanned to avoid long request bursts
        indexes = indexes[:SEC_MAX_FILINGS_SCAN]
        for i in indexes:
            f = (forms[i] or "").upper()
            an = (accno[i] or "").strip()
            pd = (primary[i] or "").strip()
            if not an:
                continue
            acc_nodash = an.replace("-", "")
            base_dir = f"https://www.sec.gov/Archives/edgar/data/{cik_nozero}/{acc_nodash}/"
            # If primary doc is a PDF, use it
            if pd.lower().endswith('.pdf'):
                referer = f"{base_dir}{an}-index.html"
                return {"url": base_dir + pd, "form_type": f, "company": info.get("company"), "referer": referer}
            # Otherwise, scan filing detail page(s) for PDF/HTML exhibits with caching
            details = [f"{base_dir}{an}-index.html", f"{base_dir}{an}-index.htm", base_dir]
            best_pdf = None
            best_referer = None
            best_html = None
            best_html_referer = None
            best_score = -1
            for detail in details:
                try:
                    html = _cache_get(detail)
                    if html is None:
                        t0d = now()
                        rr = await client.get(detail)
                        try:
                            record_http("edgar", "/archives-detail", rr.status_code, elapsed_ms(t0d))
                        except Exception:
                            pass
                        if rr.status_code >= 400:
                            continue
                        html = rr.text or ""
                        _cache_set(detail, SEC_HTML_CACHE_TTL_SECONDS, html)
                    # find links ending .pdf
                    for href in re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, flags=re.I):
                        href_clean = href
                        if href_clean.startswith("http"):
                            pdf_url = href_clean
                        else:
                            if href_clean.startswith("/"):
                                pdf_url = "https://www.sec.gov" + href_clean
                            else:
                                pdf_url = base_dir + href_clean
                        name = href_clean.lower()
                        score = 0
                        if 'ex99' in name or 'ex-99' in name:
                            score += 3
                        if 'press' in name or 'earnings' in name or 'release' in name or 'results' in name:
                            score += 2
                        if name.endswith('.pdf'):
                            score += 1
                        if score > best_score:
                            best_score = score
                            best_pdf = pdf_url
                            best_referer = detail
                    # find links ending .htm/.html with press/earnings keywords
                    for href in re.findall(r'href=["\']([^"\']+\.(?:htm|html))["\']', html, flags=re.I):
                        href_clean = href
                        if href_clean.startswith("http"):
                            html_url = href_clean
                        else:
                            if href_clean.startswith("/"):
                                html_url = "https://www.sec.gov" + href_clean
                            else:
                                html_url = base_dir + href_clean
                        name = href_clean.lower()
                        score = 0
                        if 'ex99' in name or 'ex-99' in name:
                            score += 3
                        if 'press' in name or 'earnings' in name or 'release' in name or 'results' in name or 'pr' in name:
                            score += 2
                        if name.endswith(('.htm', '.html')):
                            score += 1
                        if score > best_score and score >= 3:  # require minimal strength
                            best_score = score
                            best_html = html_url
                            best_html_referer = detail
                except Exception:
                    continue
            if best_pdf:
                return {"url": best_pdf, "form_type": f, "company": info.get("company"), "referer": best_referer}
            if best_html:
                return {"url": best_html, "form_type": f, "company": info.get("company"), "referer": best_html_referer}
            # Fallback: use primary document if it's HTML
            if pd.lower().endswith((".htm", ".html")):
                referer = f"{base_dir}{an}-index.html"
                return {"url": base_dir + pd, "form_type": f, "company": info.get("company"), "referer": referer}
    except Exception:
        return None
    return None


@router.post("/ingest_symbol", response_model=UploadResponse)
async def ingest_symbol(req: IngestSymbolRequest) -> UploadResponse:
    if not req.ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    ticker = req.ticker.upper()

    # Try provider(s)
    pdf_url: Optional[str] = None
    form_type: Optional[str] = None
    company_name: Optional[str] = None
    # Provider order: if prefer=edgar, try EDGAR first, else try FMP first
    referer_url: Optional[str] = None
    last_provider: Optional[str] = None
    used_source: str = "primary"
    if (req.prefer or '').lower() == 'edgar':
        ed = await _edgar_pdf_url_for_ticker(ticker)
        if ed and ed.get('url'):
            pdf_url = ed['url']
            form_type = ed.get('form_type')
            company_name = ed.get('company')
            referer_url = ed.get('referer')
            last_provider = 'edgar'
        if not pdf_url:
            alt = await _try_fmp_pdf_url(ticker, req.prefer)
            if alt:
                pdf_url = alt
                last_provider = 'fmp'
    else:
        alt = await _try_fmp_pdf_url(ticker, req.prefer)
        if alt:
            pdf_url = alt
            last_provider = 'fmp'
        if not pdf_url:
            ed = await _edgar_pdf_url_for_ticker(ticker)
            if ed and ed.get('url'):
                pdf_url = ed['url']
                form_type = ed.get('form_type')
                company_name = ed.get('company')
                referer_url = ed.get('referer')
                last_provider = 'edgar'
    if not pdf_url:
        pdf_url = _curated_fallback_pdf(ticker)
    if not pdf_url:
        raise HTTPException(status_code=404, detail=f"No PDF source found for {ticker}")

    # Reuse ingest_url pipeline with robust fallback; allow HTML as well.
    def _headers_for(url: str, referer: Optional[str]):
        if _is_sec_url(url):
            h = _sec_download_headers()
            if referer:
                h["Referer"] = referer
            return h
        return None

    async def _download_any(url: str, referer: Optional[str]) -> Optional[tuple[bytes, str]]:
        try:
            headers = _headers_for(url, referer)
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
                t0 = now()
                r = await client.get(url)
                try:
                    prov = "edgar" if _is_sec_url(url) else ("fmp" if "financialmodelingprep.com" in (url or "") else "generic")
                    record_http(prov, "/download", r.status_code, elapsed_ms(t0))
                except Exception:
                    pass
                if r.status_code >= 400:
                    return None
                ctype = (r.headers.get("content-type", "") or "").lower()
                data = r.content
                if not data or len(data) < 1000:
                    return None
                # accept any content-type; parser will decide
                return data, ctype
        except Exception:
            return None

    first = await _download_any(pdf_url, referer_url)
    data: Optional[bytes] = first[0] if first else None
    ctype: Optional[str] = first[1] if first else None
    if data is None:
        # Try the alternate provider, then curated
        if last_provider == 'edgar':
            alt = await _try_fmp_pdf_url(ticker, req.prefer)
            if alt:
                try:
                    record_fallback("to_fmp")
                except Exception:
                    pass
                got = await _download_any(alt, None)
                if got is not None:
                    data, ctype = got
                    pdf_url = alt
        elif last_provider == 'fmp':
            ed = await _edgar_pdf_url_for_ticker(ticker)
            if ed and ed.get('url'):
                alt = ed['url']
                try:
                    record_fallback("to_edgar")
                except Exception:
                    pass
                got = await _download_any(alt, ed.get('referer'))
                if got is not None:
                    data, ctype = got
                    pdf_url = alt
                    form_type = ed.get('form_type')
                    company_name = ed.get('company')
        if data is None:
            alt2 = _curated_fallback_pdf(ticker)
            if alt2:
                try:
                    record_fallback("to_curated")
                except Exception:
                    pass
                got = await _download_any(alt2, None)
                if got is not None:
                    data, ctype = got
                    pdf_url = alt2
            used_source = "curated"
        if data is None:
            raise HTTPException(status_code=400, detail="Failed to fetch URL from providers (EDGAR/FMP) and fallback")

    try:
        # Choose parser by content-type or URL suffix
        is_html = bool((ctype or "").startswith("text/html") or pdf_url.lower().endswith((".htm", ".html")))
        pages = extract_pages_from_html(data) if is_html else extract_pages_from_pdf(data)
        chunks = chunk_pages(pages)
        texts = [c.text for c in chunks]
        embs = embed_texts(texts)
        doc_id = str(uuid.uuid4())
        # provenance
        doc_hash = hashlib.sha256(data).hexdigest()
        page_count = len(pages)
        file_size_bytes = len(data)
        store.documents[doc_id] = {
            "chunks": chunks,
            "embeddings": embs,
            "meta": {
                "ticker": ticker,
                "company": company_name,
                "source_url": pdf_url,
                "filename": ticker,
                "is_sample": (used_source == "curated"),
                "doc_hash": doc_hash,
                "page_count": page_count,
                "file_size_bytes": file_size_bytes,
                "pdf_vs_html": ("html" if pdf_url.lower().endswith((".htm", ".html")) else "pdf"),
            },
        }
        try:
            if is_db_enabled():
                save_document(
                    doc_id,
                    ticker,
                    chunks,
                    embs,
                    ticker=ticker,
                    company=company_name,
                    form_type=form_type,
                    source_url=pdf_url,
                    ingest_status=("curated_fallback" if used_source == "curated" else "ingested_symbol"),
                )
                # Create highlight + ensure event
                try:
                    create_highlight_and_event(ticker=ticker, company=company_name, doc_id=doc_id, chunks=chunks)
                except Exception:
                    pass
        except Exception as pe:
            logger.warning("ingest_symbol: db persist error for doc_id=%s: %s", doc_id, pe)
        logger.info("ingest_symbol: ticker=%s url=%s doc_id=%s chunks=%d", ticker, pdf_url, doc_id, len(chunks))
        return UploadResponse(doc_id=doc_id, chunk_count=len(chunks))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {e}")


# P0 convenience: list in-memory docs (non-persistent)
class DocSummary(BaseModel):
    doc_id: str
    chunk_count: int
    has_meta: bool = False
    # Optional metadata when DB-backed
    ticker: Optional[str] = None
    company: Optional[str] = None
    filename: Optional[str] = None
    created_at: Optional[str] = None


@router.get("/docs", response_model=List[DocSummary])
async def list_docs(limit: int = 20, offset: int = 0, ticker: Optional[str] = None, form_type: Optional[str] = None) -> List[DocSummary]:
    if is_db_enabled():
        with db_session() as s:
            q = s.query(Document)
            if ticker:
                q = q.filter(Document.ticker == ticker)
            if form_type:
                q = q.filter(Document.form_type == form_type)
            q = q.order_by(Document.created_at.desc(), Document.id.desc()).offset(offset).limit(limit)
            docs: List[Document] = q.all()
            ids = [d.id for d in docs]
            counts: Dict[str, int] = {}
            if ids:
                for did, cnt in s.query(ChunkModel.doc_id, func.count(ChunkModel.id)).filter(ChunkModel.doc_id.in_(ids)).group_by(ChunkModel.doc_id).all():
                    counts[str(did)] = int(cnt)
            out: List[DocSummary] = []
            for d in docs:
                out.append(DocSummary(
                    doc_id=d.id,
                    chunk_count=counts.get(d.id, 0),
                    has_meta=any([d.ticker, d.company, d.source_url]),
                    ticker=d.ticker,
                    company=d.company,
                    filename=d.filename,
                    created_at=(d.created_at.isoformat() if isinstance(d.created_at, datetime) else None),
                ))
            return out


@router.delete("/docs/{doc_id}")
async def delete_doc(doc_id: str):
    deleted_chunks = 0
    deleted_doc = False
    if is_db_enabled():
        with db_session() as s:
            try:
                deleted_chunks = s.query(ChunkModel).filter(ChunkModel.doc_id == doc_id).delete()
                d = s.get(Document, doc_id)
                if d is not None:
                    s.delete(d)
                    deleted_doc = True
            except Exception as e:
                logger.warning("delete_doc: db error for doc_id=%s: %s", doc_id, e)
    deleted_mem = store.documents.pop(doc_id, None) is not None
    return {
        "doc_id": doc_id,
        "deleted_db": deleted_doc,
        "deleted_chunks": int(deleted_chunks),
        "deleted_memory": bool(deleted_mem),
    }


@router.get("/docs/{doc_id}")
async def get_doc(doc_id: str):
    if is_db_enabled():
        with db_session() as s:
            d = s.get(Document, doc_id)
            if not d:
                raise HTTPException(status_code=404, detail="Unknown doc_id")
            cnt = s.query(func.count(ChunkModel.id)).filter(ChunkModel.doc_id == doc_id).scalar() or 0
            return {
                "doc_id": d.id,
                "chunk_count": int(cnt),
                "meta": {
                    "ticker": d.ticker,
                    "company": d.company,
                    "form_type": d.form_type,
                    "fiscal_year": d.fiscal_year,
                    "fiscal_period": d.fiscal_period,
                    "source_url": d.source_url,
                    "ingest_status": d.ingest_status,
                    "filename": d.filename,
                    "created_at": d.created_at.isoformat() if isinstance(d.created_at, datetime) else None,
                },
            }
    # Fallback to in-memory
    d = store.documents.get(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Unknown doc_id")
    return {
        "doc_id": doc_id,
        "chunk_count": len(d.get("chunks") or []),
        "meta": d.get("meta") or {},
    }


@router.get("/docs/list/by_ticker", response_model=List[DocSummary])
async def docs_by_ticker(ticker: str, limit: int = 5) -> List[DocSummary]:
    if is_db_enabled():
        with db_session() as s:
            q = s.query(Document).filter(Document.ticker == ticker).order_by(Document.created_at.desc(), Document.id.desc()).limit(limit)
            docs: List[Document] = q.all()
            ids = [d.id for d in docs]
            counts: Dict[str, int] = {}
            if ids:
                for did, cnt in s.query(ChunkModel.doc_id, func.count(ChunkModel.id)).filter(ChunkModel.doc_id.in_(ids)).group_by(ChunkModel.doc_id).all():
                    counts[str(did)] = int(cnt)
            return [DocSummary(
                doc_id=d.id,
                chunk_count=counts.get(d.id, 0),
                has_meta=any([d.ticker, d.company, d.source_url]),
                ticker=d.ticker,
                company=d.company,
                filename=d.filename,
                created_at=(d.created_at.isoformat() if isinstance(d.created_at, datetime) else None),
            ) for d in docs]
    # Fallback to in-memory: filter by meta.ticker
    out: List[DocSummary] = []
    for did, d in list(store.documents.items())[:limit]:
        meta = d.get("meta") or {}
        if (meta.get("ticker") or "").upper() == ticker.upper():
            chunks = d.get("chunks") or []
            out.append(DocSummary(doc_id=did, chunk_count=len(chunks), has_meta=True, ticker=meta.get("ticker"), company=meta.get("company"), filename=meta.get("filename")))
    return out

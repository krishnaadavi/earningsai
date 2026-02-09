from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class Chunk(BaseModel):
    id: str
    text: str
    section: Optional[str] = None
    page_start: int
    page_end: int


class Citation(BaseModel):
    section: Optional[str] = None
    page: int
    snippet: str


class UploadResponse(BaseModel):
    doc_id: str
    chunk_count: int


class QueryRequest(BaseModel):
    doc_id: str
    question: str


class AnswerBullet(BaseModel):
    text: str
    citations: List[Citation]


class QueryResponse(BaseModel):
    bullets: List[AnswerBullet]
    chart: Dict[str, Any]


# P1: Metrics & Series & Guidance & Buybacks
class DocRequest(BaseModel):
    doc_id: str


class SeriesRequest(BaseModel):
    doc_id: str
    metrics: List[str]


class MetricsResponse(BaseModel):
    metrics: Dict[str, Any]


class SeriesResponse(BaseModel):
    series: Dict[str, Any]


class GuidanceResponse(BaseModel):
    guidance: List[Dict[str, Any]]


class BuybacksResponse(BaseModel):
    buybacks: List[Dict[str, Any]]

from pydantic import BaseModel, ValidationError
from typing import List

class Citation(BaseModel):
    id: str
    context: str

class SearchResult(BaseModel):
    title: str
    link: str
    summary: str
    citations: List[Citation]

class SearchResponse(BaseModel):
    results: List[SearchResult]
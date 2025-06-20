from pydantic import BaseModel, Field
from typing import List

class Citation(BaseModel):
    id: str = Field(description="Unique identifier for the citation")
    context: str = Field(description="The citation used to generate the search result")

class SearchResult(BaseModel):
    title: str = Field(description="The title of the search result")
    link: str = Field(description="The link to the source of search result")
    summary: str = Field(description="A brief summary of the search result and relvance to prompt")
    citations: List[Citation] = Field(description="A list of citations used to generate the search result")

class SearchResponse(BaseModel):
    results: List[SearchResult] = Field(description="A list of search results")
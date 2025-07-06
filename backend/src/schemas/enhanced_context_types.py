"""
Enhanced Context Processing Types
Replaces Dict[str, Any] with proper structured types for better type safety.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Union

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from .langgraph_types import LangChainDocument

# === Structured Data Models ===


@dataclass
class ExtractedInformation:
    """Structured information extracted from documents."""

    title: Optional[str] = None
    source_url: Optional[str] = None
    page_content_snippet: str = ""
    entities: List[str] = field(default_factory=list)
    key_facts: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None
    extraction_method: str = "basic"
    metadata: Dict[str, Union[str, int, float, bool]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Union[str, int, float, bool, List[str], None]]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "source_url": self.source_url,
            "page_content_snippet": self.page_content_snippet,
            "entities": self.entities,
            "key_facts": self.key_facts,
            "topics": self.topics,
            "confidence_score": self.confidence_score,
            "extraction_method": self.extraction_method,
            "metadata": self.metadata,
        }


@dataclass
class DocumentCitation:
    """Structured citation information for documents."""

    title: str
    source_url: str
    page_number: Optional[str] = None
    document_id: str = ""
    relevance_score: Optional[float] = None
    citation_type: str = "document"  # document, webpage, pdf, etc.
    access_date: Optional[datetime] = None
    authors: List[str] = field(default_factory=list)
    publication_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Union[str, int, float, bool, List[str], None]]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "source_url": self.source_url,
            "page_number": self.page_number,
            "document_id": self.document_id,
            "relevance_score": self.relevance_score,
            "citation_type": self.citation_type,
            "access_date": self.access_date.isoformat() if self.access_date else None,
            "authors": self.authors,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
        }


@dataclass
class SessionMemoryEntry:
    """Structured session memory entry."""

    memory_id: str
    content: str
    memory_type: str  # "fact", "interaction", "preference", etc.
    relevance_score: float
    timestamp: datetime
    user_id: str
    session_id: str
    metadata: Dict[str, Union[str, int, float, bool]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Union[str, int, float, bool, None]]:
        """Convert to dictionary for serialization."""
        return {"memory_id": self.memory_id, "content": self.content, "memory_type": self.memory_type, "relevance_score": self.relevance_score, "timestamp": self.timestamp.isoformat(), "user_id": self.user_id, "session_id": self.session_id, "metadata": self.metadata}


# === Enhanced TypedDict Outputs ===


class EnhancedInformationExtractionOutput(TypedDict):
    """Enhanced information extraction output with proper typing."""

    extracted_info: Optional[List[ExtractedInformation]]
    documents: List[Document]
    processing_time_ms: Optional[float]
    extraction_method: str
    error: Optional[str]


class EnhancedContextSummarizationOutput(TypedDict):
    """Enhanced context summarization output with proper typing."""

    summarized_content: List[LangChainDocument]
    documents: List[Document]
    original_length: int
    summarized_length: int
    compression_ratio: float
    summarization_method: str
    processing_time_ms: Optional[float]
    error: Optional[str]


class EnhancedCitationAttributionOutput(TypedDict):
    """Enhanced citation attribution output with proper typing."""

    citations: List[DocumentCitation]
    documents: List[Document]
    citation_count: int
    citation_method: str
    processing_time_ms: Optional[float]
    error: Optional[str]


class EnhancedContextProcessorOutput(TypedDict):
    """Enhanced context processor output with comprehensive typing."""

    documents: List[Document]
    extracted_info: Optional[List[ExtractedInformation]]
    summarized_content: Optional[List[LangChainDocument]]
    citations: Optional[List[DocumentCitation]]
    session_memory: Optional[List[SessionMemoryEntry]]
    processing_metadata: Dict[str, Union[str, int, float, bool]]
    total_processing_time_ms: Optional[float]
    error: Optional[str]


# === Pydantic Models for API Responses ===


class ExtractedInformationModel(BaseModel):
    """Pydantic model for extracted information."""

    title: Optional[str] = None
    source_url: Optional[str] = None
    page_content_snippet: str = Field(default="", max_length=500)
    entities: List[str] = Field(default_factory=list)
    key_facts: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    extraction_method: str = Field(default="basic")
    metadata: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)


class DocumentCitationModel(BaseModel):
    """Pydantic model for document citations."""

    title: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    page_number: Optional[str] = None
    document_id: str = Field(default="")
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    citation_type: str = Field(default="document")
    access_date: Optional[datetime] = None
    authors: List[str] = Field(default_factory=list)
    publication_date: Optional[datetime] = None


class SessionMemoryEntryModel(BaseModel):
    """Pydantic model for session memory entries."""

    memory_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    memory_type: str = Field(default="interaction")
    relevance_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    metadata: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)


# === Factory Functions ===


def create_extracted_info(title: Optional[str] = None, source_url: Optional[str] = None, content_snippet: str = "", **kwargs) -> ExtractedInformation:
    """Factory function for creating ExtractedInformation instances."""
    return ExtractedInformation(title=title, source_url=source_url, page_content_snippet=content_snippet, **kwargs)


def create_citation(title: str, source_url: str, **kwargs) -> DocumentCitation:
    """Factory function for creating DocumentCitation instances."""
    return DocumentCitation(title=title, source_url=source_url, **kwargs)


def create_memory_entry(memory_id: str, content: str, user_id: str, session_id: str, **kwargs) -> SessionMemoryEntry:
    """Factory function for creating SessionMemoryEntry instances."""
    return SessionMemoryEntry(memory_id=memory_id, content=content, user_id=user_id, session_id=session_id, timestamp=datetime.now(), **kwargs)


# === Type Guards ===


def is_extracted_info(obj: any) -> bool:
    """Type guard for ExtractedInformation."""
    return isinstance(obj, ExtractedInformation)


def is_citation(obj: any) -> bool:
    """Type guard for DocumentCitation."""
    return isinstance(obj, DocumentCitation)


def is_memory_entry(obj: any) -> bool:
    """Type guard for SessionMemoryEntry."""
    return isinstance(obj, SessionMemoryEntry)


# === Conversion Utilities ===


def dict_to_extracted_info(data: Dict[str, any]) -> ExtractedInformation:
    """Convert dictionary to ExtractedInformation."""
    return ExtractedInformation(
        title=data.get("title"),
        source_url=data.get("source_url"),
        page_content_snippet=data.get("page_content_snippet", ""),
        entities=data.get("entities", []),
        key_facts=data.get("key_facts", []),
        topics=data.get("topics", []),
        confidence_score=data.get("confidence_score"),
        extraction_method=data.get("extraction_method", "basic"),
        metadata=data.get("metadata", {}),
    )


def dict_to_citation(data: Dict[str, any]) -> DocumentCitation:
    """Convert dictionary to DocumentCitation."""
    return DocumentCitation(
        title=data["title"],
        source_url=data["source_url"],
        page_number=data.get("page_number"),
        document_id=data.get("document_id", ""),
        relevance_score=data.get("relevance_score"),
        citation_type=data.get("citation_type", "document"),
        access_date=datetime.fromisoformat(data["access_date"]) if data.get("access_date") else None,
        authors=data.get("authors", []),
        publication_date=datetime.fromisoformat(data["publication_date"]) if data.get("publication_date") else None,
    )

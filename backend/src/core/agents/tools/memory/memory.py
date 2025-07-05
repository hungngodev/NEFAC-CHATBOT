"""
Enhanced Memory System for Multi-Agent RAG
Provides semantic memory storage, user isolation, and intelligent retrieval using Qdrant.
"""

import asyncio
import logging
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import Qdrant
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# === Memory Models ===


@dataclass
class MemoryEntry:
    """Structured memory entry with metadata."""

    id: str
    user_id: str
    session_id: str
    query: str
    response: str
    timestamp: datetime
    metadata: Dict[str, Union[str, int, float, bool]]
    embedding: Optional[List[float]] = None
    relevance_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Union[str, int, float, bool, List[float], None]]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, int, float, bool, List[float], None]]) -> "MemoryEntry":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    def to_document(self) -> Document:
        """Convert to LangChain Document for vector storage."""
        content = f"Query: {self.query}\nResponse: {self.response}"
        metadata = {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "query": self.query,
            **self.metadata,
        }
        return Document(page_content=content, metadata=metadata)


@dataclass
class MemorySearchResult:
    """Result from memory search."""

    entries: List[MemoryEntry]
    total_found: int
    search_time_ms: float
    query_embedding: Optional[List[float]] = None


# === Memory Storage Backend ===


class QdrantMemoryBackend:
    """Vector store backend using Qdrant."""

    def __init__(self, vector_store: VectorStore, embedding_model: Embeddings):
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.metadata_store: Dict[str, MemoryEntry] = {}  # In-memory metadata cache

    async def store(self, entry: MemoryEntry) -> bool:
        """Store in vector store."""
        try:
            # Convert to document
            doc = entry.to_document()

            # Store in vector store
            await asyncio.to_thread(self.vector_store.add_documents, [doc])

            # Cache metadata
            self.metadata_store[entry.id] = entry

            logger.info(f"Stored memory entry {entry.id} in vector store")
            return True

        except Exception as e:
            logger.error(f"Failed to store in vector store: {e}")
            return False

    async def retrieve(self, user_id: str, session_id: str = None, limit: int = 10) -> List[MemoryEntry]:
        """Retrieve from metadata cache (could be enhanced with vector store query)."""
        # Filter by user/session
        relevant_entries = []
        for entry in self.metadata_store.values():
            if entry.user_id == user_id:
                if session_id is None or entry.session_id == session_id:
                    relevant_entries.append(entry)

        # Sort by timestamp and limit
        relevant_entries.sort(key=lambda x: x.timestamp, reverse=True)
        return relevant_entries[:limit]

    async def search_semantic(self, query: str, user_id: str, session_id: str = None, limit: int = 5) -> MemorySearchResult:
        """Semantic search using vector store."""
        start_time = datetime.now()

        try:
            # Build filter for user/session
            filter_dict = {"user_id": user_id}
            if session_id:
                filter_dict["session_id"] = session_id

            # Search vector store
            docs = await asyncio.to_thread(self.vector_store.similarity_search, query, k=limit, filter=filter_dict)

            # Convert back to memory entries
            entries = []
            for doc in docs:
                entry_id = doc.metadata.get("id")
                if entry_id in self.metadata_store:
                    entry = self.metadata_store[entry_id]
                    # Add relevance score if available
                    if hasattr(doc, "score"):
                        entry.relevance_score = doc.score
                    entries.append(entry)

            search_time = (datetime.now() - start_time).total_seconds() * 1000

            return MemorySearchResult(entries=entries, total_found=len(entries), search_time_ms=search_time)

        except Exception as e:
            logger.error(f"Vector store search failed: {e}")
            return MemorySearchResult(entries=[], total_found=0, search_time_ms=0)

    async def cleanup_old_memories(self, retention_days: int = 30) -> int:
        """Cleanup old memories (implementation depends on vector store capabilities)."""
        # This would need to be implemented based on the specific vector store
        # For now, just clean the metadata cache
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        old_ids = [entry_id for entry_id, entry in self.metadata_store.items() if entry.timestamp < cutoff_date]

        for entry_id in old_ids:
            del self.metadata_store[entry_id]

        logger.info(f"Cleaned up {len(old_ids)} old memory entries from cache")
        return len(old_ids)


# === Enhanced Memory Manager ===


class EnhancedMemoryManager:
    """Enhanced memory manager with Qdrant storage backend and intelligent retrieval."""

    def __init__(self, storage_backend: QdrantMemoryBackend, embedding_model: Embeddings, max_memories_per_session: int = 100, relevance_threshold: float = 0.7):
        self.storage_backend = storage_backend
        self.embedding_model = embedding_model
        self.max_memories_per_session = max_memories_per_session
        self.relevance_threshold = relevance_threshold

        # Statistics
        self.stats = {"total_stored": 0, "total_retrieved": 0, "total_searches": 0, "cache_hits": 0}

    async def store_interaction(self, user_id: str, session_id: str, query: str, response: str, metadata: Dict[str, Union[str, int, float, bool]] = None) -> bool:
        """Store a user interaction in memory."""

        try:
            # Create memory entry
            entry = MemoryEntry(id=str(uuid.uuid4()), user_id=user_id, session_id=session_id, query=query, response=response, timestamp=datetime.now(), metadata=metadata or {})

            # Store in backend
            success = await self.storage_backend.store(entry)

            if success:
                self.stats["total_stored"] += 1

                # Cleanup if we have too many memories
                await self._cleanup_session_if_needed(user_id, session_id)

            return success

        except Exception as e:
            logger.error(f"Failed to store interaction: {e}")
            return False

    async def retrieve_relevant_memories(self, user_id: str, session_id: str, query: str, k: int = 5, use_semantic_search: bool = True) -> List[MemoryEntry]:
        """Retrieve relevant memories for a query."""

        try:
            self.stats["total_searches"] += 1

            if use_semantic_search:
                # Use semantic search
                result = await self.storage_backend.search_semantic(query, user_id, session_id, k)

                # Filter by relevance threshold
                relevant_entries = [entry for entry in result.entries if entry.relevance_score and entry.relevance_score >= self.relevance_threshold]

                logger.info(f"Semantic search found {len(relevant_entries)} relevant memories")
                return relevant_entries
            else:
                # Use recency-based retrieval
                entries = await self.storage_backend.retrieve(user_id, session_id, k)
                self.stats["total_retrieved"] += len(entries)
                return entries

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return []

    async def get_conversation_summary(self, user_id: str, session_id: str, max_interactions: int = 10) -> str:
        """Get a summary of recent conversation."""

        try:
            # Get recent memories
            memories = await self.storage_backend.retrieve(user_id, session_id, max_interactions)

            if not memories:
                return ""

            # Create summary
            summary_parts = []
            for memory in memories[-5:]:  # Last 5 interactions
                summary_parts.append(f"Q: {memory.query[:100]}...")
                summary_parts.append(f"A: {memory.response[:100]}...")

            return "\n".join(summary_parts)

        except Exception as e:
            logger.error(f"Failed to create conversation summary: {e}")
            return ""

    async def cleanup_old_memories(self, retention_days: int = 30) -> int:
        """Clean up old memories across all users."""
        try:
            return await self.storage_backend.cleanup_old_memories(retention_days)
        except Exception as e:
            logger.error(f"Failed to cleanup old memories: {e}")
            return 0

    async def _cleanup_session_if_needed(self, user_id: str, session_id: str):
        """Clean up session if it has too many memories."""
        try:
            memories = await self.storage_backend.retrieve(user_id, session_id, self.max_memories_per_session + 10)

            if len(memories) > self.max_memories_per_session:
                # This would require additional backend methods to delete specific entries
                # For now, just log the need for cleanup
                logger.warning(f"Session {session_id} has {len(memories)} memories, cleanup needed")

        except Exception as e:
            logger.error(f"Failed to check session cleanup: {e}")

    def get_stats(self) -> Dict[str, Union[str, int, float]]:
        """Get memory manager statistics."""
        return self.stats.copy()


# === Factory Functions ===


def create_memory_manager(**kwargs) -> EnhancedMemoryManager:
    """Factory function to create memory manager with Qdrant backend."""

    embedding_model = kwargs.get("embedding_model") or OpenAIEmbeddings(model="text-embedding-3-small")

    # Create Qdrant backend
    qdrant_url = os.environ.get("QDRANT_ENDPOINT")
    collection_name = os.environ.get("QDRANT_CLUSTER_ID")
    api_key = os.environ.get("QDRANT_API_KEY")

    if not all([qdrant_url, collection_name, api_key]):
        raise ValueError("Qdrant environment variables not set")

    client = QdrantClient(url=qdrant_url, api_key=api_key)
    vector_store = Qdrant(client=client, collection_name=collection_name, embeddings=embedding_model)
    backend = QdrantMemoryBackend(vector_store, embedding_model)

    return EnhancedMemoryManager(storage_backend=backend, embedding_model=embedding_model, **{k: v for k, v in kwargs.items() if k not in ["embedding_model"]})


# === Background Tasks ===


class MemoryMaintenanceTask:
    """Background task for memory maintenance."""

    def __init__(self, memory_manager: EnhancedMemoryManager):
        self.memory_manager = memory_manager
        self.running = False

    async def start_maintenance_loop(self, cleanup_interval_hours: int = 24, retention_days: int = 30):
        """Start background maintenance loop."""
        self.running = True

        while self.running:
            try:
                # Wait for cleanup interval
                await asyncio.sleep(cleanup_interval_hours * 3600)

                # Perform cleanup
                cleaned_count = await self.memory_manager.cleanup_old_memories(retention_days)
                logger.info(f"Background cleanup removed {cleaned_count} old memories")

            except Exception as e:
                logger.error(f"Memory maintenance error: {e}")

    def stop(self):
        """Stop the maintenance loop."""
        self.running = False


# === Global Memory Manager Instance ===

# Create global instance (can be configured via environment variables)
global_memory_manager = create_memory_manager(max_memories_per_session=100, relevance_threshold=0.7)

if __name__ == "__main__":
    # Test the enhanced memory system
    async def test_memory():
        manager = create_memory_manager()

        # Store some interactions
        await manager.store_interaction("user1", "session1", "What are public records laws?", "Public records laws vary by state but generally require government transparency...", {"topic": "public_records", "complexity": 0.6})

        await manager.store_interaction("user1", "session1", "What about in Massachusetts?", "In Massachusetts, the Public Records Law requires agencies to provide access...", {"topic": "massachusetts_law", "complexity": 0.4})

        # Search for relevant memories
        memories = await manager.retrieve_relevant_memories("user1", "session1", "Massachusetts public records")

        print(f"Found {len(memories)} relevant memories")
        for memory in memories:
            print(f"- {memory.query} (relevance: {memory.relevance_score:.3f})")

    asyncio.run(test_memory())

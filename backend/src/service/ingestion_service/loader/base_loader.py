"""
Base loader for all document types.
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from langchain_core.documents import Document

from src.service.ingestion_service.progress_tracker import get_tracker


class BaseLoader(ABC):
    """Abstract base class for document loaders."""

    def __init__(self, metadata_json_path: str, documents_dir: str, limit: Optional[int] = None):
        self.metadata_json_path = metadata_json_path
        self.documents_dir = documents_dir
        self.limit = limit
        self.tracker = get_tracker()

    def load_metadata(self) -> List[Dict]:
        """Load metadata from the JSON file."""
        with open(self.metadata_json_path, "r") as f:
            metadata = json.load(f)
        if self.limit:
            return metadata[: self.limit]
        return metadata

    @abstractmethod
    def load_and_chunk(self) -> List[Document]:
        """Load documents from metadata and chunk them."""

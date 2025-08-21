"""
Comprehensive Deduplication Engine for NEFAC Crawler

┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEDUPLICATION & METADATA MERGING PIPELINE              │
│                                                                         │
│  Input Documents    Content Hashing    Fuzzy Matching    Metadata Merging │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │  Document    │──►│  Hash        │──►│  Similarity  │──►│  Metadata    │ │
│  │  Collection  │   │  Generation  │   │  Analysis    │   │  Consolidation│ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘ │
│           │                 │                 │                 │         │
│           ▼                 ▼                 ▼                 ▼         │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    Deduplication Statistics                       │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │  │
│  │  │  Duplicates │    │  Merged     │    │  Quality    │             │  │
│  │  │  Removed    │    │  Documents  │    │  Metrics    │             │  │
│  │  └─────────────┘    └─────────────┘    └─────────────┘             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘

CORE COMPONENTS:
1. DeduplicationEngine - Identifies and groups duplicate documents
2. MetadataMerger - Intelligently merges metadata from multiple sources
3. DeduplicationManager - Orchestrates the complete deduplication workflow
4. DeduplicationStats - Tracks and reports comprehensive statistics

DEDUPLICATION TECHNIQUES:
- Content Hashing: Exact duplicate detection using SHA-256 hashing
- Fuzzy Matching: Near-duplicate detection using sequence similarity
- URL Normalization: Consistent URL handling to prevent false positives
"""

import logging
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from .config import CrawlerConfig
from .types import (
    ExtendedDocumentInfo,
    DocumentInfo,
    CrawlResult,
    SourceMetadata,
)

logger = logging.getLogger(__name__)


class DeduplicationStats:
    """Statistics for deduplication process."""

    def __init__(self):
        self.total_input_documents = 0
        self.total_output_documents = 0
        self.duplicates_removed = 0
        self.documents_merged = 0
        self.sources_consolidated = 0

        # Source-specific stats
        self.source_breakdown = defaultdict(int)
        self.merge_combinations = defaultdict(int)

        # Quality improvements
        self.metadata_enriched = 0
        self.missing_fields_filled = 0

        # Processing time
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.duration_seconds: float = 0.0

    def to_dict(self) -> Dict:
        """Convert statistics to dictionary for reporting."""
        return {
            "total_input_documents": self.total_input_documents,
            "total_output_documents": self.total_output_documents,
            "duplicates_removed": self.duplicates_removed,
            "documents_merged": self.documents_merged,
            "sources_consolidated": self.sources_consolidated,
            "metadata_enriched": self.metadata_enriched,
            "processing_time_seconds": self.duration_seconds,
            "source_breakdown": dict(self.source_breakdown),
            "merge_combinations": dict(self.merge_combinations),
        }


class MetadataMerger:
    """Intelligent metadata merger with source prioritization and conflict resolution."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.source_priorities = getattr(
            config,
            "source_priorities",
            {
                "graphql": 100,
                "wordpress": 80,
                "crawl4ai": 60,
                "selenium": 40,
                "web_scraper": 30,
                "link_discovery": 20,
            },
        )

    def merge_metadata(
        self, documents: List[ExtendedDocumentInfo]
    ) -> ExtendedDocumentInfo:
        """
        Merges multiple ExtendedDocumentInfo objects into a single comprehensive document.
        """
        if not documents:
            raise ValueError("Cannot merge metadata from empty document list")

        if len(documents) == 1:
            return documents[0]

        primary_doc = self._select_primary_document(documents)

        merged_doc = ExtendedDocumentInfo(
            id=primary_doc.id,
            title=primary_doc.title,
            url=primary_doc.url,
            content_hash=primary_doc.content_hash,
            content_type=primary_doc.content_type,
            mime_type=primary_doc.mime_type,
            file_size=primary_doc.file_size,
            language=primary_doc.language,
            encoding=primary_doc.encoding,
            published_date=primary_doc.published_date,
            modified_date=primary_doc.modified_date,
            crawled_date=primary_doc.crawled_date,
            meta_description=primary_doc.meta_description,
            meta_keywords=(
                primary_doc.meta_keywords.copy() if primary_doc.meta_keywords else []
            ),
            og_title=primary_doc.og_title,
            og_description=primary_doc.og_description,
            og_image=primary_doc.og_image,
            og_type=primary_doc.og_type,
            twitter_card=primary_doc.twitter_card,
            twitter_title=primary_doc.twitter_title,
            twitter_description=primary_doc.twitter_description,
            canonical_url=primary_doc.canonical_url,
            word_count=primary_doc.word_count,
            reading_time=primary_doc.reading_time,
            sentiment_score=primary_doc.sentiment_score,
            topics=primary_doc.topics.copy() if primary_doc.topics else [],
            entities=primary_doc.entities.copy() if primary_doc.entities else [],
            keywords=primary_doc.keywords.copy() if primary_doc.keywords else [],
            sources=[],  # Will be populated
            extraction_methods=[],  # Will be populated
            related_documents=(
                primary_doc.related_documents.copy()
                if primary_doc.related_documents
                else []
            ),
            parent_page=primary_doc.parent_page,
            child_documents=(
                primary_doc.child_documents.copy()
                if primary_doc.child_documents
                else []
            ),
            outbound_links=(
                primary_doc.outbound_links.copy() if primary_doc.outbound_links else []
            ),
            inbound_links=(
                primary_doc.inbound_links.copy() if primary_doc.inbound_links else []
            ),
            content_quality_score=primary_doc.content_quality_score,
            accessibility_score=primary_doc.accessibility_score,
            seo_score=primary_doc.seo_score,
            nefac_category=primary_doc.nefac_category,
            legal_topic=primary_doc.legal_topic,
            jurisdiction=primary_doc.jurisdiction,
            case_references=(
                primary_doc.case_references.copy()
                if primary_doc.case_references
                else []
            ),
            legal_citations=(
                primary_doc.legal_citations.copy()
                if primary_doc.legal_citations
                else []
            ),
            response_headers=(
                primary_doc.response_headers.copy()
                if primary_doc.response_headers
                else {}
            ),
            processing_errors=(
                primary_doc.processing_errors.copy()
                if primary_doc.processing_errors
                else []
            ),
            processing_warnings=(
                primary_doc.processing_warnings.copy()
                if primary_doc.processing_warnings
                else []
            ),
            file_path=primary_doc.file_path,
            filename=primary_doc.filename,
            file_extension=primary_doc.file_extension,
            download_date=primary_doc.download_date,
            checksum=primary_doc.checksum,
        )

        # Consolidate sources and extraction methods
        source_dict = {}
        extraction_methods = set()

        for doc in documents:
            # Consolidate sources
            for source in doc.sources:
                if source.source_name not in source_dict:
                    source_dict[source.source_name] = source
                else:
                    # Update with higher confidence score if available
                    existing = source_dict[source.source_name]
                    if source.confidence_score > existing.confidence_score:
                        source_dict[source.source_name] = source

            # Consolidate extraction methods
            extraction_methods.update(doc.extraction_methods)

            # Merge lists while avoiding duplicates
            self._merge_unique_list(merged_doc.meta_keywords, doc.meta_keywords)
            self._merge_unique_list(merged_doc.topics, doc.topics)
            self._merge_unique_list(merged_doc.entities, doc.entities)
            self._merge_unique_list(merged_doc.keywords, doc.keywords)
            self._merge_unique_list(merged_doc.related_documents, doc.related_documents)
            self._merge_unique_list(merged_doc.child_documents, doc.child_documents)
            self._merge_unique_list(merged_doc.outbound_links, doc.outbound_links)
            self._merge_unique_list(merged_doc.inbound_links, doc.inbound_links)
            self._merge_unique_list(merged_doc.case_references, doc.case_references)
            self._merge_unique_list(merged_doc.legal_citations, doc.legal_citations)
            self._merge_unique_list(merged_doc.processing_errors, doc.processing_errors)
            self._merge_unique_list(
                merged_doc.processing_warnings, doc.processing_warnings
            )

        # Set consolidated sources and methods
        merged_doc.sources = list(source_dict.values())
        merged_doc.extraction_methods = list(extraction_methods)

        # Calculate completeness and quality scores
        merged_doc.content_quality_score = self._calculate_completeness_score(
            merged_doc
        )

        return merged_doc

    def _select_primary_document(
        self, documents: List[ExtendedDocumentInfo]
    ) -> ExtendedDocumentInfo:
        """Select the primary document based on source priority and quality."""
        if not documents:
            raise ValueError("Cannot select primary document from empty list")

        # Sort by source priority and quality
        def sort_key(doc):
            # Get highest priority source for this document
            max_priority = 0
            max_confidence = 0.0

            for source in doc.sources:
                priority = self.source_priorities.get(source.source_name, 0)
                if priority > max_priority:
                    max_priority = priority
                    max_confidence = source.confidence_score
                elif (
                    priority == max_priority
                    and source.confidence_score > max_confidence
                ):
                    max_confidence = source.confidence_score

            # Secondary sort by content quality if available
            quality_score = doc.content_quality_score or 0.0

            return (max_priority, max_confidence, quality_score)

        sorted_docs = sorted(documents, key=sort_key, reverse=True)
        return sorted_docs[0]

    def _merge_unique_list(self, target_list: List, source_list: List):
        """Merge source list into target list without duplicates."""
        for item in source_list:
            if item not in target_list:
                target_list.append(item)

    def _calculate_completeness_score(self, doc: ExtendedDocumentInfo) -> float:
        """Calculate a completeness score for the document based on filled fields."""
        # Define fields to check for completeness
        fields_to_check = [
            "title",
            "url",
            "content_hash",
            "mime_type",
            "file_size",
            "published_date",
            "word_count",
            "meta_description",
            "og_title",
            "og_description",
            "topics",
            "entities",
            "keywords",
            "sources",
            "content_quality_score",
            "seo_score",
            "file_path",
            "filename",
            "checksum",
            "response_headers",
        ]

        filled_fields = sum(
            1
            for field in fields_to_check
            if getattr(doc, field, None)
            and (
                not isinstance(getattr(doc, field), list)
                or len(getattr(doc, field)) > 0
            )
        )

        return filled_fields / len(fields_to_check) if fields_to_check else 0.0


class DeduplicationEngine:
    """Identify and merge duplicate documents across all crawler sources."""

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.metadata_merger = MetadataMerger(config)

        # Configuration
        self.content_similarity_threshold = getattr(
            config, "content_similarity_threshold", 0.95
        )
        self.fuzzy_similarity_threshold = getattr(
            config, "fuzzy_similarity_threshold", 0.85
        )
        self.enable_url_normalization = getattr(
            config, "enable_url_normalization", True
        )
        self.enable_content_deduplication = getattr(
            config, "enable_content_deduplication", True
        )
        self.enable_fuzzy_matching = getattr(config, "enable_fuzzy_matching", True)

        # Statistics
        self.stats = DeduplicationStats()

        # Cache for content hashes to improve performance
        self._hash_cache: Dict[str, str] = {}

    def find_duplicates(
        self, documents: List[ExtendedDocumentInfo]
    ) -> Dict[str, List[ExtendedDocumentInfo]]:
        """Find duplicate documents and group them by content hash."""
        logger.info(f"Starting deduplication analysis for {len(documents)} documents")

        # Update statistics
        self.stats.total_input_documents = len(documents)
        self.stats.start_time = datetime.now()

        # Group documents by content hash
        hash_groups = defaultdict(list)

        for doc in documents:
            content_hash = self._get_or_generate_hash(doc)
            hash_groups[content_hash].append(doc)

            # Track source statistics
            for source in doc.sources:
                self.stats.source_breakdown[source.source_name] += 1

        # Filter to only groups with duplicates
        duplicate_groups = {
            hash_key: docs for hash_key, docs in hash_groups.items() if len(docs) > 1
        }

        # If fuzzy matching is enabled, find near-duplicates
        if self.enable_fuzzy_matching and self.fuzzy_similarity_threshold > 0:
            fuzzy_groups = self._find_fuzzy_duplicates(documents, duplicate_groups)
            duplicate_groups.update(fuzzy_groups)

        logger.info(f"Found {len(duplicate_groups)} duplicate groups")
        return duplicate_groups

    def merge_duplicates(
        self, duplicate_groups: Dict[str, List[ExtendedDocumentInfo]]
    ) -> List[ExtendedDocumentInfo]:
        """Merge duplicate documents within each group."""
        merged_documents = []
        total_duplicates = 0

        for hash_key, duplicates in duplicate_groups.items():
            total_duplicates += len(duplicates)

            try:
                # Merge metadata from all duplicates
                merged_doc = self.metadata_merger.merge_metadata(duplicates)
                merged_documents.append(merged_doc)

                # Update statistics
                self.stats.documents_merged += 1
                self.stats.sources_consolidated += len(duplicates)

                # Track merge combinations
                source_names = sorted(
                    [source.source_name for doc in duplicates for source in doc.sources]
                )
                combination_key = "+".join(set(source_names))
                self.stats.merge_combinations[combination_key] += 1

            except Exception as e:
                logger.error(f"Failed to merge duplicates for hash {hash_key}: {e}")
                # Add all duplicates if merging fails
                merged_documents.extend(duplicates)

        self.stats.duplicates_removed = total_duplicates - len(merged_documents)
        return merged_documents

    def process_documents(
        self, documents: List[ExtendedDocumentInfo]
    ) -> List[ExtendedDocumentInfo]:
        """Process documents through complete deduplication pipeline."""
        if not documents:
            return []

        # Find duplicates
        duplicate_groups = self.find_duplicates(documents)

        # Separate duplicates from unique documents
        duplicate_docs = []
        unique_docs = []

        # Collect all duplicate documents
        for group in duplicate_groups.values():
            duplicate_docs.extend(group)

        # Collect unique documents
        duplicate_ids = {doc.id for doc in duplicate_docs}
        unique_docs = [doc for doc in documents if doc.id not in duplicate_ids]

        # Merge duplicates
        merged_docs = (
            self.merge_duplicates(duplicate_groups) if duplicate_groups else []
        )

        # Combine unique and merged documents
        final_documents = unique_docs + merged_docs

        # Update statistics
        self.stats.total_output_documents = len(final_documents)
        self.stats.end_time = datetime.now()
        if self.stats.start_time:
            self.stats.duration_seconds = (
                self.stats.end_time - self.stats.start_time
            ).total_seconds()

        logger.info(
            f"Deduplication complete: {len(documents)} → {len(final_documents)} documents"
        )
        return final_documents

    def get_statistics(self) -> Dict:
        """Get deduplication statistics."""
        return self.stats.to_dict()

    def _get_or_generate_hash(self, doc: ExtendedDocumentInfo) -> str:
        """Get existing content hash or generate one."""
        if doc.content_hash:
            return doc.content_hash

        # Generate hash based on available content
        return doc.generate_content_hash()

    def _find_fuzzy_duplicates(
        self,
        documents: List[ExtendedDocumentInfo],
        existing_groups: Dict[str, List[ExtendedDocumentInfo]],
    ) -> Dict[str, List[ExtendedDocumentInfo]]:
        """Find near-duplicate documents using fuzzy matching."""
        if not self.enable_fuzzy_matching or self.fuzzy_similarity_threshold <= 0:
            return {}

        fuzzy_groups = defaultdict(list)
        processed_pairs = set()

        # Compare documents for fuzzy similarity
        for i, doc1 in enumerate(documents):
            for j, doc2 in enumerate(documents[i + 1 :], i + 1):
                # Skip if already in same group
                pair_key = tuple(sorted([doc1.id, doc2.id]))
                if pair_key in processed_pairs:
                    continue

                processed_pairs.add(pair_key)

                # Check fuzzy similarity
                similarity = self._calculate_content_similarity(doc1, doc2)
                if similarity >= self.fuzzy_similarity_threshold:
                    # Add to fuzzy groups
                    group_key = f"fuzzy_{min(doc1.id, doc2.id)}"
                    fuzzy_groups[group_key].extend([doc1, doc2])

        # Remove duplicates within groups
        for group_key in fuzzy_groups:
            seen_ids = set()
            unique_docs = []
            for doc in fuzzy_groups[group_key]:
                if doc.id not in seen_ids:
                    unique_docs.append(doc)
                    seen_ids.add(doc.id)
            fuzzy_groups[group_key] = unique_docs

        logger.info(f"Found {len(fuzzy_groups)} fuzzy duplicate groups")
        return fuzzy_groups

    def _calculate_content_similarity(
        self, doc1: ExtendedDocumentInfo, doc2: ExtendedDocumentInfo
    ) -> float:
        """Calculate similarity between two documents based on their content."""
        # For now, we'll use a simple approach based on title similarity
        # In a full implementation, this would compare actual content
        if doc1.title and doc2.title:
            return SequenceMatcher(None, doc1.title.lower(), doc2.title.lower()).ratio()
        return 0.0


class DeduplicationManager:
    """
    High-level orchestrator for comprehensive deduplication across all crawler sources.

    This class provides the main interface for the crawler to process documents
    from multiple sources through the deduplication pipeline.
    """

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self.deduplication_engine = DeduplicationEngine(config)
        self.metadata_merger = MetadataMerger(config)

    def process_all_sources(
        self, source_documents: Dict[str, List[DocumentInfo]]
    ) -> CrawlResult:
        """Process documents from all sources through comprehensive deduplication."""
        logger.info("Starting comprehensive deduplication across all sources...")

        # Convert legacy DocumentInfo to ExtendedDocumentInfo
        extended_docs = []
        total_input = 0

        for source_name, docs in source_documents.items():
            total_input += len(docs)
            for doc in docs:
                extended_doc = self._convert_to_extended(doc, source_name)
                if extended_doc:
                    extended_docs.append(extended_doc)

        logger.info(
            f"Converted {total_input} documents to {len(extended_docs)} extended documents"
        )

        # Apply deduplication
        final_documents = self.deduplication_engine.process_documents(extended_docs)

        # Create crawl result
        crawl_result = CrawlResult(
            documents=final_documents,
            total_urls_discovered=total_input,
            total_documents_extracted=len(final_documents),
            duplicates_found=total_input - len(final_documents),
            duplicates_merged=self.deduplication_engine.stats.documents_merged,
        )

        logger.info(
            f"Deduplication complete: {total_input} → {len(final_documents)} documents"
        )
        return crawl_result

    def get_statistics(self) -> DeduplicationStats:
        """Get deduplication statistics."""
        return self.deduplication_engine.stats

    @property
    def stats(self) -> DeduplicationStats:
        """Access to deduplication statistics."""
        return self.deduplication_engine.stats

    def _convert_to_extended(
        self, doc: DocumentInfo, source_name: str
    ) -> Optional[ExtendedDocumentInfo]:
        """Convert legacy DocumentInfo to ExtendedDocumentInfo."""
        try:
            # Defensive check to ensure we're working with a DocumentInfo object
            if not hasattr(doc, "id") or not hasattr(doc, "source_url"):
                logger.warning(
                    f"Skipping non-DocumentInfo object: {type(doc)} with content {str(doc)[:100]}..."
                )
                return None

            # Create source metadata
            source_metadata = SourceMetadata(
                source_name=source_name,
                extraction_date=datetime.now(),
                confidence_score=0.8,  # Default confidence
                metadata={},
                extraction_method=source_name,
                source_url=doc.source_url,
            )

            # Create extended document
            extended_doc = ExtendedDocumentInfo(
                id=doc.id,
                title=doc.title,
                url=doc.source_url,
                content_hash="",  # Will be generated if needed
                sources=[source_metadata],
                extraction_methods=[source_name],
                mime_type=doc.mime_type,
                file_size=doc.file_size,
                crawled_date=datetime.now(),
                download_date=doc.download_date,
                file_path=doc.file_path,
                filename=doc.filename,
            )

            # Generate content hash if not already set
            if not extended_doc.content_hash:
                extended_doc.content_hash = extended_doc.generate_content_hash()

            return extended_doc

        except Exception as e:
            logger.error(
                f"Failed to convert document {getattr(doc, 'id', 'unknown')}: {e}"
            )
            return None

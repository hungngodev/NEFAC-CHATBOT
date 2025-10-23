"""LlamaIndex-powered node parsing utilities with optional contextual retrieval.

This module wraps the SemanticDoubleMergingSplitterNodeParser example from the
LlamaIndex docs and layers on Anthropic-style contextual summaries plus optional
LLM-driven metadata extraction. The default entry point
``build_nodes_from_text`` preserves backward compatibility while enabling the
enhanced behaviour when the relevant environment flags are set.
"""

from __future__ import annotations

import copy
import logging
import os
from functools import lru_cache
from typing import List

from llama_index.core import Document as LIDocument
from llama_index.core.extractors import (
    KeywordExtractor,
    QuestionsAnsweredExtractor,
    SummaryExtractor,
    TitleExtractor,
)
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.node_parser import (
    LanguageConfig,
    NodeParser,
    SemanticDoubleMergingSplitterNodeParser,
    SimpleNodeParser,
)
from llama_index.core.schema import BaseNode

from src.service.ingestion_service.settings import (
    ENABLE_CONTEXTUAL_RETRIEVAL,
    ENABLE_METADATA_EXTRACTION,
)

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Domain-specific semantic splitter presets
# Based on tutorial: https://developers.llamaindex.ai/python/examples/node_parsers/semantic_double_merging_chunking/
# Different spaCy models and parameter values perform differently on specific texts
SEMANTIC_SPLITTER_PRESETS = {
    # English presets
    "legal_documents": {
        "language": "english",
        "spacy_model": "en_core_web_md",
        "initial_threshold": 0.4,
        "appending_threshold": 0.5,
        "merging_threshold": 0.5,
        "max_chunk_size": 5000,
        "description": "Optimized for legal documents with complex terminology",
    },
    "technical_docs": {
        "language": "english",
        "spacy_model": "en_core_web_md",
        "initial_threshold": 0.35,
        "appending_threshold": 0.45,
        "merging_threshold": 0.45,
        "max_chunk_size": 3000,
        "description": "Optimized for technical docs with code snippets",
    },
    "general": {
        "language": "english",
        "spacy_model": "en_core_web_sm",
        "initial_threshold": 0.5,
        "appending_threshold": 0.6,
        "merging_threshold": 0.6,
        "max_chunk_size": 2000,
        "description": "General-purpose configuration for standard documents",
    },
    "academic": {
        "language": "english",
        "spacy_model": "en_core_web_md",
        "initial_threshold": 0.45,
        "appending_threshold": 0.55,
        "merging_threshold": 0.55,
        "max_chunk_size": 4000,
        "description": "Optimized for academic papers with citations",
    },
    # French presets
    "french_legal": {
        "language": "french",
        "spacy_model": "fr_core_news_md",
        "initial_threshold": 0.4,
        "appending_threshold": 0.5,
        "merging_threshold": 0.5,
        "max_chunk_size": 5000,
        "description": "Optimisé pour documents juridiques français",
    },
    "french_general": {
        "language": "french",
        "spacy_model": "fr_core_news_sm",
        "initial_threshold": 0.5,
        "appending_threshold": 0.6,
        "merging_threshold": 0.6,
        "max_chunk_size": 2000,
        "description": "Configuration générale pour documents français",
    },
    # Spanish presets
    "spanish_legal": {
        "language": "spanish",
        "spacy_model": "es_core_news_md",
        "initial_threshold": 0.4,
        "appending_threshold": 0.5,
        "merging_threshold": 0.5,
        "max_chunk_size": 5000,
        "description": "Optimizado para documentos legales en español",
    },
    "spanish_general": {
        "language": "spanish",
        "spacy_model": "es_core_news_sm",
        "initial_threshold": 0.5,
        "appending_threshold": 0.6,
        "merging_threshold": 0.6,
        "max_chunk_size": 2000,
        "description": "Configuración general para documentos en español",
    },
    # German presets
    "german_legal": {
        "language": "german",
        "spacy_model": "de_core_news_md",
        "initial_threshold": 0.4,
        "appending_threshold": 0.5,
        "merging_threshold": 0.5,
        "max_chunk_size": 5000,
        "description": "Optimiert für deutsche Rechtsdokumente",
    },
    "german_general": {
        "language": "german",
        "spacy_model": "de_core_news_sm",
        "initial_threshold": 0.5,
        "appending_threshold": 0.6,
        "merging_threshold": 0.6,
        "max_chunk_size": 2000,
        "description": "Allgemeine Konfiguration für deutsche Dokumente",
    },
    # Chinese presets
    "chinese_general": {
        "language": "chinese",
        "spacy_model": "zh_core_web_sm",
        "initial_threshold": 0.5,
        "appending_threshold": 0.6,
        "merging_threshold": 0.6,
        "max_chunk_size": 2000,
        "description": "通用中文文档配置",
    },
}


def get_semantic_splitter_for_domain(domain: str = "legal_documents", **overrides) -> NodeParser:
    """Get pre-tuned semantic splitter for specific document domains.

    Args:
        domain: One of 'legal_documents', 'technical_docs',
            'general', 'academic'
        **overrides: Override any preset configuration values

    Returns:
        Configured semantic splitter

    Example:
        >>> splitter = get_semantic_splitter_for_domain(
        ...     domain="legal_documents",
        ...     max_chunk_size=6000  # Override default
        ... )
    """
    preset = SEMANTIC_SPLITTER_PRESETS.get(domain, SEMANTIC_SPLITTER_PRESETS["general"])
    config = preset.copy()
    config.update(overrides)
    desc = config.get("description", "")
    logger.info(f"Using semantic splitter preset: {domain} - {desc}")

    return _create_semantic_splitter(
        language=config.get("language", "english"),
        spacy_model=config.get("spacy_model", "en_core_web_sm"),
        initial_threshold=config.get("initial_threshold", 0.4),
        appending_threshold=config.get("appending_threshold", 0.5),
        merging_threshold=config.get("merging_threshold", 0.5),
        max_chunk_size=config.get("max_chunk_size", 2000),
    )


def _create_semantic_splitter(
    language: str = "english",
    spacy_model: str = "en_core_web_sm",
    initial_threshold: float = 0.4,
    appending_threshold: float = 0.5,
    merging_threshold: float = 0.5,
    max_chunk_size: int = 2000,
) -> NodeParser:
    """Create semantic splitter with explicit configuration.

    Internal helper that handles spaCy model loading and fallback.
    Enhanced with auto-download from settings.
    """
    try:
        import spacy  # type: ignore[import-not-found]

        from src.service.ingestion_service.settings import SEMANTIC_SPLITTER_AUTO_DOWNLOAD

        # Auto-download spaCy model if not available
        if SEMANTIC_SPLITTER_AUTO_DOWNLOAD:
            try:
                spacy.load(spacy_model)
            except OSError:
                logger.info(f"Downloading spaCy model: {spacy_model}")
                import spacy.cli

                spacy.cli.download(spacy_model)
                logger.info(f"Successfully downloaded {spacy_model}")
    except ImportError:
        logger.warning("spacy not available")

    try:
        import spacy  # type: ignore[import-not-found]

        # Try to load the specified model
        try:
            spacy.load(spacy_model)
            logger.info(f"Loaded spaCy model: {spacy_model}")
        except OSError:
            # Fallback to smaller model
            fallback_model = "en_core_web_sm"
            logger.warning(f"Model {spacy_model} not found, " f"falling back to {fallback_model}")
            spacy.load(fallback_model)
            spacy_model = fallback_model

        config = LanguageConfig(language=language, spacy_model=spacy_model)

        logger.info(f"Initializing SemanticDoubleMergingSplitterNodeParser: " f"lang={language}, model={spacy_model}, " f"thresholds=({initial_threshold}/" f"{appending_threshold}/{merging_threshold}), " f"max_chunk={max_chunk_size}")

        return SemanticDoubleMergingSplitterNodeParser(
            language_config=config,
            initial_threshold=initial_threshold,
            appending_threshold=appending_threshold,
            merging_threshold=merging_threshold,
            max_chunk_size=max_chunk_size,
        )
    except Exception as exc:
        logger.warning(f"Semantic splitter unavailable ({exc}). " "Falling back to SimpleNodeParser.")
        return SimpleNodeParser.from_defaults(chunk_size=max_chunk_size)


@lru_cache(maxsize=1)
def get_semantic_splitter() -> NodeParser:
    """Return a configured semantic splitter, falling back to SimpleNodeParser.

    The configuration mirrors the public tutorial:
    https://developers.llamaindex.ai/python/examples/node_parsers/semantic_double_merging_chunking/
    """

    language = os.getenv("SEMANTIC_SPLITTER_LANGUAGE", "english")
    spacy_model = os.getenv("SEMANTIC_SPLITTER_SPACY_MODEL", "en_core_web_sm")
    config = LanguageConfig(language=language, spacy_model=spacy_model)

    initial_threshold = _env_float("SEMANTIC_SPLITTER_INITIAL_THRESHOLD", 0.4)
    appending_threshold = _env_float("SEMANTIC_SPLITTER_APPEND_THRESHOLD", 0.5)
    merging_threshold = _env_float("SEMANTIC_SPLITTER_MERGE_THRESHOLD", 0.5)
    max_chunk_size = int(float(os.getenv("SEMANTIC_SPLITTER_MAX_CHUNK", "2000")))

    try:
        logger.info(
            "Initializing SemanticDoubleMergingSplitterNodeParser (lang=%s, model=%s)",
            language,
            spacy_model,
        )
        return SemanticDoubleMergingSplitterNodeParser(
            language_config=config,
            initial_threshold=initial_threshold,
            appending_threshold=appending_threshold,
            merging_threshold=merging_threshold,
            max_chunk_size=max_chunk_size,
        )
    except Exception as exc:  # pragma: no cover - only hit when spaCy missing
        logger.warning(
            "Semantic splitter unavailable (%s). Falling back to SimpleNodeParser.",
            exc,
        )
        return SimpleNodeParser.from_defaults(chunk_size=max_chunk_size)


class ContextualNodeParser:
    """Semantic splitter wrapper that adds contextual summaries.

    Inspired by https://developers.llamaindex.ai/python/examples/cookbooks/contextual_retrieval/
    """

    CONTEXT_PROMPT = """<document>
{doc}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

    def __init__(
        self,
        llm: LLM | None = None,
        *,
        enable_contextual_retrieval: bool = True,
        enable_metadata_extraction: bool = False,
        enable_prompt_caching: bool = True,
        max_doc_context_length: int = 100_000,
    ) -> None:
        from llama_index.core import Settings

        self.llm: LLM | None = llm or Settings.llm
        self.enable_contextual = enable_contextual_retrieval and self.llm is not None
        self.enable_metadata = enable_metadata_extraction and self.llm is not None
        self.enable_prompt_caching = enable_prompt_caching
        self.max_doc_context_length = max_doc_context_length
        self.base_parser = get_semantic_splitter()

        self.extractors = []
        if self.enable_metadata:
            self.extractors = [
                TitleExtractor(llm=self.llm, nodes=5),
                QuestionsAnsweredExtractor(llm=self.llm, questions=3),
                SummaryExtractor(llm=self.llm, summaries=["prev", "self"]),
                KeywordExtractor(llm=self.llm, keywords=10),
            ]

    def _add_context(self, node: BaseNode, document_text: str, document_meta: dict) -> BaseNode:
        if not self.enable_contextual:
            return node

        truncated_doc = document_text[: self.max_doc_context_length]
        chunk_text = node.get_content()

        try:
            llm_model = (getattr(self.llm, "model", "") or "").lower() if self.llm else ""
            is_anthropic = any(token in llm_model for token in {"claude", "anthropic"})

            if self.llm is None:
                raise RuntimeError("No LLM configured for contextual retrieval")

            if is_anthropic and self.enable_prompt_caching:
                response = self.llm.chat(
                    [
                        ChatMessage(role="system", content="You are a helpful assistant."),
                        ChatMessage(
                            role="user",
                            content=f"<document>\n{truncated_doc}\n</document>",
                            additional_kwargs={"cache_control": {"type": "ephemeral"}},
                        ),
                        ChatMessage(
                            role="user",
                            content=self.CONTEXT_PROMPT.format(doc=truncated_doc, chunk=chunk_text),
                        ),
                    ],
                    extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                )
                contextual_summary = str(response.message.content).strip()
            else:
                prompt = self.CONTEXT_PROMPT.format(doc=truncated_doc, chunk=chunk_text)
                contextual_summary = self.llm.complete(prompt).text.strip()

        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Contextual summary generation failed: %s", exc)
            return node

        contextualised = copy.deepcopy(node)
        contextualised.metadata.setdefault("document_title", document_meta.get("title"))
        contextualised.metadata.setdefault("document_source", document_meta.get("source"))
        contextualised.metadata["contextual_summary"] = contextual_summary
        contextualised.text = f"{contextual_summary}\n\n{chunk_text}"
        return contextualised

    def build_nodes_from_documents(
        self,
        documents: List[LIDocument],
        *,
        show_progress: bool = False,
    ) -> List[BaseNode]:
        all_nodes: List[BaseNode] = []

        for doc in documents:
            nodes = list(self.base_parser.get_nodes_from_documents([doc]))

            if self.enable_contextual:
                nodes = [self._add_context(node, doc.get_content(), doc.metadata) for node in nodes]

            if self.enable_metadata and self.extractors:
                pipeline = IngestionPipeline(transformations=self.extractors)
                nodes = pipeline.run(nodes=nodes, show_progress=show_progress)

            all_nodes.extend(nodes)

        return all_nodes

    def build_nodes_from_text(self, text: str, metadata: dict) -> List[BaseNode]:
        li_doc = LIDocument(text=text, metadata=metadata)
        return self.build_nodes_from_documents([li_doc])


def build_nodes_from_text(text: str, metadata: dict) -> List[BaseNode]:
    parser = ContextualNodeParser(
        enable_contextual_retrieval=ENABLE_CONTEXTUAL_RETRIEVAL,
        enable_metadata_extraction=ENABLE_METADATA_EXTRACTION,
    )
    return parser.build_nodes_from_text(text, metadata)

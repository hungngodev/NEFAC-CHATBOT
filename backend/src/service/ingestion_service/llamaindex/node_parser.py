from __future__ import annotations

import copy
import logging
import os
from functools import lru_cache
from typing import List

import spacy
import spacy.cli
from llama_index.core import Document as LIDocument
from llama_index.core import Settings
from llama_index.core.extractors import (
    SummaryExtractor,
)
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.node_parser import (
    LanguageConfig,
    NodeParser,
    SemanticDoubleMergingSplitterNodeParser,
)
from llama_index.core.schema import BaseNode
from llama_index.core.storage.docstore import SimpleDocumentStore

from src.service.ingestion_service.llamaindex.metadata_utils import (
    build_chunk_id,
    sanitize_metadata,
)
from src.service.ingestion_service.settings import (
    ENABLE_CONTEXTUAL_RETRIEVAL,
    ENABLE_METADATA_EXTRACTION,
    SEMANTIC_SPLITTER_AUTO_DOWNLOAD,
    SEMANTIC_SPLITTER_PRESETS,
)

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def get_semantic_splitter_for_domain(domain: str = "legal_documents", **overrides) -> NodeParser:
    preset = SEMANTIC_SPLITTER_PRESETS.get(domain, SEMANTIC_SPLITTER_PRESETS["general"])
    config = preset.copy()
    config.update(overrides)
    logger.info(f"Using semantic splitter preset: {domain}")

    return _create_semantic_splitter(
        language=config.get("language", "en"),
        spacy_model=config.get("spacy_model", "en_core_web_sm"),
        initial_threshold=config.get("initial_threshold", 0.4),
        appending_threshold=config.get("appending_threshold", 0.5),
        merging_threshold=config.get("merging_threshold", 0.5),
        max_chunk_size=config.get("max_chunk_size", 2000),
    )


def _build_language_config(language: str, spacy_model: str) -> LanguageConfig:
    try:
        return LanguageConfig(language=language, spacy_model=spacy_model)
    except ValueError as exc:
        mismatch = "model is not matching your language" in str(exc)
        if not mismatch:
            raise

        logger.warning(
            "spaCy model %s is not in the approved list for %s, disabling validation",
            spacy_model,
            language,
        )
        return LanguageConfig(language=language, spacy_model=spacy_model, model_validation=False)


def _normalize_language(language: str) -> str:
    lang = (language or "").strip().lower()
    if not lang:
        return "english"

    lang = lang.replace("-", "_")
    primary = lang.split("_", 1)[0]

    language_map = {
        "en": "english",
        "eng": "english",
        "english": "english",
        "es": "spanish",
        "esp": "spanish",
        "spa": "spanish",
        "spanish": "spanish",
        "de": "german",
        "ger": "german",
        "deu": "german",
        "german": "german",
        "fr": "french",
        "fra": "french",
        "fre": "french",
        "french": "french",
        "zh": "chinese",
        "zho": "chinese",
        "chi": "chinese",
        "chinese": "chinese",
    }

    return language_map.get(lang, language_map.get(primary, lang))


def _create_semantic_splitter(
    language: str = "en",
    spacy_model: str = "en_core_web_sm",
    initial_threshold: float = 0.4,
    appending_threshold: float = 0.5,
    merging_threshold: float = 0.5,
    max_chunk_size: int = 2000,
) -> NodeParser:
    language = _normalize_language(language)

    if SEMANTIC_SPLITTER_AUTO_DOWNLOAD:
        spacy.load(spacy_model)
    else:
        spacy.load(spacy_model)

    config = _build_language_config(language=language, spacy_model=spacy_model)

    return SemanticDoubleMergingSplitterNodeParser(
        language_config=config,
        initial_threshold=initial_threshold,
        appending_threshold=appending_threshold,
        merging_threshold=merging_threshold,
        max_chunk_size=max_chunk_size,
    )


@lru_cache(maxsize=1)
def get_semantic_splitter() -> NodeParser:
    language = _normalize_language(os.getenv("SEMANTIC_SPLITTER_LANGUAGE", "en"))
    spacy_model = os.getenv("SEMANTIC_SPLITTER_SPACY_MODEL", "en_core_web_lg")
    initial_threshold = _env_float("SEMANTIC_SPLITTER_INITIAL_THRESHOLD", 0.4)
    appending_threshold = _env_float("SEMANTIC_SPLITTER_APPEND_THRESHOLD", 0.5)
    merging_threshold = _env_float("SEMANTIC_SPLITTER_MERGE_THRESHOLD", 0.5)
    max_chunk_size = int(float(os.getenv("SEMANTIC_SPLITTER_MAX_CHUNK", "2000")))
    return _create_semantic_splitter(
        language=language,
        spacy_model=spacy_model,
        initial_threshold=initial_threshold,
        appending_threshold=appending_threshold,
        merging_threshold=merging_threshold,
        max_chunk_size=max_chunk_size,
    )


def _derive_doc_id(node: BaseNode) -> str:
    meta = node.metadata or {}
    return meta.get("doc_id") or meta.get("document_id") or meta.get("ref_doc_id") or meta.get("id") or getattr(node, "node_id", None) or getattr(node, "id_", None) or "document"


class ContextualNodeParser:
    CONTEXT_PROMPT = """<document>
{doc}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>

Please generate a short succinct context summary to situate this text chunk within the overall document to enhance search retrieval, two or three sentences max. The chunk contains merged content from different document sections, so focus on the main topics and concepts rather than sequential flow. Answer only with the succinct context and nothing else."""

    def __init__(
        self,
        llm: LLM | None = None,
        *,
        enable_contextual_retrieval: bool = True,
        enable_metadata_extraction: bool = False,
        enable_prompt_caching: bool = True,
        max_doc_context_length: int = 100_000,
    ) -> None:
        self.llm: LLM | None = llm or Settings.llm
        self.enable_contextual = enable_contextual_retrieval and self.llm is not None
        self.enable_metadata = enable_metadata_extraction and self.llm is not None
        self.enable_prompt_caching = enable_prompt_caching
        self.max_doc_context_length = max_doc_context_length
        self.base_parser = get_semantic_splitter()

        self.extractors = []
        if self.enable_metadata:
            self.extractors = [
                SummaryExtractor(llm=self.llm, summaries=["prev", "self"]),
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
        contextualised.text = f"Contextual Summary: {contextual_summary}\n\nOriginal Chunk:\n{chunk_text}"
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
                pipeline = IngestionPipeline(
                    transformations=self.extractors,
                    docstore=SimpleDocumentStore(),
                )
                nodes = pipeline.run(nodes=nodes, show_progress=show_progress)

            normalized_nodes = []
            for idx, node in enumerate(nodes):
                doc_id = _derive_doc_id(node)
                chunk_id = build_chunk_id(doc_id, idx)
                meta = dict(node.metadata or {})
                meta["doc_id"] = doc_id
                meta["chunk_index"] = idx
                meta["chunk_id"] = chunk_id
                node.metadata = sanitize_metadata(meta, include_text=False)
                node.id_ = chunk_id
                normalized_nodes.append(node)

            all_nodes.extend(normalized_nodes)

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

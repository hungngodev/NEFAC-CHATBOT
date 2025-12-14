from __future__ import annotations

import copy
from typing import List, Optional

import spacy
import spacy.cli
from llama_index.core import Document as LIDocument
from llama_index.core import Settings
from llama_index.core.extractors import SummaryExtractor
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.node_parser import (
    LanguageConfig,
    NodeParser,
    SemanticDoubleMergingSplitterNodeParser,
    SentenceSplitter,
)
from llama_index.core.schema import BaseNode
from llama_index.core.storage.docstore import SimpleDocumentStore
from tqdm import tqdm

from src.service.ingestion_service.llamaindex.metadata_utils import (
    build_chunk_id,
    sanitize_metadata,
)
from src.service.ingestion_service.settings import (
    ENABLE_CONTEXTUAL_RETRIEVAL,
    ENABLE_METADATA_EXTRACTION,
    EXCLUDED_METADATA_KEYS,
    SEMANTIC_SPLITTER_APPEND_THRESHOLD,
    SEMANTIC_SPLITTER_AUTO_DOWNLOAD,
    SEMANTIC_SPLITTER_INITIAL_THRESHOLD,
    SEMANTIC_SPLITTER_LANGUAGE,
    SEMANTIC_SPLITTER_MAX_CHUNK,
    SEMANTIC_SPLITTER_MERGE_THRESHOLD,
    SEMANTIC_SPLITTER_SPACY_MODEL,
)

LANGUAGE_MAP = {
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


def _normalize_language(language: str) -> str:
    lang = (language or "").strip().lower().replace("-", "_")
    if not lang:
        return "english"
    primary = lang.split("_", 1)[0]
    return LANGUAGE_MAP.get(lang, LANGUAGE_MAP.get(primary, lang))


def _build_language_config(language: str, spacy_model: str) -> LanguageConfig:
    try:
        return LanguageConfig(language=language, spacy_model=spacy_model)
    except ValueError as exc:
        if "model is not matching your language" not in str(exc):
            raise
        return LanguageConfig(language=language, spacy_model=spacy_model, model_validation=False)


def _ensure_spacy_model(model_name: str) -> None:
    if SEMANTIC_SPLITTER_AUTO_DOWNLOAD:
        try:
            spacy.load(model_name)
        except OSError:
            spacy.cli.download(model_name)
            spacy.load(model_name)
    else:
        spacy.load(model_name)


def get_semantic_splitter() -> NodeParser:
    language = _normalize_language(SEMANTIC_SPLITTER_LANGUAGE)
    spacy_model = SEMANTIC_SPLITTER_SPACY_MODEL
    _ensure_spacy_model(spacy_model)
    config = _build_language_config(language=language, spacy_model=spacy_model)
    return SemanticDoubleMergingSplitterNodeParser(
        language_config=config,
        initial_threshold=SEMANTIC_SPLITTER_INITIAL_THRESHOLD,
        appending_threshold=SEMANTIC_SPLITTER_APPEND_THRESHOLD,
        merging_threshold=SEMANTIC_SPLITTER_MERGE_THRESHOLD,
        max_chunk_size=SEMANTIC_SPLITTER_MAX_CHUNK,
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

Please generate a short succinct context summary to situate this text chunk within the overall document
to enhance search retrieval, two or three sentences max. The chunk contains merged content from different
document sections, so focus on the main topics and concepts rather than sequential flow.
Answer only with the succinct context and nothing else."""

    def __init__(
        self,
        llm: Optional[LLM] = None,
        *,
        enable_contextual_retrieval: bool = True,
        enable_metadata_extraction: bool = False,
        enable_prompt_caching: bool = True,
        max_doc_context_length: int = 100_000,
    ) -> None:
        self.llm: Optional[LLM] = llm or Settings.llm
        self.enable_contextual = enable_contextual_retrieval and self.llm is not None
        self.enable_metadata = enable_metadata_extraction and self.llm is not None
        self.enable_prompt_caching = enable_prompt_caching
        self.max_doc_context_length = max_doc_context_length
        self.base_parser = get_semantic_splitter()
        self.extractors = []
        if self.enable_metadata:
            self.extractors = [SummaryExtractor(llm=self.llm, summaries=["prev", "self"])]

    def _get_llm_model_name(self) -> str:
        if not self.llm:
            return ""
        return (getattr(self.llm, "model", "") or "").lower()

    def _is_anthropic_model(self) -> bool:
        model_name = self._get_llm_model_name()
        return any(token in model_name for token in {"claude", "anthropic"})

    def _generate_contextual_summary_anthropic(self, truncated_doc: str, chunk_text: str) -> str:
        if self.llm is None:
            raise RuntimeError("No LLM configured for contextual retrieval")
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
        return str(response.message.content).strip()

    def _generate_contextual_summary_default(self, truncated_doc: str, chunk_text: str) -> str:
        if self.llm is None:
            raise RuntimeError("No LLM configured for contextual retrieval")
        prompt = self.CONTEXT_PROMPT.format(doc=truncated_doc, chunk=chunk_text)
        return self.llm.complete(prompt).text.strip()

    def _add_context(self, node: BaseNode, document_text: str, document_meta: dict) -> BaseNode:
        if not self.enable_contextual:
            return node

        truncated_doc = document_text[: self.max_doc_context_length]
        chunk_text = node.get_content()

        try:
            if self._is_anthropic_model() and self.enable_prompt_caching:
                contextual_summary = self._generate_contextual_summary_anthropic(truncated_doc, chunk_text)
            else:
                contextual_summary = self._generate_contextual_summary_default(truncated_doc, chunk_text)
        except Exception:
            return node

        contextualised = copy.deepcopy(node)
        contextualised.metadata.setdefault("document_title", document_meta.get("title"))
        contextualised.metadata.setdefault("document_source", document_meta.get("source"))
        contextualised.metadata["contextual_summary"] = contextual_summary
        if hasattr(contextualised, "text"):
            contextualised.text = f"Contextual Summary: {contextual_summary}\n\nOriginal Chunk:\n{chunk_text}"  # type: ignore[attr-defined]
        return contextualised

    def _run_semantic_splitting(self, doc: LIDocument, show_progress: bool) -> List[BaseNode]:
        split_doc = LIDocument(
            text=doc.get_content(),
            metadata={"title": doc.metadata.get("title", "")},
        )
        pipeline = IngestionPipeline(
            transformations=[self.base_parser],
            docstore=SimpleDocumentStore(),
        )
        nodes = pipeline.run(documents=[split_doc], show_progress=show_progress)
        return nodes

    def _run_safety_splitting(self, nodes: List[BaseNode], show_progress: bool) -> List[BaseNode]:
        safety_splitter = SentenceSplitter(
            chunk_size=SEMANTIC_SPLITTER_MAX_CHUNK,
            chunk_overlap=200,
        )
        pipeline = IngestionPipeline(
            transformations=[safety_splitter],
            docstore=SimpleDocumentStore(),
        )
        result = pipeline.run(documents=nodes, show_progress=show_progress)
        return result

    def _apply_document_metadata(self, nodes: List[BaseNode], doc: LIDocument) -> None:
        for node in nodes:
            node.metadata.update(doc.metadata)
            node.excluded_embed_metadata_keys = list(doc.excluded_embed_metadata_keys)
            node.excluded_llm_metadata_keys = list(doc.excluded_llm_metadata_keys)

    def _handle_txt_files(self, nodes: List[BaseNode], doc: LIDocument) -> None:
        filename = doc.metadata.get("filename", "")
        file_path = doc.metadata.get("file_path", "")
        if filename.lower().endswith(".txt") or file_path.lower().endswith(".txt"):
            for node in nodes:
                if "description" in node.excluded_llm_metadata_keys:
                    node.excluded_llm_metadata_keys.remove("description")

    def _run_metadata_extraction(self, nodes: List[BaseNode], show_progress: bool) -> List[BaseNode]:
        if not self.enable_metadata or not self.extractors:
            return nodes
        pipeline = IngestionPipeline(
            transformations=self.extractors,  # type: ignore[arg-type]
            docstore=SimpleDocumentStore(),
        )
        return pipeline.run(nodes=nodes, show_progress=show_progress)

    def _normalize_nodes(self, nodes: List[BaseNode]) -> List[BaseNode]:
        normalized = []
        for idx, node in enumerate(nodes):
            doc_id = _derive_doc_id(node)
            chunk_id = build_chunk_id(doc_id, idx)
            meta = dict(node.metadata or {})
            meta["doc_id"] = doc_id
            meta["chunk_index"] = idx
            meta["chunk_id"] = chunk_id
            node.metadata = sanitize_metadata(meta, include_text=False)
            node.id_ = chunk_id or str(idx)
            normalized.append(node)
        return normalized

    def build_nodes_from_documents(
        self,
        documents: List[LIDocument],
        *,
        show_progress: bool = False,
    ) -> List[BaseNode]:
        all_nodes: List[BaseNode] = []

        for doc in documents:
            semantic_nodes = self._run_semantic_splitting(doc, show_progress)
            nodes = self._run_safety_splitting(semantic_nodes, show_progress)
            self._apply_document_metadata(nodes, doc)
            self._handle_txt_files(nodes, doc)

            if self.enable_contextual:
                nodes = [self._add_context(node, doc.get_content(), doc.metadata) for node in tqdm(nodes, desc="Generating contextual summaries")]

            nodes = self._run_metadata_extraction(nodes, show_progress)
            normalized_nodes = self._normalize_nodes(nodes)
            all_nodes.extend(normalized_nodes)

        return all_nodes

    def build_nodes_from_text(self, text: str, metadata: dict) -> List[BaseNode]:
        li_doc = LIDocument(text=text, metadata=metadata)
        li_doc.excluded_embed_metadata_keys.extend(EXCLUDED_METADATA_KEYS)
        li_doc.excluded_llm_metadata_keys.extend(EXCLUDED_METADATA_KEYS)
        return self.build_nodes_from_documents([li_doc], show_progress=True)


def build_nodes_from_text(text: str, metadata: dict) -> List[BaseNode]:
    parser = ContextualNodeParser(
        enable_contextual_retrieval=ENABLE_CONTEXTUAL_RETRIEVAL,
        enable_metadata_extraction=ENABLE_METADATA_EXTRACTION,
    )
    return parser.build_nodes_from_text(text, metadata)

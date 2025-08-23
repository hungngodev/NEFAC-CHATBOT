# Requires: pip install tokenizers
import re
from typing import List, Literal, Optional

import numpy as np
from langchain.prompts import ChatPromptTemplate
from langchain.text_splitter import TextSplitter
from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from tqdm import tqdm

from src.service.ingestion_service.settings import embedding_model, llm_model


# Fallback: whitespace token count (for demonstration, replace with a real tokenizer for production)
def count_tokens(text: str) -> int:
    return len(text.split())


# Context prompt template for chunk contextualization
context_prompt_template = ChatPromptTemplate.from_template(
    """<document>\n{document}\n</document>\nHere is the chunk we want to situate within the whole document\n<chunk>\n{chunk}\n</chunk>\nPlease generate a short succinct context summary to situate this text chunk within the overall document to enhance search retrieval, two or three sentences max. The chunk contains merged content from different document sections, so focus on the main topics and concepts rather than sequential flow. Answer only with the succinct context and nothing else."""
)


class SemanticDoublePassMergingSplitterWithContext(TextSplitter):
    def __init__(
        self,
        buffer_size: int = 1,
        breakpoint_threshold_type: Literal["percentile", "standard_deviation", "interquartile", "gradient"] = "percentile",
        breakpoint_threshold_amount: Optional[float] = None,
        number_of_chunks: Optional[int] = None,
        min_chunk_size: Optional[int] = 100,
        max_chunk_size: Optional[int] = 2000,
        second_pass_threshold: float = 0.8,
        **kwargs,
    ):
        min_chunk_size = int(min_chunk_size) if min_chunk_size is not None else 100
        max_chunk_size = int(max_chunk_size) if max_chunk_size is not None else 2000
        super().__init__(chunk_size=max_chunk_size, chunk_overlap=0)
        self.embeddings = embedding_model
        self.chat_model = llm_model
        self.buffer_size = buffer_size
        self.breakpoint_threshold_type = breakpoint_threshold_type
        self.breakpoint_threshold_amount = breakpoint_threshold_amount
        self.number_of_chunks = number_of_chunks
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.second_pass_threshold = second_pass_threshold
        # Use LangChain's SemanticChunker for the first pass
        self.semantic_chunker = SemanticChunker(
            embeddings=self.embeddings,
            breakpoint_threshold_type=breakpoint_threshold_type,
            breakpoint_threshold_amount=breakpoint_threshold_amount,
            number_of_chunks=number_of_chunks,
            min_chunk_size=min_chunk_size,
        )

    def split_text(self, text: str, metadata: Optional[dict] = None) -> List[Document]:
        if not text or text.strip() == "":
            return []
        # First pass: use LangChain's SemanticChunker
        tqdm.write("[Splitter] Starting first pass: semantic chunking...")
        docs = self.semantic_chunker.create_documents([text])
        chunks = [
            doc.page_content
            for doc in tqdm(
                docs,
                desc="First pass: semantic chunks",
                dynamic_ncols=True,
                colour="yellow",
            )
        ]
        # Second pass: merge highly similar adjacent chunks
        tqdm.write("[Splitter] Starting second pass: merging similar chunks...")
        merged_chunks = self._second_pass_merge(
            list(
                tqdm(
                    chunks,
                    desc="Second pass: merging",
                    dynamic_ncols=True,
                    colour="green",
                )
            )
        )
        # Apply size constraints
        tqdm.write("[Splitter] Applying size constraints...")
        merged_chunks = self._apply_size_constraints(
            list(
                tqdm(
                    merged_chunks,
                    desc="Applying size constraints",
                    dynamic_ncols=True,
                    colour="blue",
                )
            )
        )
        # Contextualize and return as Document objects
        tqdm.write("[Splitter] Contextualizing chunks...")
        # Prefer whole-document text for context if provided in metadata
        doc_text_for_context = (metadata.get("__whole_document") if isinstance(metadata, dict) else None) or text
        return [
            self.contextualize_chunk(doc_text_for_context, chunk, metadata)
            for chunk in tqdm(
                merged_chunks,
                desc="Contextualizing",
                dynamic_ncols=True,
                colour="magenta",
            )
        ]

    def contextualize_chunk(
        self,
        whole_document: str,
        chunk: str,
        metadata: Optional[dict],
    ) -> Document:
        """Contextualize a chunk within the whole document using LLM."""
        prompt = context_prompt_template.format(document=whole_document, chunk=chunk)
        response = self.chat_model.invoke(prompt)
        context = response if isinstance(response, str) else response.content
        meta = dict(metadata) if metadata else {}
        meta["context"] = context
        return Document(page_content=chunk, metadata=meta)

    def _second_pass_merge(self, chunks: List[str]) -> List[str]:
        if len(chunks) <= 1:
            return chunks
        merged_chunks = []
        i = 0
        while i < len(chunks):
            # Try to merge with next chunk if similar
            if i < len(chunks) - 1:
                # Recompute embedding for merged chunk if needed
                sim_next = 1 - self._cosine_distance(
                    self.embeddings.embed_documents([chunks[i]])[0],
                    self.embeddings.embed_documents([chunks[i + 1]])[0],
                )
                combined_next = chunks[i] + " " + chunks[i + 1]
                if sim_next >= self.second_pass_threshold and count_tokens(combined_next) <= self.max_chunk_size:
                    # Look ahead to chunk[i+2] for triple merge
                    if i < len(chunks) - 2:
                        triple = combined_next + " " + chunks[i + 2]
                        # Recompute embedding for triple merge
                        sim_next2 = 1 - self._cosine_distance(
                            self.embeddings.embed_documents([combined_next])[0],
                            self.embeddings.embed_documents([chunks[i + 2]])[0],
                        )
                        if sim_next2 >= self.second_pass_threshold and count_tokens(triple) <= self.max_chunk_size:
                            merged_chunks.append(triple)
                            i += 3
                            continue
                    # Only merge two
                    merged_chunks.append(combined_next)
                    i += 2
                    continue
            merged_chunks.append(chunks[i])
            i += 1
        return merged_chunks

    def _cosine_distance(self, v1, v2):
        v1, v2 = np.array(v1), np.array(v2)
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 1.0
        similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return 1 - np.clip(similarity, -1, 1)

    def _apply_size_constraints(self, chunks: List[str]) -> List[str]:
        if not self.min_chunk_size and not self.max_chunk_size:
            return chunks
        constrained, buffer = [], ""
        for chunk in chunks:
            tokens = count_tokens(chunk)
            if self.max_chunk_size and tokens > self.max_chunk_size:
                # Split large chunk by sentences, then by words if needed
                sentences = re.split(r"(?<=[.?!])\s+", chunk)
                for sentence in sentences:
                    sentence_tokens = count_tokens(sentence)
                    if sentence_tokens > self.max_chunk_size:
                        # Fallback: split by words
                        words = sentence.split()
                        temp = []
                        for word in words:
                            temp.append(word)
                            if count_tokens(" ".join(temp)) >= self.max_chunk_size:
                                constrained.append(" ".join(temp))
                                temp = []
                        if temp:
                            constrained.append(" ".join(temp))
                    else:
                        buffer = f"{buffer} {sentence}".strip() if buffer else sentence
                        if count_tokens(buffer) >= self.max_chunk_size:
                            constrained.append(buffer)
                            buffer = ""
                continue
            elif self.min_chunk_size and tokens < self.min_chunk_size:
                buffer = f"{buffer} {chunk}".strip() if buffer else chunk
                if count_tokens(buffer) >= self.min_chunk_size:
                    constrained.append(buffer)
                    buffer = ""
            else:
                if buffer:
                    merged = f"{buffer} {chunk}".strip()
                    if count_tokens(merged) <= self.max_chunk_size:
                        constrained.append(merged)
                        buffer = ""
                    else:
                        constrained.append(buffer)
                        constrained.append(chunk)
                        buffer = ""
                else:
                    constrained.append(chunk)
        # Final buffer handling
        if buffer:
            if count_tokens(buffer) <= self.max_chunk_size:
                constrained.append(buffer)
            else:
                # Split buffer if too large
                words = buffer.split()
                temp = []
                for word in words:
                    temp.append(word)
                    if count_tokens(" ".join(temp)) >= self.max_chunk_size:
                        constrained.append(" ".join(temp))
                        temp = []
                if temp:
                    constrained.append(" ".join(temp))
        return constrained

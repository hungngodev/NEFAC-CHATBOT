import re
import numpy as np
from typing import List, Optional, Literal
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.base import BaseLanguageModel
from langchain.text_splitter import TextSplitter
from langchain.prompts import BasePromptTemplate


class SemanticDoublePassMergingSplitterWithContext(TextSplitter):
    def __init__(
        self,
        embeddings: Embeddings,
        chat_model: BaseLanguageModel,
        context_prompt_template: BasePromptTemplate,
        buffer_size: int = 1,
        breakpoint_threshold_type: Literal[
            "percentile", "standard_deviation", "interquartile", "gradient"
        ] = "percentile",
        breakpoint_threshold_amount: Optional[float] = None,
        number_of_chunks: Optional[int] = None,
        sentence_split_regex: str = r"(?<=[.?!])\s+",
        min_chunk_size: Optional[int] = 100,
        max_chunk_size: Optional[int] = 2000,
        second_pass_threshold: float = 0.8,
        include_labels: bool = False,
        **kwargs,
    ):
        super().__init__(chunk_size=max_chunk_size or 2000, chunk_overlap=0)
        self.embeddings = embeddings
        self.chat_model = chat_model
        self.context_prompt_template = context_prompt_template
        self.buffer_size = buffer_size
        self.breakpoint_threshold_type = breakpoint_threshold_type
        self.breakpoint_threshold_amount = breakpoint_threshold_amount
        self.number_of_chunks = number_of_chunks
        self.sentence_split_regex = re.compile(sentence_split_regex)
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.second_pass_threshold = second_pass_threshold
        self.include_labels = include_labels

    def split_text(self, text: str, metadata: Optional[dict] = None) -> List[Document]:
        """
        Splits the input text into contextualized Document chunks.
        """
        if not text or text.strip() == "":
            return []

        sentences = self._split_text_into_sentences(text)
        if not sentences:
            return []

        if len(sentences) == 1:
            single = sentences[0].strip()
            if not single:
                return []
            if self.max_chunk_size and len(single) > self.max_chunk_size:
                # Split by words if too long
                words = single.split()
                chunks, current = [], ""
                for word in words:
                    if len(current) + len(word) + 1 <= self.max_chunk_size:
                        current = f"{current} {word}".strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = word
                if current:
                    chunks.append(current)
                return [
                    self._contextualized_document(text, chunk, metadata)
                    for chunk in chunks
                ]
            return [self._contextualized_document(text, single, metadata)]

        # Combine sentences for embedding
        combined_sentences = self._combine_sentences(sentences)
        embeddings = self.embeddings.embed_documents(combined_sentences)
        distances = self._calculate_distances(embeddings)

        if not distances:
            return [
                self._contextualized_document(text, s.strip(), metadata)
                for s in sentences
                if s.strip()
            ]

        breakpoints = self._calculate_breakpoints(distances)
        chunks = self._create_chunks(sentences, breakpoints)
        chunks = self._second_pass_merge(chunks)
        chunks = self._apply_size_constraints(chunks)
        return [
            self._contextualized_document(text, chunk, metadata) for chunk in chunks
        ]

    def split_documents(self, documents: List[Document]) -> List[Document]:
        split_docs = []
        for doc in documents:
            split_docs.extend(self.split_text(doc.page_content, metadata=doc.metadata))
        return split_docs

    def _split_text_into_sentences(self, text: str) -> List[str]:
        return [s.strip() for s in self.sentence_split_regex.split(text) if s.strip()]

    def _combine_sentences(self, sentences: List[str]) -> List[str]:
        combined = []
        buffer_size = min(self.buffer_size, len(sentences))
        for i in range(len(sentences)):
            start = max(0, i - buffer_size)
            end = min(len(sentences), i + buffer_size + 1)
            combined.append(" ".join(sentences[start:end]))
        return combined

    def _calculate_distances(self, embeddings: List[List[float]]) -> List[float]:
        distances = []
        for i in range(len(embeddings) - 1):
            distances.append(self._cosine_distance(embeddings[i], embeddings[i + 1]))
        return distances

    def _cosine_distance(self, v1, v2):
        v1, v2 = np.array(v1), np.array(v2)
        if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
            return 1.0
        similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return 1 - np.clip(similarity, -1, 1)

    def _calculate_breakpoints(self, distances: List[float]) -> List[int]:
        if not distances:
            return []
        if self.number_of_chunks:
            sorted_dist = sorted(distances, reverse=True)
            idx = min(self.number_of_chunks - 1, len(sorted_dist) - 1)
            threshold = sorted_dist[idx]
        elif self.breakpoint_threshold_amount is not None:
            threshold = self.breakpoint_threshold_amount
        else:
            if self.breakpoint_threshold_type == "percentile":
                percentile = 0.95
                sorted_dist = sorted(distances)
                idx = int(len(sorted_dist) * percentile)
                threshold = sorted_dist[min(int(idx), len(sorted_dist) - 1)]
            elif self.breakpoint_threshold_type == "standard_deviation":
                mean = np.mean(distances)
                std = np.std(distances)
                threshold = mean + std
            elif self.breakpoint_threshold_type == "interquartile":
                q1 = np.percentile(distances, 25)
                q3 = np.percentile(distances, 75)
                iqr = q3 - q1
                threshold = q3 + 1.5 * iqr
            elif self.breakpoint_threshold_type == "gradient":
                gradients = [
                    abs(distances[i] - distances[i - 1])
                    for i in range(1, len(distances))
                ]
                if gradients:
                    max_grad_idx = int(np.argmax(gradients))
                    threshold = distances[min(max_grad_idx + 1, len(distances) - 1)]
                else:
                    threshold = 0.5
            else:
                threshold = 0.5
        breakpoints = [i + 1 for i, d in enumerate(distances) if d > threshold]
        return breakpoints

    def _create_chunks(self, sentences: List[str], breakpoints: List[int]) -> List[str]:
        chunks, start = [], 0
        for bp in breakpoints:
            chunk = " ".join(sentences[start:bp]).strip()
            if chunk:
                chunks.append(chunk)
            start = bp
        if start < len(sentences):
            chunk = " ".join(sentences[start:]).strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    def _second_pass_merge(self, chunks: List[str]) -> List[str]:
        if len(chunks) <= 1:
            return chunks
        chunk_embeddings = self.embeddings.embed_documents(chunks)
        merged_chunks = []
        i = 0
        while i < len(chunks):
            if i < len(chunks) - 1:
                sim = 1 - self._cosine_distance(
                    chunk_embeddings[i], chunk_embeddings[i + 1]
                )
                if sim >= self.second_pass_threshold and len(
                    chunks[i] + " " + chunks[i + 1]
                ) <= (self.max_chunk_size or 2000):
                    merged_chunks.append(chunks[i] + " " + chunks[i + 1])
                    i += 2
                    continue
            merged_chunks.append(chunks[i])
            i += 1
        return merged_chunks

    def _apply_size_constraints(self, chunks: List[str]) -> List[str]:
        if not self.min_chunk_size and not self.max_chunk_size:
            return chunks
        constrained, buffer = [], ""
        for chunk in chunks:
            if self.max_chunk_size and len(chunk) > self.max_chunk_size:
                # Split large chunk by sentences
                sentences = self._split_text_into_sentences(chunk)
                temp = ""
                for sentence in sentences:
                    if len(temp) + len(sentence) + 1 <= self.max_chunk_size:
                        temp = f"{temp} {sentence}".strip()
                    else:
                        if temp and (
                            not self.min_chunk_size or len(temp) >= self.min_chunk_size
                        ):
                            constrained.append(temp)
                            temp = sentence
                        else:
                            if buffer:
                                buffer = f"{buffer} {temp} {sentence}".strip()
                            else:
                                temp = f"{temp} {sentence}".strip()
                if temp:
                    if not self.min_chunk_size or len(temp) >= self.min_chunk_size:
                        constrained.append(temp)
                    else:
                        buffer = f"{buffer} {temp}".strip()
            elif self.min_chunk_size and len(chunk) < self.min_chunk_size:
                buffer = f"{buffer} {chunk}".strip()
                if len(buffer) >= self.min_chunk_size:
                    constrained.append(buffer)
                    buffer = ""
            else:
                if buffer:
                    if not self.min_chunk_size or len(buffer) >= self.min_chunk_size:
                        constrained.append(buffer)
                        buffer = ""
                        constrained.append(chunk)
                    else:
                        buffer = f"{buffer} {chunk}".strip()
                        if len(buffer) >= self.min_chunk_size:
                            constrained.append(buffer)
                            buffer = ""
                else:
                    constrained.append(chunk)
        if buffer:
            if not self.min_chunk_size or len(buffer) >= self.min_chunk_size:
                constrained.append(buffer)
            else:
                if constrained:
                    last = constrained.pop()
                    constrained.append(f"{last} {buffer}".strip())
                else:
                    constrained.append(buffer)
        return constrained

    def _contextualized_document(
        self, whole_document: str, chunk: str, metadata: Optional[dict]
    ) -> Document:
        prompt = self.context_prompt_template.format(
            document=whole_document, chunk=chunk
        )
        response = self.chat_model.invoke(prompt)
        context = response if isinstance(response, str) else response.content
        if self.include_labels:
            content = f"Context: {context}\n\nChunk: {chunk}"
        else:
            content = f"{context}\n\n{chunk}"
        return Document(page_content=content, metadata=metadata or {})

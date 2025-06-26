import os
import json
from tqdm import tqdm
from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    SpacyTextSplitter,
)
from langchain_experimental.text_splitter import SemanticChunker
from service.schemas.metadata import PDFChunkMetadata
from service.ingestion_service.settings import CHUNK_SIZE, CHUNK_OVERLAP

# Free embedding fallback
try:
    from langchain_community.embeddings import HuggingFaceEmbeddings

    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    print("✓ HuggingFace embeddings model ready")
except ImportError as e:
    embedding_model = None
    print(f"Warning: HuggingFace embeddings unavailable: {e}")


def analyze_document_type(title: str, sample_text: str) -> str:
    title_lower = title.lower()
    content_lower = sample_text.lower()
    legal_kws = [
        "brief",
        "amicus",
        "testimony",
        "complaint",
        "motion",
        "order",
        "ruling",
        "statute",
        "regulation",
        "court",
        "legal",
        "attorney",
        "judge",
        "defendant",
    ]
    report_kws = [
        "report",
        "study",
        "analysis",
        "investigation",
        "audit",
        "review",
        "assessment",
        "evaluation",
        "findings",
        "recommendations",
    ]
    academic_kws = [
        "research",
        "paper",
        "thesis",
        "dissertation",
        "journal",
        "article",
        "academic",
        "scholarly",
        "peer-reviewed",
        "methodology",
        "literature",
    ]
    scores = {
        "legal": sum(k in content_lower or k in title_lower for k in legal_kws),
        "report": sum(k in content_lower or k in title_lower for k in report_kws),
        "academic": sum(k in content_lower or k in title_lower for k in academic_kws),
    }
    best = max(scores.items(), key=lambda x: x[1])[0]
    return best if scores[best] > 0 else "general"


def analyze_text_features(text: str) -> dict:
    num_sentences = text.count(".") + text.count("!") + text.count("?")
    avg_len = len(text.split()) / (num_sentences or 1)
    has_bullets = any(b in text for b in ["•", "-", "*"])
    num_headings = sum(
        1
        for line in text.split("\n")
        if line.strip().isupper() and len(line.strip()) > 5
    )
    num_words = len(text.split())
    repetitiveness = max((text.count(w) for w in set(text.split())), default=0) / (
        num_words or 1
    )
    has_tables = "|" in text or "\t" in text
    return {
        "avg_sentence_length": avg_len,
        "has_bullets": has_bullets,
        "num_headings": num_headings,
        "num_words": num_words,
        "repetitiveness": repetitiveness,
        "has_tables": has_tables,
    }


def choose_chunker(text: str, doc_type: str, embedding_model=None):
    features = analyze_text_features(text)
    # Highly structured
    if (
        features["has_tables"]
        or features["has_bullets"]
        or features["num_headings"] > 3
    ):
        return SpacyTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    # Dense academic/legal and embeddings available
    if (
        embedding_model
        and features["avg_sentence_length"] > 22
        and not features["has_bullets"]
        and doc_type in ("academic", "legal")
    ):
        return SemanticChunker(embedding_model)
    # Very long docs
    if features["num_words"] > 2000 and features["repetitiveness"] < 0.05:
        return RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
    # Default
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )


def pdf_loader(metadata_json_path: str, documents_dir: str) -> list[Document]:
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    all_docs: list[Document] = []
    for entry in tqdm(entries, desc="Loading PDFs"):
        fn = entry.get("filename")
        if not fn:
            continue
        path = os.path.join(documents_dir, fn)
        if not os.path.exists(path):
            print(f"Missing PDF: {path}")
            continue
        loader = PyPDFLoader(path)
        pages = loader.load_and_split()
        title = entry.get("title", fn.rsplit(".pdf", 1)[0])
        sample_text = " ".join(p.page_content for p in pages[:2])
        doc_type = analyze_document_type(title, sample_text)
        for i, page in enumerate(pages):
            splitter = choose_chunker(page.page_content, doc_type, embedding_model)
            chunks = splitter.split_text(page.page_content)
            strat = splitter.__class__.__name__
            for j, chunk in enumerate(chunks):
                meta = dict(entry)
                chunk_meta = {
                    "page_number": i + 1,
                    "total_pages": len(pages),
                    "chunk_index": j,
                    "total_chunks_in_page": len(chunks),
                    "chunking_strategy": strat,
                    "provenance": {
                        "type": "pdf_chunk",
                        "page": i + 1,
                        "chunk_index": j,
                        "chunking_strategy": strat,
                    },
                }
                # Validate chunk metadata
                PDFChunkMetadata(**{**meta, **chunk_meta})
                meta.update(chunk_meta)
                all_docs.append(Document(page_content=chunk, metadata=meta))
    return all_docs

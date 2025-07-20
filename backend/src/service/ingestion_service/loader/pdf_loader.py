import json
import logging
import os
import time
from typing import Any, List

from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.runnables import RunnableLambda
from tqdm import tqdm

from backend.src.schemas.state import PDFChunkMetadata
from src.service.ingestion_service.loader.semantic_double_pass_splitter import (
    SemanticDoublePassMergingSplitterWithContext,
)
from src.service.ingestion_service.settings import CHUNK_SIZE, CONTEXT_FORMAT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf_loader_pipeline")


def load_pdf_entries(metadata_json_path) -> List[Document]:
    logger.info(f"[PDF Loader] Loading metadata entries from {metadata_json_path}")
    tqdm.write(f"[PDF Loader] Loading metadata entries from {metadata_json_path}")
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    logger.info(f"[PDF Loader] Loaded {len(entries)} metadata entries.")
    tqdm.write(f"[PDF Loader] Loaded {len(entries)} metadata entries.")
    return entries


def find_valid_pdf_path(documents_dir: str, entry: dict) -> str:
    """
    Check if the entry has a valid PDF filename and if the file exists in a subfolder.
    Returns the full path if valid, else an empty string.
    """
    filename = entry.get("filename") or entry.get("file_name") or entry.get("file")
    if not (filename and filename.lower().endswith(".pdf")):
        return ""
    for subfolder in os.listdir(documents_dir):
        subfolder_path = os.path.join(documents_dir, subfolder)
        if os.path.isdir(subfolder_path):
            file_path = os.path.join(subfolder_path, filename)
            if os.path.exists(file_path):
                return file_path
    return ""


def get_page_offsets(pages) -> Any:
    """
    Given a list of page objects with .page_content, return a list of (start, end) offsets for each page in the concatenated document.
    """
    offsets = []
    curr = 0
    for page in pages:
        start = curr
        end = curr + len(page.page_content)
        offsets.append((start, end))
        curr = end
    return offsets


def find_pages_for_chunk(chunk_start, chunk_end, page_offsets) -> Any:
    """
    Given chunk start/end offsets and a list of (start, end) for each page, return the list of page numbers (1-based) the chunk overlaps with.
    """
    pages = []
    for i, (p_start, p_end) in enumerate(page_offsets):
        # If chunk overlaps with this page
        if chunk_start < p_end and chunk_end > p_start:
            pages.append(i + 1)
    return pages


def get_chunk_page_positions(chunk_start, chunk_end, page_offsets) -> Any:
    """
    For each page overlapped by the chunk, return a dict with page number, start_pct, end_pct, and a qualitative label.
    """
    positions = []
    for i, (p_start, p_end) in enumerate(page_offsets):
        overlap_start = max(chunk_start, p_start)
        overlap_end = min(chunk_end, p_end)
        if overlap_start < overlap_end:
            page_len = p_end - p_start
            rel_start = (overlap_start - p_start) / page_len
            rel_end = (overlap_end - p_start) / page_len
            # Clamp to [0, 1]
            rel_start = max(0.0, min(1.0, rel_start))
            rel_end = max(0.0, min(1.0, rel_end))
            # Assign qualitative label
            span = rel_end - rel_start
            if span >= 0.95:
                label = "full"
            elif rel_start <= 0.15 and rel_end <= 0.5:
                label = "top"
            elif rel_start >= 0.5 and rel_end >= 0.85:
                label = "bottom"
            elif rel_start > 0.15 and rel_end < 0.85:
                label = "middle"
            else:
                label = "partial"
            positions.append(
                {
                    "page": i + 1,
                    "start_pct": round(rel_start, 3),
                    "end_pct": round(rel_end, 3),
                    "position": label,
                }
            )
    return positions


def parse_pdf(entry, documents_dir) -> Any:
    filename = entry.get("filename") or entry.get("file_name") or entry.get("file")
    logger.info(f"[PDF Loader] Parsing entry: {filename}")
    tqdm.write(f"[PDF Loader] Parsing entry: {filename}")
    path = find_valid_pdf_path(documents_dir, entry)
    if not path:
        logger.warning(f"[PDF Loader] File not found for entry: {filename}")
        tqdm.write(f"[PDF Loader] File not found for entry: {filename}")
        return None
    loader = PyPDFLoader(path)
    pages = loader.load()
    logger.info(f"[PDF Loader] Loaded {len(pages)} pages for {filename}")
    tqdm.write(f"[PDF Loader] Loaded {len(pages)} pages for {filename}")
    total_pages = len(pages)
    page_offsets = get_page_offsets(pages)
    full_text = "".join([p.page_content for p in tqdm(pages, desc=f"Concatenating pages for {filename}", dynamic_ncols=True)])
    return {
        "entry": entry,
        "pages": pages,
        "total_pages": total_pages,
        "page_offsets": page_offsets,
        "full_text": full_text,
        "filename": filename,
    }


def chunk_and_contextualize_pdf(pdf_data, splitter) -> Any:
    entry = pdf_data["entry"]
    full_text = pdf_data["full_text"]
    page_offsets = pdf_data["page_offsets"]
    total_pages = pdf_data["total_pages"]
    filename = pdf_data["filename"]
    logger.info(f"[PDF Loader] Chunking and contextualizing {filename}")
    tqdm.write(f"[PDF Loader] Chunking and contextualizing {filename}")
    chunks = splitter.split_text(full_text, metadata=entry)
    curr_offset = 0
    chunked_docs = []
    for j, chunk_doc in enumerate(tqdm(chunks, desc=f"Chunking {filename}", dynamic_ncols=True, colour="magenta")):
        chunk_text = chunk_doc.page_content
        chunk_len = len(chunk_text)
        chunk_start = full_text.find(chunk_text, curr_offset)
        if chunk_start == -1:
            chunk_start = curr_offset
        chunk_end = chunk_start + chunk_len
        curr_offset = chunk_end
        pages_covered = find_pages_for_chunk(chunk_start, chunk_end, page_offsets)
        pages_info = get_chunk_page_positions(chunk_start, chunk_end, page_offsets)
        chunk_meta = dict(chunk_doc.metadata)
        chunk_meta.update(
            {
                "chunk_index": j,
                "total_chunks_in_document": len(chunks),
                "pages": pages_covered,
                "pages_info": pages_info,
                "total_pages": total_pages,
                "chunking_strategy": splitter.__class__.__name__,
                "filename": filename,
            }
        )
        context = chunk_meta.pop("context", None)
        formatted_content = CONTEXT_FORMAT.format(context=context or "", chunk=chunk_text)
        try:
            PDFChunkMetadata(**chunk_meta)
            logger.info(f"[PDF Loader] Validated chunk {j+1}/{len(chunks)} for {filename}")
            tqdm.write(f"[PDF Loader] Validated chunk {j+1}/{len(chunks)} for {filename}")
        except Exception as e:
            logger.error(f"[PDF Loader] Metadata validation failed for chunk {j} in {filename}: {e}")
            tqdm.write(f"[ERROR] Metadata validation failed for chunk {j} in {filename}: {e}")
            continue
        chunked_docs.append(Document(page_content=formatted_content, metadata=chunk_meta))
    logger.info(f"[PDF Loader] Finished chunking {filename}. Total chunks: {len(chunked_docs)}")
    tqdm.write(f"[PDF Loader] Finished chunking {filename}. Total chunks: {len(chunked_docs)}")
    return chunked_docs


def count_tokens_in_docs(docs) -> Any:
    return sum(len(doc.page_content.split()) for doc in docs)


def ensure_list_of_documents(docs) -> list[Document]:
    if isinstance(docs, list):
        return [d for d in docs if isinstance(d, Document)]
    elif isinstance(docs, Document):
        return [docs]
    else:
        return []


def pdf_loader(metadata_json_path, documents_dir) -> list[Document]:
    splitter = SemanticDoublePassMergingSplitterWithContext(
        max_chunk_size=CHUNK_SIZE,
        min_chunk_size=100,
    )
    start_time = time.time()
    logger.info(f"[PDF Loader] Starting pipeline for {metadata_json_path}")
    tqdm.write(f"[PDF Loader] Starting pipeline for {metadata_json_path}")

    def parse_all(entries):
        parsed = []
        for e in tqdm(entries, desc="Parsing PDF entries", dynamic_ncols=True):
            result = parse_pdf(e, documents_dir)
            if result is not None:
                parsed.append(result)
        logger.info(f"[PDF Loader] Finished parsing {len(parsed)} PDF entries.")
        tqdm.write(f"[PDF Loader] Finished parsing {len(parsed)} PDF entries.")
        return parsed

    pipeline = (
        RunnableLambda(lambda _: load_pdf_entries(metadata_json_path))
        | RunnableLambda(parse_all)
        | RunnableLambda(lambda pdf_datas: [doc for pdf_data in (pdf_datas if isinstance(pdf_datas, list) else ([pdf_datas] if isinstance(pdf_datas, dict) else [])) for doc in chunk_and_contextualize_pdf(pdf_data, splitter)])
    )
    docs = pipeline.invoke({})
    docs = ensure_list_of_documents(docs)
    total_tokens = count_tokens_in_docs(docs)
    elapsed = time.time() - start_time
    logger.info(f"[PDF Loader] Processed {len(docs)} chunks, {total_tokens} tokens in {elapsed:.2f} seconds.")
    tqdm.write(f"[PDF Loader] Processed {len(docs)} chunks, {total_tokens} tokens in {elapsed:.2f} seconds.")
    return docs

import os
import json
from tqdm import tqdm
from langchain.docstore.document import Document
from langchain_community.document_loaders import PyPDFLoader
from service.schemas.metadata import PDFChunkMetadata
from service.ingestion_service.settings import CHUNK_SIZE, CONTEXT_FORMAT
from service.ingestion_service.loader.semantic_double_pass_splitter import (
    SemanticDoublePassMergingSplitterWithContext,
)
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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


def get_page_offsets(pages):
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


def find_pages_for_chunk(chunk_start, chunk_end, page_offsets):
    """
    Given chunk start/end offsets and a list of (start, end) for each page, return the list of page numbers (1-based) the chunk overlaps with.
    """
    pages = []
    for i, (p_start, p_end) in enumerate(page_offsets):
        # If chunk overlaps with this page
        if chunk_start < p_end and chunk_end > p_start:
            pages.append(i + 1)
    return pages


def get_chunk_page_positions(chunk_start, chunk_end, page_offsets):
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


def pdf_loader(metadata_json_path: str, documents_dir: str) -> list[Document]:
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    all_docs: list[Document] = []
    chunking_strategy = "SemanticDoublePassMergingSplitterWithContext"
    splitter = SemanticDoublePassMergingSplitterWithContext(
        max_chunk_size=CHUNK_SIZE,
        min_chunk_size=100,
    )
    tqdm.write("Starting PDF loading...")
    for entry in tqdm(entries, desc="Loading PDFs", dynamic_ncols=True, colour="cyan"):
        fn = entry.get("filename")
        if not fn:
            tqdm.write(f"Skipping entry with missing filename: {entry}")
            continue
        path = find_valid_pdf_path(documents_dir, entry)
        if not path:
            tqdm.write(f"Skipping entry, file not found: {fn}")
            continue
        filename = entry.get("filename") or entry.get("file_name") or entry.get("file")
        loader = PyPDFLoader(path)
        pages = loader.load()
        total_pages = len(pages)
        page_offsets = get_page_offsets(pages)
        full_text = "".join([p.page_content for p in pages])
        # Chunk the full document
        tqdm.write(f"Chunking document: {filename} ({total_pages} pages)")
        chunks = splitter.split_text(full_text, metadata=entry)
        curr_offset = 0
        for j, chunk_doc in enumerate(
            tqdm(
                chunks,
                desc=f"Chunking {filename}",
                dynamic_ncols=True,
                colour="magenta",
            )
        ):
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
                    "chunking_strategy": chunking_strategy,
                    "provenance_type": "pdf_chunk",
                    "provenance_file": filename,
                }
            )
            context = chunk_meta.pop("context", None)
            formatted_content = CONTEXT_FORMAT.format(
                context=context or "", chunk=chunk_text
            )
            try:
                PDFChunkMetadata(**chunk_meta)
            except Exception as e:
                tqdm.write(
                    f"[ERROR] Metadata validation failed for chunk {j} in {filename}: {e}"
                )
                continue
            all_docs.append(
                Document(page_content=formatted_content, metadata=chunk_meta)
            )
            tqdm.write(f"Processed chunk {j+1}/{len(chunks)} for {filename}")
    tqdm.write("PDF loading complete.")
    return all_docs

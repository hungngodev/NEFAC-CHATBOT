import json
import logging
import os
import time
from typing import Any, List

from bs4 import BeautifulSoup, Tag
from langchain.docstore.document import Document
from langchain_core.runnables import RunnableLambda
from tqdm import tqdm

from src.schemas.metadata import ContentChunkMetadata
from src.service.ingestion_service.loader.semantic_double_pass_splitter import (
    SemanticDoublePassMergingSplitterWithContext,
)
from src.service.ingestion_service.settings import CHUNK_SIZE, CONTEXT_FORMAT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("html_loader_pipeline")


def load_html_entries(metadata_json_path) -> List[Document]:
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    return entries


def extract_html_sections(html: str) -> Any:
    """
    Extracts structured sections from HTML, returning a list of dicts with:
    - path: heading hierarchy
    - texts: list of text blocks in the section
    - anchors: list of anchor ids/names for each block
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    for img in soup.find_all("img"):
        if isinstance(img, Tag):
            alt = img.get("alt", "")
            img.replace_with(soup.new_string(str(alt)))
    content_tags = [
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "div",
        "section",
        "article",
        "li",
        "blockquote",
    ]
    sections = []
    current = {"path": [], "texts": [], "anchors": []}
    for elem in soup.find_all(content_tags):
        if not isinstance(elem, Tag):
            continue
        text = elem.get_text(separator=" ", strip=True)
        if not text or len(text.split()) < 3:
            continue
        tag = elem.name.lower()
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if current["texts"]:
                sections.append(current)
            level = int(tag[1])
            current = {
                "path": current["path"][: level - 1] + [text],
                "texts": [],
                "anchors": [],
            }
            continue
        anchor = elem.get("id") or elem.get("name") or None
        current["texts"].append(text)
        current["anchors"].append(anchor)
    if current["texts"]:
        sections.append(current)
    return sections


def find_chunk_offsets(section_text: str, chunk_text: str, start_search: int = 0) -> Any:
    """
    Find the start and end character offsets of chunk_text within section_text, starting from start_search.
    Returns (chunk_start, chunk_end).
    """
    chunk_start = section_text.find(chunk_text, start_search)
    if chunk_start == -1:
        chunk_start = start_search
    chunk_end = chunk_start + len(chunk_text)
    return chunk_start, chunk_end


def parse_html(entry, content_dir) -> Any:
    filename = entry.get("filename")
    if not filename:
        return None
    html_path = os.path.join(content_dir, filename)
    if not os.path.exists(html_path):
        return None
    with open(html_path, "r", encoding="utf-8") as fh:
        html = fh.read()
    title = entry.get("title", os.path.splitext(filename)[0])
    sections = extract_html_sections(html)
    return {
        "entry": entry,
        "sections": sections,
        "title": title,
        "filename": filename,
    }


def chunk_and_contextualize_html(html_data, splitter) -> Any:
    entry = html_data["entry"]
    sections = html_data["sections"]
    title = html_data["title"]
    filename = html_data["filename"]
    chunked_docs = []
    for sec_idx, sec in enumerate(sections):
        section_text = "\n\n".join(sec["texts"])
        if not section_text.strip():
            continue
        chunks = splitter.split_text(section_text, metadata=entry)
        curr_offset = 0
        for chunk_idx, chunk_doc in enumerate(
            tqdm(
                chunks,
                desc=f"Chunking section {sec_idx+1} in {filename}",
                dynamic_ncols=True,
                colour="magenta",
            )
        ):
            chunk_text = chunk_doc.page_content
            chunk_start, chunk_end = find_chunk_offsets(section_text, chunk_text, curr_offset)
            curr_offset = chunk_end
            anchor = sec["anchors"][0] if sec["anchors"] else None
            meta = dict(chunk_doc.metadata)
            meta.update(
                {
                    "source": title,
                    "type": "html",
                    "section_path": sec["path"],
                    "section_index": sec_idx,
                    "chunk_index": chunk_idx,
                    "total_chunks_in_section": len(chunks),
                    "chunking_strategy": splitter.__class__.__name__,
                    "anchor": anchor,
                    "html_url": (f"{entry.get('link','')}#{anchor}" if anchor else entry.get("link", "")),
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                }
            )
            if "featured_image" in meta:
                fi = meta["featured_image"]
                if isinstance(fi, dict):
                    meta["featured_image"] = fi.get("title") or fi.get("url") or str(fi)
                elif not (isinstance(fi, str) or fi is None):
                    meta["featured_image"] = None
            if "provenance" in meta:
                del meta["provenance"]
            ContentChunkMetadata.model_config = {"extra": "ignore"}
            try:
                ContentChunkMetadata(**meta)
            except Exception as e:
                tqdm.write(f"[ERROR] Metadata validation failed for chunk {chunk_idx} in {filename}: {e}")
                continue
            context = meta.pop("context", None)
            formatted_content = CONTEXT_FORMAT.format(context=context or "", chunk=chunk_text)
            chunked_docs.append(Document(page_content=formatted_content, metadata=meta))
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


def html_loader(metadata_json_path, content_dir) -> list[Document]:
    splitter = SemanticDoublePassMergingSplitterWithContext(
        max_chunk_size=CHUNK_SIZE,
        min_chunk_size=100,
    )
    start_time = time.time()
    logger.info(f"[HTML Loader] Loading entries from {metadata_json_path}")

    def parse_all(entries):
        parsed = []
        for e in tqdm(entries, desc="Parsing HTML entries"):
            result = parse_html(e, content_dir)
            if result is not None:
                parsed.append(result)
        return parsed

    pipeline = (
        RunnableLambda(lambda _: load_html_entries(metadata_json_path))
        | RunnableLambda(parse_all)
        | RunnableLambda(lambda html_datas: [doc for html_data in (html_datas if isinstance(html_datas, list) else ([html_datas] if isinstance(html_datas, dict) else [])) for doc in chunk_and_contextualize_html(html_data, splitter)])
    )
    docs = pipeline.invoke({})
    docs = ensure_list_of_documents(docs)
    total_tokens = count_tokens_in_docs(docs)
    elapsed = time.time() - start_time
    logger.info(f"[HTML Loader] Processed {len(docs)} chunks, {total_tokens} tokens in {elapsed:.2f} seconds.")
    tqdm.write(f"[HTML Loader] Processed {len(docs)} chunks, {total_tokens} tokens in {elapsed:.2f} seconds.")
    return docs

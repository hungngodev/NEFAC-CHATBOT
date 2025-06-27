import os
import json
from tqdm import tqdm
from bs4 import BeautifulSoup, Tag
from langchain.docstore.document import Document
from service.schemas.metadata import ContentChunkMetadata
from service.ingestion_service.settings import CHUNK_SIZE, CONTEXT_FORMAT
from service.ingestion_service.loader.semantic_double_pass_splitter import (
    SemanticDoublePassMergingSplitterWithContext,
)


def extract_html_sections(html: str):
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


def find_chunk_offsets(section_text: str, chunk_text: str, start_search: int = 0):
    """
    Find the start and end character offsets of chunk_text within section_text, starting from start_search.
    Returns (chunk_start, chunk_end).
    """
    chunk_start = section_text.find(chunk_text, start_search)
    if chunk_start == -1:
        chunk_start = start_search
    chunk_end = chunk_start + len(chunk_text)
    return chunk_start, chunk_end


def html_loader(metadata_json_path: str, content_dir: str) -> list[Document]:
    """
    HTML loader using semantic chunking and detailed provenance:
      - Strips boilerplate (scripts/styles/nav/footer/header/aside)
      - Converts <img> tags to their alt text
      - Builds a hierarchy using all headings (h1–h6)
      - Groups consecutive elements under each heading into sections
      - Chunks each section using semantic splitter
      - Records provenance (section path, chunk indices, anchors, html_url)
    """
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    all_docs: list[Document] = []
    chunking_strategy = "SemanticDoublePassMergingSplitterWithContext"
    splitter = SemanticDoublePassMergingSplitterWithContext(
        max_chunk_size=CHUNK_SIZE,
        min_chunk_size=100,
    )
    tqdm.write("Starting HTML loading...")
    for entry in tqdm(
        entries, desc="Loading HTML content", dynamic_ncols=True, colour="cyan"
    ):
        filename = entry.get("filename")
        if not filename:
            tqdm.write(f"Skipping entry with missing filename: {entry}")
            continue
        html_path = os.path.join(content_dir, filename)
        if not os.path.exists(html_path):
            tqdm.write(f"Missing HTML: {html_path}")
            continue
        with open(html_path, "r", encoding="utf-8") as fh:
            html = fh.read()
        title = entry.get("title", os.path.splitext(filename)[0])
        sections = extract_html_sections(html)
        for sec_idx, sec in enumerate(sections):
            section_text = "\n\n".join(sec["texts"])
            if not section_text.strip():
                continue
            tqdm.write(f"Chunking section {sec_idx+1}/{len(sections)} in {filename}")
            chunks = splitter.split_text(section_text, metadata=entry)
            curr_offset = 0
            for chunk_idx, chunk_doc in enumerate(
                tqdm(
                    chunks,
                    desc=f"Chunking section {sec_idx+1}",
                    dynamic_ncols=True,
                    colour="magenta",
                )
            ):
                chunk_text = chunk_doc.page_content
                chunk_start, chunk_end = find_chunk_offsets(
                    section_text, chunk_text, curr_offset
                )
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
                        "chunking_strategy": chunking_strategy,
                        "anchor": anchor,
                        "html_url": (
                            f"{entry.get('link','')}#{anchor}"
                            if anchor
                            else entry.get("link", "")
                        ),
                        "chunk_start": chunk_start,
                        "chunk_end": chunk_end,
                    }
                )
                # Coerce featured_image to string if needed
                if "featured_image" in meta:
                    fi = meta["featured_image"]
                    if isinstance(fi, dict):
                        meta["featured_image"] = (
                            fi.get("title") or fi.get("url") or str(fi)
                        )
                    elif not (isinstance(fi, str) or fi is None):
                        meta["featured_image"] = None
                # Remove unused fields if present
                if "provenance" in meta:
                    del meta["provenance"]
                ContentChunkMetadata.model_config = {"extra": "ignore"}
                try:
                    ContentChunkMetadata(**meta)
                except Exception as e:
                    tqdm.write(
                        f"[ERROR] Metadata validation failed for chunk {chunk_idx} in {filename}: {e}"
                    )
                    continue
                context = meta.pop("context", None)
                formatted_content = CONTEXT_FORMAT.format(
                    context=context or "", chunk=chunk_text
                )
                all_docs.append(Document(page_content=formatted_content, metadata=meta))
                tqdm.write(
                    f"Processed chunk {chunk_idx+1}/{len(chunks)} for section {sec_idx+1} in {filename}"
                )
    tqdm.write("HTML loading complete.")
    return all_docs

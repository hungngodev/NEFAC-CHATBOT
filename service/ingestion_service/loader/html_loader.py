import os
import json
from tqdm import tqdm
from bs4 import BeautifulSoup, Tag
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from service.schemas.metadata import ContentChunkMetadata
from service.ingestion_service.settings import CHUNK_SIZE, HTML_CHUNK_OVERLAP

# Configure a recursive splitter for coherent HTML sections
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE, chunk_overlap=HTML_CHUNK_OVERLAP
)


def html_loader(metadata_json_path: str, content_dir: str) -> list[Document]:
    """
    Improved HTML loader:
      - Strips boilerplate (scripts/styles/nav/footer/header/aside)
      - Converts <img> tags to their alt text to preserve meaningful captions
      - Builds a hierarchy using all headings (h1–h6)
      - Groups consecutive elements under each heading into sections
      - Chunks each section for coherent context
      - Records detailed provenance (section path, chunk indices, anchors)
    """
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    all_docs: list[Document] = []
    for entry in tqdm(entries, desc="Loading HTML content"):
        filename = entry.get("filename")
        if not filename:
            continue
        html_path = os.path.join(content_dir, filename)
        if not os.path.exists(html_path):
            print(f"Missing HTML: {html_path}")
            continue

        with open(html_path, "r", encoding="utf-8") as fh:
            html = fh.read()
        soup = BeautifulSoup(html, "html.parser")
        # Remove boilerplate tags
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        # Replace images with their alt text
        for img in soup.find_all("img"):
            if isinstance(img, Tag):
                alt = img.get("alt", "")
                img.replace_with(soup.new_string(str(alt)))

        title = entry.get("title", os.path.splitext(filename)[0])
        # Define tags to consider as content
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
            # Headings define new sections
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
            # Accumulate content under current section
            anchor = elem.get("id") or elem.get("name") or None
            current["texts"].append(text)
            current["anchors"].append(anchor)
        # Flush last section
        if current["texts"]:
            sections.append(current)

        # Chunk each section
        for sec_idx, sec in enumerate(sections):
            section_text = "\n\n".join(sec["texts"])
            chunks = splitter.split_text(section_text)
            for chunk_idx, chunk in enumerate(chunks):
                anchor = sec["anchors"][0] if sec["anchors"] else None
                meta = dict(entry)
                meta.update(
                    {
                        "source": title,
                        "type": "html",
                        "section_path": sec["path"],
                        "section_index": sec_idx,
                        "chunk_index": chunk_idx,
                        "total_chunks_in_section": len(chunks),
                        "chunking_strategy": splitter.__class__.__name__,
                        "provenance": {
                            "type": "html_section_chunk",
                            "section_path": sec["path"],
                            "section_index": sec_idx,
                            "anchor": anchor,
                            "chunk_index": chunk_idx,
                            "chunking_strategy": splitter.__class__.__name__,
                            "html_url": (
                                f"{entry.get('link','')}#{anchor}"
                                if anchor
                                else entry.get("link", "")
                            ),
                        },
                    }
                )
                chunk_meta = {
                    "section_path": sec["path"],
                    "section_index": sec_idx,
                    "chunk_index": chunk_idx,
                    "total_chunks_in_section": len(chunks),
                    "chunking_strategy": splitter.__class__.__name__,
                    "provenance": {
                        "type": "html_section_chunk",
                        "section_path": sec["path"],
                        "section_index": sec_idx,
                        "anchor": anchor,
                        "chunk_index": chunk_idx,
                        "chunking_strategy": splitter.__class__.__name__,
                        "html_url": (
                            f"{entry.get('link','')}#{anchor}"
                            if anchor
                            else entry.get("link", "")
                        ),
                    },
                }
                # Coerce featured_image to string if needed
                if "featured_image" in meta:
                    fi = meta["featured_image"]
                    if isinstance(fi, dict):
                        meta["featured_image"] = (
                            fi.get("title") or fi.get("url") or str(fi)
                        )
                    elif not (isinstance(fi, str) or fi is None):
                        meta["featured_image"] = None
                ContentChunkMetadata.model_config = {"extra": "ignore"}
                ContentChunkMetadata(**{**meta, **chunk_meta})
                meta.update(chunk_meta)
                all_docs.append(Document(page_content=chunk, metadata=meta))

    return all_docs

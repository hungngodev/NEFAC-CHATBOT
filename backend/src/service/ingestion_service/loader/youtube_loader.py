import json
import logging
import os
import re
import time
from typing import Any, List

from langchain.docstore.document import Document
from langchain_core.runnables import RunnableLambda
from tqdm import tqdm

from src.schemas.state import YouTubeChunkMetadata
from src.service.ingestion_service.loader.semantic_double_pass_splitter import (
    SemanticDoublePassMergingSplitterWithContext,
)
from src.service.ingestion_service.settings import (
    CONTEXT_FORMAT,
    YOUTUBE_TEXT_SPLIT_CHUNK_SIZE,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("youtube_loader_pipeline")

# Helper to parse transcript and strip timestamps
TRANSCRIPT_TIMESTAMP_PATTERN = re.compile(r"\[(?P<ts>[\d:\.]+)s?\]\s*(?P<txt>.*)")


def load_youtube_entries(metadata_json_path) -> List[Document]:
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    return entries


def parse_youtube_transcript_lines(transcript_text: str) -> Any:
    """
    Parse transcript into a list of dicts: [{"start_seconds": float, "text": str}]
    """
    lines = []
    for raw in transcript_text.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        match = TRANSCRIPT_TIMESTAMP_PATTERN.match(raw)
        if match:
            ts = match.group("ts")
            text = match.group("txt").strip()
            parts = ts.split(":")
            try:
                if len(parts) == 3:
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    seconds = int(parts[0]) * 60 + float(parts[1])
                else:
                    seconds = float(parts[0])
            except ValueError:
                continue
            lines.append({"start_seconds": seconds, "text": text})
        else:
            if lines:
                lines[-1]["text"] += " " + raw
            else:
                lines.append({"start_seconds": 0.0, "text": raw})
    return lines


def strip_timestamps_from_transcript(transcript_text: str) -> str:
    """Return transcript text with all timestamps removed, just the plain text."""
    lines = []
    for raw in transcript_text.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        match = TRANSCRIPT_TIMESTAMP_PATTERN.match(raw)
        if match:
            text = match.group("txt").strip()
            if text:
                lines.append(text)
        else:
            lines.append(raw)
    return " ".join(lines)


def parse_transcript_segments(raw_lines) -> Any:
    segments = []
    for i in range(len(raw_lines) - 1):
        t0 = float(re.findall(r"\[(\d+\.\d+)s\]", raw_lines[i])[0])
        t1 = float(re.findall(r"\[(\d+\.\d+)s\]", raw_lines[i + 1])[0])
        text = re.sub(r"\[\d+\.\d+s\]", "", raw_lines[i]).strip()
        segments.append({"text": text, "start": t0, "end": t1})
    # Last line: use previous end or None
    if raw_lines:
        last_line = raw_lines[-1]
        t0 = float(re.findall(r"\[(\d+\.\d+)s\]", last_line)[0])
        text = re.sub(r"\[\d+\.\d+s\]", "", last_line).strip()
        segments.append({"text": text, "start": t0, "end": None})
    return segments


def build_offset_map(segments) -> Any:
    full_text = ""
    offset_map = []
    for seg in segments:
        start_char = len(full_text)
        full_text += seg["text"] + " "
        end_char = len(full_text)
        offset_map.append(
            {
                "start_char": start_char,
                "end_char": end_char,
                "start_time": seg["start"],
                "end_time": seg["end"],
            }
        )
    return full_text.strip(), offset_map


def get_time_bounds(chunk_start, chunk_end, offset_map) -> Any:
    start_time = end_time = None
    for entry in offset_map:
        if entry["end_char"] < chunk_start:
            continue
        if entry["start_char"] > chunk_end:
            break
        if start_time is None:
            start_time = entry["start_time"]
        end_time = entry["end_time"]
    return start_time, end_time


def parse_youtube(entry, transcripts_dir) -> Any:
    transcript_file = entry.get("transcript_file")
    if not transcript_file:
        return None
    path = os.path.join(transcripts_dir, os.path.basename(transcript_file))
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()
    segments = parse_transcript_segments(raw_lines)
    if not segments:
        return None
    full_text, offset_map = build_offset_map(segments)
    return {
        "entry": entry,
        "segments": segments,
        "full_text": full_text,
        "offset_map": offset_map,
    }


def chunk_and_contextualize_youtube(youtube_data, splitter) -> Any:
    entry = youtube_data["entry"]
    full_text = youtube_data["full_text"]
    offset_map = youtube_data["offset_map"]
    chunks = splitter.split_text(full_text, metadata=entry)
    curr_offset = 0
    chunked_docs = []
    for j, chunk_doc in enumerate(
        tqdm(
            chunks,
            desc=f"Chunking {entry.get('title', 'video')}",
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
        start_time, end_time = get_time_bounds(chunk_start, chunk_end, offset_map)
        chunk_meta = dict(chunk_doc.metadata)
        chunk_meta.update(
            {
                "chunk_index": j,
                "total_chunks_in_video": len(chunks),
                "chunking_strategy": splitter.__class__.__name__,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
        context = chunk_meta.pop("context", None)
        formatted_content = CONTEXT_FORMAT.format(context=context or "", chunk=chunk_text)
        YouTubeChunkMetadata.model_config = {"extra": "ignore"}
        try:
            YouTubeChunkMetadata(**chunk_meta)
        except Exception as e:
            tqdm.write(f"[ERROR] Metadata validation failed for chunk {j} in {entry.get('title', 'video')}: {e}")
            continue
        chunked_docs.append(Document(page_content=formatted_content, metadata=chunk_meta))
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


def youtube_loader(metadata_json_path, transcripts_dir) -> list[Document]:
    splitter = SemanticDoublePassMergingSplitterWithContext(
        max_chunk_size=YOUTUBE_TEXT_SPLIT_CHUNK_SIZE,
        min_chunk_size=100,
    )
    start_time = time.time()
    logger.info(f"[YouTube Loader] Loading entries from {metadata_json_path}")

    def parse_all(entries):
        parsed = []
        for e in tqdm(entries, desc="Parsing YouTube entries"):
            result = parse_youtube(e, transcripts_dir)
            if result is not None:
                parsed.append(result)
        return parsed

    pipeline = (
        RunnableLambda(lambda _: load_youtube_entries(metadata_json_path))
        | RunnableLambda(parse_all)
        | RunnableLambda(lambda youtube_datas: [doc for youtube_data in (youtube_datas if isinstance(youtube_datas, list) else ([youtube_datas] if isinstance(youtube_datas, dict) else [])) for doc in chunk_and_contextualize_youtube(youtube_data, splitter)])
    )
    docs = pipeline.invoke({})
    docs = ensure_list_of_documents(docs)
    total_tokens = count_tokens_in_docs(docs)
    elapsed = time.time() - start_time
    logger.info(f"[YouTube Loader] Processed {len(docs)} chunks, {total_tokens} tokens in {elapsed:.2f} seconds.")
    tqdm.write(f"[YouTube Loader] Processed {len(docs)} chunks, {total_tokens} tokens in {elapsed:.2f} seconds.")
    return docs

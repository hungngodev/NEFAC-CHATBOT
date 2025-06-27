import os
import json
import re
import logging
from tqdm import tqdm
from langchain.docstore.document import Document
from service.schemas.metadata import YouTubeChunkMetadata
from service.ingestion_service.settings import (
    YOUTUBE_TEXT_SPLIT_CHUNK_SIZE,
    CONTEXT_FORMAT,
)
from service.ingestion_service.loader.semantic_double_pass_splitter import (
    SemanticDoublePassMergingSplitterWithContext,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Helper to parse transcript and strip timestamps
TRANSCRIPT_TIMESTAMP_PATTERN = re.compile(r"\[(?P<ts>[\d:\.]+)s?\]\s*(?P<txt>.*)")


def parse_youtube_transcript_lines(transcript_text: str):
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
                    seconds = (
                        int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                    )
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


def parse_transcript_segments(raw_lines):
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


def build_offset_map(segments):
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


def get_time_bounds(chunk_start, chunk_end, offset_map):
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


def youtube_loader(metadata_json_path: str, transcripts_dir: str) -> list[Document]:
    """
    Load YouTube transcripts and produce semantically coherent chunks using SemanticDoublePassMergingSplitterWithContext.
    - Strips timestamps from transcript before chunking.
    - Each chunk gets provenance metadata similar to pdf_loader.
    - Each chunk is contextualized using contextualize_chunk.
    """

    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)
    all_docs: list[Document] = []
    chunking_strategy = "SemanticDoublePassMergingSplitterWithContext"
    splitter = SemanticDoublePassMergingSplitterWithContext(
        max_chunk_size=YOUTUBE_TEXT_SPLIT_CHUNK_SIZE,
        min_chunk_size=100,
    )
    tqdm.write("Starting YouTube transcript loading...")
    for entry in tqdm(
        entries, desc="Loading YouTube transcripts", dynamic_ncols=True, colour="cyan"
    ):
        transcript_file = entry.get("transcript_file")
        if not transcript_file:
            tqdm.write(f"Skipping entry with missing transcript_file: {entry}")
            continue
        path = os.path.join(transcripts_dir, os.path.basename(transcript_file))
        if not os.path.exists(path):
            tqdm.write(f"Skipping entry, transcript not found: {transcript_file}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
        segments = parse_transcript_segments(raw_lines)
        if not segments:
            tqdm.write(f"No segments found in transcript: {transcript_file}")
            continue
        full_text, offset_map = build_offset_map(segments)
        # Chunk the full transcript
        tqdm.write(
            f"Chunking transcript: {entry.get('title', 'video')} ({len(segments)} segments)"
        )
        chunks = splitter.split_text(full_text, metadata=entry)
        curr_offset = 0
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
            chunk_meta = dict(entry)
            chunk_meta.update(
                {
                    "chunk_index": j,
                    "total_chunks_in_video": len(chunks),
                    "chunking_strategy": chunking_strategy,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
            context = chunk_meta.pop("context", None)
            formatted_content = CONTEXT_FORMAT.format(
                context=context or "", chunk=chunk_text
            )
            YouTubeChunkMetadata.model_config = {"extra": "ignore"}
            try:
                YouTubeChunkMetadata(**chunk_meta)
            except Exception as e:
                tqdm.write(
                    f"[ERROR] Metadata validation failed for chunk {j} in {entry.get('title', 'video')}: {e}"
                )
                continue
            all_docs.append(
                Document(page_content=formatted_content, metadata=chunk_meta)
            )
            tqdm.write(
                f"Processed chunk {j+1}/{len(chunks)} for {entry.get('title', 'video')}"
            )
    tqdm.write("YouTube transcript loading complete.")
    return all_docs

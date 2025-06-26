import os
import json
import re
from tqdm import tqdm
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from service.schemas.metadata import YouTubeChunkMetadata
from service.ingestion_service.settings import YOUTUBE_SEGMENT_DURATION

# Configure a recursive splitter for sub-chunking within time segments
text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

chunk_size = YOUTUBE_SEGMENT_DURATION  # seconds per chunk


def parse_youtube_transcript(transcript_text: str) -> list[dict]:
    """
    Parse raw transcript lines with timestamps into a list of dicts:
    [{"start_seconds": float, "text": str}, ...]
    """
    lines = []
    for raw in transcript_text.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        match = re.match(r"\[(?P<ts>[\d:\.]+)s?\]\s*(?P<txt>.*)", raw)
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
            if text:
                lines.append({"start_seconds": seconds, "text": text})
        else:
            # append continuation to last line or start new
            if lines:
                lines[-1]["text"] += " " + raw
            else:
                lines.append({"start_seconds": 0.0, "text": raw})
    return lines


def youtube_loader(
    metadata_json_path: str, transcripts_dir: str, segment_duration: int = 60
) -> list[Document]:
    """
    Load YouTube transcripts and produce semantically coherent sub-chunks:

    1. Parse into timestamped lines
    2. Group lines into fixed-duration segments (segment_duration seconds)
    3. Within each segment, apply RecursiveCharacterTextSplitter for natural boundaries
    4. Preserve full provenance at both segment and sub-chunk level
    """
    # Read metadata entries
    with open(metadata_json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    documents: list[Document] = []
    for entry in tqdm(entries, desc="Loading YouTube transcripts"):
        transcript_file = entry.get("transcript_file")
        if not transcript_file:
            continue
        path = os.path.join(transcripts_dir, os.path.basename(transcript_file))
        if not os.path.exists(path):
            print(f"Missing transcript: {path}")
            continue

        raw_text = open(path, "r", encoding="utf-8").read()
        lines = parse_youtube_transcript(raw_text)
        # fallback full transcript if no timestamps
        if not lines:
            meta = dict(entry)
            meta.update(
                {
                    "type": "youtube",
                    "provenance": {
                        "type": "youtube_full",
                        "video_id": entry.get("video_id"),
                        "start_seconds": 0,
                        "end_seconds": entry.get("duration"),
                        "url": entry.get("source_url"),
                    },
                }
            )
            documents.append(Document(page_content=raw_text, metadata=meta))
            continue

        # 1. form time segments
        segments = []
        current_lines = []
        seg_start = lines[0]["start_seconds"]
        seg_end = seg_start + segment_duration
        for line in lines:
            if line["start_seconds"] >= seg_end and current_lines:
                segments.append(
                    {
                        "start": seg_start,
                        "end": current_lines[-1]["start_seconds"],
                        "lines": current_lines,
                    }
                )
                current_lines = []
                seg_start = line["start_seconds"]
                seg_end = seg_start + segment_duration
            current_lines.append(line)
        if current_lines:
            segments.append(
                {
                    "start": seg_start,
                    "end": current_lines[-1]["start_seconds"],
                    "lines": current_lines,
                }
            )

        # 2. within each segment, apply text splitter
        for seg in segments:
            seg_text = " ".join([ln["text"] for ln in seg["lines"]])
            subchunks = text_splitter.split_text(seg_text)
            total_sub = len(subchunks)
            for idx, chunk in enumerate(subchunks):
                meta = dict(entry)
                meta.update(
                    {
                        "type": "youtube",
                        "provenance": {
                            "type": "youtube_subsegment",
                            "video_id": entry.get("video_id"),
                            "segment_start": seg["start"],
                            "segment_end": seg["end"],
                            "subsegment_index": idx,
                            "total_subsegments": total_sub,
                            "chunking_strategy": text_splitter.__class__.__name__,
                            "url": f"{entry.get('source_url')}?t={int(seg['start'])}",
                        },
                    }
                )
                chunk_meta = {
                    "chunk_index": len(documents),
                    "total_chunks_in_video": 0,  # Will set after all chunks are created
                    "chunking_strategy": "timestamp_based",
                    "provenance": meta["provenance"],
                }
                # Validate chunk metadata (will update total_chunks_in_video after loop)
                YouTubeChunkMetadata.model_config = {"extra": "ignore"}
                YouTubeChunkMetadata(**{**meta, **chunk_meta})
                meta.update(chunk_meta)
                documents.append(Document(page_content=chunk, metadata=meta))
            # After all chunks, update total_chunks_in_video
            total_chunks = len(documents)
            for doc in documents[-total_chunks:]:
                doc.metadata["total_chunks_in_video"] = total_chunks

    return documents

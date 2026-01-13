"""Section Linker Tool for deep linking to specific document sections.

This tool generates deep links to:
- HTML document sections (anchor tags)
- PDF pages
- YouTube video timestamps

Uses semantic search to match user queries to document sections.
"""

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import aiohttp
from langchain_core.tools import tool
from pydantic import Field

from src.schemas.navigation_state import SectionLinkResult

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    parsed = urlparse(url)

    # youtube.com/watch?v=xxx
    if "youtube.com" in parsed.netloc:
        query = parse_qs(parsed.query)
        return query.get("v", [None])[0]

    # youtu.be/xxx
    if "youtu.be" in parsed.netloc:
        return parsed.path.lstrip("/")

    return None


def detect_document_type(url: str, content_type: Optional[str] = None) -> str:
    """Detect document type from URL and content type."""
    url_lower = url.lower()

    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"

    if url_lower.endswith(".pdf") or (content_type and "pdf" in content_type.lower()):
        return "pdf"

    if content_type and "html" in content_type.lower():
        return "html"

    # Default based on URL extension
    if url_lower.endswith((".html", ".htm", "/")):
        return "html"

    return "unknown"


async def find_html_section(content: str, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Find matching sections in HTML content using heading analysis.

    Args:
        content: HTML content
        query: User's section search query
        max_results: Maximum number of section matches to return

    Returns:
        List of section matches with anchor info
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup not installed, using regex fallback")
        return await _find_sections_regex(content, query, max_results)

    soup = BeautifulSoup(content, "html.parser")
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored_sections = []

    for heading in headings:
        heading_text = heading.get_text(strip=True)
        heading_lower = heading_text.lower()
        heading_words = set(heading_lower.split())

        # Calculate relevance score
        score = 0.0

        # Exact match
        if query_lower == heading_lower:
            score = 1.0
        elif query_lower in heading_lower:
            score = 0.8
        elif heading_lower in query_lower:
            score = 0.6
        else:
            # Word overlap
            overlap = len(query_words & heading_words)
            if overlap > 0:
                score = 0.4 * (overlap / max(len(query_words), 1))

        if score > 0:
            # Get or generate anchor ID
            anchor_id = heading.get("id")
            if not anchor_id:
                # Generate a deterministic ID
                anchor_id = f"section-{hashlib.md5(heading_text.encode()).hexdigest()[:8]}"

            scored_sections.append({"heading_text": heading_text, "anchor_id": anchor_id, "tag": heading.name, "score": score, "has_existing_id": heading.get("id") is not None})

    # Sort by score descending
    scored_sections.sort(key=lambda x: x["score"], reverse=True)

    return scored_sections[:max_results]


async def _find_sections_regex(content: str, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
    """Fallback section finder using regex."""
    # Match heading tags with optional id
    heading_pattern = r'<h([1-6])(?:\s+[^>]*id=["\']([^"\']+)["\'])?[^>]*>([^<]+)</h\1>'

    matches = re.findall(heading_pattern, content, re.IGNORECASE)
    query_lower = query.lower()

    scored_sections = []
    for level, anchor_id, text in matches:
        text = text.strip()
        text_lower = text.lower()

        score = 0.0
        if query_lower in text_lower:
            score = 0.8
        elif any(word in text_lower for word in query_lower.split()):
            score = 0.4

        if score > 0:
            if not anchor_id:
                anchor_id = f"section-{hashlib.md5(text.encode()).hexdigest()[:8]}"

            scored_sections.append({"heading_text": text, "anchor_id": anchor_id, "tag": f"h{level}", "score": score, "has_existing_id": bool(anchor_id)})

    scored_sections.sort(key=lambda x: x["score"], reverse=True)
    return scored_sections[:max_results]


async def find_youtube_timestamp(video_id: str, query: str) -> Dict[str, Any]:
    """Find matching timestamp in YouTube video transcript.

    Args:
        video_id: YouTube video ID
        query: Section/topic to find in transcript

    Returns:
        Dict with timestamp and matched text
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return {"error": "youtube_transcript_api not installed", "hint": "Install with: pip install youtube-transcript-api"}

    try:
        # Fetch transcript
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try to get English transcript
        try:
            transcript = transcript_list.find_transcript(["en"]).fetch()
        except Exception:
            # Get any available transcript
            transcript = transcript_list.find_generated_transcript(["en"]).fetch()

        query_lower = query.lower()
        query_words = set(query_lower.split())

        best_match = None
        best_score: float = 0.0

        # Search through transcript segments
        for i, segment in enumerate(transcript):
            text = segment.get("text", "").lower()
            text_words = set(text.split())

            # Calculate relevance
            score = 0.0
            if query_lower in text:
                score = 1.0
            else:
                overlap = len(query_words & text_words)
                if overlap > 0:
                    score = overlap / len(query_words)

            if score > best_score:
                best_score = score
                best_match = {"timestamp": int(segment.get("start", 0)), "text": segment.get("text", ""), "duration": int(segment.get("duration", 0)), "score": score}

                # Also include context (previous and next segments)
                if best_score >= 0.5:
                    context = []
                    if i > 0:
                        context.append(transcript[i - 1].get("text", ""))
                    context.append(segment.get("text", ""))
                    if i < len(transcript) - 1:
                        context.append(transcript[i + 1].get("text", ""))
                    best_match["context"] = " ".join(context)

        if best_match:
            return best_match
        else:
            return {"error": "No matching section found in transcript"}

    except Exception as e:
        logger.error(f"YouTube transcript error: {e}")
        return {"error": f"Failed to fetch transcript: {str(e)}"}


@tool
async def create_section_link(
    document_url: str = Field(description="URL of the document to link into"),
    section_query: str = Field(description="Description of the section to find and link to"),
    link_type: str = Field(default="auto", description="Type of deep link: 'anchor' (HTML), 'page' (PDF), 'timestamp' (video), or 'auto' (detect)"),
) -> str:
    """Generate a deep link to a specific section within a document.

    Analyzes the document to find the best matching section and returns
    a direct link. Supports:
    - HTML pages: Links to heading anchors (e.g., url#section-id)
    - PDF documents: Links to pages (e.g., url#page=5)
    - YouTube videos: Links to timestamps (e.g., url&t=120s)

    Examples:
    - create_section_link("https://nefac.org/foia-guide", "exemptions")
    - create_section_link("https://youtube.com/watch?v=xxx", "public records definition")
    """

    # Detect document type if auto
    detected_type = detect_document_type(document_url)
    effective_type = detected_type if link_type == "auto" else link_type

    if effective_type == "youtube":
        video_id = extract_video_id(document_url)
        if not video_id:
            return json.dumps({"error": "Could not extract YouTube video ID from URL", "url": document_url}, indent=2)

        timestamp_result = await find_youtube_timestamp(video_id, section_query)

        if "error" in timestamp_result:
            return json.dumps({"error": timestamp_result["error"], "hint": timestamp_result.get("hint", ""), "url": document_url}, indent=2)

        # Build timestamped URL
        timestamp = timestamp_result["timestamp"]
        parsed = urlparse(document_url)
        query = parse_qs(parsed.query)
        query["t"] = [f"{timestamp}s"]
        new_query = urlencode(query, doseq=True)
        full_url = urlunparse(parsed._replace(query=new_query))

        return json.dumps(SectionLinkResult(full_url=full_url, section_title=timestamp_result.get("text", section_query)[:100], confidence=timestamp_result.get("score", 0.5), link_type="timestamp").model_dump(), indent=2)

    elif effective_type == "pdf":
        # PDF page linking - would need PDF parsing library
        # For now, return a basic page link suggestion
        return json.dumps({"status": "partial_support", "message": "PDF section linking requires document analysis. " "Consider using metadata_filter_search to find the right PDF first.", "basic_link": f"{document_url}#page=1", "hint": "To link to a specific page, use #page=N suffix"}, indent=2)

    elif effective_type == "html":
        # Fetch HTML content
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(document_url) as resp:
                    if resp.status != 200:
                        return json.dumps({"error": f"Failed to fetch document: HTTP {resp.status}", "url": document_url}, indent=2)
                    content = await resp.text()
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch document: {str(e)}", "url": document_url}, indent=2)

        # Find matching sections
        sections = await find_html_section(content, section_query)

        if not sections:
            return json.dumps({"error": "No matching sections found", "query": section_query, "url": document_url, "suggestion": "Try broader or different search terms"}, indent=2)

        # Return best match
        best = sections[0]
        full_url = f"{document_url}#{best['anchor_id']}"

        section_result = SectionLinkResult(full_url=full_url, section_title=best["heading_text"], confidence=best["score"], link_type="anchor")

        # Include alternatives if available
        response = section_result.model_dump()
        if len(sections) > 1:
            response["alternatives"] = [{"url": f"{document_url}#{s['anchor_id']}", "title": s["heading_text"], "confidence": s["score"]} for s in sections[1:]]

        return json.dumps(response, indent=2)

    else:
        return json.dumps({"error": f"Unsupported document type: {effective_type}", "detected_type": detected_type, "url": document_url, "supported_types": ["html", "pdf", "youtube"]}, indent=2)


@tool
async def list_document_sections(document_url: str = Field(description="URL of the HTML document to analyze"), max_sections: int = Field(default=20, description="Maximum sections to return", ge=1, le=50)) -> str:
    """List all sections (headings) in an HTML document.

    Use this to discover what sections are available before creating deep links.
    Returns all headings (h1-h6) with their anchor IDs.
    """
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(document_url) as resp:
                if resp.status != 200:
                    return json.dumps({"error": f"Failed to fetch document: HTTP {resp.status}"}, indent=2)
                content = await resp.text()
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch: {str(e)}"}, indent=2)

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(content, "html.parser")
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    except ImportError:
        # Regex fallback
        heading_pattern = r"<h([1-6])[^>]*>([^<]+)</h\1>"
        matches = re.findall(heading_pattern, content, re.IGNORECASE)
        headings = [{"level": int(m[0]), "text": m[1].strip()} for m in matches]

        return json.dumps({"url": document_url, "total_sections": len(headings[:max_sections]), "sections": [{"level": h["level"], "title": h["text"]} for h in headings[:max_sections]], "note": "Anchor IDs not available without BeautifulSoup"}, indent=2)

    sections = []
    for h in headings[:max_sections]:
        text = h.get_text(strip=True)
        anchor_id = h.get("id")

        sections.append({"level": int(h.name[1]), "title": text, "anchor_id": anchor_id, "link": f"{document_url}#{anchor_id}" if anchor_id else None})

    return json.dumps({"url": document_url, "total_sections": len(sections), "sections": sections}, indent=2)

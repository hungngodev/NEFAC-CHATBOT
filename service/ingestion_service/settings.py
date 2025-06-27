# Chunking configuration for all loaders
CHUNK_SIZE = 1024  # Number of characters per chunk (PDF, HTML)
CHUNK_OVERLAP = 128  # Overlap for text chunking (PDF)
HTML_CHUNK_SIZE = 600  # Number of characters per chunk for HTML (HTML)
HTML_CHUNK_OVERLAP = 64  # Overlap for HTML chunking (HTML)
YOUTUBE_SEGMENT_DURATION = 30  # seconds per chunk for YouTube transcripts (YouTube)
YOUTUBE_TEXT_SPLIT_CHUNK_SIZE = (
    800  # Number of characters per sub-chunk within a YouTube segment (YouTube)
)
YOUTUBE_TEXT_SPLIT_CHUNK_OVERLAP = 100  # Overlap for YouTube sub-chunking (YouTube)

CONTEXT_FORMAT = "Context: {context}\n\nChunk: {chunk}"

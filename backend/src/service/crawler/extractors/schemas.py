"""
Consolidated extraction schemas for NEFAC crawler.

This module consolidates all extraction schemas into a single file
following the deep refactor principles of minimization and clarity.
"""

# Document extraction schema
DOCUMENT_SCHEMA = {
    "name": "document_extractor",
    "baseSelector": "a[href]",
    "fields": [
        {"name": "title", "selector": "text()", "type": "text"},
        {"name": "url", "selector": "@href", "type": "attribute"},
        {
            "name": "file_type",
            "selector": "@href",
            "type": "attribute",
            "transform": "extract_file_extension",
        },
    ],
}

# Content extraction schema
CONTENT_SCHEMA = {
    "name": "content_extractor",
    "baseSelector": "body",
    "fields": [
        {"name": "title", "selector": "h1, title", "type": "text"},
        {
            "name": "content",
            "selector": "main, article, .content, #content",
            "type": "text",
        },
        {"name": "headings", "selector": "h1, h2, h3, h4, h5, h6", "type": "list"},
    ],
}

# Link extraction schema
LINK_SCHEMA = {
    "name": "link_extractor",
    "baseSelector": "a[href]",
    "fields": [
        {"name": "text", "selector": "text()", "type": "text"},
        {"name": "href", "selector": "@href", "type": "attribute"},
        {"name": "title", "selector": "@title", "type": "attribute"},
    ],
}

# Media extraction schema
MEDIA_SCHEMA = {
    "name": "media_extractor",
    "baseSelector": "img, video, audio, iframe[src*='youtube'], iframe[src*='vimeo']",
    "fields": [
        {"name": "src", "selector": "@src", "type": "attribute"},
        {"name": "alt", "selector": "@alt", "type": "attribute"},
        {"name": "title", "selector": "@title", "type": "attribute"},
        {"name": "type", "selector": "name()", "type": "tag"},
    ],
}

# YouTube-specific schema
YOUTUBE_SCHEMA = {
    "name": "youtube_extractor",
    "baseSelector": "iframe[src*='youtube'], a[href*='youtube']",
    "fields": [
        {
            "name": "video_id",
            "selector": "@src, @href",
            "type": "attribute",
            "transform": "extract_youtube_id",
        },
        {"name": "title", "selector": "@title, text()", "type": "text"},
    ],
}

# Export all schemas
__all__ = [
    "DOCUMENT_SCHEMA",
    "CONTENT_SCHEMA",
    "LINK_SCHEMA",
    "MEDIA_SCHEMA",
    "YOUTUBE_SCHEMA",
]

"""
Prompts package for the NEFAC backend.
All prompts are organized by their source file for easy maintenance and reference.
"""

# Import prompts from chain.py
# Import base prompt
from .base import BASE_PROMPT
from .chain import (
    CONTEXTUALIZE_PROMPT,
    GENERAL_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    METHOD_SELECTION_PROMPT,
    RETRIEVAL_PROMPT,
)

# Import prompts from decomposition.py
from .decomposition import (
    DECOMPOSITION_PROMPT,
    FINAL_SYNTHESIS_TEMPLATE,
    QA_TEMPLATE,
)

# Import prompts from hyDe.py
from .hyDe import (
    HYDE_FINAL_PROMPT,
    HYDE_GENERATION_PROMPT,
)

# Import prompts from multi_query.py
from .multi_query import (
    MULTI_QUERY_PERSPECTIVES_PROMPT,
)

# Import prompts from rag_fusion.py
from .rag_fusion import (
    RAG_FUSION_PROMPT,
)

# Import prompts from step_back.py
from .step_back import (
    STEP_BACK_RESPONSE_PROMPT,
    STEP_BACK_SYSTEM_PROMPT,
)

# Import prompts from youtube_loader.py
from .youtube_loader import TRANSCRIPT_CLEANING_PROMPT

__all__ = [
    # Chain prompts
    "CONTEXTUALIZE_PROMPT",
    "METHOD_SELECTION_PROMPT",
    "RETRIEVAL_PROMPT",
    "GENERAL_PROMPT",
    "INTENT_CLASSIFICATION_PROMPT",
    # YouTube loader prompts
    "TRANSCRIPT_CLEANING_PROMPT",
    # Query translation prompts
    "MULTI_QUERY_PERSPECTIVES_PROMPT",
    "DECOMPOSITION_PROMPT",
    "QA_TEMPLATE",
    "FINAL_SYNTHESIS_TEMPLATE",
    "STEP_BACK_SYSTEM_PROMPT",
    "STEP_BACK_RESPONSE_PROMPT",
    "HYDE_GENERATION_PROMPT",
    "HYDE_FINAL_PROMPT",
    "RAG_FUSION_PROMPT",
    # Base prompt
    "BASE_PROMPT",
]

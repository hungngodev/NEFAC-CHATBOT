# Prompts Directory

This directory contains all the prompts used throughout the NEFAC backend, organized by their source file for easy maintenance and reference.

## Organization

Prompts are organized by the file they were extracted from:

### `chain.py`

Contains prompts from the main LangChain pipeline:

- `CONTEXTUALIZE_PROMPT` - For reformulating questions with chat history
- `METHOD_SELECTION_PROMPT` - For choosing query transformation strategy
- `RETRIEVAL_PROMPT` - For document retrieval responses
- `GENERAL_PROMPT` - For general conversation responses
- `INTENT_CLASSIFICATION_PROMPT` - For classifying user intent

### `youtube_loader.py`

Contains prompts for YouTube transcript processing:

- `TRANSCRIPT_CLEANING_PROMPT` - For cleaning auto-generated YouTube transcripts

### `multi_query.py`

Contains prompts for multi-query translation:

- `MULTI_QUERY_PERSPECTIVES_PROMPT` - For generating multiple search queries

### `decomposition.py`

Contains prompts for query decomposition:

- `QUERY_DECOMPOSITION_PROMPT` - For breaking down complex questions
- `QA_TEMPLATE` - For answering individual sub-questions
- `FINAL_SYNTHESIS_TEMPLATE` - For synthesizing final responses

### `step_back.py`

Contains prompts for step-back reasoning:

- `STEP_BACK_SYSTEM_PROMPT` - For stepping back to broader legal context
- `STEP_BACK_RESPONSE_PROMPT` - For combining normal and step-back context

### `hyDe.py`

Contains prompts for Hypothetical Document Embedding:

- `HYDE_GENERATION_PROMPT` - For generating hypothetical legal passages
- `HYDE_FINAL_PROMPT` - For final answer generation

### `rag_fusion.py`

Contains prompts for RAG fusion:

- `RAG_FUSION_PROMPT` - For generating complementary search queries

## Usage

Import prompts from the package:

```python
from prompts import (
    CONTEXTUALIZE_PROMPT,
    RETRIEVAL_PROMPT,
    TRANSCRIPT_CLEANING_PROMPT,
    # ... etc
)
```

Or import from specific files:

```python
from prompts.chain import CONTEXTUALIZE_PROMPT
from prompts.youtube_loader import TRANSCRIPT_CLEANING_PROMPT
```

## Maintenance

When adding new prompts:

1. Create a new file named after the source file (e.g., `new_file.py`)
2. Add the prompts with clear section headers and comments
3. Update the `__init__.py` file to import the new prompts
4. Update this README with the new prompts

When modifying existing prompts:

1. Update the prompt in the appropriate file
2. Update any references in the source files
3. Consider updating this README if the prompt's purpose changes

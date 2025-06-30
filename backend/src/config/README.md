# Config Directory

This directory contains all the configuration-related files for the NEFAC backend, including prompt definitions and constants.

## Organization

- `constant.py`: Defines various constants used throughout the application, such as model names.
- `prompts.py`: Contains all prompt definitions consolidated into a single file.

## Usage

Import constants:

```python
from src.config.constant import MODEL_NAME
```

Import prompts:

```python
from src.config.prompts import (
    CONTEXTUALIZE_PROMPT,
    FINAL_PROMPT,
    # ... etc
)
```

## Maintenance

When adding new prompts or constants:

1. Add them to `prompts.py` or `constant.py` respectively.
2. Update the `__init__.py` file in this directory to expose them.
3. Update this README with any significant changes.
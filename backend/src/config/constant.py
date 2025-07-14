from enum import Enum

NUMBER_OF_NEAREST_NEIGHBORS = 3
LAMBDA_MULT = 0.25
THRESHOLD = 0.7
MODEL_NAME = "gpt-4"
QUERY_TRANSLATION_MODEL_NAME = "gpt-4"
YOUTUBE_MODEL_NAME = "gpt-4"


SUMMARY_MODEL_NAME = "gpt-4"
CONTEXTUALIZED_QUERY_MODEL_NAME = "gpt-4"
INTENT_CLASSIFICATION_MODEL_NAME = "gpt-4"
COMPLEXITY_ANALYSIS_MODEL_NAME = "gpt-4"
RETRIEVAL_MODEL_NAME = "gpt-4"
RETRIEVAL_SELECTION_MODEL_NAME = "gpt-4"


EMBEDDING_MODEL_NAME = "text-embedding-3-small"


# --- Health Check Constants ---
class HealthCheckComponent(str, Enum):
    MEMORY = "memory"
    GRAPH = "graph"
    STATE = "state"
    MEMORY_STORAGE = "memory_storage"

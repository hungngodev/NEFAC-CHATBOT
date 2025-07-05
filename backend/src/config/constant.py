from enum import Enum

NUMBER_OF_NEAREST_NEIGHBORS = 3
LAMBDA_MULT = 0.25
THRESHOLD = 0.7
MODEL_NAME = "gpt-4"
QUERY_TRANSLATION_MODEL_NAME = "gpt-4"
YOUTUBE_MODEL_NAME = "gpt-4"

# --- History Manager Constants ---
HISTORY_THRESHOLD = 10
MESSAGES_TO_SUMMARIZE = 8
MESSAGES_TO_KEEP = 2

# --- Application Constants ---
STREAMING_WORD_COUNT = 5
STREAMING_SLEEP_INTERVAL = 0.05
DEFAULT_MEMORY_RETENTION_DAYS = 30


# --- Health Check Constants ---
class HealthCheckComponent(str, Enum):
    MEMORY = "memory"
    GRAPH = "graph"
    STATE = "state"
    MEMORY_STORAGE = "memory_storage"

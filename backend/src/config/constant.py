from enum import Enum

NUMBER_OF_NEAREST_NEIGHBORS = 3
LAMBDA_MULT = 0.25
THRESHOLD = 0.7


# --- Health Check Constants ---
class HealthCheckComponent(str, Enum):
    MEMORY = "memory"
    GRAPH = "graph"
    STATE = "state"
    MEMORY_STORAGE = "memory_storage"

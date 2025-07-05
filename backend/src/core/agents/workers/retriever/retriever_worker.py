from typing import Any, Dict

from src.core.agents.workers.retriever.retrieval import retrieval_agent
from src.schemas.state import AgentState


def retriever_worker(state: AgentState) -> Dict[str, Any]:
    """
    A worker that retrieves documents based on the current state.
    """
    try:
        documents = retrieval_agent(state)
        return {"documents": documents}
    except Exception as e:
        return {"error": str(e)}

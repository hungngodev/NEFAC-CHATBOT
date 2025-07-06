from typing import Any, Dict

from src.core.agents.workers.react.query_translation.contextual_strategy import get_contextual_strategy_chain
from src.core.agents.workers.react.query_translation.decomposition import get_decomposition_chain
from src.core.agents.workers.react.query_translation.factual_strategy import get_factual_strategy_chain
from src.core.agents.workers.react.query_translation.hyDe import get_hyDe_chain
from src.core.agents.workers.react.query_translation.multi_query import get_multi_query_chain
from src.core.agents.workers.react.query_translation.rag_fusion import get_rag_fusion_chain
from src.core.agents.workers.react.query_translation.step_back import get_step_back_chain
from src.schemas.state import AgentState


def query_transformer_agent(state: AgentState) -> Dict[str, Any]:
    """
    Applies the chosen query transformation using ensemble retriever.
    All strategies now use the sophisticated ensemble retriever instead of basic retrievers.
    """
    try:
        method = state.retrieval_method or "multiquery"

        # All strategies now use ensemble retriever internally - no need to pass retriever
        if "multiquery" in method:
            transformer_chain = get_multi_query_chain()
        elif "decompose" in method:
            transformer_chain = get_decomposition_chain()
        elif "stepback" in method:
            transformer_chain = get_step_back_chain()
        elif "hyde" in method:
            transformer_chain = get_hyDe_chain()
        elif "ragfusion" in method:
            transformer_chain = get_rag_fusion_chain()
        elif "factual" in method:
            transformer_chain = get_factual_strategy_chain()
        elif "contextual" in method:
            transformer_chain = get_contextual_strategy_chain()
        else:
            transformer_chain = get_multi_query_chain()

        # All strategies return formatted documents, not just transformed queries
        transformed_result: str = transformer_chain.invoke({"question": state.contextualized_query})

        return {"transformed_query": transformed_result}
    except Exception as e:
        return {"error": str(e)}

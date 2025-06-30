from src.core.agents.state import AgentState
from src.core.query_translation.contextual_strategy import get_contextual_strategy_chain
from src.core.query_translation.decomposition import get_decomposition_chain
from src.core.query_translation.factual_strategy import get_factual_strategy_chain
from src.core.query_translation.hyDe import get_hyDe_chain
from src.core.query_translation.multi_query import get_multi_query_chain
from src.core.query_translation.rag_fusion import get_rag_fusion_chain
from src.core.query_translation.step_back import get_step_back_chain


def query_transformer_agent(state: AgentState):
    """
    Applies the chosen query transformation.
    """
    try:
        method = state.retrieval_method or "multiquery"
        retriever = state.retriever

        if "multiquery" in method:
            transformer_chain = get_multi_query_chain(retriever)
        elif "decompose" in method:
            transformer_chain = get_decomposition_chain(retriever)
        elif "stepback" in method:
            transformer_chain = get_step_back_chain(retriever)
        elif "hyde" in method:
            transformer_chain = get_hyDe_chain(retriever)
        elif "ragfusion" in method:
            transformer_chain = get_rag_fusion_chain(retriever)
        elif "factual" in method:
            transformer_chain = get_factual_strategy_chain(retriever)
        elif "contextual" in method:
            transformer_chain = get_contextual_strategy_chain(retriever)
        else:
            transformer_chain = get_multi_query_chain(retriever)

        transformed_query = transformer_chain.invoke({"question": state.contextualized_query})

        return {"transformed_query": transformed_query}
    except Exception as e:
        return {"error": str(e)}

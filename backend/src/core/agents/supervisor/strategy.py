from typing import Dict, List, Optional, TypedDict, Union

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config.prompts import METHOD_SELECTION_PROMPT, RETRIEVAL_METHOD_SELECTION_PROMPT
from src.schemas.core_types import AgentState, MethodSelection, RetrievalSelection


class RetrievalStrategyAgentOutput(TypedDict):
    retrieval_method: Optional[str]
    retrieval_selection: Dict[str, Union[str, List[str], List[float]]]  # Structured retrieval selection
    error: Optional[str]


def retrieval_strategy_agent(state: AgentState, model: ChatOpenAI) -> RetrievalStrategyAgentOutput:
    """
    Selects the retrieval method and query transformation strategy.
    """
    try:
        # Choose query method
        method_chain = ChatPromptTemplate.from_template(METHOD_SELECTION_PROMPT) | model.with_structured_output(MethodSelection, method="function_calling")
        method_result = method_chain.invoke({"question": state.contextualized_query})
        method_selection = MethodSelection(**method_result)

        # Choose retriever method(s)
        retrieval_selection_chain = ChatPromptTemplate.from_template(RETRIEVAL_METHOD_SELECTION_PROMPT) | model.with_structured_output(RetrievalSelection, method="function_calling")
        retrieval_result = retrieval_selection_chain.invoke({"question": state.contextualized_query})
        retrieval_selection = RetrievalSelection(**retrieval_result)

        # Defensive: handle both dict and object with .method/.dict()
        if isinstance(method_selection, dict):
            retrieval_method = method_selection.get("method")
        else:
            retrieval_method = getattr(method_selection, "method", None)
        if isinstance(retrieval_selection, dict):
            retrieval_selection_dict = retrieval_selection
        else:
            retrieval_selection_dict = retrieval_selection.dict() if hasattr(retrieval_selection, "dict") else {}
        return {
            "retrieval_method": retrieval_method,
            "retrieval_selection": retrieval_selection_dict,
        }
    except Exception as e:
        return {"error": str(e)}

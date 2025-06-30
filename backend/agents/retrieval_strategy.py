from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.schemas import MethodSelection, RetrievalSelection
from prompts import METHOD_SELECTION_PROMPT, RETRIEVAL_METHOD_SELECTION_PROMPT

from .state import AgentState


def retrieval_strategy_agent(state: AgentState, model: ChatOpenAI):
    """
    Selects the retrieval method and query transformation strategy.
    """
    try:
        # Choose query method
        method_chain = ChatPromptTemplate.from_template(METHOD_SELECTION_PROMPT) | model.with_structured_output(MethodSelection, method="function_calling")
        method_selection = method_chain.invoke({"question": state.contextualized_query})

        # Choose retriever method(s)
        retrieval_selection_chain = ChatPromptTemplate.from_template(RETRIEVAL_METHOD_SELECTION_PROMPT) | model.with_structured_output(RetrievalSelection, method="function_calling")
        retrieval_selection = retrieval_selection_chain.invoke({"question": state.contextualized_query})

        return {
            "retrieval_method": method_selection.method,
            "retrieval_selection": retrieval_selection.dict(),
        }
    except Exception as e:
        return {"error": str(e)}

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.config.settings import Configuration
from src.schemas.core_types import AgentState


class QueryComplexity(BaseModel):
    reasoning_required: bool = Field(description="Indicates if the query requires multi-step legal reasoning to answer (e.g., interpreting statutes or synthesizing guidance).")
    multi_hop_needed: bool = Field(description="Indicates if the query requires connecting information across multiple sources, jurisdictions, or legal domains relevant to NEFAC.org (e.g., federal FOIA rules plus MA state public records law).")
    tool_usage_required: bool = Field(description="Indicates if the query requires external tools, API calls, or database filtering (e.g., FOIA log searches, public records API queries) to answer.")


def analyze_complexity_node(state: AgentState, config: RunnableConfig) -> QueryComplexity:
    """
    Graph node that runs complexity analysis on the incoming AgentState.

    This function uses RunnableConfig for LangGraph Studio compatibility.
    """
    # Get configuration from RunnableConfig
    configuration = Configuration.from_runnable_config(config)

    model = init_chat_model(configuration.analyze_complexity_model)

    # Use prompt from configuration (LangGraph Studio compatible)
    complexity_prompt = configuration.complexity_analysis_prompt

    prompt = ChatPromptTemplate(
        [
            ("system", complexity_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "Query to analyze: {query}"),
        ]
    )
    response = (prompt | model.with_structured_output(QueryComplexity)).invoke({"query": state["contextualized_query"], "chat_history": state["summarized_messages"]})
    return QueryComplexity.model_validate(response)

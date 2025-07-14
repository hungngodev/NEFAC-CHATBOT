from typing import ClassVar, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.core.agents.query_translation.contextual_strategy import contextual_strategy
from src.core.agents.query_translation.decomposition import decomposition
from src.core.agents.query_translation.factual_strategy import factual_strategy
from src.core.agents.query_translation.hyde import hyde
from src.core.agents.query_translation.multi_query import multi_query
from src.core.agents.query_translation.step_back import step_back
from src.schemas.core_types import AgentState

METHOD_SELECTION_PROMPT = """Analyze the question and choose the best query transformation strategy:
1. multiquery - Use for ambiguous or open-ended questions where multiple interpretations or perspectives are possible. Generate several diverse queries to cover different angles.
2. ragfusion - Use for complex or multifaceted questions that may require combining results from several distinct queries. Useful when a single query is unlikely to retrieve all relevant information.
3. stepback - Use for specific questions that may benefit from broader context or reframing. Reformulate the question to a more general or foundational one to improve retrieval.
4. decompose - Use for multi-part or compound questions. Break the main question into several sub-questions to ensure comprehensive coverage.
5. hyde - Use for technical, hypothetical, or highly specialized questions. Generate a hypothetical answer or document to guide retrieval.
6. factual - Use for straightforward factual questions where precision and specificity are critical. Reformulate the query to emphasize named entities, dates, legal topics, and relationships, using exact phrases and advanced search operators if appropriate.
7. contextual - Use when the question is missing important background, historical, regional (New England), or legal/policy context. Infer and add the implied context to the query to improve retrieval accuracy.
8. multi-step - Use for complex analytical questions requiring step-by-step reasoning. Breaks down complex queries into sequential reasoning steps, each building on previous context and findings.

Examples of when to use each method:
- "What are the main challenges to public records access in Vermont?" → factual
- "How has the First Amendment been interpreted in New England courts?" → multiquery
- "Explain the evolution of press freedom laws in the US." → ragfusion
- "What is the process for filing a FOIA request and appealing a denial?" → decompose
- "Can I film police during a protest in Massachusetts?" → stepback
- "What if a journalist hypothetically faces a subpoena for confidential sources?" → hyde
- "What are the legal rights around recording public officials in Massachusetts?" (missing context about public spaces, state law, etc.) → contextual
- "Analyze the impact of recent Supreme Court decisions on student free speech rights in public schools." → multi-step
- "What is NEFAC?" → default
Question: {question}
Respond ONLY with the method name."""

llm = ChatOpenAI(model=QUERY_TRANSLATION_MODEL_NAME, temperature=0)


class MethodSelection(BaseModel):
    """Enhanced method selection with metadata."""

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)

    method: Literal[
        "multiquery",
        "decompose",
        "stepback",
        "hyde",
        "ragfusion",
        "factual",
        "contextual",
    ] = Field(description="The selected query construction method.")


method_chain = ChatPromptTemplate.from_template(METHOD_SELECTION_PROMPT) | llm.with_structured_output(MethodSelection)


def route_to_transformer(state: AgentState) -> str:
    """Routes to the appropriate query transformation subgraph based on the retrieval method."""
    question = state["contextualized_query"]
    response = method_chain.invoke({"question": question})
    method = response.method.lower().strip()

    if "multiquery" in method:
        return "multi_query"
    elif "decompose" in method:
        return "decomposition"
    elif "stepback" in method:
        return "step_back"
    elif "hyde" in method:
        return "hyde"
    elif "factual" in method:
        return "factual_strategy"
    elif "contextual" in method:
        return "contextual_strategy"
    else:
        return "multi_query"


workflow = StateGraph(AgentState)

workflow.add_node("multi_query", multi_query)
workflow.add_node("decomposition", decomposition)
workflow.add_node("step_back", step_back)
workflow.add_node("hyde", hyde)
workflow.add_node("factual_strategy", factual_strategy)
workflow.add_node("contextual_strategy", contextual_strategy)

workflow.set_conditional_entry_point(
    route_to_transformer,
    {
        "multi_query": "multi_query",
        "decomposition": "decomposition",
        "step_back": "step_back",
        "hyde": "hyde",
        "factual_strategy": "factual_strategy",
        "contextual_strategy": "contextual_strategy",
    },
)

workflow.add_edge("multi_query", END)
workflow.add_edge("decomposition", END)
workflow.add_edge("step_back", END)
workflow.add_edge("hyde", END)
workflow.add_edge("factual_strategy", END)
workflow.add_edge("contextual_strategy", END)

query_transformer = workflow.compile()

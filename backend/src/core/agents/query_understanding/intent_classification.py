from typing import ClassVar, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field

from src.config.constant import INTENT_CLASSIFICATION_MODEL_NAME
from src.schemas.core_types import AgentState

INTENT_CLASSIFICATION_PROMPT = """Based on the conversation history and the latest user query, determine the user's intent:
- If the user is requesting specific information, documents, resources, or media on any particular topic, classify it as 'info'.
- If the user is asking a general question, making a statement, or seeking broad explanations, classify it as 'general query'.
- If the user is asking for specific facts or relationships that can be directly queried from a structured knowledge graph (e.g., "Who is the author of case X?", "What organizations are related to NEFAC?"), classify it as 'info'.
- If the user is asking for aggregations, counts, or statistical information that can be derived from a structured knowledge graph (e.g., "How many cases are related to FOIA?", "Count the number of organizations NEFAC has partnered with"), classify it as 'info'.
Ignore whether the topic is related to NEFAC's focus areas; focus solely on the structure and intent of the query.

Examples:
- "Do you have any information about Excel?" -> info
- "What is the First Amendment?" -> general query
- "Tell me about NEFAC's mission." -> general query
- "Are there any resources on freedom of speech?" -> info
- "Can you explain freedom of the press?" -> general query
- "Do you have documents on data privacy laws?" -> info
- "Who is the author of the case 'Smith v. Jones'?" -> info
- "What are the relationships between NEFAC and ACLU?" -> info
- "How many cases mention the First Amendment?" -> info
- "Count the number of organizations involved in free speech litigation." -> info

Respond with 'info', 'general'"""


class IntentClassification(BaseModel):
    """Enhanced intent classification"""

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)

    intent: Literal["info", "general"] = Field(description="Classify the user's intent. If they are asking for information that could be found in NEFAC's documents, classify as 'info'. Otherwise, classify as 'general'.")


model = ChatOpenAI(model=INTENT_CLASSIFICATION_MODEL_NAME)


def intent_classification_node(state: AgentState) -> IntentClassification:
    """
    Classify the user's intent based on the query.
    Uses a language model to classify the intent.
    """
    main_chain = ChatPromptTemplate.from_messages(
        [
            ("system", INTENT_CLASSIFICATION_PROMPT),
            ("human", "{query}"),
        ]
    ) | model.with_structured_output(IntentClassification)
    return main_chain.invoke(
        {
            "query": state["user_query"],
        }
    )

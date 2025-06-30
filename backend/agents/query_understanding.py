from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from prompts import CONTEXTUALIZE_PROMPT, INTENT_CLASSIFICATION_PROMPT
from schemas import Entities, IntentClassification
from vector.graph_search import entity_chain

from .state import AgentState


def query_understanding_agent(state: AgentState, model: ChatOpenAI):
    """
    Contextualizes the query and classifies the user's intent.
    """
    try:
        # Contextualize the query
        contextualize_chain = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", CONTEXTUALIZE_PROMPT),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{query}"),
                ]
            )
            | model
            | StrOutputParser()
        )
        contextualized_query = contextualize_chain.invoke(
            {"query": state.query, "chat_history": state.chat_history}
        )

        # Classify intent
        intent_chain = ChatPromptTemplate.from_messages(
            [
                ("system", INTENT_CLASSIFICATION_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{query}"),
            ]
        ) | model.with_structured_output(
            IntentClassification, method="function_calling"
        )
        intent_classification = intent_chain.invoke(
            {"query": contextualized_query, "chat_history": state.chat_history}
        )

        # Extract entities
        entities_raw = entity_chain.invoke({"question": contextualized_query})
        if isinstance(entities_raw, dict):
            entities_obj = Entities(**entities_raw)
        elif isinstance(entities_raw, Entities):
            entities_obj = entities_raw
        else:
            entities_obj = Entities(names=[])  # Fallback

        return {
            "contextualized_query": contextualized_query,
            "intent": intent_classification.intent,
            "entities": entities_obj.names,
        }
    except Exception as e:
        return {"error": str(e)}

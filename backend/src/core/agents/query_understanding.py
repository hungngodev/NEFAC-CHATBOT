from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.config.prompts import CONTEXTUALIZE_PROMPT, INTENT_CLASSIFICATION_PROMPT
from src.core.agents.graph_retrieval import Entities, canonicalize_entities, disambiguate_entities, entity_chain, generate_cypher, get_graph_schema
from src.core.agents.state import AgentState
from src.schemas.main import IntentClassification


def query_understanding_agent(state: AgentState, model: ChatOpenAI):
    """
    Contextualizes the query, classifies the user's intent, and generates graph queries if applicable.
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
        ).with_config(tags=["contextualize_q_chain"])
        contextualized_query = contextualize_chain.invoke({"query": state.query, "chat_history": state.chat_history})

        # Classify intent
        intent_chain = ChatPromptTemplate.from_messages(
            [
                ("system", INTENT_CLASSIFICATION_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{query}"),
            ]
        ) | model.with_structured_output(IntentClassification, method="function_calling")
        intent_classification = intent_chain.invoke({"query": contextualized_query, "chat_history": state.chat_history})

        # Extract entities
        entities_raw = entity_chain.invoke({"question": contextualized_query})
        if isinstance(entities_raw, dict):
            entities_obj = Entities(**entities_raw)
        elif isinstance(entities_raw, Entities):
            entities_obj = entities_raw
        else:
            entities_obj = Entities(names=[])  # Fallback
        entities = canonicalize_entities(entities_obj)
        entities = disambiguate_entities(entities, contextualized_query)

        # Initialize structured_query and statistical_query to None
        structured_query = None
        statistical_query = None

        # Generate Cypher query if intent is for structured or statistical graph query
        if intent_classification.intent == "structured_graph_query" or intent_classification.intent == "statistical_graph_query":
            schema = get_graph_schema()  # Get the graph schema
            generated_cypher = generate_cypher(contextualized_query, entities, schema)
            if intent_classification.intent == "structured_graph_query":
                structured_query = generated_cypher
            else:  # statistical_graph_query
                statistical_query = generated_cypher

        return {
            "contextualized_query": contextualized_query,
            "intent": intent_classification.intent,
            "entities": entities_obj.names,
            "structured_query": structured_query,
            "statistical_query": statistical_query,
        }
    except Exception as e:
        return {"error": str(e)}

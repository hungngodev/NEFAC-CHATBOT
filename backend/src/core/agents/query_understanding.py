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
        # Prepare context: combine summary and session memory
        history_context = state.history_summary or ""
        if state.session_memory:
            memory_text = "\n".join([str(item) for item in state.session_memory])
            history_context = f"{history_context}\nSession Memory:\n{memory_text}"

        # Contextualize the query
        contextualize_chain = (
            ChatPromptTemplate.from_messages(
                [
                    ("system", CONTEXTUALIZE_PROMPT),
                    MessagesPlaceholder(variable_name="history_context"),
                    ("human", "{query}"),
                ]
            )
            | model
            | StrOutputParser()
        ).with_config(tags=["contextualize_q_chain"])
        contextualized_query = contextualize_chain.invoke({"query": state.query, "history_context": history_context})

        # Classify intent
        intent_chain = ChatPromptTemplate.from_messages(
            [
                ("system", INTENT_CLASSIFICATION_PROMPT),
                MessagesPlaceholder(variable_name="history_context"),
                ("human", "{query}"),
            ]
        ) | model.with_structured_output(IntentClassification, method="function_calling")
        intent_classification = intent_chain.invoke({"query": contextualized_query, "history_context": history_context})

        # Extract entities
        entities_raw = entity_chain.invoke({"question": contextualized_query})
        if isinstance(entities_raw, dict):
            # Ensure both names and types are passed if available
            entities_obj = Entities(names=entities_raw.get("names", []), types=entities_raw.get("types", None))
        elif isinstance(entities_raw, Entities):
            entities_obj = entities_raw
        else:
            entities_obj = Entities(names=[], types=None)
        entities = canonicalize_entities(entities_obj)
        entities = disambiguate_entities(entities, contextualized_query)

        # Initialize structured_query and statistical_query to None
        structured_query = None
        statistical_query = None

        # Generate Cypher query if intent is for structured or statistical graph query
        intent = intent_classification.get("intent")
        if intent == "structured_graph_query" or intent == "statistical_graph_query":
            schema = get_graph_schema()  # Get the graph schema
            generated_cypher = generate_cypher(contextualized_query, entities, schema)
            if intent == "structured_graph_query":
                structured_query = generated_cypher
            else:  # statistical_graph_query
                statistical_query = generated_cypher

        return {
            "contextualized_query": contextualized_query,
            "intent": intent,
            "entities": entities_obj.names,
            "structured_query": structured_query,
            "statistical_query": statistical_query,
        }
    except Exception as e:
        return {"error": str(e)}

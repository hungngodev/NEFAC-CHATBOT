import time
from typing import List, Optional, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.config.prompts import CONTEXTUALIZE_PROMPT, INTENT_CLASSIFICATION_PROMPT
from src.core.agents.tools.retrieval.graph_retrieval import Entities, canonicalize_entities, disambiguate_entities, entity_chain, generate_cypher, get_graph_schema
from src.exceptions.agent_exceptions import QueryUnderstandingError, handle_agent_exception
from src.schemas.agent_types import QueryIntent, QueryUnderstandingData, QueryUnderstandingResult, create_error_result, create_success_result
from src.schemas.main import IntentClassification
from src.schemas.state import AgentState
from src.utils.validation import validate_complexity_input


class QueryUnderstandingAgent:
    """
    Query understanding agent with proper typing and error handling.
    """

    def __init__(self):
        self.agent_name = "QueryUnderstanding"

    def process_query(self, state: AgentState, model: ChatOpenAI) -> QueryUnderstandingResult:
        """
        Process and contextualize user query with proper error handling.

        Args:
            state: Current agent state
            model: LLM model for processing

        Returns:
            QueryUnderstandingResult with contextualized query and metadata
        """
        start_time = time.time()

        try:
            # Validate input
            chat_history = []
            for msg in state.messages:
                if hasattr(msg, "content"):
                    chat_history.append(msg.content)

            validation = validate_complexity_input(state.user_query, chat_history)

            # Step 1: Contextualize the query
            contextualized_query = self._contextualize_query(query=validation.query, chat_history=chat_history, model=model)

            # Step 2: Classify intent
            intent = self._classify_intent(query=contextualized_query, chat_history=chat_history, model=model)

            # Step 3: Extract entities
            entities = self._extract_entities(contextualized_query)

            # Step 4: Generate structured queries if needed
            structured_query, statistical_query = self._generate_structured_queries(query=contextualized_query, intent=intent, entities=entities)

            # Create result
            execution_time = (time.time() - start_time) * 1000

            data = QueryUnderstandingData(contextualized_query=contextualized_query, intent=intent, entities=entities, structured_query=structured_query, statistical_query=statistical_query, confidence=0.9)  # High confidence for successful processing

            return create_success_result(data=data, execution_time_ms=execution_time, processing_steps="contextualization,intent_classification,entity_extraction")

        except QueryUnderstandingError:
            # Re-raise our specific errors
            raise
        except Exception as e:
            # Handle unexpected errors
            execution_time = (time.time() - start_time) * 1000
            error = handle_agent_exception(e, self.agent_name, {"query": state.user_query, "processing_step": "unknown"})

            return create_error_result(error=str(error), execution_time_ms=execution_time)

    def _contextualize_query(self, query: str, chat_history: List[str], model: ChatOpenAI) -> str:
        """Contextualize the query using conversation history."""
        try:
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

            # Convert chat history to proper format
            formatted_history = []
            for i, msg in enumerate(chat_history):
                if i % 2 == 0:  # User messages
                    formatted_history.append(("human", msg))
                else:  # Assistant messages
                    formatted_history.append(("assistant", msg))

            contextualized_query = contextualize_chain.invoke({"query": query, "chat_history": formatted_history})

            if not contextualized_query or not contextualized_query.strip():
                # Fallback to original query if contextualization fails
                return query

            return contextualized_query.strip()

        except Exception as e:
            raise QueryUnderstandingError(f"Failed to contextualize query: {e}", query=query, processing_step="contextualization")

    def _classify_intent(self, query: str, chat_history: List[str], model: ChatOpenAI) -> QueryIntent:
        """Classify the intent of the query."""
        try:
            intent_chain = ChatPromptTemplate.from_messages(
                [
                    ("system", INTENT_CLASSIFICATION_PROMPT),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{query}"),
                ]
            ) | model.with_structured_output(IntentClassification, method="function_calling")

            # Convert chat history to proper format
            formatted_history = []
            for i, msg in enumerate(chat_history):
                if i % 2 == 0:  # User messages
                    formatted_history.append(("human", msg))
                else:  # Assistant messages
                    formatted_history.append(("assistant", msg))

            intent_result = intent_chain.invoke({"query": query, "chat_history": formatted_history})

            # Extract intent from result
            if isinstance(intent_result, dict):
                intent_str = intent_result.get("intent", "general_query")
            else:
                intent_str = getattr(intent_result, "intent", "general_query")

            # Convert to enum
            try:
                return QueryIntent(intent_str.lower())
            except ValueError:
                # Fallback to general query if intent not recognized
                return QueryIntent.GENERAL_QUERY

        except Exception as e:
            raise QueryUnderstandingError(f"Failed to classify intent: {e}", query=query, processing_step="intent_classification")

    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities from the query."""
        try:
            entities_raw = entity_chain.invoke({"question": query})

            # Handle different return types
            if isinstance(entities_raw, dict):
                entities_obj = Entities(**entities_raw)
            elif isinstance(entities_raw, Entities):
                entities_obj = entities_raw
            else:
                # Fallback for unexpected types
                entities_obj = Entities(names=[], types=None)

            # Canonicalize and disambiguate entities
            entities = canonicalize_entities(entities_obj)
            entities = disambiguate_entities(entities, query)

            return entities_obj.names if entities_obj.names else []

        except Exception as e:
            # Don't fail the entire process for entity extraction errors
            # Just log and return empty list
            import logging

            logging.warning(f"Entity extraction failed: {e}")
            return []

    def _generate_structured_queries(self, query: str, intent: QueryIntent, entities: List[str]) -> tuple[Optional[str], Optional[str]]:
        """Generate structured queries for graph database if needed."""
        try:
            structured_query = None
            statistical_query = None

            if intent in [QueryIntent.STRUCTURED_GRAPH_QUERY, QueryIntent.STATISTICAL_GRAPH_QUERY]:
                # Create entities object for query generation
                entities_obj = Entities(names=entities, types=None)
                schema = get_graph_schema()
                generated_cypher = generate_cypher(query, entities_obj, schema)

                if intent == QueryIntent.STRUCTURED_GRAPH_QUERY:
                    structured_query = generated_cypher
                else:  # statistical_graph_query
                    statistical_query = generated_cypher

            return structured_query, statistical_query

        except Exception as e:
            # Don't fail for structured query generation errors
            import logging

            logging.warning(f"Structured query generation failed: {e}")
            return None, None


# Create global instance
_query_understanding_agent = QueryUnderstandingAgent()


class QueryUnderstandingAgentOutput(TypedDict):
    contextualized_query: Optional[str]
    intent: Optional[str]
    entities: Optional[List[str]]
    structured_query: Optional[str]
    statistical_query: Optional[str]
    error: Optional[str]


def query_understanding_agent(state: AgentState, model: ChatOpenAI) -> QueryUnderstandingAgentOutput:
    """
    Main interface function - uses the improved agent implementation.
    """
    result = _query_understanding_agent.process_query(state, model)

    if result.is_success:
        return {
            "contextualized_query": result.data.contextualized_query,
            "intent": result.data.intent.value,
            "entities": result.data.entities,
            "structured_query": result.data.structured_query,
            "statistical_query": result.data.statistical_query,
        }
    else:
        return {"error": result.error}

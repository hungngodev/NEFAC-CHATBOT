# import time
# from typing import ClassVar, List, Literal, Optional

# from langchain_core.output_parsers import StrOutputParser
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_openai import ChatOpenAI
# from pydantic import BaseModel, ConfigDict, Field

# from src.config.constant import QUERY_UNDERSTANDING_MODEL_NAME
# from src.config.prompts import CONTEXTUALIZE_PROMPT, INTENT_CLASSIFICATION_PROMPT
# from src.core.agents.tools.retrieval.graph_retrieval import Entities, canonicalize_entities, disambiguate_entities, entity_chain, generate_cypher, get_graph_schema
# from src.exceptions.agent_exceptions import QueryUnderstandingError, handle_agent_exception
# from src.schemas.core_types import AgentState, IntentClassification, QueryIntent, QueryUnderstandingData, QueryUnderstandingResult, create_error_result, create_success_result


# class IntentClassification(BaseModel):
#     """Enhanced intent classification with confidence."""

#     model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)

#     intent: Literal["document request", "general"] = Field(description="Classify the user's intent. If they are asking for information that could be found in NEFAC's documents, classify as 'document request'. Otherwise, classify as 'general'.")


# class QueryUnderstandingAgent:
#     def __init__(self):
#         self.model = ChatOpenAI(model=QUERY_UNDERSTANDING_MODEL_NAME)

#     def process_query(self, state: AgentState) -> QueryUnderstandingResult:
#         start_time = time.time()

#         try:

#             contextualize_chain = (
#                 ChatPromptTemplate.from_messages(
#                     [
#                         ("system", CONTEXTUALIZE_PROMPT),
#                         MessagesPlaceholder(variable_name="chat_history"),
#                         ("human", "{query}"),
#                     ]
#                 )
#                 | self.model
#                 | StrOutputParser()
#             ).with_config(tags=["contextualize_q_chain"])

#             contextualized_query = contextualize_chain.invoke({"query": state.user_query, "chat_history": state.messages}).strip()
#             # Step 2: Classify intent
#             intent = self._classify_intent(query=contextualized_query, chat_history=state.messages7)

#             # Step 3: Extract entities
#             entities = self._extract_entities(contextualized_query)

#             # Step 4: Generate structured queries if needed
#             structured_query, statistical_query = self._generate_structured_queries(query=contextualized_query, intent=intent, entities=entities)

#             # Create result
#             execution_time = (time.time() - start_time) * 1000

#             data = QueryUnderstandingData(contextualized_query=contextualized_query, intent=intent, entities=entities, structured_query=structured_query, statistical_query=statistical_query, confidence=0.9)  # High confidence for successful processing

#             return create_success_result(data=data, execution_time_ms=execution_time, processing_steps="contextualization,intent_classification,entity_extraction")

#         except QueryUnderstandingError:
#             # Re-raise our specific errors
#             raise
#         except Exception as e:
#             # Handle unexpected errors
#             execution_time = (time.time() - start_time) * 1000
#             error = handle_agent_exception(e, self.agent_name, {"query": state.user_query, "processing_step": "unknown"})

#             return create_error_result(error=str(error), execution_time_ms=execution_time)

#     def _contextualize_query(self, query: str, chat_history: List[str]) -> str:
#         """Contextualize the query using conversation history."""
#         try:
#             contextualize_chain = (
#                 ChatPromptTemplate.from_messages(
#                     [
#                         ("system", CONTEXTUALIZE_PROMPT),
#                         MessagesPlaceholder(variable_name="chat_history"),
#                         ("human", "{query}"),
#                     ]
#                 )
#                 | self.model
#                 | StrOutputParser()
#             ).with_config(tags=["contextualize_q_chain"])

#             contextualized_query = contextualize_chain.invoke({"query": query, "chat_history": chat_history})
#             return contextualized_query.strip()
#         except Exception as e:
#             raise QueryUnderstandingError(f"Failed to contextualize query: {e}", query=query, processing_step="contextualization")

#     def _classify_intent(self, query: str, chat_history: List[str]) -> QueryIntent:
#         """Classify the intent of the query."""
#         try:
#             intent_chain = ChatPromptTemplate.from_messages(
#                 [
#                     ("system", INTENT_CLASSIFICATION_PROMPT),
#                     MessagesPlaceholder(variable_name="chat_history"),
#                     ("human", "{query}"),
#                 ]
#             ) | self.model.with_structured_output(IntentClassification, method="function_calling")

#             intent_result = intent_chain.invoke({"query": query, "chat_history": chat_history})
#             intent_str = getattr(intent_result, "intent", "general_query")
#             try:
#                 return QueryIntent(intent_str.lower())
#             except ValueError:
#                 return QueryIntent.GENERAL_QUERY

#         except Exception as e:
#             raise QueryUnderstandingError(f"Failed to classify intent: {e}", query=query, processing_step="intent_classification")

#     def _extract_entities(self, query: str) -> List[str]:
#         """Extract entities from the query."""
#         try:
#             entities_raw = entity_chain.invoke({"question": query})

#             # Handle different return types
#             if isinstance(entities_raw, dict):
#                 entities_obj = Entities(**entities_raw)
#             elif isinstance(entities_raw, Entities):
#                 entities_obj = entities_raw
#             else:
#                 # Fallback for unexpected types
#                 entities_obj = Entities(names=[], types=None)

#             # Canonicalize and disambiguate entities
#             entities = canonicalize_entities(entities_obj)
#             entities = disambiguate_entities(entities, query)

#             return entities_obj.names if entities_obj.names else []

#         except Exception as e:
#             # Don't fail the entire process for entity extraction errors
#             # Just log and return empty list
#             import logging

#             logging.warning(f"Entity extraction failed: {e}")
#             return []

#     def _generate_structured_queries(self, query: str, intent: QueryIntent, entities: List[str]) -> tuple[Optional[str], Optional[str]]:
#         """Generate structured queries for graph database if needed."""
#         try:
#             structured_query = None
#             statistical_query = None

#             if intent in [QueryIntent.STRUCTURED_GRAPH_QUERY, QueryIntent.STATISTICAL_GRAPH_QUERY]:
#                 # Create entities object for query generation
#                 entities_obj = Entities(names=entities, types=None)
#                 schema = get_graph_schema()
#                 generated_cypher = generate_cypher(query, entities_obj, schema)

#                 if intent == QueryIntent.STRUCTURED_GRAPH_QUERY:
#                     structured_query = generated_cypher
#                 else:  # statistical_graph_query
#                     statistical_query = generated_cypher

#             return structured_query, statistical_query

#         except Exception as e:
#             # Don't fail for structured query generation errors
#             import logging

#             logging.warning(f"Structured query generation failed: {e}")
#             return None, None


# INTENT_CLASSIFICATION_PROMPT = """Based on the conversation history and the latest user query, determine the user's intent:
# - If the user is requesting specific information, documents, resources, or media on any particular topic, classify it as 'document request'.
# - If the user is asking a general question, making a statement, or seeking broad explanations, classify it as 'general query'.
# - If the user is asking for specific facts or relationships that can be directly queried from a structured knowledge graph (e.g., "Who is the author of case X?", "What organizations are related to NEFAC?"), classify it as 'structured_graph_query'.
# - If the user is asking for aggregations, counts, or statistical information that can be derived from a structured knowledge graph (e.g., "How many cases are related to FOIA?", "Count the number of organizations NEFAC has partnered with"), classify it as 'statistical_graph_query'.
# Ignore whether the topic is related to NEFAC's focus areas; focus solely on the structure and intent of the query.

# Examples:
# - "Do you have any information about Excel?" -> document request
# - "What is the First Amendment?" -> general query
# - "Tell me about NEFAC's mission." -> general query
# - "Are there any resources on freedom of speech?" -> document request
# - "Can you explain freedom of the press?" -> general query
# - "Do you have documents on data privacy laws?" -> document request
# - "Who is the author of the case 'Smith v. Jones'?" -> structured_graph_query
# - "What are the relationships between NEFAC and ACLU?" -> structured_graph_query
# - "How many cases mention the First Amendment?" -> statistical_graph_query
# - "Count the number of organizations involved in free speech litigation." -> statistical_graph_query

# Respond with 'document request', 'general query', 'structured_graph_query', or 'statistical_graph_query'."""

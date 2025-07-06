import time
from typing import List, Optional, TypedDict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from src.config.prompts import FINAL_PROMPT, GENERAL_PROMPT
from src.exceptions.agent_exceptions import GenerationError, handle_agent_exception
from src.schemas.core_types import AgentState, GenerationData, GenerationResult, QueryIntent, create_error_result, create_success_result
from src.utils.validation import validate_generation_input


class GeneratorAgent:
    """
    Answer generation agent with proper typing and error handling.
    """

    def __init__(self):
        self.agent_name = "Generator"

    def generate_answer(self, state: AgentState, model: ChatOpenAI) -> GenerationResult:
        """
        Generate final answer from retrieved context.

        Args:
            state: Current agent state with query and retrieved documents
            model: LLM model for generation

        Returns:
            GenerationResult with generated answer and metadata
        """
        start_time = time.time()

        try:
            # Extract and validate input
            query = state.contextualized_query or state.user_query
            context = self._extract_context(state)
            intent = self._determine_intent(state)

            # Validate input
            validation = validate_generation_input(query=query, context=context, intent=intent.value if intent else None)

            # Convert messages to chat history
            chat_history = self._extract_chat_history(state)

            # Generate answer based on intent
            answer, model_info = self._generate_with_intent(query=validation.query, context=validation.context, intent=validation.intent, chat_history=chat_history, model=model, state=state)

            # Extract sources and calculate metrics
            sources_cited = self._extract_sources(state)
            word_count = len(answer.split()) if answer else 0

            # Calculate confidence based on context quality and answer length
            confidence = self._calculate_confidence(answer=answer, context=validation.context, sources_count=len(sources_cited))

            # Create result
            execution_time = (time.time() - start_time) * 1000

            data = GenerationData(
                answer=answer, confidence_score=confidence, sources_cited=sources_cited, word_count=word_count, generation_time_ms=execution_time, prompt_tokens=model_info.get("prompt_tokens"), completion_tokens=model_info.get("completion_tokens"), model_used=model_info.get("model_name")
            )

            return create_success_result(data=data, execution_time_ms=execution_time, intent=validation.intent.value, context_length=str(len(validation.context)))

        except GenerationError:
            raise
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error = handle_agent_exception(e, self.agent_name, {"query": getattr(state, "user_query", "unknown"), "context_available": bool(getattr(state, "retrieved_docs", None))})

            return create_error_result(error=str(error), execution_time_ms=execution_time)

    def _extract_context(self, state: AgentState) -> str:
        """Extract context from state."""
        if hasattr(state, "retrieved_docs") and state.retrieved_docs:
            return state.retrieved_docs

        if hasattr(state, "all_retrieved_docs") and state.all_retrieved_docs:
            context_parts = []
            for doc in state.all_retrieved_docs:
                if hasattr(doc, "page_content"):
                    context_parts.append(doc.page_content)
                else:
                    context_parts.append(str(doc))
            return "\n\n".join(context_parts)

        return ""

    def _determine_intent(self, state: AgentState) -> QueryIntent:
        """Determine query intent from state."""
        if hasattr(state, "intent") and state.intent:
            try:
                return QueryIntent(state.intent.lower())
            except ValueError:
                pass
        return QueryIntent.GENERAL_QUERY

    def _extract_chat_history(self, state: AgentState) -> List[tuple]:
        """Extract and format chat history."""
        chat_history = []

        if hasattr(state, "messages") and state.messages:
            for i, msg in enumerate(state.messages):
                if hasattr(msg, "content"):
                    if i % 2 == 0:
                        chat_history.append(("human", msg.content))
                    else:
                        chat_history.append(("assistant", msg.content))

        return chat_history

    def _generate_with_intent(self, query: str, context: str, intent: QueryIntent, chat_history: List[tuple], model: ChatOpenAI, state: AgentState) -> tuple[str, dict]:
        """Generate answer based on query intent."""
        try:
            # Select appropriate prompt based on intent
            if intent == QueryIntent.DOCUMENT_REQUEST:
                prompt_template = FINAL_PROMPT
            else:
                prompt_template = GENERAL_PROMPT

            # Create prompt
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", prompt_template),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{question}"),
                ]
            )

            # Create chain
            chain = prompt | model

            # Prepare context variables
            extracted_info = getattr(state, "extracted_info", None)
            citations = getattr(state, "citations", [])

            # Generate answer
            response = chain.invoke(
                {
                    "question": query,
                    "context": context,
                    "chat_history": chat_history,
                    "extracted_info": extracted_info,
                    "citations": citations,
                }
            )

            # Extract answer content
            if hasattr(response, "content"):
                answer = response.content
            else:
                answer = str(response)

            # Extract model information
            model_info = {
                "model_name": getattr(model, "model_name", "unknown"),
                "prompt_tokens": getattr(response, "usage", {}).get("prompt_tokens"),
                "completion_tokens": getattr(response, "usage", {}).get("completion_tokens"),
            }

            return answer, model_info

        except Exception as e:
            raise GenerationError(f"Failed to generate answer: {e}", query=query, context_length=len(context), model_name=getattr(model, "model_name", "unknown"))

    def _extract_sources(self, state: AgentState) -> List[str]:
        """Extract source citations from state."""
        sources = []

        if hasattr(state, "citations") and state.citations:
            for citation in state.citations:
                if isinstance(citation, dict):
                    source = citation.get("source_url") or citation.get("title") or citation.get("source")
                    if source:
                        sources.append(str(source))
                else:
                    sources.append(str(citation))

        if hasattr(state, "all_retrieved_docs") and state.all_retrieved_docs:
            for doc in state.all_retrieved_docs:
                if hasattr(doc, "metadata") and doc.metadata:
                    source = doc.metadata.get("source_url") or doc.metadata.get("source")
                    if source and source not in sources:
                        sources.append(source)

        return sources

    def _calculate_confidence(self, answer: str, context: str, sources_count: int) -> float:
        """Calculate confidence score for the generated answer."""
        confidence = 0.5  # Base confidence

        if answer and len(answer.split()) > 10:
            confidence += 0.2

        if context and len(context) > 100:
            confidence += 0.2

        if sources_count > 0:
            confidence += 0.1

        if answer and len(answer.split()) < 5:
            confidence -= 0.2

        return max(0.0, min(1.0, confidence))


# Create global instance
_generator_agent = GeneratorAgent()


class GeneratorAgentOutput(TypedDict):
    answer: str
    error: Optional[str]


def generator_agent(state: AgentState, model: ChatOpenAI) -> GeneratorAgentOutput:
    """
    Main interface function - uses the improved agent implementation.
    """
    result = _generator_agent.generate_answer(state, model)

    if result.is_success:
        return {"answer": result.data.answer}
    else:
        return {"answer": "I apologize, but I couldn't generate an answer.", "error": result.error}

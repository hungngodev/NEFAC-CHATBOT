"""
Enhanced Runnable Agent Implementations
Demonstrates how to implement agents using LangChain Runnable interface for better composability.
"""

from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI

from src.schemas.agent_protocols import RunnableComplexityAnalyzerProtocol, RunnableContextualizerProtocol, RunnableGeneratorProtocol, RunnableRetrieverProtocol
from src.schemas.agent_types import GenerationResult, QueryComplexityResult, QueryUnderstandingResult, RetrievalResult
from src.schemas.langgraph_types import AgentRunnable, GraphState, RetrieverRunnable
from src.schemas.state import AgentState


class RunnableComplexityAnalyzer:
    """
    Complexity analyzer that implements Runnable interface for better chain composition.
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def analyze_complexity(self, query: str, chat_history: Optional[List[BaseMessage]] = None) -> QueryComplexityResult:
        """Analyze query complexity and return routing decision."""
        # Implementation would go here - simplified for demo
        complexity_score = len(query.split()) / 50.0  # Simple heuristic
        complexity_score = min(complexity_score, 1.0)

        from src.schemas.agent_types import ComplexityCategory, QueryComplexityData, RecommendedRoute, create_success_result

        data = QueryComplexityData(
            complexity_score=complexity_score,
            reasoning_required=complexity_score > 0.5,
            multi_hop_needed=complexity_score > 0.7,
            tool_usage_required=complexity_score > 0.8,
            confidence=0.8,
            linguistic_complexity=complexity_score * 0.8,
            domain_complexity=complexity_score * 0.9,
            reasoning_complexity=complexity_score,
            temporal_complexity=complexity_score * 0.6,
            complexity_category=ComplexityCategory.COMPLEX if complexity_score > 0.7 else ComplexityCategory.SIMPLE,
            recommended_route=RecommendedRoute.REACT if complexity_score > 0.7 else RecommendedRoute.RETRIEVER,
            reasoning=f"Query complexity assessed as {complexity_score:.2f} based on length and structure",
        )

        return create_success_result(data)

    def as_runnable(self) -> Runnable[Dict[str, Any], Dict[str, Any]]:
        """Return as LangChain Runnable for chain composition."""

        def _analyze(input_dict: Dict[str, Any]) -> Dict[str, Any]:
            query = input_dict.get("query", "")
            chat_history = input_dict.get("chat_history", [])

            result = self.analyze_complexity(query, chat_history)

            return {"complexity_result": result, "complexity_score": result.data.complexity_score if result.is_success else 0.5, "recommended_route": result.data.recommended_route if result.is_success else "retriever_worker"}

        return RunnableLambda(_analyze)


class RunnableContextualizer:
    """
    Contextualizer that implements Runnable interface for better chain composition.
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def process_query(self, state: AgentState, model: ChatOpenAI) -> QueryUnderstandingResult:
        """Process and contextualize user query."""
        # Implementation would go here - simplified for demo
        from src.schemas.agent_types import QueryIntent, QueryUnderstandingData, create_success_result

        data = QueryUnderstandingData(contextualized_query=state.user_query, intent=QueryIntent.GENERAL_QUERY, entities=[], confidence=0.8)  # Simplified

        return create_success_result(data)

    def as_runnable(self) -> AgentRunnable:
        """Return as LangChain Runnable for chain composition."""

        def _process(state: GraphState) -> GraphState:
            # Convert GraphState to AgentState
            agent_state = AgentState(user_query=state["user_query"], messages=state.get("messages", []), user_id=state.get("user_id", "default"))

            result = self.process_query(agent_state, self.llm)

            if result.is_success:
                state["contextualized_query"] = result.data.contextualized_query
                state["intent"] = result.data.intent
                state["entities"] = result.data.entities
            else:
                state["error"] = result.error

            return state

        return RunnableLambda(_process)


class RunnableRetriever:
    """
    Retriever that implements Runnable interface and provides BaseRetriever access.
    """

    def __init__(self, base_retriever: BaseRetriever):
        self._base_retriever = base_retriever

    def retrieve_documents(self, state: AgentState) -> RetrievalResult:
        """Retrieve relevant documents based on query."""
        try:
            query = state.contextualized_query or state.user_query
            documents = self._base_retriever.get_relevant_documents(query)

            from src.schemas.agent_types import RetrievalData, RetrievalMethod, create_success_result

            data = RetrievalData(documents=documents, retrieval_methods_used=[RetrievalMethod.DENSE], total_documents_found=len(documents), documents_after_deduplication=len(documents), deduplication_applied=False, reranking_applied=False, query_expansion_applied=False)

            return create_success_result(data)

        except Exception as e:
            from src.schemas.agent_types import create_error_result

            return create_error_result(str(e))

    def get_base_retriever(self) -> BaseRetriever:
        """Get the underlying LangChain retriever."""
        return self._base_retriever

    def as_runnable(self) -> RetrieverRunnable:
        """Return as LangChain Runnable for chain composition."""

        def _retrieve(query: str) -> List[Document]:
            return self._base_retriever.get_relevant_documents(query)

        return RunnableLambda(_retrieve)


class RunnableGenerator:
    """
    Generator that implements Runnable interface for better chain composition.
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def generate_answer(self, state: AgentState, model: ChatOpenAI) -> GenerationResult:
        """Generate final answer from retrieved context."""
        try:
            # Simplified generation logic
            query = state.contextualized_query or state.user_query
            documents = getattr(state, "all_retrieved_docs", [])

            if documents:
                context = "\n".join([doc.page_content for doc in documents[:3]])
                answer = f"Based on the available information: {context[:200]}... I can help answer: {query}"
            else:
                answer = f"I can help with your question: {query}"

            from src.schemas.agent_types import GenerationData, create_success_result

            data = GenerationData(answer=answer, confidence_score=0.8, sources=[doc.metadata.get("source", "Unknown") for doc in documents[:3]], reasoning="Generated based on retrieved context")

            return create_success_result(data)

        except Exception as e:
            from src.schemas.agent_types import create_error_result

            return create_error_result(str(e))

    def as_runnable(self) -> Runnable[GraphState, str]:
        """Return as LangChain Runnable for chain composition."""

        def _generate(state: GraphState) -> str:
            # Convert GraphState to AgentState
            agent_state = AgentState(user_query=state["user_query"], contextualized_query=state.get("contextualized_query"), all_retrieved_docs=state.get("all_retrieved_docs", []), messages=state.get("messages", []), user_id=state.get("user_id", "default"))

            result = self.generate_answer(agent_state, self.llm)

            if result.is_success:
                return result.data.answer
            else:
                return f"Error generating answer: {result.error}"

        return RunnableLambda(_generate)


# Factory functions for creating runnable agents
def create_runnable_complexity_analyzer(llm: ChatOpenAI) -> RunnableComplexityAnalyzerProtocol:
    """Create a runnable complexity analyzer."""
    return RunnableComplexityAnalyzer(llm)


def create_runnable_contextualizer(llm: ChatOpenAI) -> RunnableContextualizerProtocol:
    """Create a runnable contextualizer."""
    return RunnableContextualizer(llm)


def create_runnable_retriever(base_retriever: BaseRetriever) -> RunnableRetrieverProtocol:
    """Create a runnable retriever."""
    return RunnableRetriever(base_retriever)


def create_runnable_generator(llm: ChatOpenAI) -> RunnableGeneratorProtocol:
    """Create a runnable generator."""
    return RunnableGenerator(llm)


# Example of creating a complete runnable chain
def create_agent_chain(complexity_analyzer: RunnableComplexityAnalyzerProtocol, contextualizer: RunnableContextualizerProtocol, retriever: RunnableRetrieverProtocol, generator: RunnableGeneratorProtocol) -> Runnable[Dict[str, Any], str]:
    """
    Create a complete agent processing chain using Runnable composition.
    """

    # Create the chain using LangChain's pipe operator
    chain = complexity_analyzer.as_runnable() | contextualizer.as_runnable() | generator.as_runnable()

    return chain

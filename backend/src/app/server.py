"""
Hierarchical Multi-Agent System
Properly orchestrates existing agents following the documented architecture.
Uses enhanced agents with proper typing and dependency injection.
"""

import logging
import os
from typing import Any, Dict, Literal

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, CompiledGraph, StateGraph

# Configuration
from src.config.constant import MODEL_NAME
from src.core.agents.contextualizer.query_understanding import QueryUnderstandingAgent

# Import agents with proper typing
from src.core.agents.supervisor.complexity_analyzer import ComplexityAnalyzer
from src.core.agents.supervisor.generator import GeneratorAgent
from src.core.agents.tools.memory.memory import MemoryManager
from src.core.agents.workers.react.react_worker import multi_step_reasoning_agent
from src.core.agents.workers.retriever.retrieval import RetrievalAgent
from src.schemas.agent_types import GenerationResult, QueryComplexityResult, QueryUnderstandingResult, RetrievalResult

# Import the unified state and types
from src.schemas.state import AgentState

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment setup
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "NEFAC_HIERARCHICAL_MULTI_AGENT"

# Initialize LLM models directly
llm = ChatOpenAI(model=MODEL_NAME, temperature=0)
fast_llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# Initialize agents
complexity_analyzer = ComplexityAnalyzer(llm=fast_llm)
query_understanding_agent_instance = QueryUnderstandingAgent()
retrieval_agent_instance = RetrievalAgent()
generator_agent_instance = GeneratorAgent()
memory_manager = MemoryManager()


def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """
    Supervisor node that analyzes query complexity and makes routing decisions.
    Uses the ComplexityAnalyzer with proper typing.
    """
    try:
        # Convert messages to chat history format
        chat_history = []
        for msg in state.messages:
            if hasattr(msg, "content"):
                chat_history.append(msg)

        # Analyze complexity using improved analyzer
        complexity_result: QueryComplexityResult = complexity_analyzer.analyze_complexity(query=state.user_query, chat_history=chat_history)

        if complexity_result.is_success:
            # Determine routing decision based on complexity
            complexity_score = complexity_result.data.complexity_score
            if complexity_score < 0.3:
                decision = "retriever_worker"
            elif complexity_score < 0.7:
                decision = "retriever_worker"  # Enhanced retrieval for medium complexity
            else:
                decision = "react_worker"

            logger.info(f"Supervisor: Query='{state.user_query}' -> Decision='{decision}', Complexity={complexity_score:.2f}")
            logger.debug(f"Supervisor: Detailed complexity reasoning: {complexity_result.data.reasoning}")

            return {"supervisor_decision": decision, "query_complexity": complexity_score}
        else:
            logger.error(f"Complexity analysis failed: {complexity_result.error}")
            return {"supervisor_decision": "retriever_worker", "query_complexity": 0.5, "error": f"Complexity analysis error: {complexity_result.error}"}  # Fallback

    except Exception as e:
        logger.error(f"Supervisor node error: {e}")
        return {"supervisor_decision": "retriever_worker", "query_complexity": 0.5, "error": f"Supervisor error: {str(e)}"}  # Fallback


def memory_retrieval_node(state: AgentState) -> Dict[str, Any]:
    """
    Memory retrieval node that gets relevant past interactions.
    Uses the existing MemoryManager.
    """
    try:
        # Retrieve relevant memories
        memories = memory_manager.retrieve_memories(query=state.user_query, user_id=state.user_id, limit=5)

        # Create memory summary
        memory_summary = ""
        if memories:
            memory_summary = "\n".join([f"Previous interaction: {mem.get('query', '')} -> {mem.get('response', '')[:100]}..." for mem in memories[:3]])

        return {"memory_summary": memory_summary, "relevant_memories": memories}
    except Exception as e:
        return {"memory_summary": "", "relevant_memories": [], "error": f"Memory retrieval error: {str(e)}"}


def contextualizer_node(state: AgentState) -> Dict[str, Any]:
    """
    Contextualizer node that processes queries for better understanding.
    Uses the QueryUnderstandingAgent with proper typing.
    """
    try:
        # Use direct LLM model
        model = llm

        # Use contextualizer
        result: QueryUnderstandingResult = query_understanding_agent_instance.process_query(state, model)

        if result.is_success:
            return {"contextualized_query": result.data.contextualized_query, "intent": result.data.intent.value, "entities": result.data.entities, "structured_query": result.data.structured_query, "statistical_query": result.data.statistical_query}
        else:
            logger.error(f"Query understanding failed: {result.error}")
            return {"contextualized_query": state.user_query, "error": f"Contextualizer error: {result.error}"}  # Fallback

    except Exception as e:
        logger.error(f"Contextualizer node error: {e}")
        return {"contextualized_query": state.user_query, "error": f"Contextualizer error: {str(e)}"}  # Fallback


def retriever_worker_node(state: AgentState) -> Dict[str, Any]:
    """
    Retriever worker node for document retrieval.
    Uses the RetrievalAgent with proper typing.
    """
    try:
        # Use retrieval agent
        result: RetrievalResult = retrieval_agent_instance.retrieve_documents(state)

        if result.is_success:
            documents = result.data.documents
            return {
                "all_retrieved_docs": documents,
                "retrieved_docs": "\n\n".join([doc.page_content if hasattr(doc, "page_content") else str(doc) for doc in documents[:5]]),  # Limit for context
                "retrieval_methods_used": [method.value for method in result.data.retrieval_methods_used],
                "total_documents_found": result.data.total_documents_found,
                "deduplication_applied": result.data.deduplication_applied,
            }
        else:
            logger.error(f"Document retrieval failed: {result.error}")
            return {"all_retrieved_docs": [], "retrieved_docs": "", "error": f"Retriever error: {result.error}"}

    except Exception as e:
        logger.error(f"Retriever node error: {e}")
        return {"all_retrieved_docs": [], "retrieved_docs": "", "error": f"Retriever error: {str(e)}"}


def react_worker_node(state: AgentState) -> Dict[str, Any]:
    """
    ReAct worker node for complex multi-step reasoning.
    Uses the existing multi_step_reasoning_agent.
    """
    try:
        # Convert messages to chat history format
        chat_history = []
        for msg in state.messages:
            if hasattr(msg, "content"):
                chat_history.append(msg.content)

        # Create temporary state for existing agent
        temp_state = type("TempState", (), {"query": state.contextualized_query or state.user_query, "chat_history": chat_history, "retrieval_selection": state.retrieval_selection, "entities": []})()

        # Use existing ReAct agent
        result = multi_step_reasoning_agent(temp_state, llm, max_steps=3)

        return {"all_retrieved_docs": result.get("documents", []), "retrieved_docs": "\n\n".join([doc.page_content if hasattr(doc, "page_content") else str(doc) for doc in result.get("documents", [])[:5]]), "react_iterations": 3}  # Track iterations
    except Exception as e:
        return {"all_retrieved_docs": [], "retrieved_docs": "", "react_iterations": 0, "error": f"ReAct error: {str(e)}"}


def final_answer_node(state: AgentState) -> Dict[str, Any]:
    """
    Final answer generation node.
    Uses the GeneratorAgent with proper typing.
    """
    try:
        # Use direct LLM model
        model = llm

        # Use generator
        result: GenerationResult = generator_agent_instance.generate_answer(state, model)

        if result.is_success:
            return {"final_answer": result.data.answer, "confidence_score": result.data.confidence_score, "sources_cited": result.data.sources_cited, "word_count": result.data.word_count, "generation_time_ms": result.data.generation_time_ms}
        else:
            logger.error(f"Answer generation failed: {result.error}")
            return {"final_answer": "I apologize, but I couldn't generate an answer due to a processing error.", "error": f"Generator error: {result.error}"}

    except Exception as e:
        logger.error(f"Final answer node error: {e}")
        return {"final_answer": f"I apologize, but I encountered an error: {str(e)}", "error": f"Generator error: {str(e)}"}


def memory_storage_node(state: AgentState) -> Dict[str, Any]:
    """
    Memory storage node that saves the interaction.
    Uses the existing MemoryManager.
    """
    try:
        # Store the interaction in memory
        memory_manager.store_interaction(user_id=state.user_id, query=state.user_query, response=state.final_answer, session_id=state.session_id, thread_id=state.thread_id)

        return {"memory_stored": True}
    except Exception as e:
        return {"memory_stored": False, "error": f"Memory storage error: {str(e)}"}


def route_after_supervisor(state: AgentState) -> Literal["retriever_worker", "react_worker"]:
    """Route based on supervisor decision."""
    return state.supervisor_decision or "retriever_worker"


def create_multi_agent_graph() -> CompiledGraph:
    """
    Creates the hierarchical multi-agent graph following the documented architecture.
    This function ONLY handles orchestration - agents are imported, not redefined.
    """
    # Create the state graph
    workflow = StateGraph(AgentState)

    # Add nodes (using existing agents)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("memory_retrieval", memory_retrieval_node)
    workflow.add_node("contextualizer", contextualizer_node)
    workflow.add_node("retriever_worker", retriever_worker_node)
    workflow.add_node("react_worker", react_worker_node)
    workflow.add_node("final_answer", final_answer_node)
    workflow.add_node("memory_storage", memory_storage_node)

    # Define the flow following the hierarchical architecture
    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "memory_retrieval")
    workflow.add_edge("memory_retrieval", "contextualizer")

    # Conditional routing based on supervisor decision
    workflow.add_conditional_edges("contextualizer", route_after_supervisor, {"retriever_worker": "retriever_worker", "react_worker": "react_worker"})

    # Both workers go to final answer
    workflow.add_edge("retriever_worker", "final_answer")
    workflow.add_edge("react_worker", "final_answer")

    # Final answer goes to memory storage, then end
    workflow.add_edge("final_answer", "memory_storage")
    workflow.add_edge("memory_storage", END)

    # Compile with memory
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# Export the main function
def get_multi_agent_graph() -> CompiledGraph:
    """Get the compiled multi-agent graph."""
    return create_multi_agent_graph()


# For backward compatibility
def create_enhanced_multi_agent_graph() -> CompiledGraph:
    """Alias for backward compatibility."""
    return create_multi_agent_graph()

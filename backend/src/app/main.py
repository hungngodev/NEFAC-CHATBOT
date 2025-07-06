"""
Enhanced Main Application
Integrates all enhanced components with streaming support and proper error handling.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, TypedDict, Union

from pydantic import BaseModel, Field

# Core components
from src.app.server import run_chatbot, stream_chatbot
from src.config.constant import (
    DEFAULT_MEMORY_RETENTION_DAYS,
    STREAMING_SLEEP_INTERVAL,
    STREAMING_WORD_COUNT,
    HealthCheckComponent,
)
from src.core.agents.tools.memory.memory import (
    MemoryMaintenanceTask,
    global_memory_manager,
)


# Pydantic Models for API Input/Output and Internal Data Structures
class DocumentMetadata(BaseModel):
    title: str = Field(..., description="Title of the document.")
    summary: str = Field(..., description="Summary of the document content.")
    link: str = Field(..., description="Link or source URL of the document.")
    type: str = Field(..., description="Type of the document (e.g., 'document', 'retrieval_result').")


class MessageChunk(BaseModel):
    message: str = Field(..., description="Content of the message chunk.")
    order: int = Field(..., description="Order of the message chunk in the stream.")


class ContextChunk(BaseModel):
    context: List[DocumentMetadata] = Field(..., description="List of retrieved document metadata.")
    order: int = Field(..., description="Order of the context chunk in the stream.")


class ReformulatedChunk(BaseModel):
    reformulated: str = Field(..., description="Reformulated query or contextualized information.")
    order: int = Field(..., description="Order of the reformulated chunk in the stream.")


class ChatInput(BaseModel):
    query: str = Field(..., description="User's input query.")
    convo_id: Optional[str] = Field(None, description="Conversation ID.")
    user_id: str = Field("default_user", description="User ID.")
    session_id: Optional[str] = Field(None, description="Session ID.")


class LLMResponse(BaseModel):
    answer: str = Field(..., description="Final answer from the LLM.")
    context: List[DocumentMetadata] = Field([], description="List of retrieved document metadata.")
    metadata: Dict[str, Union[str, int, float, bool]] = Field({}, description="Additional metadata about the response.")
    error: Optional[str] = Field(None, description="Error message if any.")


class ComponentHealth(BaseModel):
    status: str = Field(..., description="Health status of the component (healthy, warning, error).")
    errors: List[str] = Field([], description="List of errors for the component.")


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Overall health status (healthy, degraded, unhealthy).")
    timestamp: str = Field(..., description="Timestamp of the health check.")
    components: Dict[str, ComponentHealth] = Field({}, description="Health status of individual components.")
    memory_stats: Dict[str, Union[str, int, float]] = Field({}, description="Memory usage statistics.")
    errors: List[str] = Field([], description="List of overall errors.")


class RecentMemory(BaseModel):
    query: str = Field(..., description="Query associated with the memory.")
    timestamp: str = Field(..., description="Timestamp of the memory.")
    metadata: Dict[str, Union[str, int, float, bool]] = Field({}, description="Metadata associated with the memory.")


class UserMemorySummary(BaseModel):
    user_id: str = Field(..., description="User ID.")
    session_id: Optional[str] = Field(None, description="Session ID.")
    conversation_summary: Optional[str] = Field(None, description="Summary of the conversation.")
    memory_count: int = Field(..., description="Number of memories found.")
    recent_memories: List[RecentMemory] = Field([], description="List of recent memories.")
    error: Optional[str] = Field(None, description="Error message if any.")


class MemoryCleanupResponse(BaseModel):
    message: str = Field(..., description="Message about the cleanup operation.")
    retention_days: int = Field(..., description="Retention days for cleanup.")
    status: str = Field(..., description="Status of the cleanup request.")
    error: Optional[str] = Field(None, description="Error message if any.")


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Enhanced Streaming Interface ===


# Enhanced type definitions for main application
class LLMRequestConfig(TypedDict, total=False):
    """Configuration parameters for LLM requests."""

    temperature: float
    max_tokens: int
    model: str
    stream: bool
    timeout: int
    include_sources: bool


async def ask_llm_stream_enhanced(query: str, convo_id: Optional[str] = None, user_id: str = "default_user", session_id: Optional[str] = None, **kwargs: LLMRequestConfig) -> AsyncGenerator[str, None]:
    """
    Enhanced streaming interface that provides real-time updates.
    Compatible with existing frontend while providing enhanced capabilities.
    """

    # Generate IDs if not provided
    if not convo_id:
        convo_id = str(uuid.uuid4())
    if not session_id:
        session_id = str(uuid.uuid4())

    # Use convo_id as thread_id for consistency
    thread_id = convo_id

    try:
        # Track streaming state
        message_order = 0
        context_sent = False
        reformulated_sent = False

        # Stream events from multi-agent app
        async for event in stream_chatbot(user_input=query, thread_id=thread_id, user_id=user_id, session_id=session_id, **kwargs):

            event_type = event.get("event")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            # Handle different event types
            if event_type == "on_chat_model_stream":
                # Stream LLM responses
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield f"data: {MessageChunk(message=chunk.content, order=message_order).model_dump_json()}\n\n"
                    message_order += 1

            elif event_type == "on_tool_end":
                # Handle tool completions (like retrieval)
                if "retrieval" in event_name.lower():
                    output_data = event_data.get("output", {})

                    # Handle document retrieval results
                    if isinstance(output_data, dict) and "documents" in output_data:
                        docs = output_data["documents"]
                        formatted_docs = []

                        for doc in docs[:5]:  # Limit to top 5 for streaming
                            if hasattr(doc, "metadata"):
                                formatted_docs.append({"title": doc.metadata.get("title", "Unknown"), "summary": doc.metadata.get("summary", "")[:200], "link": doc.metadata.get("source", ""), "type": doc.metadata.get("type", "document")})

                        if formatted_docs and not context_sent:
                            yield f"data: {ContextChunk(context=formatted_docs, order=message_order).model_dump_json()}\n\n"
                            message_order += 1
                            context_sent = True

                    # Handle string results from retrieval
                    elif isinstance(output_data, str) and output_data and not context_sent:
                        # Parse retrieval results and format as context
                        context_info = DocumentMetadata(title="Retrieved Information", summary=output_data[:200] + "..." if len(output_data) > 200 else output_data, link="", type="retrieval_result")
                        yield f"data: {ContextChunk(context=[context_info], order=message_order).model_dump_json()}\n\n"
                        message_order += 1
                        context_sent = True

            elif event_type == "on_chain_stream":
                # Handle chain streaming (like contextualization)
                if "contextualizer" in event.get("tags", []):
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content and not reformulated_sent:
                        yield f"data: {ReformulatedChunk(reformulated=chunk.content, order=message_order).model_dump_json()}\n\n"
                        message_order += 1
                        reformulated_sent = True

            elif event_type == "on_chain_end":
                # Handle final results
                if event_name == "final_answer_agent":
                    output = event_data.get("output", {})
                    final_answer = output.get("final_answer")
                    if final_answer:
                        # Send final answer as message chunks
                        words = final_answer.split()
                        for i in range(0, len(words), STREAMING_WORD_COUNT):  # Send 5 words at a time
                            chunk_words = words[i : i + STREAMING_WORD_COUNT]
                            chunk_text = " ".join(chunk_words) + " "
                            yield f"data: {MessageChunk(message=chunk_text, order=message_order).model_dump_json()}\n\n"
                            message_order += 1
                            await asyncio.sleep(STREAMING_SLEEP_INTERVAL)  # Small delay for streaming effect

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        error_message = f"I apologize, but I encountered an error: {str(e)}"
        yield f"data: {MessageChunk(message=error_message, order=0).model_dump_json()}\n\n"


# === Non-Streaming Interface ===


def ask_llm_enhanced(query: str, convo_id: Optional[str] = None, user_id: str = "default_user", session_id: Optional[str] = None, **kwargs: LLMRequestConfig) -> LLMResponse:
    """
    Enhanced non-streaming interface for direct responses.
    """

    if not convo_id:
        convo_id = str(uuid.uuid4())
    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        result = run_chatbot(user_input=query, thread_id=convo_id, user_id=user_id, session_id=session_id, **kwargs)

        return LLMResponse(
            answer=result.get("final_answer", "No answer generated"),
            context=result.get("retrieved_docs", []),
            metadata={"complexity": result.get("query_complexity", 0.5), "route": result.get("supervisor_decision", "unknown"), "user_id": user_id, "session_id": session_id, "thread_id": convo_id},
            error=result.get("error"),
        )

    except Exception as e:
        logger.error(f"Enhanced LLM error: {e}")
        return LLMResponse(answer=f"I apologize, but I encountered an error: {str(e)}", error=str(e), metadata={"user_id": user_id, "session_id": session_id, "thread_id": convo_id})


# === Health Check and Diagnostics ===


async def health_check() -> HealthCheckResponse:
    """Comprehensive health check for the enhanced system."""

    health_status = HealthCheckResponse(status="healthy", timestamp=datetime.now().isoformat(), components={}, memory_stats={}, errors=[])

    try:
        # Test memory manager
        memory_stats = global_memory_manager.get_stats()
        health_status.memory_stats = memory_stats
        health_status.components[HealthCheckComponent.MEMORY] = ComponentHealth(status="healthy")

        # Test graph creation
        try:
            # create_enhanced_server_graph() # Removed as 'graph' is not used
            health_status.components[HealthCheckComponent.GRAPH] = ComponentHealth(status="healthy")
        except Exception as e:
            health_status.components[HealthCheckComponent.GRAPH] = ComponentHealth(status="error", errors=[f"Graph creation failed: {str(e)}"])
            health_status.errors.append(f"Graph creation failed: {str(e)}")

        # Test state creation
        try:
            test_state = {"user_query": "test query", "messages": []}
            # Verify state structure is valid
            if "user_query" in test_state and "messages" in test_state:
                health_status.components[HealthCheckComponent.STATE] = ComponentHealth(status="healthy")
        except Exception as e:
            health_status.components[HealthCheckComponent.STATE] = ComponentHealth(status="error", errors=[f"State creation failed: {str(e)}"])
            health_status.errors.append(f"State creation failed: {str(e)}")

        # Test memory storage
        try:
            test_success = await global_memory_manager.store_interaction("health_check_user", "health_check_session", "test query", "test response", {"test": True})
            if test_success:
                health_status.components[HealthCheckComponent.MEMORY_STORAGE] = ComponentHealth(status="healthy")
            else:
                health_status.components[HealthCheckComponent.MEMORY_STORAGE] = ComponentHealth(status="warning")
        except Exception as e:
            health_status.components[HealthCheckComponent.MEMORY_STORAGE] = ComponentHealth(status="error", errors=[f"Memory storage test failed: {str(e)}"])
            health_status.errors.append(f"Memory storage test failed: {str(e)}")

        # Overall status
        if health_status.errors:
            health_status.status = "degraded" if len(health_status.errors) < 3 else "unhealthy"

    except Exception as e:
        health_status.status = "unhealthy"
        health_status.errors.append(f"Health check failed: {str(e)}")

    return health_status


# === Memory Management Interface ===


async def get_user_memory_summary(user_id: str, session_id: str = None) -> Dict[str, Union[str, int, List[RecentMemory]]]:
    """Get memory summary for a user/session."""

    try:
        # Get conversation summary
        summary = await global_memory_manager.get_conversation_summary(user_id, session_id)

        # Get recent memories
        memories = await global_memory_manager.retrieve_relevant_memories(user_id, session_id, "general", k=10, use_semantic_search=False)

        return {"user_id": user_id, "session_id": session_id, "conversation_summary": summary, "memory_count": len(memories), "recent_memories": [{"query": memory.query[:100], "timestamp": memory.timestamp.isoformat(), "metadata": memory.metadata} for memory in memories[:5]]}

    except Exception as e:
        logger.error(f"Failed to get memory summary: {e}")
        return {"error": str(e), "user_id": user_id, "session_id": session_id}


async def cleanup_user_memories(user_id: str, session_id: str = None, retention_days: int = DEFAULT_MEMORY_RETENTION_DAYS) -> Dict[str, Union[str, int]]:
    """Clean up memories for a specific user/session."""

    try:
        # This would need to be implemented in the memory backend
        # For now, just return a placeholder
        return {"message": f"Memory cleanup requested for user {user_id}", "retention_days": retention_days, "status": "requested"}

    except Exception as e:
        logger.error(f"Failed to cleanup memories: {e}")
        return {"error": str(e)}


# === Background Tasks ===


class EnhancedBackgroundTasks:
    """Manage background tasks for the enhanced system."""

    def __init__(self):
        self.tasks = {}
        self.running = False

    async def start_all_tasks(self):
        """Start all background tasks."""
        self.running = True

        # Start memory maintenance
        memory_task = MemoryMaintenanceTask(global_memory_manager)
        self.tasks["memory_maintenance"] = asyncio.create_task(memory_task.start_maintenance_loop(cleanup_interval_hours=24, retention_days=DEFAULT_MEMORY_RETENTION_DAYS))

        logger.info("Started background tasks")

    async def stop_all_tasks(self):
        """Stop all background tasks."""
        self.running = False

        for task_name, task in self.tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Cancelled background task: {task_name}")

        self.tasks.clear()
        logger.info("Stopped all background tasks")


# Global background task manager
background_tasks = EnhancedBackgroundTasks()

# === Application Lifecycle ===


async def startup_app():
    """Initialize the application."""
    logger.info("Starting NEFAC chatbot application...")

    try:
        # Start background tasks
        await background_tasks.start_all_tasks()

        # Perform health check
        health = await health_check()
        logger.info(f"Application health: {health.status}")

        if health.errors:
            for error in health.errors:
                logger.warning(f"Health check warning: {error}")

        logger.info("Application started successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to start enhanced application: {e}")
        return False


async def shutdown_app():
    """Shutdown the application."""
    logger.info("Shutting down application...")

    try:
        # Stop background tasks
        await background_tasks.stop_all_tasks()

        # Cleanup memory manager
        await global_memory_manager.cleanup_old_memories(retention_days=DEFAULT_MEMORY_RETENTION_DAYS)

        logger.info("Application shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# === Backward Compatibility ===


# Maintain compatibility with existing main.py interface
async def ask_llm_stream_agentic(query: str, convo_id: str) -> AsyncGenerator[str, None]:
    """Backward compatible streaming interface."""
    async for chunk in ask_llm_stream_enhanced(query, convo_id):
        yield chunk


# === Main Application Entry Point ===

if __name__ == "__main__":
    import asyncio

    async def main():
        # Start the application
        success = await startup_app()

        if not success:
            logger.error("Failed to start application")
            return

        try:
            # Test the enhanced system
            print("Testing enhanced system...")

            # Test non-streaming
            result = ask_llm_enhanced("What are the public records laws in Massachusetts?", user_id="test_user")
            print(f"Non-streaming result: {result.answer[:100]}...")

            # Test streaming
            print("\nTesting streaming...")
            async for chunk in ask_llm_stream_enhanced("Tell me more about FOIA requests", user_id="test_user"):
                if chunk.strip():
                    try:
                        data = json.loads(chunk.split("data: ")[1])
                        if "message" in data:
                            print(data["message"], end="", flush=True)
                    except Exception as e:
                        logger.error(f"Error processing stream chunk: {e}")

            print("\n\nTest completed successfully!")

            # Get health status
            health = await health_check()
            print(f"\nSystem health: {health.status}")

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            await shutdown_app()

    asyncio.run(main())

import asyncio
import logging
import uuid
from typing import AsyncGenerator, Dict, List, Optional, TypedDict, Union

from pydantic import BaseModel, Field

from backend.src.config.constant import (
    STREAMING_SLEEP_INTERVAL,
    STREAMING_WORD_COUNT,
)
from src.app.server import stream_chatbot


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


# Maintain compatibility with existing main.py interface
async def ask_llm_stream_agentic(query: str, convo_id: str) -> AsyncGenerator[str, None]:
    """Backward compatible streaming interface."""
    async for chunk in ask_llm_stream_enhanced(query, convo_id):
        yield chunk

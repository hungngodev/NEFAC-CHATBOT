# NEFAC Chatbot - Detailed Agent Flow

## Complete Request Flow

### 1. **Entry Point: User Query**
```python
# User submits query through API
POST /chat
{
    "query": "What are the public records laws in Massachusetts?",
    "user_id": "user123",
    "session_id": "session456"
}
```

### 2. **Memory Retrieval Node**
**Purpose**: Retrieve relevant past interactions for context

```python
def memory_retrieval_node(state: AgentState) -> Dict[str, Any]:
    # Retrieve relevant memories using MemoryManager
    memories = memory_manager.retrieve_memories(
        query=state.user_query, 
        user_id=state.user_id, 
        limit=5
    )
    
    # Create memory summary from top 3 most relevant
    memory_summary = "\n".join([mem.content for mem in memories[:3]])
    
    return {
        "memory_context": memory_summary,
        "retrieved_memories": memories
    }
```

**Output**: Memory context and retrieved memories added to state

### 3. **History Length Check Node**
**Purpose**: Manage conversation history and trigger summarization

```python
def check_history_length_node(state: AgentState) -> Dict[str, Any]:
    if len(state.messages) > 10:
        # Summarize conversation history
        summary = summarizer_agent(state)
        return {"history_summary": summary}
    return {}
```

**Output**: History summary if needed

### 4. **Query Understanding Node**
**Purpose**: Contextualize query and extract structured information

```python
def query_understanding_node(state: AgentState) -> Dict[str, Any]:
    understanding_result = query_understanding_agent_instance.understand_query(
        query=state.user_query,
        chat_history=state.chat_history,
        memory_context=getattr(state, "memory_context", "")
    )
    
    return {
        "contextualized_query": understanding_result.data.contextualized_query,
        "intent": understanding_result.data.intent,
        "entities": understanding_result.data.entities,
        "structured_query": understanding_result.data.structured_query,
        "statistical_query": understanding_result.data.statistical_query,
    }
```

**Processing Steps**:
1. **Contextualization**: Converts query to standalone format
2. **Intent Classification**: Determines query type (factual, procedural, etc.)
3. **Entity Extraction**: Identifies legal entities, organizations, cases
4. **Cypher Generation**: Creates graph queries for structured data
5. **Statistical Query**: Generates aggregation queries if needed

**Example Output**:
```python
{
    "contextualized_query": "What are the public records laws in Massachusetts including exemptions and procedures?",
    "intent": "legal_information_request",
    "entities": ["Massachusetts", "public records", "FOIA"],
    "structured_query": "MATCH (s:State {name: 'Massachusetts'})-[:HAS_LAW]->(l:Law {type: 'public_records'}) RETURN l",
    "statistical_query": None
}
```

### 5. **Supervisor Node**
**Purpose**: Analyze query complexity and make routing decisions

```python
def supervisor_node(state: AgentState) -> Dict[str, Any]:
    # Analyze complexity using ComplexityAnalyzer
    complexity_result = complexity_analyzer.analyze_complexity(
        query=state.user_query,
        chat_history=state.messages
    )
    
    complexity_score = complexity_result.data.complexity_score
    
    # Route based on complexity
    if complexity_score < 0.3:
        decision = "retriever_worker"      # Simple retrieval
    elif complexity_score < 0.7:
        decision = "retriever_worker"      # Enhanced retrieval
    else:
        decision = "react_worker"          # Multi-step reasoning
    
    return {
        "supervisor_decision": decision,
        "query_complexity": complexity_score
    }
```

**Complexity Analysis Factors**:
- Query length and structure
- Number of entities mentioned
- Temporal references
- Comparison requirements
- Multi-step reasoning indicators

**Example Routing**:
- **Simple** (0.2): "What is FOIA?" → `retriever_worker`
- **Medium** (0.5): "Compare FOIA laws in MA and RI" → `retriever_worker`
- **Complex** (0.8): "How have public records exemptions evolved across New England states over the past decade?" → `react_worker`

### 6A. **Retriever Worker Node** (Simple/Medium Complexity)
**Purpose**: Direct retrieval with intelligent strategy selection

```python
def retriever_worker_node(state: AgentState) -> Dict[str, Any]:
    # Use enhanced RetrievalAgent with unified system
    retrieval_result = retrieval_agent_instance.retrieve_documents(
        query=state.contextualized_query or state.user_query,
        intent=state.intent,
        entities=state.entities,
        structured_query=state.structured_query,
        statistical_query=state.statistical_query
    )
    
    # Process documents through context processor
    context_state = AgentState(
        query=state.user_query,
        chat_history=state.chat_history,
        documents=retrieval_result.data.documents
    )
    
    processed_context = context_processor_agent(context_state)
    
    return {
        "documents": retrieval_result.data.documents,
        "retrieval_metadata": retrieval_result.data.metadata,
        "extracted_info": processed_context.get("extracted_info"),
        "summarized_content": processed_context.get("summarized_content"),
        "citations": processed_context.get("citations"),
    }
```

**Retrieval Process**:
1. **Strategy Selection**: LLM analyzes query for optimal methods
2. **Ensemble Retrieval**: Combines dense + sparse + graph search
3. **Query Expansion**: Uses graph relationships for entity queries
4. **Deduplication**: Removes duplicate documents with quality preference
5. **Reranking**: Applies Cohere rerank for relevance optimization
6. **Context Processing**: Extracts info, summarizes, and creates citations

**Example Strategy Selection**:
```python
# Query: "Massachusetts public records exemptions"
{
    "methods": ["dense", "sparse"],
    "weights": [0.4, 0.6],
    "reasoning": "Selected sparse for exact legal terms, dense for conceptual understanding",
    "query_expansion": False,
    "rerank": True
}
```

### 6B. **ReAct Worker Node** (High Complexity)
**Purpose**: Multi-step reasoning with iterative retrieval

```python
def react_worker_node(state: AgentState) -> Dict[str, Any]:
    return multi_step_reasoning_agent(state, llm, max_steps=3)

def multi_step_reasoning_agent(state: AgentState, model: ChatOpenAI, max_steps: int = 3):
    current_context = ""
    all_documents = []
    
    for step in range(max_steps):
        # 1. Generate sub-question
        sub_question = sub_question_chain.invoke({
            "question": state.query,
            "context": current_context,
            "history_context": state.history_summary or state.chat_history,
        })
        
        if sub_question == "FINAL_ANSWER":
            break
        
        # 2. Retrieve for sub-question using ensemble retriever
        retrieval_state = AgentState(
            query=sub_question,
            entities=state.entities,
            retrieval_selection=state.retrieval_selection
        )
        
        retrieval_output = ensemble_retriever_tool.retrieve_for_react_agent(retrieval_state)
        retrieved_docs = retrieval_output.get("documents", [])
        
        # 3. Process context
        processed_context = context_processor_agent(AgentState(
            query=state.query,
            documents=retrieved_docs
        ))
        
        all_documents.extend(processed_context.get("documents", []))
        
        # 4. Update context
        doc_contents = "\n\n".join([doc.page_content for doc in processed_context.get("documents", [])])
        current_context += f"\n\n--- Retrieved for '{sub_question}' ---\n{doc_contents}"
    
    # Final synthesis
    final_answer = final_synthesis_chain.invoke({
        "question": state.query,
        "context": current_context,
        "extracted_info": state.extracted_info,
        "citations": state.citations,
    })
    
    return {"answer": final_answer, "documents": all_documents}
```

**ReAct Process Example**:
```
Main Query: "How do Massachusetts and Rhode Island public records laws compare in terms of exemptions and enforcement?"

Step 1: Sub-question: "What are the key exemptions in Massachusetts public records law?"
        → Retrieve MA-specific documents
        → Extract exemption categories

Step 2: Sub-question: "What are the key exemptions in Rhode Island public records law?"
        → Retrieve RI-specific documents  
        → Extract exemption categories

Step 3: Sub-question: "How do enforcement mechanisms differ between these states?"
        → Retrieve enforcement procedure documents
        → Extract procedural differences

Final: Synthesize comprehensive comparison with citations
```

### 7. **Context Processing** (Both Paths)
**Purpose**: Extract, summarize, and attribute sources

```python
def context_processor_agent(state: AgentState) -> Dict[str, Any]:
    # Step 1: Information Extraction
    extracted_data = []
    for doc in state.documents:
        snippet = doc.page_content[:200] + "..."
        fact = f"Title: {doc.metadata.get('title')} | Source: {doc.metadata.get('source_url')} | Snippet: {snippet}"
        extracted_data.append({
            "title": doc.metadata.get("title"),
            "source_url": doc.metadata.get("source_url"),
            "page_content_snippet": snippet
        })
    
    # Step 2: Summarization (for long documents)
    summarized_docs = []
    for doc in state.documents:
        if len(doc.page_content) > 500:
            summary = summarization_chain.invoke({"document_content": doc.page_content})
            summarized_docs.append(Document(page_content=summary, metadata=doc.metadata))
        else:
            summarized_docs.append(doc)
    
    # Step 3: Citation Attribution
    citations = []
    for doc in state.documents:
        citations.append({
            "title": doc.metadata.get("title", "N/A"),
            "source_url": doc.metadata.get("source_url", "N/A"),
            "page_number": doc.metadata.get("page_number", "N/A"),
        })
    
    return {
        "extracted_info": extracted_data,
        "summarized_content": summarized_docs,
        "citations": citations
    }
```

### 8. **Generator Node**
**Purpose**: Create comprehensive final answer

```python
def generator_node(state: AgentState) -> Dict[str, Any]:
    generator_result = generator_agent_instance.generate_response(
        query=state.contextualized_query or state.user_query,
        documents=state.documents or [],
        extracted_info=state.extracted_info,
        citations=state.citations,
        chat_history=state.chat_history
    )
    
    return {
        "final_answer": generator_result.data.response,
        "confidence_score": generator_result.data.confidence_score,
        "sources_used": generator_result.data.sources_used
    }
```

**Generation Process**:
1. **Content Synthesis**: Combines retrieved information
2. **Citation Integration**: Includes proper source attribution
3. **Answer Structuring**: Organizes response logically
4. **Quality Assessment**: Evaluates completeness and accuracy

### 9. **Validation Node**
**Purpose**: Validate response quality and completeness

```python
def validation_node(state: AgentState) -> Dict[str, Any]:
    validation_result = validation_agent(state, model=llm)
    
    # Returns: {"is_valid": boolean, "reason": string}
    return {"validation": validation_result.get("validation", {"is_valid": True})}
```

**Validation Criteria**:
- Answer completeness relative to query
- Proper use of retrieved context
- Citation accuracy and relevance
- Logical consistency

**Routing Logic**:
- **Valid**: End workflow, return final answer
- **Invalid**: Route back to `retriever_worker` for refinement

### 10. **Final Response**
```json
{
    "answer": "Massachusetts public records laws are governed by the Public Records Law (M.G.L. c. 66)...",
    "sources": [
        {
            "title": "Massachusetts Public Records Law Guide",
            "url": "https://example.com/ma-records-law",
            "relevance": "Primary source for exemptions"
        }
    ],
    "metadata": {
        "complexity_score": 0.4,
        "retrieval_methods": ["dense", "sparse"],
        "processing_time_ms": 1250,
        "documents_retrieved": 8,
        "confidence_score": 0.92
    }
}
```

## Error Handling & Recovery

### Error Types
1. **Retrieval Failures**: Fallback to alternative methods
2. **LLM Failures**: Retry with different prompts
3. **Processing Errors**: Graceful degradation
4. **Validation Failures**: Loop back for refinement

### Recovery Mechanisms
- **Automatic Retry**: Up to 3 attempts with exponential backoff
- **Fallback Strategies**: Alternative retrieval methods
- **Graceful Degradation**: Partial responses when possible
- **Error Context**: Detailed logging for debugging

This detailed flow ensures robust, intelligent processing of legal queries with comprehensive error handling and quality assurance.
"""
Prompts extracted from backend/llm/query_translation/step_back.py
"""

from .base import BASE_PROMPT

# ============================================================================
# STEP BACK SYSTEM PROMPT
# ============================================================================
STEP_BACK_SYSTEM_PROMPT = f"""
You are an expert in First Amendment law and public records processes in New England.
Your task is to take a user’s question and “step back” to a broader, more answerable legal framing aligned with NEFAC’s work.
{BASE_PROMPT}
Here are examples of reformulating specific questions into broader legal inquiries:
"""

# ============================================================================
# STEP BACK RESPONSE PROMPT
# ============================================================================
STEP_BACK_RESPONSE_PROMPT = """
Using both the original question and the stepped-back legal context, produce a comprehensive answer based on these sources:

# normal_context (direct retrieval results)
{normal_context}

# step_back_context (retrieved broader context)
{step_back_context}

Original Question: {question}
Answer:
"""

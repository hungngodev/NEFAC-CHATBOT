"""
Prompts extracted from backend/llm/query_translation/rag_fusion.py
"""

from .base import BASE_PROMPT

# ============================================================================
# RAG FUSION PROMPT
# ============================================================================
RAG_FUSION_PROMPT = f"""
You are an AI assistant for the New England First Amendment Coalition (NEFAC). Your goal is to enhance document retrieval by generating multiple complementary search queries based on a single user question.

{BASE_PROMPT}
Given the user's original question, generate exactly 4 refined and diverse queries designed to:
1. Precisely address the user's original query from a NEFAC legal or press-freedom perspective.
2. Identify broader issues and historical contexts relevant to NEFAC's First Amendment advocacy.
3. Surface related case studies, precedent-setting legal cases, or real-world applications.
4. Uncover potential challenges, debates, or alternative viewpoints connected to NEFAC's work.

Original question: {{question}}

Output (4 queries, separated by newlines):
"""

"""
Query Complexity Analysis System
Implements multi-dimensional complexity assessment as documented in the architecture.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from src.schemas.supervisor import QueryComplexity


@dataclass
class ComplexityMetrics:
    """Detailed complexity metrics for analysis."""

    linguistic_score: float
    domain_score: float
    reasoning_score: float
    temporal_score: float
    multi_hop_score: float
    confidence: float


class ComplexityAnalyzer:
    """
    Complexity analyzer implementing multi-dimensional assessment.
    """

    def __init__(self, llm=None):
        self.llm = llm
        self.complexity_weights = {"linguistic": 0.2, "domain": 0.25, "reasoning": 0.3, "temporal": 0.1, "multi_hop": 0.15}

    def analyze_linguistic_complexity(self, query: str) -> float:
        """Analyze linguistic complexity of the query."""
        score = 0.0

        # Sentence structure analysis
        sentences = query.split(".")
        if len(sentences) > 2:
            score += 0.2

        # Question type complexity
        complex_question_words = ["why", "how", "analyze", "compare", "evaluate", "assess"]
        simple_question_words = ["what", "who", "when", "where"]

        query_lower = query.lower()
        if any(word in query_lower for word in complex_question_words):
            score += 0.3
        elif any(word in query_lower for word in simple_question_words):
            score += 0.1

        # Clause complexity
        conjunctions = ["and", "but", "however", "although", "because", "since"]
        conjunction_count = sum(1 for conj in conjunctions if conj in query_lower)
        score += min(conjunction_count * 0.1, 0.3)

        # Word count complexity
        word_count = len(query.split())
        if word_count > 20:
            score += 0.2
        elif word_count > 10:
            score += 0.1

        return min(score, 1.0)

    def analyze_domain_complexity(self, query: str) -> float:
        """Analyze legal domain complexity."""
        score = 0.0
        query_lower = query.lower()

        # Legal terminology
        basic_legal_terms = ["law", "legal", "court", "case", "statute", "regulation"]
        advanced_legal_terms = ["jurisdiction", "precedent", "constitutional", "procedural", "substantive", "appellate"]
        specialized_terms = ["foia", "public records", "sunshine law", "open meeting", "exemption", "redaction"]

        if any(term in query_lower for term in specialized_terms):
            score += 0.4
        elif any(term in query_lower for term in advanced_legal_terms):
            score += 0.3
        elif any(term in query_lower for term in basic_legal_terms):
            score += 0.2

        # Entity complexity
        if re.search(r"\b[A-Z][a-z]+ v\. [A-Z][a-z]+\b", query):  # Case citations
            score += 0.3
        if re.search(r"\b\d+\s+U\.S\.C\.\s+§\s+\d+\b", query):  # Statute citations
            score += 0.3

        return min(score, 1.0)

    def analyze_reasoning_complexity(self, query: str) -> float:
        """Analyze reasoning requirements."""
        score = 0.0
        query_lower = query.lower()

        # Reasoning indicators
        comparison_words = ["compare", "contrast", "difference", "similar", "versus", "vs"]
        analysis_words = ["analyze", "evaluate", "assess", "examine", "investigate"]
        synthesis_words = ["synthesize", "combine", "integrate", "develop", "create"]
        causal_words = ["cause", "effect", "result", "lead to", "because", "due to"]

        if any(word in query_lower for word in synthesis_words):
            score += 0.4
        elif any(word in query_lower for word in analysis_words):
            score += 0.3
        elif any(word in query_lower for word in comparison_words):
            score += 0.25
        elif any(word in query_lower for word in causal_words):
            score += 0.2

        # Multi-step indicators
        step_indicators = ["first", "then", "next", "finally", "step by step", "process"]
        if any(indicator in query_lower for indicator in step_indicators):
            score += 0.2

        return min(score, 1.0)

    def analyze_temporal_complexity(self, query: str) -> float:
        """Analyze temporal complexity."""
        score = 0.0
        query_lower = query.lower()

        # Time-based queries
        temporal_words = ["trend", "over time", "historical", "evolution", "change", "development"]
        time_periods = ["decade", "year", "month", "recent", "past", "future", "since", "until"]

        if any(word in query_lower for word in temporal_words):
            score += 0.3
        if any(word in query_lower for word in time_periods):
            score += 0.2

        # Date patterns
        if re.search(r"\b\d{4}\b", query):  # Years
            score += 0.1
        if re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", query):  # Dates
            score += 0.1

        return min(score, 1.0)

    def analyze_multi_hop_requirements(self, query: str) -> float:
        """Analyze multi-hop retrieval requirements."""
        score = 0.0
        query_lower = query.lower()

        # Multi-entity queries
        entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", query)
        if len(entities) > 2:
            score += 0.3
        elif len(entities) > 1:
            score += 0.2

        # Multiple jurisdiction queries
        jurisdictions = ["federal", "state", "local", "massachusetts", "rhode island", "connecticut"]
        jurisdiction_count = sum(1 for j in jurisdictions if j in query_lower)
        if jurisdiction_count > 1:
            score += 0.3

        # Cross-domain queries
        domains = ["criminal", "civil", "administrative", "constitutional", "contract"]
        domain_count = sum(1 for d in domains if d in query_lower)
        if domain_count > 1:
            score += 0.2

        return min(score, 1.0)

    def calculate_overall_complexity(self, metrics: ComplexityMetrics) -> float:
        """Calculate weighted overall complexity score."""
        return (
            metrics.linguistic_score * self.complexity_weights["linguistic"]
            + metrics.domain_score * self.complexity_weights["domain"]
            + metrics.reasoning_score * self.complexity_weights["reasoning"]
            + metrics.temporal_score * self.complexity_weights["temporal"]
            + metrics.multi_hop_score * self.complexity_weights["multi_hop"]
        )

    def determine_category_and_route(self, complexity_score: float) -> tuple[str, str]:
        """Determine complexity category and recommended route."""
        if complexity_score < 0.3:
            return "Simple", "route_to_retriever"
        elif complexity_score < 0.7:
            return "Medium", "route_to_retriever"
        else:
            return "Complex", "route_to_react"

    def analyze_with_llm(self, query: str, chat_history: List[BaseMessage]) -> QueryComplexity:
        """Use LLM for enhanced complexity analysis."""
        if not self.llm:
            # Fallback to rule-based analysis
            return self.analyze_rule_based(query, chat_history)

        complexity_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are an expert at analyzing query complexity for a legal information system.

Analyze the query across multiple dimensions:

1. Linguistic Complexity (0.0-1.0):
   - Sentence structure and grammar complexity
   - Question type (simple vs complex)
   - Vocabulary sophistication

2. Domain Complexity (0.0-1.0):
   - Legal terminology density
   - Specialized knowledge requirements
   - Citation complexity

3. Reasoning Complexity (0.0-1.0):
   - Multi-step reasoning requirements
   - Comparison and analysis needs
   - Synthesis requirements

4. Temporal Complexity (0.0-1.0):
   - Time-based analysis requirements
   - Historical context needs
   - Trend analysis

Consider conversation context for follow-up questions.

Provide detailed analysis with confidence scores.""",
                ),
                ("human", "Chat history: {chat_history}\n\nQuery to analyze: {query}"),
            ]
        )

        try:
            chain = complexity_prompt | self.llm.with_structured_output(QueryComplexity)
            result = chain.invoke({"query": query, "chat_history": chat_history})
            return result
        except Exception:
            # Fallback to rule-based analysis
            return self.analyze_rule_based(query, chat_history)

    def analyze_rule_based(self, query: str, chat_history: List[BaseMessage]) -> QueryComplexity:
        """Rule-based complexity analysis as fallback."""
        # Perform individual analyses
        linguistic = self.analyze_linguistic_complexity(query)
        domain = self.analyze_domain_complexity(query)
        reasoning = self.analyze_reasoning_complexity(query)
        temporal = self.analyze_temporal_complexity(query)
        multi_hop = self.analyze_multi_hop_requirements(query)

        # Create metrics
        metrics = ComplexityMetrics(linguistic_score=linguistic, domain_score=domain, reasoning_score=reasoning, temporal_score=temporal, multi_hop_score=multi_hop, confidence=0.8)  # Rule-based confidence

        # Calculate overall complexity
        overall_complexity = self.calculate_overall_complexity(metrics)

        # Determine category and route
        category, route = self.determine_category_and_route(overall_complexity)

        # Determine boolean flags
        reasoning_required = reasoning > 0.3 or overall_complexity > 0.5
        multi_hop_needed = multi_hop > 0.3 or overall_complexity > 0.6
        tool_usage_required = overall_complexity > 0.2

        # Generate reasoning explanation
        reasoning_text = f"Complexity analysis: Linguistic={linguistic:.2f}, Domain={domain:.2f}, "
        reasoning_text += f"Reasoning={reasoning:.2f}, Temporal={temporal:.2f}, Multi-hop={multi_hop:.2f}. "
        reasoning_text += f"Overall score: {overall_complexity:.2f} ({category})"

        return QueryComplexity(
            complexity_score=overall_complexity,
            reasoning_required=reasoning_required,
            multi_hop_needed=multi_hop_needed,
            tool_usage_required=tool_usage_required,
            confidence=metrics.confidence,
            linguistic_complexity=linguistic,
            domain_complexity=domain,
            reasoning_complexity=reasoning,
            temporal_complexity=temporal,
            complexity_category=category,
            recommended_route=route,
            reasoning=reasoning_text,
        )

    def analyze_complexity(self, query: str, chat_history: Optional[List[BaseMessage]] = None) -> QueryComplexity:
        """Main public interface for complexity analysis - used by server.py"""
        return self.analyze(query, chat_history)

    def analyze(self, query: str, chat_history: Optional[List[BaseMessage]] = None) -> QueryComplexity:
        """Main analysis method."""
        if chat_history is None:
            chat_history = []

        if self.llm:
            return self.analyze_with_llm(query, chat_history)
        else:
            return self.analyze_rule_based(query, chat_history)

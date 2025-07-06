from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI

from src.config.constant import QUERY_TRANSLATION_MODEL_NAME
from src.config.prompts import STEP_BACK_RESPONSE_PROMPT, STEP_BACK_SYSTEM_PROMPT
from src.core.agents.tools.document_formatter import format_docs
from src.core.agents.tools.retrieval.retrieval_tools import ensemble_retriever_tool
from src.load_env import load_env

load_env()

model = ChatOpenAI(temperature=0, model=QUERY_TRANSLATION_MODEL_NAME)

# Step‑back reformulation examples in a NEFAC/legal context
examples = [
    {
        "input": "Can I film police during a protest in Massachusetts?",
        "output": "What are the legal rights around recording public officials in Massachusetts?",
    },
    {
        "input": "How do I request public records from New Hampshire?",
        "output": "What are the legal processes for obtaining public records in New Hampshire?",
    },
]

example_prompt = ChatPromptTemplate.from_messages(
    [
        ("human", "{input}"),
        ("ai", "{output}"),
    ]
)

few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    examples=examples,
)

step_back_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            STEP_BACK_SYSTEM_PROMPT,
        ),
        few_shot_prompt,
        ("user", "{question}"),
    ]
)

generate_step_back_question = step_back_prompt | model | StrOutputParser()

# Step‑back RAG chain
response_prompt = ChatPromptTemplate.from_template(STEP_BACK_RESPONSE_PROMPT)


def get_step_back_chain(retriever=None) -> Runnable:
    """Step-back chain using ensemble retriever with dual retrieval strategy."""

    def normal_retrieval(question: str) -> str:
        """Retrieve documents for the original question."""
        docs = ensemble_retriever_tool.retrieve(query=question, methods=["dense", "sparse", "graph"], weights=[0.4, 0.3, 0.3], max_documents=6)  # All methods for specific question  # Balanced approach
        return format_docs(docs)

    def step_back_retrieval(step_back_question: str) -> str:
        """Retrieve documents for the abstract step-back question."""
        docs = ensemble_retriever_tool.retrieve(query=step_back_question, methods=["dense", "graph"], weights=[0.6, 0.4], max_documents=6)  # Focus on conceptual and relationship retrieval  # Favor dense for abstract concepts
        return format_docs(docs)

    return (
        {
            "normal_context": RunnableLambda(lambda x: x["question"]) | normal_retrieval,
            "step_back_context": generate_step_back_question | step_back_retrieval,
            "question": RunnableLambda(lambda x: x["question"]),
        }
        | response_prompt
        | model
        | StrOutputParser()
    )

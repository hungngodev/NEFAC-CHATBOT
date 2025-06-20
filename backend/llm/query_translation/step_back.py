from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from load_env import load_env
from llm.constant import PROMPT_MODEL_NAME, BASE_PROMPT

load_env()

model = ChatOpenAI(temperature=0, model_name=PROMPT_MODEL_NAME)

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
            f"""
You are an expert in First Amendment law and public records processes in New England.
Your task is to take a user’s question and “step back” to a broader, more answerable legal framing aligned with NEFAC’s work.
{BASE_PROMPT}
Here are examples of reformulating specific questions into broader legal inquiries:
""",
        ),
        few_shot_prompt,
        ("user", "{question}"),
    ]
)

generate_step_back_question = step_back_prompt | model | StrOutputParser()

# Step‑back RAG chain
response_prompt = ChatPromptTemplate.from_template(
    """
Using both the original question and the stepped-back legal context, produce a comprehensive answer based on these sources:

# normal_context (direct retrieval results)
{normal_context}

# step_back_context (retrieved broader context)
{step_back_context}

Original Question: {question}
Answer:
"""
)


def get_step_back_chain(retriever):
    return (
        {
            "normal_context": RunnableLambda(lambda x: x["question"]) | retriever,
            "step_back_context": generate_step_back_question | retriever,
            "question": RunnableLambda(lambda x: x["question"]),
        }
        | response_prompt
        | model
        | StrOutputParser()
    )

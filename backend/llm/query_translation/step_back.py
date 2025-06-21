from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from llm.constant import PROMPT_MODEL_NAME
from load_env import load_env
from prompts import STEP_BACK_RESPONSE_PROMPT, STEP_BACK_SYSTEM_PROMPT

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
            STEP_BACK_SYSTEM_PROMPT,
        ),
        few_shot_prompt,
        ("user", "{question}"),
    ]
)

generate_step_back_question = step_back_prompt | model | StrOutputParser()

# Step‑back RAG chain
response_prompt = ChatPromptTemplate.from_template(STEP_BACK_RESPONSE_PROMPT)


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

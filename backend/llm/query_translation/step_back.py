from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

# Define the step-back question generation chain
examples = [
    {
        "input": "Could the members of The Police perform lawful arrests?",
        "output": "what can the members of The Police do?",
    },
    {
        "input": "Jan Sindel's was born in what country?",
        "output": "what is Jan Sindel's personal history?",
    },
]

example_prompt = ChatPromptTemplate.from_messages([
    ("human", "{input}"),
    ("ai", "{output}"),
])

few_shot_prompt = FewShotChatMessagePromptTemplate(
    example_prompt=example_prompt,
    examples=examples,
)

step_back_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at world knowledge. Your task is to step back and paraphrase a question to a more generic step-back question, which is easier to answer. Here are a few examples:"""),
    few_shot_prompt,
    ("user", "{question}"),
])

generate_step_back_question = step_back_prompt | ChatOpenAI(temperature=0) | StrOutputParser()

# Define the final response chain
response_prompt = ChatPromptTemplate.from_template("""
You are an expert of world knowledge. I am going to ask you a question. Your response should be comprehensive and not contradicted with the following context if they are relevant. Otherwise, ignore them if they are not relevant.

# {normal_context}
# {step_back_context}

Original Question: {question}
Answer:""")

def get_step_back_chain(retriever):
    """Get the step-back chain."""
    
    chain = (
        {
            "normal_context": RunnableLambda(lambda x: x["question"]) | retriever,
            "step_back_context": generate_step_back_question | retriever,
            "question": lambda x: x["question"]
        }
        | response_prompt
        | ChatOpenAI(temperature=0)
        | StrOutputParser()
    )
    return chain

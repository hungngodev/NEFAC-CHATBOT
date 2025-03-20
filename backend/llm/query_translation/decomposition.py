from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from operator import itemgetter
from load_env import load_env
from llm.utils import format_docs
from llm.constant import PROMPT_MODEL_NAME, SUB_MODEL_NAME
load_env()


model = ChatOpenAI(temperature=0, model_name=PROMPT_MODEL_NAME)

decomposition_template = """You are a helpful assistant that generates multiple sub-questions related to an input question. 
The goal is to break down the input into a set of sub-problems that can be answered in isolation.
Generate multiple search queries related to: {question}
Output (3 queries):"""

generate_queries_decomposition = (
    ChatPromptTemplate.from_template(decomposition_template) 
    | model 
    | StrOutputParser() 
    | (lambda x: x.split("\n")))

# 2. Individual Question Answering Chain
qa_template = """Here is the question you need to answer:
--- 
{question}
---

Here is any available background question + answer pairs:
---
{q_a_pairs}
---

Here is additional context relevant to the question:
---
{context}
---

Use the above context and background pairs to answer the question: {question}"""

rag_model = ChatOpenAI(temperature=0, model_name=SUB_MODEL_NAME)

rag_chain = (
    {
        "context": itemgetter("context"),
        "question": itemgetter("question"),
        "q_a_pairs": itemgetter("q_a_pairs")
    }
    | ChatPromptTemplate.from_template(qa_template)
    | model
    | StrOutputParser()
)

def get_decomposition_chain(retriever):

    def process_sub_questions(input_dict):
        sub_questions = input_dict["sub_question"]
        main_question = input_dict["question"]
        contexts = input_dict["context"]

        q_a_pairs = []
        for i in range(len(sub_questions)):
            current_context = "\n---\n".join(q_a_pairs) if q_a_pairs else ""
            answer = rag_chain.invoke({"question": sub_questions[i], "q_a_pairs": current_context, "context": contexts[i]})
            q_a_pairs.append( f"Question: {sub_questions[i]}\nAnswer: {answer}")

        return {
            "context": "\n---\n".join(q_a_pairs),
            "question": main_question
        }


    final_template = """Here is a set of Q+A pairs:
    {context}

    Use these to synthesize an answer to the question: {question}"""
    final_prompt = ChatPromptTemplate.from_template(final_template)
    final_rag_chain = final_prompt | model | StrOutputParser()

    return (
        RunnableLambda(lambda x: {"question": x})
        |
        {
            "question": itemgetter("question"),
            "sub_question":
                {'question': itemgetter("question")}
                | generate_queries_decomposition
        } 
        |
        {
            "sub_question": itemgetter("sub_question"),
            "context": itemgetter("sub_question") | (retriever | format_docs).map(),
            "question": itemgetter("question"),
        }
        | RunnableLambda(process_sub_questions)
        | final_rag_chain
    )

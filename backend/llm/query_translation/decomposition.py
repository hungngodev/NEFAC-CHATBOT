from operator import itemgetter

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from llm.constant import QUERY_TRANSLATION_MODEL_NAME
from llm.utils import format_docs
from load_env import load_env
from prompts import DECOMPOSITION_PROMPT, FINAL_SYNTHESIS_TEMPLATE, QA_TEMPLATE

load_env()

model = ChatOpenAI(temperature=0, model_name=QUERY_TRANSLATION_MODEL_NAME)

generate_queries_decomposition = ChatPromptTemplate.from_template(DECOMPOSITION_PROMPT) | model | StrOutputParser() | (lambda x: x.strip().split("\n"))

qa_template = QA_TEMPLATE

rag_chain = (
    {
        "context": itemgetter("context"),
        "sub_question": itemgetter("sub_question"),
        "q_a_pairs": itemgetter("q_a_pairs"),
    }
    | ChatPromptTemplate.from_template(qa_template)
    | model
    | StrOutputParser()
)


def get_decomposition_chain(retriever):
    def process_sub_questions(input_dict):
        sub_questions = input_dict["sub_questions"]
        main_question = input_dict["question"]
        contexts = input_dict["contexts"]

        q_a_pairs = []
        for i in range(len(sub_questions)):
            current_context = "\n---\n".join(q_a_pairs) if q_a_pairs else ""
            answer = rag_chain.invoke(
                {
                    "sub_question": sub_questions[i],
                    "q_a_pairs": current_context,
                    "context": contexts[i],
                }
            )
            q_a_pairs.append(f"Question: {sub_questions[i]}\nAnswer: {answer}")

        return {"context": "\n---\n".join(q_a_pairs), "question": main_question}

    final_template = FINAL_SYNTHESIS_TEMPLATE

    final_prompt = ChatPromptTemplate.from_template(final_template)
    final_rag_chain = final_prompt | model | StrOutputParser()

    return (
        RunnableLambda(lambda x: {"question": x})
        | {
            "question": itemgetter("question"),
            "sub_questions": {"question": itemgetter("question")} | generate_queries_decomposition,
        }
        | {
            "sub_questions": itemgetter("sub_questions"),
            "contexts": itemgetter("sub_questions") | (retriever | format_docs).map(),
            "question": itemgetter("question"),
        }
        | RunnableLambda(process_sub_questions)
        | final_rag_chain
    )

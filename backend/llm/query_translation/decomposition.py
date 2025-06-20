from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from operator import itemgetter
from load_env import load_env
from llm.utils import format_docs
from llm.constant import PROMPT_MODEL_NAME, SUB_MODEL_NAME, BASE_PROMPT
load_env()

model = ChatOpenAI(temperature=0, model_name=PROMPT_MODEL_NAME)

generate_queries_decomposition = (
    ChatPromptTemplate.from_template( f"""
You are an expert assistant for the New England First Amendment Coalition (NEFAC). Your role is to break down the user's complex question into exactly 3 focused, independently-answerable sub-questions to retrieve precise documents from our vector database of legal analyses, FOI guides, press-freedom resources, and relevant transcripts.
{BASE_PROMPT}
The sub-questions should:
1. Address specific legal rights, frameworks, or procedures relevant to the original question.
2. Identify related historical cases, precedents, or contextual background crucial to the topic.
3. Explore practical applications, examples, or implications for journalists or citizens in New England.

Original question: {{question}}

Output (exactly 3 queries, one per line):
""") 
    | model 
    | StrOutputParser() 
    | (lambda x: x.strip().split("\n"))
)

# Individual Question Answering Chain (aligned with NEFAC context)
qa_template = """
You are a NEFAC legal expert answering the following sub-question:
--- 
{sub_question}
---

Background information (previously answered sub-questions):
---
{q_a_pairs}
---

Additional relevant NEFAC context:
---
{context}
---

Use the context and background to answer precisely:
{sub_question}
"""

rag_model = ChatOpenAI(temperature=0, model_name=SUB_MODEL_NAME)

rag_chain = (
    {
        "context": itemgetter("context"),
        "sub_question": itemgetter("sub_question"),
        "q_a_pairs": itemgetter("q_a_pairs")
    }
    | ChatPromptTemplate.from_template(qa_template)
    | rag_model
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
            answer = rag_chain.invoke({
                "sub_question": sub_questions[i],
                "q_a_pairs": current_context,
                "context": contexts[i]
            })
            q_a_pairs.append(f"Question: {sub_questions[i]}\nAnswer: {answer}")

        return {
            "context": "\n---\n".join(q_a_pairs),
            "question": main_question
        }

    final_template = """
    You are a NEFAC legal expert. Given the following sub-questions and answers:
    {context}

    Synthesize a cohesive, comprehensive response to the user's main question:
    {question}
    """

    final_prompt = ChatPromptTemplate.from_template(final_template)
    final_rag_chain = final_prompt | model | StrOutputParser()

    return (
        RunnableLambda(lambda x: {"question": x})
        |
        {
            "question": itemgetter("question"),
            "sub_questions":
                {'question': itemgetter("question")}
                | generate_queries_decomposition
        } 
        |
        {
            "sub_questions": itemgetter("sub_questions"),
            "contexts": itemgetter("sub_questions") | (retriever | format_docs).map(),
            "question": itemgetter("question"),
        }
        | RunnableLambda(process_sub_questions)
        | final_rag_chain
    )

from langchain_openai import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate

def generate_summary(documents):
    """Generate a summary for a list of document pages or chunks using an LLM."""
    model = ChatOpenAI(model="gpt-3.5-turbo")
    map_prompt = PromptTemplate.from_template("YOU WORK FOR NEFAC AS THEIR TRUSTY SUMMARIZER, SOMETIMES, TRANSCRIPTS SAY KNEEFACT BUT THEY MEAN NEFAC. Summarize the following:\n\n{text}")
    reduce_prompt = PromptTemplate.from_template("(Don't start by saying 'the text/site/document/summary', just summarize) -> Prompt: Combine the this into a single output:\n\n{text}")
    chain = load_summarize_chain(
        model,
        chain_type="map_reduce",
        map_prompt=map_prompt,
        combine_prompt=reduce_prompt,
    )
    result = chain.invoke({"input_documents": documents})
    # print('summary',str(result.get("output_text", result)))
    return str(result["output_text"])
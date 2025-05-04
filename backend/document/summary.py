# from langchain_openai import ChatOpenAI
# from langchain.chains.summarize import load_summarize_chain
# from langchain.prompts import PromptTemplate

# def generate_summary(documents):
#     """Generate a summary for a list of document pages or chunks using an LLM."""
#     model = ChatOpenAI(model="gpt-3.5-turbo")
#     map_prompt = PromptTemplate.from_template("KNEEFACT ACTUALLY MEANS NEFAC. Summarize the following:\n\n{text}")
#     reduce_prompt = PromptTemplate.from_template("JUST SUMMARIZE -> Prompt: Combine the this into a single output:\n\n{text}")
#     chain = load_summarize_chain(
#         model,
#         chain_type="map_reduce",
#         map_prompt=map_prompt,
#         combine_prompt=reduce_prompt,
#     )
#     result = chain.invoke({"input_documents": documents})
#     # print('summary',str(result.get("output_text", result)))
#     return str(result["output_text"])

from langchain_openai import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate

def generate_summary(documents):
    """Generate a summary for a list of document pages or chunks using an LLM."""
    model = ChatOpenAI(model="gpt-3.5-turbo")
    map_prompt = PromptTemplate.from_template("KNEEFACT ACTUALLY MEANS NEFAC. Summarize the following:\n\n{text}")
    reduce_prompt = PromptTemplate.from_template("JUST SUMMARIZE -> Prompt: Combine the this into a single output:\n\n{text}")
    chain = load_summarize_chain(
        model,
        chain_type="map_reduce",
        map_prompt=map_prompt,
        combine_prompt=reduce_prompt,
    )
    result = chain.invoke({"input_documents": documents})
    return str(result["output_text"])

def generate_tags(summary,youtube=False):
    """Generate tags for a document summary using an LLM."""
    model = ChatOpenAI(model="gpt-3.5-turbo")
    prompt = f"""
Based on the following summary of a document, suggest any and all relevant tags for each of the following categories. THEY CAN ONLY BE FROM THE PROVIDED OPTIONS:
{'This is a YouTube video.' if youtube else 'This is a pdf document.'}

SELECT ONLY FROM THESE REQUIRED OPTIONS LISTED.
- Audience: Who is the intended audience? Choose exactly 2  - (citizen, educator, journalist, lawyer)
- NEFAC Category: Which category does this fit best? Choose 5 or less from - (advocacy, civic education, community outreach, first amendment rights, government transparency, investigative journalism, media law, mentorship, open meeting law, public records law, skill building, workshops)
- Resource Type: Which resource type does this fit best? Choose 1 or less from - (guides, lessons, multimedia)

Summary:
{summary}

Provide the tags in the format:
Audience: tag1, tag2
NEFAC Category: tag1, tag2, ...
Resource Type: tag1, tag2
"""
    response = model.invoke(prompt)
    tags_text = response.content.strip()
    tags = {}
    for line in tags_text.split('\n'):
        if ':' in line:
            category, tags_str = line.split(':', 1)
            category = category.strip().lower().replace(' ', '_')
            tags_list = [tag.strip() for tag in tags_str.split(',')][:2]
            tags[category] = tags_list
    return tags
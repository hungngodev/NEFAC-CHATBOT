from chain import middleware_qa, custom_QA_structured
# Function to ask the LLM
async def ask_llm(_, info, query, convoHistory= "",roleFilter=None, contentType=None, resourceType=None):

    conversation_response = await middleware_qa(_, info, query, convoHistory, roleFilter, contentType, resourceType)
    if conversation_response == "1":
        response = await custom_QA_structured(_, info, query, roleFilter, contentType, resourceType)
    else:
        response = [{
            "title": "follow-up",
            "link": "",
            "summary": conversation_response,
            "citations": [{"id": "1", "context": "Follow-up question"}]

        }]
    if response is None:
        return ['error']
    return response


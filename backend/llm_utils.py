import faiss
from bedrock_client import BedrockClient

# Initialize FAISS and Bedrock embeddings
index = faiss.IndexFlatL2(768)
bedrock_client = BedrockClient()

def add_documents_to_faiss(docs):
    for doc in docs:
        embedding = bedrock_client.embed(doc)
        index.add(embedding)

def retrieve_documents(query):
    query_embedding = bedrock_client.embed(query)
    D, I = index.search(query_embedding, k=5)  # Retrieve top 5 docs
    return [docs[i] for i in I[0]]

def chunk_document(doc, chunk_size=500):
    chunks = [doc[i:i + chunk_size] for i in range(0, len(doc), chunk_size)]
    return chunks


def call_claude_llm(prompt, context):
    full_prompt = f"{context}\n\nUser: {prompt}\nAssistant:"
    # Use Bedrock or your Claude API key here
    response = bedrock_client.generate(full_prompt)
    return response['output_text']
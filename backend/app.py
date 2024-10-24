from flask import Flask, request, jsonify
from bedrock_client import BedrockClient
import faiss
from flask_cors import CORS
from llm_utils import add_documents_to_faiss, retrieve_documents, chunk_document, call_claude_llm

app = Flask(__name__)
CORS(app)

# Initialize Bedrock Client and FAISS Index
bedrock_client = BedrockClient()
vector_store = faiss.IndexFlatL2(768)  # Assuming 768-dim embeddings

@app.route('/a***REMOVED***llm', methods=['POST'])
def ask_llm():
    data = request.json
    prompt = data.get('prompt')

    # Retrieve documents from FAISS
    relevant_docs = retrieve_documents(prompt)
    context = "\n".join(relevant_docs)

    # Get response from LLM
    response = call_claude_llm(prompt, context)
    return jsonify({"response": response})

@app.route('/add-documents', methods=['POST'])
def add_documents():
    data = request.json
    docs = data.get('documents')
    for doc in docs:
        chunks = chunk_document(doc)
        add_documents_to_faiss(chunks)
    return jsonify({"status": "Documents added!"})


if __name__ == '__main__':
    app.run(debug=True)

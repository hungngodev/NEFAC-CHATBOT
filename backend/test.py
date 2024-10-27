import requests

# Define the GraphQL endpoint
url = "http://localhost:8000/graphql"

# Define the GraphQL mutation
mutation = """
mutation AddDocuments($documents: [String!]!) {
  addDocuments(documents: $documents)
}
"""

# Define the variables
variables = {
    "documents": [
        "Document 1 content",
        "Document 2 content",
        "Document 3 content"
    ]
}

# Define the JSON payload
payload = {
    "query": mutation,
    "variables": variables
}

# Send the POST request
response = requests.post(url, json=payload)

# Print the response
print(response.json())
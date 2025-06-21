curl --location --request GET 'http://127.0.0.1:8000/graphql' \
--header 'Content-Type: application/json' \
--data '{
  "query": "query { askLlm(prompt: \"What is LangChain?????\") }"
}
'
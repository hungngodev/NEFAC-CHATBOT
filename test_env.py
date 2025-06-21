import os
from dotenv import load_dotenv

# Load .env file from backend directory
load_dotenv("backend/.env")

# Check if OpenAI API key is available
api_key = os.getenv("OPENAI_API_KEY")
if api_key and api_key.startswith("sk-"):
    print("✅ OPENAI_API_KEY is properly loaded")
    print(f"   Key starts with: {api_key[:10]}...")
else:
    print("❌ OPENAI_API_KEY not found or invalid")
    print(f"   Value: {api_key}")

# Check other environment variables
env_vars = ["ENVIRONMENT", "LOG_LEVEL", "DISABLE_AWS_SERVICES", "LANGSMITH_TRACING", "LANGSMITH_ENDPOINT"]
for var in env_vars:
    value = os.getenv(var)
    print(f"   {var}: {value}")

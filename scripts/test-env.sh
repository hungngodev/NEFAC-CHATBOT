#!/bin/bash

# Test script to verify environment variables are loaded correctly
set -e

echo "🧪 Testing environment variable setup..."

# Check if backend .env file exists
if [ ! -f backend/.env ]; then
    echo "❌ No backend/.env file found!"
    echo "   Please run ./scripts/local.sh or ./scripts/dev.sh first to create it."
    exit 1
fi

# Check if OpenAI API key is set (handle both formats: with and without spaces)
if ! grep -q "OPENAI_API_KEY.*=.*sk-" backend/.env; then
    echo "❌ OPENAI_API_KEY not found or not properly set in backend/.env file"
    echo "   Please add: OPENAI_API_KEY=sk-your_actual_key_here"
    echo "   or: OPENAI_API_KEY = sk-your_actual_key_here"
    exit 1
fi

echo "✅ backend/.env file exists and contains OpenAI API key"

# Test environment variables by reading the .env file directly
echo "🐳 Testing environment variable loading..."

# Extract and display key environment variables
echo "📋 Environment variables found in backend/.env:"

# Extract OpenAI API key (handle both formats)
OPENAI_KEY=$(grep "OPENAI_API_KEY" backend/.env | cut -d'=' -f2 | tr -d ' "')
if [[ $OPENAI_KEY == sk-* ]]; then
    echo "✅ OPENAI_API_KEY: ${OPENAI_KEY:0:15}..."
else
    echo "❌ OPENAI_API_KEY: Not found or invalid format"
fi

# Extract other variables
LANGSMITH_TRACING=$(grep "LANGSMITH_TRACING" backend/.env | cut -d'=' -f2 | tr -d ' "')
if [[ -n "$LANGSMITH_TRACING" ]]; then
    echo "   LANGSMITH_TRACING: $LANGSMITH_TRACING"
else
    echo "   LANGSMITH_TRACING: Not set"
fi

LANGSMITH_ENDPOINT=$(grep "LANGSMITH_ENDPOINT" backend/.env | cut -d'=' -f2 | tr -d ' "')
if [[ -n "$LANGSMITH_ENDPOINT" ]]; then
    echo "   LANGSMITH_ENDPOINT: $LANGSMITH_ENDPOINT"
else
    echo "   LANGSMITH_ENDPOINT: Not set"
fi

LANGSMITH_API_KEY=$(grep "LANGSMITH_API_KEY" backend/.env | cut -d'=' -f2 | tr -d ' "')
if [[ -n "$LANGSMITH_API_KEY" ]]; then
    echo "   LANGSMITH_API_KEY: ${LANGSMITH_API_KEY:0:15}..."
else
    echo "   LANGSMITH_API_KEY: Not set"
fi

LANGSMITH_PROJECT=$(grep "LANGSMITH_PROJECT" backend/.env | cut -d'=' -f2 | tr -d ' "')
if [[ -n "$LANGSMITH_PROJECT" ]]; then
    echo "   LANGSMITH_PROJECT: $LANGSMITH_PROJECT"
else
    echo "   LANGSMITH_PROJECT: Not set"
fi

echo ""
echo "🎉 Environment variable test completed!"
echo "   If you see ✅ messages above, your backend/.env file is properly configured."
echo "   The Docker containers will be able to load these environment variables." 
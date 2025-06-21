#!/bin/bash

# Development script for NEFAC project
set -e

echo "🚀 Starting NEFAC development environment..."

# Create logs directory if it doesn't exist
mkdir -p logs/nginx logs/backend logs/localstack

# Copy nginx.conf to frontend directory if it doesn't exist
if [ ! -f frontend/nginx.conf ]; then
    echo "📋 Copying nginx configuration..."
    cp nginx.conf frontend/
fi

# Check for backend .env file
if [ ! -f backend/.env ]; then
    echo "⚠️  No backend .env file found!"
    echo "📝 Creating backend .env file from template..."
    if [ -f backend/.env.example ]; then
        cp backend/.env.example backend/.env
        echo "✅ Created backend .env file from template."
        echo ""
        echo "🔑 IMPORTANT: You need to add your OpenAI API key to backend/.env!"
        echo "   Required variable: OPENAI_API_KEY=your_actual_api_key_here"
        echo "   You can get your API key from: https://platform.openai.com/api-keys"
        echo ""
        echo "📝 Edit backend/.env and add your OpenAI API key, then press Enter to continue..."
        read -p "Press Enter after adding your API key to backend/.env..."
        
        # Verify the API key was added (handle both formats)
        if ! grep -q "OPENAI_API_KEY.*=.*sk-" backend/.env; then
            echo "❌ Error: OPENAI_API_KEY not found or not properly set in backend/.env file"
            echo "   Please make sure you have: OPENAI_API_KEY=sk-your_actual_key_here"
            exit 1
        fi
    else
        echo "❌ No backend/.env.example found. Please create backend/.env file manually."
        echo "Required variables:"
        echo "  - OPENAI_API_KEY=your_openai_api_key_here"
        exit 1
    fi
else
    # Check if API key is set in existing backend .env file (handle both formats)
    if ! grep -q "OPENAI_API_KEY.*=.*sk-" backend/.env; then
        echo "⚠️  Warning: OPENAI_API_KEY not found or not properly set in backend/.env file"
        echo "   Please make sure you have: OPENAI_API_KEY=sk-your_actual_key_here"
        echo "   The application may not work without a valid OpenAI API key."
        read -p "Press Enter to continue anyway..."
    fi
fi

# Function to cleanup on exit
cleanup() {
    echo "🛑 Stopping development environment..."
    docker-compose down
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start the development environment
echo "🐳 Starting Docker containers..."
docker-compose up --build

# If we get here, containers have stopped
echo "✅ Development environment stopped." 
#!/bin/bash

# Exit on error
set -e

# Check if Docker username is provided
if [ -z "$1" ]; then
    echo "Usage: ./build_and_push.sh <docker_hub_username>"
    exit 1
fi

DOCKER_USERNAME=$1

echo "🐳 Login to Docker Hub..."
docker login

echo "🛠️  Building Backend Image..."
docker build -t $DOCKER_USERNAME/nefac-backend:latest ./backend

echo "⬆️  Pushing Backend Image..."
docker push $DOCKER_USERNAME/nefac-backend:latest

echo "🛠️  Building Frontend Image..."
docker build -t $DOCKER_USERNAME/nefac-frontend:latest ./client \
  --build-arg NEXT_PUBLIC_API_URL=/api \
  --build-arg NEXT_PUBLIC_ASSISTANT_ID=agent

echo "⬆️  Pushing Frontend Image..."
docker push $DOCKER_USERNAME/nefac-frontend:latest

echo "✅ Done! Images are ready."
echo "   - $DOCKER_USERNAME/nefac-backend:latest"
echo "   - $DOCKER_USERNAME/nefac-frontend:latest"
echo ""
echo "To deploy on the other machine, run:"
echo "export DOCKER_USERNAME=$DOCKER_USERNAME"
echo "docker-compose -f docker/docker-compose.prod.yml pull"
echo "docker-compose -f docker/docker-compose.prod.yml up -d"

# Development Setup

This guide explains how to set up and run the NEFAC application locally using Docker and Nginx.

## Prerequisites

- Docker and Docker Compose installed
- OpenAI API key (get one from [OpenAI Platform](https://platform.openai.com/api-keys))

## Quick Comparison

| Feature          | Local Development    | Full Development       |
| ---------------- | -------------------- | ---------------------- |
| **Startup Time** | ~30 seconds          | ~2 minutes             |
| **Memory Usage** | ~500MB               | ~2GB                   |
| **AWS Services** | ❌ Disabled          | ✅ LocalStack          |
| **Use Case**     | Frontend/LLM work    | AWS-dependent features |
| **Command**      | `./scripts/local.sh` | `./scripts/dev.sh`     |

## Development Options

### Option 1: Local Development (Recommended for most work)

**Faster startup, lighter resource usage, no AWS services**

```bash
./scripts/local.sh
```

### Option 2: Full Development (with LocalStack)

**Includes AWS services emulation for testing AWS-dependent features**

```bash
./scripts/dev.sh
```

## Quick Start

1. **Clone the repository** (if you haven't already)

   ```bash
   git clone <repository-url>
   cd nefac
   ```

2. **Choose your development environment**:

   **For most development work (recommended):**

   ```bash
   ./scripts/local.sh
   ```

   **For AWS-dependent features:**

   ```bash
   ./scripts/dev.sh
   ```

   Both scripts will:

   - Create necessary directories
   - Set up the `backend/.env` file from template (if needed)
   - Prompt you to add your OpenAI API key
   - Start all services with Docker Compose

3. **Access the application**
   - Frontend: http://localhost
   - Backend API: http://localhost/api
   - Backend (direct): http://localhost:8000 (for debugging)
   - LocalStack (if using): http://localhost:4566

## Manual Setup

### Local Development (No LocalStack)

```bash
# Create environment file
cp backend/.env.example backend/.env
# Edit backend/.env and add your OpenAI API key

# Copy nginx configuration
cp nginx.conf frontend/

# Start services
docker-compose -f docker-compose.local.yml up --build
```

### Full Development (with LocalStack)

```bash
# Create environment file
cp backend/.env.example backend/.env
# Edit backend/.env and add your OpenAI API key

# Copy nginx configuration
cp nginx.conf frontend/

# Start services
docker-compose up --build
```

## Architecture Comparison

### Local Development (No LocalStack)

- **Nginx** (port 80): Serves the React frontend and proxies API requests to `/api/*`
- **Backend** (port 8000): FastAPI application with LLM integration
- **Resource usage**: ~500MB RAM, starts in ~30 seconds

### Full Development (with LocalStack)

- **Nginx** (port 80): Serves the React frontend and proxies API requests to `/api/*`
- **Backend** (port 8000): FastAPI application with LLM integration
- **LocalStack** (port 4566): AWS services emulator
- **Resource usage**: ~2GB RAM, starts in ~2 minutes

## Security Features

- **Rate limiting**: API requests are limited to 10 requests/second
- **Security headers**: XSS protection, content type validation, etc.
- **Backend protection**: Backend is not directly exposed, only through Nginx
- **Non-root containers**: All services run as non-root users

## Environment Variables

### Required for all setups:

- `OPENAI_API_KEY`: Your OpenAI API key

### Optional variables (in `backend/.env`):

- `LANGSMITH_TRACING`: Enable LangSmith tracing (true/false)
- `LANGSMITH_ENDPOINT`: LangSmith endpoint URL
- `LANGSMITH_API_KEY`: LangSmith API key
- `LANGSMITH_PROJECT`: LangSmith project name

### Local Development (No LocalStack):

- `ENVIRONMENT=development`
- `LOG_LEVEL=debug`
- `DISABLE_AWS_SERVICES=true`

### Full Development (with LocalStack):

- `AWS_ENDPOINT_URL=http://localstack:4566`
- `AWS_ACCESS_KEY_ID=test`
- `AWS_SECRET_ACCESS_KEY=test`
- `AWS_DEFAULT_REGION=us-east-1`

## Development Workflow

1. **Frontend changes**: Edit files in `frontend/src/` - changes require rebuilding the container
2. **Backend changes**: Edit files in `backend/` - changes require rebuilding the container
3. **Environment changes**: Edit `backend/.env` file and restart containers

## When to Use Each Setup

### Use Local Development (No LocalStack) when:

- Working on frontend features
- Testing LLM/chat functionality
- General development and debugging
- Limited system resources
- Quick iteration cycles

### Use Full Development (with LocalStack) when:

- Testing AWS-dependent features
- Working on Lambda functions
- Testing SQS/S3 integrations
- Preparing for production deployment
- Full end-to-end testing

## Troubleshooting

### Common Issues

1. **Port 80 already in use**

   ```bash
   # Check what's using port 80
   sudo lsof -i :80
   # Stop the service or change the port in docker-compose files
   ```

2. **OpenAI API key not working**

   - Verify your API key is correct in `backend/.env`
   - Check OpenAI account has sufficient credits
   - Ensure the key has the right permissions

3. **LocalStack not starting** (full development only)
   ```bash
   # Check LocalStack logs
   docker-compose logs localstack
   ```

### Useful Commands

```bash
# Test environment variables
./scripts/test-env.sh

# View logs (local development)
docker-compose -f docker-compose.local.yml logs -f [service-name]

# View logs (full development)
docker-compose logs -f [service-name]

# Rebuild specific service
docker-compose -f docker-compose.local.yml build [service-name]

# Stop all services
docker-compose -f docker-compose.local.yml down

# Clean up volumes
docker-compose -f docker-compose.local.yml down -v
```

## Production Deployment

For production deployment, see the Terraform configuration in the `terraform/` directory.

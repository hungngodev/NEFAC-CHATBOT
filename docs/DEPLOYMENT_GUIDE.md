# NEFAC Deployment Guide

## 1. Overview

This guide details how to deploy the NEFAC Chatbot system using **Docker Compose**. This is the recommended method for self-hosted production environments, as it orchestrates the Frontend, Backend (LangGraph), and all necessary databases (Neo4j, Postgres, Redis, Qdrant, Elasticsearch) in a single command.

## 2. Prerequisites

*   **Docker Engine**: v24.0+
*   **Docker Compose**: v2.20+
*   **Hardware Requirements**:
    *   **RAM**: Minimum 16GB recommended (due to running 5+ databases and the LLM graph).
    *   **CPU**: 4+ Cores.
    *   **Disk**: 50GB+ SSD (for vector/graph indices).

## 3. Configuration

### 3.1 Environment Variables

1.  **Copy the Template**:
    Navigate to the project root and copy `.env.template` to `.env`.
    ```bash
    cp .env.template .env
    ```

2.  **Production Values**:
    Edit `.env` and update the following for production security:
    *   `NEO4J_PASSWORD`: Set a strong password.
    *   `POSTGRES_PASSWORD`: Set a strong password.
    *   `ELASTIC_PASSWORD`: Set a strong password.
    *   `OPENAI_API_KEY`: Ensure your key has sufficient quota.
    *   `TAVILY_API_KEY`: Required for web search.

    *Note: The `NEXT_PUBLIC_API_URL` in `.env` is used by the frontend container to talk to the backend. In Docker, this is usually `http://localhost:2024` (client-side browser access) or the public domain name.*

## 4. Deployment Command

The critical command to build and launch the entire stack is:

```bash
cd docker
docker-compose up -d --build
```

### What this command does:
1.  **Builds Images**:
    *   **Backend**: Builds from `backend/Dockerfile` (based on `langchain/langgraph-api`).
    *   **Frontend**: Builds from `client/Dockerfile` (Next.js production build).
2.  **Starts Databases**:
    *   `neo4j`, `postgres`, `redis`, `qdrant`, `elasticsearch`.
3.  **Networks**:
    *   Connects all services on the `nefacnet` bridge network.

## 5. Architecture & Ports

| Service | Internal Port | Host Port | Description |
| :--- | :--- | :--- | :--- |
| **Frontend** | 3000 | **3000** | Next.js UI. Access at `http://localhost:3000`. |
| **Backend** | 8000 | **8123** | LangGraph API. Access at `http://localhost:2024`. |
| **Neo4j** | 7474 | **7474** | Graph DB Browser. |
| **Qdrant** | 6333 | **6333** | Vector DB Dashboard. |
| **Kibana** | 5601 | **5601** | Elasticsearch Dashboard. |

## 6. Maintenance & Troubleshooting

### 6.1 Viewing Logs
To check the logs of the backend (Agent logic):
```bash
cd docker
docker-compose logs -f backend
```

### 6.2 Updating the Application
To deploy code changes:
1.  Pull the latest code: `git pull`
2.  Rebuild and restart:
    ```bash
    docker-compose up -d --build
    ```

### 6.3 Database Persistence
All data is persisted in named Docker volumes:
*   `backend_neo4j-data`
*   `backend_postgres-data`
*   `backend_qdrant-data`
*   `backend_es-data`

**Backup**: To back up, you can mount these volumes to a backup location or use the database-specific backup tools (e.g., `pg_dump`, Neo4j Dump).
*   **Elasticsearch Snapshots**: Mapped to `backup/` in the project root.

### 6.4 Common Issues
*   **"Connection Refused"**: The databases take time to start. The backend might restart a few times before connecting. This is normal (handled by `restart: always` or healthchecks).
*   **OOM (Out of Memory)**: Elasticsearch and Neo4j are memory hungry. If containers crash with code 137, increase your host RAM or adjust Docker memory limits.

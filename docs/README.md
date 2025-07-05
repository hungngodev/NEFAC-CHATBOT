# NEFAC Multi-Agent System Documentation

## Overview

The NEFAC Multi-Agent System is a production-ready, hierarchical RAG (Retrieval-Augmented Generation) system designed for legal information processing. The system uses a supervisor-worker architecture with intelligent query routing, comprehensive error handling, and full type safety.

## 🏗️ Architecture

The system follows a clean hierarchical structure:

```
┌─────────────────┐
│   Supervisor    │ ← Analyzes complexity & routes queries
└─────────┬───────┘
          │
┌─────────▼───────┐
│ Contextualizer  │ ← Processes & understands queries
└─────────┬───────┘
          │
    ┌─────▼─────┐
    │  Workers  │ ← Retrieval Agent OR ReAct Worker
    └─────┬─────┘
          │
┌─────────▼───────┐
│   Generator     │ ← Creates final answers
└─────────────────┘
```

## 📁 Documentation Structure

### Core Components
- **[`backend/src/schemas/`](./backend/schemas/README.md)** - Type definitions and state management
- **[`backend/src/core/agents/`](./backend/agents/README.md)** - Agent implementations
- **[`backend/src/services/`](./backend/services/README.md)** - Service layer and dependency injection
- **[`backend/src/exceptions/`](./backend/exceptions/README.md)** - Error handling system
- **[`backend/src/utils/`](./backend/utils/README.md)** - Utilities and validation

### Application Layer
- **[`backend/src/app/`](./backend/app/README.md)** - Main application and orchestration

### Architecture Details
- **[Architecture Overview](./architecture/README.md)** - Detailed system architecture
- **[Implementation Status](./architecture/IMPLEMENTATION_STATUS.md)** - Current implementation state

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- OpenAI API key
- Qdrant vector database
- Elasticsearch
- Neo4j (optional)

### Installation
```bash
cd backend
pip install -r requirements.txt
```

### Configuration
```bash
cp .env.template .env
# Edit .env with your API keys and service endpoints
```

### Running the System
```bash
python -m src.app.main
```

## 🎯 Key Features

### Type Safety
- **100% typed** - No `Any` types in production code
- **Protocol-based interfaces** - Clear contracts between components
- **Pydantic validation** - Runtime type checking and validation

### Error Handling
- **Structured exceptions** - Typed errors with context
- **Graceful degradation** - System continues operating on partial failures
- **Comprehensive logging** - Detailed error tracking and debugging

### Performance
- **Execution tracking** - Built-in timing for all operations
- **Confidence scoring** - Quality assessment for generated answers
- **Health monitoring** - Service status checking

### Scalability
- **Dependency injection** - Testable and modular architecture
- **Service abstraction** - Easy to swap implementations
- **Horizontal scaling** - Stateless design supports scaling

## 📊 System Metrics

The system tracks comprehensive metrics:
- **Query complexity scores** (0.0-1.0)
- **Execution times** for all operations
- **Confidence scores** for generated answers
- **Service health status**
- **Document retrieval statistics**

## 🔧 Development

### Code Quality
- **mypy** for static type checking
- **pylint** for code quality
- **black** for code formatting
- **pytest** for testing

### Testing
```bash
# Run type checking
mypy backend/src/

# Run tests
pytest backend/tests/

# Check code quality
pylint backend/src/
```

## 📖 Detailed Documentation

For detailed information about each component, see the folder-specific documentation:

1. **[Schemas & Types](./backend/schemas/README.md)** - Data models and type definitions
2. **[Core Agents](./backend/agents/README.md)** - Agent implementations and interfaces
3. **[Services](./backend/services/README.md)** - External service integrations
4. **[Application](./backend/app/README.md)** - Main application orchestration
5. **[Architecture](./architecture/README.md)** - System design and patterns

## 🤝 Contributing

1. Follow the existing code patterns
2. Maintain 100% type coverage
3. Add comprehensive error handling
4. Include execution metrics
5. Update documentation

## 📝 License

See [LICENSE](../LICENSE) for details.
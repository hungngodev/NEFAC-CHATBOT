# Backend Documentation

The backend implements a hierarchical multi-agent system with proper typing, error handling, and dependency injection.

## 📁 Structure Overview

```
backend/src/
├── schemas/          # Type definitions and data models
├── core/agents/      # Agent implementations
├── exceptions/       # Error handling system
├── utils/           # Utilities and validation
├── app/             # Main application orchestration
└── config/          # Configuration and prompts
```

## 🔗 Component Documentation

- **[Schemas & Types](./schemas/README.md)** - Data models, state management, and type definitions
- **[Core Agents](./agents/README.md)** - Agent implementations and interfaces
- **[Exceptions](./exceptions/README.md)** - Error handling and exception hierarchy
- **[Utils](./utils/README.md)** - Utilities, validation, and helper functions
- **[Application](./app/README.md)** - Main application and LangGraph orchestration

## 🎯 Key Principles

### Type Safety
- **No `Any` types** in production code
- **Protocol-based interfaces** for all components
- **Pydantic models** for data validation
- **Comprehensive type hints** throughout

### Error Handling
- **Structured exceptions** with context and severity
- **Graceful degradation** on service failures
- **Proper error propagation** through the system
- **Comprehensive logging** for debugging

### Architecture
- **Dependency injection** for testability
- **Service abstraction** for modularity
- **Clean separation** of concerns
- **Hierarchical organization** following documented patterns

## 🚀 Development Workflow

### Adding New Agents
1. Define protocols in `schemas/agent_protocols.py`
2. Create result types in `schemas/agent_types.py`
3. Implement agent in appropriate `core/agents/` subfolder
4. Add service dependencies if needed
5. Update orchestration in `app/multi_agent_app.py`

### Adding External Dependencies
1. Add direct imports to agent files
2. Handle configuration in agent initialization
3. Add error handling for external service failures

### Testing
- Mock external dependencies directly in agents
- Test error scenarios with structured exceptions
- Validate type safety with mypy
- Check performance with built-in metrics
# Documentation Structure

## Overview
Documentation has been reorganized for better project structure and maintainability.

## Current Structure

### Root `docs/` (Project-level documentation)
```
docs/
├── README.md                          # Project overview
├── DEVELOPMENT.md                     # Development setup guide
├── BACKLOG.MD                         # Project backlog and roadmap
├── DOCUMENTATION_INDEX.md             # Master documentation index
├── DOCUMENTATION_STRUCTURE.md         # This file - documentation organization
├── DOCS_REORGANIZATION_PLAN.md        # Reorganization planning document
├── crawler_README.md                  # Document crawler documentation
└── infrastructure/                    # Infrastructure documentation
    ├── AWS_INFRASTRUCTURE_SETUP.md    # AWS setup and configuration
    ├── aws_README.md                   # AWS-specific documentation
    └── terraform_README.md             # Terraform infrastructure docs
```

### Backend `backend/docs/` (Backend-specific documentation)
```
backend/docs/
├── README.md                          # Backend documentation index
├── ARCHITECTURE_SUMMARY.md           # High-level architecture overview
├── CURRENT_AGENT_FLOW.md             # Detailed agent flow diagram
├── BACKEND_ARCHITECTURE_REVISION.md  # Comprehensive architecture analysis
├── ADVANCED_RETRIEVAL_ARCHITECTURE.md # State-of-the-art RAG system details
├── QUERY_TRANSLATION_STRATEGIES.md   # 8 sophisticated query processing techniques
├── architecture/                     # Detailed component documentation
│   ├── README.md
│   ├── CURRENT_IMPLEMENTATION.md
│   ├── IMPLEMENTATION_STATUS.md
│   ├── 1_Supervisor_Agent/
│   ├── 2_Contextualizer/
│   ├── 3_Retriever_Worker/
│   ├── 4_ReAct_Worker/
│   ├── 5_Search_Tools/
│   ├── 6_Graph_Orchestration/
│   ├── 7_State_and_Memory/
│   ├── 9_Query_Complexity/
│   ├── 10_Memory_System/
│   └── 11_Hierarchical_Structure/
├── agents/                           # Agent-specific documentation (empty, ready for expansion)
├── schemas/                          # Schema documentation (empty, ready for expansion)
├── service/                          # Service documentation (empty, ready for expansion)
└── migration/                        # Migration and historical documentation
    ├── MIGRATION_GUIDE.md            # System migration documentation
    ├── STATE_UNIFICATION_SUMMARY.md  # State management changes
    ├── APP_FOLDER_CLEANUP_SUMMARY.md # Cleanup documentation
    └── IMPLEMENTATION_REVIEW.md      # Implementation analysis
```

## Benefits of New Structure

### 1. **Clear Separation of Concerns**
- **Project-level docs** in root `docs/` for general project information
- **Backend-specific docs** in `backend/docs/` co-located with backend code
- **Infrastructure docs** organized separately for DevOps concerns

### 2. **Better Maintainability**
- Documentation lives closer to the code it describes
- Easier to find relevant documentation when working on specific components
- Reduced documentation drift

### 3. **Scalable Organization**
- Ready for frontend documentation in `frontend/docs/`
- Component-specific documentation folders prepared
- Migration history preserved but organized

### 4. **Developer Experience**
- Backend developers can find all relevant docs in `backend/docs/`
- Infrastructure team has dedicated `docs/infrastructure/` folder
- Project overview remains easily accessible in root `docs/`

## Key Documentation Files

### Architecture Documentation
- **[CURRENT_AGENT_FLOW.md](../backend/docs/CURRENT_AGENT_FLOW.md)** - Visual flow diagram with sophisticated retrieval system
- **[ADVANCED_RETRIEVAL_ARCHITECTURE.md](../backend/docs/ADVANCED_RETRIEVAL_ARCHITECTURE.md)** - State-of-the-art RAG system details
- **[QUERY_TRANSLATION_STRATEGIES.md](../backend/docs/QUERY_TRANSLATION_STRATEGIES.md)** - 8 advanced query processing techniques

### Development Documentation
- **[DEVELOPMENT.md](DEVELOPMENT.md)** - Development environment setup
- **[BACKLOG.MD](BACKLOG.MD)** - Project roadmap and feature backlog

### Infrastructure Documentation
- **[AWS_INFRASTRUCTURE_SETUP.md](infrastructure/AWS_INFRASTRUCTURE_SETUP.md)** - AWS deployment guide
- **[terraform_README.md](infrastructure/terraform_README.md)** - Infrastructure as code

## Migration Notes

### Files Moved
- All backend architecture docs → `backend/docs/`
- Infrastructure docs → `docs/infrastructure/`
- Migration/historical docs → `backend/docs/migration/`
- Component architecture → `backend/docs/architecture/`

### Cross-References Updated
- Documentation links updated to reflect new structure
- README files created for each major section
- Master index maintained in root `docs/`

## Future Expansion

### Ready for Addition
- `frontend/docs/` - Frontend-specific documentation
- `backend/docs/agents/` - Individual agent documentation
- `backend/docs/schemas/` - Data model documentation
- `backend/docs/service/` - Service layer documentation

### Planned Enhancements
- API documentation generation
- Component-specific README files
- Performance benchmarking docs
- Deployment guides per environment
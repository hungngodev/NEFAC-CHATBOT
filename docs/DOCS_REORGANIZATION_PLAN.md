# Documentation Reorganization Plan

## Current Issues
- Backend-specific documentation scattered in root `docs/` folder
- Architecture documents not co-located with code
- Mixed project-level and component-level documentation

## Proposed Structure

### Root `docs/` (Project-level documentation)
```
docs/
├── README.md                          # Project overview
├── DEVELOPMENT.md                     # Development setup
├── BACKLOG.MD                         # Project backlog
├── DOCUMENTATION_INDEX.md             # Master documentation index
└── infrastructure/                    # Infrastructure docs
    ├── AWS_INFRASTRUCTURE_SETUP.md
    ├── aws_README.md
    └── terraform_README.md
```

### Backend `backend/docs/` (Backend-specific documentation)
```
backend/docs/
├── README.md                          # Backend overview
├── ARCHITECTURE_SUMMARY.md           # Architecture overview
├── CURRENT_AGENT_FLOW.md             # Agent flow diagram
├── BACKEND_ARCHITECTURE_REVISION.md  # Detailed architecture
├── ADVANCED_RETRIEVAL_ARCHITECTURE.md # Retrieval system details
├── QUERY_TRANSLATION_STRATEGIES.md   # Query processing strategies
├── agents/                           # Agent-specific docs
│   ├── README.md
│   ├── supervisor/
│   ├── contextualizer/
│   ├── workers/
│   └── tools/
├── schemas/                          # Schema documentation
├── service/                          # Service documentation
└── migration/                        # Migration guides
    ├── MIGRATION_GUIDE.md
    ├── STATE_UNIFICATION_SUMMARY.md
    └── APP_FOLDER_CLEANUP_SUMMARY.md
```

### Frontend `frontend/docs/` (Frontend-specific documentation)
```
frontend/docs/
├── README.md                         # Frontend overview
├── COMPONENT_ARCHITECTURE.md        # Component structure
└── UI_DESIGN_SYSTEM.md              # Design system docs
```

## Migration Steps

1. **Create backend/docs structure**
2. **Move backend-specific files**
3. **Update cross-references**
4. **Create component-specific docs**
5. **Update main README with new structure**

## Files to Move

### To `backend/docs/`:
- ARCHITECTURE_SUMMARY.md
- CURRENT_AGENT_FLOW.md  
- BACKEND_ARCHITECTURE_REVISION.md
- ADVANCED_RETRIEVAL_ARCHITECTURE.md
- QUERY_TRANSLATION_STRATEGIES.md
- MIGRATION_GUIDE.md
- STATE_UNIFICATION_SUMMARY.md
- APP_FOLDER_CLEANUP_SUMMARY.md
- IMPLEMENTATION_REVIEW.md

### To `docs/infrastructure/`:
- AWS_INFRASTRUCTURE_SETUP.md
- aws_README.md
- terraform_README.md

### Keep in root `docs/`:
- README.md
- DEVELOPMENT.md
- BACKLOG.MD
- DOCUMENTATION_INDEX.md
- crawler_README.md
- backend_README.md (rename to backend/docs/README.md)
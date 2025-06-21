# NEFAC Scripts

This directory contains utility scripts for the NEFAC project to help with development, testing, and code quality.

## Available Scripts

### 🎯 `format-lint.sh` - Code Quality & Formatting

Runs comprehensive code quality checks, formatting, and linting on both backend and frontend.

**Features:**

- ✅ Code formatting (Black for Python, Prettier for TypeScript)
- ✅ Import sorting and organization
- ✅ Linting (Ruff for Python, ESLint for TypeScript)
- ✅ Unused import/variable removal
- ✅ Pre-commit hooks execution
- ✅ Colored output with detailed status

**Usage:**

```bash
# Run all checks (default)
./scripts/format-lint.sh

# Run only backend checks
./scripts/format-lint.sh backend

# Run only frontend checks
./scripts/format-lint.sh frontend

# Show help
./scripts/format-lint.sh help
```

**What it checks:**

- **Backend:** Black, Ruff, Autoflake, pre-commit hooks
- **Frontend:** Prettier, ESLint, pre-commit hooks

---

### 🚀 `dev.sh` - Development Environment

Sets up and starts the development environment for the NEFAC project.

**Usage:**

```bash
./scripts/dev.sh
```

**What it does:**

- Starts backend development server
- Starts frontend development server
- Sets up necessary environment variables
- Runs in development mode with hot reloading

---

### 🏠 `local.sh` - Local Development Setup

Sets up the local development environment with all necessary services.

**Usage:**

```bash
./scripts/local.sh
```

**What it does:**

- Installs dependencies for both backend and frontend
- Sets up local database and services
- Configures environment for local development
- Starts all required services locally

---

### 🧪 `test.sh` - Testing

Runs tests for the project.

**Usage:**

```bash
./scripts/test.sh
```

**What it does:**

- Runs backend tests
- Runs frontend tests
- Generates test coverage reports
- Validates code quality

---

### 🧪 `test-env.sh` - Test Environment Setup

Sets up a test environment for running tests.

**Usage:**

```bash
./scripts/test-env.sh
```

**What it does:**

- Sets up test database
- Configures test environment variables
- Prepares test data
- Validates test environment

---

## Prerequisites

Before running these scripts, ensure you have the following installed:

### Backend Requirements

- **Python 3.9+**
- **Poetry** - Python dependency management
- **Docker** (optional, for containerized services)

### Frontend Requirements

- **Node.js 18+**
- **npm** or **yarn**

### General Requirements

- **Git**
- **Make** (optional, for some automation)

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd nefac
   ```

2. **Install backend dependencies:**

   ```bash
   cd backend
   poetry install
   ```

3. **Install frontend dependencies:**

   ```bash
   cd frontend
   npm install
   ```

4. **Make scripts executable:**
   ```bash
   chmod +x scripts/*.sh
   ```

## Common Workflows

### 🆕 Starting Development

```bash
# Set up local environment
./scripts/local.sh

# Start development servers
./scripts/dev.sh
```

### 🔄 Code Quality Check

```bash
# Run all quality checks
./scripts/format-lint.sh

# Fix formatting issues automatically
./scripts/format-lint.sh
```

### 🧪 Running Tests

```bash
# Set up test environment
./scripts/test-env.sh

# Run tests
./scripts/test.sh
```

### 🚀 Production Deployment

```bash
# Build and deploy
docker-compose up --build
```

## Troubleshooting

### Script Permission Issues

If you get permission denied errors:

```bash
chmod +x scripts/*.sh
```

### Dependency Issues

If scripts fail due to missing dependencies:

**Backend:**

```bash
cd backend
poetry install
```

**Frontend:**

```bash
cd frontend
npm install
```

### Environment Issues

If environment variables are missing:

```bash
# Copy environment template
cp backend/.env.template backend/.env
cp frontend/.env.template frontend/.env

# Edit with your values
nano backend/.env
nano frontend/.env
```

## Script Development

When adding new scripts:

1. **Follow naming convention:** Use descriptive names with `.sh` extension
2. **Add error handling:** Use `set -e` and proper error messages
3. **Add help text:** Include `--help` option for all scripts
4. **Update this README:** Document new scripts here
5. **Make executable:** Ensure scripts are executable

### Script Template

```bash
#!/bin/bash

# Script description
# Usage: ./script-name.sh [options]

set -e

# Help function
show_help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -h, --help    Show this help message"
    # Add more options here
}

# Main logic
main() {
    case "${1:-}" in
        -h|--help)
            show_help
            ;;
        *)
            # Main script logic here
            ;;
    esac
}

main "$@"
```

## Contributing

When contributing to scripts:

1. **Test thoroughly** - Ensure scripts work on different environments
2. **Add documentation** - Update this README with new features
3. **Follow conventions** - Use consistent naming and structure
4. **Handle errors gracefully** - Provide helpful error messages
5. **Make portable** - Avoid hardcoded paths or system-specific commands

## License

This project is licensed under the same license as the main NEFAC project.

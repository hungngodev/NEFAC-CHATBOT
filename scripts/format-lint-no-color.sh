#!/bin/bash

# NEFAC Code Quality Script (No Color)
# Runs formatting, linting, and all code quality checks on both backend and frontend.
# This version does not use color codes to avoid terminal rendering issues.

set -e  # Exit on any error

# Function to print plain output
print_status() {
    echo "[INFO] $1"
}

print_success() {
    echo "[SUCCESS] $1"
}

print_warning() {
    echo "[WARNING] $1"
}

print_error() {
    echo "[ERROR] $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

print_status "Starting code quality checks for NEFAC project"
print_status "Project root: $PROJECT_ROOT"

# Check if we're in the right directory
if [ ! -d "$BACKEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
    print_error "Backend or frontend directory not found. Please run this script from the project root."
    exit 1
fi

# Function to run backend checks
run_backend_checks() {
    print_status "Running backend code quality checks..."
    cd "$BACKEND_DIR"
    
    # Check if poetry is installed
    if ! command_exists poetry; then
        print_error "Poetry is not installed. Please install Poetry first."
        return 1
    fi
    
    # Check if dependencies are installed
    if [ ! -f "poetry.lock" ]; then
        print_warning "Poetry lock file not found. Installing dependencies..."
        poetry install
    fi
    
    # Run Black formatting
    print_status "Running Black formatter..."
    poetry run black . --check || {
        print_warning "Black found formatting issues. Running Black to fix..."
        poetry run black .
    }
    
    # Run Ruff linting and import sorting
    print_status "Running Ruff linter and import sorter..."
    poetry run ruff check --fix . || {
        print_error "Ruff found issues that couldn't be auto-fixed"
        return 1
    }
    
    # Run autoflake to remove unused imports
    print_status "Running autoflake to remove unused imports..."
    poetry run autoflake --remove-all-unused-imports --remove-unused-variables --in-place --recursive . || {
        print_warning "Autoflake encountered issues"
    }
    
    # Run pre-commit hooks if available
    if command_exists pre-commit; then
        print_status "Running pre-commit hooks..."
        poetry run pre-commit run --all-files || {
            print_warning "Some pre-commit hooks failed"
        }
    fi
    
    print_success "Backend checks completed!"
}

# Function to run frontend checks
run_frontend_checks() {
    print_status "Running frontend code quality checks..."
    cd "$FRONTEND_DIR"
    
    # Check if npm is installed
    if ! command_exists npm; then
        print_error "npm is not installed. Please install Node.js and npm first."
        return 1
    fi
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_warning "node_modules not found. Installing dependencies..."
        npm install
    fi
    
    # Run Prettier formatting
    print_status "Running Prettier formatter..."
    npm run format || {
        print_warning "Prettier found formatting issues. Running Prettier to fix..."
        npm run format
    }
    
    # Run ESLint
    print_status "Running ESLint..."
    npm run lint || {
        print_error "ESLint found issues"
        return 1
    }
    
    # Run pre-commit hooks if available
    if command_exists pre-commit; then
        print_status "Running pre-commit hooks..."
        pre-commit run --all-files || {
            print_warning "Some pre-commit hooks failed"
        }
    fi
    
    print_success "Frontend checks completed!"
}

# Function to run all checks
run_all_checks() {
    print_status "Running all code quality checks..."
    
    # Run backend checks
    if run_backend_checks; then
        print_success "Backend checks passed!"
    else
        print_error "Backend checks failed!"
        BACKEND_FAILED=true
    fi
    
    # Run frontend checks
    if run_frontend_checks; then
        print_success "Frontend checks passed!"
    else
        print_error "Frontend checks failed!"
        FRONTEND_FAILED=true
    fi
    
    # Summary
    echo ""
    print_status "=== Code Quality Check Summary ==="
    
    if [ "$BACKEND_FAILED" = true ]; then
        print_error "Backend: FAILED"
    else
        print_success "Backend: PASSED"
    fi
    
    if [ "$FRONTEND_FAILED" = true ]; then
        print_error "Frontend: FAILED"
    else
        print_success "Frontend: PASSED"
    fi
    
    if [ "$BACKEND_FAILED" = true ] || [ "$FRONTEND_FAILED" = true ]; then
        print_error "Some checks failed. Please fix the issues and run again."
        exit 1
    else
        print_success "All code quality checks passed! 🎉"
    fi
}

# Main execution
main() {
    case "${1:-all}" in
        "backend")
            run_backend_checks
            ;;
        "frontend")
            run_frontend_checks
            ;;
        "all"|"")
            run_all_checks
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [backend|frontend|all|help]"
            echo ""
            echo "Options:"
            echo "  backend   - Run checks only on backend"
            echo "  frontend  - Run checks only on frontend"
            echo "  all       - Run checks on both backend and frontend (default)"
            echo "  help      - Show this help message"
            echo ""
            echo "This script runs:"
            echo "  Backend:  Black, Ruff, Autoflake, pre-commit hooks"
            echo "  Frontend: Prettier, ESLint, pre-commit hooks"
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@" 
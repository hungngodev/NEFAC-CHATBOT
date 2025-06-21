#!/bin/bash

# NEFAC Code Quality Debug Script
# This script is for debugging terminal rendering issues.
# It logs the output of each command to /tmp/nefac-logs/

set -e  # Exit on any error
set -x # Print each command before executing it

# --- Setup Logging ---
LOG_DIR="/tmp/nefac-logs"
mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR"/* # Clean up old logs
echo "Log files will be stored in $LOG_DIR"

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
    
    if ! command_exists poetry; then
        print_error "Poetry is not installed."
        return 1
    fi
    
    if [ ! -f "poetry.lock" ]; then
        print_warning "Poetry lock file not found. Installing dependencies..."
        poetry install > "$LOG_DIR/backend-poetry-install.log" 2>&1
    fi
    
    print_status "Running Black formatter..."
    poetry run black . --check > "$LOG_DIR/backend-black-check.log" 2>&1 || {
        print_warning "Black found formatting issues. Running Black to fix..."
        poetry run black . > "$LOG_DIR/backend-black-fix.log" 2>&1
    }
    
    print_status "Running Ruff linter..."
    poetry run ruff check --fix . > "$LOG_DIR/backend-ruff-check.log" 2>&1 || {
        print_error "Ruff found issues that couldn't be auto-fixed"
        return 1
    }
    
    print_status "Running autoflake..."
    poetry run autoflake --remove-all-unused-imports --in-place --recursive . > "$LOG_DIR/backend-autoflake.log" 2>&1 || {
        print_warning "Autoflake encountered issues"
    }
    
    print_success "Backend checks completed!"
}

# Function to run frontend checks
run_frontend_checks() {
    print_status "Running frontend code quality checks..."
    cd "$FRONTEND_DIR"
    
    if ! command_exists npm; then
        print_error "npm is not installed."
        return 1
    fi
    
    if [ ! -d "node_modules" ]; then
        print_warning "node_modules not found. Installing dependencies..."
        npm install > "$LOG_DIR/frontend-npm-install.log" 2>&1
    fi
    
    print_status "Running Prettier formatter..."
    npm run format > "$LOG_DIR/frontend-prettier.log" 2>&1 || {
        print_warning "Prettier found formatting issues."
    }
    
    print_status "Running ESLint..."
    npm run lint > "$LOG_DIR/frontend-eslint.log" 2>&1 || {
        print_error "ESLint found issues"
        return 1
    }
    
    print_success "Frontend checks completed!"
}

# Main execution
print_status "Running all checks..."
run_backend_checks
run_frontend_checks
print_success "All checks finished."
set +x # Turn off tracing
echo "Debug script finished. Check logs in $LOG_DIR" 
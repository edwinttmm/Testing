#!/bin/bash

# Script to fix PostgreSQL enum values in Docker container
# Can be run from host or inside Docker container

set -e

echo "PostgreSQL Enum Fix Runner"
echo "=========================="

# Function to check if docker-compose is available
check_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif command -v docker compose &> /dev/null; then
        echo "docker compose"
    else
        echo ""
    fi
}

# Function to run the fix script
run_enum_fix() {
    local method=$1
    
    case $method in
        "host")
            echo "Running enum fix from host..."
            python3 /home/user/Testing/ai-model-validation-platform/backend/scripts/fix_postgresql_enums.py
            ;;
        "docker")
            echo "Running enum fix inside Docker container..."
            DOCKER_COMPOSE=$(check_docker_compose)
            if [ -z "$DOCKER_COMPOSE" ]; then
                echo "Error: docker-compose not found"
                exit 1
            fi
            
            # Navigate to project root
            cd /home/user/Testing/ai-model-validation-platform
            
            # Run the script inside the backend container
            $DOCKER_COMPOSE exec -T backend python scripts/fix_postgresql_enums.py
            ;;
        "sql")
            echo "Running SQL script directly against PostgreSQL..."
            DOCKER_COMPOSE=$(check_docker_compose)
            if [ -z "$DOCKER_COMPOSE" ]; then
                echo "Error: docker-compose not found"
                exit 1
            fi
            
            cd /home/user/Testing/ai-model-validation-platform
            
            # Run SQL script directly in postgres container
            $DOCKER_COMPOSE exec -T postgres psql -U postgres -d vru_validation -f /dev/stdin < backend/scripts/fix_postgresql_enum_values.sql
            ;;
        *)
            echo "Invalid method: $method"
            echo "Usage: $0 [host|docker|sql]"
            exit 1
            ;;
    esac
}

# Determine the best method to run
if [ $# -eq 0 ]; then
    echo "Choose fix method:"
    echo "1. host   - Run Python script from host (requires psycopg2)"
    echo "2. docker - Run Python script inside backend container"
    echo "3. sql    - Run SQL script directly in postgres container"
    echo ""
    read -p "Enter choice (1-3) or method name: " choice
    
    case $choice in
        1|"host") method="host" ;;
        2|"docker") method="docker" ;;
        3|"sql") method="sql" ;;
        *) method="$choice" ;;
    esac
else
    method="$1"
fi

echo ""
echo "Selected method: $method"
echo ""

# Check if containers are running (for docker/sql methods)
if [ "$method" != "host" ]; then
    DOCKER_COMPOSE=$(check_docker_compose)
    if [ -n "$DOCKER_COMPOSE" ]; then
        cd /home/user/Testing/ai-model-validation-platform
        
        # Check if postgres container is running
        if ! $DOCKER_COMPOSE ps postgres | grep -q "Up"; then
            echo "Error: PostgreSQL container is not running"
            echo "Start it with: $DOCKER_COMPOSE up postgres -d"
            exit 1
        fi
        
        # Check if backend container is running (for docker method)
        if [ "$method" = "docker" ] && ! $DOCKER_COMPOSE ps backend | grep -q "Up"; then
            echo "Error: Backend container is not running"
            echo "Start it with: $DOCKER_COMPOSE up backend -d"
            exit 1
        fi
    fi
fi

# Set environment variables for host method
if [ "$method" = "host" ]; then
    export POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    export POSTGRES_PORT=${POSTGRES_PORT:-5432}
    export POSTGRES_DB=${POSTGRES_DB:-vru_validation}
    export POSTGRES_USER=${POSTGRES_USER:-postgres}
    export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-secure_password_change_me}
    
    echo "Using connection:"
    echo "  Host: $POSTGRES_HOST"
    echo "  Port: $POSTGRES_PORT"
    echo "  Database: $POSTGRES_DB"
    echo "  User: $POSTGRES_USER"
    echo ""
fi

# Run the fix
run_enum_fix "$method"

echo ""
echo "Enum fix completed!"
echo "Check the output above for results."
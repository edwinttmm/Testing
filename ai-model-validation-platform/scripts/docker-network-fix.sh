#!/bin/bash

# Docker Network Fix Script
# This script provides automated fixes for common Docker networking issues

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_NAME="ai-model-validation-platform"
NETWORK_NAME="vru_validation_network"
COMPOSE_FILE="docker-compose.yml"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check if docker-compose file exists
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        print_error "docker-compose.yml not found in current directory"
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null; then
        print_error "docker-compose not found. Please install docker-compose."
        exit 1
    fi
    
    print_status "Prerequisites check passed ✓"
}

# Clean up existing resources
cleanup_existing() {
    print_header "Cleaning Up Existing Resources"
    
    # Stop all containers
    print_status "Stopping all containers..."
    docker-compose down --remove-orphans --volumes 2>/dev/null || true
    
    # Remove any dangling containers
    print_status "Removing dangling containers..."
    docker container prune -f 2>/dev/null || true
    
    # Remove existing network if it exists
    if docker network ls | grep -q "$NETWORK_NAME"; then
        print_status "Removing existing network: $NETWORK_NAME"
        docker network rm "$NETWORK_NAME" 2>/dev/null || true
    fi
    
    # Clean up any orphaned volumes (optional)
    print_status "Cleaning up orphaned volumes..."
    docker volume prune -f 2>/dev/null || true
    
    print_status "Cleanup completed ✓"
}

# Create network with proper configuration
create_network() {
    print_header "Creating Docker Network"
    
    print_status "Creating network: $NETWORK_NAME"
    docker network create "$NETWORK_NAME" \
        --driver bridge \
        --subnet 172.20.0.0/16 \
        --gateway 172.20.0.1 \
        --opt com.docker.network.bridge.enable_icc=true \
        --opt com.docker.network.bridge.enable_ip_masquerade=true \
        --opt com.docker.network.driver.mtu=1500
    
    print_status "Network created successfully ✓"
    
    # Verify network
    print_status "Verifying network configuration..."
    docker network inspect "$NETWORK_NAME" --format '{{json .IPAM.Config}}' | \
        jq -r '.[0] | "Subnet: " + .Subnet + ", Gateway: " + .Gateway'
}

# Start services in correct order
start_services() {
    print_header "Starting Services in Correct Order"
    
    # Start database first
    print_status "Starting PostgreSQL database..."
    docker-compose up -d postgres
    
    # Wait for PostgreSQL to be ready
    print_status "Waiting for PostgreSQL to be ready..."
    timeout=60
    counter=0
    while ! docker-compose exec -T postgres pg_isready -U postgres -d vru_validation &> /dev/null; do
        if [ $counter -ge $timeout ]; then
            print_error "PostgreSQL failed to start within $timeout seconds"
            exit 1
        fi
        sleep 2
        counter=$((counter + 2))
        echo -n "."
    done
    echo ""
    print_status "PostgreSQL is ready ✓"
    
    # Start Redis
    print_status "Starting Redis..."
    docker-compose up -d redis
    
    # Wait for Redis to be ready
    print_status "Waiting for Redis to be ready..."
    timeout=30
    counter=0
    while ! docker-compose exec -T redis redis-cli --raw incr ping &> /dev/null; do
        if [ $counter -ge $timeout ]; then
            print_error "Redis failed to start within $timeout seconds"
            exit 1
        fi
        sleep 2
        counter=$((counter + 2))
        echo -n "."
    done
    echo ""
    print_status "Redis is ready ✓"
    
    # Start backend
    print_status "Starting backend application..."
    docker-compose up -d backend
    
    # Wait for backend to be ready
    print_status "Waiting for backend to be ready..."
    timeout=120
    counter=0
    while ! curl -sf http://localhost:8000/health &> /dev/null; do
        if [ $counter -ge $timeout ]; then
            print_warning "Backend may not be fully ready yet (timeout after $timeout seconds)"
            break
        fi
        sleep 5
        counter=$((counter + 5))
        echo -n "."
    done
    echo ""
    
    # Check if backend is responding
    if curl -sf http://localhost:8000/health &> /dev/null; then
        print_status "Backend is ready ✓"
    else
        print_warning "Backend may still be starting up"
    fi
    
    # Start frontend
    print_status "Starting frontend application..."
    docker-compose up -d frontend
    
    print_status "All services started ✓"
}

# Test connectivity
test_connectivity() {
    print_header "Testing Container Connectivity"
    
    # Wait a bit for containers to fully initialize
    print_status "Waiting for containers to initialize..."
    sleep 10
    
    # Test database connection from backend
    print_status "Testing backend → database connection..."
    if docker-compose exec -T backend python /app/scripts/test-database-connection.py &> /dev/null; then
        print_status "Backend → Database connectivity: ✓"
    else
        print_warning "Backend → Database connectivity: May still be initializing"
        # Show backend logs for debugging
        echo "Backend logs (last 10 lines):"
        docker-compose logs --tail 10 backend
    fi
    
    # Test Redis connection
    print_status "Testing Redis connectivity..."
    if docker-compose exec -T backend python -c "
import redis
import os
r = redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379'))
r.ping()
print('Redis connection successful')
" &> /dev/null; then
        print_status "Backend → Redis connectivity: ✓"
    else
        print_warning "Backend → Redis connectivity: Issue detected"
    fi
    
    # Test DNS resolution
    print_status "Testing DNS resolution..."
    containers=("postgres" "redis" "backend")
    for container in "${containers[@]}"; do
        if docker-compose exec -T backend nslookup "$container" &> /dev/null; then
            print_status "DNS resolution ($container): ✓"
        else
            print_warning "DNS resolution ($container): ✗"
        fi
    done
}

# Show status
show_status() {
    print_header "Current Status"
    
    echo "Container Status:"
    docker-compose ps
    
    echo ""
    echo "Network Information:"
    docker network inspect "$NETWORK_NAME" --format '{{json .}}' | jq -r '
    "Network Name: " + .Name + 
    "\nDriver: " + .Driver +
    "\nSubnet: " + .IPAM.Config[0].Subnet +
    "\nGateway: " + .IPAM.Config[0].Gateway'
    
    echo ""
    echo "Service Endpoints:"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend API: http://localhost:8000"
    echo "  Backend Health: http://localhost:8000/health"
    echo "  PostgreSQL: localhost:5432"
    echo "  Redis: localhost:6379"
}

# Main fix function
main_fix() {
    print_header "Docker Network Fix - Starting"
    echo "This script will fix Docker networking issues by:"
    echo "1. Cleaning up existing resources"
    echo "2. Creating proper network configuration" 
    echo "3. Starting services in correct order"
    echo "4. Testing connectivity"
    echo ""
    
    # Confirm with user unless --auto flag is passed
    if [[ "$1" != "--auto" && "$1" != "-y" ]]; then
        read -p "Do you want to continue? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Aborted by user"
            exit 0
        fi
    fi
    
    # Run fix steps
    check_prerequisites
    cleanup_existing
    create_network
    start_services
    test_connectivity
    show_status
    
    print_header "Fix Complete"
    print_status "Docker network fix completed successfully!"
    print_status "Your services should now be able to communicate properly."
    print_status "Check the service endpoints listed above to verify everything is working."
}

# Quick health check
quick_check() {
    print_header "Quick Health Check"
    
    # Check if containers are running
    containers=("postgres" "redis" "backend" "frontend")
    for container in "${containers[@]}"; do
        container_name="ai_validation_$container"
        if docker ps --format "{{.Names}}" | grep -q "$container_name"; then
            status=$(docker ps --format "{{.Status}}" --filter "name=$container_name")
            print_status "$container: $status"
        else
            print_warning "$container: Not running"
        fi
    done
    
    # Quick connectivity test
    if docker-compose exec -T backend ping -c 1 postgres &> /dev/null; then
        print_status "Network connectivity: ✓"
    else
        print_warning "Network connectivity: Issues detected"
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --fix, -f          Run complete network fix"
    echo "  --auto, -y         Run fix without confirmation"
    echo "  --check, -c        Quick health check"
    echo "  --status, -s       Show current status"
    echo "  --help, -h         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --fix           # Run interactive fix"
    echo "  $0 --auto          # Run automatic fix"
    echo "  $0 --check         # Quick health check"
}

# Main script execution
case "${1:-}" in
    --fix|-f)
        main_fix "$2"
        ;;
    --auto|-y)
        main_fix --auto
        ;;
    --check|-c)
        quick_check
        ;;
    --status|-s)
        show_status
        ;;
    --help|-h)
        show_usage
        ;;
    *)
        show_usage
        echo ""
        print_status "Use --fix to run the complete network fix"
        ;;
esac
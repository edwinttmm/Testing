#!/bin/bash

# Docker Network Troubleshooting Script
# This script helps diagnose and fix Docker container networking issues

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Docker Network Troubleshooting Script ===${NC}"
echo "This script will help diagnose and fix Docker networking issues"
echo ""

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

# Check if Docker is running
check_docker() {
    print_status "Checking Docker status..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        return 1
    fi
    
    print_status "Docker is running ✓"
}

# Check network configuration
check_network() {
    print_status "Checking Docker network configuration..."
    
    # Check if our network exists
    if docker network ls | grep -q "vru_validation_network"; then
        print_status "vru_validation_network exists ✓"
        
        # Show network details
        echo ""
        echo "Network Details:"
        docker network inspect vru_validation_network --format '{{json .}}' | jq -r '
        "Subnet: " + .IPAM.Config[0].Subnet + 
        "\nGateway: " + .IPAM.Config[0].Gateway +
        "\nDriver: " + .Driver'
    else
        print_warning "vru_validation_network does not exist"
        print_status "Creating network..."
        docker network create vru_validation_network --driver bridge
    fi
}

# Check container status
check_containers() {
    print_status "Checking container status..."
    echo ""
    
    containers=("ai_validation_postgres" "ai_validation_redis" "ai_validation_backend" "ai_validation_frontend")
    
    for container in "${containers[@]}"; do
        if docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -q "$container"; then
            status=$(docker ps -a --format "{{.Status}}" --filter "name=$container")
            if [[ $status == *"Up"* ]]; then
                print_status "$container: $status ✓"
            else
                print_warning "$container: $status"
            fi
        else
            print_warning "$container: Not found"
        fi
    done
}

# Test network connectivity between containers
test_connectivity() {
    print_status "Testing inter-container connectivity..."
    echo ""
    
    # Check if postgres is reachable from backend
    if docker ps --filter "name=ai_validation_backend" --filter "status=running" -q | head -n1 | xargs -r -I {} docker exec {} ping -c 2 postgres &> /dev/null; then
        print_status "Backend → Postgres connectivity: ✓"
    else
        print_error "Backend → Postgres connectivity: ✗"
    fi
    
    # Check if redis is reachable from backend  
    if docker ps --filter "name=ai_validation_backend" --filter "status=running" -q | head -n1 | xargs -r -I {} docker exec {} ping -c 2 redis &> /dev/null; then
        print_status "Backend → Redis connectivity: ✓"
    else
        print_error "Backend → Redis connectivity: ✗"
    fi
    
    # Check if backend is reachable from frontend
    if docker ps --filter "name=ai_validation_frontend" --filter "status=running" -q | head -n1 | xargs -r -I {} docker exec {} ping -c 2 backend &> /dev/null; then
        print_status "Frontend → Backend connectivity: ✓"
    else
        print_error "Frontend → Backend connectivity: ✗"
    fi
}

# Test database connection
test_database_connection() {
    print_status "Testing database connection..."
    echo ""
    
    # Test PostgreSQL connection
    if docker ps --filter "name=ai_validation_postgres" --filter "status=running" -q | head -n1 | xargs -r -I {} docker exec {} pg_isready -U postgres -d vru_validation &> /dev/null; then
        print_status "PostgreSQL health check: ✓"
    else
        print_error "PostgreSQL health check: ✗"
    fi
    
    # Test Redis connection  
    if docker ps --filter "name=ai_validation_redis" --filter "status=running" -q | head -n1 | xargs -r -I {} docker exec {} redis-cli --raw incr ping &> /dev/null; then
        print_status "Redis health check: ✓"
    else
        print_error "Redis health check: ✗"
    fi
}

# Show container logs
show_container_logs() {
    print_status "Showing recent container logs..."
    echo ""
    
    containers=("ai_validation_postgres" "ai_validation_redis" "ai_validation_backend")
    
    for container in "${containers[@]}"; do
        if docker ps -a --filter "name=$container" -q | head -n1 | xargs -r -I {} test -n {}; then
            echo -e "${BLUE}=== $container logs (last 20 lines) ===${NC}"
            docker logs --tail 20 "$container" 2>&1 | head -20
            echo ""
        fi
    done
}

# DNS resolution test
test_dns_resolution() {
    print_status "Testing DNS resolution within containers..."
    echo ""
    
    # Test DNS from backend container
    if docker ps --filter "name=ai_validation_backend" --filter "status=running" -q | head -n1 | xargs -r -I {} docker exec {} nslookup postgres &> /dev/null; then
        print_status "Backend DNS resolution (postgres): ✓"
    else
        print_error "Backend DNS resolution (postgres): ✗"
    fi
    
    if docker ps --filter "name=ai_validation_backend" --filter "status=running" -q | head -n1 | xargs -r -I {} docker exec {} nslookup redis &> /dev/null; then
        print_status "Backend DNS resolution (redis): ✓"
    else
        print_error "Backend DNS resolution (redis): ✗"
    fi
}

# Restart containers in correct order
restart_containers() {
    print_status "Restarting containers in correct order..."
    echo ""
    
    # Stop all containers
    print_status "Stopping all containers..."
    docker-compose down --remove-orphans
    
    # Start database and redis first
    print_status "Starting database and redis..."
    docker-compose up -d postgres redis
    
    # Wait for health checks
    print_status "Waiting for database to be ready..."
    sleep 15
    
    # Start backend
    print_status "Starting backend..."
    docker-compose up -d backend
    
    # Wait for backend health check
    sleep 10
    
    # Start frontend
    print_status "Starting frontend..."
    docker-compose up -d frontend
    
    print_status "All containers restarted ✓"
}

# Fix network issues
fix_network_issues() {
    print_status "Attempting to fix network issues..."
    echo ""
    
    # Remove existing network if it exists
    if docker network ls | grep -q "vru_validation_network"; then
        print_status "Removing existing network..."
        docker network rm vru_validation_network 2>/dev/null || true
    fi
    
    # Recreate network
    print_status "Creating new network with correct configuration..."
    docker network create vru_validation_network \
        --driver bridge \
        --subnet 172.20.0.0/16 \
        --gateway 172.20.0.1 \
        --opt com.docker.network.bridge.enable_icc=true \
        --opt com.docker.network.bridge.enable_ip_masquerade=true
    
    # Restart containers
    restart_containers
}

# Main menu
show_menu() {
    echo ""
    echo -e "${BLUE}=== Troubleshooting Options ===${NC}"
    echo "1. Check Docker status"
    echo "2. Check network configuration"
    echo "3. Check container status"
    echo "4. Test connectivity between containers"
    echo "5. Test database connections"
    echo "6. Test DNS resolution"
    echo "7. Show container logs"
    echo "8. Restart containers in correct order"
    echo "9. Fix network issues (comprehensive fix)"
    echo "10. Run all checks"
    echo "0. Exit"
    echo ""
    echo -n "Choose an option: "
}

# Run all checks
run_all_checks() {
    check_docker
    echo ""
    check_network
    echo ""
    check_containers
    echo ""
    test_connectivity
    echo ""
    test_database_connection
    echo ""
    test_dns_resolution
    echo ""
}

# Main script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -eq 1 && $1 == "auto" ]]; then
        # Run all checks automatically
        run_all_checks
        exit 0
    fi
    
    while true; do
        show_menu
        read -r choice
        
        case $choice in
            1) check_docker ;;
            2) check_network ;;
            3) check_containers ;;
            4) test_connectivity ;;
            5) test_database_connection ;;
            6) test_dns_resolution ;;
            7) show_container_logs ;;
            8) restart_containers ;;
            9) fix_network_issues ;;
            10) run_all_checks ;;
            0) echo "Exiting..."; exit 0 ;;
            *) print_error "Invalid option. Please try again." ;;
        esac
        
        echo ""
        echo "Press Enter to continue..."
        read -r
    done
fi
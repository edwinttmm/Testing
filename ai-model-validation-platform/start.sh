#!/bin/bash

# ==============================================================================
# AI Model Validation Platform - Comprehensive Startup Script
# ==============================================================================
# This script provides multiple ways to start the complete platform:
# 1. Docker Compose (Full Production Setup with CVAT)
# 2. Docker Compose Simple (Basic Setup - Backend + Frontend + Database)
# 3. Manual Development Setup (No Docker)
# 4. Health Checks and Service Monitoring
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Platform URLs
FRONTEND_URL="http://localhost:3000"
BACKEND_URL="http://localhost:8000"
BACKEND_API_URL="http://localhost:8000/api"
BACKEND_DOCS_URL="http://localhost:8000/docs"
CVAT_URL="http://localhost:8080"
DB_PORT="5432"
REDIS_PORT="6379"

# Configuration
DEFAULT_MODE="simple"
COMPOSE_FILE=""
PROJECT_NAME="ai-validation-platform"

# ==============================================================================
# Helper Functions
# ==============================================================================

print_header() {
    echo -e "${CYAN}==============================================="
    echo -e "🚀 AI Model Validation Platform Startup"
    echo -e "===============================================${NC}"
    echo
}

print_section() {
    echo -e "\n${BLUE}📋 $1${NC}"
    echo "----------------------------------------"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

print_urls() {
    echo -e "\n${PURPLE}🌐 Access URLs:${NC}"
    echo -e "   Frontend (React):     ${GREEN}${FRONTEND_URL}${NC}"
    echo -e "   Backend API:          ${GREEN}${BACKEND_API_URL}${NC}"
    echo -e "   API Documentation:    ${GREEN}${BACKEND_DOCS_URL}${NC}"
    echo -e "   Backend Health:       ${GREEN}${BACKEND_URL}/health${NC}"
    if [[ "$1" == "full" ]]; then
        echo -e "   CVAT Annotation:      ${GREEN}${CVAT_URL}${NC}"
    fi
    echo
}

check_prerequisites() {
    print_section "Checking Prerequisites"
    
    local missing_tools=()
    
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        missing_tools+=("docker-compose")
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        echo -e "\n${YELLOW}Please install Docker and Docker Compose:${NC}"
        echo "  Ubuntu/Debian: sudo apt-get update && sudo apt-get install docker.io docker-compose"
        echo "  macOS: brew install docker docker-compose"
        echo "  Windows: Download Docker Desktop from docker.com"
        return 1
    fi
    
    print_success "Docker and Docker Compose are installed"
    return 0
}

check_ports() {
    print_section "Checking Port Availability"
    
    local ports=("3000" "8000" "5432" "6379")
    if [[ "$1" == "full" ]]; then
        ports+=("8080")
    fi
    
    local busy_ports=()
    
    for port in "${ports[@]}"; do
        if lsof -i :$port &> /dev/null; then
            busy_ports+=("$port")
        fi
    done
    
    if [[ ${#busy_ports[@]} -gt 0 ]]; then
        print_warning "Ports in use: ${busy_ports[*]}"
        echo -e "${YELLOW}These ports need to be free for the platform to work correctly.${NC}"
        echo -e "${YELLOW}You can stop processes using these ports or use different ports.${NC}"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    else
        print_success "All required ports are available"
    fi
    
    return 0
}

create_env_file() {
    if [[ ! -f .env ]]; then
        print_section "Creating Environment Configuration"
        if [[ -f .env.production ]]; then
            print_info "Copying production environment template"
            cp .env.production .env
        elif [[ -f backend/.env.example ]]; then
            print_info "Copying backend environment template"
            cp backend/.env.example .env
        else
            print_info "Creating basic environment configuration"
            cat > .env << 'EOF'
# AI Model Validation Platform Environment
VRU_ENVIRONMENT=development
NODE_ENV=development

# Database Configuration
VRU_DATABASE_NAME=vru_validation
VRU_DATABASE_USER=postgres
VRU_DATABASE_PASSWORD=password
VRU_DATABASE_URL=postgresql://postgres:password@postgres:5432/vru_validation

# Redis Configuration
VRU_REDIS_PASSWORD=redis_password
VRU_REDIS_URL=redis://:redis_password@redis:6379/0

# Security
VRU_SECRET_KEY=dev-secret-key-replace-in-production

# API Configuration
AIVALIDATION_API_PORT=8000
AIVALIDATION_API_HOST=0.0.0.0
EOF
        fi
        print_success "Environment file created at .env"
    else
        print_info "Using existing .env file"
    fi
}

wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    print_info "Waiting for $service_name to be ready..."
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        
        printf "."
        sleep 2
        ((attempt++))
    done
    
    print_error "$service_name failed to start within $((max_attempts * 2)) seconds"
    return 1
}

check_service_health() {
    local service_name=$1
    local url=$2
    
    if curl -f -s "$url" > /dev/null 2>&1; then
        print_success "$service_name: Healthy"
        return 0
    else
        print_error "$service_name: Unhealthy"
        return 1
    fi
}

monitor_services() {
    local mode=$1
    print_section "Service Health Check"
    
    local services_healthy=0
    local total_services=3
    
    check_service_health "Backend API" "${BACKEND_URL}/health" && ((services_healthy++))
    check_service_health "Frontend" "${FRONTEND_URL}" && ((services_healthy++))
    
    # Check database connection indirectly through backend
    if curl -f -s "${BACKEND_URL}/api/health" > /dev/null 2>&1; then
        print_success "Database: Connected (via backend)"
        ((services_healthy++))
    else
        print_error "Database: Connection issues"
    fi
    
    if [[ "$mode" == "full" ]]; then
        total_services=4
        check_service_health "CVAT Annotation" "${CVAT_URL}/api/server/about" && ((services_healthy++))
    fi
    
    echo
    if [[ $services_healthy -eq $total_services ]]; then
        print_success "All services are healthy ($services_healthy/$total_services)"
    else
        print_warning "$services_healthy/$total_services services are healthy"
    fi
    
    return $services_healthy
}

start_docker_simple() {
    print_section "Starting Simple Docker Setup"
    print_info "Services: Frontend + Backend + PostgreSQL + Redis"
    
    COMPOSE_FILE="docker-compose.simple.yml"
    
    create_env_file
    
    print_info "Building and starting services..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build
    
    print_info "Waiting for services to be ready..."
    sleep 10
    
    wait_for_service "Backend API" "${BACKEND_URL}/health" 30
    wait_for_service "Frontend" "${FRONTEND_URL}" 20
    
    monitor_services "simple"
    print_urls "simple"
    
    print_success "Simple Docker setup completed successfully!"
}

start_docker_full() {
    print_section "Starting Full Docker Setup"
    print_info "Services: Frontend + Backend + PostgreSQL + Redis + CVAT"
    
    COMPOSE_FILE="docker-compose.yml"
    
    create_env_file
    
    print_info "Building and starting services..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --build
    
    print_info "Waiting for services to be ready..."
    sleep 15
    
    wait_for_service "Backend API" "${BACKEND_URL}/health" 30
    wait_for_service "Frontend" "${FRONTEND_URL}" 20
    wait_for_service "CVAT" "${CVAT_URL}/api/server/about" 45
    
    monitor_services "full"
    print_urls "full"
    
    print_success "Full Docker setup completed successfully!"
}

start_manual() {
    print_section "Manual Development Setup"
    print_warning "This requires Python 3.11+, Node.js 18+, PostgreSQL, and Redis to be installed"
    
    print_info "Setting up manual development environment..."
    
    # Check if required tools are installed
    local missing_tools=()
    
    if ! command -v python3 &> /dev/null; then
        missing_tools+=("python3")
    fi
    
    if ! command -v node &> /dev/null; then
        missing_tools+=("node")
    fi
    
    if ! command -v npm &> /dev/null; then
        missing_tools+=("npm")
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools for manual setup: ${missing_tools[*]}"
        echo -e "\nPlease install the missing tools and try again."
        return 1
    fi
    
    # Create environment for backend
    if [[ ! -f backend/.env ]]; then
        print_info "Creating backend environment file"
        cat > backend/.env << 'EOF'
AIVALIDATION_SECRET_KEY=dev-secret-key-replace-in-production
AIVALIDATION_DATABASE_URL=postgresql://postgres:password@localhost:5432/vru_validation
AIVALIDATION_REDIS_URL=redis://localhost:6379/0
AIVALIDATION_API_PORT=8000
AIVALIDATION_API_HOST=0.0.0.0
EOF
    fi
    
    print_info "You need to manually start PostgreSQL and Redis services:"
    echo -e "  ${CYAN}PostgreSQL:${NC} Create database 'vru_validation' on localhost:5432"
    echo -e "  ${CYAN}Redis:${NC} Start Redis server on localhost:6379"
    echo
    
    # Backend setup
    print_info "Setting up backend..."
    cd backend
    if [[ ! -d .venv ]]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install -r requirements.txt
    print_success "Backend dependencies installed"
    
    # Frontend setup
    cd ../frontend
    print_info "Setting up frontend..."
    if [[ ! -d node_modules ]]; then
        npm install
    fi
    print_success "Frontend dependencies installed"
    
    cd ..
    
    print_success "Manual setup completed!"
    echo
    print_info "To start the services manually:"
    echo -e "  ${CYAN}Backend:${NC}  cd backend && source .venv/bin/activate && uvicorn main:socketio_app --host 0.0.0.0 --port 8000 --reload"
    echo -e "  ${CYAN}Frontend:${NC} cd frontend && npm start"
}

stop_services() {
    print_section "Stopping Services"
    
    if [[ -n "$COMPOSE_FILE" ]]; then
        print_info "Stopping Docker services..."
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down
        print_success "Docker services stopped"
    else
        print_info "Looking for running Docker services..."
        if docker-compose -f docker-compose.yml -p $PROJECT_NAME ps -q &> /dev/null; then
            docker-compose -f docker-compose.yml -p $PROJECT_NAME down
        elif docker-compose -f docker-compose.simple.yml -p $PROJECT_NAME ps -q &> /dev/null; then
            docker-compose -f docker-compose.simple.yml -p $PROJECT_NAME down
        fi
        print_success "Services stopped"
    fi
}

show_logs() {
    local service=${1:-}
    
    if [[ -z "$COMPOSE_FILE" ]]; then
        # Try to detect compose file
        if docker-compose -f docker-compose.yml -p $PROJECT_NAME ps -q &> /dev/null; then
            COMPOSE_FILE="docker-compose.yml"
        elif docker-compose -f docker-compose.simple.yml -p $PROJECT_NAME ps -q &> /dev/null; then
            COMPOSE_FILE="docker-compose.simple.yml"
        else
            print_error "No running services found"
            return 1
        fi
    fi
    
    if [[ -n "$service" ]]; then
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f $service
    else
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f
    fi
}

show_help() {
    echo -e "${CYAN}AI Model Validation Platform Startup Script${NC}"
    echo
    echo -e "${YELLOW}USAGE:${NC}"
    echo "  $0 [COMMAND] [OPTIONS]"
    echo
    echo -e "${YELLOW}COMMANDS:${NC}"
    echo "  start [simple|full]  Start the platform (default: simple)"
    echo "  manual               Setup for manual development"
    echo "  stop                 Stop all services"
    echo "  status               Check service health"
    echo "  logs [SERVICE]       Show logs for all or specific service"
    echo "  urls                 Show access URLs"
    echo "  help                 Show this help message"
    echo
    echo -e "${YELLOW}STARTUP MODES:${NC}"
    echo -e "${GREEN}  simple${NC}   - Frontend + Backend + Database + Redis"
    echo -e "${GREEN}  full${NC}     - All services including CVAT annotation tool"
    echo -e "${GREEN}  manual${NC}   - Development setup without Docker"
    echo
    echo -e "${YELLOW}EXAMPLES:${NC}"
    echo "  $0 start simple      # Start basic platform"
    echo "  $0 start full        # Start with all services"
    echo "  $0 status            # Check service health"
    echo "  $0 logs backend      # Show backend logs"
    echo
    echo -e "${YELLOW}SERVICE ACCESS:${NC}"
    echo -e "  Frontend:     ${GREEN}http://localhost:3000${NC}"
    echo -e "  Backend API:  ${GREEN}http://localhost:8000/api${NC}"
    echo -e "  API Docs:     ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "  CVAT (full):  ${GREEN}http://localhost:8080${NC}"
}

# ==============================================================================
# Main Script Logic
# ==============================================================================

main() {
    print_header
    
    local command=${1:-start}
    local mode=${2:-$DEFAULT_MODE}
    
    case $command in
        "start")
            if ! check_prerequisites; then
                exit 1
            fi
            
            case $mode in
                "simple")
                    if ! check_ports "simple"; then
                        exit 1
                    fi
                    start_docker_simple
                    ;;
                "full")
                    if ! check_ports "full"; then
                        exit 1
                    fi
                    start_docker_full
                    ;;
                *)
                    print_error "Invalid mode: $mode"
                    echo -e "Available modes: simple, full"
                    exit 1
                    ;;
            esac
            ;;
        
        "manual")
            start_manual
            ;;
        
        "stop")
            stop_services
            ;;
        
        "status")
            if docker-compose -f docker-compose.yml -p $PROJECT_NAME ps -q &> /dev/null; then
                monitor_services "full"
                print_urls "full"
            elif docker-compose -f docker-compose.simple.yml -p $PROJECT_NAME ps -q &> /dev/null; then
                monitor_services "simple"
                print_urls "simple"
            else
                print_warning "No services are currently running"
            fi
            ;;
        
        "logs")
            show_logs $2
            ;;
        
        "urls")
            if docker-compose -f docker-compose.yml -p $PROJECT_NAME ps -q &> /dev/null; then
                print_urls "full"
            elif docker-compose -f docker-compose.simple.yml -p $PROJECT_NAME ps -q &> /dev/null; then
                print_urls "simple"
            else
                print_warning "No services are currently running"
                print_info "Default URLs when services are running:"
                print_urls "simple"
            fi
            ;;
        
        "help"|"-h"|"--help")
            show_help
            ;;
        
        *)
            print_error "Unknown command: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
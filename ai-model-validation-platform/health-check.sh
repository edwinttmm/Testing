#!/bin/bash

# ==============================================================================
# AI Model Validation Platform - Health Check Utility
# ==============================================================================
# Quick health check script for all platform services
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Service URLs
FRONTEND_URL="http://localhost:3000"
BACKEND_URL="http://localhost:8000"
BACKEND_API_URL="http://localhost:8000/api"
BACKEND_HEALTH_URL="http://localhost:8000/health"
CVAT_URL="http://localhost:8080/api/server/about"

print_header() {
    echo -e "${CYAN}==============================================="
    echo -e "🏥 AI Model Validation Platform Health Check"
    echo -e "===============================================${NC}"
    echo
}

check_service() {
    local service_name=$1
    local url=$2
    local timeout=${3:-5}
    
    printf "%-20s" "$service_name:"
    
    if curl -f -s -m $timeout "$url" > /dev/null 2>&1; then
        echo -e " ${GREEN}✅ Healthy${NC}"
        return 0
    else
        echo -e " ${RED}❌ Unhealthy${NC}"
        return 1
    fi
}

check_docker_services() {
    echo -e "${BLUE}📋 Docker Services Status:${NC}"
    echo "----------------------------------------"
    
    # Check if Docker Compose services are running
    local compose_files=("docker-compose.yml" "docker-compose.simple.yml")
    local services_found=false
    
    for compose_file in "${compose_files[@]}"; do
        if [[ -f "$compose_file" ]] && docker-compose -f "$compose_file" -p ai-validation-platform ps -q &> /dev/null; then
            echo -e "${CYAN}Using: $compose_file${NC}"
            docker-compose -f "$compose_file" -p ai-validation-platform ps --format "table {{.Name}}\t{{.State}}\t{{.Status}}"
            services_found=true
            break
        fi
    done
    
    if [[ "$services_found" == false ]]; then
        echo -e "${YELLOW}⚠️  No Docker services found running${NC}"
    fi
    
    echo
}

check_ports() {
    echo -e "${BLUE}🔌 Port Availability:${NC}"
    echo "----------------------------------------"
    
    local ports=("3000:Frontend" "8000:Backend" "5432:PostgreSQL" "6379:Redis" "8080:CVAT")
    
    for port_info in "${ports[@]}"; do
        IFS=':' read -r port service <<< "$port_info"
        printf "%-15s (%-10s):" "$service" "$port"
        
        if lsof -i :$port &> /dev/null; then
            echo -e " ${GREEN}✅ In Use${NC}"
        else
            echo -e " ${RED}❌ Free${NC}"
        fi
    done
    
    echo
}

main() {
    print_header
    
    # Check Docker services first
    check_docker_services
    
    # Check port status
    check_ports
    
    # Check service health
    echo -e "${BLUE}🏥 Service Health Checks:${NC}"
    echo "----------------------------------------"
    
    local healthy_services=0
    local total_services=0
    
    # Core services
    check_service "Frontend" "$FRONTEND_URL" && ((healthy_services++))
    ((total_services++))
    
    check_service "Backend Health" "$BACKEND_HEALTH_URL" && ((healthy_services++))
    ((total_services++))
    
    check_service "Backend API" "$BACKEND_API_URL/health" && ((healthy_services++))
    ((total_services++))
    
    # Optional CVAT service
    if curl -f -s -m 2 "$CVAT_URL" > /dev/null 2>&1; then
        check_service "CVAT" "$CVAT_URL" && ((healthy_services++))
        ((total_services++))
    fi
    
    echo
    echo -e "${BLUE}📊 Overall Health Summary:${NC}"
    echo "----------------------------------------"
    
    if [[ $healthy_services -eq $total_services ]] && [[ $total_services -gt 0 ]]; then
        echo -e "${GREEN}🎉 All services are healthy! ($healthy_services/$total_services)${NC}"
        echo -e "\n${CYAN}🌐 Access URLs:${NC}"
        echo -e "   Frontend:         ${GREEN}http://localhost:3000${NC}"
        echo -e "   API Documentation: ${GREEN}http://localhost:8000/docs${NC}"
        echo -e "   Backend API:      ${GREEN}http://localhost:8000/api${NC}"
        if [[ $total_services -eq 4 ]]; then
            echo -e "   CVAT Annotation:  ${GREEN}http://localhost:8080${NC}"
        fi
    elif [[ $total_services -eq 0 ]]; then
        echo -e "${YELLOW}⚠️  No services detected. Platform may not be running.${NC}"
        echo -e "\n${CYAN}💡 To start the platform:${NC}"
        echo -e "   ./start.sh start simple"
    else
        echo -e "${YELLOW}⚠️  $healthy_services out of $total_services services are healthy${NC}"
        echo -e "\n${CYAN}💡 Try restarting unhealthy services:${NC}"
        echo -e "   ./start.sh stop"
        echo -e "   ./start.sh start simple"
    fi
    
    echo
}

main "$@"
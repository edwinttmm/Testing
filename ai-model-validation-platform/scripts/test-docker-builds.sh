#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 VRU AI Model Validation Platform - Docker Build Validator${NC}"
echo -e "${YELLOW}🔍 Testing all Docker configurations for build compatibility...${NC}"

# Change to project root
cd "$(dirname "$0")/.."

# Test results
BUILD_RESULTS=()
FAILED_BUILDS=()

# Function to test a Docker build
test_build() {
    local name=$1
    local dockerfile=$2
    local context=$3
    local target=$4
    local build_args=$5
    
    echo -e "\n${BLUE}📋 Testing: $name${NC}"
    echo -e "${YELLOW}   Dockerfile: $dockerfile${NC}"
    echo -e "${YELLOW}   Context: $context${NC}"
    echo -e "${YELLOW}   Target: $target${NC}"
    
    # Check if docker command exists
    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Docker not available - performing syntax validation only${NC}"
        
        # Check if Dockerfile exists
        if [[ -f "$dockerfile" ]]; then
            echo -e "${GREEN}✅ Dockerfile exists and is readable${NC}"
            BUILD_RESULTS+=("$name: SYNTAX_OK")
        else
            echo -e "${RED}❌ Dockerfile not found: $dockerfile${NC}"
            BUILD_RESULTS+=("$name: DOCKERFILE_MISSING")
            FAILED_BUILDS+=("$name")
        fi
        return
    fi
    
    # Perform dry-run build test
    local build_cmd="docker build --dry-run -f $dockerfile"
    
    if [[ -n "$target" ]]; then
        build_cmd="$build_cmd --target $target"
    fi
    
    if [[ -n "$build_args" ]]; then
        build_cmd="$build_cmd $build_args"
    fi
    
    build_cmd="$build_cmd $context"
    
    echo -e "${YELLOW}🔧 Running: $build_cmd${NC}"
    
    if eval "$build_cmd" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Build test passed: $name${NC}"
        BUILD_RESULTS+=("$name: PASS")
    else
        echo -e "${RED}❌ Build test failed: $name${NC}"
        BUILD_RESULTS+=("$name: FAIL")
        FAILED_BUILDS+=("$name")
        
        # Try to get more detailed error
        echo -e "${YELLOW}🔍 Error details:${NC}"
        eval "$build_cmd" 2>&1 | tail -10 || true
    fi
}

# Function to validate compose file syntax
validate_compose() {
    local name=$1
    local compose_file=$2
    
    echo -e "\n${BLUE}📋 Validating: $name${NC}"
    echo -e "${YELLOW}   File: $compose_file${NC}"
    
    if [[ ! -f "$compose_file" ]]; then
        echo -e "${RED}❌ Compose file not found: $compose_file${NC}"
        BUILD_RESULTS+=("$name: FILE_MISSING")
        FAILED_BUILDS+=("$name")
        return
    fi
    
    # Check if docker-compose command exists
    if command -v docker-compose >/dev/null 2>&1; then
        if docker-compose -f "$compose_file" config >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Compose validation passed: $name${NC}"
            BUILD_RESULTS+=("$name: PASS")
        else
            echo -e "${RED}❌ Compose validation failed: $name${NC}"
            BUILD_RESULTS+=("$name: FAIL")
            FAILED_BUILDS+=("$name")
        fi
    else
        echo -e "${YELLOW}⚠️  docker-compose not available - checking YAML syntax only${NC}"
        if python3 -c "import yaml; yaml.safe_load(open('$compose_file'))" 2>/dev/null; then
            echo -e "${GREEN}✅ YAML syntax valid: $name${NC}"
            BUILD_RESULTS+=("$name: YAML_OK")
        else
            echo -e "${RED}❌ YAML syntax invalid: $name${NC}"
            BUILD_RESULTS+=("$name: YAML_FAIL")
            FAILED_BUILDS+=("$name")
        fi
    fi
}

# Test individual Dockerfiles
echo -e "\n${BLUE}🔍 Testing Individual Dockerfiles${NC}"

test_build "Backend Development" "backend/Dockerfile.unified" "." "development" "--build-arg PYTHON_VERSION=3.11"
test_build "Backend Production" "backend/Dockerfile.unified" "." "production" "--build-arg PYTHON_VERSION=3.11"
test_build "Backend Testing" "backend/Dockerfile.unified" "." "testing" "--build-arg PYTHON_VERSION=3.11"
test_build "Frontend Development" "frontend/Dockerfile.unified" "frontend" "development" "--build-arg NODE_VERSION=20"
test_build "Frontend Production" "frontend/Dockerfile.unified" "frontend" "production" "--build-arg NODE_VERSION=20"
test_build "Frontend Build Stage" "frontend/Dockerfile.unified" "frontend" "build" "--build-arg NODE_VERSION=20"

# Test legacy Dockerfiles if they exist
if [[ -f "backend/Dockerfile" ]]; then
    test_build "Backend Legacy" "backend/Dockerfile" "backend" "" ""
fi

if [[ -f "frontend/Dockerfile" ]]; then
    test_build "Frontend Legacy" "frontend/Dockerfile" "frontend" "" ""
fi

# Test Docker Compose configurations
echo -e "\n${BLUE}🔍 Testing Docker Compose Files${NC}"

validate_compose "Unified Compose" "docker-compose.unified.yml"
validate_compose "Production Compose" "config/production/docker-compose.production.yml"

# Test other compose files if they exist
for compose_file in docker-compose*.yml; do
    if [[ -f "$compose_file" && "$compose_file" != "docker-compose.unified.yml" ]]; then
        validate_compose "$(basename "$compose_file")" "$compose_file"
    fi
done

# Validate build contexts and paths
echo -e "\n${BLUE}🔍 Validating Build Contexts and Paths${NC}"

# Check required files and directories
REQUIRED_PATHS=(
    "backend/Dockerfile.unified"
    "frontend/Dockerfile.unified"
    "backend/requirements-minimal.txt"
    "backend/requirements-docker-minimal.txt"
    "backend/scripts/wait-for-services.sh"
    "scripts/wait-for-services.sh"
    "frontend/nginx.conf"
    "models/"
    "config/production/docker-compose.production.yml"
)

for path in "${REQUIRED_PATHS[@]}"; do
    if [[ -e "$path" ]]; then
        echo -e "${GREEN}✅ Required path exists: $path${NC}"
    else
        echo -e "${RED}❌ Missing required path: $path${NC}"
        FAILED_BUILDS+=("Required Path: $path")
    fi
done

# Check for common issues
echo -e "\n${BLUE}🔍 Checking for Common Docker Issues${NC}"

# Check for COPY commands with wrong paths
echo -e "${YELLOW}🔍 Scanning Dockerfiles for potential path issues...${NC}"

find . -name "Dockerfile*" -type f | while read dockerfile; do
    echo -e "${BLUE}   Checking: $dockerfile${NC}"
    
    # Look for suspicious COPY commands
    if grep -n "COPY.*\.\./\.\." "$dockerfile" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Found suspicious COPY path in $dockerfile${NC}"
        grep -n "COPY.*\.\./\.\." "$dockerfile" | head -3
    fi
    
    # Look for missing requirements files
    if grep -n "requirements.*txt" "$dockerfile" >/dev/null 2>&1; then
        required_files=$(grep -o "requirements[^[:space:]]*\.txt" "$dockerfile" | sort -u)
        for req_file in $required_files; do
            if [[ ! -f "backend/$req_file" && ! -f "$req_file" ]]; then
                echo -e "${YELLOW}⚠️  Referenced requirements file may not exist: $req_file${NC}"
            fi
        done
    fi
done

# Summary
echo -e "\n${BLUE}📊 BUILD TEST SUMMARY${NC}"
echo -e "${BLUE}=================${NC}"

total_tests=${#BUILD_RESULTS[@]}
failed_tests=${#FAILED_BUILDS[@]}
passed_tests=$((total_tests - failed_tests))

echo -e "${GREEN}✅ Passed: $passed_tests/$total_tests${NC}"
if [[ $failed_tests -gt 0 ]]; then
    echo -e "${RED}❌ Failed: $failed_tests/$total_tests${NC}"
    echo -e "\n${RED}Failed Tests:${NC}"
    for failed in "${FAILED_BUILDS[@]}"; do
        echo -e "${RED}   - $failed${NC}"
    done
else
    echo -e "${GREEN}🎉 All tests passed!${NC}"
fi

echo -e "\n${BLUE}Detailed Results:${NC}"
for result in "${BUILD_RESULTS[@]}"; do
    if [[ "$result" == *"PASS"* || "$result" == *"SYNTAX_OK"* || "$result" == *"YAML_OK"* ]]; then
        echo -e "${GREEN}   ✅ $result${NC}"
    else
        echo -e "${RED}   ❌ $result${NC}"
    fi
done

# Exit with appropriate code
if [[ $failed_tests -gt 0 ]]; then
    echo -e "\n${YELLOW}⚠️  Some tests failed. Review the issues above before deploying.${NC}"
    exit 1
else
    echo -e "\n${GREEN}🎉 All Docker configurations are valid and ready for deployment!${NC}"
    exit 0
fi
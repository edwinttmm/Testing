#!/bin/bash

# AI Model Validation Platform - Progress Reporter Utility
# Provides consistent progress reporting across all deployment scripts

# Colors and symbols
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Unicode symbols
CHECK_MARK="✓"
CROSS_MARK="✗"
WARNING="⚠"
INFO="ℹ"
ROCKET="🚀"
GEAR="⚙"
CLOCK="🕐"
SPARKLES="✨"

# Progress tracking
TOTAL_STEPS=0
CURRENT_STEP=0
START_TIME=""
STEP_START_TIME=""

# Initialize progress tracker
init_progress() {
    local total=$1
    local task_name=$2
    TOTAL_STEPS=$total
    CURRENT_STEP=0
    START_TIME=$(date +%s)
    
    echo ""
    echo "========================================"
    echo -e "${BLUE}${ROCKET} $task_name${NC}"
    echo "========================================"
    echo -e "${CYAN}Total steps: $TOTAL_STEPS${NC}"
    echo -e "${CYAN}Started: $(date)${NC}"
    echo "========================================"
    echo ""
}

# Show step progress
step_progress() {
    local step_name=$1
    local step_description=${2:-""}
    
    CURRENT_STEP=$((CURRENT_STEP + 1))
    STEP_START_TIME=$(date +%s)
    
    # Calculate progress percentage
    local progress_percent=$(( (CURRENT_STEP * 100) / TOTAL_STEPS ))
    
    # Create progress bar
    local bar_length=30
    local filled_length=$(( (progress_percent * bar_length) / 100 ))
    local bar=""
    
    for ((i=0; i<filled_length; i++)); do
        bar+="█"
    done
    
    for ((i=filled_length; i<bar_length; i++)); do
        bar+="░"
    done
    
    echo ""
    echo -e "${PURPLE}[Step $CURRENT_STEP/$TOTAL_STEPS]${NC} ${BLUE}$step_name${NC}"
    if [ -n "$step_description" ]; then
        echo -e "${CYAN}$step_description${NC}"
    fi
    echo -e "${YELLOW}Progress: [${bar}] ${progress_percent}%${NC}"
    echo ""
}

# Success message
step_success() {
    local message=$1
    local duration=""
    
    if [ -n "$STEP_START_TIME" ]; then
        local step_end_time=$(date +%s)
        local step_duration=$((step_end_time - STEP_START_TIME))
        duration=" (${step_duration}s)"
    fi
    
    echo -e "${GREEN}${CHECK_MARK} $message${duration}${NC}"
}

# Warning message
step_warning() {
    local message=$1
    echo -e "${YELLOW}${WARNING} $message${NC}"
}

# Error message
step_error() {
    local message=$1
    echo -e "${RED}${CROSS_MARK} $message${NC}"
}

# Info message
step_info() {
    local message=$1
    echo -e "${BLUE}${INFO} $message${NC}"
}

# Substep progress (for steps with multiple parts)
substep_progress() {
    local substep_name=$1
    echo -e "  ${CYAN}${GEAR} $substep_name${NC}"
}

# Final summary
final_summary() {
    local status=$1  # "success", "warning", or "error"
    local summary_message=$2
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    local minutes=$((total_duration / 60))
    local seconds=$((total_duration % 60))
    
    echo ""
    echo "========================================"
    
    case $status in
        "success")
            echo -e "${GREEN}${SPARKLES} COMPLETED SUCCESSFULLY! ${SPARKLES}${NC}"
            echo -e "${GREEN}$summary_message${NC}"
            ;;
        "warning")
            echo -e "${YELLOW}${WARNING} COMPLETED WITH WARNINGS ${WARNING}${NC}"
            echo -e "${YELLOW}$summary_message${NC}"
            ;;
        "error")
            echo -e "${RED}${CROSS_MARK} FAILED ${CROSS_MARK}${NC}"
            echo -e "${RED}$summary_message${NC}"
            ;;
    esac
    
    echo "========================================"
    echo -e "${CYAN}Completed steps: $CURRENT_STEP/$TOTAL_STEPS${NC}"
    
    if [ $minutes -gt 0 ]; then
        echo -e "${CYAN}Total duration: ${minutes}m ${seconds}s${NC}"
    else
        echo -e "${CYAN}Total duration: ${seconds}s${NC}"
    fi
    
    echo -e "${CYAN}Finished: $(date)${NC}"
    echo "========================================"
    echo ""
}

# Progress bar for long-running operations
show_spinner() {
    local message=$1
    local pid=$2
    local delay=0.1
    local spinstr='|/-\'
    
    echo -n -e "${BLUE}$message ${NC}"
    
    while ps -p $pid > /dev/null 2>&1; do
        local temp=${spinstr#?}
        printf "[%c]" "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b"
    done
    
    wait $pid
    local exit_code=$?
    
    printf "\b\b\b   \b\b\b"
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}${CHECK_MARK}${NC}"
    else
        echo -e "${RED}${CROSS_MARK}${NC}"
    fi
    
    return $exit_code
}

# Time estimation
estimate_remaining() {
    if [ $CURRENT_STEP -eq 0 ] || [ -z "$START_TIME" ]; then
        echo "Estimating..."
        return
    fi
    
    local current_time=$(date +%s)
    local elapsed_time=$((current_time - START_TIME))
    local remaining_steps=$((TOTAL_STEPS - CURRENT_STEP))
    
    if [ $remaining_steps -eq 0 ]; then
        echo "Almost done!"
        return
    fi
    
    local time_per_step=$((elapsed_time / CURRENT_STEP))
    local estimated_remaining=$((time_per_step * remaining_steps))
    
    local est_minutes=$((estimated_remaining / 60))
    local est_seconds=$((estimated_remaining % 60))
    
    if [ $est_minutes -gt 0 ]; then
        echo "~${est_minutes}m ${est_seconds}s remaining"
    else
        echo "~${est_seconds}s remaining"
    fi
}

# File size formatter
format_size() {
    local size_bytes=$1
    
    if [ $size_bytes -gt 1073741824 ]; then
        echo "$(( size_bytes / 1073741824 ))GB"
    elif [ $size_bytes -gt 1048576 ]; then
        echo "$(( size_bytes / 1048576 ))MB"
    elif [ $size_bytes -gt 1024 ]; then
        echo "$(( size_bytes / 1024 ))KB"
    else
        echo "${size_bytes}B"
    fi
}

# Performance metrics
show_performance_metrics() {
    local operation=$1
    local start_time=$2
    local end_time=$3
    local size_bytes=${4:-0}
    
    local duration=$((end_time - start_time))
    local formatted_size=$(format_size $size_bytes)
    
    echo ""
    echo -e "${PURPLE}Performance Metrics for $operation:${NC}"
    echo -e "${CYAN}Duration: ${duration}s${NC}"
    
    if [ $size_bytes -gt 0 ]; then
        echo -e "${CYAN}Size: $formatted_size${NC}"
        
        if [ $duration -gt 0 ]; then
            local throughput=$((size_bytes / duration))
            local formatted_throughput=$(format_size $throughput)
            echo -e "${CYAN}Throughput: ${formatted_throughput}/s${NC}"
        fi
    fi
    echo ""
}

# Resource usage monitoring
show_resource_usage() {
    local show_memory=${1:-true}
    local show_disk=${2:-true}
    local show_cpu=${3:-false}
    
    echo -e "${PURPLE}Resource Usage:${NC}"
    
    if [ "$show_memory" = true ]; then
        local memory_info=$(free -m 2>/dev/null | awk '/^Mem:/{printf "Used: %dMB, Available: %dMB", $3, $7}' || echo "Memory info not available")
        echo -e "${CYAN}Memory - $memory_info${NC}"
    fi
    
    if [ "$show_disk" = true ]; then
        local disk_info=$(df -h . 2>/dev/null | tail -1 | awk '{printf "Used: %s, Available: %s (%s used)", $3, $4, $5}' || echo "Disk info not available")
        echo -e "${CYAN}Disk - $disk_info${NC}"
    fi
    
    if [ "$show_cpu" = true ]; then
        local cpu_info=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 2>/dev/null || echo "CPU info not available")
        echo -e "${CYAN}CPU Usage - ${cpu_info}%${NC}"
    fi
    echo ""
}

# Validation summary
validation_summary() {
    local tests_passed=$1
    local tests_failed=$2
    local critical_failures=$3
    
    local total_tests=$((tests_passed + tests_failed))
    local success_rate=0
    
    if [ $total_tests -gt 0 ]; then
        success_rate=$(( (tests_passed * 100) / total_tests ))
    fi
    
    echo ""
    echo -e "${PURPLE}Validation Summary:${NC}"
    echo -e "${GREEN}Passed: $tests_passed${NC}"
    echo -e "${RED}Failed: $tests_failed${NC}"
    echo -e "${CYAN}Success Rate: ${success_rate}%${NC}"
    
    if [ $critical_failures -gt 0 ]; then
        echo -e "${RED}Critical Failures: $critical_failures${NC}"
    fi
    echo ""
}

# Export functions for use in other scripts
export -f init_progress
export -f step_progress
export -f step_success
export -f step_warning
export -f step_error
export -f step_info
export -f substep_progress
export -f final_summary
export -f show_spinner
export -f estimate_remaining
export -f format_size
export -f show_performance_metrics
export -f show_resource_usage
export -f validation_summary
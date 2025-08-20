#!/bin/bash

# Comprehensive Test Suite Runner for AI Model Validation Platform
# This script runs all test categories and generates a comprehensive report

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_DIR="$(dirname "$0")"
ROOT_DIR="$TEST_DIR/../.."
REPORT_DIR="$TEST_DIR/reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo -e "${BLUE}🚀 Starting Comprehensive Test Suite for AI Model Validation Platform${NC}"
echo -e "${BLUE}Timestamp: $(date)${NC}"
echo -e "${BLUE}Test Directory: $TEST_DIR${NC}"

# Create reports directory
mkdir -p "$REPORT_DIR"

# Initialize test results
declare -A test_results
total_tests=0
passed_tests=0
failed_tests=0

# Function to run test category
run_test_category() {
    local category=$1
    local command=$2
    local description=$3
    
    echo -e "\n${YELLOW}📋 Running $description${NC}"
    echo "Command: $command"
    echo "----------------------------------------"
    
    start_time=$(date +%s)
    
    if eval "$command" > "$REPORT_DIR/${category}_${TIMESTAMP}.log" 2>&1; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        echo -e "${GREEN}✅ $description - PASSED (${duration}s)${NC}"
        test_results[$category]="PASSED"
        ((passed_tests++))
    else
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        
        echo -e "${RED}❌ $description - FAILED (${duration}s)${NC}"
        echo -e "${RED}   Check log: $REPORT_DIR/${category}_${TIMESTAMP}.log${NC}"
        test_results[$category]="FAILED"
        ((failed_tests++))
    fi
    
    ((total_tests++))
}

# 1. Unit Tests - Video Upload
run_test_category "unit_video_upload" \
    "cd $ROOT_DIR && npm run test tests/comprehensive-suite/unit/video-upload.test.ts" \
    "Unit Tests - Video Upload Process"

# 2. Unit Tests - Video Player Functionality
run_test_category "unit_video_player" \
    "cd $ROOT_DIR && npm run test tests/comprehensive-suite/unit/video-player-functionality.test.tsx" \
    "Unit Tests - Video Player Functionality"

# 3. Integration Tests - Project Video Workflow
run_test_category "integration_project_workflow" \
    "cd $ROOT_DIR && npm run test tests/comprehensive-suite/integration/project-video-workflow.test.ts" \
    "Integration Tests - Project Video Workflow"

# 4. Integration Tests - Ground Truth Annotations
run_test_category "integration_annotations" \
    "cd $ROOT_DIR && npm run test tests/comprehensive-suite/integration/ground-truth-annotations.test.ts" \
    "Integration Tests - Ground Truth Annotations"

# 5. Integration Tests - Database Persistence
run_test_category "integration_database" \
    "cd $ROOT_DIR && python -m pytest tests/comprehensive-suite/integration/database-persistence.test.py -v" \
    "Integration Tests - Database Persistence"

# 6. Integration Tests - Frontend-Backend Data Flow
run_test_category "integration_dataflow" \
    "cd $ROOT_DIR && npm run test tests/comprehensive-suite/integration/frontend-backend-dataflow.test.ts" \
    "Integration Tests - Frontend-Backend Data Flow"

# 7. Integration Tests - Error Scenarios and Recovery
run_test_category "integration_error_recovery" \
    "cd $ROOT_DIR && npm run test tests/comprehensive-suite/integration/error-scenarios-recovery.test.ts" \
    "Integration Tests - Error Scenarios and Recovery"

# 8. E2E Tests - Complete User Workflow
run_test_category "e2e_workflow" \
    "cd $ROOT_DIR && npx playwright test tests/comprehensive-suite/e2e/complete-user-workflow.test.ts" \
    "E2E Tests - Complete User Workflow"

# 9. Performance Tests - Large File Upload
run_test_category "performance_upload" \
    "cd $ROOT_DIR && npm run test tests/comprehensive-suite/performance/large-file-upload.test.ts" \
    "Performance Tests - Large File Upload"

# Generate comprehensive test report
echo -e "\n${BLUE}📊 Generating Comprehensive Test Report${NC}"

cat > "$REPORT_DIR/comprehensive_test_report_${TIMESTAMP}.html" << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Model Validation Platform - Comprehensive Test Report</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            padding: 30px; 
            border-radius: 8px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        .header { 
            text-align: center; 
            margin-bottom: 30px; 
            padding-bottom: 20px; 
            border-bottom: 2px solid #e0e0e0; 
        }
        .summary { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px; 
        }
        .summary-card { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            padding: 20px; 
            border-radius: 8px; 
            text-align: center; 
        }
        .summary-card.passed { background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); }
        .summary-card.failed { background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%); }
        .summary-card h3 { margin: 0 0 10px 0; font-size: 2em; }
        .summary-card p { margin: 0; font-size: 1.1em; }
        .test-details { margin-top: 30px; }
        .test-category { 
            margin-bottom: 20px; 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            overflow: hidden; 
        }
        .test-category-header { 
            background: #f8f9fa; 
            padding: 15px; 
            font-weight: bold; 
            border-bottom: 1px solid #ddd; 
        }
        .test-category-content { padding: 15px; }
        .status-badge { 
            display: inline-block; 
            padding: 4px 12px; 
            border-radius: 20px; 
            font-size: 0.8em; 
            font-weight: bold; 
            text-transform: uppercase; 
        }
        .status-passed { background: #d4edda; color: #155724; }
        .status-failed { background: #f8d7da; color: #721c24; }
        .recommendations { 
            background: #fff3cd; 
            border: 1px solid #ffeaa7; 
            border-radius: 8px; 
            padding: 20px; 
            margin-top: 30px; 
        }
        .timestamp { 
            color: #666; 
            font-size: 0.9em; 
            text-align: center; 
            margin-top: 30px; 
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 AI Model Validation Platform</h1>
            <h2>Comprehensive Test Suite Report</h2>
            <p>Generated on: $(date)</p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <h3>$total_tests</h3>
                <p>Total Test Categories</p>
            </div>
            <div class="summary-card passed">
                <h3>$passed_tests</h3>
                <p>Passed</p>
            </div>
            <div class="summary-card failed">
                <h3>$failed_tests</h3>
                <p>Failed</p>
            </div>
            <div class="summary-card">
                <h3>$(( passed_tests * 100 / total_tests ))%</h3>
                <p>Success Rate</p>
            </div>
        </div>

        <div class="test-details">
            <h2>📋 Test Category Results</h2>
EOF

# Add test results to HTML report
for category in "${!test_results[@]}"; do
    status="${test_results[$category]}"
    status_class="status-$(echo "$status" | tr '[:upper:]' '[:lower:]')"
    
    case $category in
        "unit_video_upload")
            title="Unit Tests - Video Upload Process"
            description="Tests small and large file uploads, progress tracking, error handling, and concurrent operations."
            ;;
        "unit_video_player")
            title="Unit Tests - Video Player Functionality"
            description="Tests video playback controls, annotation display, time synchronization, and error recovery."
            ;;
        "integration_project_workflow")
            title="Integration Tests - Project Video Workflow"
            description="Tests complete project creation, video linking, and data consistency workflows."
            ;;
        "integration_annotations")
            title="Integration Tests - Ground Truth Annotations"
            description="Tests annotation creation, validation, export/import, and session management."
            ;;
        "integration_database")
            title="Integration Tests - Database Persistence"
            description="Tests data persistence, transaction integrity, and cascade operations."
            ;;
        "integration_dataflow")
            title="Integration Tests - Frontend-Backend Data Flow"
            description="Tests API communication, state synchronization, and real-time updates."
            ;;
        "integration_error_recovery")
            title="Integration Tests - Error Scenarios and Recovery"
            description="Tests network failures, server errors, validation errors, and recovery mechanisms."
            ;;
        "e2e_workflow")
            title="E2E Tests - Complete User Workflow"
            description="Tests end-to-end user scenarios including upload, processing, annotation, and testing."
            ;;
        "performance_upload")
            title="Performance Tests - Large File Upload"
            description="Tests upload performance, memory usage, concurrent operations, and resource management."
            ;;
    esac
    
    cat >> "$REPORT_DIR/comprehensive_test_report_${TIMESTAMP}.html" << EOF
            <div class="test-category">
                <div class="test-category-header">
                    <span class="status-badge $status_class">$status</span>
                    $title
                </div>
                <div class="test-category-content">
                    <p>$description</p>
                    <p><strong>Log file:</strong> <code>${category}_${TIMESTAMP}.log</code></p>
                </div>
            </div>
EOF
done

# Add recommendations section
cat >> "$REPORT_DIR/comprehensive_test_report_${TIMESTAMP}.html" << EOF
        </div>

        <div class="recommendations">
            <h2>🔧 Key Recommendations</h2>
            <ul>
                <li><strong>Critical Issues:</strong> Address any failed test categories immediately</li>
                <li><strong>Performance:</strong> Monitor large file upload performance and optimize if needed</li>
                <li><strong>Error Handling:</strong> Ensure robust error recovery mechanisms are in place</li>
                <li><strong>Database:</strong> Verify transaction integrity and cascade delete operations</li>
                <li><strong>User Experience:</strong> Test complete workflows regularly to ensure smooth operation</li>
                <li><strong>Monitoring:</strong> Set up automated testing pipeline for continuous quality assurance</li>
            </ul>
            
            <h3>Next Steps:</h3>
            <ol>
                <li>Review failed test logs for specific error details</li>
                <li>Implement fixes for identified issues</li>
                <li>Re-run affected test categories</li>
                <li>Consider adding additional test coverage for edge cases</li>
                <li>Set up continuous integration pipeline</li>
            </ol>
        </div>

        <div class="timestamp">
            <p>Report generated by Comprehensive Test Suite Runner</p>
            <p>Platform: AI Model Validation Platform | Version: $(git describe --tags --always 2>/dev/null || echo "unknown")</p>
        </div>
    </div>
</body>
</html>
EOF

# Generate summary
echo -e "\n${BLUE}📈 Test Execution Summary${NC}"
echo "========================================"
echo -e "Total Test Categories: $total_tests"
echo -e "${GREEN}Passed: $passed_tests${NC}"
echo -e "${RED}Failed: $failed_tests${NC}"
echo -e "Success Rate: $(( passed_tests * 100 / total_tests ))%"
echo ""

if [ $failed_tests -gt 0 ]; then
    echo -e "${RED}❌ Some tests failed. Please review the logs for details:${NC}"
    for category in "${!test_results[@]}"; do
        if [ "${test_results[$category]}" = "FAILED" ]; then
            echo -e "   ${RED}• $category: $REPORT_DIR/${category}_${TIMESTAMP}.log${NC}"
        fi
    done
    echo ""
fi

echo -e "${BLUE}📄 Reports generated:${NC}"
echo "• HTML Report: $REPORT_DIR/comprehensive_test_report_${TIMESTAMP}.html"
echo "• Individual logs: $REPORT_DIR/*_${TIMESTAMP}.log"
echo ""

# Open HTML report if on macOS/Linux with GUI
if command -v open >/dev/null 2>&1; then
    echo -e "${BLUE}Opening HTML report...${NC}"
    open "$REPORT_DIR/comprehensive_test_report_${TIMESTAMP}.html"
elif command -v xdg-open >/dev/null 2>&1; then
    echo -e "${BLUE}Opening HTML report...${NC}"
    xdg-open "$REPORT_DIR/comprehensive_test_report_${TIMESTAMP}.html"
fi

# Exit with appropriate code
if [ $failed_tests -gt 0 ]; then
    echo -e "${RED}🚨 Test suite completed with failures${NC}"
    exit 1
else
    echo -e "${GREEN}🎉 All tests passed successfully!${NC}"
    exit 0
fi
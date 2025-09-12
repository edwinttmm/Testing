#!/bin/bash
# Full User Experience Test - Complete Application Startup and Testing
# This simulates exactly what a real user would do

echo "=========================================="
echo "AI Model Validation Platform - Full User Experience Test"
echo "Starting at: $(date)"
echo "=========================================="

# Create comprehensive log directory
LOG_DIR="/home/rigade/Testing/ai-model-validation-platform/logs/user-experience-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

echo "📁 Log directory: $LOG_DIR"
echo ""

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/main.log"
}

# Function to capture errors
capture_errors() {
    local component=$1
    local log_file=$2
    echo "" >> "$LOG_DIR/${component}_errors.log"
    echo "=== Errors from $component at $(date) ===" >> "$LOG_DIR/${component}_errors.log"
    grep -i "error\|fail\|exception\|warning\|critical" "$log_file" >> "$LOG_DIR/${component}_errors.log" 2>/dev/null || echo "No errors found" >> "$LOG_DIR/${component}_errors.log"
}

# ============================================
# PHASE 1: BACKEND SETUP AND STARTUP
# ============================================
log_message "🚀 PHASE 1: Starting Backend Setup"

cd /home/rigade/Testing/ai-model-validation-platform/backend

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    log_message "📦 Creating Python virtual environment..."
    python3 -m venv venv 2>&1 | tee -a "$LOG_DIR/backend_setup.log"
fi

# Activate virtual environment
log_message "🔧 Activating virtual environment..."
source venv/bin/activate

# Install backend dependencies
log_message "📦 Installing backend dependencies (this may take a while)..."
pip install --upgrade pip 2>&1 | tee -a "$LOG_DIR/backend_setup.log"

# Install core requirements first
log_message "📦 Installing core dependencies..."
pip install fastapi uvicorn sqlalchemy python-dotenv pydantic pydantic-settings 2>&1 | tee -a "$LOG_DIR/backend_setup.log"
pip install aiofiles python-socketio python-engineio 2>&1 | tee -a "$LOG_DIR/backend_setup.log"
pip install opencv-python-headless psutil numpy pandas 2>&1 | tee -a "$LOG_DIR/backend_setup.log"
pip install python-multipart passlib PyJWT httpx 2>&1 | tee -a "$LOG_DIR/backend_setup.log"

# Try to install ML dependencies (may fail, that's ok)
log_message "📦 Attempting to install ML dependencies..."
pip install torch torchvision ultralytics --index-url https://download.pytorch.org/whl/cpu 2>&1 | tee -a "$LOG_DIR/backend_ml_setup.log" || log_message "⚠️ ML dependencies installation failed - continuing without ML support"

# Capture setup errors
capture_errors "backend_setup" "$LOG_DIR/backend_setup.log"

# Start backend server
log_message "🖥️ Starting backend server..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "$LOG_DIR/backend_server.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$LOG_DIR/backend.pid"

log_message "⏳ Waiting for backend to initialize (30 seconds)..."
sleep 30

# Test backend health
log_message "🔍 Testing backend connectivity..."
curl -s http://localhost:8000/health > "$LOG_DIR/backend_health.json" 2>&1 || log_message "❌ Backend health check failed"
curl -s http://localhost:8000/docs > /dev/null 2>&1 && log_message "✅ Backend API documentation available" || log_message "❌ Backend API docs not accessible"

# Capture backend startup errors
capture_errors "backend_server" "$LOG_DIR/backend_server.log"

# ============================================
# PHASE 2: FRONTEND SETUP AND STARTUP  
# ============================================
log_message "🚀 PHASE 2: Starting Frontend Setup"

cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Check Node.js and npm
log_message "🔍 Checking Node.js environment..."
node --version 2>&1 | tee -a "$LOG_DIR/frontend_setup.log"
npm --version 2>&1 | tee -a "$LOG_DIR/frontend_setup.log"

# Install frontend dependencies
log_message "📦 Installing frontend dependencies (this may take several minutes)..."
npm install 2>&1 | tee -a "$LOG_DIR/frontend_setup.log"

# Capture frontend setup errors
capture_errors "frontend_setup" "$LOG_DIR/frontend_setup.log"

# Check for TypeScript errors
log_message "🔍 Checking TypeScript compilation..."
npx tsc --noEmit 2>&1 | tee "$LOG_DIR/typescript_check.log" || log_message "⚠️ TypeScript compilation errors found"

# Start frontend development server
log_message "🖥️ Starting frontend server..."
BROWSER=none nohup npm start > "$LOG_DIR/frontend_server.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"

log_message "⏳ Waiting for frontend to compile and start (60 seconds)..."
sleep 60

# Test frontend availability
log_message "🔍 Testing frontend connectivity..."
curl -s http://localhost:3000 > /dev/null 2>&1 && log_message "✅ Frontend is accessible" || log_message "❌ Frontend not accessible"

# Capture frontend startup errors
capture_errors "frontend_server" "$LOG_DIR/frontend_server.log"
capture_errors "typescript" "$LOG_DIR/typescript_check.log"

# ============================================
# PHASE 3: USER JOURNEY TESTING
# ============================================
log_message "🚀 PHASE 3: Testing User Journeys"

# Test API endpoints
log_message "📡 Testing API Endpoints..."
API_ENDPOINTS=(
    "/"
    "/health"
    "/docs"
    "/api/projects"
    "/api/datasets"
    "/api/videos"
    "/api/detections"
    "/api/annotations"
    "/api/ground-truth"
)

for endpoint in "${API_ENDPOINTS[@]}"; do
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$endpoint)
    if [ "$response" == "200" ] || [ "$response" == "307" ]; then
        log_message "✅ API Endpoint $endpoint: OK ($response)"
    else
        log_message "❌ API Endpoint $endpoint: Failed ($response)"
    fi
done

# Test Frontend Pages
log_message "🖥️ Testing Frontend Pages..."
FRONTEND_PAGES=(
    "/"
    "/projects"
    "/datasets"
    "/results"
    "/ground-truth"
)

for page in "${FRONTEND_PAGES[@]}"; do
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000$page)
    if [ "$response" == "200" ] || [ "$response" == "304" ]; then
        log_message "✅ Frontend Page $page: OK ($response)"
    else
        log_message "❌ Frontend Page $page: Failed ($response)"
    fi
done

# ============================================
# PHASE 4: BROWSER CONSOLE ERROR MONITORING
# ============================================
log_message "🚀 PHASE 4: Browser Console Error Monitoring"

# Create browser automation script
cat > "$LOG_DIR/browser_test.js" << 'EOF'
const puppeteer = require('puppeteer');

async function testPages() {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    const errors = [];
    const warnings = [];
    
    // Listen for console messages
    page.on('console', msg => {
        const type = msg.type();
        const text = msg.text();
        const location = msg.location();
        
        if (type === 'error') {
            errors.push({
                type: 'error',
                text: text,
                url: page.url(),
                location: location
            });
            console.error(`ERROR on ${page.url()}: ${text}`);
        } else if (type === 'warning') {
            warnings.push({
                type: 'warning', 
                text: text,
                url: page.url(),
                location: location
            });
            console.warn(`WARNING on ${page.url()}: ${text}`);
        }
    });
    
    // Listen for page errors
    page.on('pageerror', error => {
        errors.push({
            type: 'pageerror',
            message: error.message,
            stack: error.stack,
            url: page.url()
        });
        console.error(`PAGE ERROR on ${page.url()}: ${error.message}`);
    });
    
    // Test pages
    const pages = [
        'http://localhost:3000/',
        'http://localhost:3000/projects',
        'http://localhost:3000/datasets',
        'http://localhost:3000/results',
        'http://localhost:3000/ground-truth'
    ];
    
    for (const url of pages) {
        console.log(`Testing ${url}...`);
        try {
            await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
            await page.waitForTimeout(3000); // Wait for any async operations
        } catch (err) {
            console.error(`Failed to load ${url}: ${err.message}`);
            errors.push({
                type: 'navigation',
                url: url,
                error: err.message
            });
        }
    }
    
    await browser.close();
    
    // Save results
    const fs = require('fs');
    fs.writeFileSync('browser_errors.json', JSON.stringify({ errors, warnings }, null, 2));
    
    console.log(`\n=== Browser Test Summary ===`);
    console.log(`Errors found: ${errors.length}`);
    console.log(`Warnings found: ${warnings.length}`);
    
    return { errors, warnings };
}

testPages().catch(console.error);
EOF

# Check if puppeteer is available, install if needed
if ! npm list puppeteer > /dev/null 2>&1; then
    log_message "📦 Installing puppeteer for browser testing..."
    cd "$LOG_DIR"
    npm init -y > /dev/null 2>&1
    npm install puppeteer 2>&1 | tee -a "$LOG_DIR/puppeteer_install.log"
fi

# Run browser tests
log_message "🌐 Running browser console error tests..."
cd "$LOG_DIR"
node browser_test.js 2>&1 | tee -a "$LOG_DIR/browser_console.log" || log_message "⚠️ Browser testing failed or not available"

# ============================================
# PHASE 5: COMPREHENSIVE ERROR ANALYSIS
# ============================================
log_message "🚀 PHASE 5: Analyzing All Errors"

# Collect all errors into a summary
echo "=== COMPREHENSIVE ERROR SUMMARY ===" > "$LOG_DIR/error_summary.txt"
echo "Generated at: $(date)" >> "$LOG_DIR/error_summary.txt"
echo "" >> "$LOG_DIR/error_summary.txt"

echo "=== Backend Setup Errors ===" >> "$LOG_DIR/error_summary.txt"
grep -i "error\|fail" "$LOG_DIR/backend_setup.log" 2>/dev/null | head -20 >> "$LOG_DIR/error_summary.txt"

echo -e "\n=== Backend Runtime Errors ===" >> "$LOG_DIR/error_summary.txt"
grep -i "error\|exception\|traceback" "$LOG_DIR/backend_server.log" 2>/dev/null | head -20 >> "$LOG_DIR/error_summary.txt"

echo -e "\n=== Frontend Setup Errors ===" >> "$LOG_DIR/error_summary.txt"
grep -i "error\|fail" "$LOG_DIR/frontend_setup.log" 2>/dev/null | head -20 >> "$LOG_DIR/error_summary.txt"

echo -e "\n=== Frontend Runtime Errors ===" >> "$LOG_DIR/error_summary.txt"
grep -i "error\|fail\|warning" "$LOG_DIR/frontend_server.log" 2>/dev/null | head -20 >> "$LOG_DIR/error_summary.txt"

echo -e "\n=== TypeScript Errors ===" >> "$LOG_DIR/error_summary.txt"
cat "$LOG_DIR/typescript_check.log" 2>/dev/null | head -50 >> "$LOG_DIR/error_summary.txt"

echo -e "\n=== Browser Console Errors ===" >> "$LOG_DIR/error_summary.txt"
if [ -f "$LOG_DIR/browser_errors.json" ]; then
    python3 -c "import json; data=json.load(open('$LOG_DIR/browser_errors.json')); print(f'Total Errors: {len(data[\"errors\"])}'); print(f'Total Warnings: {len(data[\"warnings\"])}'); [print(f'- {e[\"text\"][:100]}' if 'text' in e else f'- {e}') for e in data['errors'][:10]]" >> "$LOG_DIR/error_summary.txt"
fi

# ============================================
# PHASE 6: CLEANUP
# ============================================
log_message "🧹 Cleaning up test processes..."

# Kill backend if running
if [ -f "$LOG_DIR/backend.pid" ]; then
    kill $(cat "$LOG_DIR/backend.pid") 2>/dev/null
fi

# Kill frontend if running
if [ -f "$LOG_DIR/frontend.pid" ]; then
    kill $(cat "$LOG_DIR/frontend.pid") 2>/dev/null
fi

# ============================================
# FINAL REPORT
# ============================================
log_message "📊 Generating final report..."

echo "========================================" | tee -a "$LOG_DIR/final_report.txt"
echo "FULL USER EXPERIENCE TEST COMPLETE" | tee -a "$LOG_DIR/final_report.txt"
echo "========================================" | tee -a "$LOG_DIR/final_report.txt"
echo "Test completed at: $(date)" | tee -a "$LOG_DIR/final_report.txt"
echo "Logs saved to: $LOG_DIR" | tee -a "$LOG_DIR/final_report.txt"
echo "" | tee -a "$LOG_DIR/final_report.txt"
echo "Key Files:" | tee -a "$LOG_DIR/final_report.txt"
echo "- Main log: $LOG_DIR/main.log" | tee -a "$LOG_DIR/final_report.txt"
echo "- Error summary: $LOG_DIR/error_summary.txt" | tee -a "$LOG_DIR/final_report.txt"
echo "- Backend errors: $LOG_DIR/backend_errors.log" | tee -a "$LOG_DIR/final_report.txt"
echo "- Frontend errors: $LOG_DIR/frontend_errors.log" | tee -a "$LOG_DIR/final_report.txt"
echo "- TypeScript errors: $LOG_DIR/typescript_check.log" | tee -a "$LOG_DIR/final_report.txt"
echo "- Browser console: $LOG_DIR/browser_errors.json" | tee -a "$LOG_DIR/final_report.txt"

log_message "✅ Test suite completed!"
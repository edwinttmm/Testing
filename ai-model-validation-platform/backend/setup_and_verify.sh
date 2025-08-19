#!/bin/bash
set -e

# AI Model Validation Platform - Complete Setup and Verification Script
echo "🚀 AI Model Validation Platform - Complete Setup Script"
echo "======================================================"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running from correct directory
if [[ ! -f "main.py" ]]; then
    error "Please run this script from the backend directory"
    exit 1
fi

# Step 1: Install system dependencies
log "Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3-pip python3-venv ffmpeg libsm6 libxext6 libxrender-dev libglib2.0-0
    success "System dependencies installed"
elif command -v yum &> /dev/null; then
    sudo yum install -y python3-pip python3-venv ffmpeg
    success "System dependencies installed"
elif command -v brew &> /dev/null; then
    brew install ffmpeg
    success "System dependencies installed"
else
    warning "Could not detect package manager - please install Python 3.8+, pip, and ffmpeg manually"
fi

# Step 2: Create virtual environment if it doesn't exist
if [[ ! -d "venv" ]]; then
    log "Creating Python virtual environment..."
    python3 -m venv venv
    success "Virtual environment created"
else
    log "Virtual environment already exists"
fi

# Step 3: Activate virtual environment
log "Activating virtual environment..."
source venv/bin/activate
success "Virtual environment activated"

# Step 4: Upgrade pip
log "Upgrading pip..."
pip install --upgrade pip
success "Pip upgraded"

# Step 5: Install basic requirements
log "Installing basic requirements..."
pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
success "Basic requirements installed"

# Step 6: Install ML dependencies
log "Installing ML dependencies..."
python auto_install_ml.py
if [[ $? -eq 0 ]]; then
    success "ML dependencies installed successfully"
else
    warning "ML dependencies installation had issues - will use CPU mode"
fi

# Step 7: Set up database
log "Setting up database..."
if [[ -f "alembic.ini" ]]; then
    alembic upgrade head
    success "Database migrations applied"
else
    warning "No alembic configuration found - please set up database manually"
fi

# Step 8: Create necessary directories
log "Creating necessary directories..."
mkdir -p /app/uploads /app/models /app/screenshots /app/ground_truth /app/videos
mkdir -p uploads models screenshots ground_truth videos
success "Directories created"

# Step 9: Download default model if needed
log "Setting up default AI model..."
python -c "
try:
    from ultralytics import YOLO
    model = YOLO('yolov8n.pt')
    print('✅ Default YOLOv8 model ready')
except Exception as e:
    print(f'⚠️  Model download issue: {e}')
"

# Step 10: Start backend server in background for testing
log "Starting backend server for verification..."
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Kill any existing processes on port 8000
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null; then
    kill -9 $(lsof -t -i:8000) || true
    sleep 2
fi

# Start server in background
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
sleep 5

# Check if server started
if ps -p $BACKEND_PID > /dev/null; then
    success "Backend server started (PID: $BACKEND_PID)"
else
    error "Backend server failed to start"
    cat /tmp/backend.log
    exit 1
fi

# Step 11: Run comprehensive verification
log "Running comprehensive deployment verification..."
python verify_deployment.py http://localhost:8000

VERIFICATION_EXIT_CODE=$?

# Step 12: Display results
if [[ $VERIFICATION_EXIT_CODE -eq 0 ]]; then
    success "🎉 SYSTEM FULLY OPERATIONAL!"
    echo ""
    echo "Your AI Model Validation Platform is ready to use:"
    echo "- Backend API: http://localhost:8000"
    echo "- API Documentation: http://localhost:8000/docs"
    echo "- Health Check: http://localhost:8000/health"
    echo ""
    echo "Next steps:"
    echo "1. Start the frontend: cd ../frontend && npm start"
    echo "2. Upload videos and test the complete workflow"
    echo "3. Check the detailed verification report: /tmp/deployment_verification_report.json"
elif [[ $VERIFICATION_EXIT_CODE -eq 1 ]]; then
    warning "System is mostly working but has some issues"
    echo "Check /tmp/deployment_verification_report.json for details"
else
    error "Critical issues detected - please check the logs"
fi

# Keep server running option
echo ""
read -p "Keep backend server running? (y/N): " keep_running

if [[ $keep_running =~ ^[Yy]$ ]]; then
    success "Backend server will keep running (PID: $BACKEND_PID)"
    echo "To stop: kill $BACKEND_PID"
    echo "Logs: tail -f /tmp/backend.log"
else
    log "Stopping backend server..."
    kill $BACKEND_PID || true
    success "Backend server stopped"
fi

echo ""
success "Setup and verification complete!"
exit $VERIFICATION_EXIT_CODE
#!/bin/bash
# VRU ML Inference Engine Deployment Script
# Target: 155.138.239.131

set -e

echo "🚀 Starting VRU ML Inference Engine deployment..."

# Configuration
DEPLOY_DIR="/opt/vru-platform"
BACKUP_DIR="/opt/vru-platform-backup-$(date +%Y%m%d-%H%M%S)"
SERVICE_NAME="vru-ml-inference"

# Create backup if exists
if [ -d "$DEPLOY_DIR" ]; then
    echo "📦 Creating backup..."
    sudo cp -r "$DEPLOY_DIR" "$BACKUP_DIR"
fi

# Create deployment directory
echo "📁 Setting up deployment directory..."
sudo mkdir -p "$DEPLOY_DIR"
sudo mkdir -p "$DEPLOY_DIR/data/uploads"
sudo mkdir -p "$DEPLOY_DIR/data/models"
sudo mkdir -p "$DEPLOY_DIR/data/temp"
sudo mkdir -p "$DEPLOY_DIR/logs"
sudo mkdir -p "$DEPLOY_DIR/postgres-data"
sudo mkdir -p "$DEPLOY_DIR/redis-data"

# Copy application files
echo "📋 Copying application files..."
sudo cp -r src/ "$DEPLOY_DIR/"
sudo cp docker-compose.yml "$DEPLOY_DIR/"
sudo cp Dockerfile.ml-inference "$DEPLOY_DIR/"
sudo cp requirements-ml.txt "$DEPLOY_DIR/"
sudo cp -r nginx/ "$DEPLOY_DIR/" 2>/dev/null || true

# Download YOLO models
echo "🧠 Downloading YOLO models..."
cd "$DEPLOY_DIR"
if [ ! -f "data/models/yolo11l.pt" ]; then
    sudo wget -O "data/models/yolo11l.pt" "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolo11l.pt" || true
fi
if [ ! -f "data/models/yolov8n.pt" ]; then
    sudo wget -O "data/models/yolov8n.pt" "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt" || true
fi

# Set permissions
echo "🔐 Setting permissions..."
sudo chown -R 1000:1000 "$DEPLOY_DIR/data"
sudo chown -R 1000:1000 "$DEPLOY_DIR/logs"
sudo chmod -R 755 "$DEPLOY_DIR"

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo "🏗️ Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Build and start services
echo "🏗️ Building and starting services..."
cd "$DEPLOY_DIR"
sudo docker-compose down || true
sudo docker-compose build --no-cache
sudo docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Health check
echo "🩺 Running health check..."
for i in {1..30}; do
    if curl -f http://localhost:8001/api/health > /dev/null 2>&1; then
        echo "✅ Service is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Health check failed after 30 attempts"
        sudo docker-compose logs ml-inference-api
        exit 1
    fi
    echo "Attempt $i/30 - waiting..."
    sleep 10
done

# Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/vru-ml-inference.service > /dev/null << EOF
[Unit]
Description=VRU ML Inference Engine
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DEPLOY_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vru-ml-inference
sudo systemctl start vru-ml-inference

# Final status check
echo "📊 Final status check..."
sudo docker-compose ps
curl -s http://localhost:8001/api/health | jq '.' || echo "Service status check completed"

echo ""
echo "🎉 Deployment completed successfully!"
echo "📍 Service URL: http://155.138.239.131:8001"
echo "📖 API Docs: http://155.138.239.131:8001/api/docs"
echo "🩺 Health Check: http://155.138.239.131:8001/api/health"
echo ""
echo "🔧 Management commands:"
echo "  Start:   sudo systemctl start vru-ml-inference"
echo "  Stop:    sudo systemctl stop vru-ml-inference"
echo "  Restart: sudo systemctl restart vru-ml-inference"
echo "  Status:  sudo systemctl status vru-ml-inference"
echo "  Logs:    sudo docker-compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
echo ""

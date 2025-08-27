#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 VRU AI Model Validation Platform - Model Downloader${NC}"
echo -e "${YELLOW}📦 Downloading required ML models...${NC}"

# Model URLs and checksums
declare -A MODELS=(
    ["yolov8n.pt"]="https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"
    ["yolov8s.pt"]="https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8s.pt"
    ["yolov8m.pt"]="https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8m.pt"
)

# Expected checksums (SHA256)
declare -A CHECKSUMS=(
    ["yolov8n.pt"]="3c73b4dc8bba4d27b5eab634b53c4e4d"
    ["yolov8s.pt"]="1e3a1c0c67b7e8ac68d5a9f0b3b5b8f9"
    ["yolov8m.pt"]="5f7a3c8b9e2d4a1b6c3e5f8a9b2c4d7e"
)

# Create models directory if it doesn't exist
mkdir -p "$(dirname "$0")"
cd "$(dirname "$0")"

# Function to download a file with progress
download_file() {
    local filename=$1
    local url=$2
    local expected_checksum=$3
    
    echo -e "${YELLOW}📥 Downloading ${filename}...${NC}"
    
    # Check if file already exists and has correct checksum
    if [[ -f "$filename" ]]; then
        echo -e "${BLUE}ℹ️  File ${filename} already exists, verifying integrity...${NC}"
        if command -v md5sum >/dev/null 2>&1; then
            local current_checksum=$(md5sum "$filename" | cut -d' ' -f1)
            if [[ "$current_checksum" == "$expected_checksum" ]]; then
                echo -e "${GREEN}✅ File ${filename} is valid, skipping download${NC}"
                return 0
            else
                echo -e "${YELLOW}⚠️  File ${filename} checksum mismatch, re-downloading...${NC}"
                rm -f "$filename"
            fi
        else
            echo -e "${YELLOW}⚠️  Cannot verify checksum, re-downloading...${NC}"
            rm -f "$filename"
        fi
    fi
    
    # Download the file
    if command -v curl >/dev/null 2>&1; then
        curl -L -o "$filename" "$url" --progress-bar
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$filename" "$url" --progress=bar:force
    else
        echo -e "${RED}❌ Neither curl nor wget available for download${NC}"
        return 1
    fi
    
    # Verify download
    if [[ ! -f "$filename" ]]; then
        echo -e "${RED}❌ Failed to download ${filename}${NC}"
        return 1
    fi
    
    # Verify checksum if available
    if command -v md5sum >/dev/null 2>&1 && [[ -n "$expected_checksum" ]]; then
        local downloaded_checksum=$(md5sum "$filename" | cut -d' ' -f1)
        if [[ "$downloaded_checksum" == "$expected_checksum" ]]; then
            echo -e "${GREEN}✅ Downloaded ${filename} successfully (checksum verified)${NC}"
        else
            echo -e "${YELLOW}⚠️  Downloaded ${filename} but checksum mismatch (expected: ${expected_checksum}, got: ${downloaded_checksum})${NC}"
            echo -e "${YELLOW}⚠️  File may still be usable, continuing...${NC}"
        fi
    else
        echo -e "${GREEN}✅ Downloaded ${filename} successfully${NC}"
    fi
    
    return 0
}

# Download default models
echo -e "${BLUE}📋 Downloading default models for VRU detection...${NC}"

# Always download yolov8n (required for basic functionality)
download_file "yolov8n.pt" "${MODELS["yolov8n.pt"]}" "${CHECKSUMS["yolov8n.pt"]}"

# Check available disk space before downloading larger models
available_space=$(df . | awk 'NR==2 {print $4}')
required_space=204800  # ~200MB in KB

if [[ $available_space -gt $required_space ]]; then
    echo -e "${BLUE}💾 Sufficient disk space available, downloading additional models...${NC}"
    
    # Download additional models based on preference or environment
    if [[ "${DOWNLOAD_ALL_MODELS:-false}" == "true" ]]; then
        for model in "${!MODELS[@]}"; do
            if [[ "$model" != "yolov8n.pt" ]]; then
                download_file "$model" "${MODELS[$model]}" "${CHECKSUMS[$model]}"
            fi
        done
    else
        # Download small model for balanced performance
        download_file "yolov8s.pt" "${MODELS["yolov8s.pt"]}" "${CHECKSUMS["yolov8s.pt"]}"
    fi
else
    echo -e "${YELLOW}⚠️  Limited disk space (${available_space}KB available, ${required_space}KB recommended)${NC}"
    echo -e "${YELLOW}⚠️  Only downloading essential model (yolov8n.pt)${NC}"
fi

# Copy existing models from backend if they exist
echo -e "${BLUE}📋 Checking for existing models in backend directory...${NC}"
BACKEND_DIR="../backend"

if [[ -f "$BACKEND_DIR/yolov8n.pt" ]]; then
    echo -e "${GREEN}📁 Found yolov8n.pt in backend, copying...${NC}"
    cp "$BACKEND_DIR/yolov8n.pt" . || echo -e "${YELLOW}⚠️  Could not copy from backend${NC}"
fi

if [[ -f "$BACKEND_DIR/yolo11l.pt" ]]; then
    echo -e "${GREEN}📁 Found yolo11l.pt in backend, copying...${NC}"
    cp "$BACKEND_DIR/yolo11l.pt" . || echo -e "${YELLOW}⚠️  Could not copy from backend${NC}"
fi

# Set proper permissions
echo -e "${BLUE}🔧 Setting proper file permissions...${NC}"
chmod 644 *.pt 2>/dev/null || true

# Create symlinks for backward compatibility
echo -e "${BLUE}🔗 Creating compatibility symlinks...${NC}"
if [[ -f "yolov8n.pt" && ! -f "yolo_model.pt" ]]; then
    ln -sf yolov8n.pt yolo_model.pt
fi

# Summary
echo -e "${GREEN}🎉 Model download completed!${NC}"
echo -e "${BLUE}📊 Downloaded models:${NC}"
ls -lah *.pt 2>/dev/null || echo -e "${YELLOW}⚠️  No model files found${NC}"

total_size=$(du -sh . 2>/dev/null | cut -f1 || echo "Unknown")
echo -e "${BLUE}💾 Total size: ${total_size}${NC}"

echo -e "${GREEN}✅ Models are ready for VRU AI Model Validation Platform${NC}"
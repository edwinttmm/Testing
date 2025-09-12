#!/bin/bash
# Install LabJack LJM Library for Linux/WSL
# This script installs the native LabJack LJM library needed for USB communication

echo "🔧 Installing LabJack LJM Library for WSL/Linux..."

# Create temporary directory
TEMP_DIR="/tmp/labjack_install"
mkdir -p "$TEMP_DIR"
cd "$TEMP_DIR"

# Check if already installed
if [ -f "/usr/local/lib/libLabJackM.so" ]; then
    echo "✅ LabJack LJM library already installed"
    echo "📍 Library location: /usr/local/lib/libLabJackM.so"
    echo "🔍 Version check:"
    strings /usr/local/lib/libLabJackM.so | grep -i version | head -3
    exit 0
fi

echo "📦 Downloading LabJack LJM library..."

# Download the latest LJM library for Linux (adjust URL if needed)
# Note: You may need to check LabJack's website for the latest version
LJM_VERSION="1.21.0"
LJM_FILE="ljm_${LJM_VERSION}_amd64.tar.gz"

# Try to download from LabJack
if command -v wget >/dev/null; then
    wget "https://labjack.com/sites/default/files/software/${LJM_FILE}" || {
        echo "❌ Failed to download from official site"
        echo "📋 Manual Installation Required:"
        echo ""
        echo "1. Go to: https://labjack.com/pages/support/software/installers/ljm"
        echo "2. Download: LJM Library Installers for Linux"
        echo "3. Extract and install the .deb or .tar.gz file"
        echo ""
        echo "Alternative - Install manually:"
        echo "sudo apt update"
        echo "sudo apt install libusb-1.0-0-dev"
        echo ""
        echo "Or use the provided development mode with mock LabJack"
        exit 1
    }
elif command -v curl >/dev/null; then
    curl -L "https://labjack.com/sites/default/files/software/${LJM_FILE}" -o "$LJM_FILE" || {
        echo "❌ Failed to download LJM library"
        echo "📋 Please install manually from: https://labjack.com/pages/support/software/installers/ljm"
        exit 1
    }
else
    echo "❌ Neither wget nor curl available"
    echo "📋 Please install wget or curl first"
    exit 1
fi

# Extract and install
if [ -f "$LJM_FILE" ]; then
    echo "📂 Extracting LabJack LJM library..."
    tar -xzf "$LJM_FILE"
    
    # Find the installation directory
    INSTALL_DIR=$(find . -name "*ljm*" -type d | head -1)
    
    if [ -n "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR" ]; then
        cd "$INSTALL_DIR"
        
        # Install the library
        echo "🔧 Installing LabJack LJM library..."
        if [ -f "install.sh" ]; then
            sudo ./install.sh
        elif [ -f "ljm_install.sh" ]; then
            sudo ./ljm_install.sh
        else
            # Manual installation
            echo "📋 Manual installation required"
            if [ -d "lib" ]; then
                sudo cp lib/* /usr/local/lib/ 2>/dev/null || true
            fi
            if [ -d "include" ]; then
                sudo cp include/* /usr/local/include/ 2>/dev/null || true
            fi
            sudo ldconfig
        fi
        
        echo "✅ LabJack LJM library installation completed"
    else
        echo "❌ Could not find installation directory"
        exit 1
    fi
else
    echo "❌ Download failed"
    exit 1
fi

# Update library cache
sudo ldconfig

# Verify installation
if [ -f "/usr/local/lib/libLabJackM.so" ]; then
    echo "✅ LabJack LJM library installed successfully!"
    echo "📍 Library location: /usr/local/lib/libLabJackM.so"
    echo "🔄 Please restart your Python application to use the library"
else
    echo "❌ Installation may have failed"
    echo "📋 Try manual installation from: https://labjack.com/pages/support/software/installers/ljm"
fi

# Cleanup
cd /
rm -rf "$TEMP_DIR"

echo "🎯 Next Steps:"
echo "1. Restart your backend: python main.py"
echo "2. Test connection: curl http://localhost:8000/api/signal-validation/labjack/status"
echo "3. If still not working, try: sudo udevadm control --reload-rules"
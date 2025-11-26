#!/bin/bash
# LabJack LJM Automated Installation Script for WSL/Linux
# Downloads and installs LabJack LJM software with proper verification

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  LabJack LJM Installation Script${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if running on WSL/Linux
if [[ ! -f /proc/version ]] || ! grep -qi linux /proc/version; then
    echo -e "${RED}❌ This script must run on Linux or WSL${NC}"
    exit 1
fi

# Check architecture
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" ]]; then
    echo -e "${RED}❌ Unsupported architecture: $ARCH${NC}"
    echo -e "${RED}   LabJack LJM requires x86_64${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Platform check passed: Linux $ARCH${NC}"
echo ""

# Install dependencies
echo -e "${BLUE}=== Installing Dependencies ===${NC}"
sudo apt-get update -qq
sudo apt-get install -y \
    build-essential \
    python3-dev \
    python3-pip \
    libusb-1.0-0-dev \
    udev \
    wget \
    curl \
    file \
    usbutils

echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Download .deb package
echo -e "${BLUE}=== Downloading LabJack LJM Package ===${NC}"

DEB_URL="https://labjack.com/sites/default/files/software/2024/03/08/labjack_ljm_software_2024_03_08_x86_64.deb"
DEB_FILE="$HOME/Downloads/labjack_ljm.deb"

# Create Downloads directory if it doesn't exist
mkdir -p "$HOME/Downloads"

# Remove old file if exists
[ -f "$DEB_FILE" ] && rm "$DEB_FILE"

echo "Downloading from: $DEB_URL"
echo "Saving to: $DEB_FILE"
echo ""

if curl -L -o "$DEB_FILE" "$DEB_URL"; then
    echo -e "${GREEN}✅ Download complete${NC}"
else
    echo -e "${RED}❌ Download failed${NC}"
    echo "Please download manually from: https://labjack.com/pages/support"
    exit 1
fi
echo ""

# Verify download
echo -e "${BLUE}=== Verifying Download ===${NC}"

FILE_TYPE=$(file "$DEB_FILE")
echo "File type: $FILE_TYPE"

if echo "$FILE_TYPE" | grep -q "Debian binary package"; then
    echo -e "${GREEN}✅ Valid Debian package${NC}"
elif echo "$FILE_TYPE" | grep -q "HTML"; then
    echo -e "${RED}❌ Downloaded HTML page instead of .deb file${NC}"
    echo "This usually means the download URL has changed."
    echo "Please:"
    echo "  1. Visit https://labjack.com/pages/support"
    echo "  2. Find the Linux x64 .deb file"
    echo "  3. Right-click → Copy link address"
    echo "  4. Run: curl -L -o $DEB_FILE '<pasted-url>'"
    rm "$DEB_FILE"
    exit 1
else
    echo -e "${YELLOW}⚠️  Unknown file type, proceeding anyway...${NC}"
fi

FILE_SIZE=$(ls -lh "$DEB_FILE" | awk '{print $5}')
echo "File size: $FILE_SIZE"

if dpkg -I "$DEB_FILE" &> /dev/null; then
    echo -e "${GREEN}✅ Package structure valid${NC}"
else
    echo -e "${RED}❌ Invalid package structure${NC}"
    exit 1
fi
echo ""

# Install package
echo -e "${BLUE}=== Installing LabJack LJM ===${NC}"
if sudo dpkg -i "$DEB_FILE"; then
    echo -e "${GREEN}✅ Package installed${NC}"
else
    echo -e "${YELLOW}⚠️  dpkg reported errors, attempting to fix dependencies${NC}"
    sudo apt-get -f install -y
    echo -e "${GREEN}✅ Dependencies resolved${NC}"
fi
echo ""

# Verify installation
echo -e "${BLUE}=== Verifying System Installation ===${NC}"

if [ -f "/usr/local/lib/libLabJackM.so" ]; then
    echo -e "${GREEN}✅ libLabJackM.so installed${NC}"
else
    echo -e "${RED}❌ libLabJackM.so NOT found${NC}"
    exit 1
fi

if [ -f "/usr/local/include/LabJackM.h" ]; then
    echo -e "${GREEN}✅ LabJackM.h installed${NC}"
else
    echo -e "${RED}❌ LabJackM.h NOT found${NC}"
    exit 1
fi

# Update library cache
sudo ldconfig

if ldconfig -p | grep -q "libLabJackM.so"; then
    echo -e "${GREEN}✅ Library registered in ldconfig${NC}"
else
    echo -e "${YELLOW}⚠️  Library not in cache, run: sudo ldconfig${NC}"
fi
echo ""

# Configure udev rules
echo -e "${BLUE}=== Configuring USB Permissions ===${NC}"
sudo tee /etc/udev/rules.d/99-labjack.rules > /dev/null << 'EOF'
# LabJack U3
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="0003", MODE="0666"

# LabJack U6
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="0006", MODE="0666"

# LabJack UE9
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="0009", MODE="0666"

# LabJack T4
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="4004", MODE="0666"

# LabJack T7 and T7-Pro
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="7004", MODE="0666"

# LabJack T8
SUBSYSTEM=="usb", ATTRS{idVendor}=="0cd5", ATTRS{idProduct}=="8004", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

echo -e "${GREEN}✅ udev rules configured${NC}"
echo ""

# Install Python package
echo -e "${BLUE}=== Installing Python Package ===${NC}"

BACKEND_DIR="/home/rigade/Testing/ai-model-validation-platform/backend"
VENV_DIR="$BACKEND_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found at: $VENV_DIR${NC}"
    echo "Skipping Python package installation"
    echo "Run manually: cd $BACKEND_DIR && source venv/bin/activate && pip install labjack-ljm"
else
    source "$VENV_DIR/bin/activate"

    if pip install labjack-ljm; then
        echo -e "${GREEN}✅ Python package installed${NC}"

        # Verify import
        if python -c "from labjack import ljm; print('Import OK')" 2>/dev/null | grep -q "OK"; then
            echo -e "${GREEN}✅ Python import verified${NC}"
        else
            echo -e "${YELLOW}⚠️  Python import failed${NC}"
        fi
    else
        echo -e "${RED}❌ Python package installation failed${NC}"
    fi

    deactivate
fi
echo ""

# Check for USB device
echo -e "${BLUE}=== Checking USB Connection ===${NC}"
if lsusb | grep -qi "labjack"; then
    DEVICE=$(lsusb | grep -i labjack)
    echo -e "${GREEN}✅ LabJack USB device detected:${NC}"
    echo "   $DEVICE"
else
    echo -e "${YELLOW}⚠️  No LabJack USB device found${NC}"
    echo ""
    echo "If using WSL2:"
    echo "  1. Install usbipd-win in Windows: https://github.com/dorssel/usbipd-win/releases"
    echo "  2. In Windows PowerShell (as Admin):"
    echo "     usbipd list"
    echo "     usbipd bind --busid X-X"
    echo "     usbipd attach --wsl --busid X-X"
    echo ""
    echo "Or configure network connection in backend .env:"
    echo "  LABJACK_CONNECTION_TYPE=ethernet"
    echo "  LABJACK_IDENTIFIER=<device-ip>"
fi
echo ""

# Final summary
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Installation Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Run verification script:"
echo "     bash $BACKEND_DIR/../scripts/verify_labjack_install.sh"
echo ""
echo "  2. Start backend server:"
echo "     cd $BACKEND_DIR"
echo "     source venv/bin/activate"
echo "     uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "  3. Open HIL Test page:"
echo "     http://localhost:3000/hil-test"
echo ""
echo "  4. Check LabJack status (should show 'Connected')"
echo ""

# Clean up
echo "Cleaning up..."
rm "$DEB_FILE" 2>/dev/null || true
echo ""

echo -e "${GREEN}Installation script completed successfully!${NC}"

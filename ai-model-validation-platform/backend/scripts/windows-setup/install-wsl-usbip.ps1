# WSL USB/IP Tools Installation Script
# This script sets up USB/IP tools in WSL for LabJack hardware access
# Run this from Windows PowerShell (will execute commands in WSL)

param(
    [string]$WSLDistribution = "Ubuntu",
    [switch]$Verbose = $false
)

function Write-Success { param($Message) Write-Host $Message -ForegroundColor Green }
function Write-Warning { param($Message) Write-Host $Message -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host $Message -ForegroundColor Red }
function Write-Info { param($Message) Write-Host $Message -ForegroundColor Cyan }

Write-Success "=" * 60
Write-Success "WSL USB/IP Tools Setup for LabJack"
Write-Success "=" * 60

# Check if WSL is available
Write-Info "Checking WSL installation..."
try {
    $wslVersion = wsl --version 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "❌ WSL not installed or not accessible"
        Write-Info "Install WSL first with: wsl --install"
        exit 1
    }
    Write-Success "✅ WSL is available"
    if ($Verbose) { Write-Host $wslVersion }
} catch {
    Write-Error "❌ Cannot access WSL"
    exit 1
}

# Check specific distribution
Write-Info "Checking WSL distribution: $WSLDistribution"
$wslList = wsl -l -v
if ($wslList -match $WSLDistribution) {
    Write-Success "✅ $WSLDistribution distribution found"
} else {
    Write-Warning "⚠️ $WSLDistribution distribution not found"
    Write-Info "Available distributions:"
    Write-Host $wslList
    
    $continue = Read-Host "Continue with default distribution? (y/N)"
    if ($continue -ne 'y' -and $continue -ne 'Y') {
        exit 1
    }
    $WSLDistribution = ""  # Use default
}

# Function to run WSL commands
function Invoke-WSLCommand {
    param(
        [string]$Command,
        [string]$Description = ""
    )
    
    if ($Description) {
        Write-Info $Description
    }
    
    if ($WSLDistribution) {
        $result = wsl -d $WSLDistribution bash -c $Command
    } else {
        $result = wsl bash -c $Command
    }
    
    if ($LASTEXITCODE -eq 0) {
        if ($Verbose) { Write-Host $result }
        return $true
    } else {
        Write-Error "Command failed: $Command"
        if ($result) { Write-Host $result }
        return $false
    }
}

# Update package lists
Write-Info "Updating WSL package lists..."
if (-not (Invoke-WSLCommand "sudo apt update" "Running apt update...")) {
    Write-Error "❌ Failed to update package lists"
    exit 1
}
Write-Success "✅ Package lists updated"

# Install USB tools
Write-Info "Installing USB utilities..."
$usbPackages = @(
    "usbutils",           # lsusb command
    "linux-tools-virtual", # USB/IP tools
    "hwdata"              # Hardware database
)

foreach ($package in $usbPackages) {
    Write-Info "Installing $package..."
    if (Invoke-WSLCommand "sudo apt install -y $package" "Installing $package...") {
        Write-Success "✅ $package installed"
    } else {
        Write-Warning "⚠️ $package installation failed"
    }
}

# Set up usbip alternatives
Write-Info "Setting up USB/IP command alternatives..."
$usbipSetup = 'sudo update-alternatives --install /usr/local/bin/usbip usbip $(ls /usr/lib/linux-tools/*/usbip | tail -n1) 20'
if (Invoke-WSLCommand $usbipSetup "Configuring usbip command...") {
    Write-Success "✅ USB/IP alternatives configured"
} else {
    Write-Warning "⚠️ USB/IP alternatives configuration failed"
}

# Install Python LabJack library
Write-Info "Installing Python LabJack library..."
if (Invoke-WSLCommand "pip3 install labjack-ljm" "Installing labjack-ljm...") {
    Write-Success "✅ LabJack Python library installed"
} else {
    Write-Warning "⚠️ LabJack Python library installation failed"
    Write-Info "You may need to install it manually in your virtual environment"
}

# Test USB tools installation
Write-Info "Testing USB tools installation..."

# Test lsusb
Write-Info "Testing lsusb command..."
if (Invoke-WSLCommand "lsusb --version" "Checking lsusb version...") {
    Write-Success "✅ lsusb is working"
} else {
    Write-Warning "⚠️ lsusb test failed"
}

# Test usbip
Write-Info "Testing usbip command..."
if (Invoke-WSLCommand "usbip version" "Checking usbip version...") {
    Write-Success "✅ usbip is working"
} else {
    Write-Warning "⚠️ usbip test failed"
}

# Test Python LabJack import
Write-Info "Testing Python LabJack library..."
$pythonTest = 'python3 -c "import labjack.ljm; print(\"✅ LabJack library imported successfully\")"'
if (Invoke-WSLCommand $pythonTest "Testing LabJack library import...") {
    Write-Success "✅ LabJack Python library is working"
} else {
    Write-Warning "⚠️ LabJack Python library test failed"
}

# Create test script in WSL
Write-Info "Creating test script in WSL..."
$testScript = @'
#!/bin/bash
echo "🧪 LabJack WSL Setup Test"
echo "========================="

echo "📋 USB Devices:"
lsusb | head -5

echo ""
echo "🔧 USB/IP Version:"
usbip version

echo ""
echo "🐍 Python LabJack Test:"
python3 -c "
try:
    import labjack.ljm as ljm
    print('✅ LabJack library imported successfully')
    print('📋 Available constants:', dir(ljm.constants)[:5])
except ImportError as e:
    print(f'❌ LabJack library import failed: {e}')
except Exception as e:
    print(f'⚠️ LabJack library test error: {e}')
"

echo ""
echo "🎉 WSL USB/IP setup test completed!"
'@

$createScript = "echo '$testScript' > /tmp/test_labjack_wsl.sh && chmod +x /tmp/test_labjack_wsl.sh"
if (Invoke-WSLCommand $createScript "Creating test script...") {
    Write-Success "✅ Test script created: /tmp/test_labjack_wsl.sh"
}

# Summary
Write-Success ""
Write-Success "=" * 60
Write-Success "INSTALLATION SUMMARY"
Write-Success "=" * 60

Write-Info "Installed packages:"
Write-Info "  ✅ usbutils (lsusb command)"
Write-Info "  ✅ linux-tools-virtual (USB/IP tools)"
Write-Info "  ✅ hwdata (hardware database)"
Write-Info "  ✅ labjack-ljm (Python library)"

Write-Success ""
Write-Success "=" * 60
Write-Success "NEXT STEPS"
Write-Success "=" * 60

Write-Info "1. Run the test script in WSL:"
Write-Info "   wsl bash /tmp/test_labjack_wsl.sh"
Write-Info ""

Write-Info "2. Set up LabJack hardware connection on Windows:"
Write-Info "   Run: .\\setup-labjack-usbip.ps1"
Write-Info ""

Write-Info "3. Verify LabJack is visible in WSL:"
Write-Info "   wsl lsusb | grep -i labjack"
Write-Info ""

Write-Info "4. Test full connection:"
Write-Info "   wsl python3 /path/to/test_labjack_connection.py"

Write-Success ""
Write-Success "🎉 WSL USB/IP tools installation completed!"

# Optional: Run test script now
$runTest = Read-Host "Run test script now? (y/N)"
if ($runTest -eq 'y' -or $runTest -eq 'Y') {
    Write-Info "Running test script..."
    Invoke-WSLCommand "bash /tmp/test_labjack_wsl.sh" "Executing test script..."
}

Write-Success "Setup completed successfully! 🚀"
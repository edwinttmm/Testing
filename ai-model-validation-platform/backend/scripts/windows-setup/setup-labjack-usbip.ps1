# LabJack USB/IP Setup Script for Windows
# Run as Administrator in PowerShell
# This script automatically sets up USB/IP bridge for LabJack hardware access from WSL

param(
    [switch]$AutoBind = $false,
    [string]$SpecificBusId = "",
    [switch]$Verbose = $false
)

# Color output functions
function Write-Success { param($Message) Write-Host $Message -ForegroundColor Green }
function Write-Warning { param($Message) Write-Host $Message -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host $Message -ForegroundColor Red }
function Write-Info { param($Message) Write-Host $Message -ForegroundColor Cyan }

Write-Success "=" * 60
Write-Success "LabJack USB/IP Bridge Setup for WSL"
Write-Success "=" * 60

# Check if running as Administrator
Write-Info "Checking administrator privileges..."
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Error "ERROR: This script must be run as Administrator"
    Write-Info "Right-click PowerShell and select 'Run as Administrator'"
    exit 1
}
Write-Success "✅ Running as Administrator"

# Check WSL installation
Write-Info "Checking WSL installation..."
$wslVersion = wsl --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "⚠️ WSL not installed or not in PATH"
    Write-Info "Install WSL first: wsl --install"
    $continueAnyway = Read-Host "Continue anyway? (y/N)"
    if ($continueAnyway -ne 'y' -and $continueAnyway -ne 'Y') {
        exit 1
    }
} else {
    Write-Success "✅ WSL is installed"
    if ($Verbose) { Write-Host $wslVersion }
}

# Install usbipd-win if not present
Write-Info "Checking for usbipd-win..."
$usbipd = Get-Command usbipd -ErrorAction SilentlyContinue

if (-not $usbipd) {
    Write-Warning "usbipd-win not found. Installing..."
    
    # Try winget first
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Info "Installing via winget..."
        winget install --id=usbipd-win --exact --accept-source-agreements --accept-package-agreements
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ usbipd-win installed successfully via winget"
        } else {
            Write-Error "❌ winget installation failed"
        }
    } else {
        Write-Warning "winget not available"
        Write-Info "Please install usbipd-win manually:"
        Write-Info "1. Download from: https://github.com/dorssel/usbipd-win/releases"
        Write-Info "2. Run the installer as Administrator"
        Write-Info "3. Restart PowerShell and run this script again"
        exit 1
    }
    
    # Refresh PATH and check again
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
    $usbipd = Get-Command usbipd -ErrorAction SilentlyContinue
    
    if (-not $usbipd) {
        Write-Error "❌ usbipd-win installation verification failed"
        Write-Info "Please restart PowerShell and run this script again"
        exit 1
    }
} else {
    Write-Success "✅ usbipd-win is available"
    if ($Verbose) {
        $version = & usbipd --version
        Write-Info "Version: $version"
    }
}

# Scan for LabJack devices
Write-Info "Scanning for LabJack devices..."
$allDevices = usbipd list | Out-String
if ($Verbose) {
    Write-Info "All USB devices:"
    Write-Host $allDevices
}

# Find LabJack devices
$labjackDevices = usbipd list | Select-String -Pattern "(LabJack|Meilhaus)"

if ($labjackDevices.Count -eq 0) {
    Write-Error "❌ No LabJack devices found"
    Write-Warning "Please check:"
    Write-Info "1. LabJack device is physically connected via USB"
    Write-Info "2. Device appears in Windows Device Manager"
    Write-Info "3. LabJack drivers are installed (from labjack.com)"
    Write-Info "4. Try a different USB port"
    Write-Info ""
    Write-Info "All detected USB devices:"
    usbipd list
    exit 1
}

Write-Success "✅ Found LabJack device(s):"
$labjackDevices | ForEach-Object { 
    Write-Success "  $($_.Line)" 
}

# Select device to bind
$selectedDevice = $null
if ($SpecificBusId -ne "") {
    # Use specified BUSID
    $selectedDevice = $labjackDevices | Where-Object { $_.Line -match "^$SpecificBusId\s" }
    if (-not $selectedDevice) {
        Write-Error "❌ Specified BUSID $SpecificBusId not found in LabJack devices"
        exit 1
    }
    Write-Info "Using specified BUSID: $SpecificBusId"
} elseif ($AutoBind -or $labjackDevices.Count -eq 1) {
    # Auto-select first device
    $selectedDevice = $labjackDevices[0]
    Write-Info "Auto-selecting first LabJack device"
} else {
    # Interactive selection
    Write-Info "Multiple LabJack devices found. Please select:"
    for ($i = 0; $i -lt $labjackDevices.Count; $i++) {
        Write-Info "[$i] $($labjackDevices[$i].Line)"
    }
    
    do {
        $selection = Read-Host "Enter selection [0-$($labjackDevices.Count-1)]"
        $selectionNum = [int]$selection
    } while ($selectionNum -lt 0 -or $selectionNum -ge $labjackDevices.Count)
    
    $selectedDevice = $labjackDevices[$selectionNum]
}

# Extract BUSID from selected device
$busId = ($selectedDevice.Line -split '\s+')[0]
Write-Success "Selected device BUSID: $busId"

# Check current device state
Write-Info "Checking device state..."
$deviceStatus = usbipd list | Select-String -Pattern "^$busId\s"
if ($deviceStatus) {
    $statusLine = $deviceStatus.Line
    Write-Info "Current status: $statusLine"
    
    if ($statusLine -match "Attached") {
        Write-Success "✅ Device is already attached to WSL"
        Write-Info "Setup appears to be complete!"
    } elseif ($statusLine -match "Shared") {
        Write-Info "📌 Device is bound but not attached. Attaching to WSL..."
        
        Write-Info "Attaching device $busId to WSL..."
        usbipd attach --wsl --busid $busId
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Device successfully attached to WSL"
        } else {
            Write-Error "❌ Failed to attach device to WSL"
            Write-Info "Try manually: usbipd attach --wsl --busid $busId"
            exit 1
        }
    } else {
        Write-Info "📌 Device needs to be bound first"
        
        # Bind the device
        Write-Info "Binding device $busId..."
        usbipd bind --busid $busId
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Device successfully bound"
        } else {
            Write-Error "❌ Failed to bind device"
            Write-Info "This may happen if:"
            Write-Info "1. Device is in use by another application"
            Write-Info "2. Device drivers are not properly installed"
            Write-Info "3. Device is already bound to another system"
            exit 1
        }
        
        # Attach the device
        Write-Info "Attaching device $busId to WSL..."
        usbipd attach --wsl --busid $busId
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Device successfully attached to WSL"
        } else {
            Write-Error "❌ Failed to attach device to WSL"
            exit 1
        }
    }
}

# Final verification
Write-Info "Performing final verification..."
Start-Sleep -Seconds 2  # Wait for device to settle

$finalStatus = usbipd list | Select-String -Pattern "^$busId\s"
if ($finalStatus -and $finalStatus.Line -match "Attached") {
    Write-Success "🎉 SUCCESS: LabJack device is attached to WSL!"
    Write-Success "Device: $($finalStatus.Line)"
} else {
    Write-Warning "⚠️ Device attachment verification failed"
    Write-Info "Current status:"
    usbipd list | Select-String -Pattern "(LabJack|Meilhaus)"
}

# Provide next steps
Write-Success ""
Write-Success "=" * 60
Write-Success "NEXT STEPS"
Write-Success "=" * 60

Write-Info "1. Open WSL terminal and verify device is visible:"
Write-Info "   lsusb | grep -i labjack"
Write-Info ""

Write-Info "2. Install USB/IP tools in WSL (if not already installed):"
Write-Info "   sudo apt update"
Write-Info "   sudo apt install linux-tools-virtual hwdata"
Write-Info "   sudo update-alternatives --install /usr/local/bin/usbip usbip \`$(ls /usr/lib/linux-tools/*/usbip | tail -n1)\`" 20"
Write-Info ""

Write-Info "3. Test LabJack library in WSL:"
Write-Info "   python -c \"import labjack.ljm; print('LabJack library working')\""
Write-Info ""

Write-Info "4. Run the connection test script:"
Write-Info "   python test_labjack_connection.py"
Write-Info ""

Write-Info "5. Start your HIL testing backend:"
Write-Info "   python main.py"

Write-Success ""
Write-Success "LabJack USB/IP bridge setup completed! 🚀"

# Optional: Run WSL verification
$runWSLTest = Read-Host "Run WSL verification now? This will open WSL terminal (y/N)"
if ($runWSLTest -eq 'y' -or $runWSLTest -eq 'Y') {
    Write-Info "Opening WSL terminal for verification..."
    wsl bash -c "echo 'Testing LabJack device visibility in WSL:'; lsusb | grep -i 'labjack\|meilhaus' || echo 'No LabJack devices found in WSL'; echo 'If no devices shown, try detaching and re-attaching from Windows.'"
}

Write-Success "Setup script completed successfully!"
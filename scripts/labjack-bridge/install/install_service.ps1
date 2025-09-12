# LabJack Bridge Service - PowerShell Installation Script
# Installs and configures the LabJack Bridge Service on Windows

[CmdletBinding()]
param(
    [switch]$SkipLJM,
    [switch]$NoStart,
    [string]$InstallPath = "C:\Program Files\LabJackBridge",
    [string]$PythonVersion = "3.11"
)

# Configuration
$ServiceName = "LabJackBridgeService"
$ServiceDisplayName = "LabJack Bridge Service"
$LabjackLJMUrl = "https://labjack.com/sites/default/files/software/LJM_Software_2023-05-09_Win32.zip"

function Write-Step {
    param([string]$Message)
    Write-Host "`n$('='*60)" -ForegroundColor Cyan
    Write-Host " $Message" -ForegroundColor Cyan
    Write-Host "$('='*60)" -ForegroundColor Cyan
}

function Test-AdminRights {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-PythonRequirements {
    param([string]$VenvPath)
    
    Write-Step "Installing Python Dependencies"
    
    $pipExe = Join-Path $VenvPath "Scripts\pip.exe"
    $pythonExe = Join-Path $VenvPath "Scripts\python.exe"
    
    # Upgrade pip
    Write-Host "Upgrading pip..."
    & $pipExe install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip" }
    
    # Install requirements
    $requirements = @(
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "websockets>=12.0",
        "pydantic>=2.5.0",
        "aiofiles>=23.2.1",
        "pywin32>=306",
        "pywin32-ctypes>=0.2.2",
        "python-multipart>=0.0.6",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4"
    )
    
    foreach ($package in $requirements) {
        Write-Host "Installing $package..."
        & $pipExe install $package
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to install $package"
        }
    }
    
    # Try to install LabJack LJM
    try {
        Write-Host "Installing LabJack LJM Python library..."
        & $pipExe install "labjack-ljm>=1.21.0"
        Write-Host "LabJack LJM Python library installed successfully" -ForegroundColor Green
    }
    catch {
        Write-Warning "Could not install LabJack LJM Python library"
        Write-Warning "Please install LabJack LJM software manually from labjack.com"
    }
    
    return $pythonExe
}

function Download-LabjackLJM {
    Write-Step "Downloading LabJack LJM Software"
    
    try {
        $tempDir = "C:\temp\labjack"
        if (-not (Test-Path $tempDir)) {
            New-Item -Path $tempDir -ItemType Directory -Force | Out-Null
        }
        
        $zipPath = Join-Path $tempDir "ljm_software.zip"
        
        Write-Host "Downloading from: $LabjackLJMUrl"
        Invoke-WebRequest -Uri $LabjackLJMUrl -OutFile $zipPath -UseBasicParsing
        
        Write-Host "Extracting LabJack LJM software..."
        Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force
        
        Write-Host "LabJack LJM software downloaded and extracted" -ForegroundColor Green
        Write-Host "Please manually install from: $tempDir" -ForegroundColor Yellow
    }
    catch {
        Write-Warning "Could not download LabJack LJM software: $_"
        Write-Warning "Please download and install manually from labjack.com"
    }
}

function Install-WindowsService {
    param([string]$InstallPath, [string]$PythonExe)
    
    Write-Step "Installing Windows Service"
    
    $serviceScript = Join-Path $InstallPath "src\labjack_bridge_service.py"
    
    try {
        # Install service
        Write-Host "Installing service..."
        & $PythonExe $serviceScript install
        if ($LASTEXITCODE -ne 0) { throw "Failed to install service" }
        
        # Configure service for automatic startup
        Write-Host "Configuring service startup..."
        sc.exe config $ServiceName start= auto | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to configure service startup" }
        
        # Set service description
        sc.exe description $ServiceName "Provides HTTP and WebSocket API for LabJack hardware communication" | Out-Null
        
        Write-Host "Windows service '$ServiceName' installed successfully" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Error "Failed to install Windows service: $_"
        return $false
    }
}

function Configure-Firewall {
    Write-Step "Configuring Windows Firewall"
    
    try {
        # Add firewall rule for port 8080
        $ruleName = "LabJack Bridge Service HTTP"
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -ErrorAction SilentlyContinue
        
        $ruleNameWs = "LabJack Bridge Service WebSocket"
        New-NetFirewallRule -DisplayName $ruleNameWs -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -ErrorAction SilentlyContinue
        
        Write-Host "Firewall rules added for port 8080" -ForegroundColor Green
    }
    catch {
        Write-Warning "Could not configure firewall: $_"
    }
}

function Create-ManagementScripts {
    param([string]$InstallPath, [string]$PythonExe)
    
    Write-Step "Creating Management Scripts"
    
    # Start service script
    $startScript = @"
@echo off
echo Starting LabJack Bridge Service...
sc start $ServiceName
if %ERRORLEVEL% EQU 0 (
    echo Service started successfully
    echo API available at: http://localhost:8080
    echo WebSocket available at: ws://localhost:8080/ws/stream
) else (
    echo Failed to start service
    echo Check Windows Event Viewer for details
)
pause
"@
    
    # Stop service script
    $stopScript = @"
@echo off
echo Stopping LabJack Bridge Service...
sc stop $ServiceName
if %ERRORLEVEL% EQU 0 (
    echo Service stopped successfully
) else (
    echo Failed to stop service or service was not running
)
pause
"@
    
    # Status script
    $statusScript = @"
@echo off
echo Checking LabJack Bridge Service status...
sc query $ServiceName
echo.
echo Configuration file: $InstallPath\config\service_config.json
echo Log files: $InstallPath\logs
echo.
pause
"@
    
    # Uninstall script
    $uninstallScript = @"
@echo off
echo Uninstalling LabJack Bridge Service...
echo WARNING: This will remove the service and all files!
set /p confirm=Are you sure? (y/N): 
if /i "%confirm%" NEQ "y" exit /b
echo.
echo Stopping service...
sc stop $ServiceName
timeout /t 2 > nul
echo Uninstalling service...
"$PythonExe" "$InstallPath\src\labjack_bridge_service.py" remove
echo Removing firewall rules...
netsh advfirewall firewall delete rule name="LabJack Bridge Service HTTP"
netsh advfirewall firewall delete rule name="LabJack Bridge Service WebSocket"
echo Removing files...
rmdir /s /q "$InstallPath"
echo Uninstallation complete
pause
"@
    
    # PowerShell management script
    $psScript = @"
# LabJack Bridge Service Management Script

param(
    [Parameter(Mandatory=`$true)]
    [ValidateSet('start', 'stop', 'restart', 'status', 'logs')]
    [string]`$Action
)

switch (`$Action) {
    'start' {
        Write-Host "Starting LabJack Bridge Service..." -ForegroundColor Green
        Start-Service -Name "$ServiceName"
        `$service = Get-Service -Name "$ServiceName"
        Write-Host "Service Status: `$(`$service.Status)" -ForegroundColor (`$service.Status -eq 'Running' ? 'Green' : 'Red')
        if (`$service.Status -eq 'Running') {
            Write-Host "API available at: http://localhost:8080" -ForegroundColor Cyan
            Write-Host "WebSocket available at: ws://localhost:8080/ws/stream" -ForegroundColor Cyan
        }
    }
    'stop' {
        Write-Host "Stopping LabJack Bridge Service..." -ForegroundColor Yellow
        Stop-Service -Name "$ServiceName" -Force
        `$service = Get-Service -Name "$ServiceName"
        Write-Host "Service Status: `$(`$service.Status)" -ForegroundColor (`$service.Status -eq 'Stopped' ? 'Green' : 'Red')
    }
    'restart' {
        Write-Host "Restarting LabJack Bridge Service..." -ForegroundColor Yellow
        Restart-Service -Name "$ServiceName"
        `$service = Get-Service -Name "$ServiceName"
        Write-Host "Service Status: `$(`$service.Status)" -ForegroundColor (`$service.Status -eq 'Running' ? 'Green' : 'Red')
    }
    'status' {
        `$service = Get-Service -Name "$ServiceName"
        Write-Host "Service Status: `$(`$service.Status)" -ForegroundColor (`$service.Status -eq 'Running' ? 'Green' : 'Red')
        Write-Host "Configuration: $InstallPath\config\service_config.json"
        Write-Host "Log Directory: $InstallPath\logs"
        
        # Check API health
        try {
            `$response = Invoke-RestMethod -Uri "http://localhost:8080/api/health" -TimeoutSec 5
            Write-Host "API Health: `$(`$response.status)" -ForegroundColor Green
            Write-Host "Connected Devices: `$(`$response.devices_connected)" -ForegroundColor Cyan
        } catch {
            Write-Host "API Health: Not responding" -ForegroundColor Red
        }
    }
    'logs' {
        `$logDir = "$InstallPath\logs"
        if (Test-Path `$logDir) {
            `$latestLog = Get-ChildItem `$logDir -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if (`$latestLog) {
                Write-Host "Opening latest log file: `$(`$latestLog.FullName)" -ForegroundColor Cyan
                notepad.exe `$latestLog.FullName
            } else {
                Write-Host "No log files found in `$logDir" -ForegroundColor Yellow
            }
        } else {
            Write-Host "Log directory not found: `$logDir" -ForegroundColor Red
        }
    }
}
"@
    
    # Create script files
    $scripts = @{
        "start_service.bat" = $startScript
        "stop_service.bat" = $stopScript
        "service_status.bat" = $statusScript
        "uninstall_service.bat" = $uninstallScript
        "manage_service.ps1" = $psScript
    }
    
    foreach ($filename in $scripts.Keys) {
        $scriptPath = Join-Path $InstallPath $filename
        $scripts[$filename] | Out-File -FilePath $scriptPath -Encoding UTF8
        Write-Host "Created: $filename" -ForegroundColor Green
    }
}

function Test-Installation {
    param([string]$InstallPath)
    
    Write-Step "Testing Installation"
    
    try {
        # Test service status
        $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($service) {
            Write-Host "✓ Service is installed" -ForegroundColor Green
        } else {
            Write-Host "✗ Service not found" -ForegroundColor Red
            return $false
        }
        
        # Start service for testing
        Write-Host "Starting service for testing..."
        Start-Service -Name $ServiceName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 5
        
        # Test HTTP endpoint
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8080/api/health" -TimeoutSec 10
            if ($response.status -eq "healthy") {
                Write-Host "✓ HTTP API is responding" -ForegroundColor Green
            } else {
                Write-Host "✗ HTTP API returned unexpected response" -ForegroundColor Red
            }
        }
        catch {
            Write-Host "✗ HTTP API test failed: $_" -ForegroundColor Red
        }
        
        Write-Host "Installation test completed" -ForegroundColor Cyan
        return $true
    }
    catch {
        Write-Error "Error during testing: $_"
        return $false
    }
}

function Write-InstallationSummary {
    param([string]$InstallPath)
    
    Write-Step "Installation Summary"
    
    Write-Host @"

✓ LabJack Bridge Service has been installed successfully!

Installation Directory: $InstallPath
Service Name: $ServiceName

API Endpoints:
  • Health Check: http://localhost:8080/api/health
  • Device Discovery: http://localhost:8080/api/devices  
  • WebSocket Stream: ws://localhost:8080/ws/stream

Management Commands:
  • Start Service: Start-Service -Name $ServiceName
  • Stop Service: Stop-Service -Name $ServiceName
  • Service Status: Get-Service -Name $ServiceName

Management Scripts:
  • $InstallPath\start_service.bat
  • $InstallPath\stop_service.bat
  • $InstallPath\service_status.bat
  • $InstallPath\manage_service.ps1
  • $InstallPath\uninstall_service.bat

Configuration:
  • Service Config: $InstallPath\config\service_config.json
  • Log Files: $InstallPath\logs\

Next Steps:
1. Ensure LabJack LJM software is installed from labjack.com
2. Connect your LabJack device(s)
3. Start the service using the management scripts
4. Test the API endpoints

For support, check the log files in $InstallPath\logs\
"@ -ForegroundColor Green
}

# Main installation function
function Install-LabjackBridgeService {
    Write-Host "LabJack Bridge Service Installer (PowerShell)" -ForegroundColor Cyan
    Write-Host "=" * 50 -ForegroundColor Cyan
    
    # Check admin rights
    if (-not (Test-AdminRights)) {
        Write-Error "This script must be run as Administrator. Please run PowerShell as Administrator and try again."
        exit 1
    }
    
    try {
        # Create directories
        Write-Step "Creating Directories"
        $directories = @("$InstallPath", "$InstallPath\src", "$InstallPath\config", "$InstallPath\logs", "$InstallPath\data")
        foreach ($dir in $directories) {
            if (-not (Test-Path $dir)) {
                New-Item -Path $dir -ItemType Directory -Force | Out-Null
                Write-Host "Created directory: $dir" -ForegroundColor Green
            }
        }
        
        # Check Python
        Write-Step "Checking Python Installation"
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCmd) {
            throw "Python is not installed or not in PATH. Please install Python $PythonVersion or higher."
        }
        
        $pythonExePath = "C:\Users\Brigade\AppData\Local\Microsoft\WindowsApps\python.exe"
        $pythonVersion = & $pythonExePath --version 2>&1
        Write-Host "Found Python: $pythonVersion" -ForegroundColor Green
        
        # Create virtual environment
        Write-Host "Creating virtual environment..."
        $venvPath = Join-Path $InstallPath "venv"
        $pythonExe = "C:\Users\Brigade\AppData\Local\Microsoft\WindowsApps\python.exe"
        & $pythonExe -m venv $venvPath
        if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment" }
        
        # Install Python dependencies
        $pythonExe = Install-PythonRequirements $venvPath
        
        # Download LabJack LJM if requested
        if (-not $SkipLJM) {
            Download-LabjackLJM
        }
        
        # Copy service files
        Write-Step "Copying Service Files"
        $scriptDir = Split-Path -Parent $PSScriptRoot
        $sourceFiles = @(
            @{Source = "$scriptDir\src\labjack_bridge_service.py"; Dest = "$InstallPath\src\labjack_bridge_service.py"},
            @{Source = "$scriptDir\config\service_config.json"; Dest = "$InstallPath\config\service_config.json"}
        )
        
        foreach ($file in $sourceFiles) {
            if (Test-Path $file.Source) {
                Copy-Item -Path $file.Source -Destination $file.Dest -Force
                Write-Host "Copied: $(Split-Path -Leaf $file.Source)" -ForegroundColor Green
            } else {
                Write-Warning "Source file not found: $($file.Source)"
            }
        }
        
        # Install Windows service
        $serviceInstalled = Install-WindowsService $InstallPath $pythonExe
        
        if ($serviceInstalled) {
            # Configure firewall
            Configure-Firewall
            
            # Create management scripts
            Create-ManagementScripts $InstallPath $pythonExe
            
            # Test installation if requested
            if (-not $NoStart) {
                Test-Installation $InstallPath
            }
            
            # Print summary
            Write-InstallationSummary $InstallPath
            
            Write-Host "`n🎉 Installation completed successfully!" -ForegroundColor Green
        } else {
            Write-Error "Installation failed during service installation"
            exit 1
        }
    }
    catch {
        Write-Error "Installation failed: $_"
        exit 1
    }
}

# Run the installer
Install-LabjackBridgeService
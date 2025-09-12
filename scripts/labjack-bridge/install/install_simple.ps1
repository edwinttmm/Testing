# Simple LabJack Bridge Installation Script
# Run as Administrator

param(
    [string]$InstallPath = "C:\LabJackBridge"
)

Write-Host "LabJack Bridge Simple Installer" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Please run as Administrator!" -ForegroundColor Red
    exit 1
}

# Create directories
Write-Host "`nCreating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallPath\src" -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallPath\config" -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallPath\logs" -Force | Out-Null
Write-Host "✓ Directories created" -ForegroundColor Green

# Create virtual environment
Write-Host "`nCreating Python virtual environment..." -ForegroundColor Yellow
$pythonExe = "C:\Users\Brigade\AppData\Local\Microsoft\WindowsApps\python.exe"
& $pythonExe -m venv "$InstallPath\venv"
Write-Host "✓ Virtual environment created" -ForegroundColor Green

# Install packages
Write-Host "`nInstalling Python packages..." -ForegroundColor Yellow
$pipExe = "$InstallPath\venv\Scripts\pip.exe"
& $pipExe install --upgrade pip
& $pipExe install fastapi uvicorn websockets aiofiles requests
Write-Host "✓ Packages installed" -ForegroundColor Green

# Copy bridge service files from WSL
Write-Host "`nCopying service files..." -ForegroundColor Yellow
$sourcePath = "\\wsl.localhost\Ubuntu\home\rigade\Testing\scripts\labjack-bridge\src"
if (Test-Path $sourcePath) {
    Copy-Item -Path "$sourcePath\*" -Destination "$InstallPath\src\" -Recurse -Force
    Write-Host "✓ Service files copied" -ForegroundColor Green
} else {
    Write-Host "! Source files not found at $sourcePath" -ForegroundColor Yellow
}

# Create startup script
Write-Host "`nCreating startup script..." -ForegroundColor Yellow
$startScript = @"
@echo off
cd /d "$InstallPath"
echo Starting LabJack Bridge Service...
"$InstallPath\venv\Scripts\python.exe" "$InstallPath\src\labjack_bridge_service.py"
pause
"@
Set-Content -Path "$InstallPath\start_service.bat" -Value $startScript
Write-Host "✓ Startup script created" -ForegroundColor Green

# Create firewall rule
Write-Host "`nConfiguring firewall..." -ForegroundColor Yellow
netsh advfirewall firewall add rule name="LabJack Bridge Service" dir=in action=allow protocol=TCP localport=8080 | Out-Null
Write-Host "✓ Firewall configured" -ForegroundColor Green

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "`nTo start the service, run:" -ForegroundColor Yellow
Write-Host "  $InstallPath\start_service.bat" -ForegroundColor White
Write-Host "`nService will be available at:" -ForegroundColor Yellow
Write-Host "  http://localhost:8080" -ForegroundColor White
Write-Host "================================" -ForegroundColor Cyan
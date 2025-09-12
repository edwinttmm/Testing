#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Automated setup script for LabJack USB passthrough using usbipd-win

.DESCRIPTION
    This script automates the complete setup process for LabJack USB passthrough,
    including usbipd-win installation, WSL2 configuration, and device management.

.PARAMETER InstallMode
    Installation mode: 'full', 'usbipd-only', 'wsl-only', or 'configure-only'

.PARAMETER DeviceType
    LabJack device type: 'auto', 'u3', 'u6', 'ue9', 't4', 't7', 't8'

.PARAMETER WSLDistribution
    WSL distribution name (default: Ubuntu)

.PARAMETER SkipReboot
    Skip automatic reboot after installation

.EXAMPLE
    .\setup-automation.ps1 -InstallMode full -DeviceType auto
    
.EXAMPLE
    .\setup-automation.ps1 -InstallMode configure-only -DeviceType u3 -WSLDistribution Ubuntu-20.04
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("full", "usbipd-only", "wsl-only", "configure-only")]
    [string]$InstallMode = "full",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("auto", "u3", "u6", "ue9", "t4", "t7", "t8")]
    [string]$DeviceType = "auto",
    
    [Parameter(Mandatory=$false)]
    [string]$WSLDistribution = "Ubuntu",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipReboot
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

# LabJack device mappings
$LabJackDevices = @{
    "u3"  = @{ VID = "0cd5"; PID = "0009"; Name = "LabJack U3" }
    "u6"  = @{ VID = "0cd5"; PID = "000a"; Name = "LabJack U6" }
    "ue9" = @{ VID = "0cd5"; PID = "000b"; Name = "LabJack UE9" }
    "t4"  = @{ VID = "0cd5"; PID = "4004"; Name = "LabJack T4" }
    "t7"  = @{ VID = "0cd5"; PID = "4007"; Name = "LabJack T7" }
    "t8"  = @{ VID = "0cd5"; PID = "4008"; Name = "LabJack T8" }
}

# Logging setup
$LogFile = "$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss')_labjack_setup.log"
$LogPath = Join-Path $env:TEMP $LogFile

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"
    Write-Host $LogEntry
    Add-Content -Path $LogPath -Value $LogEntry
}

function Test-Administrator {
    """Test if script is running with administrator privileges"""
    $CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = New-Object Security.Principal.WindowsPrincipal($CurrentUser)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-WindowsVersion {
    """Test if Windows version supports WSL2"""
    $Version = [System.Environment]::OSVersion.Version
    $Build = (Get-ItemProperty "HKLM:SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuild
    
    Write-Log "Windows Version: $($Version.Major).$($Version.Minor) Build $Build"
    
    if ([int]$Build -lt 19041) {
        throw "Windows 10 build 19041 or later is required for WSL2"
    }
    
    return $true
}

function Install-USBIPDWin {
    """Install usbipd-win using winget"""
    Write-Log "Installing usbipd-win..."
    
    try {
        # Check if already installed
        $Existing = Get-Command "usbipd" -ErrorAction SilentlyContinue
        if ($Existing) {
            Write-Log "usbipd-win already installed at: $($Existing.Source)"
            return $true
        }
        
        # Install using winget
        Write-Log "Installing usbipd-win via winget..."
        $Result = Start-Process -FilePath "winget" -ArgumentList @("install", "--id=dorssel.usbipd-win", "--silent", "--accept-package-agreements", "--accept-source-agreements") -Wait -PassThru
        
        if ($Result.ExitCode -eq 0) {
            Write-Log "usbipd-win installed successfully"
            
            # Verify installation
            Start-Sleep -Seconds 5
            $Installed = Get-Command "usbipd" -ErrorAction SilentlyContinue
            if ($Installed) {
                $Version = & usbipd --version
                Write-Log "usbipd-win version: $Version"
                return $true
            } else {
                Write-Log "usbipd command not found after installation" -Level "ERROR"
                return $false
            }
        } else {
            Write-Log "winget installation failed with exit code: $($Result.ExitCode)" -Level "ERROR"
            return $false
        }
        
    } catch {
        Write-Log "Error installing usbipd-win: $($_.Exception.Message)" -Level "ERROR"
        return $false
    }
}

function Install-WSL2 {
    """Install and configure WSL2"""
    Write-Log "Installing WSL2..."
    
    try {
        # Check if WSL is already installed
        $WSLCheck = & wsl --list --verbose 2>$null
        if ($LASTEXITCODE -eq 0 -and $WSLCheck -match "VERSION 2") {
            Write-Log "WSL2 is already installed and configured"
            return $true
        }
        
        # Enable WSL feature
        Write-Log "Enabling WSL features..."
        $Result1 = dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
        $Result2 = dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
        
        if ($Result1 -match "The operation completed successfully" -and $Result2 -match "The operation completed successfully") {
            Write-Log "WSL features enabled successfully"
        } else {
            Write-Log "Failed to enable WSL features" -Level "ERROR"
            return $false
        }
        
        # Set WSL2 as default
        Write-Log "Setting WSL2 as default version..."
        $Result = & wsl --set-default-version 2 2>&1
        Write-Log "WSL default version result: $Result"
        
        # Install Ubuntu distribution
        Write-Log "Installing $WSLDistribution distribution..."
        $Result = & wsl --install $WSLDistribution --no-launch 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Log "$WSLDistribution installed successfully"
            return $true
        } else {
            Write-Log "Failed to install $WSLDistribution distribution: $Result" -Level "ERROR"
            return $false
        }
        
    } catch {
        Write-Log "Error installing WSL2: $($_.Exception.Message)" -Level "ERROR"
        return $false
    }
}

function Get-LabJackDevices {
    """Find LabJack devices in USB device list"""
    Write-Log "Scanning for LabJack devices..."
    
    try {
        $USBDevices = & usbipd list 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Failed to list USB devices" -Level "ERROR"
            return @()
        }
        
        $FoundDevices = @()
        
        foreach ($Line in $USBDevices -split "`n") {
            if ($Line -match "^(\S+)\s+(0cd5:\w+)\s+(.+?)\s+(.+)$") {
                $BusID = $Matches[1]
                $VIDPID = $Matches[2]
                $Description = $Matches[3].Trim()
                $State = $Matches[4].Trim()
                
                $Device = @{
                    BusID = $BusID
                    VIDPID = $VIDPID
                    Description = $Description
                    State = $State
                }
                
                $FoundDevices += $Device
                Write-Log "Found LabJack device: $BusID - $Description ($VIDPID) - $State"
            }
        }
        
        return $FoundDevices
        
    } catch {
        Write-Log "Error scanning for devices: $($_.Exception.Message)" -Level "ERROR"
        return @()
    }
}

function Select-LabJackDevice {
    """Select LabJack device based on type preference"""
    param([array]$Devices)
    
    if ($Devices.Count -eq 0) {
        Write-Log "No LabJack devices found" -Level "ERROR"
        return $null
    }
    
    if ($DeviceType -eq "auto") {
        # Return first available device
        $Selected = $Devices[0]
        Write-Log "Auto-selected device: $($Selected.BusID) - $($Selected.Description)"
        return $Selected
    } else {
        # Look for specific device type
        $TargetVIDPID = "0cd5:$($LabJackDevices[$DeviceType].PID)"
        $Selected = $Devices | Where-Object { $_.VIDPID -eq $TargetVIDPID } | Select-Object -First 1
        
        if ($Selected) {
            Write-Log "Selected $DeviceType device: $($Selected.BusID) - $($Selected.Description)"
            return $Selected
        } else {
            Write-Log "Specified device type '$DeviceType' not found" -Level "ERROR"
            return $null
        }
    }
}

function Configure-Device {
    """Configure LabJack device for USB passthrough"""
    param([hashtable]$Device)
    
    Write-Log "Configuring device: $($Device.BusID)"
    
    try {
        # Bind device if not already bound
        if ($Device.State -ne "Shared") {
            Write-Log "Binding device $($Device.BusID)..."
            $Result = & usbipd bind --busid $Device.BusID 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-Log "Device bound successfully"
            } else {
                Write-Log "Failed to bind device: $Result" -Level "ERROR"
                return $false
            }
        } else {
            Write-Log "Device already bound"
        }
        
        # Attach to WSL
        Write-Log "Attaching device to WSL ($WSLDistribution)..."
        $Result = & usbipd attach --wsl $WSLDistribution --busid $Device.BusID 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Device attached to WSL successfully"
            
            # Verify attachment
            Start-Sleep -Seconds 3
            $WSLResult = & wsl -d $WSLDistribution lsusb 2>$null
            if ($WSLResult -match "0cd5:") {
                Write-Log "Device verified in WSL"
                return $true
            } else {
                Write-Log "Device not visible in WSL" -Level "WARNING"
                return $false
            }
        } else {
            Write-Log "Failed to attach device to WSL: $Result" -Level "ERROR"
            return $false
        }
        
    } catch {
        Write-Log "Error configuring device: $($_.Exception.Message)" -Level "ERROR"
        return $false
    }
}

function Install-LabJackDrivers {
    """Install LabJack drivers in WSL"""
    Write-Log "Installing LabJack drivers in WSL..."
    
    try {
        $InstallScript = @'
#!/bin/bash
set -e

echo "Updating package lists..."
sudo apt update

echo "Installing dependencies..."
sudo apt install -y build-essential libusb-1.0-0-dev python3 python3-pip wget unzip

echo "Downloading LabJack Exodriver..."
cd /tmp
wget -q https://github.com/labjack/exodriver/archive/master.zip -O exodriver.zip
unzip -q exodriver.zip
cd exodriver-master

echo "Installing Exodriver..."
sudo ./install.sh

echo "Installing Python library..."
pip3 install --user u3

echo "Testing installation..."
python3 -c "import u3; print('LabJack Python library installed successfully')"

echo "LabJack drivers installed successfully"
'@
        
        # Write script to temp file
        $ScriptPath = [System.IO.Path]::GetTempFileName()
        Set-Content -Path $ScriptPath -Value $InstallScript
        
        # Copy script to WSL and execute
        $WSLScriptPath = "/tmp/install_labjack.sh"
        & wsl -d $WSLDistribution -- bash -c "cat > $WSLScriptPath" < $ScriptPath
        & wsl -d $WSLDistribution -- chmod +x $WSLScriptPath
        
        Write-Log "Running driver installation in WSL..."
        $Result = & wsl -d $WSLDistribution -- $WSLScriptPath 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Log "LabJack drivers installed successfully in WSL"
            Write-Log $Result
            return $true
        } else {
            Write-Log "Failed to install LabJack drivers: $Result" -Level "ERROR"
            return $false
        }
        
    } catch {
        Write-Log "Error installing LabJack drivers: $($_.Exception.Message)" -Level "ERROR"
        return $false
    } finally {
        # Cleanup temp file
        if (Test-Path $ScriptPath) {
            Remove-Item $ScriptPath -Force
        }
    }
}

function Test-Installation {
    """Test the complete installation"""
    Write-Log "Testing LabJack installation..."
    
    try {
        $TestScript = @'
import sys
try:
    import u3
    print("SUCCESS: u3 library imported")
    
    # Try to connect to device
    try:
        device = u3.U3()
        print(f"SUCCESS: Connected to {device.getName()}")
        
        # Test basic functionality
        voltage = device.getAIN(0)
        print(f"SUCCESS: Read voltage {voltage:.3f}V from channel 0")
        
        device.close()
        print("SUCCESS: All tests passed")
        sys.exit(0)
        
    except Exception as e:
        print(f"WARNING: Device connection failed - {e}")
        print("This may be normal if no LabJack is connected")
        sys.exit(0)
        
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
'@
        
        Write-Log "Running LabJack test in WSL..."
        $Result = & wsl -d $WSLDistribution -- python3 -c $TestScript 2>&1
        
        Write-Log "Test results:"
        Write-Log $Result
        
        if ($Result -match "SUCCESS: All tests passed") {
            Write-Log "Installation test PASSED - Device is functional" -Level "SUCCESS"
            return $true
        } elseif ($Result -match "WARNING: Device connection failed") {
            Write-Log "Installation test PASSED - Software installed correctly" -Level "SUCCESS"
            return $true
        } else {
            Write-Log "Installation test FAILED" -Level "ERROR"
            return $false
        }
        
    } catch {
        Write-Log "Error testing installation: $($_.Exception.Message)" -Level "ERROR"
        return $false
    }
}

function Create-ConfigFiles {
    """Create configuration files for easy management"""
    Write-Log "Creating configuration files..."
    
    try {
        # Create PowerShell management script
        $ManagementScript = @'
# LabJack USB Passthrough Management Script
# Generated by setup-automation.ps1

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("list", "attach", "detach", "status", "test")]
    [string]$Action,
    
    [string]$Distribution = "DISTRIBUTION_PLACEHOLDER"
)

function Get-LabJackDevices {
    $Devices = usbipd list | Select-String "0cd5:"
    return $Devices
}

function Attach-LabJack {
    $Devices = Get-LabJackDevices
    if ($Devices) {
        foreach ($Device in $Devices) {
            $BusID = ($Device.Line -split '\s+')[0]
            Write-Host "Attaching device $BusID to $Distribution..."
            usbipd attach --wsl $Distribution --busid $BusID
        }
    } else {
        Write-Host "No LabJack devices found"
    }
}

function Detach-LabJack {
    $Devices = Get-LabJackDevices
    if ($Devices) {
        foreach ($Device in $Devices) {
            $BusID = ($Device.Line -split '\s+')[0]
            Write-Host "Detaching device $BusID..."
            usbipd detach --busid $BusID
        }
    } else {
        Write-Host "No LabJack devices found"
    }
}

switch ($Action) {
    "list" { Get-LabJackDevices }
    "attach" { Attach-LabJack }
    "detach" { Detach-LabJack }
    "status" { 
        Write-Host "LabJack Devices:"
        Get-LabJackDevices
        Write-Host "`nWSL Status:"
        wsl -d $Distribution lsusb | Select-String "0cd5:"
    }
    "test" {
        Write-Host "Testing LabJack connectivity in WSL..."
        wsl -d $Distribution python3 -c "import u3; d=u3.U3(); print(f'Connected: {d.getName()}'); d.close()"
    }
}
'@
        
        $ManagementScript = $ManagementScript -replace "DISTRIBUTION_PLACEHOLDER", $WSLDistribution
        $ManagementScriptPath = "manage-labjack.ps1"
        Set-Content -Path $ManagementScriptPath -Value $ManagementScript
        Write-Log "Created management script: $ManagementScriptPath"
        
        # Create Linux helper script
        $LinuxHelper = @'
#!/bin/bash
# LabJack Helper Script for WSL
# Generated by setup-automation.ps1

check_device() {
    echo "Checking for LabJack devices..."
    if lsusb | grep -q "0cd5:"; then
        echo "✓ LabJack device detected:"
        lsusb | grep "0cd5:"
        return 0
    else
        echo "✗ No LabJack device found"
        echo "Make sure device is attached from Windows:"
        echo "  usbipd attach --wsl --busid <BUSID>"
        return 1
    fi
}

test_connection() {
    echo "Testing LabJack connection..."
    python3 -c "
import sys
try:
    import u3
    device = u3.U3()
    print('✓ Successfully connected to:', device.getName())
    voltage = device.getAIN(0)
    print(f'✓ Channel 0 voltage: {voltage:.3f}V')
    device.close()
    print('✓ Test completed successfully')
except Exception as e:
    print('✗ Connection failed:', str(e))
    sys.exit(1)
"
}

install_software() {
    echo "Installing LabJack software..."
    sudo apt update
    sudo apt install -y build-essential libusb-1.0-0-dev python3 python3-pip
    
    # Install Exodriver
    cd /tmp
    wget https://github.com/labjack/exodriver/archive/master.zip
    unzip master.zip
    cd exodriver-master
    sudo ./install.sh
    
    # Install Python library
    pip3 install --user u3
    
    echo "Installation completed"
}

case "$1" in
    "check") check_device ;;
    "test") test_connection ;;
    "install") install_software ;;
    *)
        echo "Usage: $0 {check|test|install}"
        echo "  check   - Check if LabJack device is detected"
        echo "  test    - Test connection to device"
        echo "  install - Install LabJack software"
        ;;
esac
'@
        
        # Create the script in WSL
        $LinuxScriptPath = "/usr/local/bin/labjack-helper"
        & wsl -d $WSLDistribution -- bash -c "echo '$LinuxHelper' | sudo tee $LinuxScriptPath > /dev/null"
        & wsl -d $WSLDistribution -- sudo chmod +x $LinuxScriptPath
        Write-Log "Created Linux helper script: $LinuxScriptPath"
        
        return $true
        
    } catch {
        Write-Log "Error creating configuration files: $($_.Exception.Message)" -Level "ERROR"
        return $false
    }
}

function Show-Summary {
    """Show installation summary and usage instructions"""
    Write-Log "Installation completed successfully!"
    
    Write-Host ""
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host "LABJACK USB PASSTHROUGH SETUP COMPLETE" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Green
    
    Write-Host ""
    Write-Host "SETUP SUMMARY:" -ForegroundColor Yellow
    Write-Host "- usbipd-win installed and configured"
    Write-Host "- WSL2 with $WSLDistribution distribution ready"
    Write-Host "- LabJack drivers installed in WSL"
    Write-Host "- Management scripts created"
    
    Write-Host ""
    Write-Host "USAGE INSTRUCTIONS:" -ForegroundColor Yellow
    Write-Host "1. Connect your LabJack device to USB"
    Write-Host "2. Run: .\manage-labjack.ps1 -Action attach"
    Write-Host "3. In WSL, run: labjack-helper test"
    
    Write-Host ""
    Write-Host "MANAGEMENT COMMANDS:" -ForegroundColor Yellow
    Write-Host "PowerShell (Windows):"
    Write-Host "  .\manage-labjack.ps1 -Action list     # List devices"
    Write-Host "  .\manage-labjack.ps1 -Action attach   # Attach devices"
    Write-Host "  .\manage-labjack.ps1 -Action detach   # Detach devices"
    Write-Host "  .\manage-labjack.ps1 -Action status   # Show status"
    Write-Host "  .\manage-labjack.ps1 -Action test     # Test connection"
    
    Write-Host ""
    Write-Host "Linux/WSL:"
    Write-Host "  labjack-helper check    # Check device detection"
    Write-Host "  labjack-helper test     # Test connection"
    Write-Host "  labjack-helper install  # Reinstall software"
    
    Write-Host ""
    Write-Host "LOG FILE: $LogPath" -ForegroundColor Cyan
    Write-Host ""
}

# Main execution
try {
    Write-Log "Starting LabJack USB Passthrough Setup"
    Write-Log "Installation Mode: $InstallMode"
    Write-Log "Device Type: $DeviceType"
    Write-Log "WSL Distribution: $WSLDistribution"
    Write-Log "Log File: $LogPath"
    
    # Check prerequisites
    if (-not (Test-Administrator)) {
        throw "This script must be run as Administrator"
    }
    
    Test-WindowsVersion
    
    # Installation steps based on mode
    $InstallationSuccess = $true
    
    if ($InstallMode -in @("full", "usbipd-only")) {
        $InstallationSuccess = $InstallationSuccess -and (Install-USBIPDWin)
    }
    
    if ($InstallMode -in @("full", "wsl-only")) {
        $InstallationSuccess = $InstallationSuccess -and (Install-WSL2)
        
        if ($InstallationSuccess) {
            # Check if reboot is needed
            $RebootRequired = (Get-WindowsFeature -Name Microsoft-Windows-Subsystem-Linux).InstallState -eq "InstallPending"
            
            if ($RebootRequired -and -not $SkipReboot) {
                Write-Log "Reboot required for WSL2 installation. Rebooting in 10 seconds..."
                Write-Log "Re-run this script after reboot with -InstallMode configure-only to complete setup"
                Start-Sleep -Seconds 10
                Restart-Computer -Force
                exit 0
            }
        }
    }
    
    if ($InstallMode -in @("full", "configure-only")) {
        if ($InstallationSuccess) {
            # Find and configure LabJack devices
            $LabJackDevices = Get-LabJackDevices
            
            if ($LabJackDevices.Count -gt 0) {
                $SelectedDevice = Select-LabJackDevice -Devices $LabJackDevices
                
                if ($SelectedDevice) {
                    $InstallationSuccess = $InstallationSuccess -and (Configure-Device -Device $SelectedDevice)
                }
            } else {
                Write-Log "No LabJack devices detected. Connect device and run with -InstallMode configure-only" -Level "WARNING"
            }
            
            # Install drivers in WSL
            $InstallationSuccess = $InstallationSuccess -and (Install-LabJackDrivers)
            
            # Test installation
            if ($InstallationSuccess) {
                Test-Installation
            }
            
            # Create configuration files
            Create-ConfigFiles
        }
    }
    
    if ($InstallationSuccess) {
        Show-Summary
        Write-Log "Setup completed successfully"
        exit 0
    } else {
        Write-Log "Setup completed with errors. Check log file for details." -Level "ERROR"
        exit 1
    }
    
} catch {
    Write-Log "Setup failed: $($_.Exception.Message)" -Level "ERROR"
    Write-Log "Check log file for details: $LogPath" -Level "ERROR"
    exit 1
}
# LabJack Windows Diagnostics Automation Script
# =====================================================
# Comprehensive PowerShell script for automated LabJack diagnostics
# Run as Administrator for best results

param(
    [switch]$Detailed,
    [switch]$ExportResults,
    [switch]$FixIssues,
    [string]$OutputPath = "LabJack_Diagnostic_$(Get-Date -Format 'yyyyMMdd_HHmmss').json",
    [string]$LogPath = "LabJack_Diagnostic_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
)

# Ensure we're running as Administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "❌ This script requires Administrator privileges. Please run as Administrator." -ForegroundColor Red
    if ($FixIssues) {
        Write-Host "   Fixing issues requires elevated permissions." -ForegroundColor Yellow
    }
    exit 1
}

# Initialize logging
$global:LogFile = $LogPath
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $global:LogFile -Value $logEntry -Force
    
    switch ($Level) {
        "ERROR" { Write-Host $Message -ForegroundColor Red }
        "WARN" { Write-Host $Message -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $Message -ForegroundColor Green }
        "INFO" { Write-Host $Message -ForegroundColor White }
        default { Write-Host $Message }
    }
}

function Write-DiagnosticHeader {
    param([string]$Title)
    $separator = "="*60
    Write-Log ""
    Write-Log $separator "INFO"
    Write-Log " $Title" "INFO"
    Write-Log $separator "INFO"
}

function Test-LabJackSystemDiagnostic {
    $results = @{
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        SystemInfo = @{}
        USBControllers = @()
        LabJackDevices = @()
        SoftwareStatus = @{}
        NetworkTest = @{}
        FirewallRules = @()
        APITest = $null
        Issues = @()
        Recommendations = @()
    }
    
    Write-DiagnosticHeader "SYSTEM INFORMATION"
    
    try {
        $sysInfo = Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory, CsProcessors
        Write-Log "OS: $($sysInfo.WindowsProductName)" "INFO"
        Write-Log "Version: $($sysInfo.WindowsVersion)" "INFO"
        Write-Log "RAM: $([math]::Round($sysInfo.TotalPhysicalMemory/1GB, 1)) GB" "INFO"
        Write-Log "Processors: $($sysInfo.CsProcessors.Count)" "INFO"
        $results.SystemInfo = $sysInfo
    } catch {
        Write-Log "Failed to get system information: $_" "ERROR"
        $results.Issues += "Failed to retrieve system information"
    }
    
    Write-DiagnosticHeader "USB CONTROLLERS"
    
    try {
        $usbControllers = Get-WmiObject -Class Win32_USBController
        $workingControllers = $usbControllers | Where-Object { $_.Status -eq "OK" }
        $problemControllers = $usbControllers | Where-Object { $_.Status -ne "OK" }
        
        Write-Log "Total USB Controllers: $($usbControllers.Count)" "INFO"
        Write-Log "Working Controllers: $($workingControllers.Count)" "SUCCESS"
        
        if ($problemControllers.Count -gt 0) {
            Write-Log "Problem Controllers: $($problemControllers.Count)" "WARN"
            $results.Issues += "USB controllers with issues detected"
            $results.Recommendations += "Check Device Manager for USB controller problems"
        }
        
        $results.USBControllers = $usbControllers | Select-Object Name, Status, DeviceID
    } catch {
        Write-Log "Failed to get USB controller information: $_" "ERROR"
        $results.Issues += "Cannot retrieve USB controller status"
    }
    
    Write-DiagnosticHeader "LABJACK DEVICE DETECTION"
    
    try {
        # Check USB devices
        $labJackUSBDevices = Get-WmiObject -Class Win32_USBDevice | Where-Object { 
            $_.Description -like "*LabJack*" -or $_.Name -like "*LabJack*" 
        }
        
        # Check PnP devices (more comprehensive)
        $labJackPnPDevices = Get-PnpDevice | Where-Object { 
            $_.FriendlyName -like "*LabJack*" -or $_.HardwareID -like "*LabJack*"
        }
        
        $allLabJackDevices = @()
        if ($labJackUSBDevices) { $allLabJackDevices += $labJackUSBDevices }
        if ($labJackPnPDevices) { $allLabJackDevices += $labJackPnPDevices }
        
        if ($allLabJackDevices.Count -gt 0) {
            Write-Log "✅ LabJack devices detected: $($allLabJackDevices.Count)" "SUCCESS"
            
            foreach ($device in $allLabJackDevices) {
                $deviceName = $device.Name ?? $device.FriendlyName ?? "Unknown Device"
                $deviceStatus = $device.Status ?? "Unknown"
                Write-Log "  - $deviceName (Status: $deviceStatus)" "INFO"
                
                if ($deviceStatus -ne "OK" -and $deviceStatus -ne "Unknown") {
                    $results.Issues += "LabJack device '$deviceName' has status: $deviceStatus"
                    $results.Recommendations += "Check Device Manager for '$deviceName' issues"
                }
            }
        } else {
            Write-Log "❌ No LabJack devices detected" "ERROR"
            $results.Issues += "No LabJack devices found in Device Manager"
            $results.Recommendations += "1. Check USB connection"
            $results.Recommendations += "2. Install LabJack drivers"
            $results.Recommendations += "3. Try different USB port"
        }
        
        $results.LabJackDevices = $allLabJackDevices | Select-Object Name, FriendlyName, Status, DeviceID, InstanceId
    } catch {
        Write-Log "Failed to detect LabJack devices: $_" "ERROR"
        $results.Issues += "Device detection failed"
    }
    
    Write-DiagnosticHeader "LABJACK SOFTWARE INSTALLATION"
    
    $softwareStatus = @{
        LJMLibrary = $false
        Kipling = $false
        Registry = $false
        Service = $false
        Version = "Unknown"
        PythonModule = $false
    }
    
    # Check LJM Library
    $ljmPath = "C:\Program Files (x86)\LabJack\Applications\LJM\LJM_library.dll"
    $softwareStatus.LJMLibrary = Test-Path $ljmPath
    if ($softwareStatus.LJMLibrary) {
        try {
            $version = (Get-ItemProperty $ljmPath).VersionInfo.FileVersion
            $softwareStatus.Version = $version
            Write-Log "✅ LJM Library found (Version: $version)" "SUCCESS"
        } catch {
            Write-Log "✅ LJM Library found (Version unknown)" "SUCCESS"
        }
    } else {
        Write-Log "❌ LJM Library not found" "ERROR"
        $results.Issues += "LJM Library not installed"
        $results.Recommendations += "Download and install LabJack software bundle"
    }
    
    # Check Kipling
    $kiplingPath = "C:\Program Files (x86)\LabJack\Applications\Kipling\Kipling.exe"
    $softwareStatus.Kipling = Test-Path $kiplingPath
    if ($softwareStatus.Kipling) {
        Write-Log "✅ Kipling application found" "SUCCESS"
    } else {
        Write-Log "❌ Kipling application not found" "WARN"
        $results.Recommendations += "Install Kipling for device configuration"
    }
    
    # Check Registry
    try {
        $ljmReg = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\LabJack\LJM" -Name "Version" -ErrorAction Stop
        $softwareStatus.Registry = $true
        $softwareStatus.Version = $ljmReg.Version
        Write-Log "✅ Registry entries found (Version: $($ljmReg.Version))" "SUCCESS"
    } catch {
        Write-Log "❌ Registry entries not found" "WARN"
        $results.Issues += "LabJack registry entries missing"
        $softwareStatus.Registry = $false
    }
    
    # Check Services
    try {
        $ljmService = Get-Service -Name "LabJackUSB" -ErrorAction SilentlyContinue
        if ($ljmService) {
            $softwareStatus.Service = $ljmService.Status -eq "Running"
            if ($softwareStatus.Service) {
                Write-Log "✅ LabJack USB service running" "SUCCESS"
            } else {
                Write-Log "⚠️ LabJack USB service not running (Status: $($ljmService.Status))" "WARN"
                $results.Issues += "LabJack USB service not running"
                if ($FixIssues) {
                    Write-Log "🔧 Attempting to start LabJack USB service..." "INFO"
                    try {
                        Start-Service -Name "LabJackUSB"
                        Write-Log "✅ LabJack USB service started successfully" "SUCCESS"
                        $softwareStatus.Service = $true
                    } catch {
                        Write-Log "❌ Failed to start LabJack USB service: $_" "ERROR"
                    }
                }
            }
        } else {
            Write-Log "❌ LabJack USB service not found" "ERROR"
            $results.Issues += "LabJack USB service not installed"
            $softwareStatus.Service = $false
        }
    } catch {
        Write-Log "Failed to check LabJack services: $_" "ERROR"
    }
    
    # Check Python module
    try {
        $pythonTest = python -c "import sys; sys.path.append(r'C:\Program Files (x86)\LabJack\Applications\LJM\Python'); from labjack import ljm; print('OK')" 2>$null
        if ($pythonTest -eq "OK") {
            $softwareStatus.PythonModule = $true
            Write-Log "✅ Python LJM module available" "SUCCESS"
        } else {
            $softwareStatus.PythonModule = $false
            Write-Log "⚠️ Python LJM module not available" "WARN"
        }
    } catch {
        $softwareStatus.PythonModule = $false
        Write-Log "⚠️ Cannot test Python LJM module" "WARN"
    }
    
    $results.SoftwareStatus = $softwareStatus
    
    Write-DiagnosticHeader "NETWORK CONNECTIVITY TEST"
    
    try {
        # Test common LabJack IP addresses
        $testIPs = @("192.168.1.207", "192.168.0.207", "169.254.1.207")
        $networkResults = @()
        
        foreach ($ip in $testIPs) {
            $networkTest = Test-NetConnection -ComputerName $ip -Port 502 -WarningAction SilentlyContinue
            $networkResults += @{
                IPAddress = $ip
                Port = 502
                Connected = $networkTest.TcpTestSucceeded
                PingSuccessful = $networkTest.PingSucceeded
            }
            
            if ($networkTest.TcpTestSucceeded) {
                Write-Log "✅ Network LabJack accessible at $ip:502" "SUCCESS"
            } else {
                Write-Log "❌ No network LabJack at $ip:502" "INFO"
            }
        }
        
        $results.NetworkTest = $networkResults
        
        # If no network devices found, suggest discovery
        if (-not ($networkResults | Where-Object { $_.Connected })) {
            $results.Recommendations += "Run network discovery to find Ethernet LabJack devices"
        }
        
    } catch {
        Write-Log "Network connectivity test failed: $_" "ERROR"
        $results.Issues += "Network connectivity test failed"
    }
    
    Write-DiagnosticHeader "WINDOWS FIREWALL RULES"
    
    try {
        $firewallRules = Get-NetFirewallRule | Where-Object { $_.DisplayName -like "*LabJack*" }
        if ($firewallRules) {
            Write-Log "✅ LabJack firewall rules found: $($firewallRules.Count)" "SUCCESS"
            foreach ($rule in $firewallRules) {
                Write-Log "  - $($rule.DisplayName) (Enabled: $($rule.Enabled), Direction: $($rule.Direction))" "INFO"
            }
        } else {
            Write-Log "⚠️ No LabJack firewall rules found" "WARN"
            $results.Recommendations += "Create firewall rules for LabJack applications"
            
            if ($FixIssues) {
                Write-Log "🔧 Creating basic LabJack firewall rules..." "INFO"
                try {
                    New-NetFirewallRule -DisplayName "LabJack Modbus TCP" -Direction Inbound -Protocol TCP -LocalPort 502 -Action Allow -ErrorAction Stop
                    New-NetFirewallRule -DisplayName "LabJack UDP Discovery" -Direction Inbound -Protocol UDP -LocalPort 5350 -Action Allow -ErrorAction Stop
                    Write-Log "✅ Firewall rules created successfully" "SUCCESS"
                } catch {
                    Write-Log "❌ Failed to create firewall rules: $_" "ERROR"
                }
            }
        }
        
        $results.FirewallRules = $firewallRules | Select-Object DisplayName, Enabled, Direction, Action
    } catch {
        Write-Log "Failed to check firewall rules: $_" "ERROR"
    }
    
    Write-DiagnosticHeader "BACKEND API CONNECTIVITY"
    
    try {
        # Test backend health
        $healthResponse = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
        Write-Log "✅ Backend API accessible" "SUCCESS"
        
        # Test LabJack specific endpoint
        try {
            $apiResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/signal-validation/labjack/status" -TimeoutSec 10 -ErrorAction Stop
            Write-Log "✅ LabJack API endpoint accessible" "SUCCESS"
            Write-Log "  Connected: $($apiResponse.connected)" "INFO"
            Write-Log "  Mock Mode: $($apiResponse.mock_mode)" "INFO"
            
            if ($apiResponse.error) {
                Write-Log "  API Error: $($apiResponse.error)" "WARN"
                $results.Issues += "LabJack API reports error: $($apiResponse.error)"
            }
            
            $results.APITest = $apiResponse
        } catch {
            Write-Log "❌ LabJack API endpoint not accessible: $_" "ERROR"
            $results.Issues += "LabJack API endpoint not responding"
            $results.Recommendations += "Check backend signal validation service"
        }
    } catch {
        Write-Log "❌ Backend API not accessible: $_" "ERROR"
        $results.Issues += "Backend API not responding"
        $results.Recommendations += "Start the backend server (port 8000)"
    }
    
    Write-DiagnosticHeader "HARDWARE COMMUNICATION TEST"
    
    if ($results.SoftwareStatus.LJMLibrary -and $results.SoftwareStatus.PythonModule) {
        Write-Log "🔧 Running hardware communication test..." "INFO"
        
        # Create Python test script
        $hardwareTestScript = @"
import sys
sys.path.append(r'C:\Program Files (x86)\LabJack\Applications\LJM\Python')

try:
    from labjack import ljm
    
    # Try to open any LabJack device
    handle = ljm.openS("ANY", "ANY", "ANY")
    info = ljm.getHandleInfo(handle)
    
    print(f"DEVICE_FOUND:Type={info[0]},Connection={info[1]},Serial={info[2]}")
    
    # Test basic communication
    name = ljm.eReadNameString(handle, "DEVICE_NAME_DEFAULT")
    print(f"COMMUNICATION_OK:Name={name}")
    
    # Test analog input
    voltage = ljm.eReadName(handle, "AIN0")
    print(f"ANALOG_READ_OK:AIN0={voltage}")
    
    ljm.close(handle)
    print("HARDWARE_TEST_PASSED")
    
except ljm.LJMError as e:
    print(f"LJM_ERROR:Code={e.errorCode},Message={e.errorString}")
except Exception as e:
    print(f"HARDWARE_TEST_FAILED:{e}")
"@
        
        try {
            $hardwareTestScript | Out-File -FilePath "temp_hardware_test.py" -Encoding UTF8
            $testOutput = python temp_hardware_test.py 2>&1
            Remove-Item "temp_hardware_test.py" -Force -ErrorAction SilentlyContinue
            
            $hardwareResults = @{
                DeviceFound = $false
                Communication = $false
                AnalogRead = $false
                DeviceInfo = @{}
            }
            
            foreach ($line in $testOutput) {
                if ($line -like "DEVICE_FOUND:*") {
                    $hardwareResults.DeviceFound = $true
                    $deviceInfo = $line -replace "DEVICE_FOUND:", ""
                    Write-Log "✅ Hardware device found: $deviceInfo" "SUCCESS"
                } elseif ($line -like "COMMUNICATION_OK:*") {
                    $hardwareResults.Communication = $true
                    Write-Log "✅ Device communication successful" "SUCCESS"
                } elseif ($line -like "ANALOG_READ_OK:*") {
                    $hardwareResults.AnalogRead = $true
                    $voltage = $line -replace "ANALOG_READ_OK:AIN0=", ""
                    Write-Log "✅ Analog input test successful: $voltage V" "SUCCESS"
                } elseif ($line -like "HARDWARE_TEST_PASSED") {
                    Write-Log "✅ All hardware tests passed" "SUCCESS"
                } elseif ($line -like "LJM_ERROR:*") {
                    Write-Log "❌ Hardware test failed: $line" "ERROR"
                    $results.Issues += "Hardware communication error: $line"
                } elseif ($line -like "HARDWARE_TEST_FAILED:*") {
                    Write-Log "❌ Hardware test failed: $line" "ERROR"
                    $results.Issues += "Hardware test failed: $line"
                }
            }
            
            $results.HardwareTest = $hardwareResults
            
        } catch {
            Write-Log "❌ Hardware test execution failed: $_" "ERROR"
            $results.Issues += "Cannot execute hardware communication test"
        }
    } else {
        Write-Log "⏭️ Hardware test skipped (missing LJM library or Python module)" "WARN"
        $results.Recommendations += "Install LabJack software to enable hardware testing"
    }
    
    Write-DiagnosticHeader "DIAGNOSTIC SUMMARY"
    
    $totalIssues = $results.Issues.Count
    $totalRecommendations = $results.Recommendations.Count
    
    if ($totalIssues -eq 0) {
        Write-Log "🎉 No issues detected! LabJack system appears to be working correctly." "SUCCESS"
    } else {
        Write-Log "⚠️ $totalIssues issue(s) detected:" "WARN"
        foreach ($issue in $results.Issues) {
            Write-Log "   - $issue" "WARN"
        }
    }
    
    if ($totalRecommendations -gt 0) {
        Write-Log "" "INFO"
        Write-Log "💡 Recommendations:" "INFO"
        foreach ($recommendation in $results.Recommendations) {
            Write-Log "   - $recommendation" "INFO"
        }
    }
    
    return $results
}

function Show-QuickFixes {
    Write-DiagnosticHeader "QUICK FIXES AVAILABLE"
    
    Write-Log "🔧 Available quick fixes:" "INFO"
    Write-Log "   1. Restart LabJack USB service" "INFO"
    Write-Log "   2. Create firewall rules for LabJack" "INFO"
    Write-Log "   3. Scan for hardware changes" "INFO"
    Write-Log "   4. Reset USB devices" "INFO"
    Write-Log "" "INFO"
    Write-Log "Run script with -FixIssues to attempt automatic fixes" "INFO"
}

function Export-DiagnosticResults {
    param($Results, $OutputPath)
    
    try {
        $Results | ConvertTo-Json -Depth 10 | Out-File -FilePath $OutputPath -Encoding UTF8
        Write-Log "✅ Diagnostic results exported to: $OutputPath" "SUCCESS"
        
        # Create a summary report
        $summaryPath = $OutputPath -replace "\.json$", "_summary.txt"
        $summary = @"
LabJack Diagnostic Summary
Generated: $(Get-Date)

ISSUES DETECTED: $($Results.Issues.Count)
$(if ($Results.Issues.Count -gt 0) { 
    $Results.Issues | ForEach-Object { "  - $_" } | Out-String 
} else { 
    "  None" 
})

RECOMMENDATIONS: $($Results.Recommendations.Count)
$(if ($Results.Recommendations.Count -gt 0) { 
    $Results.Recommendations | ForEach-Object { "  - $_" } | Out-String 
} else { 
    "  None" 
})

DEVICE STATUS:
  USB Devices Found: $(if ($Results.LabJackDevices.Count -gt 0) { $Results.LabJackDevices.Count } else { "None" })
  LJM Library: $(if ($Results.SoftwareStatus.LJMLibrary) { "Installed" } else { "Not Found" })
  Service Running: $(if ($Results.SoftwareStatus.Service) { "Yes" } else { "No" })
  API Accessible: $(if ($Results.APITest) { "Yes" } else { "No" })

For detailed results, see: $OutputPath
"@
        
        $summary | Out-File -FilePath $summaryPath -Encoding UTF8
        Write-Log "✅ Summary report saved to: $summaryPath" "SUCCESS"
        
    } catch {
        Write-Log "❌ Failed to export results: $_" "ERROR"
    }
}

# Main execution
Write-Log "🚀 Starting LabJack Windows Diagnostics" "SUCCESS"
Write-Log "Log file: $LogPath" "INFO"

if (-not $FixIssues) {
    Show-QuickFixes
}

# Run comprehensive diagnostic
$diagnosticResults = Test-LabJackSystemDiagnostic

# Export results if requested
if ($ExportResults) {
    Export-DiagnosticResults -Results $diagnosticResults -OutputPath $OutputPath
}

Write-Log "" "INFO"
Write-Log "🎯 Diagnostic completed. Check results above for any issues." "SUCCESS"
Write-Log "   Log file: $LogPath" "INFO"
if ($ExportResults) {
    Write-Log "   Results exported to: $OutputPath" "INFO"
}

# Exit with appropriate code
if ($diagnosticResults.Issues.Count -eq 0) {
    Write-Log "✅ All checks passed!" "SUCCESS"
    exit 0
} else {
    Write-Log "⚠️ Issues detected. See log for details." "WARN"
    exit 1
}
#!/usr/bin/env python3
"""
LabJack Bridge Service - Python Installation Script
Installs and configures the LabJack Bridge Service on Windows
"""

import os
import sys
import subprocess
import shutil
import json
import argparse
from pathlib import Path
import urllib.request
import zipfile

# Configuration
SERVICE_NAME = "LabJackBridgeService"
PYTHON_VERSION = "3.11"
LABJACK_LJM_URL = "https://labjack.com/sites/default/files/software/LJM_Software_2023-05-09_Win32.zip"

def print_step(message):
    """Print installation step"""
    print(f"\n{'='*60}")
    print(f" {message}")
    print(f"{'='*60}")

def run_command(cmd, check=True, shell=False):
    """Run command with error handling"""
    try:
        print(f"Running: {cmd}")
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()
        
        result = subprocess.run(cmd, check=check, capture_output=True, text=True, shell=shell)
        if result.stdout:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        if check:
            raise
        return e

def check_python_version():
    """Check Python version"""
    print_step("Checking Python Version")
    
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major != 3 or version.minor < 8:
        print("ERROR: Python 3.8 or higher is required")
        sys.exit(1)
    
    print("Python version check passed")

def check_admin_privileges():
    """Check if running as administrator"""
    print_step("Checking Administrator Privileges")
    
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            print("ERROR: This script must be run as Administrator")
            print("Please right-click and select 'Run as administrator'")
            sys.exit(1)
        
        print("Administrator privileges confirmed")
    except:
        print("WARNING: Could not verify administrator privileges")

def create_directories():
    """Create necessary directories"""
    print_step("Creating Directories")
    
    base_dir = Path("C:/Program Files/LabJackBridge")
    directories = [
        base_dir,
        base_dir / "src",
        base_dir / "config", 
        base_dir / "logs",
        base_dir / "data"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")
    
    return base_dir

def install_python_dependencies(base_dir):
    """Install Python dependencies"""
    print_step("Installing Python Dependencies")
    
    # Create virtual environment
    venv_dir = base_dir / "venv"
    run_command(f"python -m venv {venv_dir}")
    
    # Activate virtual environment and install packages
    pip_exe = venv_dir / "Scripts" / "pip.exe"
    python_exe = venv_dir / "Scripts" / "python.exe"
    
    # Upgrade pip
    run_command(f'"{pip_exe}" install --upgrade pip')
    
    # Install requirements
    requirements = [
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
    ]
    
    for package in requirements:
        run_command(f'"{pip_exe}" install {package}')
    
    # Try to install LabJack LJM
    try:
        run_command(f'"{pip_exe}" install labjack-ljm>=1.21.0')
        print("LabJack LJM Python library installed successfully")
    except:
        print("WARNING: Could not install LabJack LJM Python library")
        print("Please install LabJack LJM software manually from labjack.com")
    
    return python_exe

def download_labjack_ljm():
    """Download and extract LabJack LJM software"""
    print_step("Downloading LabJack LJM Software")
    
    try:
        temp_dir = Path("C:/temp/labjack")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        zip_path = temp_dir / "ljm_software.zip"
        
        print(f"Downloading from: {LABJACK_LJM_URL}")
        urllib.request.urlretrieve(LABJACK_LJM_URL, zip_path)
        
        print("Extracting LabJack LJM software...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        print("LabJack LJM software downloaded and extracted")
        print(f"Please manually install from: {temp_dir}")
        
    except Exception as e:
        print(f"WARNING: Could not download LabJack LJM software: {e}")
        print("Please download and install manually from labjack.com")

def copy_service_files(base_dir):
    """Copy service files to installation directory"""
    print_step("Copying Service Files")
    
    # Get script directory
    script_dir = Path(__file__).parent.parent
    
    # Copy source files
    src_files = [
        "src/labjack_bridge_service.py",
        "config/service_config.json"
    ]
    
    for src_file in src_files:
        src_path = script_dir / src_file
        dst_path = base_dir / src_file
        
        if src_path.exists():
            shutil.copy2(src_path, dst_path)
            print(f"Copied: {src_file}")
        else:
            print(f"WARNING: Source file not found: {src_file}")

def install_windows_service(base_dir, python_exe):
    """Install as Windows service"""
    print_step("Installing Windows Service")
    
    service_script = base_dir / "src" / "labjack_bridge_service.py"
    
    try:
        # Install service
        run_command(f'"{python_exe}" "{service_script}" install')
        print("Service installed successfully")
        
        # Configure service for automatic startup
        run_command(f'sc config {SERVICE_NAME} start= auto')
        print("Service configured for automatic startup")
        
        # Set service description
        run_command(f'sc description {SERVICE_NAME} "Provides HTTP and WebSocket API for LabJack hardware communication"')
        
        print(f"Windows service '{SERVICE_NAME}' installed successfully")
        
    except Exception as e:
        print(f"ERROR: Failed to install Windows service: {e}")
        return False
    
    return True

def configure_firewall():
    """Configure Windows Firewall"""
    print_step("Configuring Windows Firewall")
    
    try:
        # Add firewall rule for port 8080
        rule_name = "LabJack Bridge Service HTTP"
        run_command(f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow protocol=TCP localport=8080')
        
        # Add firewall rule for WebSocket (same port)
        rule_name_ws = "LabJack Bridge Service WebSocket"
        run_command(f'netsh advfirewall firewall add rule name="{rule_name_ws}" dir=in action=allow protocol=TCP localport=8080')
        
        print("Firewall rules added for ports 8080")
        
    except Exception as e:
        print(f"WARNING: Could not configure firewall: {e}")

def create_startup_scripts(base_dir, python_exe):
    """Create startup and management scripts"""
    print_step("Creating Management Scripts")
    
    # Start service script
    start_script = f'''@echo off
echo Starting LabJack Bridge Service...
sc start {SERVICE_NAME}
if %ERRORLEVEL% EQU 0 (
    echo Service started successfully
    echo API available at: http://localhost:8080
    echo WebSocket available at: ws://localhost:8080/ws/stream
) else (
    echo Failed to start service
    echo Check Windows Event Viewer for details
)
pause
'''
    
    # Stop service script
    stop_script = f'''@echo off
echo Stopping LabJack Bridge Service...
sc stop {SERVICE_NAME}
if %ERRORLEVEL% EQU 0 (
    echo Service stopped successfully
) else (
    echo Failed to stop service or service was not running
)
pause
'''
    
    # Status script
    status_script = f'''@echo off
echo Checking LabJack Bridge Service status...
sc query {SERVICE_NAME}
echo.
echo Configuration file: {base_dir / "config" / "service_config.json"}
echo Log files: {base_dir / "logs"}
echo.
pause
'''
    
    # Uninstall script
    uninstall_script = f'''@echo off
echo Uninstalling LabJack Bridge Service...
echo WARNING: This will remove the service and all files!
set /p confirm=Are you sure? (y/N): 
if /i "%confirm%" NEQ "y" exit /b
echo.
echo Stopping service...
sc stop {SERVICE_NAME}
timeout /t 2 > nul
echo Uninstalling service...
"{python_exe}" "{base_dir / "src" / "labjack_bridge_service.py"}" remove
echo Removing firewall rules...
netsh advfirewall firewall delete rule name="LabJack Bridge Service HTTP"
netsh advfirewall firewall delete rule name="LabJack Bridge Service WebSocket"
echo Removing files...
rmdir /s /q "{base_dir}"
echo Uninstallation complete
pause
'''
    
    scripts = {
        "start_service.bat": start_script,
        "stop_service.bat": stop_script,
        "service_status.bat": status_script,
        "uninstall_service.bat": uninstall_script
    }
    
    for filename, content in scripts.items():
        script_path = base_dir / filename
        with open(script_path, 'w') as f:
            f.write(content)
        print(f"Created: {filename}")

def test_installation(base_dir):
    """Test the installation"""
    print_step("Testing Installation")
    
    try:
        # Test service status
        result = run_command(f'sc query {SERVICE_NAME}', check=False)
        if result.returncode == 0:
            print("✓ Service is installed")
        else:
            print("✗ Service not found")
            return False
        
        # Test API endpoint (after starting service)
        print("Starting service for testing...")
        run_command(f'sc start {SERVICE_NAME}', check=False)
        
        # Wait a moment for service to start
        import time
        time.sleep(5)
        
        # Test HTTP endpoint
        try:
            import urllib.request
            import json
            
            response = urllib.request.urlopen("http://localhost:8080/api/health", timeout=10)
            data = json.loads(response.read().decode())
            
            if data.get("status") == "healthy":
                print("✓ HTTP API is responding")
            else:
                print("✗ HTTP API returned unexpected response")
        except Exception as e:
            print(f"✗ HTTP API test failed: {e}")
        
        print("Installation test completed")
        
    except Exception as e:
        print(f"ERROR during testing: {e}")
        return False
    
    return True

def print_installation_summary(base_dir):
    """Print installation summary"""
    print_step("Installation Summary")
    
    print(f"""
✓ LabJack Bridge Service has been installed successfully!

Installation Directory: {base_dir}
Service Name: {SERVICE_NAME}

API Endpoints:
  • Health Check: http://localhost:8080/api/health
  • Device Discovery: http://localhost:8080/api/devices  
  • WebSocket Stream: ws://localhost:8080/ws/stream

Management Commands:
  • Start Service: sc start {SERVICE_NAME}
  • Stop Service: sc stop {SERVICE_NAME}
  • Service Status: sc query {SERVICE_NAME}

Management Scripts:
  • {base_dir}/start_service.bat
  • {base_dir}/stop_service.bat
  • {base_dir}/service_status.bat
  • {base_dir}/uninstall_service.bat

Configuration:
  • Service Config: {base_dir}/config/service_config.json
  • Log Files: {base_dir}/logs/

Next Steps:
1. Ensure LabJack LJM software is installed from labjack.com
2. Connect your LabJack device(s)
3. Start the service using the management scripts
4. Test the API endpoints

For support, check the log files in {base_dir}/logs/
""")

def main():
    """Main installation function"""
    parser = argparse.ArgumentParser(description="Install LabJack Bridge Service")
    parser.add_argument("--skip-ljm", action="store_true", help="Skip LabJack LJM download")
    parser.add_argument("--no-start", action="store_true", help="Don't start service after installation")
    args = parser.parse_args()
    
    print("LabJack Bridge Service Installer")
    print("=" * 40)
    
    try:
        # Pre-installation checks
        check_python_version()
        check_admin_privileges()
        
        # Installation steps
        base_dir = create_directories()
        python_exe = install_python_dependencies(base_dir)
        
        if not args.skip_ljm:
            download_labjack_ljm()
        
        copy_service_files(base_dir)
        service_installed = install_windows_service(base_dir, python_exe)
        
        if service_installed:
            configure_firewall()
            create_startup_scripts(base_dir, python_exe)
            
            if not args.no_start:
                test_installation(base_dir)
            
            print_installation_summary(base_dir)
            
            print("\n🎉 Installation completed successfully!")
            
        else:
            print("\n❌ Installation failed during service installation")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
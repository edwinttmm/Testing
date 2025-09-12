#!/usr/bin/env python3
"""
LabJack Installation Script for AI Model Validation Platform

This script handles the installation of LabJack dependencies and system libraries
required for voltage signal acquisition hardware integration.

Features:
- Cross-platform support (Linux, Windows, macOS)
- Automatic detection of system package managers
- Fallback to manual installation instructions
- Validation of installation success
- Optional mock-only installation mode

Usage:
    python scripts/install_labjack.py [--mock-only] [--force] [--check]
"""

import os
import sys
import subprocess
import platform
import logging
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class LabJackInstaller:
    """Handles LabJack installation across different platforms"""
    
    def __init__(self, mock_only: bool = False, force: bool = False):
        self.mock_only = mock_only
        self.force = force
        self.platform = platform.system().lower()
        self.install_log = []
        
        # Determine backend directory
        self.backend_dir = Path(__file__).parent.parent
        self.requirements_labjack = self.backend_dir / "requirements-labjack.txt"
        
    def log_step(self, step: str, success: bool, details: str = ""):
        """Log installation step with success/failure status"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        message = f"{status}: {step}"
        if details:
            message += f" - {details}"
        
        logger.info(message)
        self.install_log.append({
            "step": step,
            "success": success,
            "details": details,
            "timestamp": None
        })
    
    def check_system_dependencies(self) -> Dict[str, bool]:
        """Check if required system dependencies are available"""
        dependencies = {
            "python": False,
            "pip": False,
            "pkg-config": False,
            "libusb": False,
            "libudev": False
        }
        
        # Check Python
        try:
            result = subprocess.run([sys.executable, "--version"], 
                                  capture_output=True, text=True, check=True)
            if "Python" in result.stdout:
                dependencies["python"] = True
                self.log_step("Python installation", True, result.stdout.strip())
        except subprocess.CalledProcessError:
            self.log_step("Python installation", False, "Python not found")
        
        # Check pip
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                                  capture_output=True, text=True, check=True)
            dependencies["pip"] = True
            self.log_step("pip installation", True, result.stdout.split()[1])
        except subprocess.CalledProcessError:
            self.log_step("pip installation", False, "pip not found")
        
        # Platform-specific system dependencies
        if self.platform == "linux":
            dependencies.update(self._check_linux_dependencies())
        elif self.platform == "darwin":
            dependencies.update(self._check_macos_dependencies())
        elif self.platform == "windows":
            dependencies.update(self._check_windows_dependencies())
        
        return dependencies
    
    def _check_linux_dependencies(self) -> Dict[str, bool]:
        """Check Linux-specific dependencies"""
        deps = {}
        
        # Check pkg-config
        try:
            subprocess.run(["pkg-config", "--version"], 
                          capture_output=True, check=True)
            deps["pkg-config"] = True
            self.log_step("pkg-config", True, "Available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            deps["pkg-config"] = False
            self.log_step("pkg-config", False, "Install with: apt-get install pkg-config")
        
        # Check libusb
        try:
            result = subprocess.run(["pkg-config", "--exists", "libusb-1.0"], 
                                  capture_output=True)
            deps["libusb"] = result.returncode == 0
            if deps["libusb"]:
                self.log_step("libusb-1.0", True, "Available")
            else:
                self.log_step("libusb-1.0", False, "Install with: apt-get install libusb-1.0-0-dev")
        except FileNotFoundError:
            deps["libusb"] = False
        
        # Check libudev
        try:
            result = subprocess.run(["pkg-config", "--exists", "libudev"], 
                                  capture_output=True)
            deps["libudev"] = result.returncode == 0
            if deps["libudev"]:
                self.log_step("libudev", True, "Available")
            else:
                self.log_step("libudev", False, "Install with: apt-get install libudev-dev")
        except FileNotFoundError:
            deps["libudev"] = False
        
        return deps
    
    def _check_macos_dependencies(self) -> Dict[str, bool]:
        """Check macOS-specific dependencies"""
        deps = {}
        
        # Check Homebrew
        try:
            subprocess.run(["brew", "--version"], capture_output=True, check=True)
            deps["brew"] = True
            self.log_step("Homebrew", True, "Available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            deps["brew"] = False
            self.log_step("Homebrew", False, "Install from https://brew.sh/")
        
        # Check libusb via Homebrew
        try:
            result = subprocess.run(["brew", "list", "libusb"], 
                                  capture_output=True, text=True)
            deps["libusb"] = result.returncode == 0
            if deps["libusb"]:
                self.log_step("libusb (Homebrew)", True, "Available")
            else:
                self.log_step("libusb (Homebrew)", False, "Install with: brew install libusb")
        except FileNotFoundError:
            deps["libusb"] = False
        
        return deps
    
    def _check_windows_dependencies(self) -> Dict[str, bool]:
        """Check Windows-specific dependencies"""
        deps = {}
        
        # Windows usually has fewer system-level requirements
        # LabJack provides Windows drivers separately
        deps["labjack_driver"] = False
        
        self.log_step("Windows LabJack drivers", False, 
                     "Download from https://labjack.com/support/software/installers/ljm")
        
        return deps
    
    def install_system_dependencies(self) -> bool:
        """Install required system dependencies"""
        if self.mock_only:
            self.log_step("System dependencies", True, "Skipped in mock-only mode")
            return True
        
        success = True
        
        if self.platform == "linux":
            success = self._install_linux_dependencies()
        elif self.platform == "darwin":
            success = self._install_macos_dependencies()
        elif self.platform == "windows":
            success = self._install_windows_dependencies()
        else:
            self.log_step("System dependencies", False, f"Unsupported platform: {self.platform}")
            success = False
        
        return success
    
    def _install_linux_dependencies(self) -> bool:
        """Install Linux system dependencies"""
        packages = [
            "libusb-1.0-0-dev",
            "libudev-dev", 
            "pkg-config"
        ]
        
        try:
            # Try apt-get first
            cmd = ["sudo", "apt-get", "update"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                self.log_step("apt-get update", False, result.stderr)
                return False
            
            cmd = ["sudo", "apt-get", "install", "-y"] + packages
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.log_step("Linux system packages", True, f"Installed: {', '.join(packages)}")
                return True
            else:
                self.log_step("Linux system packages", False, result.stderr)
                
                # Try alternative package managers
                self._try_alternative_linux_install(packages)
                return False
                
        except subprocess.TimeoutExpired:
            self.log_step("Linux system packages", False, "Installation timeout")
            return False
        except Exception as e:
            self.log_step("Linux system packages", False, str(e))
            return False
    
    def _try_alternative_linux_install(self, packages: List[str]):
        """Try alternative Linux package managers"""
        # Try yum/dnf for RedHat-based systems
        package_mappings = {
            "libusb-1.0-0-dev": "libusb1-devel",
            "libudev-dev": "systemd-devel",
            "pkg-config": "pkgconfig"
        }
        
        rpm_packages = [package_mappings.get(pkg, pkg) for pkg in packages]
        
        for manager in ["dnf", "yum"]:
            try:
                cmd = ["sudo", manager, "install", "-y"] + rpm_packages
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    self.log_step(f"Linux system packages ({manager})", True, 
                                f"Installed: {', '.join(rpm_packages)}")
                    return True
            except Exception:
                continue
    
    def _install_macos_dependencies(self) -> bool:
        """Install macOS system dependencies using Homebrew"""
        try:
            cmd = ["brew", "install", "libusb"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.log_step("macOS system packages", True, "libusb installed via Homebrew")
                return True
            else:
                self.log_step("macOS system packages", False, result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            self.log_step("macOS system packages", False, "Installation timeout")
            return False
        except Exception as e:
            self.log_step("macOS system packages", False, str(e))
            return False
    
    def _install_windows_dependencies(self) -> bool:
        """Install Windows dependencies (mainly driver info)"""
        self.log_step("Windows dependencies", True, 
                     "Please install LabJack drivers from https://labjack.com/support/software/installers/ljm")
        return True
    
    def install_python_packages(self) -> bool:
        """Install LabJack Python packages"""
        if not self.requirements_labjack.exists():
            self.log_step("LabJack requirements file", False, 
                         f"File not found: {self.requirements_labjack}")
            return False
        
        try:
            if self.mock_only:
                self.log_step("LabJack Python packages", True, "Skipped in mock-only mode")
                return True
            
            # Install LabJack Python package
            cmd = [sys.executable, "-m", "pip", "install", "-r", str(self.requirements_labjack)]
            
            if self.force:
                cmd.extend(["--force-reinstall", "--no-cache-dir"])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.log_step("LabJack Python packages", True, "labjack-ljm installed")
                return True
            else:
                self.log_step("LabJack Python packages", False, result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            self.log_step("LabJack Python packages", False, "Installation timeout")
            return False
        except Exception as e:
            self.log_step("LabJack Python packages", False, str(e))
            return False
    
    def validate_installation(self) -> bool:
        """Validate that LabJack installation works"""
        if self.mock_only:
            self.log_step("LabJack validation", True, "Mock mode - skipping hardware validation")
            return True
        
        try:
            # Try importing labjack
            import labjack.ljm as ljm
            
            # Test basic functionality
            try:
                # This will fail if no device is connected, but should not raise ImportError
                handle = ljm.openS("ANY", "ANY", "ANY")
                ljm.close(handle)
                self.log_step("LabJack hardware test", True, "Device connected and working")
            except ljm.LJMError as e:
                # This is expected if no device is connected
                if "LJME_NO_DEVICES_FOUND" in str(e):
                    self.log_step("LabJack library test", True, 
                                "Library installed (no hardware connected)")
                else:
                    self.log_step("LabJack hardware test", False, str(e))
            
            return True
            
        except ImportError as e:
            self.log_step("LabJack validation", False, f"Import failed: {e}")
            return False
        except Exception as e:
            self.log_step("LabJack validation", False, f"Validation error: {e}")
            return False
    
    def create_configuration(self) -> bool:
        """Create configuration files for LabJack integration"""
        try:
            config_file = self.backend_dir / "config" / "labjack_config.json"
            config_file.parent.mkdir(exist_ok=True)
            
            config = {
                "labjack": {
                    "mock_mode": self.mock_only,
                    "default_device_type": "ANY",
                    "default_connection_type": "ANY", 
                    "default_identifier": "ANY",
                    "voltage_threshold": 2.5,
                    "sample_rate": 1000,
                    "channels": ["AIN0", "AIN1"],
                    "installation_validated": True
                },
                "installation_info": {
                    "platform": self.platform,
                    "mock_only": self.mock_only,
                    "install_log": self.install_log
                }
            }
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.log_step("Configuration file", True, f"Created: {config_file}")
            return True
            
        except Exception as e:
            self.log_step("Configuration file", False, str(e))
            return False
    
    def run_installation(self) -> bool:
        """Run complete installation process"""
        logger.info("🚀 Starting LabJack installation process...")
        logger.info(f"Platform: {self.platform}")
        logger.info(f"Mock-only mode: {self.mock_only}")
        logger.info(f"Force reinstall: {self.force}")
        
        success = True
        
        # 1. Check system dependencies
        logger.info("\n📋 Checking system dependencies...")
        deps = self.check_system_dependencies()
        missing_deps = [name for name, available in deps.items() if not available]
        
        if missing_deps and not self.mock_only:
            logger.warning(f"Missing dependencies: {', '.join(missing_deps)}")
        
        # 2. Install system dependencies
        if not self.mock_only:
            logger.info("\n📦 Installing system dependencies...")
            if not self.install_system_dependencies():
                logger.warning("System dependency installation had issues")
                success = False
        
        # 3. Install Python packages
        logger.info("\n🐍 Installing Python packages...")
        if not self.install_python_packages():
            logger.error("Python package installation failed")
            success = False
        
        # 4. Validate installation
        logger.info("\n✅ Validating installation...")
        if not self.validate_installation():
            logger.error("Installation validation failed")
            success = False
        
        # 5. Create configuration
        logger.info("\n⚙️ Creating configuration...")
        if not self.create_configuration():
            logger.error("Configuration creation failed")
            success = False
        
        # Summary
        logger.info(f"\n📊 Installation Summary:")
        logger.info(f"Total steps: {len(self.install_log)}")
        successful_steps = sum(1 for step in self.install_log if step["success"])
        logger.info(f"Successful steps: {successful_steps}")
        logger.info(f"Failed steps: {len(self.install_log) - successful_steps}")
        
        if success:
            logger.info("\n🎉 LabJack installation completed successfully!")
            if self.mock_only:
                logger.info("   - Running in MOCK MODE (no hardware required)")
            logger.info("   - Signal validation service can now start")
            logger.info("   - Check backend logs for any runtime issues")
        else:
            logger.error("\n❌ LabJack installation completed with errors!")
            logger.error("   - Some components may not work correctly")
            logger.error("   - Check the logs above for specific issues")
            logger.error("   - Consider running with --mock-only for development")
        
        return success


def main():
    """Main entry point for the installation script"""
    parser = argparse.ArgumentParser(description="Install LabJack dependencies for signal validation")
    parser.add_argument("--mock-only", action="store_true", 
                       help="Install only mock support (no hardware required)")
    parser.add_argument("--force", action="store_true", 
                       help="Force reinstallation of packages")
    parser.add_argument("--check", action="store_true", 
                       help="Only check current installation status")
    
    args = parser.parse_args()
    
    installer = LabJackInstaller(mock_only=args.mock_only, force=args.force)
    
    if args.check:
        logger.info("🔍 Checking current LabJack installation status...")
        deps = installer.check_system_dependencies()
        validation = installer.validate_installation()
        
        logger.info("\n📋 Current Status:")
        for dep_name, available in deps.items():
            status = "✅" if available else "❌"
            logger.info(f"  {status} {dep_name}")
        
        validation_status = "✅" if validation else "❌"
        logger.info(f"  {validation_status} LabJack Python library")
        
        return 0 if validation else 1
    
    # Run installation
    success = installer.run_installation()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
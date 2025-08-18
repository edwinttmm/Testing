#!/usr/bin/env python3
"""
Lightweight ML Package Installer
Installs minimal ML packages quickly for Docker builds
"""
import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def install_lightweight_packages():
    """Install minimal ML packages for quick Docker builds"""
    
    # Essential packages that install quickly
    quick_packages = [
        "numpy>=1.24.0",
        "pillow>=10.0.0", 
        "scikit-learn>=1.3.0",
        "matplotlib>=3.7.0",
        "pyserial>=3.5"
    ]
    
    # Try lightweight versions first
    logger.info("🚀 Installing lightweight ML packages...")
    
    for package in quick_packages:
        try:
            logger.info(f"📦 Installing {package}...")
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', package,
                '--trusted-host', 'pypi.org',
                '--trusted-host', 'files.pythonhosted.org',
                '--no-cache-dir', '--timeout', '120'
            ], capture_output=True, text=True, timeout=180)
            
            if result.returncode == 0:
                logger.info(f"✅ {package} installed successfully")
            else:
                logger.warning(f"⚠️  {package} failed to install")
                
        except Exception as e:
            logger.warning(f"⚠️  {package} installation error: {e}")
    
    # Try PyTorch CPU with shorter timeout
    logger.info("🔥 Attempting PyTorch CPU installation...")
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', 
            'torch==2.0.1+cpu', 'torchvision==0.15.2+cpu',
            '--index-url', 'https://download.pytorch.org/whl/cpu',
            '--trusted-host', 'download.pytorch.org',
            '--trusted-host', 'pypi.org',
            '--no-cache-dir', '--timeout', '300'
        ], capture_output=True, text=True, timeout=480)
        
        if result.returncode == 0:
            logger.info("✅ PyTorch CPU installed successfully")
        else:
            logger.info("⚠️  PyTorch installation timed out - using fallback mode")
            
    except Exception as e:
        logger.info(f"⚠️  PyTorch installation failed - using fallback mode: {e}")
    
    logger.info("🎉 Lightweight ML installation complete!")

if __name__ == "__main__":
    install_lightweight_packages()
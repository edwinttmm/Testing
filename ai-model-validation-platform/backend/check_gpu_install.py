#!/usr/bin/env python3
"""
Quick GPU detection and ML package checker
"""
import subprocess
import sys

def check_gpu_and_install():
    """Check for GPU and auto-install if needed"""
    try:
        # Try importing ML packages
        import torch
        import ultralytics
        print("✅ ML packages already available")
        
        # Check GPU availability
        if torch.cuda.is_available():
            print(f"🚀 CUDA GPU available: {torch.cuda.get_device_name()}")
        else:
            print("💻 Using CPU-only mode")
        return True
        
    except ImportError:
        print("📦 ML packages not found. Installing...")
        
        # Run auto-installer
        result = subprocess.run([sys.executable, "auto_install_ml.py"])
        if result.returncode == 0:
            print("✅ Installation completed successfully")
            return True
        else:
            print("⚠️  Installation had issues - will use fallback mode")
            return False

if __name__ == "__main__":
    check_gpu_and_install()
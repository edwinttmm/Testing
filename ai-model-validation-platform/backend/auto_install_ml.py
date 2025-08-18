#!/usr/bin/env python3
"""
Intelligent ML Dependency Installer
Automatically detects GPU availability and installs appropriate ML dependencies
"""
import subprocess
import sys
import os
import platform
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(cmd, check=True, capture_output=True):
    """Run shell command and return result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, 
                              text=True, check=check, timeout=30)
        return result
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out: {cmd}")
        return None
    except subprocess.CalledProcessError as e:
        if check:
            logger.error(f"Command failed: {cmd}, Error: {e}")
        return None

def detect_gpu():
    """Detect available GPU hardware"""
    gpu_info = {
        'has_gpu': False,
        'vendor': 'none',
        'cuda_available': False,
        'rocm_available': False
    }
    
    # Check NVIDIA GPU
    nvidia_check = run_command("nvidia-smi --query-gpu=name --format=csv,noheader,nounits", check=False)
    if nvidia_check and nvidia_check.returncode == 0 and nvidia_check.stdout.strip():
        gpu_info['has_gpu'] = True
        gpu_info['vendor'] = 'nvidia'
        gpu_info['gpu_name'] = nvidia_check.stdout.strip()
        logger.info(f"✅ NVIDIA GPU detected: {gpu_info['gpu_name']}")
        
        # Check CUDA availability
        cuda_check = run_command("nvcc --version", check=False)
        if cuda_check and cuda_check.returncode == 0:
            gpu_info['cuda_available'] = True
            logger.info("✅ CUDA toolkit available")
    
    # Check AMD GPU
    if not gpu_info['has_gpu']:
        amd_check = run_command("rocm-smi --showproductname", check=False)
        if amd_check and amd_check.returncode == 0 and amd_check.stdout.strip():
            gpu_info['has_gpu'] = True
            gpu_info['vendor'] = 'amd'
            gpu_info['gpu_name'] = amd_check.stdout.strip()
            logger.info(f"✅ AMD GPU detected: {gpu_info['gpu_name']}")
            
            # Check ROCm availability
            rocm_check = run_command("hipcc --version", check=False)
            if rocm_check and rocm_check.returncode == 0:
                gpu_info['rocm_available'] = True
                logger.info("✅ ROCm toolkit available")
    
    # Check Intel GPU (less common but possible)
    if not gpu_info['has_gpu']:
        intel_check = run_command("clinfo", check=False)
        if intel_check and intel_check.returncode == 0 and 'intel' in intel_check.stdout.lower():
            gpu_info['has_gpu'] = True
            gpu_info['vendor'] = 'intel'
            logger.info("✅ Intel GPU detected")
    
    if not gpu_info['has_gpu']:
        logger.info("ℹ️  No GPU detected - will use CPU-only mode")
    
    return gpu_info

def get_python_executable():
    """Get the correct Python executable"""
    # Try current Python first
    if hasattr(sys, 'executable') and sys.executable:
        return sys.executable
    
    # Fallback options
    for cmd in ['python3', 'python', 'py']:
        if run_command(f"which {cmd}", check=False):
            return cmd
    
    raise RuntimeError("No Python executable found")

def install_packages(packages, extra_index_urls=None):
    """Install Python packages with proper error handling"""
    python_exe = get_python_executable()
    
    for package in packages:
        logger.info(f"📦 Installing {package}...")
        
        # Add SSL and certificate options for Docker environments
        cmd = f'"{python_exe}" -m pip install {package} --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org'
        if extra_index_urls:
            for url in extra_index_urls:
                cmd += f' --extra-index-url {url}'
                # Add trusted host for extra index URLs
                if 'pytorch.org' in url:
                    cmd += ' --trusted-host download.pytorch.org'
        
        result = run_command(cmd, check=False, capture_output=True)
        
        if result and result.returncode == 0:
            logger.info(f"✅ Successfully installed {package}")
        else:
            error_msg = result.stderr if result else "Unknown error"
            logger.error(f"❌ Failed to install {package}: {error_msg}")
            
            # Try alternative installation methods
            if 'torch' in package:
                logger.info("🔄 Trying CPU-only PyTorch installation...")
                cpu_cmd = f'"{python_exe}" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --trusted-host download.pytorch.org --trusted-host pypi.org --trusted-host files.pythonhosted.org'
                cpu_result = run_command(cpu_cmd, check=False)
                if cpu_result and cpu_result.returncode == 0:
                    logger.info("✅ CPU-only PyTorch installed successfully")
                else:
                    logger.warning("⚠️  Could not install PyTorch - will use fallback mode")

def create_ml_requirements():
    """Create ML requirements file based on detected hardware"""
    gpu_info = detect_gpu()
    
    # Base requirements (always needed)
    base_requirements = [
        "opencv-python-headless>=4.8.0",
        "pillow>=10.0.0", 
        "numpy>=1.24.0"
    ]
    
    # Hardware interface requirements (always try to install)
    hardware_requirements = [
        "pyserial>=3.5"  # For serial communication
    ]
    
    # GPU-specific requirements
    gpu_requirements = []
    extra_index_urls = []
    
    if gpu_info['has_gpu']:
        if gpu_info['vendor'] == 'nvidia' and gpu_info['cuda_available']:
            logger.info("🚀 Installing NVIDIA GPU-optimized packages...")
            gpu_requirements.extend([
                "torch>=2.0.0+cu118",
                "torchvision>=0.15.0+cu118", 
                "torchaudio>=2.0.0+cu118",
                "ultralytics>=8.0.0"
            ])
            extra_index_urls.append("https://download.pytorch.org/whl/cu118")
            
        elif gpu_info['vendor'] == 'amd' and gpu_info['rocm_available']:
            logger.info("🚀 Installing AMD GPU-optimized packages...")
            gpu_requirements.extend([
                "torch>=2.0.0+rocm5.4.2",
                "torchvision>=0.15.0+rocm5.4.2",
                "ultralytics>=8.0.0"
            ])
            extra_index_urls.append("https://download.pytorch.org/whl/rocm5.4.2")
            
        else:
            logger.info("🔧 GPU detected but no accelerated ML framework available - using CPU mode")
            gpu_requirements.extend([
                "torch>=2.0.0+cpu",
                "torchvision>=0.15.0+cpu",
                "torchaudio>=2.0.0+cpu",
                "ultralytics>=8.0.0"
            ])
            extra_index_urls.append("https://download.pytorch.org/whl/cpu")
    else:
        logger.info("💻 Installing CPU-only ML packages...")
        gpu_requirements.extend([
            "torch>=2.0.0+cpu",
            "torchvision>=0.15.0+cpu", 
            "torchaudio>=2.0.0+cpu",
            "ultralytics>=8.0.0"
        ])
        extra_index_urls.append("https://download.pytorch.org/whl/cpu")
    
    # Install packages
    logger.info("📥 Installing base ML packages...")
    install_packages(base_requirements)
    
    logger.info("🔌 Installing hardware interface packages...")
    install_packages(hardware_requirements)
    
    if gpu_requirements:
        logger.info("🚀 Installing GPU/compute packages...")
        install_packages(gpu_requirements, extra_index_urls)
    
    # Write requirements file for future reference
    all_requirements = base_requirements + gpu_requirements
    requirements_path = Path(__file__).parent / "requirements-ml-auto.txt"
    
    with open(requirements_path, 'w') as f:
        f.write("# Auto-generated ML requirements based on detected hardware\n")
        f.write(f"# GPU detected: {gpu_info['has_gpu']} ({gpu_info['vendor']})\n")
        f.write(f"# Generated on: {platform.platform()}\n\n")
        
        for req in all_requirements:
            f.write(f"{req}\n")
        
        if extra_index_urls:
            f.write(f"\n# Extra index URLs used:\n")
            for url in extra_index_urls:
                f.write(f"# {url}\n")
    
    logger.info(f"📝 Requirements saved to {requirements_path}")
    return gpu_info

def verify_installation():
    """Verify that ML packages were installed correctly"""
    logger.info("🔍 Verifying ML package installation...")
    
    # Test imports
    test_imports = [
        ("cv2", "OpenCV"),
        ("numpy", "NumPy"),
        ("PIL", "Pillow"),
        ("torch", "PyTorch"),
        ("ultralytics", "Ultralytics")
    ]
    
    results = {}
    for module, name in test_imports:
        try:
            __import__(module)
            logger.info(f"✅ {name} import successful")
            results[module] = True
        except ImportError as e:
            logger.warning(f"⚠️  {name} import failed: {e}")
            results[module] = False
    
    # Test basic functionality
    if results.get('torch', False):
        try:
            import torch
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            logger.info(f"🎯 PyTorch using device: {device}")
            
            # Test basic tensor operations
            x = torch.randn(2, 2, device=device)
            y = x + 1
            logger.info("✅ PyTorch tensor operations working")
            results['torch_functional'] = True
        except Exception as e:
            logger.warning(f"⚠️  PyTorch functionality test failed: {e}")
            results['torch_functional'] = False
    
    return results

def main():
    """Main installation routine"""
    logger.info("🚀 Starting intelligent ML dependency installation...")
    logger.info(f"🖥️  Platform: {platform.platform()}")
    logger.info(f"🐍 Python: {sys.version}")
    
    # Apply SSL fixes for Docker environments
    try:
        from pip_ssl_fix import fix_ssl_certificates
        fix_ssl_certificates()
    except ImportError:
        logger.info("🔧 Applying basic SSL bypass...")
        import os
        os.environ['PYTHONHTTPSVERIFY'] = '0'
    
    try:
        # Detect hardware and install appropriate packages
        gpu_info = create_ml_requirements()
        
        # Verify installation
        results = verify_installation()
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("📊 INSTALLATION SUMMARY")
        logger.info("="*50)
        logger.info(f"GPU Detected: {gpu_info['has_gpu']} ({gpu_info['vendor']})")
        logger.info(f"CUDA Available: {gpu_info['cuda_available']}")
        logger.info(f"ROCm Available: {gpu_info['rocm_available']}")
        
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        logger.info(f"Packages: {success_count}/{total_count} successful")
        
        if success_count == total_count:
            logger.info("🎉 All ML dependencies installed successfully!")
            return 0
        else:
            logger.warning("⚠️  Some ML dependencies failed to install - will use fallback mode")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Installation failed: {e}")
        logger.info("🔄 Will use CPU-only fallback mode")
        return 1

if __name__ == "__main__":
    sys.exit(main())
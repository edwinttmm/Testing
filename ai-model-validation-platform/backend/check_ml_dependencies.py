#!/usr/bin/env python3
"""
ML Dependencies Checker
Verify all required ML dependencies are available for YOLO detection
"""

import sys
import logging
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check all required ML dependencies"""
    dependencies_status = {}
    
    # Check torch
    try:
        import torch
        dependencies_status['torch'] = {
            'available': True,
            'version': torch.__version__,
            'cuda_available': torch.cuda.is_available(),
            'cuda_devices': torch.cuda.device_count() if torch.cuda.is_available() else 0
        }
        logger.info(f"✅ PyTorch {torch.__version__} - CUDA: {torch.cuda.is_available()}")
    except ImportError as e:
        dependencies_status['torch'] = {'available': False, 'error': str(e)}
        logger.error(f"❌ PyTorch not available: {e}")
    
    # Check ultralytics
    try:
        import ultralytics
        dependencies_status['ultralytics'] = {
            'available': True,
            'version': ultralytics.__version__
        }
        logger.info(f"✅ Ultralytics {ultralytics.__version__}")
    except ImportError as e:
        dependencies_status['ultralytics'] = {'available': False, 'error': str(e)}
        logger.error(f"❌ Ultralytics not available: {e}")
    
    # Check OpenCV
    try:
        import cv2
        dependencies_status['opencv'] = {
            'available': True,
            'version': cv2.__version__
        }
        logger.info(f"✅ OpenCV {cv2.__version__}")
    except ImportError as e:
        dependencies_status['opencv'] = {'available': False, 'error': str(e)}
        logger.error(f"❌ OpenCV not available: {e}")
    
    # Check numpy
    try:
        import numpy as np
        dependencies_status['numpy'] = {
            'available': True,
            'version': np.__version__
        }
        logger.info(f"✅ NumPy {np.__version__}")
    except ImportError as e:
        dependencies_status['numpy'] = {'available': False, 'error': str(e)}
        logger.error(f"❌ NumPy not available: {e}")
    
    return dependencies_status

def test_yolo_loading():
    """Test YOLO model loading"""
    try:
        from ultralytics import YOLO
        import torch
        
        logger.info("🔍 Testing YOLO model loading...")
        
        # Try to load a small model for testing
        model = YOLO('yolov8n.pt')
        logger.info(f"✅ YOLO model loaded successfully")
        
        # Test inference
        import numpy as np
        dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
        results = model(dummy_image, verbose=False)
        logger.info(f"✅ YOLO inference test successful")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ YOLO test failed: {e}")
        return False

def install_missing_dependencies():
    """Install missing dependencies"""
    logger.info("🔧 Installing missing ML dependencies...")
    
    try:
        # Install PyTorch (CPU version)
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "torch", "torchvision", "torchaudio", "--index-url", 
            "https://download.pytorch.org/whl/cpu"
        ])
        logger.info("✅ PyTorch installed")
    except Exception as e:
        logger.error(f"❌ Failed to install PyTorch: {e}")
    
    try:
        # Install Ultralytics
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "ultralytics"
        ])
        logger.info("✅ Ultralytics installed")
    except Exception as e:
        logger.error(f"❌ Failed to install Ultralytics: {e}")
    
    try:
        # Install OpenCV
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "opencv-python-headless"
        ])
        logger.info("✅ OpenCV installed")
    except Exception as e:
        logger.error(f"❌ Failed to install OpenCV: {e}")

def main():
    """Main dependency check"""
    logger.info("🚀 ML Dependencies Check")
    logger.info("=" * 50)
    
    # Check dependencies
    status = check_dependencies()
    
    # Count missing dependencies
    missing = [name for name, info in status.items() if not info['available']]
    
    if missing:
        logger.warning(f"❌ Missing dependencies: {missing}")
        
        # Ask to install
        response = input("Install missing dependencies? (y/n): ")
        if response.lower() == 'y':
            install_missing_dependencies()
            
            # Re-check
            logger.info("🔄 Re-checking dependencies...")
            status = check_dependencies()
            missing = [name for name, info in status.items() if not info['available']]
    
    if not missing:
        logger.info("✅ All dependencies available")
        
        # Test YOLO
        if test_yolo_loading():
            logger.info("🎉 YOLO detection system ready!")
            return True
        else:
            logger.error("❌ YOLO testing failed")
            return False
    else:
        logger.error(f"❌ Still missing: {missing}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
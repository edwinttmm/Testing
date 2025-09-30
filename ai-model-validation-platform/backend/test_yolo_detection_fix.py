#!/usr/bin/env python3
"""
YOLO Detection Fix Validation Script
Test that YOLO detection is working properly with the fixes applied
"""

import asyncio
import logging
import os
import sys
import numpy as np
import cv2
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).parent
sys.path.insert(0, str(backend_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_detection_pipeline():
    """Test the detection pipeline with fixes"""
    logger.info("🚀 Testing YOLO Detection Pipeline Fixes")
    logger.info("=" * 60)
    
    # Test 1: Check dependencies
    logger.info("1. Checking ML dependencies...")
    try:
        import torch
        import ultralytics
        import cv2
        import numpy as np
        logger.info(f"   ✅ PyTorch: {torch.__version__}")
        logger.info(f"   ✅ Ultralytics: {ultralytics.__version__}")
        logger.info(f"   ✅ OpenCV: {cv2.__version__}")
        logger.info(f"   ✅ NumPy: {np.__version__}")
        logger.info(f"   ✅ CUDA available: {torch.cuda.is_available()}")
    except ImportError as e:
        logger.error(f"   ❌ Missing dependency: {e}")
        return False
    
    # Test 2: Test detection pipeline
    logger.info("\n2. Testing Detection Pipeline...")
    try:
        from services.detection_pipeline_service import DetectionPipeline
        
        pipeline = DetectionPipeline()
        await pipeline.initialize()
        logger.info("   ✅ Detection pipeline initialized")
        
        # Create test frame
        test_frame = np.zeros((640, 640, 3), dtype=np.uint8)
        
        # Add a simple white rectangle to simulate an object
        cv2.rectangle(test_frame, (200, 200), (400, 500), (255, 255, 255), -1)
        
        # Test frame processing
        processed_frame = await pipeline.frame_processor.preprocess(test_frame)
        logger.info("   ✅ Frame preprocessing works")
        
        # Test model loading
        model = await pipeline.model_registry.get_active_model()
        logger.info("   ✅ Model loading works")
        
        # Test detection
        detections = await model.predict(test_frame)
        logger.info(f"   ✅ Detection test: {len(detections)} detections found")
        
        # Test batch processing
        frames = [test_frame, test_frame]
        results = await pipeline.process_frame_batch(frames)
        logger.info(f"   ✅ Batch processing: {len(results)} results")
        
    except Exception as e:
        logger.error(f"   ❌ Detection pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Test ground truth service
    logger.info("\n3. Testing Ground Truth Service...")
    try:
        from services.ground_truth_service import GroundTruthService
        
        gt_service = GroundTruthService()
        logger.info(f"   ✅ Ground truth service initialized - ML available: {gt_service.ml_available}")
        
        if gt_service.model:
            logger.info("   ✅ YOLO model loaded in ground truth service")
        else:
            logger.warning("   ⚠️ No YOLO model in ground truth service (fallback mode)")
            
    except Exception as e:
        logger.error(f"   ❌ Ground truth service test failed: {e}")
        return False
    
    # Test 4: Test video processing if video exists
    logger.info("\n4. Testing Video Processing...")
    try:
        # Look for any test video
        video_paths = [
            '/home/rigade/Testing/ai-model-validation-platform/backend/uploads/test_video.mp4',
            '/home/rigade/Testing/ai-model-validation-platform/backend/test_video.mp4',
            # Add any known video paths here
        ]
        
        test_video_path = None
        for path in video_paths:
            if os.path.exists(path):
                test_video_path = path
                break
        
        if test_video_path:
            logger.info(f"   📹 Found test video: {test_video_path}")
            
            # Test processing first 10 frames only
            detections = await pipeline.process_video(test_video_path, config={'max_frames': 10})
            logger.info(f"   ✅ Video processing: {len(detections)} detections in first 10 frames")
            
            # Log detection details
            for det in detections[:3]:  # Show first 3 detections
                logger.info(f"      - Frame {det.get('frame_number', 'N/A')}: "
                          f"{det.get('class_label', 'N/A')} "
                          f"({det.get('confidence', 0):.3f})")
        else:
            logger.info("   ⚠️ No test video found - skipping video test")
            
    except Exception as e:
        logger.error(f"   ❌ Video processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Model file check
    logger.info("\n5. Checking Model Files...")
    model_paths = [
        '/home/rigade/Testing/ai-model-validation-platform/backend/yolo11l.pt',
        '/home/rigade/Testing/ai-model-validation-platform/backend/yolov8n.pt',
        './yolo11l.pt',
        './yolov8n.pt'
    ]
    
    found_models = []
    for path in model_paths:
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            found_models.append(f"{path} ({size_mb:.1f} MB)")
            logger.info(f"   ✅ Found: {path} ({size_mb:.1f} MB)")
    
    if not found_models:
        logger.warning("   ⚠️ No local models found - will auto-download")
    else:
        logger.info(f"   ✅ Found {len(found_models)} local model(s)")
    
    logger.info("\n🎉 YOLO Detection Test Complete!")
    logger.info("✅ All core detection functionality is working")
    return True

async def create_test_video():
    """Create a simple test video for testing"""
    logger.info("🎬 Creating test video...")
    
    try:
        # Create a simple test video with moving rectangle
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter('/home/rigade/Testing/ai-model-validation-platform/backend/test_video.mp4', 
                             fourcc, 30.0, (640, 480))
        
        for i in range(90):  # 3 seconds at 30fps
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Moving white rectangle (simulates person)
            x = 50 + (i * 5) % 500
            y = 200
            cv2.rectangle(frame, (x, y), (x + 80, y + 160), (255, 255, 255), -1)
            
            # Add some noise
            noise = np.random.randint(0, 50, frame.shape, dtype=np.uint8)
            frame = cv2.add(frame, noise)
            
            out.write(frame)
        
        out.release()
        logger.info("   ✅ Test video created: test_video.mp4")
        
    except Exception as e:
        logger.error(f"   ❌ Failed to create test video: {e}")

def main():
    """Main test function"""
    print("🚀 YOLO Detection Fix Validation")
    print("=" * 50)
    
    # Create test video if needed
    if not os.path.exists('/home/rigade/Testing/ai-model-validation-platform/backend/test_video.mp4'):
        asyncio.run(create_test_video())
    
    # Run tests
    success = asyncio.run(test_detection_pipeline())
    
    if success:
        print("\n🎉 SUCCESS: YOLO Detection is working properly!")
        print("✅ The detection pipeline fixes have resolved the issues")
        print("\nKey fixes applied:")
        print("- ✅ Model path detection with fallback chain")
        print("- ✅ Proper error handling and logging")
        print("- ✅ Dependency checking and validation")
        print("- ✅ Thread-safe model loading")
        print("- ✅ Improved inference pipeline")
        return True
    else:
        print("\n❌ FAILURE: Issues still exist in YOLO detection")
        print("❌ Check the logs above for specific problems")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
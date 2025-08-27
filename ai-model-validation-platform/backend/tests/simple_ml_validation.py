#!/usr/bin/env python3
"""
Simple ML Inference Engine Validation
====================================

This script performs essential validation of the ML inference pipeline
without complex dependencies to verify basic functionality.

Author: ML Validation Team
Version: 1.0.0
"""

import os
import sys
import time
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add backend path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

def check_dependencies():
    """Check if required ML dependencies are available"""
    dependencies = {
        'torch': False,
        'cv2': False,
        'numpy': False,
        'ultralytics': False
    }
    
    try:
        import torch
        dependencies['torch'] = True
        print(f"✅ PyTorch {torch.__version__} available")
    except ImportError:
        print("❌ PyTorch not available")
    
    try:
        import cv2
        dependencies['cv2'] = True
        print(f"✅ OpenCV {cv2.__version__} available")
    except ImportError:
        print("❌ OpenCV not available")
    
    try:
        import numpy as np
        dependencies['numpy'] = True
        print(f"✅ NumPy {np.__version__} available")
    except ImportError:
        print("❌ NumPy not available")
    
    try:
        from ultralytics import YOLO
        dependencies['ultralytics'] = True
        print("✅ Ultralytics YOLO available")
    except ImportError:
        print("❌ Ultralytics YOLO not available")
    
    return dependencies

def check_yolo_models():
    """Check available YOLO model files"""
    model_paths = [
        '/home/user/Testing/ai-model-validation-platform/backend/yolo11l.pt',
        '/home/user/Testing/ai-model-validation-platform/backend/yolov8n.pt'
    ]
    
    available_models = []
    for path in model_paths:
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            available_models.append({
                'path': path,
                'name': os.path.basename(path),
                'size_mb': round(size_mb, 1)
            })
            print(f"✅ Found model: {os.path.basename(path)} ({size_mb:.1f} MB)")
        else:
            print(f"❌ Missing model: {os.path.basename(path)}")
    
    return available_models

def test_basic_inference():
    """Test basic YOLO inference if available"""
    results = {'status': 'unknown', 'details': {}}
    
    try:
        import torch
        import numpy as np
        from ultralytics import YOLO
        
        # Check available models
        available_models = check_yolo_models()
        if not available_models:
            results['status'] = 'skipped'
            results['details']['reason'] = 'No YOLO models available'
            return results
        
        # Use the smallest available model for testing
        model_path = min(available_models, key=lambda x: x['size_mb'])['path']
        print(f"Testing with model: {os.path.basename(model_path)}")
        
        # Load model
        model = YOLO(model_path)
        
        # Create test image
        test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        
        # Run inference
        start_time = time.time()
        results_yolo = model(test_image, verbose=False)
        inference_time = time.time() - start_time
        
        # Process results
        detections = []
        for r in results_yolo:
            if r.boxes is not None:
                for box in r.boxes:
                    detections.append({
                        'class_id': int(box.cls[0]),
                        'confidence': float(box.conf[0]),
                        'bbox': box.xyxy[0].tolist()
                    })
        
        results['status'] = 'passed'
        results['details'] = {
            'model_used': os.path.basename(model_path),
            'inference_time': inference_time,
            'detections_found': len(detections),
            'detections': detections[:3]  # First 3 detections
        }
        
        print(f"✅ Inference successful: {len(detections)} detections in {inference_time:.3f}s")
        
    except Exception as e:
        results['status'] = 'failed'
        results['details'] = {
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        print(f"❌ Inference failed: {e}")
    
    return results

def test_video_processing():
    """Test video processing capabilities"""
    results = {'status': 'unknown', 'details': {}}
    
    try:
        import cv2
        import numpy as np
        import tempfile
        
        # Create a simple test video
        temp_video = tempfile.mktemp(suffix='.mp4')
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(temp_video, fourcc, 10.0, (320, 240))
        
        # Write 30 test frames
        for i in range(30):
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            # Add some content
            cv2.circle(frame, (160 + i*2, 120), 20, (255, 255, 255), -1)
            cv2.putText(frame, f'Frame {i}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
            writer.write(frame)
        
        writer.release()
        
        # Test video reading
        cap = cv2.VideoCapture(temp_video)
        if not cap.isOpened():
            raise ValueError("Could not open test video")
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Read frames
        frames_read = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames_read += 1
        
        cap.release()
        
        # Cleanup
        if os.path.exists(temp_video):
            os.remove(temp_video)
        
        results['status'] = 'passed'
        results['details'] = {
            'fps': fps,
            'frame_count': frame_count,
            'resolution': f"{width}x{height}",
            'frames_read': frames_read
        }
        
        print(f"✅ Video processing: {frames_read} frames at {fps}fps ({width}x{height})")
        
    except Exception as e:
        results['status'] = 'failed'
        results['details'] = {
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        print(f"❌ Video processing failed: {e}")
    
    return results

def test_database_connection():
    """Test database connectivity"""
    results = {'status': 'unknown', 'details': {}}
    
    try:
        from unified_database import get_database_manager
        
        db_manager = get_database_manager()
        health = db_manager.test_connection()
        
        results['status'] = 'passed' if health['status'] == 'healthy' else 'failed'
        results['details'] = {
            'connection_status': health['status'],
            'database_type': health.get('database_type', 'unknown'),
            'response_time': health.get('response_time_ms', 0)
        }
        
        if health['status'] == 'healthy':
            print(f"✅ Database connection: {health.get('database_type', 'unknown')}")
        else:
            print(f"❌ Database connection failed: {health}")
        
    except Exception as e:
        results['status'] = 'failed'
        results['details'] = {
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        print(f"❌ Database connection failed: {e}")
    
    return results

def test_ml_engine_initialization():
    """Test ML engine initialization"""
    results = {'status': 'unknown', 'details': {}}
    
    try:
        # Try to import ML engine modules
        try:
            from src.ml_inference_engine import MLInferenceEngine
            basic_engine_available = True
        except ImportError:
            basic_engine_available = False
        
        try:
            from src.enhanced_ml_inference_engine import ProductionMLInferenceEngine
            enhanced_engine_available = True
        except ImportError:
            enhanced_engine_available = False
        
        results['details'] = {
            'basic_engine_available': basic_engine_available,
            'enhanced_engine_available': enhanced_engine_available
        }
        
        if basic_engine_available or enhanced_engine_available:
            results['status'] = 'passed'
            print(f"✅ ML engine modules available (basic: {basic_engine_available}, enhanced: {enhanced_engine_available})")
        else:
            results['status'] = 'failed'
            print("❌ No ML engine modules available")
            
    except Exception as e:
        results['status'] = 'failed'
        results['details']['error'] = str(e)
        print(f"❌ ML engine check failed: {e}")
    
    return results

def run_simple_validation():
    """Run simple validation tests"""
    print("🚀 Simple ML Inference Engine Validation")
    print("=" * 50)
    
    validation_results = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'tests': {}
    }
    
    # Test 1: Check dependencies
    print("\n1. Checking Dependencies...")
    dependencies = check_dependencies()
    validation_results['tests']['dependencies'] = {
        'status': 'passed' if any(dependencies.values()) else 'failed',
        'details': dependencies
    }
    
    # Test 2: Check YOLO models
    print("\n2. Checking YOLO Models...")
    available_models = check_yolo_models()
    validation_results['tests']['yolo_models'] = {
        'status': 'passed' if available_models else 'failed',
        'details': {'available_models': available_models}
    }
    
    # Test 3: Test ML engine initialization
    print("\n3. Testing ML Engine Initialization...")
    ml_engine_result = test_ml_engine_initialization()
    validation_results['tests']['ml_engine_init'] = ml_engine_result
    
    # Test 4: Test basic inference (if possible)
    print("\n4. Testing Basic Inference...")
    if dependencies.get('torch') and dependencies.get('ultralytics') and available_models:
        inference_result = test_basic_inference()
        validation_results['tests']['basic_inference'] = inference_result
    else:
        print("⏭️  Skipping inference test - dependencies not available")
        validation_results['tests']['basic_inference'] = {
            'status': 'skipped',
            'details': {'reason': 'Dependencies not available'}
        }
    
    # Test 5: Test video processing
    print("\n5. Testing Video Processing...")
    if dependencies.get('cv2'):
        video_result = test_video_processing()
        validation_results['tests']['video_processing'] = video_result
    else:
        print("⏭️  Skipping video test - OpenCV not available")
        validation_results['tests']['video_processing'] = {
            'status': 'skipped',
            'details': {'reason': 'OpenCV not available'}
        }
    
    # Test 6: Test database connection
    print("\n6. Testing Database Connection...")
    db_result = test_database_connection()
    validation_results['tests']['database'] = db_result
    
    # Generate summary
    print("\n📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    skipped_tests = 0
    
    for test_name, test_result in validation_results['tests'].items():
        total_tests += 1
        status = test_result['status']
        
        if status == 'passed':
            passed_tests += 1
            status_emoji = "✅"
        elif status == 'failed':
            failed_tests += 1
            status_emoji = "❌"
        else:
            skipped_tests += 1
            status_emoji = "⏭️"
        
        print(f"{status_emoji} {test_name.replace('_', ' ').title()}: {status.upper()}")
    
    print(f"\nResults: {passed_tests} passed, {failed_tests} failed, {skipped_tests} skipped")
    
    # Overall status
    if failed_tests == 0 and passed_tests > 0:
        overall_status = "PASSED"
        print("\n🎉 Overall Status: PASSED - Basic ML functionality is working!")
    elif passed_tests > failed_tests:
        overall_status = "PARTIAL"
        print("\n⚠️  Overall Status: PARTIAL - Some functionality working, issues found")
    else:
        overall_status = "FAILED"
        print("\n❌ Overall Status: FAILED - Major issues with ML infrastructure")
    
    validation_results['summary'] = {
        'overall_status': overall_status,
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'failed_tests': failed_tests,
        'skipped_tests': skipped_tests,
        'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
    }
    
    # Save results
    results_file = f"/home/user/Testing/ai-model-validation-platform/backend/tests/simple_ml_validation_{int(time.time())}.json"
    with open(results_file, 'w') as f:
        json.dump(validation_results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {results_file}")
    
    return validation_results

if __name__ == "__main__":
    try:
        results = run_simple_validation()
        overall_status = results['summary']['overall_status']
        
        if overall_status == "PASSED":
            exit(0)
        elif overall_status == "PARTIAL":
            exit(1)
        else:
            exit(2)
            
    except Exception as e:
        print(f"\n💥 Validation crashed: {e}")
        print(traceback.format_exc())
        exit(3)
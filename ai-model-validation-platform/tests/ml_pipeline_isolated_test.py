#!/usr/bin/env python3
"""
ML Pipeline Isolated Testing
============================

Tests ML pipeline components without requiring full infrastructure setup.
This allows testing core ML functionality even when database/API services are down.
"""

import sys
import json
import time
import uuid
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

def test_ml_dependencies():
    """Test that all ML dependencies are available"""
    results = {
        "success": False,
        "dependencies": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Test PyTorch
        import torch
        results["dependencies"]["pytorch"] = {
            "available": True,
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "device": "cuda" if torch.cuda.is_available() else "cpu"
        }
        
        # Test Ultralytics
        import ultralytics
        results["dependencies"]["ultralytics"] = {
            "available": True,
            "version": ultralytics.__version__
        }
        
        # Test OpenCV
        import cv2
        results["dependencies"]["opencv"] = {
            "available": True,
            "version": cv2.__version__
        }
        
        # Test NumPy
        import numpy as np
        results["dependencies"]["numpy"] = {
            "available": True,
            "version": np.__version__
        }
        
        results["success"] = True
        print("✅ All ML dependencies are available")
        
    except Exception as e:
        results["error"] = str(e)
        print(f"❌ ML dependency error: {e}")
    
    return results

def test_model_loading():
    """Test YOLO model loading and initialization"""
    results = {
        "success": False,
        "model_tests": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        from ultralytics import YOLO
        
        # Test different model sizes
        models_to_test = ['yolo11n.pt', 'yolo11s.pt']  # Start with smaller models
        
        for model_name in models_to_test:
            try:
                print(f"Loading {model_name}...")
                start_time = time.time()
                model = YOLO(model_name)
                load_time = (time.time() - start_time) * 1000
                
                results["model_tests"][model_name] = {
                    "loaded": True,
                    "load_time_ms": load_time,
                    "model_size": model_name
                }
                print(f"✅ {model_name} loaded in {load_time:.1f}ms")
                
            except Exception as e:
                results["model_tests"][model_name] = {
                    "loaded": False,
                    "error": str(e)
                }
                print(f"❌ Failed to load {model_name}: {e}")
        
        # Success if at least one model loads
        results["success"] = any(test.get("loaded", False) for test in results["model_tests"].values())
        
    except Exception as e:
        results["error"] = str(e)
        print(f"❌ Model loading error: {e}")
    
    return results

def test_inference_pipeline():
    """Test complete inference pipeline"""
    results = {
        "success": False,
        "inference_tests": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        from ultralytics import YOLO
        
        # Load model
        print("Loading model for inference test...")
        model = YOLO('yolo11n.pt')
        
        # Create test images
        test_images = {
            "empty": np.zeros((640, 640, 3), dtype=np.uint8),
            "noise": np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8),
            "synthetic": create_synthetic_pedestrian_image()
        }
        
        for image_type, test_image in test_images.items():
            try:
                print(f"Testing inference on {image_type} image...")
                start_time = time.time()
                
                # Run inference
                results_yolo = model(test_image, verbose=False, conf=0.1)
                inference_time = (time.time() - start_time) * 1000
                
                # Parse results
                detections = []
                for r in results_yolo:
                    if r.boxes is not None:
                        for box in r.boxes:
                            detections.append({
                                "confidence": float(box.conf[0]),
                                "class_id": int(box.cls[0]),
                                "class_name": model.names[int(box.cls[0])],
                                "bbox": box.xyxy[0].cpu().numpy().tolist()
                            })
                
                results["inference_tests"][image_type] = {
                    "success": True,
                    "inference_time_ms": inference_time,
                    "detections_count": len(detections),
                    "detections": detections[:5]  # Store first 5 detections
                }
                print(f"✅ {image_type} inference: {len(detections)} detections in {inference_time:.1f}ms")
                
            except Exception as e:
                results["inference_tests"][image_type] = {
                    "success": False,
                    "error": str(e)
                }
                print(f"❌ Inference failed on {image_type}: {e}")
        
        # Success if at least one inference works
        results["success"] = any(test.get("success", False) for test in results["inference_tests"].values())
        
    except Exception as e:
        results["error"] = str(e)
        print(f"❌ Inference pipeline error: {e}")
    
    return results

def test_video_processing():
    """Test video file processing"""
    results = {
        "success": False,
        "video_tests": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Find test videos
        video_files = list(Path("backend/uploads").glob("*.mp4"))
        if not video_files:
            results["error"] = "No test videos found"
            return results
        
        test_video = video_files[0]
        print(f"Testing video processing with: {test_video.name}")
        
        # Test video file reading
        cap = cv2.VideoCapture(str(test_video))
        if not cap.isOpened():
            results["error"] = f"Cannot open video: {test_video}"
            return results
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        results["video_tests"]["properties"] = {
            "fps": fps,
            "frame_count": frame_count,
            "duration_seconds": duration,
            "file_size_mb": test_video.stat().st_size / 1024 / 1024
        }
        
        # Process first few frames
        from ultralytics import YOLO
        model = YOLO('yolo11n.pt')
        
        processed_frames = 0
        total_detections = 0
        processing_times = []
        
        print("Processing video frames...")
        while processed_frames < min(30, frame_count):  # Process up to 30 frames
            ret, frame = cap.read()
            if not ret:
                break
            
            # Skip every 5th frame for efficiency
            if processed_frames % 5 == 0:
                start_time = time.time()
                results_yolo = model(frame, verbose=False, conf=0.3)
                processing_time = (time.time() - start_time) * 1000
                processing_times.append(processing_time)
                
                # Count detections
                frame_detections = 0
                for r in results_yolo:
                    if r.boxes is not None:
                        frame_detections = len(r.boxes)
                total_detections += frame_detections
            
            processed_frames += 1
        
        cap.release()
        
        results["video_tests"]["processing"] = {
            "frames_processed": processed_frames,
            "total_detections": total_detections,
            "avg_processing_time_ms": np.mean(processing_times) if processing_times else 0,
            "fps_achieved": 1000 / np.mean(processing_times) if processing_times and np.mean(processing_times) > 0 else 0
        }
        
        results["success"] = processed_frames > 0
        print(f"✅ Video processing: {processed_frames} frames, {total_detections} detections")
        
    except Exception as e:
        results["error"] = str(e)
        print(f"❌ Video processing error: {e}")
    
    return results

def test_detection_accuracy():
    """Test detection accuracy with known objects"""
    results = {
        "success": False,
        "accuracy_tests": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        from ultralytics import YOLO
        model = YOLO('yolo11n.pt')
        
        # Test with synthetic image containing known objects
        synthetic_image = create_synthetic_pedestrian_image()
        
        print("Testing detection accuracy...")
        results_yolo = model(synthetic_image, verbose=False, conf=0.1)
        
        # Analyze results
        person_detections = []
        for r in results_yolo:
            if r.boxes is not None:
                for box in r.boxes:
                    class_id = int(box.cls[0])
                    if class_id == 0:  # Person class in COCO
                        person_detections.append({
                            "confidence": float(box.conf[0]),
                            "bbox": box.xyxy[0].cpu().numpy().tolist()
                        })
        
        # We expect to detect the 2 synthetic pedestrians we created
        expected_detections = 2
        detected_count = len(person_detections)
        accuracy = min(detected_count / expected_detections, 1.0) if expected_detections > 0 else 0
        
        results["accuracy_tests"]["synthetic_pedestrians"] = {
            "expected_detections": expected_detections,
            "detected_count": detected_count,
            "accuracy_score": accuracy,
            "detections": person_detections
        }
        
        # Test confidence distribution
        if person_detections:
            confidences = [d["confidence"] for d in person_detections]
            results["accuracy_tests"]["confidence_analysis"] = {
                "avg_confidence": np.mean(confidences),
                "min_confidence": np.min(confidences),
                "max_confidence": np.max(confidences),
                "high_confidence_count": len([c for c in confidences if c > 0.5])
            }
        
        results["success"] = detected_count > 0
        print(f"✅ Detection accuracy: {detected_count}/{expected_detections} = {accuracy*100:.1f}%")
        
    except Exception as e:
        results["error"] = str(e)
        print(f"❌ Detection accuracy error: {e}")
    
    return results

def test_performance_benchmarks():
    """Test performance under different conditions"""
    results = {
        "success": False,
        "performance_tests": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        from ultralytics import YOLO
        model = YOLO('yolo11n.pt')
        
        # Test different image sizes
        image_sizes = [(320, 320), (640, 640), (1280, 1280)]
        
        for width, height in image_sizes:
            test_image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            
            # Warm up
            _ = model(test_image, verbose=False)
            
            # Benchmark
            processing_times = []
            for _ in range(5):
                start_time = time.time()
                _ = model(test_image, verbose=False)
                processing_times.append((time.time() - start_time) * 1000)
            
            results["performance_tests"][f"{width}x{height}"] = {
                "avg_time_ms": np.mean(processing_times),
                "min_time_ms": np.min(processing_times),
                "max_time_ms": np.max(processing_times),
                "fps": 1000 / np.mean(processing_times),
                "pixels": width * height
            }
            
            print(f"✅ {width}x{height}: {np.mean(processing_times):.1f}ms avg, {1000/np.mean(processing_times):.1f} FPS")
        
        # Batch processing test
        batch_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        batch_sizes = [1, 4, 8]
        
        for batch_size in batch_sizes:
            batch_images = [batch_image for _ in range(batch_size)]
            
            start_time = time.time()
            _ = model(batch_images, verbose=False)
            batch_time = (time.time() - start_time) * 1000
            
            results["performance_tests"][f"batch_{batch_size}"] = {
                "total_time_ms": batch_time,
                "time_per_image_ms": batch_time / batch_size,
                "batch_fps": batch_size * 1000 / batch_time
            }
            
            print(f"✅ Batch {batch_size}: {batch_time/batch_size:.1f}ms per image")
        
        results["success"] = True
        
    except Exception as e:
        results["error"] = str(e)
        print(f"❌ Performance benchmark error: {e}")
    
    return results

def create_synthetic_pedestrian_image():
    """Create synthetic image with pedestrian-like objects"""
    # Create base image
    image = np.zeros((640, 640, 3), dtype=np.uint8)
    
    # Add background texture
    noise = np.random.randint(20, 50, (640, 640, 3), dtype=np.uint8)
    image = cv2.add(image, noise)
    
    # Draw pedestrian-like rectangles (simulating people)
    # Person 1 - standing upright
    cv2.rectangle(image, (150, 200), (200, 400), (128, 128, 128), -1)  # Body
    cv2.rectangle(image, (165, 180), (185, 200), (150, 150, 150), -1)  # Head
    cv2.rectangle(image, (140, 250), (210, 280), (100, 100, 100), -1)  # Arms
    cv2.rectangle(image, (160, 400), (190, 450), (80, 80, 80), -1)     # Legs
    
    # Person 2 - different size
    cv2.rectangle(image, (400, 250), (440, 420), (120, 120, 120), -1)  # Body
    cv2.rectangle(image, (410, 230), (430, 250), (140, 140, 140), -1)  # Head
    cv2.rectangle(image, (390, 290), (450, 310), (90, 90, 90), -1)     # Arms
    cv2.rectangle(image, (410, 420), (430, 460), (70, 70, 70), -1)     # Legs
    
    return image

def main():
    """Run all isolated ML pipeline tests"""
    print("🔬 Running ML Pipeline Isolated Tests")
    print("=" * 50)
    
    all_results = {
        "test_suite": "ml_pipeline_isolated",
        "timestamp": datetime.now().isoformat(),
        "test_run_id": str(uuid.uuid4()),
        "tests": {},
        "summary": {"passed": 0, "failed": 0, "total": 0}
    }
    
    # Test functions
    test_functions = [
        ("dependencies", test_ml_dependencies),
        ("model_loading", test_model_loading),
        ("inference_pipeline", test_inference_pipeline),
        ("video_processing", test_video_processing),
        ("detection_accuracy", test_detection_accuracy),
        ("performance_benchmarks", test_performance_benchmarks)
    ]
    
    for test_name, test_func in test_functions:
        print(f"\n🧪 Running {test_name} test...")
        try:
            test_result = test_func()
            all_results["tests"][test_name] = test_result
            all_results["summary"]["total"] += 1
            
            if test_result.get("success", False):
                all_results["summary"]["passed"] += 1
                print(f"✅ {test_name}: PASSED")
            else:
                all_results["summary"]["failed"] += 1
                print(f"❌ {test_name}: FAILED")
                if "error" in test_result:
                    print(f"   Error: {test_result['error']}")
        except Exception as e:
            all_results["tests"][test_name] = {
                "success": False,
                "error": f"Test execution failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            all_results["summary"]["failed"] += 1
            all_results["summary"]["total"] += 1
            print(f"💥 {test_name}: EXCEPTION - {str(e)}")
    
    # Calculate success rate
    success_rate = (all_results["summary"]["passed"] / all_results["summary"]["total"] * 100) if all_results["summary"]["total"] > 0 else 0
    
    # Save results
    results_file = "tests/ml_pipeline_isolated_results.json"
    Path("tests").mkdir(exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "=" * 50)
    print("🏁 ML PIPELINE ISOLATED TEST SUMMARY")
    print("=" * 50)
    print(f"Total Tests: {all_results['summary']['total']}")
    print(f"Passed: {all_results['summary']['passed']}")
    print(f"Failed: {all_results['summary']['failed']}")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Results saved to: {results_file}")
    
    if success_rate >= 80:
        print("🎉 ML Pipeline is functioning well!")
    elif success_rate >= 60:
        print("⚠️  ML Pipeline has some issues but is partially functional")
    else:
        print("🚨 ML Pipeline has significant issues")
    
    return all_results

if __name__ == "__main__":
    main()
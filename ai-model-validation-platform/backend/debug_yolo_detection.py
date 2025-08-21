#!/usr/bin/env python3
"""
Deep debugging script for YOLOv8 detection issues with child video
"""

import asyncio
import sys
import cv2
import numpy as np
from pathlib import Path
import logging
import time
import traceback
import json

# Add backend to path
sys.path.append('.')

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence verbose logs from some libraries
logging.getLogger('ultralytics').setLevel(logging.WARNING)

async def debug_video_properties(video_path):
    """Debug video file properties"""
    logger.info(f"🎬 DEBUGGING VIDEO PROPERTIES: {video_path}")
    
    try:
        # Check if file exists and basic properties
        video_file = Path(video_path)
        if not video_file.exists():
            logger.error(f"❌ Video file does not exist: {video_path}")
            return False
        
        # Get file size
        file_size = video_file.stat().st_size
        logger.info(f"📁 File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        # Try to open with OpenCV
        cap = cv2.VideoCapture(str(video_file))
        if not cap.isOpened():
            logger.error(f"❌ Cannot open video with OpenCV: {video_path}")
            return False
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0
        
        logger.info(f"🎯 Video Properties:")
        logger.info(f"   Resolution: {width}x{height}")
        logger.info(f"   FPS: {fps:.2f}")
        logger.info(f"   Total frames: {total_frames}")
        logger.info(f"   Duration: {duration:.2f} seconds")
        
        # Test reading first few frames
        frames_read = 0
        valid_frames = 0
        
        for i in range(min(10, total_frames)):
            ret, frame = cap.read()
            if ret:
                frames_read += 1
                if frame is not None and frame.size > 0:
                    valid_frames += 1
                    if i < 3:  # Log details for first 3 frames
                        logger.debug(f"   Frame {i+1}: Shape {frame.shape}, dtype {frame.dtype}, min={frame.min()}, max={frame.max()}")
            else:
                logger.warning(f"⚠️ Failed to read frame {i+1}")
                break
        
        cap.release()
        
        logger.info(f"✅ Successfully read {frames_read}/{min(10, total_frames)} frames, {valid_frames} valid")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error analyzing video: {str(e)}")
        traceback.print_exc()
        return False

async def debug_model_loading():
    """Debug YOLOv8 model loading and initialization"""
    logger.info("🤖 DEBUGGING MODEL LOADING")
    
    try:
        # Test torch availability
        try:
            import torch
            logger.info(f"✅ PyTorch available: {torch.__version__}")
            logger.info(f"   CUDA available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                logger.info(f"   CUDA version: {torch.version.cuda}")
                logger.info(f"   GPU count: {torch.cuda.device_count()}")
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            logger.info(f"   Using device: {device}")
        except ImportError as e:
            logger.error(f"❌ PyTorch not available: {e}")
            return False
        
        # Test ultralytics availability
        try:
            from ultralytics import YOLO
            logger.info("✅ Ultralytics available")
        except ImportError as e:
            logger.error(f"❌ Ultralytics not available: {e}")
            return False
        
        # Load YOLOv8 model
        logger.info("🔄 Loading YOLOv8 model...")
        model = YOLO('yolov8n.pt')  # This will download if needed
        
        # Move to device
        model.to(device)
        logger.info(f"✅ Model loaded successfully on {device}")
        
        # Test model with dummy input
        logger.info("🧪 Testing model with dummy input...")
        dummy_input = torch.randn(1, 3, 640, 640).to(device)
        with torch.no_grad():
            try:
                output = model.model(dummy_input)
                logger.info(f"✅ Model forward pass successful: output shape {len(output) if hasattr(output, '__len__') else 'single tensor'}")
            except Exception as e:
                logger.error(f"❌ Model forward pass failed: {e}")
                return False
        
        # Test model prediction interface
        logger.info("🧪 Testing model prediction interface...")
        dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        results = model(dummy_frame, verbose=False, conf=0.01)
        logger.info(f"✅ Model prediction interface works: {len(results)} result objects")
        
        # Analyze model classes
        if hasattr(model, 'names') and model.names:
            logger.info(f"🏷️ Model classes available: {len(model.names)}")
            # Show first 10 classes
            class_sample = {k: v for k, v in list(model.names.items())[:10]}
            logger.info(f"   First 10 classes: {class_sample}")
            
            # Check for 'person' class
            person_classes = {k: v for k, v in model.names.items() if 'person' in v.lower()}
            if person_classes:
                logger.info(f"✅ 'Person' classes found: {person_classes}")
            else:
                logger.warning("⚠️ No 'person' classes found in model!")
        else:
            logger.warning("⚠️ Model class names not accessible")
        
        return model
        
    except Exception as e:
        logger.error(f"❌ Error loading model: {str(e)}")
        traceback.print_exc()
        return False

async def debug_frame_preprocessing(frame):
    """Debug frame preprocessing pipeline"""
    logger.info("🔧 DEBUGGING FRAME PREPROCESSING")
    
    try:
        # Original frame info
        logger.info(f"Original frame: shape={frame.shape}, dtype={frame.dtype}")
        logger.info(f"   Min/Max values: {frame.min()} / {frame.max()}")
        logger.info(f"   Mean values per channel: {frame.mean(axis=(0,1))}")
        
        # Step 1: Resize to target size (640x640)
        target_size = (640, 640)
        resized = cv2.resize(frame, target_size)
        logger.info(f"After resize: shape={resized.shape}")
        
        # Step 2: Normalize pixel values
        normalized = resized.astype(np.float32) / 255.0
        logger.info(f"After normalize: dtype={normalized.dtype}, min/max={normalized.min()}/{normalized.max()}")
        
        # Step 3: Convert BGR to RGB
        rgb_frame = cv2.cvtColor(normalized, cv2.COLOR_BGR2RGB)
        logger.info(f"After BGR->RGB: shape={rgb_frame.shape}")
        logger.info(f"   Mean values per channel (RGB): {rgb_frame.mean(axis=(0,1))}")
        
        # Alternative preprocessing (what YOLOv8 might expect)
        yolo_frame = resized  # Keep as uint8, BGR
        logger.info(f"Alternative YOLO frame: shape={yolo_frame.shape}, dtype={yolo_frame.dtype}")
        
        return rgb_frame, yolo_frame
        
    except Exception as e:
        logger.error(f"❌ Error in preprocessing: {str(e)}")
        traceback.print_exc()
        return None, None

async def debug_model_inference(model, frame, original_frame):
    """Debug model inference with multiple configurations"""
    logger.info("🔮 DEBUGGING MODEL INFERENCE")
    
    try:
        # Test with different confidence thresholds
        conf_thresholds = [0.01, 0.1, 0.25, 0.35, 0.5, 0.7]
        
        for conf in conf_thresholds:
            logger.info(f"🎯 Testing with confidence threshold: {conf}")
            
            # Run inference with original frame (BGR, uint8 - what YOLOv8 expects)
            results = model(original_frame, verbose=False, conf=conf)
            
            total_detections = 0
            person_detections = 0
            all_classes = set()
            
            for r in results:
                if r.boxes is not None:
                    boxes = r.boxes
                    total_detections += len(boxes)
                    
                    for box in boxes:
                        cls_id = int(box.cls[0].cpu().numpy())
                        confidence = float(box.conf[0].cpu().numpy())
                        all_classes.add(cls_id)
                        
                        # Check if it's a person (class 0 in COCO)
                        if cls_id == 0:  # person class
                            person_detections += 1
                            xyxy = box.xyxy[0].cpu().numpy()
                            logger.info(f"   ✅ PERSON detected: conf={confidence:.3f}, bbox={xyxy}")
                        
                        # Log all detections for very low confidence
                        if conf <= 0.01:
                            class_name = model.names.get(cls_id, f"class_{cls_id}")
                            logger.debug(f"   Detection: {class_name} (id={cls_id}), conf={confidence:.3f}")
            
            logger.info(f"   📊 Total detections: {total_detections}, Person detections: {person_detections}")
            logger.info(f"   📊 Classes detected: {sorted(all_classes)}")
            
            if person_detections > 0:
                logger.info(f"🎉 FOUND PERSONS at confidence {conf}!")
                return True
        
        logger.warning("❌ NO PERSON DETECTIONS FOUND at any confidence level!")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error in inference: {str(e)}")
        traceback.print_exc()
        return False

async def debug_specific_frames(video_path, model, frame_indices=None):
    """Debug specific frames from the video"""
    logger.info("🎞️ DEBUGGING SPECIFIC FRAMES")
    
    if frame_indices is None:
        frame_indices = [1, 30, 60, 90, 120]  # Sample frames
    
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("❌ Cannot open video for frame analysis")
            return False
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Save debug frames
        debug_dir = Path('./debug_frames')
        debug_dir.mkdir(exist_ok=True)
        
        found_persons = 0
        
        for frame_idx in frame_indices:
            if frame_idx >= total_frames:
                continue
                
            logger.info(f"🎯 Analyzing frame {frame_idx}/{total_frames}")
            
            # Seek to frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret or frame is None:
                logger.warning(f"⚠️ Could not read frame {frame_idx}")
                continue
            
            # Save original frame for inspection
            frame_path = debug_dir / f"frame_{frame_idx:04d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            logger.debug(f"💾 Saved frame to: {frame_path}")
            
            # Debug preprocessing
            processed_rgb, processed_yolo = await debug_frame_preprocessing(frame)
            
            # Run inference
            logger.info(f"🔮 Running inference on frame {frame_idx}...")
            results = model(frame, verbose=False, conf=0.01)  # Very low confidence
            
            frame_detections = 0
            frame_persons = 0
            
            for r in results:
                if r.boxes is not None:
                    for box in r.boxes:
                        cls_id = int(box.cls[0].cpu().numpy())
                        confidence = float(box.conf[0].cpu().numpy())
                        xyxy = box.xyxy[0].cpu().numpy()
                        
                        frame_detections += 1
                        
                        if cls_id == 0:  # person
                            frame_persons += 1
                            found_persons += 1
                            logger.info(f"   ✅ PERSON in frame {frame_idx}: conf={confidence:.3f}")
                            
                            # Save annotated frame
                            annotated = frame.copy()
                            x1, y1, x2, y2 = map(int, xyxy)
                            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(annotated, f"Person {confidence:.2f}", (x1, y1-10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            
                            annotated_path = debug_dir / f"frame_{frame_idx:04d}_detected.jpg"
                            cv2.imwrite(str(annotated_path), annotated)
                            logger.info(f"💾 Saved annotated frame to: {annotated_path}")
            
            logger.info(f"   📊 Frame {frame_idx}: {frame_detections} total, {frame_persons} persons")
        
        cap.release()
        
        logger.info(f"🎉 SUMMARY: Found {found_persons} person detections across sampled frames")
        return found_persons > 0
        
    except Exception as e:
        logger.error(f"❌ Error in frame analysis: {str(e)}")
        traceback.print_exc()
        return False

async def debug_detection_pipeline():
    """Debug the full detection pipeline"""
    logger.info("🔧 DEBUGGING DETECTION PIPELINE")
    
    try:
        from services.detection_pipeline_service import DetectionPipeline
        
        # Initialize pipeline
        pipeline = DetectionPipeline()
        await pipeline.initialize()
        logger.info("✅ Pipeline initialized")
        
        # Check active model
        model = await pipeline.model_registry.get_active_model()
        logger.info(f"✅ Active model: {type(model).__name__}")
        
        # Test with the actual video
        video_path = "/home/user/Testing/ai-model-validation-platform/backend/uploads/child-1-1-1.mp4"
        
        # Create config with very low confidence
        config = {"confidence_threshold": 0.01}
        
        logger.info("🎬 Testing pipeline.process_video() method...")
        detections = await pipeline.process_video(video_path, config)
        
        logger.info(f"📊 Pipeline returned {len(detections)} detections")
        
        # Analyze detections
        if detections:
            for i, det in enumerate(detections[:5]):  # Show first 5
                logger.info(f"   Detection {i+1}: {det}")
        else:
            logger.warning("❌ NO DETECTIONS from pipeline!")
        
        return len(detections) > 0
        
    except Exception as e:
        logger.error(f"❌ Error in pipeline debug: {str(e)}")
        traceback.print_exc()
        return False

async def main():
    """Main debugging function"""
    logger.info("🚀 STARTING DEEP YOLOV8 DETECTION DEBUGGING")
    logger.info("=" * 80)
    
    video_path = "/home/user/Testing/ai-model-validation-platform/backend/uploads/child-1-1-1.mp4"
    
    success_count = 0
    total_tests = 6
    
    # 1. Debug video properties
    logger.info("\n" + "=" * 80)
    if await debug_video_properties(video_path):
        success_count += 1
    
    # 2. Debug model loading
    logger.info("\n" + "=" * 80)
    model = await debug_model_loading()
    if model:
        success_count += 1
    else:
        logger.error("❌ Cannot continue without working model")
        return False
    
    # 3. Read and debug first frame
    logger.info("\n" + "=" * 80)
    try:
        cap = cv2.VideoCapture(video_path)
        ret, first_frame = cap.read()
        cap.release()
        
        if ret and first_frame is not None:
            logger.info("✅ Successfully read first frame")
            
            # 4. Debug preprocessing
            logger.info("\n" + "=" * 80)
            processed_rgb, processed_yolo = await debug_frame_preprocessing(first_frame)
            if processed_rgb is not None and processed_yolo is not None:
                success_count += 1
            
            # 5. Debug inference on first frame
            logger.info("\n" + "=" * 80)
            if await debug_model_inference(model, processed_rgb, first_frame):
                success_count += 1
        else:
            logger.error("❌ Cannot read first frame")
    except Exception as e:
        logger.error(f"❌ Error reading frame: {e}")
    
    # 6. Debug specific frames
    logger.info("\n" + "=" * 80)
    if await debug_specific_frames(video_path, model):
        success_count += 1
    
    # 7. Debug detection pipeline
    logger.info("\n" + "=" * 80)
    if await debug_detection_pipeline():
        success_count += 1
        total_tests += 1
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("🎯 DEBUGGING SUMMARY")
    logger.info("=" * 80)
    logger.info(f"✅ Passed: {success_count}/{total_tests} tests")
    
    if success_count < total_tests:
        logger.error("❌ Some tests failed - check logs above for details")
        
        # Provide recommendations
        logger.info("\n🔧 TROUBLESHOOTING RECOMMENDATIONS:")
        logger.info("1. Check if video contains clearly visible people/children")
        logger.info("2. Try different confidence thresholds (0.01 - 0.7)")
        logger.info("3. Verify YOLOv8 model is properly loaded and working")
        logger.info("4. Check frame preprocessing doesn't corrupt the image")
        logger.info("5. Ensure COCO class 0 (person) is being detected")
        logger.info("6. Look at debug_frames/ directory for visual inspection")
    else:
        logger.info("🎉 All tests passed! Detection should work.")
    
    return success_count == total_tests

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
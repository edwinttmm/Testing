#!/usr/bin/env python3
"""
Enhanced VRU Detection Service
Addresses fundamental detection issues and provides multiple detection strategies.
"""

import logging
import numpy as np
import cv2
import time
import uuid
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class EnhancedDetection:
    class_label: str
    confidence: float
    x: float
    y: float
    width: float
    height: float
    frame_number: int
    timestamp: float
    detection_id: str
    method: str  # 'yolo', 'opencv', 'hybrid'

class EnhancedVRUDetector:
    """Enhanced VRU detector with multiple strategies"""
    
    def __init__(self):
        self.yolo_model = None
        self.opencv_detector = None
        self.detection_strategies = ['opencv_fallback', 'yolo_enhanced', 'hybrid']
        
    async def initialize(self):
        """Initialize all detection methods"""
        try:
            # Try to load YOLOv11l
            await self._initialize_yolo()
        except Exception as e:
            logger.warning(f"YOLO initialization failed: {e}")
            
        # Initialize OpenCV-based detection as fallback
        self._initialize_opencv_detector()
        
    async def _initialize_yolo(self):
        """Initialize YOLO model with better error handling"""
        try:
            from ultralytics import YOLO
            import torch
            
            # Use a more reliable model
            logger.info("🚀 Loading YOLOv8n (faster, more reliable than YOLOv11l)...")
            self.yolo_model = YOLO('yolov8n.pt')  # Faster, more stable
            
            # Test the model
            test_frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            results = self.yolo_model(test_frame, conf=0.1, verbose=False)
            
            logger.info("✅ YOLO model test successful")
            
        except Exception as e:
            logger.error(f"❌ YOLO initialization failed: {e}")
            self.yolo_model = None
            
    def _initialize_opencv_detector(self):
        """Initialize OpenCV-based people detector as fallback"""
        try:
            # Initialize HOG people detector
            self.opencv_detector = cv2.HOGDescriptor()
            self.opencv_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            logger.info("✅ OpenCV HOG people detector initialized")
            
        except Exception as e:
            logger.error(f"❌ OpenCV detector initialization failed: {e}")
            self.opencv_detector = None
    
    async def detect_vru_objects(self, frame: np.ndarray, strategy: str = 'hybrid') -> List[EnhancedDetection]:
        """Detect VRU objects using specified strategy"""
        
        if strategy == 'yolo_enhanced' and self.yolo_model:
            return await self._detect_with_yolo(frame)
        elif strategy == 'opencv_fallback' and self.opencv_detector:
            return self._detect_with_opencv(frame)
        elif strategy == 'hybrid':
            return await self._detect_hybrid(frame)
        else:
            logger.warning(f"Strategy {strategy} not available, using fallback")
            return self._detect_with_opencv(frame) if self.opencv_detector else []
    
    async def _detect_with_yolo(self, frame: np.ndarray) -> List[EnhancedDetection]:
        """Enhanced YOLO detection with better preprocessing"""
        detections = []
        
        try:
            # Enhanced preprocessing for better YOLO performance
            if frame.shape[2] == 3:  # BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
                
            # Run inference with multiple confidence levels
            results = self.yolo_model(frame_rgb, conf=0.01, verbose=False)  # Very low threshold
            
            for r in results:
                if r.boxes is not None:
                    logger.debug(f"YOLO found {len(r.boxes)} raw detections")
                    
                    for box in r.boxes:
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        xyxy = box.xyxy[0].cpu().numpy()
                        
                        # Map COCO classes to VRU
                        vru_mapping = {0: 'pedestrian', 1: 'cyclist', 2: 'motorcyclist'}
                        if cls in vru_mapping:
                            detection = EnhancedDetection(
                                class_label=vru_mapping[cls],
                                confidence=conf,
                                x=float(xyxy[0]),
                                y=float(xyxy[1]),
                                width=float(xyxy[2] - xyxy[0]),
                                height=float(xyxy[3] - xyxy[1]),
                                frame_number=0,
                                timestamp=time.time(),
                                detection_id=str(uuid.uuid4()),
                                method='yolo'
                            )
                            detections.append(detection)
                            logger.info(f"🎯 YOLO detection: {vru_mapping[cls]} conf={conf:.3f}")
                
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            
        return detections
    
    def _detect_with_opencv(self, frame: np.ndarray) -> List[EnhancedDetection]:
        """OpenCV HOG-based people detection"""
        detections = []
        
        try:
            # Convert to grayscale for HOG
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect people using HOG
            (rects, weights) = self.opencv_detector.detectMultiScale(
                gray,
                winStride=(4, 4),
                padding=(8, 8),
                scale=1.05,
                hitThreshold=0.0  # Lower threshold for better detection
            )
            
            logger.debug(f"OpenCV HOG found {len(rects)} potential people")
            
            for i, (x, y, w, h) in enumerate(rects):
                confidence = float(weights[i]) if i < len(weights) else 0.5
                
                # Normalize confidence to 0-1 range
                normalized_conf = min(1.0, max(0.0, (confidence + 1.0) / 2.0))
                
                if normalized_conf > 0.3:  # Basic confidence filter
                    detection = EnhancedDetection(
                        class_label='pedestrian',
                        confidence=normalized_conf,
                        x=float(x),
                        y=float(y),
                        width=float(w),
                        height=float(h),
                        frame_number=0,
                        timestamp=time.time(),
                        detection_id=str(uuid.uuid4()),
                        method='opencv'
                    )
                    detections.append(detection)
                    logger.info(f"🎯 OpenCV detection: pedestrian conf={normalized_conf:.3f}")
                    
        except Exception as e:
            logger.error(f"OpenCV detection failed: {e}")
            
        return detections
    
    async def _detect_hybrid(self, frame: np.ndarray) -> List[EnhancedDetection]:
        """Hybrid detection using both YOLO and OpenCV"""
        all_detections = []
        
        # Try YOLO first
        if self.yolo_model:
            yolo_detections = await self._detect_with_yolo(frame)
            all_detections.extend(yolo_detections)
            
        # If YOLO found nothing, use OpenCV fallback
        if len(all_detections) == 0 and self.opencv_detector:
            logger.info("🔄 YOLO found nothing, falling back to OpenCV detection")
            opencv_detections = self._detect_with_opencv(frame)
            all_detections.extend(opencv_detections)
            
        return all_detections

class QuickTestRunner:
    """Quick test runner for detection strategies"""
    
    @staticmethod
    async def test_detection_methods():
        """Test all detection methods with sample content"""
        logger.info("🧪 Testing enhanced detection methods...")
        
        # Create simple test frame
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        test_frame[200:400, 300:400] = [100, 150, 200]  # Simple rectangular "person"
        
        detector = EnhancedVRUDetector()
        await detector.initialize()
        
        # Test each strategy
        strategies = ['opencv_fallback', 'yolo_enhanced', 'hybrid']
        results = {}
        
        for strategy in strategies:
            logger.info(f"Testing strategy: {strategy}")
            detections = await detector.detect_vru_objects(test_frame, strategy)
            results[strategy] = len(detections)
            logger.info(f"  {strategy}: {len(detections)} detections")
            
        return results

# Integration function for existing pipeline
async def get_enhanced_detections(frame: np.ndarray) -> List[Dict]:
    """Enhanced detection function that can replace the existing one"""
    detector = EnhancedVRUDetector()
    await detector.initialize()
    
    detections = await detector.detect_vru_objects(frame, 'hybrid')
    
    # Convert to API format
    api_detections = []
    for detection in detections:
        api_detection = {
            "id": detection.detection_id,
            "frame_number": detection.frame_number,
            "timestamp": detection.timestamp,
            "class_label": detection.class_label,
            "confidence": detection.confidence,
            "bounding_box": {
                "x": detection.x,
                "y": detection.y,
                "width": detection.width,
                "height": detection.height
            },
            "vru_type": detection.class_label,
            "detection_method": detection.method
        }
        api_detections.append(api_detection)
    
    return api_detections

if __name__ == "__main__":
    # Quick test
    import asyncio
    asyncio.run(QuickTestRunner.test_detection_methods())
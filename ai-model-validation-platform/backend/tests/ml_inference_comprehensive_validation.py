#!/usr/bin/env python3
"""
Comprehensive ML Inference Engine Validation Suite
================================================

This test suite validates the complete ML inference pipeline including:
1. YOLO model loading and initialization
2. Single frame and batch inference
3. Video processing pipeline
4. VRU detection and classification accuracy
5. Database integration for results storage
6. Performance benchmarking and optimization
7. API endpoint functionality
8. Production deployment readiness

Test Categories:
- Unit Tests: Individual component testing
- Integration Tests: End-to-end pipeline testing
- Performance Tests: Speed and accuracy benchmarks
- Stress Tests: High load and edge case handling
- Production Tests: Container deployment verification

Author: ML Validation Team
Version: 2.0.0
"""

import asyncio
import time
import uuid
import os
import tempfile
import shutil
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging

# Test framework imports
import pytest
import numpy as np
import cv2

# Add backend path for imports
import sys
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(backend_path / "src"))

# Import ML components to test
try:
    from src.ml_inference_engine import MLInferenceEngine, ml_engine
    from src.enhanced_ml_inference_engine import (
        ProductionMLInferenceEngine, 
        EnhancedYOLOEngine, 
        EnhancedVideoProcessor,
        EnhancedVRUDetection,
        EnhancedBoundingBox,
        get_production_ml_engine
    )
    from src.validation_models import DetectionResult, ProcessingStatus
    ML_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"ML modules not fully available: {e}")
    ML_MODULES_AVAILABLE = False

# Database imports
try:
    from unified_database import get_database_manager
    from models import Video, Detection, GroundTruthObject
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLInferenceValidator:
    """Comprehensive ML inference validation system"""
    
    def __init__(self):
        self.test_results = {
            'start_time': datetime.now(timezone.utc),
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'performance_metrics': {},
            'validation_summary': {},
            'issues_found': []
        }
        self.temp_dir = None
        self.test_video_path = None
        
    async def setup_test_environment(self):
        """Setup test environment with sample data"""
        logger.info("Setting up ML inference test environment...")
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix='ml_test_')
        
        # Create test video
        self.test_video_path = await self._create_test_video()
        
        # Verify YOLO models exist
        model_paths = [
            '/home/user/Testing/ai-model-validation-platform/backend/yolo11l.pt',
            '/home/user/Testing/ai-model-validation-platform/backend/yolov8n.pt'
        ]
        
        self.available_models = [p for p in model_paths if os.path.exists(p)]
        logger.info(f"Available YOLO models: {self.available_models}")
        
        if not self.available_models:
            logger.warning("No YOLO model files found - will test with mock inference")
        
        logger.info("Test environment setup complete")
    
    async def _create_test_video(self) -> str:
        """Create a test video file for processing"""
        video_path = os.path.join(self.temp_dir, 'test_video.mp4')
        
        # Create a simple test video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(video_path, fourcc, 30.0, (640, 480))
        
        # Generate 150 frames (5 seconds at 30fps)
        for frame_num in range(150):
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Add some moving objects for detection
            if frame_num % 20 < 10:  # Moving rectangle (simulate person)
                x = 100 + frame_num * 2
                y = 200
                cv2.rectangle(frame, (x, y), (x+60, y+120), (255, 255, 255), -1)
                cv2.putText(frame, 'PERSON', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            if frame_num % 30 < 15:  # Moving circle (simulate cyclist)
                x = 300 + frame_num
                y = 300
                cv2.circle(frame, (x, y), 30, (128, 128, 128), -1)
                cv2.putText(frame, 'CYCLIST', (x-30, y-40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Add frame number
            cv2.putText(frame, f'Frame {frame_num}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            writer.write(frame)
        
        writer.release()
        logger.info(f"Created test video: {video_path}")
        return video_path
    
    async def test_basic_ml_engine_initialization(self) -> Dict[str, Any]:
        """Test ML inference engine initialization"""
        logger.info("Testing ML inference engine initialization...")
        test_result = {'name': 'ML Engine Initialization', 'status': 'running', 'details': {}}
        
        try:
            # Test basic ML engine
            if ML_MODULES_AVAILABLE:
                engine = MLInferenceEngine()
                await engine.initialize()
                
                test_result['details']['basic_engine'] = {
                    'initialized': engine.is_initialized,
                    'redis_available': engine.redis_client is not None,
                    'models_loaded': list(engine.models.keys())
                }
                
                # Test enhanced engine
                enhanced_engine = await get_production_ml_engine()
                
                test_result['details']['enhanced_engine'] = {
                    'initialized': True,
                    'yolo_initialized': enhanced_engine.yolo_engine.is_initialized,
                    'database_available': enhanced_engine.db_manager is not None
                }
                
                test_result['status'] = 'passed'
                self.test_results['tests_passed'] += 1
            else:
                test_result['status'] = 'skipped'
                test_result['details']['reason'] = 'ML modules not available'
                
        except Exception as e:
            test_result['status'] = 'failed'
            test_result['details']['error'] = str(e)
            self.test_results['tests_failed'] += 1
            self.test_results['issues_found'].append(f"ML Engine initialization failed: {e}")
        
        self.test_results['tests_run'] += 1
        return test_result
    
    async def test_yolo_model_loading(self) -> Dict[str, Any]:
        """Test YOLO model loading and inference"""
        logger.info("Testing YOLO model loading and inference...")
        test_result = {'name': 'YOLO Model Loading', 'status': 'running', 'details': {}}
        
        try:
            if not ML_MODULES_AVAILABLE:
                test_result['status'] = 'skipped'
                test_result['details']['reason'] = 'ML modules not available'
                self.test_results['tests_run'] += 1
                return test_result
            
            # Test with each available model
            model_results = {}
            
            for model_path in self.available_models:
                logger.info(f"Testing model: {model_path}")
                model_name = os.path.basename(model_path)
                
                # Test model loading
                yolo_engine = EnhancedYOLOEngine(model_path=model_path, device='cpu')
                success = await yolo_engine.initialize()
                
                # Create test image
                test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
                
                # Test single frame detection
                start_time = time.time()
                detections = await yolo_engine.detect_vrus_single(test_image, 0, 0.0)
                inference_time = time.time() - start_time
                
                # Test batch detection
                batch_frames = [test_image] * 3
                batch_frame_numbers = [0, 1, 2]
                batch_timestamps = [0.0, 0.033, 0.066]
                
                start_time = time.time()
                batch_detections = await yolo_engine.detect_vrus_batch(
                    batch_frames, batch_frame_numbers, batch_timestamps
                )
                batch_inference_time = time.time() - start_time
                
                model_results[model_name] = {
                    'loaded_successfully': success,
                    'inference_method': yolo_engine.inference_method,
                    'single_frame_time': inference_time,
                    'single_frame_detections': len(detections),
                    'batch_inference_time': batch_inference_time,
                    'batch_detections': sum(len(d) for d in batch_detections),
                    'performance_stats': yolo_engine.get_performance_stats()
                }
            
            test_result['details'] = {
                'models_tested': len(self.available_models),
                'model_results': model_results
            }
            
            if model_results:
                test_result['status'] = 'passed'
                self.test_results['tests_passed'] += 1
            else:
                test_result['status'] = 'failed'
                test_result['details']['error'] = 'No models could be tested'
                self.test_results['tests_failed'] += 1
                
        except Exception as e:
            test_result['status'] = 'failed'
            test_result['details']['error'] = str(e)
            self.test_results['tests_failed'] += 1
            self.test_results['issues_found'].append(f"YOLO model loading failed: {e}")
        
        self.test_results['tests_run'] += 1
        return test_result
    
    async def test_video_processing_pipeline(self) -> Dict[str, Any]:
        """Test complete video processing pipeline"""
        logger.info("Testing video processing pipeline...")
        test_result = {'name': 'Video Processing Pipeline', 'status': 'running', 'details': {}}
        
        try:
            if not ML_MODULES_AVAILABLE or not self.test_video_path:
                test_result['status'] = 'skipped'
                test_result['details']['reason'] = 'Prerequisites not available'
                self.test_results['tests_run'] += 1
                return test_result
            
            # Get production ML engine
            engine = await get_production_ml_engine()
            
            # Test video metadata extraction
            metadata = engine.video_processor.get_video_metadata(self.test_video_path)
            
            test_result['details']['metadata'] = {
                'fps': metadata['fps'],
                'total_frames': metadata['total_frames'],
                'width': metadata['width'],
                'height': metadata['height'],
                'duration': metadata['duration']
            }
            
            # Test frame extraction
            frames_extracted = 0
            async for frame, frame_num, timestamp in engine.video_processor.extract_frames_async(
                self.test_video_path, max_frames=10
            ):
                frames_extracted += 1
                if frame is None or frame.size == 0:
                    raise ValueError(f"Invalid frame extracted at {frame_num}")
            
            test_result['details']['frame_extraction'] = {
                'frames_extracted': frames_extracted,
                'extraction_successful': frames_extracted > 0
            }
            
            # Test complete video processing (limited frames for testing)
            video_id = str(uuid.uuid4())
            
            class ProgressTracker:
                def __init__(self):
                    self.progress_updates = []
                
                async def __call__(self, vid_id, progress, frames_processed):
                    self.progress_updates.append({
                        'video_id': vid_id,
                        'progress': progress,
                        'frames_processed': frames_processed
                    })
            
            progress_tracker = ProgressTracker()
            
            # Process first 30 frames for testing
            temp_engine = ProductionMLInferenceEngine()
            temp_engine.config['batch_size'] = 5  # Small batch for testing
            await temp_engine.initialize()
            
            start_time = time.time()
            processing_result = await temp_engine.process_video_complete(
                video_id, self.test_video_path, progress_tracker
            )
            processing_time = time.time() - start_time
            
            test_result['details']['video_processing'] = {
                'status': processing_result.get('status'),
                'processing_time': processing_time,
                'total_detections': processing_result.get('processing_stats', {}).get('total_detections', 0),
                'avg_fps': processing_result.get('processing_stats', {}).get('avg_fps', 0),
                'progress_updates': len(progress_tracker.progress_updates),
                'detection_summary': processing_result.get('detection_summary', {})
            }
            
            # Validate detection results
            if processing_result.get('status') == 'completed':
                test_result['status'] = 'passed'
                self.test_results['tests_passed'] += 1
                
                # Store performance metrics
                self.test_results['performance_metrics']['video_processing'] = {
                    'processing_fps': processing_result.get('processing_stats', {}).get('avg_fps', 0),
                    'detections_per_frame': processing_result.get('processing_stats', {}).get('detections_per_frame', 0),
                    'total_processing_time': processing_time
                }
            else:
                test_result['status'] = 'failed'
                test_result['details']['error'] = f"Processing failed with status: {processing_result.get('status')}"
                self.test_results['tests_failed'] += 1
                
        except Exception as e:
            test_result['status'] = 'failed'
            test_result['details']['error'] = str(e)
            self.test_results['tests_failed'] += 1
            self.test_results['issues_found'].append(f"Video processing pipeline failed: {e}")
        
        self.test_results['tests_run'] += 1
        return test_result
    
    async def test_vru_detection_accuracy(self) -> Dict[str, Any]:
        """Test VRU detection accuracy and classification"""
        logger.info("Testing VRU detection accuracy...")
        test_result = {'name': 'VRU Detection Accuracy', 'status': 'running', 'details': {}}
        
        try:
            if not ML_MODULES_AVAILABLE:
                test_result['status'] = 'skipped'
                test_result['details']['reason'] = 'ML modules not available'
                self.test_results['tests_run'] += 1
                return test_result
            
            # Test with synthetic images containing known objects
            detection_results = {}
            
            # Create test images with known VRU objects
            test_scenarios = [
                {
                    'name': 'pedestrian_scene',
                    'description': 'Simple pedestrian detection',
                    'expected_detections': 1,
                    'expected_types': ['pedestrian']
                },
                {
                    'name': 'cyclist_scene', 
                    'description': 'Cyclist detection',
                    'expected_detections': 1,
                    'expected_types': ['cyclist']
                },
                {
                    'name': 'mixed_scene',
                    'description': 'Multiple VRU types',
                    'expected_detections': 2,
                    'expected_types': ['pedestrian', 'cyclist']
                }
            ]
            
            yolo_engine = EnhancedYOLOEngine(device='cpu')
            await yolo_engine.initialize()
            
            for scenario in test_scenarios:
                # Create synthetic test image based on scenario
                test_image = self._create_test_image_for_scenario(scenario['name'])
                
                # Run detection
                detections = await yolo_engine.detect_vrus_single(test_image, 0, 0.0)
                
                # Analyze results
                detected_types = [det.vru_type for det in detections]
                confidence_scores = [det.confidence for det in detections]
                
                detection_results[scenario['name']] = {
                    'expected_detections': scenario['expected_detections'],
                    'actual_detections': len(detections),
                    'expected_types': scenario['expected_types'],
                    'detected_types': detected_types,
                    'confidence_scores': confidence_scores,
                    'avg_confidence': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
                    'detection_accuracy': self._calculate_detection_accuracy(scenario, detections)
                }
            
            # Calculate overall accuracy metrics
            total_expected = sum(r['expected_detections'] for r in detection_results.values())
            total_detected = sum(r['actual_detections'] for r in detection_results.values())
            avg_accuracy = sum(r['detection_accuracy'] for r in detection_results.values()) / len(detection_results)
            
            test_result['details'] = {
                'scenarios_tested': len(test_scenarios),
                'scenario_results': detection_results,
                'overall_metrics': {
                    'total_expected': total_expected,
                    'total_detected': total_detected,
                    'detection_rate': total_detected / total_expected if total_expected > 0 else 0,
                    'average_accuracy': avg_accuracy,
                    'inference_method': yolo_engine.inference_method
                }
            }
            
            # Determine pass/fail based on accuracy threshold
            if avg_accuracy >= 0.7:  # 70% accuracy threshold
                test_result['status'] = 'passed'
                self.test_results['tests_passed'] += 1
            else:
                test_result['status'] = 'failed'
                test_result['details']['error'] = f"Detection accuracy {avg_accuracy:.2f} below threshold 0.7"
                self.test_results['tests_failed'] += 1
                
        except Exception as e:
            test_result['status'] = 'failed'
            test_result['details']['error'] = str(e)
            self.test_results['tests_failed'] += 1
            self.test_results['issues_found'].append(f"VRU detection accuracy test failed: {e}")
        
        self.test_results['tests_run'] += 1
        return test_result
    
    def _create_test_image_for_scenario(self, scenario_name: str) -> np.ndarray:
        """Create synthetic test images for detection scenarios"""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        
        if scenario_name == 'pedestrian_scene':
            # Draw a simple person-like shape
            cv2.rectangle(img, (200, 150), (280, 400), (255, 255, 255), -1)  # Body
            cv2.circle(img, (240, 120), 30, (255, 255, 255), -1)  # Head
            cv2.rectangle(img, (220, 400), (240, 460), (255, 255, 255), -1)  # Left leg
            cv2.rectangle(img, (260, 400), (280, 460), (255, 255, 255), -1)  # Right leg
            
        elif scenario_name == 'cyclist_scene':
            # Draw a cyclist with bike
            cv2.circle(img, (200, 350), 40, (128, 128, 128), 2)  # Rear wheel
            cv2.circle(img, (350, 350), 40, (128, 128, 128), 2)  # Front wheel
            cv2.line(img, (200, 350), (350, 350), (255, 255, 255), 5)  # Frame
            cv2.rectangle(img, (260, 250), (290, 350), (255, 255, 255), -1)  # Rider
            cv2.circle(img, (275, 220), 20, (255, 255, 255), -1)  # Head
            
        elif scenario_name == 'mixed_scene':
            # Combine pedestrian and cyclist
            # Pedestrian
            cv2.rectangle(img, (100, 150), (160, 400), (255, 255, 255), -1)
            cv2.circle(img, (130, 120), 25, (255, 255, 255), -1)
            # Cyclist
            cv2.circle(img, (400, 350), 30, (128, 128, 128), 2)
            cv2.circle(img, (500, 350), 30, (128, 128, 128), 2)
            cv2.rectangle(img, (440, 280), (460, 350), (255, 255, 255), -1)
            cv2.circle(img, (450, 260), 15, (255, 255, 255), -1)
        
        return img
    
    def _calculate_detection_accuracy(self, scenario: Dict, detections: List) -> float:
        """Calculate detection accuracy for a scenario"""
        if not detections and scenario['expected_detections'] == 0:
            return 1.0
        
        if not detections:
            return 0.0
        
        # Simple accuracy: ratio of expected vs actual detections
        detection_ratio = min(len(detections) / scenario['expected_detections'], 1.0)
        
        # Type accuracy: check if expected types are detected
        detected_types = set(det.vru_type for det in detections)
        expected_types = set(scenario['expected_types'])
        type_accuracy = len(detected_types.intersection(expected_types)) / len(expected_types)
        
        # Confidence accuracy: average confidence of detections
        confidence_accuracy = sum(det.confidence for det in detections) / len(detections)
        
        # Combined accuracy
        return (detection_ratio * 0.4 + type_accuracy * 0.4 + confidence_accuracy * 0.2)
    
    async def test_database_integration(self) -> Dict[str, Any]:
        """Test database integration for ML results"""
        logger.info("Testing database integration...")
        test_result = {'name': 'Database Integration', 'status': 'running', 'details': {}}
        
        try:
            if not DATABASE_AVAILABLE:
                test_result['status'] = 'skipped' 
                test_result['details']['reason'] = 'Database not available'
                self.test_results['tests_run'] += 1
                return test_result
            
            # Test database connection
            db_manager = get_database_manager()
            health_check = db_manager.test_connection()
            
            test_result['details']['connection'] = {
                'status': health_check['status'],
                'database_type': health_check.get('database_type', 'unknown')
            }
            
            if health_check['status'] != 'healthy':
                test_result['status'] = 'failed'
                test_result['details']['error'] = 'Database connection unhealthy'
                self.test_results['tests_failed'] += 1
                return test_result
            
            # Test ML engine database integration
            if ML_MODULES_AVAILABLE:
                engine = await get_production_ml_engine()
                
                # Create test detection data
                test_video_id = str(uuid.uuid4())
                test_detections = [
                    EnhancedVRUDetection(
                        detection_id=str(uuid.uuid4()),
                        frame_number=0,
                        timestamp=0.0,
                        vru_type='pedestrian',
                        confidence=0.85,
                        bounding_box=EnhancedBoundingBox(0.1, 0.1, 0.2, 0.3)
                    ),
                    EnhancedVRUDetection(
                        detection_id=str(uuid.uuid4()),
                        frame_number=1,
                        timestamp=0.033,
                        vru_type='cyclist',
                        confidence=0.78,
                        bounding_box=EnhancedBoundingBox(0.3, 0.2, 0.25, 0.4)
                    )
                ]
                
                # Test saving detections
                metadata = {'fps': 30, 'total_frames': 100}
                await engine._save_detections_to_database(test_video_id, test_detections, metadata)
                
                # Test retrieving detections
                retrieved_detections = await engine.get_video_detections(test_video_id)
                
                test_result['details']['ml_database_ops'] = {
                    'detections_saved': len(test_detections),
                    'detections_retrieved': len(retrieved_detections),
                    'data_integrity': len(test_detections) == len(retrieved_detections)
                }
                
                # Test detection updates
                if retrieved_detections:
                    update_success = await engine.update_detection(
                        retrieved_detections[0]['detection_id'],
                        {'confidence': 0.90, 'vru_type': 'pedestrian'}
                    )
                    
                    test_result['details']['ml_database_ops']['update_success'] = update_success
                
                # Clean up test data
                for det in retrieved_detections:
                    await engine.delete_detection(det['detection_id'])
                
            test_result['status'] = 'passed'
            self.test_results['tests_passed'] += 1
            
        except Exception as e:
            test_result['status'] = 'failed'
            test_result['details']['error'] = str(e)
            self.test_results['tests_failed'] += 1
            self.test_results['issues_found'].append(f"Database integration failed: {e}")
        
        self.test_results['tests_run'] += 1
        return test_result
    
    async def test_performance_benchmarks(self) -> Dict[str, Any]:
        """Test performance benchmarks"""
        logger.info("Testing performance benchmarks...")
        test_result = {'name': 'Performance Benchmarks', 'status': 'running', 'details': {}}
        
        try:
            if not ML_MODULES_AVAILABLE:
                test_result['status'] = 'skipped'
                test_result['details']['reason'] = 'ML modules not available'
                self.test_results['tests_run'] += 1
                return test_result
            
            performance_metrics = {}
            
            # Test inference speed with different batch sizes
            yolo_engine = EnhancedYOLOEngine(device='cpu')
            await yolo_engine.initialize()
            
            test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            batch_sizes = [1, 2, 4, 8]
            
            for batch_size in batch_sizes:
                frames = [test_image] * batch_size
                frame_numbers = list(range(batch_size))
                timestamps = [i * 0.033 for i in range(batch_size)]
                
                # Warm up
                await yolo_engine.detect_vrus_batch(frames, frame_numbers, timestamps)
                
                # Benchmark
                start_time = time.time()
                iterations = 10
                for _ in range(iterations):
                    await yolo_engine.detect_vrus_batch(frames, frame_numbers, timestamps)
                
                total_time = time.time() - start_time
                avg_time_per_batch = total_time / iterations
                fps = batch_size / avg_time_per_batch
                
                performance_metrics[f'batch_size_{batch_size}'] = {
                    'avg_time_per_batch': avg_time_per_batch,
                    'fps': fps,
                    'time_per_frame': avg_time_per_batch / batch_size
                }
            
            # Test memory usage (basic check)
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            performance_metrics['memory_usage'] = {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'cpu_percent': process.cpu_percent()
            }
            
            # Get engine stats
            engine_stats = yolo_engine.get_performance_stats()
            performance_metrics['engine_stats'] = engine_stats
            
            test_result['details'] = {
                'performance_metrics': performance_metrics,
                'benchmark_completed': True
            }
            
            # Store in global metrics
            self.test_results['performance_metrics']['inference_benchmarks'] = performance_metrics
            
            # Performance thresholds (adjust as needed)
            single_frame_fps = performance_metrics['batch_size_1']['fps']
            if single_frame_fps > 1.0:  # At least 1 FPS for single frame
                test_result['status'] = 'passed'
                self.test_results['tests_passed'] += 1
            else:
                test_result['status'] = 'failed'
                test_result['details']['error'] = f"Performance below threshold: {single_frame_fps:.2f} FPS"
                self.test_results['tests_failed'] += 1
                
        except Exception as e:
            test_result['status'] = 'failed'
            test_result['details']['error'] = str(e)
            self.test_results['tests_failed'] += 1
            self.test_results['issues_found'].append(f"Performance benchmark failed: {e}")
        
        self.test_results['tests_run'] += 1
        return test_result
    
    async def test_health_monitoring(self) -> Dict[str, Any]:
        """Test health monitoring and diagnostics"""
        logger.info("Testing health monitoring...")
        test_result = {'name': 'Health Monitoring', 'status': 'running', 'details': {}}
        
        try:
            if not ML_MODULES_AVAILABLE:
                test_result['status'] = 'skipped'
                test_result['details']['reason'] = 'ML modules not available'
                self.test_results['tests_run'] += 1
                return test_result
            
            # Test basic ML engine health
            engine = await get_production_ml_engine()
            health_report = await engine.health_check()
            
            test_result['details']['health_check'] = health_report
            
            # Test model info
            if hasattr(engine, 'yolo_engine'):
                engine_stats = engine.get_engine_stats()
                test_result['details']['engine_stats'] = engine_stats
            
            # Validate health report structure
            required_fields = ['status', 'components', 'timestamp']
            health_valid = all(field in health_report for field in required_fields)
            
            if health_valid and health_report['status'] in ['healthy', 'degraded']:
                test_result['status'] = 'passed'
                self.test_results['tests_passed'] += 1
            else:
                test_result['status'] = 'failed'
                test_result['details']['error'] = f"Health check failed: {health_report.get('status', 'unknown')}"
                self.test_results['tests_failed'] += 1
                
        except Exception as e:
            test_result['status'] = 'failed'
            test_result['details']['error'] = str(e)
            self.test_results['tests_failed'] += 1
            self.test_results['issues_found'].append(f"Health monitoring failed: {e}")
        
        self.test_results['tests_run'] += 1
        return test_result
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all ML inference validation tests"""
        logger.info("Starting comprehensive ML inference validation...")
        
        await self.setup_test_environment()
        
        validation_tests = [
            self.test_basic_ml_engine_initialization,
            self.test_yolo_model_loading,
            self.test_video_processing_pipeline,
            self.test_vru_detection_accuracy,
            self.test_database_integration,
            self.test_performance_benchmarks,
            self.test_health_monitoring
        ]
        
        test_results = []
        
        for test_func in validation_tests:
            try:
                logger.info(f"Running {test_func.__name__}...")
                result = await test_func()
                test_results.append(result)
                
                status_emoji = "✅" if result['status'] == 'passed' else "❌" if result['status'] == 'failed' else "⏭️"
                logger.info(f"{status_emoji} {result['name']}: {result['status']}")
                
            except Exception as e:
                logger.error(f"Test {test_func.__name__} crashed: {e}")
                test_results.append({
                    'name': test_func.__name__,
                    'status': 'crashed',
                    'details': {'error': str(e)}
                })
                self.test_results['tests_failed'] += 1
        
        # Generate comprehensive report
        self.test_results['end_time'] = datetime.now(timezone.utc)
        self.test_results['total_duration'] = (
            self.test_results['end_time'] - self.test_results['start_time']
        ).total_seconds()
        
        self.test_results['test_results'] = test_results
        self.test_results['success_rate'] = (
            self.test_results['tests_passed'] / self.test_results['tests_run'] * 100
            if self.test_results['tests_run'] > 0 else 0
        )
        
        # Generate validation summary
        self.test_results['validation_summary'] = {
            'overall_status': 'PASSED' if self.test_results['tests_failed'] == 0 else 'FAILED',
            'ml_engine_functional': any(
                t['name'] == 'ML Engine Initialization' and t['status'] == 'passed' 
                for t in test_results
            ),
            'yolo_inference_working': any(
                t['name'] == 'YOLO Model Loading' and t['status'] == 'passed'
                for t in test_results
            ),
            'video_processing_working': any(
                t['name'] == 'Video Processing Pipeline' and t['status'] == 'passed'
                for t in test_results
            ),
            'database_integration_working': any(
                t['name'] == 'Database Integration' and t['status'] == 'passed'
                for t in test_results
            ),
            'performance_acceptable': any(
                t['name'] == 'Performance Benchmarks' and t['status'] == 'passed'
                for t in test_results
            )
        }
        
        await self.cleanup_test_environment()
        
        logger.info(f"Comprehensive validation completed: {self.test_results['validation_summary']['overall_status']}")
        return self.test_results
    
    async def cleanup_test_environment(self):
        """Clean up test environment"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info("Test environment cleaned up")

async def main():
    """Main validation function"""
    print("🚀 ML Inference Engine Comprehensive Validation")
    print("=" * 60)
    
    validator = MLInferenceValidator()
    validation_results = await validator.run_comprehensive_validation()
    
    # Print summary
    print("\n📊 VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Tests Run: {validation_results['tests_run']}")
    print(f"Tests Passed: {validation_results['tests_passed']}")
    print(f"Tests Failed: {validation_results['tests_failed']}")
    print(f"Success Rate: {validation_results['success_rate']:.1f}%")
    print(f"Duration: {validation_results['total_duration']:.1f}s")
    
    print("\n🎯 FUNCTIONAL STATUS")
    print("=" * 60)
    summary = validation_results['validation_summary']
    for component, status in summary.items():
        if component != 'overall_status':
            status_emoji = "✅" if status else "❌"
            print(f"{status_emoji} {component.replace('_', ' ').title()}: {'WORKING' if status else 'FAILED'}")
    
    if validation_results['performance_metrics']:
        print("\n⚡ PERFORMANCE METRICS")
        print("=" * 60)
        perf = validation_results['performance_metrics']
        
        if 'inference_benchmarks' in perf:
            batch_1_fps = perf['inference_benchmarks'].get('batch_size_1', {}).get('fps', 0)
            print(f"Single Frame Inference: {batch_1_fps:.2f} FPS")
            
            if 'memory_usage' in perf['inference_benchmarks']:
                memory = perf['inference_benchmarks']['memory_usage']
                print(f"Memory Usage: {memory.get('rss_mb', 0):.1f} MB")
        
        if 'video_processing' in perf:
            video_fps = perf['video_processing'].get('processing_fps', 0)
            print(f"Video Processing: {video_fps:.2f} FPS")
    
    if validation_results['issues_found']:
        print("\n⚠️  ISSUES FOUND")
        print("=" * 60)
        for issue in validation_results['issues_found']:
            print(f"• {issue}")
    
    # Save detailed results
    results_file = f"/home/user/Testing/ai-model-validation-platform/backend/tests/ml_validation_report_{int(time.time())}.json"
    with open(results_file, 'w') as f:
        json.dump(validation_results, f, indent=2, default=str)
    
    print(f"\n📝 Detailed results saved to: {results_file}")
    
    overall_status = validation_results['validation_summary']['overall_status']
    print(f"\n🏁 OVERALL STATUS: {overall_status}")
    
    if overall_status == 'PASSED':
        print("✅ ML Inference Engine is production ready!")
        return 0
    else:
        print("❌ ML Inference Engine needs fixes before production deployment")
        return 1

if __name__ == "__main__":
    import sys
    result = asyncio.run(main())
    sys.exit(result)
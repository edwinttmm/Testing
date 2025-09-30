#!/usr/bin/env python3
"""
End-to-End ML Pipeline Test Suite
Tests the complete ML pipeline from video input to ground truth output with error recovery scenarios.
"""

import sys
import os
import asyncio
import logging
import time
import json
import traceback
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import cv2
from datetime import datetime, timezone

# Add backend root to path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MLPipelineEndToEndTest:
    """Comprehensive end-to-end ML pipeline test suite"""
    
    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_suite": "ML Pipeline End-to-End",
            "tests": {},
            "overall_status": "unknown",
            "performance_metrics": {},
            "error_scenarios": {},
            "recovery_tests": {}
        }
        
        self.temp_dir = None
        self.setup_test_environment()
    
    def setup_test_environment(self):
        """Set up test environment with temporary files"""
        try:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="ml_pipeline_test_"))
            logger.info(f"Test environment created: {self.temp_dir}")
            
            # Create test directories
            (self.temp_dir / "videos").mkdir()
            (self.temp_dir / "screenshots").mkdir()
            (self.temp_dir / "models").mkdir()
            
        except Exception as e:
            logger.error(f"Failed to set up test environment: {e}")
            raise
    
    def cleanup_test_environment(self):
        """Clean up test environment"""
        try:
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"Test environment cleaned up: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up test environment: {e}")
    
    def create_test_video(self, name: str, duration_frames: int = 90, 
                         include_objects: bool = True) -> Path:
        """Create a test video with controllable content"""
        try:
            video_path = self.temp_dir / "videos" / f"{name}.mp4"
            
            # Video properties
            width, height = 640, 480
            fps = 30
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(video_path), fourcc, fps, (width, height))
            
            for frame_num in range(duration_frames):
                # Create base frame
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                
                # Add background texture
                noise = np.random.randint(0, 30, (height, width, 3), dtype=np.uint8)
                frame = cv2.add(frame, noise)
                
                if include_objects:
                    # Add moving pedestrian (white rectangle)
                    ped_x = 50 + (frame_num * 3) % (width - 100)
                    ped_y = height - 200
                    cv2.rectangle(frame, (ped_x, ped_y), (ped_x + 40, ped_y + 120), (255, 255, 255), -1)
                    
                    # Add cyclist (larger moving rectangle)
                    if frame_num > 30:
                        cyc_x = width - 50 - (frame_num * 4) % (width - 100)
                        cyc_y = height - 150
                        cv2.rectangle(frame, (cyc_x, cyc_y), (cyc_x + 60, cyc_y + 80), (200, 200, 200), -1)
                    
                    # Add stationary object (potential false positive)
                    if frame_num > 60:
                        stat_x = width // 2
                        stat_y = height - 100
                        cv2.rectangle(frame, (stat_x, stat_y), (stat_x + 30, stat_y + 80), (150, 150, 150), -1)
                
                out.write(frame)
            
            out.release()
            
            if video_path.exists():
                logger.info(f"Test video created: {video_path} ({duration_frames} frames)")
                return video_path
            else:
                raise Exception("Video file not created")
            
        except Exception as e:
            logger.error(f"Failed to create test video {name}: {e}")
            raise
    
    def create_corrupted_video(self, name: str) -> Path:
        """Create a corrupted video file for error testing"""
        try:
            video_path = self.temp_dir / "videos" / f"{name}.mp4"
            
            # Create a file with invalid video data
            with open(video_path, 'wb') as f:
                f.write(b"This is not a valid video file")
            
            logger.info(f"Corrupted video created: {video_path}")
            return video_path
            
        except Exception as e:
            logger.error(f"Failed to create corrupted video {name}: {e}")
            raise
    
    async def test_basic_video_processing(self) -> Dict[str, Any]:
        """Test basic video processing workflow"""
        test_name = "basic_video_processing"
        logger.info(f"🧪 Running {test_name} test...")
        
        result = {
            "test_name": test_name,
            "status": "unknown",
            "details": {},
            "issues": [],
            "metrics": {}
        }
        
        try:
            # Create test video
            test_video = self.create_test_video("basic_test", duration_frames=60)
            
            # Test with Ground Truth Service
            from services.ground_truth_service import GroundTruthService
            
            gt_service = GroundTruthService()
            start_time = time.time()
            
            # Test video processing
            video_id = "test_basic_video_123"
            detections = gt_service._extract_detections(str(test_video))
            
            processing_time = time.time() - start_time
            
            result["details"] = {
                "video_path": str(test_video),
                "video_size_mb": test_video.stat().st_size / (1024*1024),
                "detections_found": len(detections),
                "processing_time": processing_time,
                "fps": 60 / processing_time if processing_time > 0 else 0
            }
            
            # Validate detections
            if detections:
                confidences = [d["confidence"] for d in detections]
                classes = [d["class_label"] for d in detections]
                
                result["details"]["detection_analysis"] = {
                    "avg_confidence": sum(confidences) / len(confidences),
                    "confidence_range": [min(confidences), max(confidences)],
                    "unique_classes": list(set(classes)),
                    "class_distribution": {cls: classes.count(cls) for cls in set(classes)}
                }
                
                # Check for expected detections (pedestrians from our test video)
                pedestrian_count = classes.count("pedestrian")
                if pedestrian_count == 0:
                    result["issues"].append("No pedestrian detections found in test video with moving objects")
            else:
                result["issues"].append("No detections found in test video")
            
            # Test model status
            model_status = gt_service.get_model_status()
            result["details"]["model_status"] = model_status
            
            if not model_status.get("ml_available"):
                result["issues"].append("ML not available")
            
            if not model_status.get("model_loaded"):
                result["issues"].append("Model not loaded")
            
            result["metrics"]["processing_fps"] = result["details"]["fps"]
            result["metrics"]["detections_per_second"] = len(detections) / processing_time if processing_time > 0 else 0
            
            result["status"] = "passed" if len(result["issues"]) == 0 else "failed"
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            logger.error(f"Basic video processing test failed: {e}")
        
        return result
    
    async def test_enhanced_video_processing(self) -> Dict[str, Any]:
        """Test enhanced video processing workflow"""
        test_name = "enhanced_video_processing"
        logger.info(f"🧪 Running {test_name} test...")
        
        result = {
            "test_name": test_name,
            "status": "unknown",
            "details": {},
            "issues": [],
            "metrics": {}
        }
        
        try:
            # Create test video
            test_video = self.create_test_video("enhanced_test", duration_frames=120, include_objects=True)
            
            # Test with Enhanced ML Inference Engine
            try:
                from src.enhanced_ml_inference_engine import get_production_ml_engine
                
                start_time = time.time()
                engine = await get_production_ml_engine()
                
                # Process video
                video_id = "test_enhanced_video_456"
                processing_result = await engine.process_video_complete(
                    video_id, str(test_video)
                )
                
                processing_time = time.time() - start_time
                
                result["details"] = {
                    "video_path": str(test_video),
                    "processing_result": processing_result,
                    "total_processing_time": processing_time
                }
                
                # Analyze results
                if processing_result.get("status") == "completed":
                    stats = processing_result.get("processing_stats", {})
                    summary = processing_result.get("detection_summary", {})
                    
                    result["details"]["performance_analysis"] = {
                        "frames_processed": stats.get("total_frames", 0),
                        "detections_found": stats.get("total_detections", 0),
                        "processing_fps": stats.get("avg_fps", 0),
                        "detections_per_frame": stats.get("detections_per_frame", 0),
                        "detection_types": summary.get("by_type", {})
                    }
                    
                    result["metrics"]["enhanced_processing_fps"] = stats.get("avg_fps", 0)
                    result["metrics"]["total_detections"] = stats.get("total_detections", 0)
                    
                    # Validate expected detections
                    expected_classes = ["pedestrian"]  # From our test video
                    found_classes = list(summary.get("by_type", {}).keys())
                    
                    for expected_class in expected_classes:
                        if expected_class not in found_classes:
                            result["issues"].append(f"Expected {expected_class} not detected")
                
                else:
                    result["issues"].append(f"Processing failed: {processing_result.get('status')}")
                    if "error" in processing_result:
                        result["issues"].append(f"Error: {processing_result['error']}")
                
                # Test engine health
                health = await engine.health_check()
                result["details"]["engine_health"] = health
                
                if health.get("status") != "healthy":
                    result["issues"].append(f"Engine health check failed: {health.get('status')}")
                
            except ImportError:
                result["issues"].append("Enhanced ML Inference Engine not available")
                result["status"] = "skipped"
                return result
            
            result["status"] = "passed" if len(result["issues"]) == 0 else "failed"
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            logger.error(f"Enhanced video processing test failed: {e}")
        
        return result
    
    async def test_bulletproof_detection(self) -> Dict[str, Any]:
        """Test bulletproof detection service"""
        test_name = "bulletproof_detection"
        logger.info(f"🧪 Running {test_name} test...")
        
        result = {
            "test_name": test_name,
            "status": "unknown",
            "details": {},
            "issues": [],
            "metrics": {}
        }
        
        try:
            # Create test video
            test_video = self.create_test_video("bulletproof_test", duration_frames=90)
            
            # Test with Bulletproof Detection Service
            try:
                from src.bulletproof_detection_service import BulletproofYOLOWrapper
                
                bp_yolo = BulletproofYOLOWrapper()
                
                # Initialize
                init_success = await bp_yolo.initialize()
                result["details"]["initialization"] = {
                    "success": init_success,
                    "model_version": bp_yolo.model_version,
                    "has_model": bp_yolo.model is not None
                }
                
                if not init_success:
                    result["issues"].append("Bulletproof YOLO initialization failed")
                    result["status"] = "failed"
                    return result
                
                # Test single frame detection
                cap = cv2.VideoCapture(str(test_video))
                ret, frame = cap.read()
                cap.release()
                
                if ret:
                    start_time = time.time()
                    detections = await bp_yolo.detect_objects(
                        frame, "test_video_789", 1, 0.033
                    )
                    detection_time = time.time() - start_time
                    
                    result["details"]["frame_detection"] = {
                        "detections_found": len(detections),
                        "detection_time": detection_time,
                        "frame_shape": frame.shape
                    }
                    
                    result["metrics"]["bulletproof_detection_time"] = detection_time
                    result["metrics"]["bulletproof_detections"] = len(detections)
                    
                    # Analyze detection quality
                    if detections:
                        confidences = [d.confidence for d in detections]
                        vru_types = [d.vru_type for d in detections]
                        
                        result["details"]["detection_quality"] = {
                            "confidence_stats": {
                                "avg": sum(confidences) / len(confidences),
                                "min": min(confidences),
                                "max": max(confidences)
                            },
                            "vru_type_distribution": {vru_type: vru_types.count(vru_type) for vru_type in set(vru_types)}
                        }
                else:
                    result["issues"].append("Could not read frame from test video")
                
            except ImportError:
                result["issues"].append("Bulletproof Detection Service not available")
                result["status"] = "skipped"
                return result
            
            result["status"] = "passed" if len(result["issues"]) == 0 else "failed"
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            logger.error(f"Bulletproof detection test failed: {e}")
        
        return result
    
    async def test_error_recovery_scenarios(self) -> Dict[str, Any]:
        """Test error recovery mechanisms"""
        test_name = "error_recovery"
        logger.info(f"🧪 Running {test_name} test...")
        
        result = {
            "test_name": test_name,
            "status": "unknown",
            "scenarios": {},
            "issues": []
        }
        
        try:
            # Scenario 1: Corrupted video file
            await self._test_corrupted_video_recovery(result)
            
            # Scenario 2: Missing video file
            await self._test_missing_video_recovery(result)
            
            # Scenario 3: Out of memory simulation
            await self._test_memory_pressure_recovery(result)
            
            # Scenario 4: Model loading failure
            await self._test_model_failure_recovery(result)
            
            # Analyze recovery performance
            successful_recoveries = sum(1 for scenario in result["scenarios"].values() 
                                      if scenario.get("recovery_successful", False))
            total_scenarios = len(result["scenarios"])
            
            recovery_rate = successful_recoveries / total_scenarios if total_scenarios > 0 else 0
            
            result["recovery_rate"] = recovery_rate
            result["total_scenarios"] = total_scenarios
            result["successful_recoveries"] = successful_recoveries
            
            if recovery_rate < 0.5:
                result["issues"].append(f"Low error recovery rate: {recovery_rate:.1%}")
            
            result["status"] = "passed" if len(result["issues"]) == 0 else "failed"
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            logger.error(f"Error recovery test failed: {e}")
        
        return result
    
    async def _test_corrupted_video_recovery(self, result: Dict[str, Any]):
        """Test recovery from corrupted video file"""
        try:
            corrupted_video = self.create_corrupted_video("corrupted_test")
            
            from services.ground_truth_service import GroundTruthService
            gt_service = GroundTruthService()
            
            # Attempt to process corrupted video
            try:
                detections = gt_service._extract_detections(str(corrupted_video))
                recovery_successful = len(detections) == 0  # Should return empty list, not crash
                error_handled = True
            except Exception as e:
                recovery_successful = False
                error_handled = False
                error_message = str(e)
            
            result["scenarios"]["corrupted_video"] = {
                "scenario": "Corrupted video file",
                "recovery_successful": recovery_successful,
                "error_handled": error_handled,
                "details": {
                    "video_path": str(corrupted_video),
                    "file_size": corrupted_video.stat().st_size,
                    "error_message": error_message if not error_handled else None
                }
            }
            
        except Exception as e:
            result["scenarios"]["corrupted_video"] = {
                "scenario": "Corrupted video file",
                "recovery_successful": False,
                "error": str(e)
            }
    
    async def _test_missing_video_recovery(self, result: Dict[str, Any]):
        """Test recovery from missing video file"""
        try:
            missing_video_path = self.temp_dir / "videos" / "nonexistent.mp4"
            
            from services.ground_truth_service import GroundTruthService
            gt_service = GroundTruthService()
            
            # Attempt to process missing video
            try:
                detections = gt_service._extract_detections(str(missing_video_path))
                recovery_successful = len(detections) == 0  # Should return empty list
                error_handled = True
                error_message = None
            except Exception as e:
                recovery_successful = False
                error_handled = False
                error_message = str(e)
            
            result["scenarios"]["missing_video"] = {
                "scenario": "Missing video file",
                "recovery_successful": recovery_successful,
                "error_handled": error_handled,
                "details": {
                    "video_path": str(missing_video_path),
                    "file_exists": missing_video_path.exists(),
                    "error_message": error_message
                }
            }
            
        except Exception as e:
            result["scenarios"]["missing_video"] = {
                "scenario": "Missing video file",
                "recovery_successful": False,
                "error": str(e)
            }
    
    async def _test_memory_pressure_recovery(self, result: Dict[str, Any]):
        """Test recovery under memory pressure"""
        try:
            # Create a large video that might cause memory issues
            large_video = self.create_test_video("memory_pressure_test", duration_frames=300)
            
            from services.ground_truth_service import GroundTruthService
            gt_service = GroundTruthService()
            
            try:
                # Monitor memory usage
                import psutil
                process = psutil.Process()
                memory_before = process.memory_info().rss
                
                detections = gt_service._extract_detections(str(large_video))
                
                memory_after = process.memory_info().rss
                memory_increase = memory_after - memory_before
                
                recovery_successful = True
                error_handled = True
                error_message = None
                
            except Exception as e:
                recovery_successful = False
                error_handled = False
                error_message = str(e)
                memory_increase = 0
            
            result["scenarios"]["memory_pressure"] = {
                "scenario": "Memory pressure test",
                "recovery_successful": recovery_successful,
                "error_handled": error_handled,
                "details": {
                    "video_frames": 300,
                    "memory_increase_mb": memory_increase / (1024*1024),
                    "detections_found": len(detections) if recovery_successful else 0,
                    "error_message": error_message
                }
            }
            
        except Exception as e:
            result["scenarios"]["memory_pressure"] = {
                "scenario": "Memory pressure test",
                "recovery_successful": False,
                "error": str(e)
            }
    
    async def _test_model_failure_recovery(self, result: Dict[str, Any]):
        """Test recovery from model loading failure"""
        try:
            # Test with non-existent model path
            from services.ground_truth_service import GroundTruthService
            
            # Create service instance
            gt_service = GroundTruthService()
            
            # Force model to None to simulate failure
            original_model = gt_service.model
            gt_service.model = None
            gt_service.ml_available = False
            
            try:
                test_video = self.create_test_video("model_failure_test", duration_frames=30)
                detections = gt_service._extract_detections(str(test_video))
                
                # Should return empty list without crashing
                recovery_successful = len(detections) == 0
                error_handled = True
                error_message = None
                
            except Exception as e:
                recovery_successful = False
                error_handled = False
                error_message = str(e)
            finally:
                # Restore original model
                gt_service.model = original_model
                gt_service.ml_available = original_model is not None
            
            result["scenarios"]["model_failure"] = {
                "scenario": "Model loading failure",
                "recovery_successful": recovery_successful,
                "error_handled": error_handled,
                "details": {
                    "fallback_used": recovery_successful,
                    "error_message": error_message
                }
            }
            
        except Exception as e:
            result["scenarios"]["model_failure"] = {
                "scenario": "Model loading failure",
                "recovery_successful": False,
                "error": str(e)
            }
    
    async def test_performance_benchmarks(self) -> Dict[str, Any]:
        """Test performance benchmarks"""
        test_name = "performance_benchmarks"
        logger.info(f"🧪 Running {test_name} test...")
        
        result = {
            "test_name": test_name,
            "status": "unknown",
            "benchmarks": {},
            "issues": []
        }
        
        try:
            # Benchmark 1: Processing speed vs video length
            await self._benchmark_processing_speed(result)
            
            # Benchmark 2: Memory usage vs video resolution
            await self._benchmark_memory_usage(result)
            
            # Benchmark 3: Detection accuracy vs confidence threshold
            await self._benchmark_detection_accuracy(result)
            
            # Benchmark 4: Concurrent processing capability
            await self._benchmark_concurrent_processing(result)
            
            # Analyze benchmark results
            self._analyze_benchmark_results(result)
            
            result["status"] = "passed" if len(result["issues"]) == 0 else "failed"
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            logger.error(f"Performance benchmark test failed: {e}")
        
        return result
    
    async def _benchmark_processing_speed(self, result: Dict[str, Any]):
        """Benchmark processing speed vs video length"""
        try:
            from services.ground_truth_service import GroundTruthService
            gt_service = GroundTruthService()
            
            video_lengths = [30, 60, 120, 180]  # frames
            speed_results = {}
            
            for length in video_lengths:
                test_video = self.create_test_video(f"speed_test_{length}", duration_frames=length)
                
                start_time = time.time()
                detections = gt_service._extract_detections(str(test_video))
                processing_time = time.time() - start_time
                
                fps = length / processing_time if processing_time > 0 else 0
                
                speed_results[f"{length}_frames"] = {
                    "frames": length,
                    "processing_time": processing_time,
                    "fps": fps,
                    "detections": len(detections),
                    "detections_per_second": len(detections) / processing_time if processing_time > 0 else 0
                }
            
            result["benchmarks"]["processing_speed"] = speed_results
            
            # Check if processing speed degrades significantly with video length
            fps_values = [data["fps"] for data in speed_results.values()]
            if len(fps_values) > 1:
                fps_degradation = (max(fps_values) - min(fps_values)) / max(fps_values)
                if fps_degradation > 0.5:  # More than 50% degradation
                    result["issues"].append(f"Significant FPS degradation with video length: {fps_degradation:.1%}")
            
        except Exception as e:
            result["benchmarks"]["processing_speed"] = {"error": str(e)}
    
    async def _benchmark_memory_usage(self, result: Dict[str, Any]):
        """Benchmark memory usage vs video resolution"""
        try:
            import psutil
            from services.ground_truth_service import GroundTruthService
            gt_service = GroundTruthService()
            
            resolutions = [(320, 240), (640, 480), (1280, 720)]
            memory_results = {}
            
            for width, height in resolutions:
                # Create video with specific resolution
                video_path = self.temp_dir / "videos" / f"memory_test_{width}x{height}.mp4"
                
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (width, height))
                
                for i in range(60):  # 60 frames
                    frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
                    out.write(frame)
                out.release()
                
                # Measure memory usage
                process = psutil.Process()
                memory_before = process.memory_info().rss
                
                detections = gt_service._extract_detections(str(video_path))
                
                memory_after = process.memory_info().rss
                memory_increase = memory_after - memory_before
                
                memory_results[f"{width}x{height}"] = {
                    "resolution": [width, height],
                    "memory_increase_mb": memory_increase / (1024*1024),
                    "detections": len(detections),
                    "memory_per_pixel": memory_increase / (width * height) if width * height > 0 else 0
                }
            
            result["benchmarks"]["memory_usage"] = memory_results
            
            # Check for excessive memory usage
            max_memory_mb = max(data["memory_increase_mb"] for data in memory_results.values())
            if max_memory_mb > 500:  # More than 500MB
                result["issues"].append(f"High memory usage detected: {max_memory_mb:.1f} MB")
            
        except Exception as e:
            result["benchmarks"]["memory_usage"] = {"error": str(e)}
    
    async def _benchmark_detection_accuracy(self, result: Dict[str, Any]):
        """Benchmark detection accuracy vs confidence threshold"""
        try:
            from services.ground_truth_service import GroundTruthService
            gt_service = GroundTruthService()
            
            # Create test video with known objects
            test_video = self.create_test_video("accuracy_test", duration_frames=90, include_objects=True)
            
            confidence_thresholds = [0.1, 0.3, 0.5, 0.7, 0.9]
            accuracy_results = {}
            
            for threshold in confidence_thresholds:
                # Modify service threshold (would need to implement this in actual service)
                detections = gt_service._extract_detections(str(test_video))
                
                # Filter by threshold
                filtered_detections = [d for d in detections if d["confidence"] >= threshold]
                
                accuracy_results[f"threshold_{threshold}"] = {
                    "threshold": threshold,
                    "total_detections": len(filtered_detections),
                    "avg_confidence": sum(d["confidence"] for d in filtered_detections) / len(filtered_detections) if filtered_detections else 0,
                    "pedestrian_count": len([d for d in filtered_detections if d["class_label"] == "pedestrian"]),
                    "cyclist_count": len([d for d in filtered_detections if d["class_label"] == "cyclist"])
                }
            
            result["benchmarks"]["detection_accuracy"] = accuracy_results
            
        except Exception as e:
            result["benchmarks"]["detection_accuracy"] = {"error": str(e)}
    
    async def _benchmark_concurrent_processing(self, result: Dict[str, Any]):
        """Benchmark concurrent processing capability"""
        try:
            from services.ground_truth_service import GroundTruthService
            
            # Create multiple test videos
            test_videos = []
            for i in range(3):
                video = self.create_test_video(f"concurrent_test_{i}", duration_frames=60)
                test_videos.append(video)
            
            # Test sequential processing
            gt_service = GroundTruthService()
            
            start_time = time.time()
            sequential_results = []
            for video in test_videos:
                detections = gt_service._extract_detections(str(video))
                sequential_results.append(len(detections))
            sequential_time = time.time() - start_time
            
            # Test concurrent processing (simulate)
            start_time = time.time()
            concurrent_tasks = []
            for video in test_videos:
                # In a real implementation, this would use async processing
                task = asyncio.create_task(self._process_video_async(gt_service, video))
                concurrent_tasks.append(task)
            
            concurrent_results = await asyncio.gather(*concurrent_tasks)
            concurrent_time = time.time() - start_time
            
            result["benchmarks"]["concurrent_processing"] = {
                "sequential": {
                    "time": sequential_time,
                    "results": sequential_results,
                    "total_detections": sum(sequential_results)
                },
                "concurrent": {
                    "time": concurrent_time,
                    "results": concurrent_results,
                    "total_detections": sum(concurrent_results),
                    "speedup": sequential_time / concurrent_time if concurrent_time > 0 else 1
                }
            }
            
        except Exception as e:
            result["benchmarks"]["concurrent_processing"] = {"error": str(e)}
    
    async def _process_video_async(self, gt_service, video_path: Path) -> int:
        """Async wrapper for video processing"""
        loop = asyncio.get_event_loop()
        detections = await loop.run_in_executor(
            None, gt_service._extract_detections, str(video_path)
        )
        return len(detections)
    
    def _analyze_benchmark_results(self, result: Dict[str, Any]):
        """Analyze benchmark results and identify performance issues"""
        try:
            benchmarks = result["benchmarks"]
            
            # Analyze processing speed
            if "processing_speed" in benchmarks and "error" not in benchmarks["processing_speed"]:
                speed_data = benchmarks["processing_speed"]
                min_fps = min(data["fps"] for data in speed_data.values() if "fps" in data)
                if min_fps < 10:  # Less than 10 FPS is concerning
                    result["issues"].append(f"Low processing speed detected: {min_fps:.1f} FPS minimum")
            
            # Analyze memory usage
            if "memory_usage" in benchmarks and "error" not in benchmarks["memory_usage"]:
                memory_data = benchmarks["memory_usage"]
                max_memory = max(data["memory_increase_mb"] for data in memory_data.values() if "memory_increase_mb" in data)
                if max_memory > 1000:  # More than 1GB
                    result["issues"].append(f"High memory usage: {max_memory:.1f} MB")
            
            # Analyze concurrent processing
            if "concurrent_processing" in benchmarks and "error" not in benchmarks["concurrent_processing"]:
                concurrent_data = benchmarks["concurrent_processing"]
                speedup = concurrent_data.get("concurrent", {}).get("speedup", 1)
                if speedup < 1.5:  # Less than 50% improvement
                    result["issues"].append(f"Poor concurrent processing speedup: {speedup:.1f}x")
            
        except Exception as e:
            logger.warning(f"Failed to analyze benchmark results: {e}")
    
    async def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """Run the complete end-to-end test suite"""
        logger.info("🚀 Starting Comprehensive ML Pipeline End-to-End Test Suite")
        
        start_time = time.time()
        
        # Define test suite
        tests = [
            ("basic_video_processing", self.test_basic_video_processing()),
            ("enhanced_video_processing", self.test_enhanced_video_processing()),
            ("bulletproof_detection", self.test_bulletproof_detection()),
            ("error_recovery", self.test_error_recovery_scenarios()),
            ("performance_benchmarks", self.test_performance_benchmarks())
        ]
        
        # Run tests
        for test_name, test_coro in tests:
            try:
                logger.info(f"Running {test_name}...")
                test_result = await test_coro
                self.test_results["tests"][test_name] = test_result
                
                # Log test result
                status = test_result.get("status", "unknown")
                logger.info(f"{test_name}: {status.upper()}")
                
                if status == "failed":
                    issues = test_result.get("issues", [])
                    for issue in issues[:3]:  # Show first 3 issues
                        logger.warning(f"  Issue: {issue}")
                
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                self.test_results["tests"][test_name] = {
                    "test_name": test_name,
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
        
        # Calculate overall status
        test_statuses = [test.get("status") for test in self.test_results["tests"].values()]
        
        if "error" in test_statuses:
            self.test_results["overall_status"] = "error"
        elif "failed" in test_statuses:
            self.test_results["overall_status"] = "failed"
        elif "passed" in test_statuses:
            self.test_results["overall_status"] = "passed"
        else:
            self.test_results["overall_status"] = "unknown"
        
        # Collect performance metrics
        self._collect_performance_metrics()
        
        # Calculate test duration
        self.test_results["test_duration"] = time.time() - start_time
        
        logger.info(f"✅ Test suite completed in {self.test_results['test_duration']:.2f}s")
        logger.info(f"Overall status: {self.test_results['overall_status'].upper()}")
        
        return self.test_results
    
    def _collect_performance_metrics(self):
        """Collect performance metrics from test results"""
        metrics = {}
        
        for test_name, test_result in self.test_results["tests"].items():
            test_metrics = test_result.get("metrics", {})
            for metric_name, metric_value in test_metrics.items():
                full_metric_name = f"{test_name}_{metric_name}"
                metrics[full_metric_name] = metric_value
        
        self.test_results["performance_metrics"] = metrics


async def main():
    """Main execution function"""
    print("🚀 ML Pipeline End-to-End Test Suite")
    print("=" * 60)
    
    test_suite = MLPipelineEndToEndTest()
    
    try:
        # Run comprehensive test suite
        results = await test_suite.run_comprehensive_test_suite()
        
        # Save results
        results_file = backend_root / "analysis" / f"ml_pipeline_e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print summary
        print(f"\n📊 Test Suite Results:")
        print(f"Overall Status: {results['overall_status'].upper()}")
        print(f"Total Tests: {len(results['tests'])}")
        
        status_counts = {}
        for test in results['tests'].values():
            status = test.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            print(f"{status.title()} Tests: {count}")
        
        print(f"Test Duration: {results['test_duration']:.2f}s")
        
        # Show performance metrics
        if results['performance_metrics']:
            print(f"\n⚡ Performance Metrics:")
            for metric, value in results['performance_metrics'].items():
                if isinstance(value, (int, float)):
                    print(f"  {metric}: {value:.2f}")
                else:
                    print(f"  {metric}: {value}")
        
        print(f"\n📁 Detailed results saved to: {results_file}")
        
        return results
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        traceback.print_exc()
        return None
    
    finally:
        # Cleanup
        test_suite.cleanup_test_environment()


if __name__ == "__main__":
    asyncio.run(main())
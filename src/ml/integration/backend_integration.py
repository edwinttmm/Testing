"""
Integration with existing backend validation service
"""
import asyncio
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import time

from ..inference.yolo_service import yolo_service, Detection
from ..preprocessing.video_processor import video_processor
from ..monitoring.performance_monitor import performance_monitor
from ..models.model_manager import model_manager

logger = logging.getLogger(__name__)

class MLValidationService:
    """
    Enhanced validation service with ML capabilities
    Integrates with existing backend validation service
    """
    
    def __init__(self):
        self.is_initialized = False
        
    async def initialize(self) -> bool:
        """Initialize ML validation service"""
        try:
            # Initialize ML components
            await model_manager.initialize_default_model()
            success = await yolo_service.initialize()
            
            if success:
                performance_monitor.start_monitoring()
                self.is_initialized = True
                logger.info("ML validation service initialized")
                return True
            else:
                logger.error("Failed to initialize YOLO service")
                return False
                
        except Exception as e:
            logger.error(f"ML validation service initialization failed: {str(e)}")
            return False
    
    async def generate_ground_truth(self, video_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate ground truth detections for a video using ML model
        
        Args:
            video_path: Path to video file
            output_dir: Directory to save results
            
        Returns:
            Dictionary with ground truth data and metadata
        """
        try:
            if not self.is_initialized:
                await self.initialize()
            
            logger.info(f"Generating ground truth for video: {video_path}")
            
            # Process video with ML pipeline
            result = await video_processor.process_video(
                video_path=video_path,
                yolo_service=yolo_service,
                output_dir=output_dir,
                enable_tracking=True,
                save_screenshots=True,
                frame_skip=1  # Process all frames for ground truth
            )
            
            # Convert detections to ground truth format
            ground_truth_objects = []
            
            for frame_number, detections in result.detections_by_frame.items():
                timestamp = frame_number / 30.0  # Assume 30 FPS
                
                for detection in detections:
                    ground_truth_obj = {
                        "timestamp": timestamp,
                        "frame_number": frame_number,
                        "class_label": detection.class_name,
                        "confidence": detection.confidence,
                        "bbox": {
                            "x1": detection.bbox[0],
                            "y1": detection.bbox[1],
                            "x2": detection.bbox[2],
                            "y2": detection.bbox[3]
                        },
                        "track_id": detection.track_id,
                        "detection_id": f"{frame_number}_{detection.class_id}_{int(detection.timestamp * 1000)}"
                    }
                    ground_truth_objects.append(ground_truth_obj)
            
            # Create response in format expected by existing validation service
            ground_truth_response = {
                "video_path": video_path,
                "total_detections": result.total_detections,
                "processing_time_seconds": result.processing_time_seconds,
                "fps": result.fps,
                "objects": ground_truth_objects,
                "metadata": {
                    "model_name": model_manager.get_active_model_info().name if model_manager.get_active_model_info() else "yolov8n",
                    "confidence_threshold": yolo_service.performance_monitor.get_current_stats(),
                    "total_frames": result.total_frames,
                    "processed_frames": result.processed_frames,
                    "tracking_enabled": result.tracking_enabled,
                    "screenshot_paths": result.screenshot_paths
                },
                "status": "completed",
                "generated_at": time.time()
            }
            
            logger.info(f"Ground truth generation completed: {result.total_detections} detections across {result.processed_frames} frames")
            
            return ground_truth_response
            
        except Exception as e:
            logger.error(f"Ground truth generation failed for {video_path}: {str(e)}", exc_info=True)
            return {
                "video_path": video_path,
                "objects": [],
                "total_detections": 0,
                "status": "failed",
                "error": str(e),
                "generated_at": time.time()
            }
    
    async def validate_detection_event(self, 
                                     detection_event: Dict[str, Any], 
                                     ground_truth_objects: List[Dict[str, Any]],
                                     tolerance_ms: int = 1000) -> str:
        """
        Validate a detection event against ML-generated ground truth
        
        Args:
            detection_event: Detection event from Raspberry Pi
            ground_truth_objects: Ground truth objects from ML
            tolerance_ms: Time tolerance in milliseconds
            
        Returns:
            Validation result: "TP", "FP", "FN", or "ERROR"
        """
        try:
            event_timestamp = detection_event.get("timestamp", 0)
            event_class = detection_event.get("class_label", "")
            event_confidence = detection_event.get("confidence", 0)
            
            tolerance_seconds = tolerance_ms / 1000.0
            
            # Find matching ground truth within tolerance
            best_match = None
            best_match_score = 0
            
            for gt_obj in ground_truth_objects:
                # Check time tolerance
                time_diff = abs(gt_obj["timestamp"] - event_timestamp)
                if time_diff > tolerance_seconds:
                    continue
                
                # Check class match
                if gt_obj["class_label"] != event_class:
                    continue
                
                # Calculate match score based on time proximity and confidence
                time_score = 1.0 - (time_diff / tolerance_seconds)
                confidence_score = min(gt_obj["confidence"], event_confidence)
                match_score = (time_score + confidence_score) / 2
                
                if match_score > best_match_score:
                    best_match = gt_obj
                    best_match_score = match_score
            
            if best_match and best_match_score > 0.5:  # Threshold for valid match
                logger.debug(f"Detection validated as TP: {event_class} at {event_timestamp}s (score: {best_match_score:.2f})")
                return "TP"
            else:
                logger.debug(f"Detection marked as FP: {event_class} at {event_timestamp}s (no valid ground truth match)")
                return "FP"
                
        except Exception as e:
            logger.error(f"Detection validation failed: {str(e)}")
            return "ERROR"
    
    async def calculate_session_metrics(self, 
                                      detection_events: List[Dict[str, Any]], 
                                      ground_truth_objects: List[Dict[str, Any]],
                                      tolerance_ms: int = 1000) -> Dict[str, Any]:
        """
        Calculate comprehensive validation metrics for a test session
        
        Args:
            detection_events: List of detection events from test session
            ground_truth_objects: Ground truth objects from ML
            tolerance_ms: Time tolerance for matching
            
        Returns:
            Dictionary with precision, recall, F1, accuracy and detailed metrics
        """
        try:
            tolerance_seconds = tolerance_ms / 1000.0
            
            # Track matches
            matched_detections = set()
            matched_ground_truth = set()
            
            true_positives = 0
            false_positives = 0
            
            # Validate each detection event
            for i, event in enumerate(detection_events):
                event_timestamp = event.get("timestamp", 0)
                event_class = event.get("class_label", "")
                
                # Find best matching ground truth
                best_match_idx = None
                best_time_diff = float('inf')
                
                for j, gt_obj in enumerate(ground_truth_objects):
                    if j in matched_ground_truth:
                        continue
                    
                    # Check class and time tolerance
                    if (gt_obj["class_label"] == event_class and
                        abs(gt_obj["timestamp"] - event_timestamp) <= tolerance_seconds):
                        
                        time_diff = abs(gt_obj["timestamp"] - event_timestamp)
                        if time_diff < best_time_diff:
                            best_match_idx = j
                            best_time_diff = time_diff
                
                if best_match_idx is not None:
                    # True positive
                    true_positives += 1
                    matched_detections.add(i)
                    matched_ground_truth.add(best_match_idx)
                else:
                    # False positive
                    false_positives += 1
            
            # False negatives are unmatched ground truth objects
            false_negatives = len(ground_truth_objects) - len(matched_ground_truth)
            
            # Calculate metrics
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            accuracy = true_positives / len(ground_truth_objects) if len(ground_truth_objects) > 0 else 0
            
            # Additional metrics
            total_detections = len(detection_events)
            detection_rate = total_detections / len(ground_truth_objects) if len(ground_truth_objects) > 0 else 0
            
            # Class-wise breakdown
            class_metrics = self._calculate_class_metrics(detection_events, ground_truth_objects, tolerance_seconds)
            
            metrics = {
                "overall_metrics": {
                    "true_positives": true_positives,
                    "false_positives": false_positives,
                    "false_negatives": false_negatives,
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                    "f1_score": round(f1_score, 4),
                    "accuracy": round(accuracy, 4)
                },
                "detection_summary": {
                    "total_detections": total_detections,
                    "total_ground_truth": len(ground_truth_objects),
                    "detection_rate": round(detection_rate, 4),
                    "matched_detections": len(matched_detections),
                    "unmatched_detections": total_detections - len(matched_detections)
                },
                "class_breakdown": class_metrics,
                "validation_config": {
                    "tolerance_ms": tolerance_ms,
                    "ml_model": model_manager.get_active_model_info().name if model_manager.get_active_model_info() else "unknown"
                },
                "calculated_at": time.time()
            }
            
            logger.info(f"Session metrics calculated: P={precision:.3f}, R={recall:.3f}, F1={f1_score:.3f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Session metrics calculation failed: {str(e)}")
            return {
                "overall_metrics": {
                    "true_positives": 0,
                    "false_positives": 0,
                    "false_negatives": 0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1_score": 0.0,
                    "accuracy": 0.0
                },
                "error": str(e),
                "calculated_at": time.time()
            }
    
    def _calculate_class_metrics(self, detection_events: List[Dict], ground_truth_objects: List[Dict], tolerance_seconds: float) -> Dict[str, Dict]:
        """Calculate metrics per class"""
        try:
            classes = set()
            for event in detection_events:
                classes.add(event.get("class_label", "unknown"))
            for gt_obj in ground_truth_objects:
                classes.add(gt_obj.get("class_label", "unknown"))
            
            class_metrics = {}
            
            for class_name in classes:
                # Filter events and ground truth for this class
                class_events = [e for e in detection_events if e.get("class_label") == class_name]
                class_gt = [gt for gt in ground_truth_objects if gt.get("class_label") == class_name]
                
                # Simple matching for class-specific metrics
                tp = 0
                matched_gt = set()
                
                for event in class_events:
                    event_timestamp = event.get("timestamp", 0)
                    
                    for i, gt_obj in enumerate(class_gt):
                        if i in matched_gt:
                            continue
                        
                        if abs(gt_obj["timestamp"] - event_timestamp) <= tolerance_seconds:
                            tp += 1
                            matched_gt.add(i)
                            break
                
                fp = len(class_events) - tp
                fn = len(class_gt) - len(matched_gt)
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
                
                class_metrics[class_name] = {
                    "true_positives": tp,
                    "false_positives": fp,
                    "false_negatives": fn,
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                    "f1_score": round(f1, 4),
                    "detections_count": len(class_events),
                    "ground_truth_count": len(class_gt)
                }
            
            return class_metrics
            
        except Exception as e:
            logger.error(f"Class metrics calculation failed: {str(e)}")
            return {}
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get ML validation service status"""
        try:
            active_model = model_manager.get_active_model_info()
            yolo_stats = yolo_service.get_performance_stats()
            performance_stats = performance_monitor.get_current_stats()
            
            return {
                "initialized": self.is_initialized,
                "yolo_service_ready": yolo_service.is_initialized,
                "active_model": {
                    "name": active_model.name if active_model else None,
                    "version": active_model.version if active_model else None,
                    "device": active_model.device if active_model else None
                } if active_model else None,
                "performance": {
                    "yolo_stats": yolo_stats,
                    "system_stats": performance_stats
                },
                "capabilities": {
                    "ground_truth_generation": True,
                    "real_time_validation": True,
                    "batch_processing": True,
                    "performance_monitoring": True,
                    "model_hot_swapping": True
                }
            }
            
        except Exception as e:
            logger.error(f"Service status retrieval failed: {str(e)}")
            return {
                "initialized": False,
                "error": str(e)
            }
    
    async def shutdown(self):
        """Shutdown ML validation service"""
        try:
            await yolo_service.shutdown()
            await model_manager.shutdown()
            await video_processor.shutdown()
            await performance_monitor.stop_monitoring()
            
            self.is_initialized = False
            logger.info("ML validation service shut down")
            
        except Exception as e:
            logger.error(f"ML validation service shutdown failed: {str(e)}")

# Global ML validation service instance
ml_validation_service = MLValidationService()
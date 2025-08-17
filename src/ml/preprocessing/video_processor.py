"""
Video processing pipeline for batch VRU detection
"""
import asyncio
import cv2
import numpy as np
import logging
from typing import List, Dict, Optional, AsyncIterator, Tuple, Any
from pathlib import Path
import tempfile
import os
from dataclasses import dataclass
import json
from concurrent.futures import ThreadPoolExecutor
import time

from ..inference.yolo_service import Detection
from ..tracking.kalman_tracker import VRUTracker
from ..monitoring.performance_monitor import PerformanceMonitor
from ..config import ml_config

logger = logging.getLogger(__name__)

@dataclass
class VideoProcessingResult:
    """Result of video processing"""
    video_path: str
    total_frames: int
    processed_frames: int
    total_detections: int
    processing_time_seconds: float
    fps: float
    detections_by_frame: Dict[int, List[Detection]]
    tracking_enabled: bool
    screenshot_paths: List[str]
    performance_metrics: Dict[str, Any]

@dataclass
class FrameResult:
    """Result of processing a single frame"""
    frame_number: int
    timestamp: float
    detections: List[Detection]
    processing_time_ms: float
    screenshot_path: Optional[str] = None

class VideoProcessor:
    """
    High-performance video processor for batch VRU detection
    """
    
    def __init__(self):
        self.performance_monitor = PerformanceMonitor()
        self.executor = ThreadPoolExecutor(max_workers=ml_config.preprocessing_threads)
        
    async def process_video(self, 
                          video_path: str, 
                          yolo_service,
                          output_dir: Optional[str] = None,
                          enable_tracking: bool = True,
                          save_screenshots: bool = True,
                          frame_skip: int = 1) -> VideoProcessingResult:
        """
        Process entire video for VRU detection
        
        Args:
            video_path: Path to input video
            yolo_service: Initialized YOLO detection service
            output_dir: Directory for outputs (screenshots, metadata)
            enable_tracking: Enable temporal tracking
            save_screenshots: Save annotated screenshots
            frame_skip: Process every Nth frame (1 = all frames)
            
        Returns:
            VideoProcessingResult with all detections and metadata
        """
        start_time = time.time()
        
        try:
            # Setup output directory
            if output_dir is None:
                output_dir = tempfile.mkdtemp(prefix="vru_detection_")
            
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize tracker if enabled
            tracker = VRUTracker() if enable_tracking else None
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Could not open video: {video_path}")
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            original_fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logger.info(f"Processing video: {total_frames} frames at {original_fps} FPS ({width}x{height})")
            
            # Process frames
            detections_by_frame = {}
            screenshot_paths = []
            processed_frames = 0
            total_detections = 0
            
            frame_number = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Skip frames if specified
                if frame_number % frame_skip != 0:
                    frame_number += 1
                    continue
                
                # Process frame
                frame_result = await self._process_frame(
                    frame, frame_number, yolo_service, tracker,
                    output_path if save_screenshots else None
                )
                
                if frame_result:
                    detections_by_frame[frame_number] = frame_result.detections
                    total_detections += len(frame_result.detections)
                    processed_frames += 1
                    
                    if frame_result.screenshot_path:
                        screenshot_paths.append(frame_result.screenshot_path)
                    
                    # Log progress every 100 frames
                    if processed_frames % 100 == 0:
                        logger.info(f"Processed {processed_frames}/{total_frames//frame_skip} frames")
                
                frame_number += 1
            
            cap.release()
            
            # Calculate metrics
            processing_time = time.time() - start_time
            processing_fps = processed_frames / processing_time if processing_time > 0 else 0
            
            # Save metadata
            metadata_path = output_path / "detection_metadata.json"
            await self._save_metadata(
                metadata_path, video_path, detections_by_frame,
                processing_time, processing_fps, total_detections
            )
            
            # Get performance metrics
            performance_metrics = self.performance_monitor.get_current_stats()
            
            result = VideoProcessingResult(
                video_path=video_path,
                total_frames=total_frames,
                processed_frames=processed_frames,
                total_detections=total_detections,
                processing_time_seconds=processing_time,
                fps=processing_fps,
                detections_by_frame=detections_by_frame,
                tracking_enabled=enable_tracking,
                screenshot_paths=screenshot_paths,
                performance_metrics=performance_metrics
            )
            
            logger.info(f"Video processing complete: {total_detections} detections in {processing_time:.2f}s ({processing_fps:.1f} FPS)")
            return result
            
        except Exception as e:
            logger.error(f"Video processing failed: {str(e)}", exc_info=True)
            raise
    
    async def _process_frame(self, 
                           frame: np.ndarray, 
                           frame_number: int,
                           yolo_service,
                           tracker: Optional[VRUTracker],
                           output_dir: Optional[Path]) -> Optional[FrameResult]:
        """Process a single frame"""
        try:
            frame_start_time = time.time()
            
            # Calculate timestamp
            timestamp = frame_number / 30.0  # Assume 30 FPS if not available
            
            # Run detection
            detections, annotated_frame = await yolo_service.detect_vru(
                frame, return_annotated=(output_dir is not None)
            )
            
            # Apply tracking if enabled
            if tracker and detections:
                detections = tracker.update(detections)
            
            # Save screenshot if requested and detections found
            screenshot_path = None
            if output_dir and detections and annotated_frame is not None:
                screenshot_path = await self._save_screenshot(
                    annotated_frame, frame_number, output_dir
                )
            
            processing_time_ms = (time.time() - frame_start_time) * 1000
            
            return FrameResult(
                frame_number=frame_number,
                timestamp=timestamp,
                detections=detections,
                processing_time_ms=processing_time_ms,
                screenshot_path=screenshot_path
            )
            
        except Exception as e:
            logger.error(f"Frame {frame_number} processing failed: {str(e)}")
            return None
    
    async def _save_screenshot(self, 
                             annotated_frame: np.ndarray, 
                             frame_number: int,
                             output_dir: Path) -> str:
        """Save annotated frame as screenshot"""
        try:
            screenshot_filename = f"frame_{frame_number:06d}_detections.jpg"
            screenshot_path = output_dir / screenshot_filename
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                lambda: cv2.imwrite(
                    str(screenshot_path), 
                    annotated_frame,
                    [cv2.IMWRITE_JPEG_QUALITY, ml_config.screenshot_quality]
                )
            )
            
            return str(screenshot_path)
            
        except Exception as e:
            logger.error(f"Screenshot save failed for frame {frame_number}: {str(e)}")
            return None
    
    async def _save_metadata(self,
                           metadata_path: Path,
                           video_path: str,
                           detections_by_frame: Dict[int, List[Detection]],
                           processing_time: float,
                           fps: float,
                           total_detections: int):
        """Save processing metadata"""
        try:
            metadata = {
                "video_path": video_path,
                "processing_timestamp": time.time(),
                "processing_time_seconds": processing_time,
                "processing_fps": fps,
                "total_detections": total_detections,
                "frames_processed": len(detections_by_frame),
                "ml_config": {
                    "model_name": ml_config.model_name,
                    "confidence_threshold": ml_config.confidence_threshold,
                    "iou_threshold": ml_config.iou_threshold,
                    "device": ml_config.get_device()
                },
                "detections_summary": self._create_detections_summary(detections_by_frame)
            }
            
            # Save metadata
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            logger.info(f"Metadata saved to {metadata_path}")
            
        except Exception as e:
            logger.error(f"Metadata save failed: {str(e)}")
    
    def _create_detections_summary(self, detections_by_frame: Dict[int, List[Detection]]) -> Dict[str, Any]:
        """Create summary of detections"""
        try:
            class_counts = {}
            confidence_stats = []
            
            for frame_detections in detections_by_frame.values():
                for detection in frame_detections:
                    # Count by class
                    class_name = detection.class_name
                    class_counts[class_name] = class_counts.get(class_name, 0) + 1
                    
                    # Collect confidence scores
                    confidence_stats.append(detection.confidence)
            
            summary = {
                "detections_by_class": class_counts,
                "total_detections": sum(class_counts.values()),
                "frames_with_detections": len([f for f, dets in detections_by_frame.items() if dets]),
                "average_detections_per_frame": sum(class_counts.values()) / len(detections_by_frame) if detections_by_frame else 0
            }
            
            if confidence_stats:
                summary["confidence_stats"] = {
                    "mean": np.mean(confidence_stats),
                    "min": np.min(confidence_stats),
                    "max": np.max(confidence_stats),
                    "std": np.std(confidence_stats)
                }
            
            return summary
            
        except Exception as e:
            logger.error(f"Detection summary creation failed: {str(e)}")
            return {}
    
    async def process_video_batch(self, 
                                video_paths: List[str],
                                yolo_service,
                                output_base_dir: str,
                                max_concurrent: int = 2) -> List[VideoProcessingResult]:
        """
        Process multiple videos concurrently
        
        Args:
            video_paths: List of video file paths
            yolo_service: Initialized YOLO detection service
            output_base_dir: Base directory for outputs
            max_concurrent: Maximum concurrent video processing
            
        Returns:
            List of VideoProcessingResult for each video
        """
        try:
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def process_single_video(video_path: str) -> VideoProcessingResult:
                async with semaphore:
                    video_name = Path(video_path).stem
                    output_dir = Path(output_base_dir) / f"video_{video_name}_{int(time.time())}"
                    
                    return await self.process_video(
                        video_path, yolo_service, str(output_dir)
                    )
            
            # Process all videos concurrently
            tasks = [process_single_video(video_path) for video_path in video_paths]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and log errors
            successful_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Video {video_paths[i]} processing failed: {str(result)}")
                else:
                    successful_results.append(result)
            
            logger.info(f"Batch processing complete: {len(successful_results)}/{len(video_paths)} videos processed successfully")
            return successful_results
            
        except Exception as e:
            logger.error(f"Batch video processing failed: {str(e)}")
            return []
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get video processing statistics"""
        return self.performance_monitor.get_current_stats()
    
    async def shutdown(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        await self.performance_monitor.stop_monitoring()
        logger.info("Video processor shut down")

# Global video processor instance
video_processor = VideoProcessor()
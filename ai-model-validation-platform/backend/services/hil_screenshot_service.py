"""
HIL Screenshot Service for Hardware-in-the-Loop Testing

This service captures video frames at the exact moment when LabJack voltage detections occur,
providing visual evidence for ground truth comparison in HIL validation tests.

Key Features:
- Synchronized video frame capture during LabJack 4.2V detection events
- Integration with video timing service for precise frame extraction
- Screenshot storage with timestamp correlation for ground truth matching
- Support for both full frame and zoomed region capture
"""

import logging
import time
import uuid
import cv2
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Local imports
from services.video_timing_service import get_video_timing_service, VideoTimingService
from services.detection_pipeline_service import ScreenshotCapture, BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class HILScreenshotResult:
    """Result of HIL screenshot capture operation"""
    detection_id: str
    timestamp: float
    video_relative_timestamp: float
    frame_number: int
    screenshot_path: Optional[str]
    screenshot_zoom_path: Optional[str]
    capture_success: bool
    error_message: Optional[str] = None


class HILVideoFrameCapture:
    """
    Video frame capture service specifically designed for HIL voltage detection events.
    
    This service opens video files and captures frames at precise timestamps when
    LabJack voltage detections occur, ensuring visual evidence is available for
    ground truth comparison.
    """
    
    def __init__(self, screenshot_dir: str = "screenshots/hil"):
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Video capture instances (one per active session)
        self.video_captures: Dict[str, cv2.VideoCapture] = {}
        self.video_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Screenshot capture service
        self.screenshot_capture = ScreenshotCapture(str(self.screenshot_dir))
        
        # Video timing service for timestamp synchronization
        self.video_timing_service = get_video_timing_service()
        
        logger.info(f"HIL video frame capture initialized: {self.screenshot_dir}")
    
    def initialize_video_session(self, session_id: str, video_path: str, video_metadata: Dict[str, Any]) -> bool:
        """
        Initialize video capture for an HIL test session.
        
        Args:
            session_id: Test session identifier
            video_path: Path to video file
            video_metadata: Video metadata including fps, duration, etc.
            
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Open video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video file: {video_path}")
                return False
            
            # Store video capture and metadata
            self.video_captures[session_id] = cap
            
            # Extract video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.video_metadata[session_id] = {
                **video_metadata,
                'video_path': video_path,
                'fps': fps,
                'total_frames': total_frames,
                'width': width,
                'height': height,
                'frame_duration': 1.0 / fps if fps > 0 else 0
            }
            
            logger.info(f"HIL video session initialized: {session_id} - {fps:.2f} fps, {total_frames} frames, {width}x{height}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize HIL video session {session_id}: {e}")
            return False
    
    async def capture_detection_frame(
        self,
        session_id: str,
        detection_timestamp: float,
        video_relative_timestamp: float,
        frame_number: int,
        detection_id: str
    ) -> HILScreenshotResult:
        """
        Capture video frame at the exact moment of LabJack voltage detection.
        
        Args:
            session_id: Test session identifier
            detection_timestamp: Unix timestamp of detection
            video_relative_timestamp: Timestamp relative to video start
            frame_number: Video frame number to capture
            detection_id: Unique detection identifier
            
        Returns:
            HILScreenshotResult with capture details and paths
        """
        try:
            # Check if video session is initialized
            if session_id not in self.video_captures:
                error_msg = f"Video session {session_id} not initialized"
                logger.error(error_msg)
                return HILScreenshotResult(
                    detection_id=detection_id,
                    timestamp=detection_timestamp,
                    video_relative_timestamp=video_relative_timestamp,
                    frame_number=frame_number,
                    screenshot_path=None,
                    screenshot_zoom_path=None,
                    capture_success=False,
                    error_message=error_msg
                )
            
            cap = self.video_captures[session_id]
            metadata = self.video_metadata[session_id]
            
            # Set video position to exact frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_number - 1))
            
            # Verify frame position
            actual_frame_number = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            logger.debug(f"HIL frame capture: requested={frame_number}, actual={actual_frame_number}")
            
            # Capture frame
            ret, frame = cap.read()
            if not ret or frame is None:
                error_msg = f"Failed to capture frame {frame_number} from video"
                logger.error(error_msg)
                return HILScreenshotResult(
                    detection_id=detection_id,
                    timestamp=detection_timestamp,
                    video_relative_timestamp=video_relative_timestamp,
                    frame_number=frame_number,
                    screenshot_path=None,
                    screenshot_zoom_path=None,
                    capture_success=False,
                    error_message=error_msg
                )
            
            # Create HIL-specific bounding box (full frame with detection indicator)
            height, width = frame.shape[:2]
            detection_bbox = BoundingBox(
                x=width * 0.1,  # 10% from left
                y=height * 0.1,  # 10% from top
                width=width * 0.8,  # 80% of frame width
                height=height * 0.8   # 80% of frame height
            )
            
            # Capture full frame with HIL detection annotation
            screenshot_path = await self._capture_hil_frame(
                frame, detection_bbox, detection_id, video_relative_timestamp
            )
            
            # Capture center region zoom for detailed analysis
            screenshot_zoom_path = await self._capture_hil_zoom(
                frame, detection_id, video_relative_timestamp
            )
            
            logger.info(f"HIL frame captured successfully: detection_id={detection_id}, frame={frame_number}, time={video_relative_timestamp:.3f}s")
            
            return HILScreenshotResult(
                detection_id=detection_id,
                timestamp=detection_timestamp,
                video_relative_timestamp=video_relative_timestamp,
                frame_number=frame_number,
                screenshot_path=screenshot_path,
                screenshot_zoom_path=screenshot_zoom_path,
                capture_success=True
            )
            
        except Exception as e:
            error_msg = f"HIL frame capture failed: {e}"
            logger.error(error_msg)
            return HILScreenshotResult(
                detection_id=detection_id,
                timestamp=detection_timestamp,
                video_relative_timestamp=video_relative_timestamp,
                frame_number=frame_number,
                screenshot_path=None,
                screenshot_zoom_path=None,
                capture_success=False,
                error_message=error_msg
            )
    
    async def _capture_hil_frame(
        self, 
        frame: np.ndarray, 
        bbox: BoundingBox, 
        detection_id: str,
        video_timestamp: float
    ) -> Optional[str]:
        """Capture full frame with HIL detection overlay"""
        try:
            # Create annotated frame with HIL-specific overlay
            annotated_frame = self._annotate_hil_frame(frame, bbox, video_timestamp)
            
            # Save HIL detection screenshot
            screenshot_path = self.screenshot_dir / f"hil_detection_{detection_id}.jpg"
            success = cv2.imwrite(str(screenshot_path), annotated_frame)
            
            if success:
                logger.debug(f"HIL screenshot saved: {screenshot_path}")
                return str(screenshot_path)
            else:
                logger.error(f"Failed to save HIL screenshot: {screenshot_path}")
                return None
                
        except Exception as e:
            logger.error(f"HIL frame capture failed: {e}")
            return None
    
    async def _capture_hil_zoom(
        self, 
        frame: np.ndarray, 
        detection_id: str,
        video_timestamp: float
    ) -> Optional[str]:
        """Capture center region zoom for detailed HIL analysis"""
        try:
            height, width = frame.shape[:2]
            
            # Extract center region (50% of frame)
            center_x, center_y = width // 2, height // 2
            zoom_size = min(width, height) // 2
            
            x1 = max(0, center_x - zoom_size // 2)
            y1 = max(0, center_y - zoom_size // 2)
            x2 = min(width, center_x + zoom_size // 2)
            y2 = min(height, center_y + zoom_size // 2)
            
            roi = frame[y1:y2, x1:x2]
            
            # Resize for better visibility
            zoomed = cv2.resize(roi, (400, 400))
            
            # Add timestamp overlay to zoom
            cv2.putText(zoomed, f"HIL Detection: {video_timestamp:.3f}s", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Save zoom screenshot
            zoom_path = self.screenshot_dir / f"hil_detection_{detection_id}_zoom.jpg"
            success = cv2.imwrite(str(zoom_path), zoomed)
            
            if success:
                logger.debug(f"HIL zoom screenshot saved: {zoom_path}")
                return str(zoom_path)
            else:
                logger.error(f"Failed to save HIL zoom screenshot: {zoom_path}")
                return None
                
        except Exception as e:
            logger.error(f"HIL zoom capture failed: {e}")
            return None
    
    def _annotate_hil_frame(self, frame: np.ndarray, bbox: BoundingBox, video_timestamp: float) -> np.ndarray:
        """Add HIL-specific annotations to frame"""
        annotated = frame.copy()
        
        # Draw detection region
        x, y, w, h = int(bbox.x), int(bbox.y), int(bbox.width), int(bbox.height)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 255), 3)  # Yellow rectangle
        
        # Add HIL detection label
        label = f"HIL 4.2V Detection"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
        cv2.rectangle(annotated, (x, y - label_size[1] - 10), 
                     (x + label_size[0], y), (0, 255, 255), -1)
        cv2.putText(annotated, label, (x, y - 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        
        # Add timestamp
        timestamp_label = f"Video Time: {video_timestamp:.3f}s"
        cv2.putText(annotated, timestamp_label, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Add detection marker at center
        center_x = x + w // 2
        center_y = y + h // 2
        cv2.circle(annotated, (center_x, center_y), 20, (0, 0, 255), 3)  # Red circle
        cv2.putText(annotated, "4.2V", (center_x - 20, center_y + 5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        return annotated
    
    def cleanup_session(self, session_id: str) -> None:
        """Clean up video capture resources for a session"""
        try:
            if session_id in self.video_captures:
                cap = self.video_captures[session_id]
                cap.release()
                del self.video_captures[session_id]
                
            if session_id in self.video_metadata:
                del self.video_metadata[session_id]
                
            logger.info(f"HIL video session cleaned up: {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup HIL video session {session_id}: {e}")
    
    def cleanup_all_sessions(self) -> None:
        """Clean up all video capture resources"""
        session_ids = list(self.video_captures.keys())
        for session_id in session_ids:
            self.cleanup_session(session_id)


class HILGroundTruthComparison:
    """
    Service for comparing HIL voltage detections against ground truth timing data
    with visual evidence from screenshot capture.
    """
    
    def __init__(self):
        self.video_frame_capture = HILVideoFrameCapture()
        
        # Import ground truth matching service
        from services.ground_truth_matching_service import get_ground_truth_matching_service
        self.ground_truth_service = get_ground_truth_matching_service()
        
        logger.info("HIL ground truth comparison service initialized")
    
    async def process_hil_detection_with_screenshots(
        self,
        session_id: str,
        detection_data: Dict[str, Any],
        video_path: str,
        video_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process HIL detection event with screenshot capture and ground truth comparison.
        
        Args:
            session_id: Test session identifier
            detection_data: HIL detection event data
            video_path: Path to video file
            video_metadata: Video timing and metadata
            
        Returns:
            Dictionary with detection results, screenshots, and ground truth comparison
        """
        try:
            # Initialize video session if not already done
            if session_id not in self.video_frame_capture.video_captures:
                success = self.video_frame_capture.initialize_video_session(
                    session_id, video_path, video_metadata
                )
                if not success:
                    return {
                        'success': False,
                        'error': 'Failed to initialize video session',
                        'detection_id': detection_data.get('id')
                    }
            
            # Extract detection timing information
            detection_id = detection_data.get('id', str(uuid.uuid4()))
            unix_timestamp = detection_data.get('unix_timestamp')
            video_relative_timestamp = detection_data.get('video_relative_timestamp')
            frame_number = detection_data.get('video_frame_number')
            
            # Capture screenshot at detection moment
            screenshot_result = await self.video_frame_capture.capture_detection_frame(
                session_id=session_id,
                detection_timestamp=unix_timestamp,
                video_relative_timestamp=video_relative_timestamp,
                frame_number=frame_number,
                detection_id=detection_id
            )
            
            # Perform ground truth matching for this session
            ground_truth_metrics = self.ground_truth_service.match_detections_to_ground_truth(
                session_id=session_id,
                tolerance_ms=100,  # 100ms tolerance for HIL validation
                force_rematch=False
            )
            
            # Get detailed ground truth analysis
            detailed_analysis = self.ground_truth_service.get_detailed_analysis(session_id)
            
            # Get matching results summary
            matching_summary = self.ground_truth_service.get_matching_results_summary(session_id)
            
            return {
                'success': True,
                'detection_id': detection_id,
                'session_id': session_id,
                'screenshot_capture': {
                    'success': screenshot_result.capture_success,
                    'screenshot_path': screenshot_result.screenshot_path,
                    'screenshot_zoom_path': screenshot_result.screenshot_zoom_path,
                    'frame_number': screenshot_result.frame_number,
                    'video_timestamp': screenshot_result.video_relative_timestamp,
                    'error_message': screenshot_result.error_message
                },
                'ground_truth_comparison': {
                    'metrics': ground_truth_metrics.__dict__ if ground_truth_metrics else None,
                    'detailed_analysis': detailed_analysis,
                    'matching_summary': matching_summary
                },
                'hil_detection': {
                    'unix_timestamp': unix_timestamp,
                    'video_relative_timestamp': video_relative_timestamp,
                    'frame_number': frame_number,
                    'voltage': detection_data.get('labjack_voltage'),
                    'channel': detection_data.get('detection_channel'),
                    'latency_ms': detection_data.get('actual_latency_ms'),
                    'timing_quality': detection_data.get('timing_sync_quality')
                }
            }
            
        except Exception as e:
            logger.error(f"HIL detection processing with screenshots failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'detection_id': detection_data.get('id'),
                'session_id': session_id
            }
    
    def cleanup_session(self, session_id: str) -> None:
        """Clean up HIL comparison resources for a session"""
        self.video_frame_capture.cleanup_session(session_id)


# Global service instances
_hil_frame_capture: Optional[HILVideoFrameCapture] = None
_hil_ground_truth_comparison: Optional[HILGroundTruthComparison] = None


def get_hil_frame_capture() -> HILVideoFrameCapture:
    """Get global HIL video frame capture service instance"""
    global _hil_frame_capture
    if _hil_frame_capture is None:
        _hil_frame_capture = HILVideoFrameCapture()
    return _hil_frame_capture


def get_hil_ground_truth_comparison() -> HILGroundTruthComparison:
    """Get global HIL ground truth comparison service instance"""
    global _hil_ground_truth_comparison
    if _hil_ground_truth_comparison is None:
        _hil_ground_truth_comparison = HILGroundTruthComparison()
    return _hil_ground_truth_comparison


# Export key components
__all__ = [
    "HILVideoFrameCapture",
    "HILGroundTruthComparison", 
    "HILScreenshotResult",
    "get_hil_frame_capture",
    "get_hil_ground_truth_comparison"
]
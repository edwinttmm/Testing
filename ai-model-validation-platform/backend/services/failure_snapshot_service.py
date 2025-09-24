import cv2
import os
import base64
import uuid
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
import numpy as np

class FailureSnapshotService:
    """
    PRD Module 4.2 - Failure Snapshot Service
    
    Captures video snapshots at exact failure timestamps for:
    - HIGH_LATENCY failures
    - MISSED_DETECTION failures
    
    PRD Requirement: Video snapshot for EVERY failure, timestamped to moment event occurred
    """
    
    def __init__(self, snapshots_dir: str = "snapshots"):
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(exist_ok=True)
        self.failure_snapshots_dir = self.snapshots_dir / "failures"
        self.failure_snapshots_dir.mkdir(exist_ok=True)
    
    async def capture_failure_snapshot(
        self, 
        video_path: str, 
        timestamp_ms: float, 
        failure_type: str,
        event_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Capture video frame at exact failure timestamp
        
        Args:
            video_path: Path to video file
            timestamp_ms: Timestamp in milliseconds when failure occurred
            failure_type: 'HIGH_LATENCY' or 'MISSED_DETECTION'
            event_id: Detection event UUID for unique naming
            
        Returns:
            Dict with snapshot information or None if failed
        """
        try:
            # Check if video file exists
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Open video capture
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Could not open video: {video_path}")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_ms = (total_frames / fps) * 1000 if fps > 0 else 0
            
            # Calculate frame number from timestamp
            frame_number = int((timestamp_ms / 1000) * fps)
            
            # Validate frame number
            if frame_number < 0 or frame_number >= total_frames:
                raise ValueError(f"Frame {frame_number} out of range (0-{total_frames-1})")
            
            # Seek to specific frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            
            # Read the frame
            ret, frame = cap.read()
            if not ret:
                raise ValueError(f"Could not read frame {frame_number}")
            
            # Generate unique filename
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{failure_type.lower()}_{event_id}_{timestamp_str}.jpg"
            snapshot_path = self.failure_snapshots_dir / filename
            
            # Add timestamp overlay to frame
            frame_with_overlay = self._add_failure_overlay(
                frame, failure_type, timestamp_ms, frame_number
            )
            
            # Save snapshot
            success = cv2.imwrite(str(snapshot_path), frame_with_overlay)
            if not success:
                raise ValueError("Failed to save snapshot image")
            
            # Convert to base64 for embedding in reports
            base64_data = self._frame_to_base64(frame_with_overlay)
            
            # Get file size
            file_size = os.path.getsize(snapshot_path)
            
            # Clean up
            cap.release()
            
            return {
                "snapshot_path": str(snapshot_path),
                "filename": filename,
                "frame_number": frame_number,
                "timestamp_ms": timestamp_ms,
                "failure_type": failure_type,
                "event_id": event_id,
                "base64_data": base64_data,
                "file_size_bytes": file_size,
                "video_fps": fps,
                "video_total_frames": total_frames,
                "captured_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error capturing failure snapshot: {str(e)}")
            return None
    
    def _add_failure_overlay(
        self, 
        frame: np.ndarray, 
        failure_type: str, 
        timestamp_ms: float, 
        frame_number: int
    ) -> np.ndarray:
        """
        Add failure information overlay to frame
        
        Overlays include:
        - Failure type (HIGH_LATENCY / MISSED_DETECTION)
        - Timestamp
        - Frame number
        - Failure indicator border
        """
        overlay_frame = frame.copy()
        height, width = frame.shape[:2]
        
        # Add red border for failures
        border_color = (0, 0, 255)  # Red in BGR
        border_thickness = 10
        cv2.rectangle(
            overlay_frame, 
            (0, 0), 
            (width-1, height-1), 
            border_color, 
            border_thickness
        )
        
        # Add text overlays
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        text_color = (255, 255, 255)  # White
        text_bg_color = (0, 0, 0)  # Black background
        thickness = 2
        
        # Failure type overlay (top-left)
        failure_text = f"FAILURE: {failure_type}"
        text_size = cv2.getTextSize(failure_text, font, font_scale, thickness)[0]
        text_x, text_y = 20, 40
        
        # Add black background for text
        cv2.rectangle(
            overlay_frame,
            (text_x - 10, text_y - text_size[1] - 10),
            (text_x + text_size[0] + 10, text_y + 10),
            text_bg_color,
            -1
        )
        cv2.putText(overlay_frame, failure_text, (text_x, text_y), font, font_scale, text_color, thickness)
        
        # Timestamp overlay (top-right)
        timestamp_text = f"T: {timestamp_ms/1000:.3f}s"
        timestamp_size = cv2.getTextSize(timestamp_text, font, font_scale, thickness)[0]
        timestamp_x = width - timestamp_size[0] - 20
        timestamp_y = 40
        
        cv2.rectangle(
            overlay_frame,
            (timestamp_x - 10, timestamp_y - timestamp_size[1] - 10),
            (timestamp_x + timestamp_size[0] + 10, timestamp_y + 10),
            text_bg_color,
            -1
        )
        cv2.putText(overlay_frame, timestamp_text, (timestamp_x, timestamp_y), font, font_scale, text_color, thickness)
        
        # Frame number overlay (bottom-left)
        frame_text = f"Frame: {frame_number}"
        frame_size = cv2.getTextSize(frame_text, font, font_scale, thickness)[0]
        frame_x, frame_y = 20, height - 20
        
        cv2.rectangle(
            overlay_frame,
            (frame_x - 10, frame_y - frame_size[1] - 10),
            (frame_x + frame_size[0] + 10, frame_y + 10),
            text_bg_color,
            -1
        )
        cv2.putText(overlay_frame, frame_text, (frame_x, frame_y), font, font_scale, text_color, thickness)
        
        return overlay_frame
    
    def _frame_to_base64(self, frame: np.ndarray) -> str:
        """
        Convert frame to base64 string for embedding in HTML reports
        """
        try:
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            # Convert to base64
            base64_data = base64.b64encode(buffer).decode('utf-8')
            
            return f"data:image/jpeg;base64,{base64_data}"
        except Exception as e:
            print(f"Error converting frame to base64: {str(e)}")
            return ""
    
    async def capture_success_thumbnail(
        self, 
        video_path: str, 
        timestamp_ms: float, 
        event_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Capture thumbnail for successful detection (optional, for detailed reports)
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_number = int((timestamp_ms / 1000) * fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if not ret:
                cap.release()
                return None
            
            # Resize for thumbnail
            thumbnail = cv2.resize(frame, (320, 240))
            
            # Add success overlay (green border)
            height, width = thumbnail.shape[:2]
            cv2.rectangle(thumbnail, (0, 0), (width-1, height-1), (0, 255, 0), 5)  # Green border
            
            # Save thumbnail
            filename = f"success_{event_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            thumbnail_path = self.snapshots_dir / "success" / filename
            thumbnail_path.parent.mkdir(exist_ok=True)
            
            cv2.imwrite(str(thumbnail_path), thumbnail)
            cap.release()
            
            return {
                "thumbnail_path": str(thumbnail_path),
                "filename": filename,
                "frame_number": frame_number,
                "timestamp_ms": timestamp_ms,
                "base64_data": self._frame_to_base64(thumbnail)
            }
            
        except Exception as e:
            print(f"Error capturing success thumbnail: {str(e)}")
            return None
    
    def cleanup_old_snapshots(self, days_old: int = 30):
        """
        Clean up snapshot files older than specified days
        """
        try:
            import time
            cutoff_time = time.time() - (days_old * 24 * 60 * 60)
            
            for snapshot_file in self.failure_snapshots_dir.iterdir():
                if snapshot_file.is_file() and snapshot_file.stat().st_mtime < cutoff_time:
                    snapshot_file.unlink()
                    print(f"Deleted old snapshot: {snapshot_file}")
            
        except Exception as e:
            print(f"Error cleaning up old snapshots: {str(e)}")
    
    def _add_text_background(self, frame: np.ndarray, x: int, y: int, text_size: Tuple[int, int], accent_color: Optional[Tuple[int, int, int]] = None):
        """Add enhanced text background with optional accent color"""
        padding = 8
        bg_color = (0, 0, 0, 200)  # Semi-transparent black
        
        # Main background
        cv2.rectangle(
            frame,
            (x - padding, y - text_size[1] - padding),
            (x + text_size[0] + padding, y + padding),
            (0, 0, 0),  # Black background
            -1
        )
        
        # Optional accent stripe
        if accent_color:
            cv2.rectangle(
                frame,
                (x - padding, y - text_size[1] - padding),
                (x - padding + 4, y + padding),
                accent_color,
                -1
            )
    
    def _add_detection_overlays(self, frame: np.ndarray, detection_data: Dict[str, Any], label_prefix: str = "") -> np.ndarray:
        """Add detection bounding boxes and labels to frame"""
        if 'bounding_box' not in detection_data:
            return frame
            
        bbox = detection_data['bounding_box']
        if isinstance(bbox, dict):
            x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('width', 0), bbox.get('height', 0)
        else:
            return frame
            
        # Draw bounding box
        color = (0, 255, 0)  # Green for actual detections
        cv2.rectangle(frame, (int(x), int(y)), (int(x + w), int(y + h)), color, 3)
        
        # Add label
        label = f"{label_prefix} "
        if 'class_label' in detection_data:
            label += detection_data['class_label']
        if 'confidence' in detection_data:
            label += f" ({detection_data['confidence']:.2%})"
            
        # Position label above bounding box
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        label_y = max(int(y) - 10, label_size[1] + 10)
        
        self._add_text_background(frame, int(x), label_y, label_size, color)
        cv2.putText(frame, label, (int(x), label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return frame
    
    def _add_expected_overlays(self, frame: np.ndarray, expected_data: Dict[str, Any]) -> np.ndarray:
        """Add expected/ground truth overlays to frame"""
        if 'bounding_box' in expected_data:
            bbox = expected_data['bounding_box']
            if isinstance(bbox, dict):
                x, y, w, h = bbox.get('x', 0), bbox.get('y', 0), bbox.get('width', 0), bbox.get('height', 0)
                
                # Draw expected bounding box in dashed style
                color = (255, 255, 0)  # Cyan for expected
                self._draw_dashed_rectangle(frame, (int(x), int(y)), (int(x + w), int(y + h)), color, 3)
                
                # Add "EXPECTED" label
                label = "EXPECTED"
                if 'class_label' in expected_data:
                    label += f" {expected_data['class_label']}"
                    
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                label_y = max(int(y) - 40, label_size[1] + 10)
                
                self._add_text_background(frame, int(x), label_y, label_size, color)
                cv2.putText(frame, label, (int(x), label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return frame
    
    def _draw_dashed_rectangle(self, frame: np.ndarray, pt1: Tuple[int, int], pt2: Tuple[int, int], color: Tuple[int, int, int], thickness: int):
        """Draw a dashed rectangle"""
        x1, y1 = pt1
        x2, y2 = pt2
        dash_length = 10
        
        # Top edge
        for x in range(x1, x2, dash_length * 2):
            cv2.line(frame, (x, y1), (min(x + dash_length, x2), y1), color, thickness)
        
        # Bottom edge  
        for x in range(x1, x2, dash_length * 2):
            cv2.line(frame, (x, y2), (min(x + dash_length, x2), y2), color, thickness)
            
        # Left edge
        for y in range(y1, y2, dash_length * 2):
            cv2.line(frame, (x1, y), (x1, min(y + dash_length, y2)), color, thickness)
            
        # Right edge
        for y in range(y1, y2, dash_length * 2):
            cv2.line(frame, (x2, y), (x2, min(y + dash_length, y2)), color, thickness)
    
    def _create_zoomed_region(self, frame: np.ndarray, bounding_box: Dict[str, Any], failure_type: str) -> Optional[np.ndarray]:
        """Create zoomed region around detection area"""
        try:
            x = getattr(bounding_box, 'x', bounding_box.get('x', 0) if hasattr(bounding_box, 'get') else 0)
            y = getattr(bounding_box, 'y', bounding_box.get('y', 0) if hasattr(bounding_box, 'get') else 0)
            w = getattr(bounding_box, 'width', bounding_box.get('width', 0) if hasattr(bounding_box, 'get') else 0)
            h = getattr(bounding_box, 'height', bounding_box.get('height', 0) if hasattr(bounding_box, 'get') else 0)
            
            # Calculate zoom region with padding
            padding = max(50, int(max(w, h) * 0.5))  # 50% padding around detection
            
            zoom_x1 = max(0, int(x - padding))
            zoom_y1 = max(0, int(y - padding))
            zoom_x2 = min(frame.shape[1], int(x + w + padding))
            zoom_y2 = min(frame.shape[0], int(y + h + padding))
            
            # Extract zoom region
            zoom_region = frame[zoom_y1:zoom_y2, zoom_x1:zoom_x2].copy()
            
            # Resize to standard size for consistency
            target_size = (400, 300)
            zoom_region = cv2.resize(zoom_region, target_size, interpolation=cv2.INTER_LANCZOS4)
            
            # Add zoom indicators
            border_color = self.failure_colors.get(failure_type, (0, 0, 255))
            cv2.rectangle(zoom_region, (0, 0), (target_size[0]-1, target_size[1]-1), border_color, 5)
            
            # Add "ZOOMED REGION" text
            zoom_text = "🔍 ZOOMED REGION"
            text_size = cv2.getTextSize(zoom_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            text_x = (target_size[0] - text_size[0]) // 2
            text_y = 30
            
            self._add_text_background(zoom_region, text_x, text_y, text_size, border_color)
            cv2.putText(zoom_region, zoom_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            return zoom_region
            
        except Exception as e:
            print(f"Error creating zoomed region: {str(e)}")
            return None
    
    def _create_comparison_view(self, frame: np.ndarray, detection_data: Optional[Dict[str, Any]], 
                              ground_truth_data: Dict[str, Any], failure_type: str) -> Optional[np.ndarray]:
        """Create side-by-side comparison view of expected vs actual"""
        try:
            height, width = frame.shape[:2]
            
            # Create comparison frame (2x width)
            comparison_frame = np.zeros((height, width * 2, 3), dtype=np.uint8)
            
            # Left side: Expected (ground truth)
            left_frame = frame.copy()
            left_frame = self._add_expected_overlays(left_frame, ground_truth_data)
            
            # Add "EXPECTED" header
            expected_text = "EXPECTED"
            text_size = cv2.getTextSize(expected_text, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)[0]
            text_x = (width - text_size[0]) // 2
            self._add_text_background(left_frame, text_x, 40, text_size, (255, 255, 0))
            cv2.putText(left_frame, expected_text, (text_x, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            
            # Right side: Actual (detection result)  
            right_frame = frame.copy()
            if detection_data:
                right_frame = self._add_detection_overlays(right_frame, detection_data, "ACTUAL")
            else:
                # Add "NO DETECTION" overlay for missed detections
                no_detect_text = "❌ NO DETECTION"
                text_size = cv2.getTextSize(no_detect_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)[0]
                text_x = (width - text_size[0]) // 2
                text_y = height // 2
                self._add_text_background(right_frame, text_x, text_y, text_size, (0, 0, 255))
                cv2.putText(right_frame, no_detect_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
            
            # Add "ACTUAL" header
            actual_text = "ACTUAL"
            text_size = cv2.getTextSize(actual_text, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)[0]
            text_x = (width - text_size[0]) // 2
            self._add_text_background(right_frame, text_x, 40, text_size, (0, 255, 0))
            cv2.putText(right_frame, actual_text, (text_x, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            
            # Combine frames
            comparison_frame[:, :width] = left_frame
            comparison_frame[:, width:] = right_frame
            
            # Add center divider
            cv2.line(comparison_frame, (width, 0), (width, height), (255, 255, 255), 3)
            
            # Add comparison title
            title_text = f"COMPARISON - {failure_type} FAILURE"
            title_size = cv2.getTextSize(title_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            title_x = (width * 2 - title_size[0]) // 2
            title_y = height - 20
            
            self._add_text_background(comparison_frame, title_x, title_y, title_size)
            cv2.putText(comparison_frame, title_text, (title_x, title_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            return comparison_frame
            
        except Exception as e:
            print(f"Error creating comparison view: {str(e)}")
            return None

    def get_snapshot_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about stored snapshots
        """
        try:
            # Get stats for all snapshot types
            stats = {
                "full_frame": self._get_directory_stats(self.full_frame_dir),
                "zoomed": self._get_directory_stats(self.zoomed_dir),
                "comparison": self._get_directory_stats(self.comparison_dir),
                "total_size_mb": 0,
                "total_snapshots": 0,
                "failure_type_breakdown": {},
                "storage_paths": {
                    "full_frame": str(self.full_frame_dir),
                    "zoomed": str(self.zoomed_dir),
                    "comparison": str(self.comparison_dir)
                }
            }
            
            # Calculate totals
            for snapshot_type in ["full_frame", "zoomed", "comparison"]:
                stats["total_size_mb"] += stats[snapshot_type]["size_mb"]
                stats["total_snapshots"] += stats[snapshot_type]["count"]
            
            # Analyze failure types
            for jpg_file in self.failure_snapshots_dir.rglob("*.jpg"):
                filename = jpg_file.name
                for failure_type in self.failure_colors.keys():
                    if failure_type.lower() in filename.lower():
                        if failure_type not in stats["failure_type_breakdown"]:
                            stats["failure_type_breakdown"][failure_type] = 0
                        stats["failure_type_breakdown"][failure_type] += 1
                        break
            
            return stats
        except Exception as e:
            print(f"Error getting snapshot stats: {str(e)}")
            return {}
    
    def _get_directory_stats(self, directory: Path) -> Dict[str, Any]:
        """Get statistics for a specific directory"""
        try:
            files = list(directory.glob("*.jpg"))
            total_size = sum(f.stat().st_size for f in files)
            
            return {
                "count": len(files),
                "size_bytes": total_size,
                "size_mb": round(total_size / (1024 * 1024), 2)
            }
        except Exception:
            return {"count": 0, "size_bytes": 0, "size_mb": 0}
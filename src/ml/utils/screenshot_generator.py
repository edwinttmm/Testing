"""
Screenshot generation with annotations for VRU detections
"""
import cv2
import numpy as np
import logging
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import json
import time
from datetime import datetime

from ..inference.yolo_service import Detection
from ..config import ml_config

logger = logging.getLogger(__name__)

class ScreenshotGenerator:
    """
    Generate annotated screenshots of VRU detections
    """
    
    def __init__(self):
        self.color_map = {
            "person": (0, 255, 0),        # Green for pedestrians
            "bicycle": (255, 0, 0),       # Blue for cyclists  
            "motorcycle": (0, 0, 255),    # Red for motorcyclists
            "wheelchair": (255, 255, 0),  # Cyan for wheelchairs
            "scooter": (255, 0, 255),     # Magenta for scooters
            "default": (255, 255, 255)    # White for unknown
        }
        
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 0.6
        self.thickness = ml_config.annotation_thickness
        
    def generate_annotated_screenshot(self, 
                                    frame: np.ndarray,
                                    detections: List[Detection],
                                    output_path: str,
                                    include_metadata: bool = True,
                                    draw_confidence: bool = True,
                                    draw_track_ids: bool = True) -> str:
        """
        Generate annotated screenshot with detection overlays
        
        Args:
            frame: Input frame
            detections: List of VRU detections
            output_path: Output file path
            include_metadata: Include metadata overlay
            draw_confidence: Draw confidence scores
            draw_track_ids: Draw track IDs if available
            
        Returns:
            Path to saved screenshot
        """
        try:
            annotated_frame = frame.copy()
            
            # Draw detection overlays
            for detection in detections:
                self._draw_detection(
                    annotated_frame, detection,
                    draw_confidence, draw_track_ids
                )
            
            # Add metadata overlay if requested
            if include_metadata:
                self._add_metadata_overlay(annotated_frame, detections)
            
            # Save screenshot with high quality
            success = cv2.imwrite(
                output_path, 
                annotated_frame,
                [cv2.IMWRITE_JPEG_QUALITY, ml_config.screenshot_quality]
            )
            
            if success:
                logger.debug(f"Screenshot saved: {output_path}")
                return output_path
            else:
                logger.error(f"Failed to save screenshot: {output_path}")
                return None
                
        except Exception as e:
            logger.error(f"Screenshot generation failed: {str(e)}")
            return None
    
    def _draw_detection(self, 
                       frame: np.ndarray, 
                       detection: Detection,
                       draw_confidence: bool = True,
                       draw_track_ids: bool = True):
        """Draw single detection on frame"""
        try:
            x1, y1, x2, y2 = map(int, detection.bbox)
            
            # Get color for class
            color = self.color_map.get(detection.class_name, self.color_map["default"])
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, self.thickness)
            
            # Prepare label text
            label_parts = [detection.class_name]
            
            if draw_confidence:
                label_parts.append(f"{detection.confidence:.2f}")
            
            if draw_track_ids and detection.track_id is not None:
                label_parts.append(f"ID:{detection.track_id}")
            
            label = " | ".join(label_parts)
            
            # Calculate label size and position
            (label_width, label_height), baseline = cv2.getTextSize(
                label, self.font, self.font_scale, 1
            )
            
            # Draw label background
            label_y = y1 - 10 if y1 - 10 > label_height else y2 + label_height + 10
            cv2.rectangle(
                frame,
                (x1, label_y - label_height - baseline),
                (x1 + label_width, label_y + baseline),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                frame, label, (x1, label_y - baseline),
                self.font, self.font_scale, (255, 255, 255), 1
            )
            
            # Draw center point
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            cv2.circle(frame, (center_x, center_y), 3, color, -1)
            
        except Exception as e:
            logger.error(f"Detection drawing failed: {str(e)}")
    
    def _add_metadata_overlay(self, frame: np.ndarray, detections: List[Detection]):
        """Add metadata overlay to frame"""
        try:
            height, width = frame.shape[:2]
            
            # Prepare metadata text
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            total_detections = len(detections)
            
            # Count by class
            class_counts = {}
            for detection in detections:
                class_name = detection.class_name
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            # Create metadata text
            metadata_lines = [
                f"Timestamp: {timestamp}",
                f"Total VRUs: {total_detections}",
                f"Model: {ml_config.model_name}",
                f"Device: {ml_config.get_device()}"
            ]
            
            # Add class breakdown
            if class_counts:
                class_info = ", ".join([f"{cls}: {count}" for cls, count in class_counts.items()])
                metadata_lines.append(f"Classes: {class_info}")
            
            # Draw metadata background
            line_height = 25
            metadata_height = len(metadata_lines) * line_height + 20
            metadata_width = max(len(line) * 12 for line in metadata_lines) + 20
            
            # Position metadata box
            box_x = width - metadata_width - 10
            box_y = 10
            
            # Draw background rectangle
            cv2.rectangle(
                frame,
                (box_x, box_y),
                (box_x + metadata_width, box_y + metadata_height),
                (0, 0, 0),  # Black background
                -1
            )
            
            # Draw border
            cv2.rectangle(
                frame,
                (box_x, box_y),
                (box_x + metadata_width, box_y + metadata_height),
                (255, 255, 255),  # White border
                2
            )
            
            # Draw metadata text
            for i, line in enumerate(metadata_lines):
                text_y = box_y + 20 + (i * line_height)
                cv2.putText(
                    frame, line, (box_x + 10, text_y),
                    self.font, 0.5, (255, 255, 255), 1
                )
                
        except Exception as e:
            logger.error(f"Metadata overlay failed: {str(e)}")
    
    def generate_detection_montage(self, 
                                 detections_data: List[Dict[str, Any]],
                                 output_path: str,
                                 grid_size: Tuple[int, int] = (3, 3),
                                 thumbnail_size: Tuple[int, int] = (300, 200)) -> str:
        """
        Generate a montage of detection screenshots
        
        Args:
            detections_data: List of detection data with frames and detections
            output_path: Output montage file path
            grid_size: Grid dimensions (cols, rows)
            thumbnail_size: Size of each thumbnail
            
        Returns:
            Path to saved montage
        """
        try:
            cols, rows = grid_size
            thumb_width, thumb_height = thumbnail_size
            
            # Create montage canvas
            montage_width = cols * thumb_width
            montage_height = rows * thumb_height
            montage = np.zeros((montage_height, montage_width, 3), dtype=np.uint8)
            
            # Fill montage with detection screenshots
            for i, detection_data in enumerate(detections_data[:cols * rows]):
                row = i // cols
                col = i % cols
                
                # Get frame and detections
                frame = detection_data.get("frame")
                detections = detection_data.get("detections", [])
                
                if frame is None:
                    continue
                
                # Create annotated thumbnail
                annotated_frame = frame.copy()
                for detection in detections:
                    self._draw_detection(annotated_frame, detection, True, True)
                
                # Resize to thumbnail size
                thumbnail = cv2.resize(annotated_frame, thumbnail_size)
                
                # Add frame number overlay
                frame_number = detection_data.get("frame_number", i)
                cv2.putText(
                    thumbnail, f"Frame {frame_number}", (10, 30),
                    self.font, 0.7, (255, 255, 255), 2
                )
                
                # Place in montage
                start_y = row * thumb_height
                end_y = start_y + thumb_height
                start_x = col * thumb_width
                end_x = start_x + thumb_width
                
                montage[start_y:end_y, start_x:end_x] = thumbnail
            
            # Add montage title
            title = f"VRU Detection Montage - {len(detections_data)} Frames"
            title_y = 30
            cv2.putText(
                montage, title, (10, title_y),
                self.font, 1.0, (255, 255, 255), 2
            )
            
            # Save montage
            success = cv2.imwrite(
                output_path,
                montage,
                [cv2.IMWRITE_JPEG_QUALITY, 95]
            )
            
            if success:
                logger.info(f"Detection montage saved: {output_path}")
                return output_path
            else:
                logger.error(f"Failed to save montage: {output_path}")
                return None
                
        except Exception as e:
            logger.error(f"Montage generation failed: {str(e)}")
            return None
    
    def generate_tracking_visualization(self,
                                      tracking_data: Dict[int, List[Detection]],
                                      frame_size: Tuple[int, int],
                                      output_path: str) -> str:
        """
        Generate visualization of tracking paths
        
        Args:
            tracking_data: Dictionary mapping frame numbers to detections
            frame_size: Size of visualization canvas
            output_path: Output file path
            
        Returns:
            Path to saved visualization
        """
        try:
            width, height = frame_size
            canvas = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Collect track paths
            track_paths = {}
            
            for frame_number, detections in tracking_data.items():
                for detection in detections:
                    if detection.track_id is not None:
                        track_id = detection.track_id
                        center_x = (detection.bbox[0] + detection.bbox[2]) / 2
                        center_y = (detection.bbox[1] + detection.bbox[3]) / 2
                        
                        if track_id not in track_paths:
                            track_paths[track_id] = []
                        
                        track_paths[track_id].append({
                            "frame": frame_number,
                            "center": (int(center_x), int(center_y)),
                            "class": detection.class_name
                        })
            
            # Draw track paths
            for track_id, path in track_paths.items():
                if len(path) < 2:
                    continue
                
                # Get color for track class
                class_name = path[0]["class"]
                color = self.color_map.get(class_name, self.color_map["default"])
                
                # Draw path lines
                for i in range(1, len(path)):
                    pt1 = path[i-1]["center"]
                    pt2 = path[i]["center"]
                    cv2.line(canvas, pt1, pt2, color, 2)
                
                # Draw start and end points
                start_point = path[0]["center"]
                end_point = path[-1]["center"]
                
                cv2.circle(canvas, start_point, 8, (0, 255, 0), -1)  # Green start
                cv2.circle(canvas, end_point, 8, (0, 0, 255), -1)    # Red end
                
                # Label track
                label = f"Track {track_id} ({class_name})"
                cv2.putText(
                    canvas, label, (end_point[0] + 10, end_point[1]),
                    self.font, 0.5, color, 1
                )
            
            # Add legend
            self._add_tracking_legend(canvas, track_paths)
            
            # Save visualization
            success = cv2.imwrite(
                output_path,
                canvas,
                [cv2.IMWRITE_JPEG_QUALITY, 95]
            )
            
            if success:
                logger.info(f"Tracking visualization saved: {output_path}")
                return output_path
            else:
                logger.error(f"Failed to save tracking visualization: {output_path}")
                return None
                
        except Exception as e:
            logger.error(f"Tracking visualization failed: {str(e)}")
            return None
    
    def _add_tracking_legend(self, canvas: np.ndarray, track_paths: Dict):
        """Add legend to tracking visualization"""
        try:
            height, width = canvas.shape[:2]
            
            # Count tracks by class
            class_track_counts = {}
            for track_id, path in track_paths.items():
                class_name = path[0]["class"]
                class_track_counts[class_name] = class_track_counts.get(class_name, 0) + 1
            
            # Draw legend background
            legend_height = len(class_track_counts) * 30 + 40
            legend_width = 200
            legend_x = width - legend_width - 10
            legend_y = 10
            
            cv2.rectangle(
                canvas,
                (legend_x, legend_y),
                (legend_x + legend_width, legend_y + legend_height),
                (50, 50, 50),
                -1
            )
            
            # Draw legend border
            cv2.rectangle(
                canvas,
                (legend_x, legend_y),
                (legend_x + legend_width, legend_y + legend_height),
                (255, 255, 255),
                2
            )
            
            # Add legend title
            cv2.putText(
                canvas, "Track Legend", (legend_x + 10, legend_y + 25),
                self.font, 0.6, (255, 255, 255), 1
            )
            
            # Add class entries
            y_offset = 50
            for class_name, count in class_track_counts.items():
                color = self.color_map.get(class_name, self.color_map["default"])
                
                # Draw color indicator
                cv2.circle(
                    canvas, 
                    (legend_x + 20, legend_y + y_offset), 
                    8, color, -1
                )
                
                # Draw text
                text = f"{class_name}: {count} tracks"
                cv2.putText(
                    canvas, text, (legend_x + 35, legend_y + y_offset + 5),
                    self.font, 0.4, (255, 255, 255), 1
                )
                
                y_offset += 30
                
        except Exception as e:
            logger.error(f"Legend generation failed: {str(e)}")

# Global screenshot generator instance
screenshot_generator = ScreenshotGenerator()
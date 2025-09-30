#!/usr/bin/env python3
"""
Video Timing Analysis Tool

This script analyzes the actual video timing vs detection timing to identify
why detections don't match what's actually visible in the video.

Key Analysis:
1. Extract video metadata (duration, FPS, frame timing)
2. Load detection events from database
3. Compare detection timestamps with actual video frame content
4. Identify timing discrepancies and offset issues
5. Visual frame extraction at detection points

Expected to find: Detection timestamps not corresponding to actual video content
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np
from dataclasses import dataclass, asdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('video_timing_analysis.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class VideoMetadata:
    """Video metadata structure"""
    filename: str
    filepath: str
    duration_seconds: float
    fps: float
    total_frames: int
    frame_duration_ms: float
    resolution: str
    filesize_bytes: int

@dataclass
class DetectionEvent:
    """Detection event from database"""
    id: str
    test_session_id: str
    video_id: str
    timestamp: float
    validation_result: str
    latency_ms: Optional[float]
    labjack_timestamp: Optional[float]
    video_start_time: Optional[float]
    frame_number: Optional[int]
    video_relative_timestamp: Optional[float]
    actual_latency_ms: Optional[float]
    timing_sync_quality: str

@dataclass
class GroundTruthEvent:
    """Ground truth event from database"""
    id: str
    video_id: str
    timestamp: float
    frame_number: Optional[int]
    class_label: str
    x: float
    y: float
    width: float
    height: float
    confidence: Optional[float]

@dataclass
class TimingAnalysisResult:
    """Analysis result structure"""
    video_metadata: VideoMetadata
    detection_events: List[DetectionEvent]
    ground_truth_events: List[GroundTruthEvent]
    timing_discrepancies: List[Dict[str, Any]]
    frame_analysis: List[Dict[str, Any]]
    recommendations: List[str]
    analysis_timestamp: str

class VideoTimingAnalyzer:
    """Main video timing analysis class"""
    
    def __init__(self, video_path: str, database_path: str = "dev_database.db"):
        self.video_path = Path(video_path)
        self.database_path = Path(database_path)
        self.analysis_dir = Path("timing_analysis_output")
        self.analysis_dir.mkdir(exist_ok=True)
        
        # Verify video exists
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        logger.info(f"Initialized analyzer for video: {self.video_path}")
        logger.info(f"Database: {self.database_path}")
        logger.info(f"Output directory: {self.analysis_dir}")
    
    def extract_video_metadata(self) -> VideoMetadata:
        """Extract comprehensive video metadata using OpenCV"""
        logger.info("Extracting video metadata...")
        
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise Exception(f"Could not open video file: {self.video_path}")
        
        try:
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration_seconds = total_frames / fps if fps > 0 else 0
            frame_duration_ms = 1000.0 / fps if fps > 0 else 0
            
            metadata = VideoMetadata(
                filename=self.video_path.name,
                filepath=str(self.video_path),
                duration_seconds=duration_seconds,
                fps=fps,
                total_frames=total_frames,
                frame_duration_ms=frame_duration_ms,
                resolution=f"{width}x{height}",
                filesize_bytes=self.video_path.stat().st_size
            )
            
            logger.info(f"Video metadata extracted:")
            logger.info(f"  Duration: {duration_seconds:.3f} seconds")
            logger.info(f"  FPS: {fps:.2f}")
            logger.info(f"  Total frames: {total_frames}")
            logger.info(f"  Frame duration: {frame_duration_ms:.3f} ms")
            logger.info(f"  Resolution: {width}x{height}")
            
            return metadata
            
        finally:
            cap.release()
    
    def load_detection_events(self) -> List[DetectionEvent]:
        """Load detection events from database"""
        logger.info("Loading detection events from database...")
        
        if not self.database_path.exists():
            logger.warning(f"Database file not found: {self.database_path}")
            return []
        
        try:
            conn = sqlite3.connect(str(self.database_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get video ID first
            video_filename = self.video_path.name
            cursor.execute("""
                SELECT id FROM videos WHERE filename = ?
            """, (video_filename,))
            video_row = cursor.fetchone()
            
            if not video_row:
                logger.warning(f"Video not found in database: {video_filename}")
                return []
            
            video_id = video_row['id']
            logger.info(f"Found video ID: {video_id}")
            
            # Load detection events for this video
            cursor.execute("""
                SELECT 
                    de.id,
                    de.test_session_id,
                    de.video_id,
                    de.timestamp,
                    de.validation_result,
                    de.actual_latency_ms,
                    de.labjack_timestamp,
                    de.video_start_time,
                    de.frame_number,
                    de.video_relative_timestamp,
                    de.timing_sync_quality,
                    ts.created_at,
                    ts.video_playback_start_time
                FROM detection_events de
                LEFT JOIN test_sessions ts ON de.test_session_id = ts.id
                WHERE de.video_id = ?
                ORDER BY de.timestamp
            """, (video_id,))
            
            events = []
            for row in cursor.fetchall():
                event = DetectionEvent(
                    id=row['id'],
                    test_session_id=row['test_session_id'],
                    video_id=row['video_id'],
                    timestamp=row['timestamp'],
                    validation_result=row['validation_result'] or 'Unknown',
                    latency_ms=row['actual_latency_ms'],
                    labjack_timestamp=row['labjack_timestamp'],
                    video_start_time=row['video_start_time'],
                    frame_number=row['frame_number'],
                    video_relative_timestamp=row['video_relative_timestamp'],
                    actual_latency_ms=row['actual_latency_ms'],
                    timing_sync_quality=row['timing_sync_quality'] or 'unknown'
                )
                events.append(event)
            
            logger.info(f"Loaded {len(events)} detection events")
            return events
            
        except Exception as e:
            logger.error(f"Error loading detection events: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
    
    def load_ground_truth_events(self) -> List[GroundTruthEvent]:
        """Load ground truth events from database"""
        logger.info("Loading ground truth events from database...")
        
        if not self.database_path.exists():
            logger.warning(f"Database file not found: {self.database_path}")
            return []
        
        try:
            conn = sqlite3.connect(str(self.database_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get video ID first
            video_filename = self.video_path.name
            cursor.execute("""
                SELECT id FROM videos WHERE filename = ?
            """, (video_filename,))
            video_row = cursor.fetchone()
            
            if not video_row:
                logger.warning(f"Video not found in database: {video_filename}")
                return []
            
            video_id = video_row['id']
            
            # Load ground truth events
            cursor.execute("""
                SELECT 
                    id,
                    video_id,
                    timestamp,
                    frame_number,
                    class_label,
                    x,
                    y,
                    width,
                    height,
                    confidence
                FROM ground_truth_objects
                WHERE video_id = ?
                ORDER BY timestamp
            """, (video_id,))
            
            events = []
            for row in cursor.fetchall():
                event = GroundTruthEvent(
                    id=row['id'],
                    video_id=row['video_id'],
                    timestamp=row['timestamp'],
                    frame_number=row['frame_number'],
                    class_label=row['class_label'],
                    x=row['x'],
                    y=row['y'],
                    width=row['width'],
                    height=row['height'],
                    confidence=row['confidence']
                )
                events.append(event)
            
            logger.info(f"Loaded {len(events)} ground truth events")
            return events
            
        except Exception as e:
            logger.error(f"Error loading ground truth events: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
    
    def calculate_frame_timing(self, metadata: VideoMetadata) -> Dict[int, Dict[str, float]]:
        """Calculate precise frame timing"""
        frame_timing = {}
        
        for frame_num in range(1, min(metadata.total_frames + 1, 100)):  # First 100 frames
            # Frame timing starts at 0 for frame 1
            timestamp_seconds = (frame_num - 1) / metadata.fps
            timestamp_ms = timestamp_seconds * 1000
            
            frame_timing[frame_num] = {
                'timestamp_seconds': timestamp_seconds,
                'timestamp_ms': timestamp_ms,
                'frame_duration_ms': metadata.frame_duration_ms
            }
        
        return frame_timing
    
    def extract_frame_at_timestamp(self, timestamp_seconds: float, output_path: str, 
                                   bbox: Optional[Dict[str, float]] = None) -> bool:
        """Extract frame at specific timestamp"""
        try:
            cap = cv2.VideoCapture(str(self.video_path))
            if not cap.isOpened():
                return False
            
            # Seek to timestamp
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_seconds * 1000)
            ret, frame = cap.read()
            
            if not ret:
                cap.release()
                return False
            
            # Draw bounding box if provided
            if bbox:
                x, y, w, h = int(bbox['x']), int(bbox['y']), int(bbox['width']), int(bbox['height'])
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, f"GT: {bbox.get('class_label', 'unknown')}", 
                           (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add timestamp overlay
            cv2.putText(frame, f"t={timestamp_seconds:.3f}s", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            cv2.imwrite(output_path, frame)
            cap.release()
            return True
            
        except Exception as e:
            logger.error(f"Error extracting frame at {timestamp_seconds}s: {e}")
            return False
    
    def analyze_timing_discrepancies(self, metadata: VideoMetadata, 
                                   detection_events: List[DetectionEvent],
                                   ground_truth_events: List[GroundTruthEvent]) -> List[Dict[str, Any]]:
        """Analyze timing discrepancies between detections and expected content"""
        logger.info("Analyzing timing discrepancies...")
        
        discrepancies = []
        frame_timing = self.calculate_frame_timing(metadata)
        
        for detection in detection_events:
            discrepancy = {
                'detection_id': detection.id,
                'detection_timestamp': detection.timestamp,
                'detection_frame_number': detection.frame_number,
                'validation_result': detection.validation_result,
                'issues': []
            }
            
            # Calculate expected frame from timestamp
            if detection.timestamp > 0:
                expected_frame = int(detection.timestamp * metadata.fps) + 1
                discrepancy['expected_frame_from_timestamp'] = expected_frame
                
                # Check if frame number matches expected
                if detection.frame_number and abs(detection.frame_number - expected_frame) > 1:
                    discrepancy['issues'].append({
                        'type': 'frame_timestamp_mismatch',
                        'description': f"Frame number {detection.frame_number} doesn't match expected {expected_frame} from timestamp {detection.timestamp:.3f}s",
                        'severity': 'HIGH'
                    })
            
            # Check if detection timestamp corresponds to video content
            matching_gt = None
            min_time_diff = float('inf')
            
            for gt in ground_truth_events:
                time_diff = abs(gt.timestamp - detection.timestamp)
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    matching_gt = gt
            
            if matching_gt:
                discrepancy['closest_ground_truth'] = {
                    'gt_id': matching_gt.id,
                    'gt_timestamp': matching_gt.timestamp,
                    'time_difference': min_time_diff,
                    'gt_class': matching_gt.class_label
                }
                
                # Flag large time differences
                if min_time_diff > 0.1:  # 100ms threshold
                    discrepancy['issues'].append({
                        'type': 'ground_truth_timing_mismatch',
                        'description': f"Detection at {detection.timestamp:.3f}s is {min_time_diff:.3f}s away from closest GT at {matching_gt.timestamp:.3f}s",
                        'severity': 'MEDIUM' if min_time_diff < 0.5 else 'HIGH'
                    })
            else:
                discrepancy['issues'].append({
                    'type': 'no_matching_ground_truth',
                    'description': f"No ground truth found near detection timestamp {detection.timestamp:.3f}s",
                    'severity': 'HIGH'
                })
            
            # Check video relative timing
            if detection.video_relative_timestamp:
                expected_video_time = detection.video_relative_timestamp
                if abs(expected_video_time - detection.timestamp) > 0.05:  # 50ms threshold
                    discrepancy['issues'].append({
                        'type': 'video_relative_timing_mismatch',
                        'description': f"Video relative timestamp {expected_video_time:.3f}s differs from detection timestamp {detection.timestamp:.3f}s",
                        'severity': 'MEDIUM'
                    })
            
            discrepancies.append(discrepancy)
        
        logger.info(f"Found {len(discrepancies)} detection events with {sum(len(d['issues']) for d in discrepancies)} total timing issues")
        return discrepancies
    
    def perform_frame_analysis(self, metadata: VideoMetadata, 
                              detection_events: List[DetectionEvent],
                              ground_truth_events: List[GroundTruthEvent]) -> List[Dict[str, Any]]:
        """Perform detailed frame-by-frame analysis"""
        logger.info("Performing frame analysis...")
        
        frame_analysis = []
        
        # Analyze key frames
        key_frames = [1, 5, 10, 20]  # Frame numbers to analyze
        
        for frame_num in key_frames:
            if frame_num > metadata.total_frames:
                continue
                
            frame_timestamp = (frame_num - 1) / metadata.fps
            
            analysis = {
                'frame_number': frame_num,
                'timestamp_seconds': frame_timestamp,
                'timestamp_ms': frame_timestamp * 1000,
                'expected_content': [],
                'detections_at_frame': [],
                'frame_extracted': False
            }
            
            # Find ground truth at this frame
            for gt in ground_truth_events:
                if gt.frame_number == frame_num:
                    analysis['expected_content'].append({
                        'class': gt.class_label,
                        'bbox': {'x': gt.x, 'y': gt.y, 'width': gt.width, 'height': gt.height},
                        'confidence': gt.confidence
                    })
            
            # Find detections near this frame time
            for detection in detection_events:
                time_diff = abs(detection.timestamp - frame_timestamp)
                if time_diff < 0.1:  # Within 100ms
                    analysis['detections_at_frame'].append({
                        'detection_id': detection.id,
                        'timestamp': detection.timestamp,
                        'time_difference': time_diff,
                        'validation_result': detection.validation_result
                    })
            
            # Extract frame image
            frame_output = self.analysis_dir / f"frame_{frame_num:03d}_t{frame_timestamp:.3f}s.jpg"
            bbox = analysis['expected_content'][0] if analysis['expected_content'] else None
            if self.extract_frame_at_timestamp(frame_timestamp, str(frame_output), bbox):
                analysis['frame_extracted'] = True
                analysis['frame_path'] = str(frame_output)
            
            frame_analysis.append(analysis)
        
        return frame_analysis
    
    def generate_recommendations(self, metadata: VideoMetadata,
                               discrepancies: List[Dict[str, Any]],
                               ground_truth_events: List[GroundTruthEvent],
                               detection_events: List[DetectionEvent]) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Count issues by type
        issue_counts = {}
        for disc in discrepancies:
            for issue in disc['issues']:
                issue_type = issue['type']
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        # Frame timing issues
        if issue_counts.get('frame_timestamp_mismatch', 0) > 0:
            recommendations.append(
                f"CRITICAL: {issue_counts['frame_timestamp_mismatch']} frame/timestamp mismatches detected. "
                "Check frame number calculation logic in detection pipeline."
            )
        
        # Ground truth timing issues
        if issue_counts.get('ground_truth_timing_mismatch', 0) > 0:
            recommendations.append(
                f"HIGH: {issue_counts['ground_truth_timing_mismatch']} detections don't align with ground truth timing. "
                "Verify video start time synchronization and timing reference points."
            )
        
        # Video relative timing issues
        if issue_counts.get('video_relative_timing_mismatch', 0) > 0:
            recommendations.append(
                f"MEDIUM: {issue_counts['video_relative_timing_mismatch']} video relative timing mismatches. "
                "Check video playback start time calculation."
            )
        
        # No ground truth matches
        if issue_counts.get('no_matching_ground_truth', 0) > 0:
            recommendations.append(
                f"HIGH: {issue_counts['no_matching_ground_truth']} detections have no nearby ground truth. "
                "Either detections are happening at wrong times or ground truth is incomplete."
            )
        
        # Overall timing health
        total_detections = len(detection_events)
        clean_detections = len([d for d in discrepancies if not d['issues']])
        if total_detections > 0:
            health_percent = (clean_detections / total_detections) * 100
            recommendations.append(
                f"Timing health: {clean_detections}/{total_detections} ({health_percent:.1f}%) detections have clean timing."
            )
            
            if health_percent < 50:
                recommendations.append(
                    "CRITICAL: Less than 50% of detections have clean timing. "
                    "Major timing synchronization issues detected."
                )
        
        # Frame rate analysis
        if metadata.fps < 24:
            recommendations.append(
                f"WARNING: Low frame rate ({metadata.fps:.2f} FPS) may cause timing precision issues."
            )
        
        return recommendations
    
    def run_analysis(self) -> TimingAnalysisResult:
        """Run complete timing analysis"""
        logger.info("=== Starting Video Timing Analysis ===")
        
        # Extract video metadata
        metadata = self.extract_video_metadata()
        
        # Load database events
        detection_events = self.load_detection_events()
        ground_truth_events = self.load_ground_truth_events()
        
        # Perform timing analysis
        discrepancies = self.analyze_timing_discrepancies(metadata, detection_events, ground_truth_events)
        
        # Perform frame analysis
        frame_analysis = self.perform_frame_analysis(metadata, detection_events, ground_truth_events)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(metadata, discrepancies, ground_truth_events, detection_events)
        
        # Create result object
        result = TimingAnalysisResult(
            video_metadata=metadata,
            detection_events=detection_events,
            ground_truth_events=ground_truth_events,
            timing_discrepancies=discrepancies,
            frame_analysis=frame_analysis,
            recommendations=recommendations,
            analysis_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        return result
    
    def save_analysis_report(self, result: TimingAnalysisResult) -> str:
        """Save analysis report to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.analysis_dir / f"video_timing_analysis_report_{timestamp}.json"
        
        # Convert dataclasses to dict for JSON serialization
        report_data = {
            'video_metadata': asdict(result.video_metadata),
            'detection_events': [asdict(de) for de in result.detection_events],
            'ground_truth_events': [asdict(gte) for gte in result.ground_truth_events],
            'timing_discrepancies': result.timing_discrepancies,
            'frame_analysis': result.frame_analysis,
            'recommendations': result.recommendations,
            'analysis_timestamp': result.analysis_timestamp,
            'summary': {
                'total_detection_events': len(result.detection_events),
                'total_ground_truth_events': len(result.ground_truth_events),
                'total_timing_issues': sum(len(d['issues']) for d in result.timing_discrepancies),
                'frames_analyzed': len(result.frame_analysis),
                'frames_extracted': sum(1 for fa in result.frame_analysis if fa['frame_extracted'])
            }
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        logger.info(f"Analysis report saved to: {report_file}")
        return str(report_file)


def main():
    """Main analysis execution"""
    # Configuration
    video_path = "/home/rigade/Testing/ai-model-validation-platform/backend/uploads/Child_20250923_163333.mp4"
    database_paths = [
        "/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db",
        "/home/rigade/Testing/ai-model-validation-platform/backend/test_database.db",
        "./dev_database.db"
    ]
    
    # Find existing database
    database_path = None
    for db_path in database_paths:
        if os.path.exists(db_path):
            database_path = db_path
            break
    
    if not database_path:
        logger.error("No database file found. Checked paths:")
        for path in database_paths:
            logger.error(f"  {path}")
        return
    
    try:
        # Create analyzer
        analyzer = VideoTimingAnalyzer(video_path, database_path)
        
        # Run analysis
        result = analyzer.run_analysis()
        
        # Save report
        report_path = analyzer.save_analysis_report(result)
        
        # Print summary
        print("\n" + "="*80)
        print("VIDEO TIMING ANALYSIS SUMMARY")
        print("="*80)
        print(f"Video: {result.video_metadata.filename}")
        print(f"Duration: {result.video_metadata.duration_seconds:.3f} seconds")
        print(f"FPS: {result.video_metadata.fps:.2f}")
        print(f"Total Frames: {result.video_metadata.total_frames}")
        print(f"Frame Duration: {result.video_metadata.frame_duration_ms:.3f} ms")
        print(f"")
        print(f"Detection Events: {len(result.detection_events)}")
        print(f"Ground Truth Events: {len(result.ground_truth_events)}")
        print(f"Timing Issues Found: {sum(len(d['issues']) for d in result.timing_discrepancies)}")
        print(f"Frames Analyzed: {len(result.frame_analysis)}")
        print(f"")
        print("RECOMMENDATIONS:")
        for i, rec in enumerate(result.recommendations, 1):
            print(f"{i:2d}. {rec}")
        print(f"")
        print(f"Full report saved to: {report_path}")
        print("="*80)
        
        # Print critical issues
        critical_issues = []
        for disc in result.timing_discrepancies:
            for issue in disc['issues']:
                if issue['severity'] == 'HIGH':
                    critical_issues.append(f"Detection {disc['detection_id']}: {issue['description']}")
        
        if critical_issues:
            print("\nCRITICAL TIMING ISSUES:")
            for issue in critical_issues[:10]:  # Show first 10
                print(f"  • {issue}")
            if len(critical_issues) > 10:
                print(f"  ... and {len(critical_issues) - 10} more critical issues")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
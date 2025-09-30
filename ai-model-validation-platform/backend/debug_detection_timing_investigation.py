#!/usr/bin/env python3
"""
Enhanced Detection Timing Investigation

This script investigates the suspicious pattern where all detections happen at
perfect frame intervals, which suggests artificial timing rather than real detection.

Key Investigation Areas:
1. Detection timestamp patterns (too regular = artificial)
2. Comparison between ground truth and actual video content
3. Frame-by-frame visual inspection
4. LabJack vs AI detection timing analysis
"""

import os
import sys
import json
import sqlite3
import logging
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DetectionTimingInvestigator:
    """Investigate suspicious detection timing patterns"""
    
    def __init__(self, video_path: str, database_path: str = "dev_database.db"):
        self.video_path = Path(video_path)
        self.database_path = Path(database_path)
        self.output_dir = Path("detection_timing_investigation")
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"Investigating video: {self.video_path}")
        logger.info(f"Database: {self.database_path}")
        
    def analyze_detection_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in detection timestamps"""
        logger.info("Analyzing detection timestamp patterns...")
        
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get video ID
        cursor.execute("SELECT id FROM videos WHERE filename = ?", (self.video_path.name,))
        video_row = cursor.fetchone()
        if not video_row:
            return {"error": "Video not found in database"}
        
        video_id = video_row['id']
        
        # Load detection events
        cursor.execute("""
            SELECT 
                id,
                timestamp,
                frame_number,
                validation_result,
                labjack_timestamp,
                video_relative_timestamp,
                actual_latency_ms,
                created_at
            FROM detection_events 
            WHERE video_id = ? 
            ORDER BY timestamp
        """, (video_id,))
        
        detections = cursor.fetchall()
        conn.close()
        
        if not detections:
            return {"error": "No detections found"}
        
        # Analyze patterns
        timestamps = [d['timestamp'] for d in detections]
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        
        analysis = {
            "total_detections": len(detections),
            "timestamp_range": f"{min(timestamps):.3f}s - {max(timestamps):.3f}s",
            "intervals": {
                "mean": np.mean(intervals),
                "std": np.std(intervals),
                "min": min(intervals),
                "max": max(intervals),
                "all_intervals": [round(i, 6) for i in intervals]
            },
            "regularity_analysis": {
                "extremely_regular": np.std(intervals) < 0.001,  # < 1ms variation
                "too_perfect": all(abs(i - 0.208333) < 0.001 for i in intervals),  # All exactly 5 frames apart
                "artificial_pattern": True if np.std(intervals) < 0.001 else False
            },
            "frame_analysis": {
                "frame_numbers": [d['frame_number'] for d in detections if d['frame_number']],
                "frame_intervals": []
            }
        }
        
        # Check frame intervals
        frame_numbers = [d['frame_number'] for d in detections if d['frame_number']]
        if len(frame_numbers) > 1:
            frame_intervals = [frame_numbers[i+1] - frame_numbers[i] for i in range(len(frame_numbers)-1)]
            analysis["frame_analysis"]["frame_intervals"] = frame_intervals
            analysis["frame_analysis"]["all_same_interval"] = len(set(frame_intervals)) == 1
            analysis["frame_analysis"]["interval_value"] = frame_intervals[0] if frame_intervals else None
        
        return analysis
    
    def compare_ground_truth_vs_video_content(self) -> Dict[str, Any]:
        """Compare ground truth locations with actual video content"""
        logger.info("Comparing ground truth with actual video content...")
        
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get video ID
        cursor.execute("SELECT id FROM videos WHERE filename = ?", (self.video_path.name,))
        video_row = cursor.fetchone()
        video_id = video_row['id']
        
        # Load ground truth
        cursor.execute("""
            SELECT 
                id,
                timestamp,
                frame_number,
                class_label,
                x, y, width, height,
                confidence
            FROM ground_truth_objects 
            WHERE video_id = ? 
            ORDER BY timestamp
        """, (video_id,))
        
        ground_truth = cursor.fetchall()
        conn.close()
        
        # Open video
        cap = cv2.VideoCapture(str(self.video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        analysis = {
            "ground_truth_count": len(ground_truth),
            "frame_inspections": []
        }
        
        # Inspect specific frames
        key_frames = [1, 5, 10, 15, 20]  # Based on detection pattern
        
        for frame_num in key_frames:
            if frame_num > cap.get(cv2.CAP_PROP_FRAME_COUNT):
                continue
                
            # Seek to frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num - 1)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # Find ground truth for this frame
            frame_gt = [gt for gt in ground_truth if gt['frame_number'] == frame_num]
            
            # Calculate timestamp from frame number
            expected_timestamp = (frame_num - 1) / fps
            
            inspection = {
                "frame_number": frame_num,
                "expected_timestamp": expected_timestamp,
                "ground_truth_count": len(frame_gt),
                "ground_truth_objects": []
            }
            
            # Analyze each ground truth object
            for gt in frame_gt:
                x, y, w, h = int(gt['x']), int(gt['y']), int(gt['width']), int(gt['height'])
                
                # Extract the region of interest
                if 0 <= x < frame.shape[1] and 0 <= y < frame.shape[0] and w > 0 and h > 0:
                    roi = frame[y:y+h, x:x+w] if y+h <= frame.shape[0] and x+w <= frame.shape[1] else None
                    
                    gt_analysis = {
                        "gt_id": gt['id'],
                        "class_label": gt['class_label'],
                        "bbox": [x, y, w, h],
                        "timestamp": gt['timestamp'],
                        "roi_valid": roi is not None,
                        "roi_size": [w, h] if roi is not None else None
                    }
                    
                    # Simple motion detection in ROI
                    if roi is not None and roi.size > 0:
                        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        gt_analysis["roi_brightness_mean"] = float(np.mean(roi_gray))
                        gt_analysis["roi_has_content"] = np.std(roi_gray) > 10  # Some variation = content
                    
                    inspection["ground_truth_objects"].append(gt_analysis)
                    
                    # Save frame with bounding box
                    frame_with_bbox = frame.copy()
                    cv2.rectangle(frame_with_bbox, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    cv2.putText(frame_with_bbox, f"Frame {frame_num} - GT", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    output_path = self.output_dir / f"frame_{frame_num:03d}_with_gt.jpg"
                    cv2.imwrite(str(output_path), frame_with_bbox)
            
            analysis["frame_inspections"].append(inspection)
        
        cap.release()
        return analysis
    
    def investigate_detection_source(self) -> Dict[str, Any]:
        """Investigate the source of detections - LabJack vs AI"""
        logger.info("Investigating detection source...")
        
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get video ID
        cursor.execute("SELECT id FROM videos WHERE filename = ?", (self.video_path.name,))
        video_row = cursor.fetchone()
        video_id = video_row['id']
        
        # Load detection events with full details
        cursor.execute("""
            SELECT 
                de.*,
                ts.name as session_name,
                ts.created_at as session_created,
                ts.video_playback_start_time
            FROM detection_events de
            LEFT JOIN test_sessions ts ON de.test_session_id = ts.id
            WHERE de.video_id = ?
            ORDER BY de.timestamp
        """, (video_id,))
        
        detections = cursor.fetchall()
        conn.close()
        
        analysis = {
            "detection_sources": {
                "labjack_detections": 0,
                "ai_detections": 0,
                "manual_detections": 0,
                "unknown_source": 0
            },
            "timing_data_availability": {
                "has_labjack_timestamp": 0,
                "has_video_relative_timestamp": 0,
                "has_actual_latency": 0,
                "has_frame_number": 0
            },
            "detection_details": []
        }
        
        for detection in detections:
            # Determine source
            source = "unknown"
            if detection['labjack_timestamp']:
                analysis["detection_sources"]["labjack_detections"] += 1
                source = "labjack"
            elif detection['source'] == 'manual':
                analysis["detection_sources"]["manual_detections"] += 1
                source = "manual"
            elif detection['confidence'] is not None:
                analysis["detection_sources"]["ai_detections"] += 1
                source = "ai"
            else:
                analysis["detection_sources"]["unknown_source"] += 1
            
            # Check timing data availability
            if detection['labjack_timestamp']:
                analysis["timing_data_availability"]["has_labjack_timestamp"] += 1
            if detection['video_relative_timestamp']:
                analysis["timing_data_availability"]["has_video_relative_timestamp"] += 1
            if detection['actual_latency_ms']:
                analysis["timing_data_availability"]["has_actual_latency"] += 1
            if detection['frame_number']:
                analysis["timing_data_availability"]["has_frame_number"] += 1
            
            # Collect details
            detail = {
                "id": detection['id'],
                "timestamp": detection['timestamp'],
                "frame_number": detection['frame_number'],
                "source": source,
                "validation_result": detection['validation_result'],
                "has_bbox": bool(detection['bounding_box_x']),
                "confidence": detection['confidence'],
                "class_label": detection['class_label']
            }
            analysis["detection_details"].append(detail)
        
        return analysis
    
    def run_investigation(self) -> Dict[str, Any]:
        """Run complete investigation"""
        logger.info("=== Starting Detection Timing Investigation ===")
        
        results = {
            "video_file": str(self.video_path),
            "investigation_timestamp": datetime.now().isoformat(),
            "pattern_analysis": self.analyze_detection_patterns(),
            "ground_truth_comparison": self.compare_ground_truth_vs_video_content(),
            "detection_source_analysis": self.investigate_detection_source()
        }
        
        # Generate conclusions
        conclusions = []
        
        # Check for artificial patterns
        pattern = results["pattern_analysis"]
        if pattern.get("regularity_analysis", {}).get("artificial_pattern"):
            conclusions.append("🚨 CRITICAL: Detections follow artificial pattern - intervals too regular")
            conclusions.append(f"   All intervals are {pattern['intervals']['mean']:.6f}s ± {pattern['intervals']['std']:.6f}s")
        
        if pattern.get("regularity_analysis", {}).get("too_perfect"):
            conclusions.append("🚨 CRITICAL: All detections exactly 5 frames apart - this is NOT natural")
        
        # Check frame intervals
        frame_analysis = pattern.get("frame_analysis", {})
        if frame_analysis.get("all_same_interval") and frame_analysis.get("interval_value") == 5:
            conclusions.append("🚨 CRITICAL: All detections exactly every 5th frame - artificially generated")
        
        # Check detection source
        source_analysis = results["detection_source_analysis"]
        total_detections = sum(source_analysis["detection_sources"].values())
        ai_detections = source_analysis["detection_sources"]["ai_detections"]
        
        if ai_detections == total_detections:
            conclusions.append("ℹ️  INFO: All detections are AI-generated (not LabJack hardware)")
        
        if source_analysis["timing_data_availability"]["has_labjack_timestamp"] == 0:
            conclusions.append("⚠️  WARNING: No LabJack timestamps found - not true HIL testing")
        
        # Check ground truth alignment
        gt_comparison = results["ground_truth_comparison"]
        frame_inspections = gt_comparison.get("frame_inspections", [])
        
        has_actual_content = any(
            any(obj.get("roi_has_content", False) for obj in inspection.get("ground_truth_objects", []))
            for inspection in frame_inspections
        )
        
        if not has_actual_content:
            conclusions.append("🚨 CRITICAL: Ground truth bounding boxes don't contain meaningful visual content")
        
        results["conclusions"] = conclusions
        
        return results
    
    def save_investigation_report(self, results: Dict[str, Any]) -> str:
        """Save investigation report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"detection_timing_investigation_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Investigation report saved to: {report_file}")
        return str(report_file)


def main():
    """Main investigation execution"""
    video_path = "/home/rigade/Testing/ai-model-validation-platform/backend/uploads/Child_20250923_163333.mp4"
    database_path = "/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db"
    
    try:
        investigator = DetectionTimingInvestigator(video_path, database_path)
        results = investigator.run_investigation()
        report_path = investigator.save_investigation_report(results)
        
        print("\n" + "="*80)
        print("DETECTION TIMING INVESTIGATION RESULTS")
        print("="*80)
        
        # Print pattern analysis
        pattern = results["pattern_analysis"]
        print(f"Detection Pattern Analysis:")
        print(f"  Total detections: {pattern['total_detections']}")
        print(f"  Timestamp range: {pattern['timestamp_range']}")
        print(f"  Interval std deviation: {pattern['intervals']['std']:.6f}s")
        print(f"  Extremely regular: {pattern['regularity_analysis']['extremely_regular']}")
        print(f"  Too perfect: {pattern['regularity_analysis']['too_perfect']}")
        print(f"  Artificial pattern: {pattern['regularity_analysis']['artificial_pattern']}")
        
        # Print source analysis
        source = results["detection_source_analysis"]
        print(f"\nDetection Source Analysis:")
        for source_type, count in source["detection_sources"].items():
            print(f"  {source_type}: {count}")
        
        # Print conclusions
        print(f"\nCONCLUSIONS:")
        for i, conclusion in enumerate(results["conclusions"], 1):
            print(f"{i:2d}. {conclusion}")
        
        print(f"\nFull report: {report_path}")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Investigation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Video Startup Delay Hypothesis Validation Script

This script analyzes actual timing data to validate the hypothesis that
the 1,825ms "camera delay" is actually video startup delay, not detection latency.

Key validations:
1. Extract video_startup_delay_ms from test sessions
2. Analyze ground truth timing context
3. Recalculate detection latencies with corrected reference
4. Compare old vs new latency measurements
"""

import sqlite3
import json
import logging
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class TimingAnalysisResult:
    """Results of timing analysis"""
    session_id: str
    system_start_time: float
    video_start_time: Optional[float]
    video_startup_delay_ms: float
    ground_truth_events: List[Dict]
    detection_events: List[Dict]
    original_latencies: List[float]
    corrected_latencies: List[float]
    timing_sync_status: str
    
    @property
    def avg_original_latency(self) -> float:
        return statistics.mean(self.original_latencies) if self.original_latencies else 0
    
    @property
    def avg_corrected_latency(self) -> float:
        return statistics.mean(self.corrected_latencies) if self.corrected_latencies else 0
    
    @property
    def latency_improvement_ms(self) -> float:
        return self.avg_original_latency - self.avg_corrected_latency

class VideoStartupDelayValidator:
    """Validates the video startup delay hypothesis"""
    
    def __init__(self, db_path: str = "dev_database.db"):
        self.db_path = db_path
        self.results: List[TimingAnalysisResult] = []
    
    def connect_db(self) -> sqlite3.Connection:
        """Create database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def extract_test_session_timing(self, session_id: str) -> Dict[str, Any]:
        """Extract timing data for a specific test session"""
        with self.connect_db() as conn:
            cursor = conn.cursor()
            
            # Get test session timing data
            cursor.execute("""
                SELECT 
                    id, started_at, completed_at,
                    video_start_timestamp, video_playback_start_time,
                    video_timing_sync_status,
                    timing_accuracy_ns
                FROM test_sessions 
                WHERE id = ?
            """, (session_id,))
            
            session_row = cursor.fetchone()
            if not session_row:
                raise ValueError(f"Test session {session_id} not found")
            
            # Calculate video startup delay
            video_startup_delay_ms = 0
            if session_row['video_playback_start_time'] and session_row['started_at']:
                started_timestamp = datetime.fromisoformat(session_row['started_at'].replace('Z', '+00:00')).timestamp()
                video_start_timestamp = session_row['video_playback_start_time']
                video_startup_delay_ms = (video_start_timestamp - started_timestamp) * 1000
            
            return {
                'session_id': session_id,
                'started_at': session_row['started_at'],
                'video_start_timestamp': session_row['video_start_timestamp'],
                'video_playback_start_time': session_row['video_playback_start_time'],
                'video_startup_delay_ms': video_startup_delay_ms,
                'video_timing_sync_status': session_row['video_timing_sync_status'] or 'unknown',
                'timing_accuracy_ns': session_row['timing_accuracy_ns']
            }
    
    def extract_ground_truth_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Extract ground truth events for a session"""
        with self.connect_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT gt.id, gt.timestamp, gt.class_label, gt.x, gt.y, gt.width, gt.height,
                       v.id as video_id, v.filename as video_filename
                FROM ground_truth_objects gt
                JOIN videos v ON gt.video_id = v.id
                JOIN test_sessions ts ON v.id = ts.video_id
                WHERE ts.id = ?
                ORDER BY gt.timestamp
            """, (session_id,))
            
            events = []
            for row in cursor.fetchall():
                events.append({
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'class_label': row['class_label'],
                    'bbox': [row['x'], row['y'], row['width'], row['height']],
                    'video_id': row['video_id'],
                    'video_filename': row['video_filename']
                })
            
            return events
    
    def extract_detection_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Extract detection events for a session"""
        with self.connect_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, timestamp, detection_time, confidence, class_label,
                       x, y, width, height, processing_time_ms,
                       labjack_timestamp, voltage_level, channel
                FROM detection_events
                WHERE session_id = ?
                ORDER BY timestamp
            """, (session_id,))
            
            events = []
            for row in cursor.fetchall():
                events.append({
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'detection_time': row['detection_time'],
                    'confidence': row['confidence'],
                    'class_label': row['class_label'],
                    'bbox': [row['x'], row['y'], row['width'], row['height']],
                    'processing_time_ms': row['processing_time_ms'],
                    'labjack_timestamp': row['labjack_timestamp'],
                    'voltage_level': row['voltage_level'],
                    'channel': row['channel']
                })
            
            return events
    
    def calculate_original_latencies(self, detection_events: List[Dict], 
                                   system_start_time: float) -> List[float]:
        """Calculate latencies using current method (system start time reference)"""
        latencies = []
        for detection in detection_events:
            if detection['labjack_timestamp']:
                latency_ms = (detection['labjack_timestamp'] - system_start_time) * 1000
                latencies.append(latency_ms)
        return latencies
    
    def calculate_corrected_latencies(self, detection_events: List[Dict], 
                                    ground_truth_events: List[Dict],
                                    video_start_time: float) -> List[float]:
        """Calculate latencies using corrected method (video start time reference)"""
        latencies = []
        
        for detection in detection_events:
            if not detection['labjack_timestamp']:
                continue
                
            # Find matching ground truth event (simplified - use closest in time)
            closest_gt = None
            min_time_diff = float('inf')
            
            for gt in ground_truth_events:
                # GT timestamp should be relative to video start
                gt_absolute_time = video_start_time + gt['timestamp']
                time_diff = abs(detection['labjack_timestamp'] - gt_absolute_time)
                
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_gt = gt
            
            if closest_gt:
                # Calculate corrected latency: detection_time - (video_start + gt_relative_time)
                expected_time = video_start_time + closest_gt['timestamp']
                corrected_latency_ms = (detection['labjack_timestamp'] - expected_time) * 1000
                latencies.append(corrected_latency_ms)
        
        return latencies
    
    def analyze_session(self, session_id: str) -> TimingAnalysisResult:
        """Perform complete timing analysis for a session"""
        logger.info(f"Analyzing session {session_id}")
        
        try:
            # Extract timing data
            timing_data = self.extract_test_session_timing(session_id)
            ground_truth_events = self.extract_ground_truth_events(session_id)
            detection_events = self.extract_detection_events(session_id)
            
            if not detection_events:
                logger.warning(f"No detection events found for session {session_id}")
                return None
            
            # Parse system start time
            system_start_time = datetime.fromisoformat(
                timing_data['started_at'].replace('Z', '+00:00')
            ).timestamp()
            
            video_start_time = timing_data['video_playback_start_time']
            
            # Calculate latencies using both methods
            original_latencies = self.calculate_original_latencies(detection_events, system_start_time)
            
            corrected_latencies = []
            if video_start_time and ground_truth_events:
                corrected_latencies = self.calculate_corrected_latencies(
                    detection_events, ground_truth_events, video_start_time
                )
            
            result = TimingAnalysisResult(
                session_id=session_id,
                system_start_time=system_start_time,
                video_start_time=video_start_time,
                video_startup_delay_ms=timing_data['video_startup_delay_ms'],
                ground_truth_events=ground_truth_events,
                detection_events=detection_events,
                original_latencies=original_latencies,
                corrected_latencies=corrected_latencies,
                timing_sync_status=timing_data['video_timing_sync_status']
            )
            
            self.results.append(result)
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze session {session_id}: {e}")
            return None
    
    def find_sessions_with_timing_data(self) -> List[str]:
        """Find test sessions with video timing data"""
        with self.connect_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM test_sessions 
                WHERE video_playback_start_time IS NOT NULL
                   AND started_at IS NOT NULL
                ORDER BY started_at DESC
                LIMIT 10
            """)
            
            return [row['id'] for row in cursor.fetchall()]
    
    def validate_hypothesis(self) -> Dict[str, Any]:
        """Run complete hypothesis validation"""
        logger.info("Starting video startup delay hypothesis validation")
        
        # Find sessions with timing data
        session_ids = self.find_sessions_with_timing_data()
        logger.info(f"Found {len(session_ids)} sessions with video timing data")
        
        if not session_ids:
            return {"error": "No sessions with video timing data found"}
        
        # Analyze each session
        successful_analyses = []
        for session_id in session_ids:
            result = self.analyze_session(session_id)
            if result:
                successful_analyses.append(result)
        
        if not successful_analyses:
            return {"error": "No successful session analyses completed"}
        
        # Generate summary statistics
        summary = self.generate_summary(successful_analyses)
        
        logger.info("Hypothesis validation completed")
        return summary
    
    def generate_summary(self, results: List[TimingAnalysisResult]) -> Dict[str, Any]:
        """Generate summary of hypothesis validation results"""
        
        # Calculate aggregate statistics
        startup_delays = [r.video_startup_delay_ms for r in results if r.video_startup_delay_ms > 0]
        original_avg_latencies = [r.avg_original_latency for r in results if r.original_latencies]
        corrected_avg_latencies = [r.avg_corrected_latency for r in results if r.corrected_latencies]
        
        # Check if hypothesis is supported
        hypothesis_evidence = {
            "startup_delays_found": len(startup_delays) > 0,
            "avg_startup_delay_ms": statistics.mean(startup_delays) if startup_delays else 0,
            "startup_delay_consistent": len(set(round(d/100)*100 for d in startup_delays)) <= 2 if startup_delays else False,
            "latency_improvement": statistics.mean(corrected_avg_latencies) < statistics.mean(original_avg_latencies) if corrected_avg_latencies and original_avg_latencies else False
        }
        
        return {
            "hypothesis_validation": {
                "total_sessions_analyzed": len(results),
                "sessions_with_startup_delay": len(startup_delays),
                "evidence_supports_hypothesis": all(hypothesis_evidence.values()),
                "evidence_details": hypothesis_evidence
            },
            "timing_statistics": {
                "average_startup_delay_ms": statistics.mean(startup_delays) if startup_delays else 0,
                "startup_delay_range": [min(startup_delays), max(startup_delays)] if startup_delays else [0, 0],
                "original_avg_latency_ms": statistics.mean(original_avg_latencies) if original_avg_latencies else 0,
                "corrected_avg_latency_ms": statistics.mean(corrected_avg_latencies) if corrected_avg_latencies else 0,
                "average_improvement_ms": statistics.mean(original_avg_latencies) - statistics.mean(corrected_avg_latencies) if original_avg_latencies and corrected_avg_latencies else 0
            },
            "session_details": [
                {
                    "session_id": r.session_id,
                    "startup_delay_ms": r.video_startup_delay_ms,
                    "original_avg_latency": r.avg_original_latency,
                    "corrected_avg_latency": r.avg_corrected_latency,
                    "improvement_ms": r.latency_improvement_ms,
                    "timing_sync_status": r.timing_sync_status,
                    "num_detections": len(r.detection_events),
                    "num_ground_truth": len(r.ground_truth_events)
                }
                for r in results
            ]
        }

def main():
    """Main execution function"""
    validator = VideoStartupDelayValidator()
    
    try:
        results = validator.validate_hypothesis()
        
        # Print results
        print("\n" + "="*80)
        print("VIDEO STARTUP DELAY HYPOTHESIS VALIDATION RESULTS")
        print("="*80)
        
        if "error" in results:
            print(f"ERROR: {results['error']}")
            return
        
        hypothesis_validation = results['hypothesis_validation']
        timing_stats = results['timing_statistics']
        
        print(f"\nHYPOTHESIS VALIDATION:")
        print(f"  Sessions Analyzed: {hypothesis_validation['total_sessions_analyzed']}")
        print(f"  Sessions with Startup Delay: {hypothesis_validation['sessions_with_startup_delay']}")
        print(f"  Evidence Supports Hypothesis: {hypothesis_validation['evidence_supports_hypothesis']}")
        
        print(f"\nTIMING ANALYSIS:")
        print(f"  Average Startup Delay: {timing_stats['average_startup_delay_ms']:.1f}ms")
        print(f"  Original Avg Latency: {timing_stats['original_avg_latency_ms']:.1f}ms")
        print(f"  Corrected Avg Latency: {timing_stats['corrected_avg_latency_ms']:.1f}ms")
        print(f"  Average Improvement: {timing_stats['average_improvement_ms']:.1f}ms")
        
        print(f"\nSESSION DETAILS:")
        for session in results['session_details']:
            print(f"  {session['session_id'][:8]}...")
            print(f"    Startup Delay: {session['startup_delay_ms']:.1f}ms")
            print(f"    Latency Improvement: {session['improvement_ms']:.1f}ms")
            print(f"    Sync Status: {session['timing_sync_status']}")
        
        # Save detailed results
        output_file = "/home/rigade/Testing/ai-model-validation-platform/backend/analysis/hypothesis_validation_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"ERROR: Validation failed - {e}")

if __name__ == "__main__":
    main()
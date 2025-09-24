#!/usr/bin/env python3
"""
Simple Video Startup Delay Analysis

Analyzes the video startup delay hypothesis with actual database schema.
Focuses on key question: Does video_playback_start_time show significant delay?
"""

import sqlite3
import json
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional

def analyze_video_startup_delays(db_path: str = "dev_database.db") -> Dict[str, Any]:
    """Analyze video startup delays in test sessions"""
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get test sessions with video timing data
    cursor.execute("""
        SELECT 
            id, started_at, video_start_timestamp, video_playback_start_time,
            video_timing_sync_status, timing_accuracy_ns, 
            status, completed_at
        FROM test_sessions 
        WHERE video_playback_start_time IS NOT NULL 
          AND started_at IS NOT NULL
        ORDER BY started_at DESC
        LIMIT 20
    """)
    
    sessions = cursor.fetchall()
    
    if not sessions:
        conn.close()
        return {"error": "No sessions with video timing data found"}
    
    print(f"\nFound {len(sessions)} sessions with video timing data")
    print("=" * 60)
    
    startup_delays = []
    analysis_results = []
    
    for session in sessions:
        try:
            # Parse timestamps
            if session['started_at']:
                # Handle different datetime formats
                started_at_str = session['started_at']
                if started_at_str.endswith('Z'):
                    started_at_str = started_at_str.replace('Z', '+00:00')
                started_timestamp = datetime.fromisoformat(started_at_str).timestamp()
            else:
                continue
                
            video_start_timestamp = session['video_playback_start_time']
            
            if video_start_timestamp:
                # Calculate startup delay
                startup_delay_seconds = video_start_timestamp - started_timestamp
                startup_delay_ms = startup_delay_seconds * 1000
                
                startup_delays.append(startup_delay_ms)
                
                session_analysis = {
                    "session_id": session['id'][:8] + "...",
                    "started_at": session['started_at'],
                    "video_start_timestamp": video_start_timestamp,
                    "startup_delay_ms": round(startup_delay_ms, 2),
                    "sync_status": session['video_timing_sync_status'],
                    "timing_accuracy_ns": session['timing_accuracy_ns'],
                    "session_status": session['status']
                }
                
                analysis_results.append(session_analysis)
                
                print(f"Session {session['id'][:8]}:")
                print(f"  Startup Delay: {startup_delay_ms:.1f}ms")
                print(f"  Sync Status: {session['video_timing_sync_status']}")
                print(f"  Timing Accuracy: {session['timing_accuracy_ns']}ns")
                print()
                
        except Exception as e:
            print(f"Error analyzing session {session['id'][:8]}: {e}")
            continue
    
    # Get detection events to understand the data better
    cursor.execute("""
        SELECT 
            COUNT(*) as total_detections,
            COUNT(timestamp) as with_timestamp,
            COUNT(labjack_timestamp) as with_labjack_timestamp,
            COUNT(processing_time_ms) as with_processing_time,
            AVG(processing_time_ms) as avg_processing_time
        FROM detection_events
    """)
    
    detection_stats = dict(cursor.fetchone())
    
    # Get ground truth stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_ground_truth,
            MIN(timestamp) as earliest_gt,
            MAX(timestamp) as latest_gt,
            AVG(timestamp) as avg_gt_time
        FROM ground_truth_objects
    """)
    
    gt_stats = dict(cursor.fetchone())
    
    conn.close()
    
    # Calculate statistics
    if startup_delays:
        stats = {
            "count": len(startup_delays),
            "average_ms": round(statistics.mean(startup_delays), 2),
            "median_ms": round(statistics.median(startup_delays), 2),
            "min_ms": round(min(startup_delays), 2),
            "max_ms": round(max(startup_delays), 2),
            "std_dev_ms": round(statistics.stdev(startup_delays), 2) if len(startup_delays) > 1 else 0
        }
        
        # Hypothesis validation
        hypothesis_evidence = {
            "significant_startup_delay": stats["average_ms"] > 1000,  # More than 1 second
            "consistent_delay": stats["std_dev_ms"] < (stats["average_ms"] * 0.3),  # Low variance
            "delay_around_1825ms": 1500 < stats["average_ms"] < 2200,  # Near reported 1825ms
            "multiple_sessions": stats["count"] >= 3
        }
        
        hypothesis_supported = sum(hypothesis_evidence.values()) >= 3
        
        print("\nSTARTUP DELAY STATISTICS:")
        print(f"  Sessions analyzed: {stats['count']}")
        print(f"  Average startup delay: {stats['average_ms']}ms")
        print(f"  Median startup delay: {stats['median_ms']}ms")
        print(f"  Range: {stats['min_ms']}ms - {stats['max_ms']}ms")
        print(f"  Standard deviation: {stats['std_dev_ms']}ms")
        
        print(f"\nHYPOTHESIS EVIDENCE:")
        for key, value in hypothesis_evidence.items():
            print(f"  {key}: {'✅' if value else '❌'}")
        
        print(f"\nHYPOTHESIS SUPPORTED: {'✅ YES' if hypothesis_supported else '❌ NO'}")
        
        if hypothesis_supported:
            print(f"\n🎯 CONCLUSION:")
            print(f"   The video startup delay hypothesis is SUPPORTED!")
            print(f"   Average startup delay of {stats['average_ms']}ms explains")
            print(f"   the reported 1.8s 'camera delay' in detection measurements.")
            print(f"   Real detection latency is likely much lower (~50-100ms).")
        
        return {
            "hypothesis_supported": hypothesis_supported,
            "startup_delay_stats": stats,
            "hypothesis_evidence": hypothesis_evidence,
            "session_analyses": analysis_results,
            "detection_stats": detection_stats,
            "ground_truth_stats": gt_stats
        }
    
    else:
        return {
            "error": "No valid startup delay calculations possible",
            "session_count": len(sessions),
            "detection_stats": detection_stats,
            "ground_truth_stats": gt_stats
        }

def main():
    """Run the analysis"""
    print("Video Startup Delay Hypothesis Analysis")
    print("=" * 50)
    
    try:
        results = analyze_video_startup_delays()
        
        # Save results
        output_file = "/home/rigade/Testing/ai-model-validation-platform/backend/analysis/startup_delay_analysis_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {output_file}")
        
        if "error" not in results and results.get("hypothesis_supported"):
            print(f"\n🚀 NEXT STEPS:")
            print(f"   1. Update latency calculation in validation service")
            print(f"   2. Recalculate all detection latencies using video start time")
            print(f"   3. Verify improved latency measurements")
            print(f"   4. Update documentation with corrected understanding")
            
    except Exception as e:
        print(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
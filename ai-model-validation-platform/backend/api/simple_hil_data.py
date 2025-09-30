"""
Simple HIL Data API - Direct database access for frontend display
"""

from fastapi import APIRouter, HTTPException
import sqlite3
from typing import Dict, List, Any, Optional
import json

router = APIRouter()

@router.post("/api/test-sessions/{session_id}/compute-and-fetch")
async def get_hil_session_data(session_id: str):
    """Get HIL session data with detection events and ground truth"""
    
    try:
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        
        # Get detection events for this session
        cursor.execute("""
            SELECT 
                id, timestamp, labjack_timestamp, video_relative_timestamp, 
                video_frame_number, labjack_voltage, detection_type, source,
                processing_time_ms, actual_latency_ms
            FROM detection_events 
            WHERE test_session_id = ? 
            ORDER BY timestamp ASC
        """, (session_id,))
        
        detection_rows = cursor.fetchall()
        detection_events = []
        
        for row in detection_rows:
            detection_events.append({
                "id": row[0],
                "timestamp": row[1],
                "labjack_timestamp": row[2],
                "video_relative_timestamp": row[3],
                "video_frame_number": row[4],
                "labjack_voltage": row[5],
                "detection_type": row[6],
                "source": row[7],
                "processing_time_ms": row[8],
                "actual_latency_ms": row[9],
                "video_time_sec": row[3]  # For compatibility
            })
        
        # Get ground truth events for the video
        cursor.execute("""
            SELECT ts.video_id, v.filename
            FROM test_sessions ts
            LEFT JOIN videos v ON ts.video_id = v.id
            WHERE ts.id = ?
        """, (session_id,))
        
        session_info = cursor.fetchone()
        ground_truth_events = []
        
        if session_info and session_info[0]:  # has video_id
            video_id = session_info[0]
            cursor.execute("""
                SELECT id, frame_number, timestamp, class_label, confidence
                FROM ground_truth_objects
                WHERE video_id = ?
                ORDER BY frame_number ASC
            """, (video_id,))
            
            gt_rows = cursor.fetchall()
            for row in gt_rows:
                ground_truth_events.append({
                    "id": row[0],
                    "frame_number": row[1], 
                    "timestamp": row[2],
                    "class_label": row[3],
                    "confidence": row[4]
                })
        
        conn.close()
        
        # Return data in expected format
        response = {
            "success": True,
            "data": {
                "results": {
                    "latencyValidation": {
                        "detection_events": detection_events
                    },
                    "groundTruthEvents": ground_truth_events,
                    "video_metadata": {
                        "fps": 24,
                        "filename": session_info[1] if session_info else None
                    }
                }
            }
        }
        
        return response
        
    except Exception as e:
        print(f"Error in HIL data API: {e}")
        raise HTTPException(status_code=500, detail=str(e))
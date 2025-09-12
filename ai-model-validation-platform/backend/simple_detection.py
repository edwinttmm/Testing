#!/usr/bin/env python3
"""
SIMPLE LabJack Detection - No WebSocket Complexity
Just start, detect in background, stop, get results.
"""

import threading
import time
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Simple LabJack Detection")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimpleLabJackDetection:
    """Dead simple LabJack detection - just start/stop/get results"""
    
    def __init__(self):
        self.is_running = False
        self.detection_thread = None
        self.detection_data = []
        self.session_id = None
        self.tolerance_ms = 100
        self.start_time = None
        
    def start_detection(self, session_id: str, tolerance_ms: int = 100):
        """Start background detection - runs silently"""
        if self.is_running:
            return {"status": "already_running", "session_id": self.session_id}
            
        print(f"🚀 Starting simple LabJack detection for session: {session_id}")
        
        self.session_id = session_id
        self.tolerance_ms = tolerance_ms
        self.detection_data = []
        self.is_running = True
        self.start_time = time.time()
        
        # Simple background thread - just collect timestamps
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        return {
            "status": "started", 
            "session_id": session_id, 
            "tolerance_ms": tolerance_ms,
            "message": "Detection running in background - video can play fullscreen"
        }
    
    def stop_detection(self):
        """Stop detection and return all collected data"""
        if not self.is_running:
            return {"status": "not_running", "data": []}
            
        print(f"⏹️ Stopping detection for session: {self.session_id}")
        
        self.is_running = False
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
            
        data = self.detection_data.copy()
        duration = time.time() - self.start_time if self.start_time else 0
        
        result = {
            "status": "stopped", 
            "session_id": self.session_id,
            "duration_seconds": round(duration, 3),
            "total_detections": len(data),
            "data": data,
            "message": f"Collected {len(data)} detections in {duration:.1f} seconds"
        }
        
        print(f"✅ Detection stopped: {len(data)} detections in {duration:.1f}s")
        return result
    
    def get_status(self):
        """Simple status check"""
        duration = time.time() - self.start_time if self.start_time else 0
        return {
            "running": self.is_running,
            "session_id": self.session_id,
            "detections_count": len(self.detection_data),
            "tolerance_ms": self.tolerance_ms,
            "duration_seconds": round(duration, 3) if self.is_running else 0
        }
    
    def _detection_loop(self):
        """Simple detection loop - awaiting signal pattern"""
        print("🔍 Detection loop started - awaiting signals...")
        
        while self.is_running:
            current_time = time.time()
            relative_time = current_time - self.start_time
            
            # SIMPLE MOCK DETECTION - Replace with real LabJack code
            # In real implementation: read LabJack voltage, check threshold
            
            # Simulate some detections for testing
            if len(self.detection_data) == 0 and relative_time > 2.0:
                # First detection at 2 seconds
                self._add_detection(relative_time, 3.2)
            elif len(self.detection_data) == 1 and relative_time > 5.0:
                # Second detection at 5 seconds  
                self._add_detection(relative_time, 3.5)
            elif len(self.detection_data) == 2 and relative_time > 8.0:
                # Third detection at 8 seconds
                self._add_detection(relative_time, 3.1)
            
            time.sleep(0.001)  # 1ms polling for precision
        
        print("🔍 Detection loop ended")
    
    def _add_detection(self, relative_time: float, voltage: float):
        """Add a detection event"""
        detection = {
            "timestamp": round(relative_time, 3),
            "voltage": voltage,
            "system_time": time.time(),
            "session_time": round(relative_time, 3),
            "datetime": datetime.now().isoformat()
        }
        
        self.detection_data.append(detection)
        print(f"🎯 Detection #{len(self.detection_data)} at {relative_time:.3f}s: {voltage}V")

# Global simple detection service
simple_labjack = SimpleLabJackDetection()

@app.get("/")
async def root():
    return {
        "message": "Simple LabJack Detection Service", 
        "status": "running",
        "endpoints": [
            "POST /start - Start detection",
            "POST /stop - Stop detection and get results", 
            "GET /status - Check current status"
        ]
    }

@app.post("/start")
async def start_detection(session_id: str = "video_session", tolerance_ms: int = 100):
    """
    Start LabJack detection in background
    - Runs silently during video playback
    - No interference with video
    - Just collects timestamps
    """
    return simple_labjack.start_detection(session_id, tolerance_ms)

@app.post("/stop") 
async def stop_detection():
    """
    Stop detection and get all collected data
    - Returns all detection events
    - Ready for post-processing
    """
    return simple_labjack.stop_detection()

@app.get("/status")
async def get_status():
    """Simple status check - doesn't interrupt anything"""
    return simple_labjack.get_status()

@app.post("/analyze/{session_id}")
async def analyze_detections(session_id: str, video_events: list = None):
    """
    Analyze detection data against video events
    - Post-processing after video finishes
    - Compare timestamps and correlate events
    """
    if not video_events:
        video_events = []
    
    detections = simple_labjack.detection_data
    
    # Simple correlation analysis
    correlations = []
    for detection in detections:
        detection_time = detection["timestamp"]
        
        # Find closest video events within tolerance
        closest_events = []
        for video_event in video_events:
            video_time = video_event.get("timestamp", 0)
            time_diff = abs(detection_time - video_time)
            
            if time_diff <= (simple_labjack.tolerance_ms / 1000.0):
                closest_events.append({
                    "video_event": video_event,
                    "time_difference_ms": round(time_diff * 1000, 1)
                })
        
        correlations.append({
            "detection": detection,
            "matched_events": closest_events,
            "has_match": len(closest_events) > 0
        })
    
    # Calculate accuracy metrics
    matched_detections = sum(1 for c in correlations if c["has_match"])
    accuracy = (matched_detections / len(detections)) * 100 if detections else 0
    
    return {
        "session_id": session_id,
        "total_detections": len(detections),
        "total_video_events": len(video_events),
        "matched_detections": matched_detections,
        "accuracy_percent": round(accuracy, 1),
        "tolerance_ms": simple_labjack.tolerance_ms,
        "correlations": correlations
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Simple LabJack Detection Service...")
    print("📍 Available at: http://localhost:8001")
    print("📖 API docs at: http://localhost:8001/docs")
    print()
    print("USAGE:")
    print("1. POST /start?session_id=my_video&tolerance_ms=100")  
    print("2. Play your video fullscreen (detection runs silently)")
    print("3. POST /stop (get all detection data)")
    print("4. POST /analyze/my_video (compare with video events)")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
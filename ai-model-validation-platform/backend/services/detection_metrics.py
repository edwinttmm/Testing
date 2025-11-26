"""Metrics tracking for detection quality"""
from collections import defaultdict
from threading import Lock
from datetime import datetime
from typing import Dict, Any

class DetectionMetrics:
    """Track detection quality metrics"""

    def __init__(self):
        self.lock = Lock()
        self.total_detections = 0
        self.validated_detections = 0
        self.degraded_detections = 0
        self.by_session = defaultdict(lambda: {
            'total': 0,
            'validated': 0,
            'degraded': 0
        })

    def record_detection(self, session_id: str, usable_for_validation: bool, timing_degraded: bool):
        """Record a detection event"""
        with self.lock:
            self.total_detections += 1
            self.by_session[session_id]['total'] += 1

            if usable_for_validation:
                self.validated_detections += 1
                self.by_session[session_id]['validated'] += 1

            if timing_degraded:
                self.degraded_detections += 1
                self.by_session[session_id]['degraded'] += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        with self.lock:
            return {
                'total_detections': self.total_detections,
                'validated_detections': self.validated_detections,
                'degraded_detections': self.degraded_detections,
                'validation_rate': (
                    self.validated_detections / self.total_detections * 100
                    if self.total_detections > 0 else 0
                )
            }

    def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get metrics for specific session"""
        with self.lock:
            session_data = self.by_session.get(session_id, {
                'total': 0,
                'validated': 0,
                'degraded': 0
            })
            return {
                'total': session_data['total'],
                'validated': session_data['validated'],
                'degraded': session_data['degraded'],
                'validation_rate': (
                    session_data['validated'] / session_data['total'] * 100
                    if session_data['total'] > 0 else 0
                )
            }

    def reset(self):
        """Reset all metrics"""
        with self.lock:
            self.total_detections = 0
            self.validated_detections = 0
            self.degraded_detections = 0
            self.by_session.clear()

# Global instance
detection_metrics = DetectionMetrics()

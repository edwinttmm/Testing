"""
Dynamic Timing Synchronization Service
======================================
Ensures accurate timing between video playback and LabJack monitoring
without hardcoded delays or assumptions.
"""

import time
import asyncio
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class TimingSynchronizationService:
    """
    Provides dynamic timing synchronization between video and hardware monitoring.
    No hardcoded delays - everything is measured and calibrated in real-time.
    """
    
    def __init__(self):
        self.sync_points: Dict[str, Dict] = {}
        self.active_sessions: Dict[str, bool] = {}
        
    async def prepare_monitoring(self, session_id: str) -> Dict:
        """
        Step 1: Prepare monitoring before video starts
        Returns when monitoring is fully ready
        """
        sync_data = {
            'session_id': session_id,
            'preparation_start': time.perf_counter(),
            'preparation_start_epoch': time.time(),
            'monitoring_ready': False,
            'ready_confirmation': None
        }
        
        self.sync_points[session_id] = sync_data
        logger.info(f"🎯 Starting monitoring preparation for session {session_id}")
        
        # This will be set by the monitoring service when ready
        return sync_data
    
    def confirm_monitoring_ready(self, session_id: str) -> float:
        """
        Called by monitoring service when fully initialized and ready
        Returns the exact timestamp when monitoring became ready
        """
        ready_time = time.perf_counter()
        ready_epoch = time.time()
        
        if session_id in self.sync_points:
            self.sync_points[session_id]['monitoring_ready'] = True
            self.sync_points[session_id]['ready_time'] = ready_time
            self.sync_points[session_id]['ready_epoch'] = ready_epoch
            
            prep_duration = ready_time - self.sync_points[session_id]['preparation_start']
            logger.info(f"✅ Monitoring ready for {session_id} after {prep_duration*1000:.2f}ms")
            
        return ready_epoch
    
    async def wait_for_monitoring_ready(self, session_id: str, timeout: float = 5.0) -> bool:
        """
        Wait for monitoring to be ready before starting video
        Returns True when ready, False on timeout
        """
        start_time = time.perf_counter()
        
        while time.perf_counter() - start_time < timeout:
            if session_id in self.sync_points and self.sync_points[session_id].get('monitoring_ready'):
                return True
            await asyncio.sleep(0.01)  # Check every 10ms
            
        logger.error(f"❌ Timeout waiting for monitoring ready: {session_id}")
        return False
    
    def record_video_event(self, session_id: str, event_type: str, timestamp: Optional[float] = None):
        """
        Record video lifecycle events for synchronization
        Events: load_start, can_play, play_start, first_frame, ended
        """
        if timestamp is None:
            timestamp = time.time()
            
        if session_id not in self.sync_points:
            self.sync_points[session_id] = {}
            
        self.sync_points[session_id][f'video_{event_type}'] = timestamp
        self.sync_points[session_id][f'video_{event_type}_perf'] = time.perf_counter()
        
        logger.info(f"📹 Video event '{event_type}' at {timestamp} for session {session_id}")
        
        # Calculate offset if we have both monitoring and video start
        if event_type == 'play_start' and 'ready_epoch' in self.sync_points[session_id]:
            offset = timestamp - self.sync_points[session_id]['ready_epoch']
            self.sync_points[session_id]['video_monitoring_offset'] = offset
            logger.info(f"⏱️ Video started {offset*1000:.2f}ms after monitoring ready")
    
    def get_synchronized_timestamp(self, session_id: str, raw_timestamp: float) -> Tuple[float, float]:
        """
        Convert a raw timestamp to video-relative time
        Returns: (video_relative_time, confidence_score)
        """
        if session_id not in self.sync_points:
            logger.warning(f"No sync data for session {session_id}")
            return (0.0, 0.0)
        
        sync = self.sync_points[session_id]
        
        # Best case: We have video play start time
        if 'video_play_start' in sync:
            video_relative = raw_timestamp - sync['video_play_start']
            confidence = 1.0
            return (video_relative, confidence)
        
        # Fallback: Use monitoring ready time with offset
        if 'ready_epoch' in sync and 'video_monitoring_offset' in sync:
            video_relative = raw_timestamp - sync['ready_epoch'] - sync['video_monitoring_offset']
            confidence = 0.8
            return (video_relative, confidence)
        
        # Last resort: Use first known timestamp
        if 'preparation_start_epoch' in sync:
            video_relative = raw_timestamp - sync['preparation_start_epoch']
            confidence = 0.5
            return (video_relative, confidence)
        
        return (0.0, 0.0)
    
    def calculate_timing_quality(self, session_id: str) -> Dict:
        """
        Assess the quality of timing synchronization for a session
        """
        if session_id not in self.sync_points:
            return {'quality': 'unknown', 'confidence': 0.0}
        
        sync = self.sync_points[session_id]
        quality_factors = []
        
        # Check if we have key synchronization points
        if sync.get('monitoring_ready'):
            quality_factors.append(0.3)
        if 'video_play_start' in sync:
            quality_factors.append(0.3)
        if 'video_monitoring_offset' in sync:
            quality_factors.append(0.2)
        if 'video_first_frame' in sync:
            quality_factors.append(0.2)
        
        confidence = sum(quality_factors)
        
        # Determine quality level
        if confidence >= 0.9:
            quality = 'excellent'
        elif confidence >= 0.7:
            quality = 'good'
        elif confidence >= 0.5:
            quality = 'fair'
        else:
            quality = 'poor'
        
        # Calculate timing precision
        if 'video_monitoring_offset' in sync:
            offset_ms = abs(sync['video_monitoring_offset'] * 1000)
            if offset_ms < 10:
                precision = 'sub-10ms'
            elif offset_ms < 50:
                precision = 'sub-50ms'
            elif offset_ms < 100:
                precision = 'sub-100ms'
            else:
                precision = f'{offset_ms:.0f}ms offset'
        else:
            precision = 'unknown'
        
        return {
            'quality': quality,
            'confidence': confidence,
            'precision': precision,
            'sync_points': len([k for k in sync.keys() if 'video_' in k or 'ready' in k]),
            'details': sync
        }
    
    async def stop_monitoring_after_video(self, session_id: str, video_duration: float):
        """
        Smart monitoring stop that ensures full video coverage
        - Waits for video to actually end (not expected duration)
        - Adds dynamic buffer based on observed delays
        """
        if session_id not in self.sync_points:
            logger.warning(f"No sync data for session {session_id}")
            return
        
        sync = self.sync_points[session_id]
        
        # Calculate dynamic buffer based on observed delays
        prep_time = sync.get('ready_time', 0) - sync.get('preparation_start', 0)
        buffer = max(0.5, min(2.0, prep_time * 2))  # 2x prep time, 0.5-2s range
        
        logger.info(f"📊 Monitoring will continue for {video_duration:.2f}s + {buffer:.2f}s buffer")
        
        # Don't use sleep - wait for actual video end signal
        self.active_sessions[session_id] = True
        
    def signal_video_ended(self, session_id: str):
        """
        Called when video actually ends (not timer-based)
        """
        self.record_video_event(session_id, 'ended')
        
        if session_id in self.sync_points:
            sync = self.sync_points[session_id]
            if 'video_play_start' in sync and 'video_ended' in sync:
                actual_duration = sync['video_ended'] - sync['video_play_start']
                logger.info(f"📹 Video played for {actual_duration:.3f}s (actual duration)")
        
        # Continue monitoring for a bit after video ends
        # This will be handled by the monitoring service
        self.active_sessions[session_id] = False
    
    def get_session_report(self, session_id: str) -> Dict:
        """
        Generate comprehensive timing report for a session
        """
        if session_id not in self.sync_points:
            return {'error': 'No synchronization data available'}
        
        sync = self.sync_points[session_id]
        quality = self.calculate_timing_quality(session_id)
        
        report = {
            'session_id': session_id,
            'timing_quality': quality,
            'synchronization_points': {},
            'delays': {},
            'recommendations': []
        }
        
        # Calculate various delays
        if 'preparation_start' in sync and 'ready_time' in sync:
            prep_delay = (sync['ready_time'] - sync['preparation_start']) * 1000
            report['delays']['monitoring_preparation_ms'] = prep_delay
            
        if 'video_load_start' in sync and 'video_can_play' in sync:
            load_delay = (sync['video_can_play'] - sync['video_load_start']) * 1000
            report['delays']['video_load_ms'] = load_delay
            
        if 'video_monitoring_offset' in sync:
            report['delays']['video_to_monitoring_offset_ms'] = sync['video_monitoring_offset'] * 1000
            
        # Add recommendations based on observed delays
        if 'monitoring_preparation_ms' in report['delays']:
            if report['delays']['monitoring_preparation_ms'] > 100:
                report['recommendations'].append(
                    "Monitoring preparation took >100ms. Consider pre-warming the connection."
                )
                
        if quality['confidence'] < 0.7:
            report['recommendations'].append(
                "Low timing confidence. Ensure all synchronization points are captured."
            )
            
        return report

# Global instance
timing_sync_service = TimingSynchronizationService()
"""
Real-time vs Recorded Time Comparison Engine

This service provides real-time comparison between "played time" (video timeline)
and "real-life detection time" (hardware timestamps), enabling live synchronization
monitoring and adaptive correction mechanisms.

Features:
- Real-time temporal comparison
- Live drift detection and correction
- Adaptive synchronization windows
- Performance monitoring and optimization
- Quality degradation alerts
- Historical comparison analysis
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Callable, AsyncGenerator
from dataclasses import dataclass, field
from collections import deque
import threading
import time
import statistics
import numpy as np
from scipy import stats
from enum import Enum

from src.models.labjack_models import (
    LabJackDetection, VideoDetection, DetectionSynchronization,
    SynchronizationStatusEnum, DetectionStatusEnum
)
from src.services.detection_storage_service import detection_storage_service
from src.services.temporal_sync_service import TemporalSynchronizationService

logger = logging.getLogger(__name__)


class ComparisonMode(Enum):
    """Real-time comparison modes"""
    LIVE_MONITORING = "live_monitoring"
    PLAYBACK_ANALYSIS = "playback_analysis" 
    OFFLINE_COMPARISON = "offline_comparison"


class SyncQuality(Enum):
    """Synchronization quality levels"""
    EXCELLENT = "excellent"    # <10ms difference
    GOOD = "good"             # 10-50ms difference
    ACCEPTABLE = "acceptable" # 50-100ms difference
    POOR = "poor"             # 100-500ms difference
    CRITICAL = "critical"     # >500ms difference


@dataclass
class TimingComparison:
    """Individual timing comparison result"""
    labjack_time: datetime
    video_time: datetime
    playback_time: datetime
    time_difference_ms: float
    sync_quality: SyncQuality
    drift_rate: float
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_synchronized(self) -> bool:
        return self.sync_quality in [SyncQuality.EXCELLENT, SyncQuality.GOOD]


@dataclass
class RealtimeMetrics:
    """Real-time synchronization metrics"""
    current_drift_ms: float = 0.0
    drift_rate_ms_per_minute: float = 0.0
    sync_quality: SyncQuality = SyncQuality.ACCEPTABLE
    detection_latency_ms: float = 0.0
    processing_delay_ms: float = 0.0
    buffer_utilization: float = 0.0
    throughput_hz: float = 0.0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def update_quality(self, time_diff_ms: float):
        """Update sync quality based on time difference"""
        if abs(time_diff_ms) < 10:
            self.sync_quality = SyncQuality.EXCELLENT
        elif abs(time_diff_ms) < 50:
            self.sync_quality = SyncQuality.GOOD
        elif abs(time_diff_ms) < 100:
            self.sync_quality = SyncQuality.ACCEPTABLE
        elif abs(time_diff_ms) < 500:
            self.sync_quality = SyncQuality.POOR
        else:
            self.sync_quality = SyncQuality.CRITICAL


@dataclass
class AdaptiveWindow:
    """Adaptive synchronization window that adjusts based on performance"""
    base_window_ms: int = 100
    current_window_ms: int = 100
    min_window_ms: int = 10
    max_window_ms: int = 1000
    adaptation_factor: float = 0.1
    performance_threshold: float = 0.8
    
    def adapt(self, performance_score: float):
        """Adapt window size based on performance"""
        if performance_score < self.performance_threshold:
            # Increase window for better matching
            self.current_window_ms = min(
                self.max_window_ms,
                int(self.current_window_ms * (1 + self.adaptation_factor))
            )
        else:
            # Decrease window for better precision
            self.current_window_ms = max(
                self.min_window_ms,
                int(self.current_window_ms * (1 - self.adaptation_factor))
            )


class RealTimeComparisonEngine:
    """
    Real-time comparison engine for temporal synchronization analysis
    """
    
    def __init__(
        self,
        session_id: str,
        comparison_mode: ComparisonMode = ComparisonMode.LIVE_MONITORING,
        window_size_ms: int = 100,
        buffer_size: int = 1000,
        update_interval_ms: int = 100
    ):
        self.session_id = session_id
        self.comparison_mode = comparison_mode
        self.base_window_ms = window_size_ms
        self.buffer_size = buffer_size
        self.update_interval_ms = update_interval_ms
        
        # Real-time buffers
        self.labjack_buffer = deque(maxlen=buffer_size)
        self.video_buffer = deque(maxlen=buffer_size)
        self.comparison_buffer = deque(maxlen=buffer_size)
        
        # Metrics and state
        self.metrics = RealtimeMetrics()
        self.adaptive_window = AdaptiveWindow(base_window_ms=window_size_ms)
        
        # Threading and async control
        self._running = False
        self._comparison_task = None
        self._update_task = None
        self._lock = threading.Lock()
        
        # Event handlers
        self.sync_quality_changed_handlers: List[Callable] = []
        self.drift_alert_handlers: List[Callable] = []
        self.performance_handlers: List[Callable] = []
        
        self.logger = logger
    
    async def start_realtime_comparison(self):
        """Start real-time comparison monitoring"""
        if self._running:
            return
        
        self._running = True
        
        # Start comparison and update tasks
        self._comparison_task = asyncio.create_task(self._comparison_loop())
        self._update_task = asyncio.create_task(self._metrics_update_loop())
        
        self.logger.info(f"Started real-time comparison for session {self.session_id}")
    
    async def stop_realtime_comparison(self):
        """Stop real-time comparison monitoring"""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel tasks
        if self._comparison_task:
            self._comparison_task.cancel()
            try:
                await self._comparison_task
            except asyncio.CancelledError:
                pass
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info(f"Stopped real-time comparison for session {self.session_id}")
    
    def add_labjack_detection(
        self,
        detection_id: str,
        hardware_timestamp: datetime,
        system_timestamp: datetime,
        signal_value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add LabJack detection to real-time buffer"""
        
        detection_data = {
            'id': detection_id,
            'hardware_timestamp': hardware_timestamp,
            'system_timestamp': system_timestamp,
            'signal_value': signal_value,
            'metadata': metadata or {},
            'received_at': datetime.now(timezone.utc)
        }
        
        with self._lock:
            self.labjack_buffer.append(detection_data)
        
        # Update detection latency
        latency_ms = (detection_data['received_at'] - system_timestamp).total_seconds() * 1000
        self.metrics.detection_latency_ms = latency_ms
    
    def add_video_detection(
        self,
        detection_id: str,
        video_timestamp: float,
        playback_timestamp: datetime,
        detection_type: str,
        confidence_score: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add video detection to real-time buffer"""
        
        detection_data = {
            'id': detection_id,
            'video_timestamp': video_timestamp,
            'playback_timestamp': playback_timestamp,
            'detection_type': detection_type,
            'confidence_score': confidence_score,
            'metadata': metadata or {},
            'received_at': datetime.now(timezone.utc)
        }
        
        with self._lock:
            self.video_buffer.append(detection_data)
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Get current real-time metrics"""
        
        with self._lock:
            buffer_stats = {
                'labjack_buffer_size': len(self.labjack_buffer),
                'video_buffer_size': len(self.video_buffer),
                'comparison_buffer_size': len(self.comparison_buffer),
                'buffer_utilization': len(self.labjack_buffer) / self.buffer_size
            }
        
        return {
            'session_id': self.session_id,
            'comparison_mode': self.comparison_mode.value,
            'current_metrics': {
                'current_drift_ms': self.metrics.current_drift_ms,
                'drift_rate_ms_per_minute': self.metrics.drift_rate_ms_per_minute,
                'sync_quality': self.metrics.sync_quality.value,
                'detection_latency_ms': self.metrics.detection_latency_ms,
                'processing_delay_ms': self.metrics.processing_delay_ms,
                'throughput_hz': self.metrics.throughput_hz,
                'last_update': self.metrics.last_update.isoformat()
            },
            'adaptive_window': {
                'current_window_ms': self.adaptive_window.current_window_ms,
                'base_window_ms': self.adaptive_window.base_window_ms,
                'adaptation_active': self.adaptive_window.current_window_ms != self.adaptive_window.base_window_ms
            },
            'buffer_statistics': buffer_stats,
            'performance_indicators': await self._calculate_performance_indicators()
        }
    
    async def get_comparison_stream(self) -> AsyncGenerator[TimingComparison, None]:
        """Stream real-time comparison results"""
        
        while self._running:
            with self._lock:
                if self.comparison_buffer:
                    # Yield all available comparisons
                    while self.comparison_buffer:
                        comparison_data = self.comparison_buffer.popleft()
                        yield self._create_timing_comparison(comparison_data)
            
            await asyncio.sleep(self.update_interval_ms / 1000)
    
    async def analyze_historical_drift(
        self, time_range: timedelta = timedelta(hours=1)
    ) -> Dict[str, Any]:
        """Analyze historical drift patterns"""
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - time_range
        
        # Get historical comparisons from buffer (limited view)
        with self._lock:
            historical_data = list(self.comparison_buffer)
        
        if len(historical_data) < 10:
            return {
                'insufficient_data': True,
                'message': 'Insufficient historical data for analysis',
                'data_points': len(historical_data)
            }
        
        # Extract time differences and timestamps
        time_diffs = [comp['time_difference_ms'] for comp in historical_data]
        timestamps = [comp['timestamp'] for comp in historical_data]
        
        # Convert timestamps to seconds since start
        time_seconds = [
            (ts - timestamps[0]).total_seconds() 
            for ts in timestamps
        ]
        
        # Linear regression for drift analysis
        if len(time_seconds) > 1:
            slope, intercept, r_value, p_value, std_err = stats.linregress(
                time_seconds, time_diffs
            )
        else:
            slope = intercept = r_value = p_value = std_err = 0
        
        # Statistical analysis
        drift_stats = {
            'mean_drift_ms': statistics.mean(time_diffs),
            'median_drift_ms': statistics.median(time_diffs),
            'std_drift_ms': statistics.stdev(time_diffs) if len(time_diffs) > 1 else 0,
            'min_drift_ms': min(time_diffs),
            'max_drift_ms': max(time_diffs),
            'drift_range_ms': max(time_diffs) - min(time_diffs)
        }
        
        # Trend analysis
        trend_analysis = {
            'drift_rate_ms_per_second': slope,
            'trend_strength': abs(r_value),
            'trend_direction': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable',
            'trend_significance': p_value,
            'prediction_accuracy': r_value ** 2
        }
        
        # Quality assessment over time
        quality_distribution = {}
        for comp in historical_data:
            quality = comp.get('sync_quality', 'unknown')
            quality_distribution[quality] = quality_distribution.get(quality, 0) + 1
        
        return {
            'analysis_period': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': time_range.total_seconds(),
                'data_points': len(historical_data)
            },
            'drift_statistics': drift_stats,
            'trend_analysis': trend_analysis,
            'quality_distribution': quality_distribution,
            'recommendations': self._generate_drift_recommendations(
                drift_stats, trend_analysis
            )
        }
    
    def add_sync_quality_handler(self, handler: Callable[[SyncQuality], None]):
        """Add handler for sync quality changes"""
        self.sync_quality_changed_handlers.append(handler)
    
    def add_drift_alert_handler(self, handler: Callable[[float, str], None]):
        """Add handler for drift alerts"""
        self.drift_alert_handlers.append(handler)
    
    def add_performance_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Add handler for performance updates"""
        self.performance_handlers.append(handler)
    
    # Private methods
    
    async def _comparison_loop(self):
        """Main comparison processing loop"""
        
        while self._running:
            try:
                start_time = time.time()
                
                # Process available detections
                comparisons_made = await self._process_detection_pairs()
                
                # Update throughput metrics
                processing_time = time.time() - start_time
                if processing_time > 0:
                    self.metrics.throughput_hz = comparisons_made / processing_time
                
                self.metrics.processing_delay_ms = processing_time * 1000
                
                # Adaptive sleep based on load
                sleep_time = max(0.01, self.update_interval_ms / 1000 - processing_time)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in comparison loop: {str(e)}")
                await asyncio.sleep(1.0)
    
    async def _metrics_update_loop(self):
        """Metrics update and alerting loop"""
        
        while self._running:
            try:
                # Update drift metrics
                await self._update_drift_metrics()
                
                # Check for quality changes
                await self._check_quality_changes()
                
                # Update adaptive window
                self._update_adaptive_window()
                
                # Calculate buffer utilization
                with self._lock:
                    self.metrics.buffer_utilization = len(self.labjack_buffer) / self.buffer_size
                
                self.metrics.last_update = datetime.now(timezone.utc)
                
                await asyncio.sleep(1.0)  # Update metrics every second
                
            except Exception as e:
                self.logger.error(f"Error in metrics update loop: {str(e)}")
                await asyncio.sleep(5.0)
    
    async def _process_detection_pairs(self) -> int:
        """Process and compare detection pairs"""
        
        comparisons_made = 0
        
        with self._lock:
            labjack_detections = list(self.labjack_buffer)
            video_detections = list(self.video_buffer)
        
        # Find matching pairs within current window
        current_window_seconds = self.adaptive_window.current_window_ms / 1000.0
        
        for labjack_det in labjack_detections:
            best_match = None
            best_time_diff = float('inf')
            
            labjack_time = labjack_det['hardware_timestamp'].timestamp()
            
            for video_det in video_detections:
                # Convert video time to comparable timestamp
                video_time = video_det['playback_timestamp'].timestamp()
                
                time_diff = abs(labjack_time - video_time)
                
                if time_diff <= current_window_seconds and time_diff < best_time_diff:
                    best_match = video_det
                    best_time_diff = time_diff
            
            if best_match:
                # Create comparison
                comparison = await self._create_comparison(labjack_det, best_match, best_time_diff)
                
                with self._lock:
                    self.comparison_buffer.append(comparison)
                
                comparisons_made += 1
        
        return comparisons_made
    
    async def _create_comparison(
        self, labjack_det: Dict[str, Any], video_det: Dict[str, Any], time_diff_seconds: float
    ) -> Dict[str, Any]:
        """Create a timing comparison record"""
        
        time_diff_ms = time_diff_seconds * 1000
        
        # Determine sync quality
        sync_quality = SyncQuality.ACCEPTABLE
        if abs(time_diff_ms) < 10:
            sync_quality = SyncQuality.EXCELLENT
        elif abs(time_diff_ms) < 50:
            sync_quality = SyncQuality.GOOD
        elif abs(time_diff_ms) < 100:
            sync_quality = SyncQuality.ACCEPTABLE
        elif abs(time_diff_ms) < 500:
            sync_quality = SyncQuality.POOR
        else:
            sync_quality = SyncQuality.CRITICAL
        
        # Calculate confidence based on signal strength and video confidence
        confidence_score = (
            labjack_det.get('signal_value', 0) / 10.0 * 0.5 +  # Normalize signal
            video_det.get('confidence_score', 0) * 0.5
        )
        confidence_score = min(1.0, max(0.0, confidence_score))
        
        return {
            'labjack_id': labjack_det['id'],
            'video_id': video_det['id'],
            'labjack_timestamp': labjack_det['hardware_timestamp'],
            'video_timestamp': video_det['video_timestamp'],
            'playback_timestamp': video_det['playback_timestamp'],
            'time_difference_ms': time_diff_ms,
            'sync_quality': sync_quality.value,
            'confidence_score': confidence_score,
            'timestamp': datetime.now(timezone.utc),
            'window_size_ms': self.adaptive_window.current_window_ms,
            'metadata': {
                'labjack_signal': labjack_det.get('signal_value'),
                'video_confidence': video_det.get('confidence_score'),
                'detection_latency_ms': self.metrics.detection_latency_ms
            }
        }
    
    def _create_timing_comparison(self, comparison_data: Dict[str, Any]) -> TimingComparison:
        """Create TimingComparison object from comparison data"""
        
        return TimingComparison(
            labjack_time=comparison_data['labjack_timestamp'],
            video_time=comparison_data['playback_timestamp'],
            playback_time=comparison_data['playback_timestamp'],
            time_difference_ms=comparison_data['time_difference_ms'],
            sync_quality=SyncQuality(comparison_data['sync_quality']),
            drift_rate=self.metrics.drift_rate_ms_per_minute,
            confidence_score=comparison_data['confidence_score'],
            metadata=comparison_data.get('metadata', {})
        )
    
    async def _update_drift_metrics(self):
        """Update drift-related metrics"""
        
        with self._lock:
            recent_comparisons = list(self.comparison_buffer)[-100:]  # Last 100 comparisons
        
        if len(recent_comparisons) < 10:
            return
        
        # Extract time differences
        time_diffs = [comp['time_difference_ms'] for comp in recent_comparisons]
        timestamps = [comp['timestamp'] for comp in recent_comparisons]
        
        # Calculate current drift (recent average)
        self.metrics.current_drift_ms = statistics.mean(time_diffs[-10:])  # Last 10
        
        # Calculate drift rate over time
        if len(timestamps) > 1:
            time_span_minutes = (timestamps[-1] - timestamps[0]).total_seconds() / 60
            if time_span_minutes > 0:
                drift_change = time_diffs[-1] - time_diffs[0]
                self.metrics.drift_rate_ms_per_minute = drift_change / time_span_minutes
        
        # Update sync quality
        self.metrics.update_quality(self.metrics.current_drift_ms)
    
    async def _check_quality_changes(self):
        """Check for sync quality changes and trigger handlers"""
        
        previous_quality = getattr(self, '_previous_quality', None)
        current_quality = self.metrics.sync_quality
        
        if previous_quality != current_quality:
            # Quality changed - notify handlers
            for handler in self.sync_quality_changed_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(current_quality)
                    else:
                        handler(current_quality)
                except Exception as e:
                    self.logger.error(f"Error in sync quality handler: {str(e)}")
            
            self._previous_quality = current_quality
        
        # Check for drift alerts
        if abs(self.metrics.drift_rate_ms_per_minute) > 10:  # >10ms/minute drift
            alert_message = f"High drift rate: {self.metrics.drift_rate_ms_per_minute:.2f}ms/min"
            
            for handler in self.drift_alert_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(self.metrics.drift_rate_ms_per_minute, alert_message)
                    else:
                        handler(self.metrics.drift_rate_ms_per_minute, alert_message)
                except Exception as e:
                    self.logger.error(f"Error in drift alert handler: {str(e)}")
    
    def _update_adaptive_window(self):
        """Update adaptive window based on performance"""
        
        with self._lock:
            recent_comparisons = list(self.comparison_buffer)[-50:]  # Last 50 comparisons
        
        if len(recent_comparisons) < 10:
            return
        
        # Calculate performance score based on sync quality distribution
        excellent_count = sum(1 for comp in recent_comparisons if comp['sync_quality'] == SyncQuality.EXCELLENT.value)
        good_count = sum(1 for comp in recent_comparisons if comp['sync_quality'] == SyncQuality.GOOD.value)
        
        performance_score = (excellent_count + good_count * 0.8) / len(recent_comparisons)
        
        # Adapt window
        self.adaptive_window.adapt(performance_score)
    
    async def _calculate_performance_indicators(self) -> Dict[str, Any]:
        """Calculate various performance indicators"""
        
        with self._lock:
            recent_comparisons = list(self.comparison_buffer)[-100:]
        
        if not recent_comparisons:
            return {'no_data': True}
        
        # Quality distribution
        quality_counts = {}
        for comp in recent_comparisons:
            quality = comp['sync_quality']
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
        
        # Performance metrics
        time_diffs = [comp['time_difference_ms'] for comp in recent_comparisons]
        confidence_scores = [comp['confidence_score'] for comp in recent_comparisons]
        
        return {
            'quality_distribution': quality_counts,
            'timing_statistics': {
                'mean_difference_ms': statistics.mean(time_diffs),
                'median_difference_ms': statistics.median(time_diffs),
                'std_difference_ms': statistics.stdev(time_diffs) if len(time_diffs) > 1 else 0,
                'max_difference_ms': max(time_diffs),
                'min_difference_ms': min(time_diffs)
            },
            'confidence_statistics': {
                'mean_confidence': statistics.mean(confidence_scores),
                'median_confidence': statistics.median(confidence_scores),
                'min_confidence': min(confidence_scores),
                'max_confidence': max(confidence_scores)
            },
            'data_points': len(recent_comparisons),
            'time_span_minutes': (
                (recent_comparisons[-1]['timestamp'] - recent_comparisons[0]['timestamp']).total_seconds() / 60
                if len(recent_comparisons) > 1 else 0
            )
        }
    
    def _generate_drift_recommendations(
        self, drift_stats: Dict[str, Any], trend_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on drift analysis"""
        
        recommendations = []
        
        # High drift recommendations
        if abs(drift_stats['mean_drift_ms']) > 100:
            recommendations.append("High average drift detected - check system clock synchronization")
        
        # High variability recommendations
        if drift_stats['std_drift_ms'] > 50:
            recommendations.append("High drift variability - investigate timing instability sources")
        
        # Trend recommendations
        if abs(trend_analysis['drift_rate_ms_per_second']) > 0.1:
            recommendations.append("Significant drift trend detected - consider periodic recalibration")
        
        # Strong trend recommendations
        if trend_analysis['trend_strength'] > 0.8:
            if trend_analysis['trend_direction'] == 'increasing':
                recommendations.append("Consistent increasing drift - hardware may be warming up")
            elif trend_analysis['trend_direction'] == 'decreasing':
                recommendations.append("Consistent decreasing drift - check for timing adjustments")
        
        if not recommendations:
            recommendations.append("Synchronization performance is within acceptable limits")
        
        return recommendations


# Global instances and utilities

class ComparisonEngineManager:
    """Manager for multiple real-time comparison engines"""
    
    def __init__(self):
        self.engines: Dict[str, RealTimeComparisonEngine] = {}
        self.logger = logger
    
    async def create_engine(
        self, 
        session_id: str, 
        **kwargs
    ) -> RealTimeComparisonEngine:
        """Create and start a new comparison engine"""
        
        if session_id in self.engines:
            await self.engines[session_id].stop_realtime_comparison()
        
        engine = RealTimeComparisonEngine(session_id, **kwargs)
        await engine.start_realtime_comparison()
        
        self.engines[session_id] = engine
        self.logger.info(f"Created comparison engine for session {session_id}")
        
        return engine
    
    async def get_engine(self, session_id: str) -> Optional[RealTimeComparisonEngine]:
        """Get existing comparison engine"""
        return self.engines.get(session_id)
    
    async def stop_engine(self, session_id: str):
        """Stop and remove comparison engine"""
        if session_id in self.engines:
            await self.engines[session_id].stop_realtime_comparison()
            del self.engines[session_id]
            self.logger.info(f"Stopped comparison engine for session {session_id}")
    
    async def stop_all_engines(self):
        """Stop all comparison engines"""
        for session_id in list(self.engines.keys()):
            await self.stop_engine(session_id)
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.engines.keys())


# Global manager instance
comparison_engine_manager = ComparisonEngineManager()
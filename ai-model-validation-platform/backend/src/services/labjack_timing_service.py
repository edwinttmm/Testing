"""
LabJack Timing Validation Service

This service handles LabJack timing validation logic, latency calculations,
and test result analysis for the AI Model Validation Platform.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from statistics import mean, median, stdev
from sqlalchemy.orm import Session

from models import DetectionEvent, TestSession, TestResult


logger = logging.getLogger(__name__)


class LabJackTimingService:
    """Service for LabJack timing validation operations."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def calculate_latency(
        self, 
        labjack_timestamp: float, 
        detection_timestamp: float, 
        video_start_time: float = 0.0
    ) -> float:
        """
        Calculate latency between LabJack signal and detection.
        
        Args:
            labjack_timestamp: Timestamp when LabJack detected signal
            detection_timestamp: Timestamp when detection occurred 
            video_start_time: Video recording start time reference
            
        Returns:
            Latency in milliseconds
        """
        # Adjust timestamps relative to video start
        adjusted_labjack = labjack_timestamp - video_start_time
        adjusted_detection = detection_timestamp - video_start_time
        
        # Calculate latency (detection time - signal time)
        latency_seconds = adjusted_detection - adjusted_labjack
        latency_ms = latency_seconds * 1000.0
        
        return latency_ms
    
    def validate_detection_event(
        self, 
        detection_event: DetectionEvent, 
        latency_threshold_ms: float = 100.0
    ) -> str:
        """
        Validate a detection event against latency threshold.
        
        Args:
            detection_event: DetectionEvent to validate
            latency_threshold_ms: Maximum allowed latency in ms
            
        Returns:
            Validation result: 'Pass' or 'Fail'
        """
        if detection_event.latency_ms is None:
            return 'Unknown'
        
        return 'Pass' if detection_event.latency_ms <= latency_threshold_ms else 'Fail'
    
    def create_detection_event(
        self,
        test_session_id: str,
        labjack_timestamp: float,
        detection_timestamp: float,
        video_start_time: float = 0.0,
        labjack_voltage: Optional[float] = None,
        video_id: Optional[str] = None,
        frame_number: Optional[int] = None
    ) -> DetectionEvent:
        """
        Create a new DetectionEvent with LabJack timing data.
        
        Args:
            test_session_id: ID of the test session
            labjack_timestamp: LabJack detection timestamp
            detection_timestamp: Video detection timestamp
            video_start_time: Video start reference time
            labjack_voltage: LabJack voltage reading (optional)
            video_id: Associated video ID (optional)
            frame_number: Associated frame number (optional)
            
        Returns:
            Created DetectionEvent instance
        """
        # Calculate latency
        latency_ms = self.calculate_latency(
            labjack_timestamp, 
            detection_timestamp, 
            video_start_time
        )
        
        # Get test session to determine threshold
        test_session = self.db_session.query(TestSession).filter_by(
            id=test_session_id
        ).first()
        
        if not test_session:
            raise ValueError(f"Test session {test_session_id} not found")
        
        # Create detection event
        detection_event = DetectionEvent(
            test_session_id=test_session_id,
            video_id=video_id,
            timestamp=detection_timestamp,
            latency_ms=latency_ms,
            labjack_timestamp=labjack_timestamp,
            video_start_time=video_start_time,
            labjack_voltage=labjack_voltage,
            frame_number=frame_number,
            validation_result=self.validate_detection_event_by_threshold(
                latency_ms, test_session.latency_threshold_ms
            )
        )
        
        return detection_event
    
    def validate_detection_event_by_threshold(
        self, 
        latency_ms: float, 
        threshold_ms: float
    ) -> str:
        """Validate latency against threshold."""
        return 'Pass' if latency_ms <= threshold_ms else 'Fail'
    
    def calculate_test_session_metrics(
        self, 
        test_session_id: str
    ) -> Dict[str, any]:
        """
        Calculate comprehensive timing metrics for a test session.
        
        Args:
            test_session_id: ID of the test session
            
        Returns:
            Dictionary containing timing metrics
        """
        # Get all detection events for this session
        detection_events = self.db_session.query(DetectionEvent).filter_by(
            test_session_id=test_session_id
        ).all()
        
        if not detection_events:
            return self._empty_metrics()
        
        # Extract latencies (filter out None values)
        latencies = [
            event.latency_ms for event in detection_events 
            if event.latency_ms is not None
        ]
        
        if not latencies:
            return self._empty_metrics()
        
        # Calculate basic statistics
        total_detections = len(detection_events)
        passed_detections = len([
            event for event in detection_events 
            if event.validation_result == 'Pass'
        ])
        failed_detections = len([
            event for event in detection_events 
            if event.validation_result == 'Fail'
        ])
        
        pass_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
        
        # Calculate latency statistics
        avg_latency = mean(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
        median_latency = median(latencies)
        std_dev = stdev(latencies) if len(latencies) > 1 else 0
        
        # Calculate percentiles
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        percentiles = {
            '25th': sorted_latencies[int(0.25 * n)] if n > 0 else 0,
            '50th': median_latency,
            '75th': sorted_latencies[int(0.75 * n)] if n > 0 else 0,
            '90th': sorted_latencies[int(0.90 * n)] if n > 0 else 0,
            '95th': sorted_latencies[int(0.95 * n)] if n > 0 else 0,
            '99th': sorted_latencies[int(0.99 * n)] if n > 0 else 0
        }
        
        # Create latency distribution
        latency_distribution = {
            'mean': avg_latency,
            'median': median_latency,
            'std_dev': std_dev,
            'percentiles': percentiles,
            'histogram': self._create_latency_histogram(latencies),
            'outliers': self._detect_outliers(latencies, avg_latency, std_dev)
        }
        
        return {
            'total_detections': total_detections,
            'passed_detections': passed_detections,
            'failed_detections': failed_detections,
            'pass_rate': pass_rate,
            'avg_latency_ms': avg_latency,
            'max_latency_ms': max_latency,
            'min_latency_ms': min_latency,
            'median_latency_ms': median_latency,
            'latency_std_dev': std_dev,
            'latency_distribution': latency_distribution
        }
    
    def create_or_update_test_result(
        self, 
        test_session_id: str
    ) -> TestResult:
        """
        Create or update TestResult record with calculated metrics.
        
        Args:
            test_session_id: ID of the test session
            
        Returns:
            Created or updated TestResult instance
        """
        metrics = self.calculate_test_session_metrics(test_session_id)
        
        # Check if TestResult already exists
        existing_result = self.db_session.query(TestResult).filter_by(
            test_session_id=test_session_id
        ).first()
        
        if existing_result:
            # Update existing result
            existing_result.pass_rate = metrics['pass_rate']
            existing_result.avg_latency_ms = metrics['avg_latency_ms']
            existing_result.max_latency_ms = metrics['max_latency_ms']
            existing_result.min_latency_ms = metrics['min_latency_ms']
            existing_result.total_detections = metrics['total_detections']
            existing_result.passed_detections = metrics['passed_detections']
            existing_result.failed_detections = metrics['failed_detections']
            existing_result.latency_distribution = metrics['latency_distribution']
            
            return existing_result
        else:
            # Create new result
            test_result = TestResult(
                test_session_id=test_session_id,
                pass_rate=metrics['pass_rate'],
                avg_latency_ms=metrics['avg_latency_ms'],
                max_latency_ms=metrics['max_latency_ms'],
                min_latency_ms=metrics['min_latency_ms'],
                total_detections=metrics['total_detections'],
                passed_detections=metrics['passed_detections'],
                failed_detections=metrics['failed_detections'],
                latency_distribution=metrics['latency_distribution']
            )
            
            self.db_session.add(test_result)
            return test_result
    
    def analyze_test_session_performance(
        self, 
        test_session_id: str
    ) -> Dict[str, any]:
        """
        Perform comprehensive performance analysis of a test session.
        
        Args:
            test_session_id: ID of the test session
            
        Returns:
            Detailed performance analysis
        """
        metrics = self.calculate_test_session_metrics(test_session_id)
        test_session = self.db_session.query(TestSession).filter_by(
            id=test_session_id
        ).first()
        
        if not test_session:
            raise ValueError(f"Test session {test_session_id} not found")
        
        # Performance assessment
        threshold = test_session.latency_threshold_ms or 100
        performance_grade = self._calculate_performance_grade(
            metrics['pass_rate'], 
            metrics['avg_latency_ms'], 
            threshold
        )
        
        # Identify issues
        issues = []
        recommendations = []
        
        if metrics['pass_rate'] < 80:
            issues.append(f"Low pass rate: {metrics['pass_rate']:.1f}%")
            recommendations.append("Review detection algorithm sensitivity")
        
        if metrics['avg_latency_ms'] > threshold * 0.8:
            issues.append(f"High average latency: {metrics['avg_latency_ms']:.1f}ms")
            recommendations.append("Optimize detection processing pipeline")
        
        if metrics['latency_distribution']['std_dev'] > threshold * 0.3:
            issues.append("High latency variance detected")
            recommendations.append("Investigate inconsistent processing times")
        
        return {
            'metrics': metrics,
            'performance_grade': performance_grade,
            'threshold_ms': threshold,
            'issues': issues,
            'recommendations': recommendations,
            'summary': self._generate_performance_summary(metrics, performance_grade, threshold)
        }
    
    def _empty_metrics(self) -> Dict[str, any]:
        """Return empty metrics structure."""
        return {
            'total_detections': 0,
            'passed_detections': 0,
            'failed_detections': 0,
            'pass_rate': 0.0,
            'avg_latency_ms': None,
            'max_latency_ms': None,
            'min_latency_ms': None,
            'median_latency_ms': None,
            'latency_std_dev': None,
            'latency_distribution': None
        }
    
    def _create_latency_histogram(self, latencies: List[float], bins: int = 10) -> Dict[str, List]:
        """Create histogram data for latency distribution."""
        if not latencies:
            return {'bins': [], 'counts': []}
        
        min_val = min(latencies)
        max_val = max(latencies)
        bin_width = (max_val - min_val) / bins
        
        bin_edges = [min_val + i * bin_width for i in range(bins + 1)]
        bin_counts = [0] * bins
        
        for latency in latencies:
            bin_idx = min(int((latency - min_val) / bin_width), bins - 1)
            bin_counts[bin_idx] += 1
        
        return {
            'bin_edges': bin_edges,
            'counts': bin_counts,
            'bin_width': bin_width
        }
    
    def _detect_outliers(self, latencies: List[float], mean_val: float, std_dev: float) -> List[float]:
        """Detect outliers using standard deviation method."""
        if std_dev == 0:
            return []
        
        threshold = 2.0  # 2 standard deviations
        outliers = []
        
        for latency in latencies:
            z_score = abs(latency - mean_val) / std_dev
            if z_score > threshold:
                outliers.append(latency)
        
        return outliers
    
    def _calculate_performance_grade(self, pass_rate: float, avg_latency: float, threshold: float) -> str:
        """Calculate performance grade based on pass rate and latency."""
        if pass_rate >= 95 and avg_latency <= threshold * 0.6:
            return 'A'
        elif pass_rate >= 90 and avg_latency <= threshold * 0.8:
            return 'B'
        elif pass_rate >= 80 and avg_latency <= threshold:
            return 'C'
        elif pass_rate >= 70 and avg_latency <= threshold * 1.2:
            return 'D'
        else:
            return 'F'
    
    def _generate_performance_summary(
        self, 
        metrics: Dict[str, any], 
        grade: str, 
        threshold: float
    ) -> str:
        """Generate human-readable performance summary."""
        pass_rate = metrics['pass_rate']
        avg_latency = metrics['avg_latency_ms']
        total_detections = metrics['total_detections']
        
        summary = f"Performance Grade: {grade}\n"
        summary += f"Processed {total_detections} detection events with {pass_rate:.1f}% pass rate.\n"
        
        if avg_latency:
            summary += f"Average latency: {avg_latency:.1f}ms (threshold: {threshold}ms)\n"
            
            if avg_latency <= threshold:
                summary += "Latency performance meets requirements."
            else:
                summary += f"Latency exceeds threshold by {avg_latency - threshold:.1f}ms."
        
        return summary
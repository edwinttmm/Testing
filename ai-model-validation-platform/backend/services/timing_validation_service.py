"""
Timing Validation and Reporting Service
PRD Module 3.2 Implementation - Precision Time & Signal Logging

This service provides comprehensive timing validation and analysis for
Hardware-in-the-Loop testing with LabJack hardware.

Features:
- Millisecond precision timing validation
- Latency calculation and analysis
- Detection performance metrics
- Statistical analysis and reporting
- Real-time timing alerts
- Comprehensive test reports
"""

import asyncio
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
import json
import queue

# Import hardware services
from services.labjack_hardware_service import HardwareEvent
from services.video_hardware_sync_service import SyncEvent, get_video_hardware_sync_service

logger = logging.getLogger(__name__)


class TimingMetric(Enum):
    """Timing validation metrics"""
    LATENCY = "latency"
    JITTER = "jitter"
    ACCURACY = "accuracy"
    DETECTION_RATE = "detection_rate"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    SYNC_DRIFT = "sync_drift"


class ValidationResult(Enum):
    """Validation results"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class TimingRequirement:
    """Timing requirement specification"""
    name: str
    metric: TimingMetric
    target_value: float
    tolerance: float
    warning_threshold: float
    critical_threshold: float
    unit: str
    description: str


@dataclass
class TimingMeasurement:
    """Individual timing measurement"""
    measurement_id: str
    timestamp: datetime
    metric: TimingMetric
    value: float
    unit: str
    context: Dict[str, Any]
    passed: bool
    warning: bool
    critical: bool


@dataclass
class ValidationReport:
    """Timing validation report"""
    report_id: str
    session_id: str
    test_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    
    # Requirements and results
    requirements: List[TimingRequirement]
    measurements: List[TimingMeasurement]
    
    # Summary statistics
    total_measurements: int
    passed_measurements: int
    warning_measurements: int
    failed_measurements: int
    critical_measurements: int
    
    # Performance metrics
    overall_latency_ms: float
    latency_std_dev: float
    detection_rate: float
    false_positive_rate: float
    
    # Results
    overall_result: ValidationResult
    requirement_results: Dict[str, ValidationResult]
    
    # Metadata
    created_at: datetime
    test_configuration: Dict[str, Any]


class TimingValidationService:
    """
    Timing Validation and Reporting Service
    
    Provides comprehensive timing validation for HIL testing with
    precision timing analysis and automated reporting.
    """
    
    def __init__(self, sync_service=None):
        self.sync_service = sync_service or get_video_hardware_sync_service()
        
        # Validation state
        self.active_validations: Dict[str, Dict[str, Any]] = {}
        self.validation_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        
        # Requirements and measurements
        self.default_requirements = self._create_default_requirements()
        self.measurements: Dict[str, List[TimingMeasurement]] = {}
        self.reports: Dict[str, ValidationReport] = {}
        
        # Real-time monitoring
        self.alert_callbacks: List[callable] = []
        self.measurement_callbacks: List[callable] = []
        
        # Statistics
        self.statistics = {
            "total_validations": 0,
            "active_validations": 0,
            "total_measurements": 0,
            "reports_generated": 0,
            "alerts_triggered": 0,
            "average_latency_ms": 0.0,
            "best_latency_ms": float('inf'),
            "worst_latency_ms": 0.0
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        logger.info("⏱️ Timing Validation Service initialized")
    
    def start_validation(self, session_id: str, test_name: str,
                        requirements: Optional[List[TimingRequirement]] = None,
                        test_config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start timing validation for a test session
        
        Args:
            session_id: Test session identifier
            test_name: Name of the test
            requirements: Custom timing requirements (uses defaults if None)
            test_config: Test configuration metadata
            
        Returns:
            True if validation started successfully
        """
        with self.lock:
            if session_id in self.active_validations:
                logger.warning(f"Timing validation already active for session {session_id}")
                return True
            
            try:
                # Setup validation session
                validation_session = {
                    "session_id": session_id,
                    "test_name": test_name,
                    "start_time": datetime.now(),
                    "requirements": requirements or self.default_requirements,
                    "test_config": test_config or {},
                    "measurements": [],
                    "alerts": []
                }
                
                self.active_validations[session_id] = validation_session
                self.measurements[session_id] = []
                self.stop_events[session_id] = threading.Event()
                
                # Start validation monitoring thread
                validation_thread = threading.Thread(
                    target=self._validation_monitoring_loop,
                    args=(session_id,),
                    daemon=True,
                    name=f"TimingValidation-{session_id}"
                )
                self.validation_threads[session_id] = validation_thread
                validation_thread.start()
                
                self.statistics["total_validations"] += 1
                self.statistics["active_validations"] += 1
                
                logger.info(f"✅ Timing validation started for session {session_id}")
                logger.info(f"📊 Test: {test_name}, Requirements: {len(validation_session['requirements'])}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to start timing validation: {e}")
                return False
    
    def stop_validation(self, session_id: str, generate_report: bool = True) -> Optional[ValidationReport]:
        """
        Stop timing validation and optionally generate report
        
        Args:
            session_id: Session identifier
            generate_report: Whether to generate validation report
            
        Returns:
            Validation report if generated, None otherwise
        """
        with self.lock:
            if session_id not in self.active_validations:
                logger.warning(f"No active validation for session {session_id}")
                return None
            
            try:
                # Signal stop to validation thread
                if session_id in self.stop_events:
                    self.stop_events[session_id].set()
                
                # Wait for thread to finish
                if session_id in self.validation_threads:
                    thread = self.validation_threads[session_id]
                    thread.join(timeout=5)
                    if thread.is_alive():
                        logger.warning(f"Validation thread for session {session_id} did not stop gracefully")
                
                # Generate report if requested
                report = None
                if generate_report:
                    report = self.generate_validation_report(session_id)
                
                # Clean up session
                self._cleanup_validation_session(session_id)
                
                if self.statistics["active_validations"] > 0:
                    self.statistics["active_validations"] -= 1
                
                logger.info(f"⏹️ Timing validation stopped for session {session_id}")
                
                return report
                
            except Exception as e:
                logger.error(f"❌ Failed to stop timing validation: {e}")
                return None
    
    def add_manual_measurement(self, session_id: str, metric: TimingMetric,
                             value: float, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add manual timing measurement
        
        Args:
            session_id: Session identifier
            metric: Timing metric type
            value: Measured value
            context: Additional context information
            
        Returns:
            True if measurement added successfully
        """
        if session_id not in self.active_validations:
            logger.warning(f"No active validation for session {session_id}")
            return False
        
        try:
            measurement = self._create_measurement(
                session_id=session_id,
                metric=metric,
                value=value,
                context=context or {}
            )
            
            self._record_measurement(session_id, measurement)
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add manual measurement: {e}")
            return False
    
    def generate_validation_report(self, session_id: str) -> Optional[ValidationReport]:
        """
        Generate comprehensive validation report
        
        Args:
            session_id: Session identifier
            
        Returns:
            Validation report if successful, None otherwise
        """
        if session_id not in self.active_validations:
            logger.warning(f"No validation session found for {session_id}")
            return None
        
        try:
            validation_session = self.active_validations[session_id]
            measurements = self.measurements.get(session_id, [])
            
            # Calculate timing statistics
            latency_measurements = [m for m in measurements if m.metric == TimingMetric.LATENCY]
            latencies = [m.value for m in latency_measurements if not m.critical]
            
            overall_latency = statistics.mean(latencies) if latencies else 0.0
            latency_std_dev = statistics.stdev(latencies) if len(latencies) > 1 else 0.0
            
            # Calculate detection metrics from sync service
            detection_metrics = self._calculate_detection_metrics(session_id)
            
            # Evaluate requirements
            requirement_results = {}
            overall_result = ValidationResult.PASS
            
            for requirement in validation_session["requirements"]:
                result = self._evaluate_requirement(requirement, measurements)
                requirement_results[requirement.name] = result
                
                # Update overall result
                if result == ValidationResult.CRITICAL:
                    overall_result = ValidationResult.CRITICAL
                elif result == ValidationResult.FAIL and overall_result != ValidationResult.CRITICAL:
                    overall_result = ValidationResult.FAIL
                elif result == ValidationResult.WARNING and overall_result == ValidationResult.PASS:
                    overall_result = ValidationResult.WARNING
            
            # Count measurement results
            passed_count = sum(1 for m in measurements if m.passed and not m.warning)
            warning_count = sum(1 for m in measurements if m.warning and not m.critical)
            failed_count = sum(1 for m in measurements if not m.passed and not m.critical)
            critical_count = sum(1 for m in measurements if m.critical)
            
            # Create report
            report = ValidationReport(
                report_id=f"report_{session_id}_{int(datetime.now().timestamp())}",
                session_id=session_id,
                test_name=validation_session["test_name"],
                start_time=validation_session["start_time"],
                end_time=datetime.now(),
                duration_seconds=(datetime.now() - validation_session["start_time"]).total_seconds(),
                requirements=validation_session["requirements"],
                measurements=measurements,
                total_measurements=len(measurements),
                passed_measurements=passed_count,
                warning_measurements=warning_count,
                failed_measurements=failed_count,
                critical_measurements=critical_count,
                overall_latency_ms=overall_latency,
                latency_std_dev=latency_std_dev,
                detection_rate=detection_metrics.get("detection_rate", 0.0),
                false_positive_rate=detection_metrics.get("false_positive_rate", 0.0),
                overall_result=overall_result,
                requirement_results=requirement_results,
                created_at=datetime.now(),
                test_configuration=validation_session["test_config"]
            )
            
            # Store report
            self.reports[session_id] = report
            self.statistics["reports_generated"] += 1
            
            logger.info(f"📊 Validation report generated for session {session_id}")
            logger.info(f"   Overall result: {overall_result.value}")
            logger.info(f"   Measurements: {len(measurements)} total")
            logger.info(f"   Average latency: {overall_latency:.2f}ms (±{latency_std_dev:.2f}ms)")
            logger.info(f"   Detection rate: {detection_metrics.get('detection_rate', 0.0):.1%}")
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Failed to generate validation report: {e}")
            return None
    
    def export_report(self, session_id: str, format: str = "json") -> Optional[str]:
        """
        Export validation report in specified format
        
        Args:
            session_id: Session identifier
            format: Export format ("json", "csv", "html")
            
        Returns:
            Exported report data as string, None if failed
        """
        if session_id not in self.reports:
            logger.error(f"No report found for session {session_id}")
            return None
        
        report = self.reports[session_id]
        
        try:
            if format.lower() == "json":
                return self._export_json_report(report)
            elif format.lower() == "csv":
                return self._export_csv_report(report)
            elif format.lower() == "html":
                return self._export_html_report(report)
            else:
                logger.error(f"Unsupported export format: {format}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to export report: {e}")
            return None
    
    def get_real_time_metrics(self, session_id: str) -> Dict[str, Any]:
        """
        Get real-time timing metrics for active validation
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary of current timing metrics
        """
        if session_id not in self.active_validations:
            return {}
        
        try:
            measurements = self.measurements.get(session_id, [])
            recent_measurements = [
                m for m in measurements 
                if m.timestamp > datetime.now() - timedelta(minutes=1)
            ]
            
            # Calculate recent metrics
            recent_latencies = [m.value for m in recent_measurements if m.metric == TimingMetric.LATENCY]
            
            return {
                "session_id": session_id,
                "active": True,
                "total_measurements": len(measurements),
                "recent_measurements": len(recent_measurements),
                "current_latency_ms": recent_latencies[-1] if recent_latencies else 0.0,
                "average_latency_ms": statistics.mean(recent_latencies) if recent_latencies else 0.0,
                "latency_trend": self._calculate_latency_trend(measurements),
                "detection_rate": self._get_current_detection_rate(session_id),
                "alerts_count": len(self.active_validations[session_id].get("alerts", [])),
                "last_measurement_time": measurements[-1].timestamp.isoformat() if measurements else None
            }
            
        except Exception as e:
            logger.error(f"Error getting real-time metrics: {e}")
            return {}
    
    def add_alert_callback(self, callback: callable):
        """Add callback for timing alerts"""
        self.alert_callbacks.append(callback)
    
    def add_measurement_callback(self, callback: callable):
        """Add callback for new measurements"""
        self.measurement_callbacks.append(callback)
    
    def _create_default_requirements(self) -> List[TimingRequirement]:
        """Create default timing requirements for HIL testing"""
        return [
            TimingRequirement(
                name="Maximum Latency",
                metric=TimingMetric.LATENCY,
                target_value=50.0,  # Target: 50ms
                tolerance=20.0,     # ±20ms acceptable
                warning_threshold=70.0,   # Warning at 70ms
                critical_threshold=100.0, # Critical at 100ms
                unit="ms",
                description="Maximum detection latency requirement"
            ),
            TimingRequirement(
                name="Latency Jitter",
                metric=TimingMetric.JITTER,
                target_value=10.0,  # Target: ±10ms jitter
                tolerance=5.0,      # ±5ms acceptable
                warning_threshold=15.0,   # Warning at 15ms
                critical_threshold=25.0,  # Critical at 25ms
                unit="ms",
                description="Maximum latency variation (jitter)"
            ),
            TimingRequirement(
                name="Detection Rate",
                metric=TimingMetric.DETECTION_RATE,
                target_value=0.98,  # Target: 98% detection rate
                tolerance=0.02,     # 96% minimum acceptable
                warning_threshold=0.95,   # Warning at 95%
                critical_threshold=0.90,  # Critical at 90%
                unit="%",
                description="Minimum detection success rate"
            ),
            TimingRequirement(
                name="False Positive Rate",
                metric=TimingMetric.FALSE_POSITIVE_RATE,
                target_value=0.02,  # Target: 2% false positive rate
                tolerance=0.03,     # 5% maximum acceptable
                warning_threshold=0.08,   # Warning at 8%
                critical_threshold=0.15,  # Critical at 15%
                unit="%",
                description="Maximum false positive detection rate"
            ),
            TimingRequirement(
                name="Sync Accuracy",
                metric=TimingMetric.ACCURACY,
                target_value=10.0,  # Target: 10ms sync accuracy
                tolerance=15.0,     # ±15ms acceptable
                warning_threshold=25.0,   # Warning at 25ms
                critical_threshold=50.0,  # Critical at 50ms
                unit="ms",
                description="Video-hardware synchronization accuracy"
            )
        ]
    
    def _validation_monitoring_loop(self, session_id: str):
        """Main validation monitoring loop"""
        try:
            validation_session = self.active_validations[session_id]
            stop_event = self.stop_events[session_id]
            
            logger.info(f"🔍 Timing validation monitoring started for session {session_id}")
            
            while not stop_event.is_set():
                try:
                    # Get sync events from sync service
                    sync_events = self.sync_service.get_session_sync_events(session_id)
                    
                    # Process new sync events for timing measurements
                    for event_data in sync_events:
                        if event_data.get("detection_result") == "detected":
                            self._process_sync_event_for_timing(session_id, event_data)
                    
                    # Check for timing violations and alerts
                    self._check_timing_alerts(session_id)
                    
                    # Sleep before next check
                    time.sleep(1.0)
                    
                except Exception as e:
                    logger.error(f"❌ Error in validation monitoring loop: {e}")
                    time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"❌ Fatal error in timing validation loop: {e}")
        
        finally:
            logger.info(f"🏁 Timing validation monitoring ended for session {session_id}")
    
    def _process_sync_event_for_timing(self, session_id: str, sync_event_data: Dict[str, Any]):
        """Process sync event for timing measurements"""
        try:
            # Extract timing information
            latency_ms = sync_event_data.get("latency_ms", 0.0)
            sync_accuracy_ms = sync_event_data.get("sync_accuracy_ms", 0.0)
            
            # Create latency measurement
            if latency_ms != float('inf'):  # Valid latency measurement
                latency_measurement = self._create_measurement(
                    session_id=session_id,
                    metric=TimingMetric.LATENCY,
                    value=latency_ms,
                    context={
                        "event_id": sync_event_data.get("event_id"),
                        "channel": sync_event_data.get("hardware_event", {}).get("channel"),
                        "voltage": sync_event_data.get("hardware_event", {}).get("voltage")
                    }
                )
                self._record_measurement(session_id, latency_measurement)
            
            # Create accuracy measurement
            accuracy_measurement = self._create_measurement(
                session_id=session_id,
                metric=TimingMetric.ACCURACY,
                value=sync_accuracy_ms,
                context={
                    "event_id": sync_event_data.get("event_id"),
                    "sync_type": "video_hardware"
                }
            )
            self._record_measurement(session_id, accuracy_measurement)
            
        except Exception as e:
            logger.error(f"Error processing sync event for timing: {e}")
    
    def _create_measurement(self, session_id: str, metric: TimingMetric,
                          value: float, context: Dict[str, Any]) -> TimingMeasurement:
        """Create timing measurement with validation"""
        measurement_id = f"meas_{session_id}_{metric.value}_{int(datetime.now().timestamp() * 1000000)}"
        
        # Get requirements for this metric
        validation_session = self.active_validations[session_id]
        requirements = [r for r in validation_session["requirements"] if r.metric == metric]
        
        # Evaluate measurement against requirements
        passed = True
        warning = False
        critical = False
        
        for requirement in requirements:
            if value > requirement.critical_threshold:
                critical = True
                passed = False
            elif value > requirement.warning_threshold:
                warning = True
            elif value > requirement.target_value + requirement.tolerance:
                passed = False
        
        # Determine unit based on metric
        unit_map = {
            TimingMetric.LATENCY: "ms",
            TimingMetric.JITTER: "ms",
            TimingMetric.ACCURACY: "ms",
            TimingMetric.SYNC_DRIFT: "ms",
            TimingMetric.DETECTION_RATE: "%",
            TimingMetric.FALSE_POSITIVE_RATE: "%"
        }
        
        return TimingMeasurement(
            measurement_id=measurement_id,
            timestamp=datetime.now(),
            metric=metric,
            value=value,
            unit=unit_map.get(metric, ""),
            context=context,
            passed=passed,
            warning=warning,
            critical=critical
        )
    
    def _record_measurement(self, session_id: str, measurement: TimingMeasurement):
        """Record measurement and update statistics"""
        with self.lock:
            if session_id in self.measurements:
                self.measurements[session_id].append(measurement)
            
            # Update global statistics
            self.statistics["total_measurements"] += 1
            
            if measurement.metric == TimingMetric.LATENCY:
                current_avg = self.statistics["average_latency_ms"]
                total_measurements = self.statistics["total_measurements"]
                new_avg = ((current_avg * (total_measurements - 1)) + measurement.value) / total_measurements
                self.statistics["average_latency_ms"] = new_avg
                
                self.statistics["best_latency_ms"] = min(self.statistics["best_latency_ms"], measurement.value)
                self.statistics["worst_latency_ms"] = max(self.statistics["worst_latency_ms"], measurement.value)
        
        # Check for alerts
        if measurement.critical:
            self._trigger_alert(session_id, f"CRITICAL: {measurement.metric.value} = {measurement.value}{measurement.unit}")
        elif measurement.warning:
            self._trigger_alert(session_id, f"WARNING: {measurement.metric.value} = {measurement.value}{measurement.unit}")
        
        # Notify callbacks
        for callback in self.measurement_callbacks:
            try:
                callback(measurement)
            except Exception as e:
                logger.error(f"Error in measurement callback: {e}")
        
        logger.debug(f"📊 Measurement recorded: {measurement.metric.value} = {measurement.value}{measurement.unit}")
    
    def _check_timing_alerts(self, session_id: str):
        """Check for timing violations and generate alerts"""
        try:
            measurements = self.measurements.get(session_id, [])
            recent_measurements = [
                m for m in measurements 
                if m.timestamp > datetime.now() - timedelta(minutes=5)
            ]
            
            # Check for sustained issues
            recent_critical = [m for m in recent_measurements if m.critical]
            if len(recent_critical) >= 3:
                self._trigger_alert(session_id, f"SUSTAINED CRITICAL ISSUE: {len(recent_critical)} critical measurements in 5 minutes")
            
            # Check for latency trend
            latency_measurements = [m for m in recent_measurements if m.metric == TimingMetric.LATENCY]
            if len(latency_measurements) >= 5:
                trend = self._calculate_latency_trend(latency_measurements)
                if trend > 10:  # Increasing by >10ms
                    self._trigger_alert(session_id, f"TIMING DEGRADATION: Latency trend +{trend:.1f}ms")
            
        except Exception as e:
            logger.error(f"Error checking timing alerts: {e}")
    
    def _trigger_alert(self, session_id: str, message: str):
        """Trigger timing alert"""
        alert = {
            "session_id": session_id,
            "timestamp": datetime.now(),
            "message": message,
            "alert_id": f"alert_{session_id}_{int(datetime.now().timestamp())}"
        }
        
        # Store alert
        if session_id in self.active_validations:
            if "alerts" not in self.active_validations[session_id]:
                self.active_validations[session_id]["alerts"] = []
            self.active_validations[session_id]["alerts"].append(alert)
        
        self.statistics["alerts_triggered"] += 1
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
        
        logger.warning(f"⚠️ TIMING ALERT [{session_id}]: {message}")
    
    def _calculate_detection_metrics(self, session_id: str) -> Dict[str, float]:
        """Calculate detection performance metrics"""
        try:
            # Get sync status from sync service
            sync_status = self.sync_service.get_sync_status(session_id)
            if "statistics" in sync_status:
                stats = sync_status["statistics"]
                return {
                    "detection_rate": stats.get("detection_rate", 0.0) / 100.0,  # Convert percentage
                    "false_positive_rate": 0.0  # Would need to be calculated based on expected vs actual
                }
            return {"detection_rate": 0.0, "false_positive_rate": 0.0}
            
        except Exception as e:
            logger.error(f"Error calculating detection metrics: {e}")
            return {"detection_rate": 0.0, "false_positive_rate": 0.0}
    
    def _evaluate_requirement(self, requirement: TimingRequirement,
                            measurements: List[TimingMeasurement]) -> ValidationResult:
        """Evaluate requirement against measurements"""
        relevant_measurements = [m for m in measurements if m.metric == requirement.metric]
        
        if not relevant_measurements:
            return ValidationResult.WARNING  # No data to evaluate
        
        # Get latest or average value based on metric
        if requirement.metric in [TimingMetric.DETECTION_RATE, TimingMetric.FALSE_POSITIVE_RATE]:
            # Use latest value for rates
            value = relevant_measurements[-1].value
        else:
            # Use average for timing metrics
            values = [m.value for m in relevant_measurements if not m.critical]
            value = statistics.mean(values) if values else 0.0
        
        # Evaluate against thresholds
        if value > requirement.critical_threshold:
            return ValidationResult.CRITICAL
        elif value > requirement.warning_threshold:
            return ValidationResult.WARNING
        elif value > requirement.target_value + requirement.tolerance:
            return ValidationResult.FAIL
        else:
            return ValidationResult.PASS
    
    def _calculate_latency_trend(self, measurements: List[TimingMeasurement]) -> float:
        """Calculate latency trend (positive = increasing)"""
        if len(measurements) < 2:
            return 0.0
        
        try:
            # Use simple linear trend calculation
            latencies = [m.value for m in measurements if m.metric == TimingMetric.LATENCY]
            if len(latencies) < 2:
                return 0.0
            
            # Calculate slope of recent latency measurements
            x_values = list(range(len(latencies)))
            n = len(latencies)
            
            sum_x = sum(x_values)
            sum_y = sum(latencies)
            sum_xy = sum(x * y for x, y in zip(x_values, latencies))
            sum_x2 = sum(x * x for x in x_values)
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            return slope
            
        except Exception:
            return 0.0
    
    def _get_current_detection_rate(self, session_id: str) -> float:
        """Get current detection rate"""
        try:
            sync_status = self.sync_service.get_sync_status(session_id)
            if "statistics" in sync_status:
                return sync_status["statistics"].get("detection_rate", 0.0) / 100.0
            return 0.0
        except:
            return 0.0
    
    def _cleanup_validation_session(self, session_id: str):
        """Clean up validation session resources"""
        with self.lock:
            self.active_validations.pop(session_id, None)
            self.validation_threads.pop(session_id, None)
            self.stop_events.pop(session_id, None)
            
            # Keep measurements and reports for analysis
    
    def _export_json_report(self, report: ValidationReport) -> str:
        """Export report as JSON"""
        report_dict = asdict(report)
        
        # Convert datetime objects to ISO strings
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            else:
                return obj
        
        return json.dumps(convert_datetime(report_dict), indent=2)
    
    def _export_csv_report(self, report: ValidationReport) -> str:
        """Export report as CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Measurement ID", "Timestamp", "Metric", "Value", "Unit", "Passed", "Warning", "Critical"])
        
        # Data rows
        for measurement in report.measurements:
            writer.writerow([
                measurement.measurement_id,
                measurement.timestamp.isoformat(),
                measurement.metric.value,
                measurement.value,
                measurement.unit,
                measurement.passed,
                measurement.warning,
                measurement.critical
            ])
        
        return output.getvalue()
    
    def _export_html_report(self, report: ValidationReport) -> str:
        """Export report as HTML"""
        # This would generate a comprehensive HTML report
        # For now, return a simple HTML structure
        html = f"""
        <html>
        <head>
            <title>Timing Validation Report - {report.session_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #f0f0f0; padding: 10px; }}
                .summary {{ margin: 20px 0; }}
                .measurements {{ margin: 20px 0; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .pass {{ color: green; }}
                .warning {{ color: orange; }}
                .critical {{ color: red; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Timing Validation Report</h1>
                <h2>{report.test_name}</h2>
                <p>Session: {report.session_id}</p>
                <p>Duration: {report.duration_seconds:.1f} seconds</p>
                <p>Overall Result: <span class="{report.overall_result.value}">{report.overall_result.value.upper()}</span></p>
            </div>
            
            <div class="summary">
                <h3>Summary</h3>
                <p>Total Measurements: {report.total_measurements}</p>
                <p>Passed: {report.passed_measurements}</p>
                <p>Warnings: {report.warning_measurements}</p>
                <p>Failed: {report.failed_measurements}</p>
                <p>Critical: {report.critical_measurements}</p>
                <p>Average Latency: {report.overall_latency_ms:.2f}ms (±{report.latency_std_dev:.2f}ms)</p>
                <p>Detection Rate: {report.detection_rate:.1%}</p>
            </div>
            
            <div class="measurements">
                <h3>Measurements</h3>
                <table>
                    <tr>
                        <th>Timestamp</th>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Unit</th>
                        <th>Result</th>
                    </tr>
        """
        
        for measurement in report.measurements[-100:]:  # Show last 100 measurements
            result_class = "critical" if measurement.critical else ("warning" if measurement.warning else "pass")
            result_text = "CRITICAL" if measurement.critical else ("WARNING" if measurement.warning else "PASS")
            
            html += f"""
                    <tr>
                        <td>{measurement.timestamp.strftime('%H:%M:%S.%f')[:-3]}</td>
                        <td>{measurement.metric.value}</td>
                        <td>{measurement.value:.2f}</td>
                        <td>{measurement.unit}</td>
                        <td class="{result_class}">{result_text}</td>
                    </tr>
            """
        
        html += """
                </table>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get timing validation statistics"""
        return {
            **self.statistics,
            "active_sessions": list(self.active_validations.keys()),
            "available_reports": list(self.reports.keys()),
            "default_requirements_count": len(self.default_requirements)
        }


# Global timing validation service instance
_timing_service: Optional[TimingValidationService] = None


def get_timing_validation_service() -> TimingValidationService:
    """Get global timing validation service instance"""
    global _timing_service
    if _timing_service is None:
        _timing_service = TimingValidationService()
    return _timing_service


# Export key classes and functions
__all__ = [
    "TimingValidationService",
    "TimingMetric",
    "ValidationResult",
    "TimingRequirement",
    "TimingMeasurement",
    "ValidationReport",
    "get_timing_validation_service"
]
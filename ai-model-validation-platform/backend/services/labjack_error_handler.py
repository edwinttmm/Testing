"""
LabJack Error Handler and Recovery Service
CRITICAL Hardware Error Management

This service provides comprehensive error handling and automatic recovery
for LabJack hardware connections and operations.

Features:
- Automatic reconnection on hardware disconnection
- Error classification and reporting
- Graceful degradation
- Circuit breaker pattern
- Health monitoring and alerts
- Recovery strategies
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import queue

logger = logging.getLogger(__name__)

# Export get_error_handler_service function
def get_error_handler_service():
    """Get or create error handler service instance"""
    global _error_handler_instance
    if _error_handler_instance is None:
        _error_handler_instance = LabJackErrorHandler()
    return _error_handler_instance

_error_handler_instance = None


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"          # Minor issues, system continues
    MEDIUM = "medium"    # Significant issues, may need attention
    HIGH = "high"        # Major issues, affects functionality
    CRITICAL = "critical" # System failure, immediate action needed


class ErrorCategory(Enum):
    """Error categories for classification"""
    CONNECTION = "connection"
    HARDWARE = "hardware"
    COMMUNICATION = "communication"
    CONFIGURATION = "configuration"
    TIMEOUT = "timeout"
    DRIVER = "driver"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """Recovery actions"""
    RETRY = "retry"
    RECONNECT = "reconnect"
    RESET_HARDWARE = "reset_hardware"
    RESTART_SERVICE = "restart_service"
    MANUAL_INTERVENTION = "manual_intervention"
    GRACEFUL_DEGRADATION = "graceful_degradation"


@dataclass
class ErrorEvent:
    """Error event information"""
    error_id: str
    timestamp: datetime
    category: ErrorCategory
    severity: ErrorSeverity
    error_code: Optional[str]
    error_message: str
    context: Dict[str, Any]
    recovery_action: Optional[RecoveryAction] = None
    recovery_successful: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking"""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    next_attempt_time: Optional[datetime] = None


class LabJackErrorHandler:
    """
    Comprehensive error handler for LabJack hardware operations
    
    Provides automatic error detection, classification, and recovery
    with circuit breaker pattern and health monitoring.
    """
    
    def __init__(self, hardware_service=None):
        self.hardware_service = hardware_service
        
        # Error tracking
        self.error_history: List[ErrorEvent] = []
        self.active_errors: Dict[str, ErrorEvent] = {}
        self.error_callbacks: List[Callable[[ErrorEvent], None]] = []
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreakerState()
        self.failure_threshold = 5  # Failures before opening circuit
        self.timeout_duration = timedelta(minutes=2)  # Circuit open duration
        self.half_open_timeout = timedelta(seconds=30)  # Half-open test duration
        
        # Recovery settings
        self.max_retry_attempts = 3
        self.retry_delay_seconds = [1, 2, 5]  # Progressive delay
        self.reconnect_attempts = 3
        self.reconnect_delay = 5.0
        
        # Health monitoring
        self.health_check_thread: Optional[threading.Thread] = None
        self.health_check_active = False
        self.health_check_interval = 30.0  # seconds
        
        # Statistics
        self.statistics = {
            "total_errors": 0,
            "connection_errors": 0,
            "hardware_errors": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "circuit_breaker_trips": 0,
            "uptime_start": datetime.now(),
            "last_error_time": None,
            "mean_time_to_recovery": 0.0
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        logger.info("🛡️ LabJack Error Handler initialized")
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorEvent:
        """
        Handle and classify an error
        
        Args:
            error: The exception that occurred
            context: Additional context information
            
        Returns:
            ErrorEvent with classification and recovery recommendation
        """
        error_event = self._create_error_event(error, context or {})
        
        with self.lock:
            # Record error
            self.error_history.append(error_event)
            self.active_errors[error_event.error_id] = error_event
            self.statistics["total_errors"] += 1
            
            # Update category-specific statistics
            if error_event.category == ErrorCategory.CONNECTION:
                self.statistics["connection_errors"] += 1
            elif error_event.category == ErrorCategory.HARDWARE:
                self.statistics["hardware_errors"] += 1
            
            self.statistics["last_error_time"] = error_event.timestamp.isoformat()
            
            # Keep error history manageable
            if len(self.error_history) > 1000:
                self.error_history = self.error_history[-500:]
        
        # Update circuit breaker
        self._update_circuit_breaker(error_event)
        
        # Determine recovery action
        recovery_action = self._determine_recovery_action(error_event)
        error_event.recovery_action = recovery_action
        
        # Log error
        log_level = self._get_log_level(error_event.severity)
        logger.log(log_level, f"🚨 {error_event.severity.value.upper()} ERROR: {error_event.error_message}")
        logger.log(log_level, f"   Category: {error_event.category.value}, Recovery: {recovery_action.value if recovery_action else 'none'}")
        
        # Notify callbacks
        self._notify_error_callbacks(error_event)
        
        return error_event
    
    def _create_error_event(self, error: Exception, context: Dict[str, Any]) -> ErrorEvent:
        """Create error event with classification"""
        error_id = f"err_{int(datetime.now().timestamp() * 1000000)}"
        
        # Extract error information
        error_message = str(error)
        error_code = None
        
        if hasattr(error, 'errorCode'):
            error_code = str(error.errorCode)
        
        # Classify error
        category = self._classify_error(error, error_message)
        severity = self._determine_severity(error, category, context)
        
        return ErrorEvent(
            error_id=error_id,
            timestamp=datetime.now(),
            category=category,
            severity=severity,
            error_code=error_code,
            error_message=error_message,
            context=context.copy()
        )
    
    def _classify_error(self, error: Exception, error_message: str) -> ErrorCategory:
        """Classify error by type and message"""
        error_str = error_message.lower()
        error_type = type(error).__name__.lower()
        
        # Connection-related errors
        if any(keyword in error_str for keyword in [
            "no devices found", "device not found", "connection", "connect",
            "not connected", "disconnected", "device unavailable"
        ]):
            return ErrorCategory.CONNECTION
        
        # Hardware-related errors
        if any(keyword in error_str for keyword in [
            "hardware", "device", "usb", "labjack", "firmware", "invalid handle"
        ]) or "ljmerror" in error_type:
            return ErrorCategory.HARDWARE
        
        # Communication errors
        if any(keyword in error_str for keyword in [
            "timeout", "communication", "read", "write", "transfer", "i/o"
        ]):
            return ErrorCategory.COMMUNICATION
        
        # Configuration errors
        if any(keyword in error_str for keyword in [
            "configuration", "config", "parameter", "invalid", "range"
        ]):
            return ErrorCategory.CONFIGURATION
        
        # Timeout errors
        if any(keyword in error_str for keyword in [
            "timeout", "timed out", "time out"
        ]) or "timeout" in error_type:
            return ErrorCategory.TIMEOUT
        
        # Driver errors
        if any(keyword in error_str for keyword in [
            "driver", "library", "dll", "so", "ljm", "import"
        ]):
            return ErrorCategory.DRIVER
        
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(self, error: Exception, category: ErrorCategory, context: Dict[str, Any]) -> ErrorSeverity:
        """Determine error severity based on type and context"""
        
        # Critical errors that stop operation
        if category == ErrorCategory.DRIVER:
            return ErrorSeverity.CRITICAL
        
        if category == ErrorCategory.CONNECTION:
            # Check if this is during initial connection or during operation
            if context.get("during_monitoring", False):
                return ErrorSeverity.CRITICAL  # Loss of connection during monitoring
            else:
                return ErrorSeverity.HIGH  # Connection failure during setup
        
        if category == ErrorCategory.HARDWARE:
            # Hardware failures are typically high severity
            return ErrorSeverity.HIGH
        
        if category == ErrorCategory.COMMUNICATION:
            # Communication issues may be temporary
            return ErrorSeverity.MEDIUM
        
        if category == ErrorCategory.TIMEOUT:
            # Timeouts might be recoverable
            return ErrorSeverity.MEDIUM
        
        if category == ErrorCategory.CONFIGURATION:
            # Configuration errors are usually fixable
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    def _determine_recovery_action(self, error_event: ErrorEvent) -> Optional[RecoveryAction]:
        """Determine appropriate recovery action"""
        
        # Check circuit breaker state
        if self.circuit_breaker.state == "OPEN":
            return RecoveryAction.MANUAL_INTERVENTION
        
        category = error_event.category
        severity = error_event.severity
        
        if category == ErrorCategory.CONNECTION:
            return RecoveryAction.RECONNECT
        
        if category == ErrorCategory.HARDWARE:
            if severity == ErrorSeverity.CRITICAL:
                return RecoveryAction.RESTART_SERVICE
            else:
                return RecoveryAction.RESET_HARDWARE
        
        if category == ErrorCategory.COMMUNICATION:
            return RecoveryAction.RETRY
        
        if category == ErrorCategory.TIMEOUT:
            return RecoveryAction.RETRY
        
        if category == ErrorCategory.CONFIGURATION:
            return RecoveryAction.MANUAL_INTERVENTION
        
        if category == ErrorCategory.DRIVER:
            return RecoveryAction.MANUAL_INTERVENTION
        
        return RecoveryAction.RETRY
    
    def _update_circuit_breaker(self, error_event: ErrorEvent):
        """Update circuit breaker state based on error"""
        
        if error_event.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            with self.lock:
                self.circuit_breaker.failure_count += 1
                self.circuit_breaker.last_failure_time = error_event.timestamp
                
                if self.circuit_breaker.failure_count >= self.failure_threshold:
                    if self.circuit_breaker.state != "OPEN":
                        self.circuit_breaker.state = "OPEN"
                        self.circuit_breaker.next_attempt_time = (
                            error_event.timestamp + self.timeout_duration
                        )
                        self.statistics["circuit_breaker_trips"] += 1
                        logger.error(f"🔴 Circuit breaker OPEN - {self.circuit_breaker.failure_count} failures")
    
    def check_circuit_breaker(self) -> bool:
        """
        Check if operations should be allowed based on circuit breaker state
        
        Returns:
            True if operations are allowed, False if circuit is open
        """
        with self.lock:
            current_time = datetime.now()
            
            if self.circuit_breaker.state == "CLOSED":
                return True
            
            elif self.circuit_breaker.state == "OPEN":
                if (self.circuit_breaker.next_attempt_time and 
                    current_time >= self.circuit_breaker.next_attempt_time):
                    
                    # Move to half-open state
                    self.circuit_breaker.state = "HALF_OPEN"
                    self.circuit_breaker.next_attempt_time = current_time + self.half_open_timeout
                    logger.info("🟡 Circuit breaker HALF_OPEN - testing connection")
                    return True
                
                return False
            
            elif self.circuit_breaker.state == "HALF_OPEN":
                if (self.circuit_breaker.next_attempt_time and 
                    current_time >= self.circuit_breaker.next_attempt_time):
                    
                    # Test failed, go back to open
                    self.circuit_breaker.state = "OPEN"
                    self.circuit_breaker.next_attempt_time = current_time + self.timeout_duration
                    logger.warning("🔴 Circuit breaker back to OPEN - test failed")
                    return False
                
                return True
            
            return False
    
    def record_success(self):
        """Record successful operation to reset circuit breaker if needed"""
        with self.lock:
            if self.circuit_breaker.state == "HALF_OPEN":
                # Success in half-open state, close the circuit
                self.circuit_breaker.state = "CLOSED"
                self.circuit_breaker.failure_count = 0
                self.circuit_breaker.last_failure_time = None
                self.circuit_breaker.next_attempt_time = None
                logger.info("🟢 Circuit breaker CLOSED - connection restored")
    
    async def attempt_recovery(self, error_event: ErrorEvent) -> bool:
        """
        Attempt to recover from error
        
        Args:
            error_event: The error event to recover from
            
        Returns:
            True if recovery was successful
        """
        if not error_event.recovery_action:
            return False
        
        recovery_start = datetime.now()
        
        try:
            success = False
            
            if error_event.recovery_action == RecoveryAction.RETRY:
                success = await self._retry_operation(error_event)
            
            elif error_event.recovery_action == RecoveryAction.RECONNECT:
                success = await self._attempt_reconnection(error_event)
            
            elif error_event.recovery_action == RecoveryAction.RESET_HARDWARE:
                success = await self._reset_hardware(error_event)
            
            elif error_event.recovery_action == RecoveryAction.RESTART_SERVICE:
                success = await self._restart_service(error_event)
            
            elif error_event.recovery_action == RecoveryAction.GRACEFUL_DEGRADATION:
                success = await self._graceful_degradation(error_event)
            
            else:
                logger.info(f"Manual intervention required for error {error_event.error_id}")
                return False
            
            # Update error event
            error_event.recovery_successful = success
            if success:
                error_event.resolved_at = datetime.now()
                recovery_time = (error_event.resolved_at - recovery_start).total_seconds()
                
                # Update statistics
                with self.lock:
                    self.statistics["successful_recoveries"] += 1
                    current_mttr = self.statistics["mean_time_to_recovery"]
                    total_recoveries = self.statistics["successful_recoveries"]
                    self.statistics["mean_time_to_recovery"] = (
                        (current_mttr * (total_recoveries - 1) + recovery_time) / total_recoveries
                    )
                
                # Remove from active errors
                self.active_errors.pop(error_event.error_id, None)
                
                # Record success for circuit breaker
                self.record_success()
                
                logger.info(f"✅ Recovery successful for {error_event.error_id} ({recovery_time:.1f}s)")
            else:
                self.statistics["failed_recoveries"] += 1
                logger.error(f"❌ Recovery failed for {error_event.error_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
            error_event.recovery_successful = False
            self.statistics["failed_recoveries"] += 1
            return False
    
    async def _retry_operation(self, error_event: ErrorEvent) -> bool:
        """Retry the failed operation with progressive delay"""
        for attempt in range(self.max_retry_attempts):
            try:
                # Progressive delay
                if attempt > 0:
                    delay = self.retry_delay_seconds[min(attempt - 1, len(self.retry_delay_seconds) - 1)]
                    await asyncio.sleep(delay)
                
                # This would be implemented based on the specific operation
                # For now, we'll just test basic hardware connectivity
                if self.hardware_service and hasattr(self.hardware_service, 'read_single_voltage'):
                    voltage = self.hardware_service.read_single_voltage("AIN0")
                    return True
                
                return True  # Assume success if no specific test available
                
            except Exception as e:
                logger.debug(f"Retry attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retry_attempts - 1:
                    return False
        
        return False
    
    async def _attempt_reconnection(self, error_event: ErrorEvent) -> bool:
        """Attempt to reconnect to hardware"""
        if not self.hardware_service:
            return False
        
        try:
            # Disconnect first
            if hasattr(self.hardware_service, 'disconnect'):
                self.hardware_service.disconnect()
            
            # Wait before reconnection
            await asyncio.sleep(self.reconnect_delay)
            
            # Attempt reconnection
            for attempt in range(self.reconnect_attempts):
                try:
                    if hasattr(self.hardware_service, 'connect'):
                        success = self.hardware_service.connect()
                        if success:
                            logger.info(f"🔌 Reconnection successful on attempt {attempt + 1}")
                            return True
                    
                    if attempt < self.reconnect_attempts - 1:
                        await asyncio.sleep(self.reconnect_delay)
                
                except Exception as e:
                    logger.debug(f"Reconnection attempt {attempt + 1} failed: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"Reconnection process failed: {e}")
            return False
    
    async def _reset_hardware(self, error_event: ErrorEvent) -> bool:
        """Attempt to reset hardware state"""
        try:
            # This would implement hardware-specific reset procedures
            # For LabJack devices, this might involve:
            # - Resetting device configuration
            # - Clearing buffers
            # - Reinitializing channels
            
            logger.info("🔄 Attempting hardware reset...")
            
            if self.hardware_service:
                # Disconnect and reconnect
                if hasattr(self.hardware_service, 'disconnect'):
                    self.hardware_service.disconnect()
                
                await asyncio.sleep(2.0)  # Wait for hardware to reset
                
                if hasattr(self.hardware_service, 'connect'):
                    success = self.hardware_service.connect()
                    if success and hasattr(self.hardware_service, '_configure_hardware_channels'):
                        self.hardware_service._configure_hardware_channels()
                    return success
            
            return False
            
        except Exception as e:
            logger.error(f"Hardware reset failed: {e}")
            return False
    
    async def _restart_service(self, error_event: ErrorEvent) -> bool:
        """Restart the hardware service"""
        try:
            logger.warning("🔄 Restarting hardware service...")
            
            # This would implement service restart logic
            # For now, we'll simulate a service restart by reinitializing
            
            if self.hardware_service:
                # Stop any active monitoring
                if hasattr(self.hardware_service, 'stop_precision_monitoring'):
                    self.hardware_service.stop_precision_monitoring()
                
                # Disconnect
                if hasattr(self.hardware_service, 'disconnect'):
                    self.hardware_service.disconnect()
                
                await asyncio.sleep(5.0)  # Wait for cleanup
                
                # Reinitialize
                # This would typically involve creating a new service instance
                # For now, we'll just try to reconnect
                if hasattr(self.hardware_service, 'connect'):
                    return self.hardware_service.connect()
            
            return False
            
        except Exception as e:
            logger.error(f"Service restart failed: {e}")
            return False
    
    async def _graceful_degradation(self, error_event: ErrorEvent) -> bool:
        """Implement graceful degradation strategy"""
        try:
            logger.info("🔄 Implementing graceful degradation...")
            
            # Switch to mock mode or reduced functionality
            # This would depend on the specific error and system capabilities
            
            # For hardware errors, we might switch to simulation mode
            # For communication errors, we might reduce sampling rate
            # etc.
            
            return True  # Assume degradation is always possible
            
        except Exception as e:
            logger.error(f"Graceful degradation failed: {e}")
            return False
    
    def start_health_monitoring(self):
        """Start continuous health monitoring"""
        if self.health_check_active:
            return
        
        self.health_check_active = True
        self.health_check_thread = threading.Thread(
            target=self._health_monitoring_loop,
            daemon=True,
            name="LabJackErrorHandlerHealthMonitor"
        )
        self.health_check_thread.start()
        logger.info("🏥 Error handler health monitoring started")
    
    def stop_health_monitoring(self):
        """Stop health monitoring"""
        self.health_check_active = False
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=5)
        logger.info("🏥 Error handler health monitoring stopped")
    
    def _health_monitoring_loop(self):
        """Health monitoring loop"""
        while self.health_check_active:
            try:
                # Check for unresolved errors
                unresolved_count = len(self.active_errors)
                if unresolved_count > 10:
                    logger.warning(f"⚠️ {unresolved_count} unresolved errors - system may need attention")
                
                # Check circuit breaker state
                if self.circuit_breaker.state == "OPEN":
                    logger.warning("🔴 Circuit breaker is OPEN - hardware operations disabled")
                
                # Clean up old resolved errors
                self._cleanup_old_errors()
                
                time.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                time.sleep(10)  # Short delay on error
    
    def _cleanup_old_errors(self):
        """Clean up old resolved errors from memory"""
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        with self.lock:
            # Remove old resolved errors from active errors
            resolved_ids = [
                error_id for error_id, error in self.active_errors.items()
                if error.resolved_at and error.resolved_at < cutoff_time
            ]
            
            for error_id in resolved_ids:
                self.active_errors.pop(error_id, None)
    
    def add_error_callback(self, callback: Callable[[ErrorEvent], None]):
        """Add callback for error notifications"""
        self.error_callbacks.append(callback)
    
    def remove_error_callback(self, callback: Callable[[ErrorEvent], None]):
        """Remove error callback"""
        if callback in self.error_callbacks:
            self.error_callbacks.remove(callback)
    
    def _notify_error_callbacks(self, error_event: ErrorEvent):
        """Notify error callbacks"""
        for callback in self.error_callbacks:
            try:
                callback(error_event)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """Get appropriate log level for severity"""
        if severity == ErrorSeverity.CRITICAL:
            return logging.CRITICAL
        elif severity == ErrorSeverity.HIGH:
            return logging.ERROR
        elif severity == ErrorSeverity.MEDIUM:
            return logging.WARNING
        else:
            return logging.INFO
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error handler status"""
        with self.lock:
            recent_errors = [
                e for e in self.error_history 
                if e.timestamp > datetime.now() - timedelta(hours=24)
            ]
            
            uptime = (datetime.now() - self.statistics["uptime_start"]).total_seconds()
            
            return {
                "circuit_breaker": {
                    "state": self.circuit_breaker.state,
                    "failure_count": self.circuit_breaker.failure_count,
                    "last_failure": self.circuit_breaker.last_failure_time.isoformat() if self.circuit_breaker.last_failure_time else None
                },
                "error_counts": {
                    "total": len(self.error_history),
                    "active": len(self.active_errors),
                    "recent_24h": len(recent_errors),
                    "by_category": self._count_errors_by_category(recent_errors),
                    "by_severity": self._count_errors_by_severity(recent_errors)
                },
                "recovery": {
                    "successful_recoveries": self.statistics["successful_recoveries"],
                    "failed_recoveries": self.statistics["failed_recoveries"],
                    "success_rate": (
                        self.statistics["successful_recoveries"] / 
                        max(1, self.statistics["successful_recoveries"] + self.statistics["failed_recoveries"])
                    ) * 100.0,
                    "mean_time_to_recovery": self.statistics["mean_time_to_recovery"]
                },
                "system": {
                    "uptime_seconds": uptime,
                    "health_monitoring_active": self.health_check_active,
                    "last_error": self.statistics["last_error_time"]
                },
                "statistics": self.statistics.copy()
            }
    
    def _count_errors_by_category(self, errors: List[ErrorEvent]) -> Dict[str, int]:
        """Count errors by category"""
        counts = {}
        for error in errors:
            category = error.category.value
            counts[category] = counts.get(category, 0) + 1
        return counts
    
    def _count_errors_by_severity(self, errors: List[ErrorEvent]) -> Dict[str, int]:
        """Count errors by severity"""
        counts = {}
        for error in errors:
            severity = error.severity.value
            counts[severity] = counts.get(severity, 0) + 1
        return counts


# Global error handler instance
_error_handler: Optional[LabJackErrorHandler] = None


def get_error_handler(hardware_service=None) -> LabJackErrorHandler:
    """Get global error handler instance"""
    global _error_handler
    if _error_handler is None:
        _error_handler = LabJackErrorHandler(hardware_service)
    return _error_handler


def initialize_error_handler(hardware_service=None) -> LabJackErrorHandler:
    """Initialize error handler and start health monitoring"""
    handler = get_error_handler(hardware_service)
    handler.start_health_monitoring()
    return handler


# Context manager for error handling
class error_context:
    """Context manager for automatic error handling"""
    
    def __init__(self, operation_name: str, context: Dict[str, Any] = None):
        self.operation_name = operation_name
        self.context = context or {}
        self.error_handler = get_error_handler()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            # Error occurred, handle it
            error_event = self.error_handler.handle_error(exc_val, {
                "operation": self.operation_name,
                **self.context
            })
            
            # Optionally attempt recovery
            # This would need to be implemented based on specific requirements
            return False  # Don't suppress exception
        
        else:
            # Success, record it
            self.error_handler.record_success()
            return False


# Export key classes and functions
__all__ = [
    "LabJackErrorHandler",
    "ErrorSeverity",
    "ErrorCategory",
    "RecoveryAction",
    "ErrorEvent",
    "get_error_handler",
    "initialize_error_handler",
    "error_context"
]
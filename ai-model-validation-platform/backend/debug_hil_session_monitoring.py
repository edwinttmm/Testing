#!/usr/bin/env python3
"""
HIL Session Monitoring Diagnostic

This script monitors HIL session execution in real-time to identify
exactly when and why detection capture fails.

Focus Areas:
1. Real-time HIL session monitoring
2. Service status tracking
3. Detection event flow analysis
4. Database write verification
5. Frontend data availability check
"""

import time
import logging
import sys
import os
import json
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HILSessionMonitor:
    """Real-time HIL session monitor and diagnostic tool"""
    
    def __init__(self):
        self.monitoring_active = False
        self.monitoring_thread = None
        self.captured_data = {
            'labjack_status': [],
            'detection_events': [],
            'database_writes': [],
            'service_status': [],
            'voltage_readings': []
        }
        self.callbacks = []
        
    def add_callback(self, callback: Callable[[str, Any], None]):
        """Add callback for monitoring events"""
        self.callbacks.append(callback)
    
    def notify_callbacks(self, event_type: str, data: Any):
        """Notify all callbacks of monitoring event"""
        for callback in self.callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def check_labjack_status(self) -> Dict[str, Any]:
        """Check LabJack hardware status"""
        status = {}
        
        try:
            from services.labjack_service import get_labjack_service
            labjack_service = get_labjack_service()
            
            status.update({
                'service_status': labjack_service.status.name,
                'service_mode': labjack_service.mode.value,
                'is_connected': labjack_service.is_connected(),
                'connection_timestamp': time.time()
            })
            
            # Test connection manager
            try:
                from services.labjack_connection_manager import get_connection_manager
                connection_manager = get_connection_manager()
                
                status.update({
                    'connection_manager_available': True,
                    'connection_manager_connected': connection_manager.is_connected()
                })
                
                # Test voltage reading
                if connection_manager.is_connected():
                    voltage = connection_manager.read_voltage("AIN0")
                    status.update({
                        'voltage_reading': voltage,
                        'voltage_timestamp': time.time()
                    })
                    
            except Exception as e:
                status.update({
                    'connection_manager_available': False,
                    'connection_manager_error': str(e)
                })
                
        except Exception as e:
            status.update({
                'error': str(e),
                'timestamp': time.time()
            })
        
        return status
    
    def check_detection_service_status(self) -> Dict[str, Any]:
        """Check detection service status"""
        status = {}
        
        try:
            from services.labjack_detection_service import get_detection_service
            detection_service = get_detection_service()
            
            # Get service statistics
            stats = detection_service.get_statistics()
            
            status.update({
                'service_available': True,
                'statistics': stats,
                'timestamp': time.time()
            })
            
            # Check active sessions
            active_sessions = detection_service.get_all_sessions()
            status.update({
                'active_sessions': active_sessions,
                'active_session_count': len(active_sessions)
            })
            
        except Exception as e:
            status.update({
                'service_available': False,
                'error': str(e),
                'timestamp': time.time()
            })
        
        return status
    
    def check_dedicated_monitor_status(self) -> Dict[str, Any]:
        """Check dedicated monitor service status"""
        status = {}
        
        try:
            from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
            dedicated_monitor = get_dedicated_labjack_monitor()
            
            # Get monitoring statistics
            stats = dedicated_monitor.get_monitoring_statistics()
            
            status.update({
                'service_available': True,
                'statistics': stats,
                'timestamp': time.time()
            })
            
        except Exception as e:
            status.update({
                'service_available': False,
                'error': str(e),
                'timestamp': time.time()
            })
        
        return status
    
    def check_database_status(self) -> Dict[str, Any]:
        """Check database connectivity and DetectionEvent table"""
        status = {}
        
        try:
            from database import get_db
            from models import DetectionEvent, TestSession
            
            db = next(get_db())
            
            try:
                # Test database connectivity
                detection_count = db.query(DetectionEvent).count()
                session_count = db.query(TestSession).count()
                
                # Get recent events
                recent_events = db.query(DetectionEvent).order_by(
                    DetectionEvent.timestamp.desc()
                ).limit(5).all()
                
                status.update({
                    'database_connected': True,
                    'detection_event_count': detection_count,
                    'test_session_count': session_count,
                    'recent_events': [
                        {
                            'id': event.id,
                            'timestamp': event.timestamp,
                            'session_id': event.test_session_id,
                            'voltage': getattr(event, 'labjack_voltage', None),
                            'channel': getattr(event, 'detection_channel', None)
                        }
                        for event in recent_events
                    ],
                    'timestamp': time.time()
                })
                
            finally:
                db.close()
                
        except Exception as e:
            status.update({
                'database_connected': False,
                'error': str(e),
                'timestamp': time.time()
            })
        
        return status
    
    def monitor_voltage_readings(self, duration_seconds: int = 30) -> List[Dict[str, Any]]:
        """Monitor voltage readings for specified duration"""
        readings = []
        
        try:
            from services.labjack_connection_manager import get_connection_manager
            connection_manager = get_connection_manager()
            
            if not connection_manager.is_connected():
                connection_manager.connect()
            
            if not connection_manager.is_connected():
                logger.error("Cannot connect to LabJack for voltage monitoring")
                return readings
            
            logger.info(f"Monitoring voltage readings for {duration_seconds} seconds...")
            
            start_time = time.time()
            channels = ["AIN0", "AIN1"]
            
            while time.time() - start_time < duration_seconds:
                timestamp = time.time()
                reading = {'timestamp': timestamp, 'channels': {}}
                
                for channel in channels:
                    try:
                        voltage = connection_manager.read_voltage(channel)
                        reading['channels'][channel] = voltage
                        
                        # Detect significant voltage changes
                        if len(readings) > 0:
                            last_voltage = readings[-1]['channels'].get(channel, 0)
                            if abs(voltage - last_voltage) > 0.5:
                                logger.info(f"📊 Voltage change detected on {channel}: "
                                           f"{last_voltage:.3f}V -> {voltage:.3f}V")
                                self.notify_callbacks('voltage_change', {
                                    'channel': channel,
                                    'old_voltage': last_voltage,
                                    'new_voltage': voltage,
                                    'timestamp': timestamp
                                })
                        
                    except Exception as e:
                        reading['channels'][channel] = None
                        logger.error(f"Error reading {channel}: {e}")
                
                readings.append(reading)
                time.sleep(0.1)  # 10Hz sampling
            
        except Exception as e:
            logger.error(f"Voltage monitoring failed: {e}")
        
        return readings
    
    def simulate_hil_session(self, duration_seconds: int = 15) -> Dict[str, Any]:
        """Simulate HIL session and monitor all components"""
        logger.info("🚀 Starting HIL Session Simulation with Real-time Monitoring")
        
        session_id = f"hil_monitor_test_{int(time.time())}"
        results = {
            'session_id': session_id,
            'start_time': time.time(),
            'duration_seconds': duration_seconds,
            'monitoring_data': []
        }
        
        # Setup monitoring callback
        def monitoring_callback(event_type: str, data: Any):
            results['monitoring_data'].append({
                'timestamp': time.time(),
                'event_type': event_type,
                'data': data
            })
        
        self.add_callback(monitoring_callback)
        
        try:
            # Start dedicated monitor
            from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
            dedicated_monitor = get_dedicated_labjack_monitor()
            
            video_timing_config = {
                'video_id': 'monitor-test-video',
                'fps': 30,
                'duration': duration_seconds,
                'channels': ['AIN0'],
                'voltage_threshold': 2.5,
                'debounce_ms': 50,
                'sample_rate': 100,
                'enable_websocket': True
            }
            
            logger.info("Starting HIL monitoring session...")
            success = dedicated_monitor.start_monitoring_with_video_sync(
                session_id, video_timing_config
            )
            
            if not success:
                logger.error("❌ Failed to start HIL monitoring session")
                return results
            
            logger.info("✅ HIL monitoring session started")
            
            # Monitor system status every second
            monitor_start = time.time()
            monitoring_count = 0
            
            while time.time() - monitor_start < duration_seconds:
                monitoring_count += 1
                timestamp = time.time()
                
                # Collect status from all services
                labjack_status = self.check_labjack_status()
                detection_status = self.check_detection_service_status()
                dedicated_status = self.check_dedicated_monitor_status()
                database_status = self.check_database_status()
                
                status_snapshot = {
                    'monitoring_count': monitoring_count,
                    'timestamp': timestamp,
                    'labjack': labjack_status,
                    'detection_service': detection_status,
                    'dedicated_monitor': dedicated_status,
                    'database': database_status
                }
                
                # Log significant events
                if labjack_status.get('voltage_reading') and labjack_status['voltage_reading'] > 2.0:
                    logger.info(f"🎯 High voltage detected: {labjack_status['voltage_reading']:.3f}V")
                    self.notify_callbacks('high_voltage', labjack_status)
                
                detection_stats = detection_status.get('statistics', {})
                if detection_stats.get('total_events', 0) > 0:
                    logger.info(f"📊 Detection events: {detection_stats['total_events']}")
                    self.notify_callbacks('detection_event', detection_stats)
                
                database_events = database_status.get('detection_event_count', 0)
                if monitoring_count == 1:
                    results['initial_db_events'] = database_events
                else:
                    new_events = database_events - results.get('initial_db_events', 0)
                    if new_events > 0:
                        logger.info(f"💾 New database events: {new_events}")
                        self.notify_callbacks('database_write', {'new_events': new_events})
                
                self.captured_data['service_status'].append(status_snapshot)
                
                time.sleep(1.0)  # Monitor every second
            
            # Stop monitoring and get final statistics
            final_stats = dedicated_monitor.stop_monitoring(session_id)
            logger.info(f"📊 Final HIL Statistics: {final_stats}")
            
            results.update({
                'end_time': time.time(),
                'final_statistics': final_stats,
                'monitoring_snapshots': len(self.captured_data['service_status']),
                'events_captured': len(self.captured_data['monitoring_data'])
            })
            
        except Exception as e:
            logger.error(f"HIL session simulation failed: {e}")
            results['error'] = str(e)
        
        return results
    
    def generate_monitoring_report(self, session_results: Dict[str, Any]) -> str:
        """Generate comprehensive monitoring report"""
        report_lines = [
            "=" * 80,
            "HIL SESSION MONITORING REPORT",
            "=" * 80,
            "",
            f"Session ID: {session_results.get('session_id', 'Unknown')}",
            f"Duration: {session_results.get('duration_seconds', 0)} seconds",
            f"Start Time: {datetime.fromtimestamp(session_results.get('start_time', 0))}",
            "",
            "SERVICE STATUS ANALYSIS:",
            "-" * 40
        ]
        
        # Analyze service status over time
        status_snapshots = self.captured_data.get('service_status', [])
        if status_snapshots:
            first_snapshot = status_snapshots[0]
            last_snapshot = status_snapshots[-1]
            
            # LabJack analysis
            labjack_connected = sum(1 for s in status_snapshots 
                                  if s.get('labjack', {}).get('is_connected', False))
            report_lines.extend([
                f"LabJack Connection: {labjack_connected}/{len(status_snapshots)} snapshots connected",
                f"Initial LabJack Status: {first_snapshot.get('labjack', {}).get('service_status', 'Unknown')}",
                f"Final LabJack Status: {last_snapshot.get('labjack', {}).get('service_status', 'Unknown')}",
                ""
            ])
            
            # Detection service analysis
            detection_available = sum(1 for s in status_snapshots 
                                    if s.get('detection_service', {}).get('service_available', False))
            report_lines.extend([
                f"Detection Service: {detection_available}/{len(status_snapshots)} snapshots available",
                f"Active Sessions: {last_snapshot.get('detection_service', {}).get('active_session_count', 0)}",
                ""
            ])
            
            # Database analysis
            db_connected = sum(1 for s in status_snapshots 
                             if s.get('database', {}).get('database_connected', False))
            report_lines.extend([
                f"Database Connection: {db_connected}/{len(status_snapshots)} snapshots connected",
                ""
            ])
        
        # Event analysis
        monitoring_events = session_results.get('monitoring_data', [])
        event_types = {}
        for event in monitoring_events:
            event_type = event.get('event_type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        report_lines.extend([
            "MONITORING EVENTS:",
            "-" * 40
        ])
        for event_type, count in event_types.items():
            report_lines.append(f"{event_type:20}: {count} events")
        
        # Final statistics
        final_stats = session_results.get('final_statistics', {})
        report_lines.extend([
            "",
            "FINAL STATISTICS:",
            "-" * 40,
            f"Detection Count: {final_stats.get('detection_count', 0)}",
            f"Average Latency: {final_stats.get('average_latency_ms', 0):.1f}ms",
            f"Success Rate: {final_stats.get('conversion_success_rate', 0):.1f}%",
            "",
            "DIAGNOSIS:",
            "-" * 40
        ])
        
        # Generate diagnosis
        detection_count = final_stats.get('detection_count', 0)
        if detection_count == 0:
            report_lines.append("🚨 CRITICAL: Zero detections captured")
            if labjack_connected < len(status_snapshots) * 0.8:
                report_lines.append("  - LabJack connection issues detected")
            if detection_available < len(status_snapshots) * 0.8:
                report_lines.append("  - Detection service availability issues")
            if 'voltage_change' not in event_types:
                report_lines.append("  - No voltage changes detected - check signal source")
        elif detection_count > 0:
            report_lines.append("✅ Detections captured successfully")
            if final_stats.get('average_latency_ms', 0) > 200:
                report_lines.append("  - High latency detected - performance issue")
        
        report_lines.extend(["", "=" * 80])
        
        return "\n".join(report_lines)

def main():
    """Main monitoring function"""
    logger.info("🔍 Starting HIL Session Monitoring Diagnostic")
    
    monitor = HILSessionMonitor()
    
    # Run comprehensive monitoring test
    session_results = monitor.simulate_hil_session(duration_seconds=20)
    
    # Generate and save monitoring report
    report = monitor.generate_monitoring_report(session_results)
    
    report_file = f'hil_monitoring_report_{int(time.time())}.txt'
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(report)
    logger.info(f"📄 Monitoring report saved to: {report_file}")
    
    # Save raw monitoring data
    data_file = f'hil_monitoring_data_{int(time.time())}.json'
    with open(data_file, 'w') as f:
        json.dump({
            'session_results': session_results,
            'captured_data': monitor.captured_data
        }, f, indent=2)
    
    logger.info(f"📄 Raw monitoring data saved to: {data_file}")
    
    # Determine success
    detection_count = session_results.get('final_statistics', {}).get('detection_count', 0)
    success = detection_count > 0
    
    if success:
        logger.info("🎉 HIL MONITORING SUCCESS - System is working")
    else:
        logger.error("🚨 HIL MONITORING FAILED - System needs repair")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
# Hardware Integration Test Plan - AI Model Validation Platform

## Overview

The Hardware Integration Test Plan covers testing the AI Model Validation Platform's integration with Raspberry Pi devices, camera systems, and real-world hardware scenarios. This ensures reliable communication, data accuracy, and system stability in production environments.

## Hardware Test Architecture

### Test Environment Components
1. **Raspberry Pi Test Devices** - Multiple Pi units with different configurations
2. **Camera Systems** - Various camera models and connection types
3. **Network Infrastructure** - WiFi, Ethernet, and cellular connections
4. **GPIO Test Harness** - Hardware simulation for signal testing
5. **Power Management** - Battery and power supply testing
6. **Environmental Chamber** - Temperature and humidity testing

## Raspberry Pi Integration Testing

### Hardware Setup and Configuration Tests

```python
# tests/hardware/test_raspberry_pi_setup.py

import pytest
import time
import subprocess
import json
import requests
from typing import Dict, Any, List
from unittest.mock import Mock, patch
import RPi.GPIO as GPIO
import picamera
import socket

class RaspberryPiTestHarness:
    """Test harness for Raspberry Pi hardware integration."""
    
    def __init__(self, pi_ip: str = "192.168.1.100", api_port: int = 8080):
        self.pi_ip = pi_ip
        self.api_port = api_port
        self.base_url = f"http://{pi_ip}:{api_port}"
        self.gpio_pins = []
        
    def setup_gpio_pins(self, pins: List[int]):
        """Setup GPIO pins for testing."""
        GPIO.setmode(GPIO.BCM)
        self.gpio_pins = pins
        
        for pin in pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
    
    def cleanup_gpio(self):
        """Clean up GPIO resources."""
        for pin in self.gpio_pins:
            GPIO.output(pin, GPIO.LOW)
        GPIO.cleanup()
    
    def test_network_connectivity(self) -> Dict[str, Any]:
        """Test network connectivity to Raspberry Pi."""
        try:
            # Test ping
            ping_result = subprocess.run(
                ["ping", "-c", "3", self.pi_ip],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            ping_success = ping_result.returncode == 0
            
            # Test API connectivity
            api_response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            
            api_success = api_response.status_code == 200
            
            return {
                "ping_success": ping_success,
                "ping_output": ping_result.stdout,
                "api_success": api_success,
                "api_response": api_response.json() if api_success else None,
                "response_time_ms": api_response.elapsed.total_seconds() * 1000 if api_success else None
            }
            
        except Exception as e:
            return {
                "ping_success": False,
                "api_success": False,
                "error": str(e)
            }
    
    def test_camera_functionality(self) -> Dict[str, Any]:
        """Test camera capture functionality."""
        try:
            with picamera.PiCamera() as camera:
                camera.resolution = (1920, 1080)
                camera.start_preview()
                time.sleep(2)  # Camera warm-up
                
                # Test image capture
                camera.capture('/tmp/test_image.jpg')
                
                # Test video recording
                camera.start_recording('/tmp/test_video.h264')
                time.sleep(5)
                camera.stop_recording()
                
                camera.stop_preview()
                
                # Verify files exist and have content
                import os
                image_size = os.path.getsize('/tmp/test_image.jpg')
                video_size = os.path.getsize('/tmp/test_video.h264')
                
                return {
                    "camera_available": True,
                    "image_capture_success": image_size > 0,
                    "video_capture_success": video_size > 0,
                    "image_size_bytes": image_size,
                    "video_size_bytes": video_size
                }
                
        except Exception as e:
            return {
                "camera_available": False,
                "error": str(e)
            }
    
    def test_gpio_signals(self, test_pin: int = 18) -> Dict[str, Any]:
        """Test GPIO signal generation and detection."""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(test_pin, GPIO.OUT)
            
            # Test signal patterns
            test_patterns = [
                [GPIO.HIGH, GPIO.LOW] * 5,  # Alternating
                [GPIO.HIGH] * 10,           # Constant high
                [GPIO.LOW] * 10,            # Constant low
            ]
            
            results = []
            
            for i, pattern in enumerate(test_patterns):
                pattern_start = time.time()
                
                for signal in pattern:
                    GPIO.output(test_pin, signal)
                    time.sleep(0.1)  # 100ms per signal
                
                pattern_duration = time.time() - pattern_start
                
                results.append({
                    "pattern_id": i,
                    "expected_duration": len(pattern) * 0.1,
                    "actual_duration": pattern_duration,
                    "timing_accuracy": abs(pattern_duration - (len(pattern) * 0.1)) < 0.05
                })
            
            GPIO.cleanup()
            
            return {
                "gpio_available": True,
                "test_results": results,
                "overall_success": all(r["timing_accuracy"] for r in results)
            }
            
        except Exception as e:
            return {
                "gpio_available": False,
                "error": str(e)
            }
    
    def test_system_resources(self) -> Dict[str, Any]:
        """Test system resource availability and performance."""
        try:
            # CPU temperature
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                cpu_temp = int(f.read()) / 1000.0
            
            # CPU usage
            cpu_info = subprocess.run(
                ["cat", "/proc/stat"],
                capture_output=True,
                text=True
            )
            
            # Memory usage
            with open('/proc/meminfo', 'r') as f:
                mem_info = f.read()
            
            # Parse memory info
            mem_lines = mem_info.split('\n')
            mem_total = int([line for line in mem_lines if 'MemTotal:' in line][0].split()[1]) * 1024
            mem_available = int([line for line in mem_lines if 'MemAvailable:' in line][0].split()[1]) * 1024
            mem_usage_percent = ((mem_total - mem_available) / mem_total) * 100
            
            # Disk usage
            disk_usage = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True,
                text=True
            )
            
            disk_usage_line = disk_usage.stdout.split('\n')[1]
            disk_usage_percent = int(disk_usage_line.split()[4].replace('%', ''))
            
            return {
                "cpu_temperature_celsius": cpu_temp,
                "memory_usage_percent": round(mem_usage_percent, 2),
                "memory_total_gb": round(mem_total / (1024**3), 2),
                "memory_available_gb": round(mem_available / (1024**3), 2),
                "disk_usage_percent": disk_usage_percent,
                "system_healthy": (
                    cpu_temp < 80 and 
                    mem_usage_percent < 90 and 
                    disk_usage_percent < 95
                )
            }
            
        except Exception as e:
            return {
                "system_healthy": False,
                "error": str(e)
            }

@pytest.mark.hardware
class TestRaspberryPiIntegration:
    """Raspberry Pi hardware integration tests."""
    
    @pytest.fixture
    def pi_harness(self):
        """Raspberry Pi test harness fixture."""
        harness = RaspberryPiTestHarness()
        yield harness
        harness.cleanup_gpio()
    
    def test_raspberry_pi_connectivity(self, pi_harness):
        """Test basic connectivity to Raspberry Pi."""
        result = pi_harness.test_network_connectivity()
        
        assert result["ping_success"], "Failed to ping Raspberry Pi"
        assert result["api_success"], "Failed to connect to Pi API"
        assert result["response_time_ms"] < 100, f"API response too slow: {result['response_time_ms']}ms"
        
        print(f"Pi connectivity test passed - Response time: {result['response_time_ms']:.2f}ms")
    
    def test_camera_hardware(self, pi_harness):
        """Test camera hardware functionality."""
        result = pi_harness.test_camera_functionality()
        
        assert result["camera_available"], f"Camera not available: {result.get('error', 'Unknown error')}"
        assert result["image_capture_success"], "Image capture failed"
        assert result["video_capture_success"], "Video capture failed"
        assert result["image_size_bytes"] > 10000, "Image file too small"
        assert result["video_size_bytes"] > 50000, "Video file too small"
        
        print(f"Camera test passed - Image: {result['image_size_bytes']} bytes, Video: {result['video_size_bytes']} bytes")
    
    def test_gpio_functionality(self, pi_harness):
        """Test GPIO signal generation."""
        result = pi_harness.test_gpio_signals(18)
        
        assert result["gpio_available"], f"GPIO not available: {result.get('error', 'Unknown error')}"
        assert result["overall_success"], "GPIO timing accuracy test failed"
        
        for test_result in result["test_results"]:
            assert test_result["timing_accuracy"], f"Pattern {test_result['pattern_id']} timing failed"
        
        print("GPIO functionality test passed")
    
    def test_system_performance(self, pi_harness):
        """Test Raspberry Pi system performance."""
        result = pi_harness.test_system_resources()
        
        assert result["system_healthy"], f"System unhealthy: {result.get('error', 'Resource limits exceeded')}"
        assert result["cpu_temperature_celsius"] < 80, f"CPU too hot: {result['cpu_temperature_celsius']}°C"
        assert result["memory_usage_percent"] < 90, f"Memory usage too high: {result['memory_usage_percent']}%"
        assert result["disk_usage_percent"] < 95, f"Disk usage too high: {result['disk_usage_percent']}%"
        
        print(f"System performance: CPU {result['cpu_temperature_celsius']}°C, "
              f"Memory {result['memory_usage_percent']}%, Disk {result['disk_usage_percent']}%")
```

### Real-time Detection Testing

```python
# tests/hardware/test_real_time_detection.py

import pytest
import asyncio
import websockets
import json
import time
import threading
from typing import Dict, Any, List
import cv2
import numpy as np

class RealTimeDetectionTester:
    """Test real-time detection capabilities."""
    
    def __init__(self, pi_ip: str = "192.168.1.100", websocket_port: int = 8081):
        self.pi_ip = pi_ip
        self.websocket_port = websocket_port
        self.websocket_url = f"ws://{pi_ip}:{websocket_port}/detection"
        self.detection_events = []
        self.connection = None
        
    async def connect_to_pi(self):
        """Connect to Raspberry Pi WebSocket."""
        try:
            self.connection = await websockets.connect(self.websocket_url)
            print(f"Connected to Pi WebSocket: {self.websocket_url}")
            return True
        except Exception as e:
            print(f"Failed to connect to Pi WebSocket: {e}")
            return False
    
    async def start_detection_stream(self, duration: float = 30.0):
        """Start detection stream and collect events."""
        if not self.connection:
            await self.connect_to_pi()
        
        start_time = time.time()
        self.detection_events.clear()
        
        # Send start detection command
        start_command = {
            "command": "start_detection",
            "config": {
                "confidence_threshold": 0.5,
                "detection_classes": ["pedestrian", "cyclist", "vehicle"]
            }
        }
        
        await self.connection.send(json.dumps(start_command))
        
        try:
            while time.time() - start_time < duration:
                # Wait for detection events
                message = await asyncio.wait_for(
                    self.connection.recv(),
                    timeout=1.0
                )
                
                event = json.loads(message)
                if event.get("type") == "detection":
                    self.detection_events.append(event)
                    
        except asyncio.TimeoutError:
            # No event received in timeout period
            pass
        
        # Send stop detection command
        stop_command = {"command": "stop_detection"}
        await self.connection.send(json.dumps(stop_command))
        
        return self.detection_events
    
    async def simulate_detection_scenario(self, scenario_config: Dict[str, Any]):
        """Simulate specific detection scenario."""
        # Send scenario configuration to Pi
        scenario_command = {
            "command": "simulate_scenario",
            "scenario": scenario_config
        }
        
        await self.connection.send(json.dumps(scenario_command))
        
        # Wait for scenario completion
        scenario_duration = scenario_config.get("duration", 10.0)
        events = await self.start_detection_stream(scenario_duration + 5.0)
        
        return events
    
    def analyze_detection_performance(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze detection performance metrics."""
        if not events:
            return {
                "total_events": 0,
                "events_per_second": 0,
                "avg_confidence": 0,
                "class_distribution": {},
                "timing_consistency": False
            }
        
        # Basic statistics
        total_events = len(events)
        
        # Calculate events per second
        if total_events > 1:
            first_timestamp = events[0]["timestamp"]
            last_timestamp = events[-1]["timestamp"]
            duration = last_timestamp - first_timestamp
            events_per_second = total_events / duration if duration > 0 else 0
        else:
            events_per_second = 0
        
        # Average confidence
        confidences = [event["confidence"] for event in events]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Class distribution
        class_distribution = {}
        for event in events:
            class_label = event["class_label"]
            class_distribution[class_label] = class_distribution.get(class_label, 0) + 1
        
        # Timing consistency (check for regular intervals)
        timing_intervals = []
        for i in range(1, len(events)):
            interval = events[i]["timestamp"] - events[i-1]["timestamp"]
            timing_intervals.append(interval)
        
        timing_consistency = False
        if timing_intervals:
            avg_interval = sum(timing_intervals) / len(timing_intervals)
            interval_variance = sum((x - avg_interval) ** 2 for x in timing_intervals) / len(timing_intervals)
            timing_consistency = interval_variance < 0.1  # Low variance indicates consistency
        
        return {
            "total_events": total_events,
            "events_per_second": round(events_per_second, 2),
            "avg_confidence": round(avg_confidence, 3),
            "confidence_range": [min(confidences), max(confidences)] if confidences else [0, 0],
            "class_distribution": class_distribution,
            "timing_consistency": timing_consistency,
            "avg_interval_ms": round(sum(timing_intervals) / len(timing_intervals) * 1000, 2) if timing_intervals else 0
        }
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.connection:
            await self.connection.close()
            self.connection = None

@pytest.mark.hardware
@pytest.mark.asyncio
class TestRealTimeDetection:
    """Real-time detection hardware tests."""
    
    @pytest.fixture
    async def detection_tester(self):
        """Detection tester fixture."""
        tester = RealTimeDetectionTester()
        yield tester
        await tester.disconnect()
    
    async def test_basic_detection_stream(self, detection_tester):
        """Test basic detection stream functionality."""
        connected = await detection_tester.connect_to_pi()
        assert connected, "Failed to connect to Pi detection WebSocket"
        
        # Run detection for 15 seconds
        events = await detection_tester.start_detection_stream(15.0)
        
        # Analyze performance
        performance = detection_tester.analyze_detection_performance(events)
        
        # Performance assertions
        assert performance["total_events"] > 0, "No detection events received"
        assert performance["events_per_second"] > 0.1, "Detection rate too low"
        assert performance["avg_confidence"] > 0.3, "Average confidence too low"
        
        print(f"Detection performance: {performance['total_events']} events, "
              f"{performance['events_per_second']} events/sec, "
              f"avg confidence: {performance['avg_confidence']}")
    
    async def test_pedestrian_detection_scenario(self, detection_tester):
        """Test pedestrian detection scenario."""
        connected = await detection_tester.connect_to_pi()
        assert connected, "Failed to connect to Pi detection WebSocket"
        
        # Configure pedestrian scenario
        scenario_config = {
            "type": "pedestrian_crossing",
            "duration": 10.0,
            "pedestrian_count": 2,
            "crossing_speed": "normal"
        }
        
        events = await detection_tester.simulate_detection_scenario(scenario_config)
        performance = detection_tester.analyze_detection_performance(events)
        
        # Scenario-specific assertions
        assert performance["total_events"] >= 2, "Expected at least 2 pedestrian detections"
        assert "pedestrian" in performance["class_distribution"], "No pedestrian class detected"
        assert performance["class_distribution"]["pedestrian"] >= 2, "Insufficient pedestrian detections"
        
        print(f"Pedestrian scenario: {performance['class_distribution']} detections")
    
    async def test_multi_object_detection(self, detection_tester):
        """Test multi-object detection scenario."""
        connected = await detection_tester.connect_to_pi()
        assert connected, "Failed to connect to Pi detection WebSocket"
        
        # Configure multi-object scenario
        scenario_config = {
            "type": "mixed_traffic",
            "duration": 20.0,
            "objects": {
                "pedestrians": 2,
                "cyclists": 1,
                "vehicles": 3
            }
        }
        
        events = await detection_tester.simulate_detection_scenario(scenario_config)
        performance = detection_tester.analyze_detection_performance(events)
        
        # Multi-object assertions
        assert len(performance["class_distribution"]) >= 2, "Expected multiple object classes"
        
        total_expected = sum(scenario_config["objects"].values())
        total_detected = sum(performance["class_distribution"].values())
        
        detection_rate = total_detected / total_expected if total_expected > 0 else 0
        assert detection_rate >= 0.6, f"Detection rate too low: {detection_rate * 100:.1f}%"
        
        print(f"Multi-object scenario: {performance['class_distribution']} (rate: {detection_rate * 100:.1f}%)")
    
    async def test_detection_timing_accuracy(self, detection_tester):
        """Test detection timing accuracy."""
        connected = await detection_tester.connect_to_pi()
        assert connected, "Failed to connect to Pi detection WebSocket"
        
        # Configure regular interval scenario
        scenario_config = {
            "type": "timed_objects",
            "duration": 15.0,
            "interval_seconds": 2.0,
            "object_type": "pedestrian"
        }
        
        events = await detection_tester.simulate_detection_scenario(scenario_config)
        performance = detection_tester.analyze_detection_performance(events)
        
        # Timing accuracy assertions
        expected_interval_ms = 2000  # 2 seconds
        actual_interval_ms = performance["avg_interval_ms"]
        
        timing_error = abs(actual_interval_ms - expected_interval_ms)
        assert timing_error < 200, f"Timing accuracy error too high: {timing_error}ms"
        
        assert performance["timing_consistency"], "Detection timing not consistent"
        
        print(f"Timing accuracy: expected {expected_interval_ms}ms, actual {actual_interval_ms}ms")
```

### Environmental and Stress Testing

```python
# tests/hardware/test_environmental_conditions.py

import pytest
import time
import requests
import subprocess
from typing import Dict, Any, List
import json

class EnvironmentalTestHarness:
    """Test harness for environmental condition testing."""
    
    def __init__(self, pi_ip: str = "192.168.1.100"):
        self.pi_ip = pi_ip
        self.base_url = f"http://{pi_ip}:8080"
        self.stress_processes = []
        
    def monitor_system_during_stress(self, duration: int = 300) -> List[Dict[str, Any]]:
        """Monitor system performance during stress test."""
        metrics = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                response = requests.get(f"{self.base_url}/system/metrics", timeout=5)
                
                if response.status_code == 200:
                    metric = response.json()
                    metric["timestamp"] = time.time()
                    metrics.append(metric)
                
                time.sleep(10)  # Sample every 10 seconds
                
            except requests.RequestException as e:
                # Log error but continue monitoring
                error_metric = {
                    "timestamp": time.time(),
                    "error": str(e),
                    "system_responsive": False
                }
                metrics.append(error_metric)
        
        return metrics
    
    def start_cpu_stress_test(self, cpu_percent: int = 80):
        """Start CPU stress test."""
        # Use stress tool to load CPU
        stress_cmd = [
            "stress",
            "--cpu", str(4),  # Use 4 CPU cores
            "--timeout", "600"  # 10 minute timeout
        ]
        
        process = subprocess.Popen(stress_cmd)
        self.stress_processes.append(process)
        
        return process.pid
    
    def start_memory_stress_test(self, memory_mb: int = 512):
        """Start memory stress test."""
        stress_cmd = [
            "stress",
            "--vm", "2",
            "--vm-bytes", f"{memory_mb}M",
            "--timeout", "600"
        ]
        
        process = subprocess.Popen(stress_cmd)
        self.stress_processes.append(process)
        
        return process.pid
    
    def start_io_stress_test(self):
        """Start I/O stress test."""
        stress_cmd = [
            "stress",
            "--io", "4",
            "--timeout", "600"
        ]
        
        process = subprocess.Popen(stress_cmd)
        self.stress_processes.append(process)
        
        return process.pid
    
    def stop_all_stress_tests(self):
        """Stop all running stress tests."""
        for process in self.stress_processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        self.stress_processes.clear()
    
    def test_thermal_performance(self, target_temp: float = 70.0) -> Dict[str, Any]:
        """Test system performance under thermal stress."""
        # Start stress tests to heat up system
        self.start_cpu_stress_test(90)
        
        temp_readings = []
        detection_performance = []
        
        start_time = time.time()
        
        while time.time() - start_time < 600:  # 10 minute test
            try:
                # Get temperature reading
                temp_response = requests.get(f"{self.base_url}/system/temperature")
                if temp_response.status_code == 200:
                    temp_data = temp_response.json()
                    temp_readings.append({
                        "timestamp": time.time(),
                        "temperature": temp_data["cpu_temperature"]
                    })
                
                # Test detection performance
                perf_response = requests.get(f"{self.base_url}/detection/performance")
                if perf_response.status_code == 200:
                    perf_data = perf_response.json()
                    detection_performance.append({
                        "timestamp": time.time(),
                        "fps": perf_data["current_fps"],
                        "accuracy": perf_data["detection_accuracy"]
                    })
                
                # Check if target temperature reached
                if temp_readings and temp_readings[-1]["temperature"] > target_temp:
                    print(f"Target temperature {target_temp}°C reached")
                
                time.sleep(30)  # Sample every 30 seconds
                
            except requests.RequestException:
                # Continue test even if request fails
                pass
        
        self.stop_all_stress_tests()
        
        return {
            "temperature_readings": temp_readings,
            "detection_performance": detection_performance,
            "max_temperature": max([r["temperature"] for r in temp_readings]) if temp_readings else 0,
            "min_fps": min([p["fps"] for p in detection_performance]) if detection_performance else 0,
            "thermal_throttling": any(r["temperature"] > 80 for r in temp_readings)
        }
    
    def test_power_consumption(self, duration: int = 300) -> Dict[str, Any]:
        """Test power consumption under various loads."""
        power_readings = []
        
        # Test phases: idle, moderate load, high load
        test_phases = [
            {"name": "idle", "duration": 60, "load": None},
            {"name": "moderate", "duration": 120, "load": "cpu_50"},
            {"name": "high", "duration": 120, "load": "cpu_90"}
        ]
        
        for phase in test_phases:
            phase_start = time.time()
            
            # Start appropriate load
            if phase["load"] == "cpu_50":
                self.start_cpu_stress_test(50)
            elif phase["load"] == "cpu_90":
                self.start_cpu_stress_test(90)
            
            # Monitor power consumption
            while time.time() - phase_start < phase["duration"]:
                try:
                    power_response = requests.get(f"{self.base_url}/system/power")
                    if power_response.status_code == 200:
                        power_data = power_response.json()
                        power_readings.append({
                            "timestamp": time.time(),
                            "phase": phase["name"],
                            "power_watts": power_data["power_consumption"],
                            "voltage": power_data["voltage"],
                            "current": power_data["current"]
                        })
                    
                    time.sleep(10)  # Sample every 10 seconds
                    
                except requests.RequestException:
                    pass
            
            self.stop_all_stress_tests()
            time.sleep(30)  # Cool down between phases
        
        # Analyze power consumption by phase
        phase_analysis = {}
        for phase_name in ["idle", "moderate", "high"]:
            phase_readings = [r for r in power_readings if r["phase"] == phase_name]
            
            if phase_readings:
                power_values = [r["power_watts"] for r in phase_readings]
                phase_analysis[phase_name] = {
                    "avg_power_watts": sum(power_values) / len(power_values),
                    "max_power_watts": max(power_values),
                    "min_power_watts": min(power_values)
                }
        
        return {
            "power_readings": power_readings,
            "phase_analysis": phase_analysis,
            "total_duration": duration
        }

@pytest.mark.hardware
@pytest.mark.environmental
class TestEnvironmentalConditions:
    """Environmental and stress testing."""
    
    @pytest.fixture
    def env_harness(self):
        """Environmental test harness fixture."""
        harness = EnvironmentalTestHarness()
        yield harness
        harness.stop_all_stress_tests()
    
    def test_thermal_stress_performance(self, env_harness):
        """Test system performance under thermal stress."""
        result = env_harness.test_thermal_performance(70.0)
        
        # Performance assertions
        assert result["max_temperature"] < 85, f"Temperature too high: {result['max_temperature']}°C"
        
        if result["detection_performance"]:
            assert result["min_fps"] > 5, f"FPS dropped too low under thermal stress: {result['min_fps']}"
        
        # System should not thermally throttle severely
        high_temp_readings = sum(1 for r in result["temperature_readings"] if r["temperature"] > 80)
        total_readings = len(result["temperature_readings"])
        
        if total_readings > 0:
            thermal_stress_ratio = high_temp_readings / total_readings
            assert thermal_stress_ratio < 0.3, f"Too much time in thermal stress: {thermal_stress_ratio * 100:.1f}%"
        
        print(f"Thermal test: max temp {result['max_temperature']}°C, min FPS {result['min_fps']}")
    
    def test_memory_stress_detection(self, env_harness):
        """Test detection performance under memory stress."""
        # Start memory stress
        env_harness.start_memory_stress_test(800)  # 800MB stress
        
        # Monitor for 5 minutes
        metrics = env_harness.monitor_system_during_stress(300)
        
        env_harness.stop_all_stress_tests()
        
        # Analyze metrics
        responsive_count = sum(1 for m in metrics if m.get("system_responsive", True))
        total_count = len(metrics)
        
        if total_count > 0:
            responsiveness = responsive_count / total_count
            assert responsiveness > 0.8, f"System responsiveness too low under memory stress: {responsiveness * 100:.1f}%"
        
        # Check memory usage stayed within limits
        memory_metrics = [m for m in metrics if "memory_percent" in m]
        if memory_metrics:
            max_memory = max(m["memory_percent"] for m in memory_metrics)
            assert max_memory < 95, f"Memory usage too high: {max_memory}%"
        
        print(f"Memory stress test: {responsiveness * 100:.1f}% responsive, max memory {max_memory:.1f}%")
    
    def test_network_connectivity_stress(self, env_harness):
        """Test network connectivity under system stress."""
        # Start I/O stress to impact network performance
        env_harness.start_io_stress_test()
        
        network_tests = []
        start_time = time.time()
        
        # Test network connectivity every 30 seconds for 10 minutes
        while time.time() - start_time < 600:
            try:
                response_start = time.time()
                response = requests.get(f"{env_harness.base_url}/health", timeout=10)
                response_time = time.time() - response_start
                
                network_tests.append({
                    "timestamp": time.time(),
                    "success": response.status_code == 200,
                    "response_time": response_time
                })
                
            except requests.RequestException as e:
                network_tests.append({
                    "timestamp": time.time(),
                    "success": False,
                    "error": str(e),
                    "response_time": 10.0  # Timeout
                })
            
            time.sleep(30)
        
        env_harness.stop_all_stress_tests()
        
        # Analyze network performance
        successful_tests = [t for t in network_tests if t["success"]]
        success_rate = len(successful_tests) / len(network_tests) if network_tests else 0
        
        assert success_rate > 0.9, f"Network success rate too low under stress: {success_rate * 100:.1f}%"
        
        if successful_tests:
            avg_response_time = sum(t["response_time"] for t in successful_tests) / len(successful_tests)
            assert avg_response_time < 2.0, f"Average response time too slow under stress: {avg_response_time:.2f}s"
        
        print(f"Network stress test: {success_rate * 100:.1f}% success rate, avg response {avg_response_time:.2f}s")
    
    @pytest.mark.slow
    def test_long_duration_stability(self, env_harness):
        """Test system stability over extended period."""
        # 4-hour stability test
        duration = 4 * 60 * 60  # 4 hours in seconds
        
        # Light continuous load
        env_harness.start_cpu_stress_test(30)
        
        stability_metrics = env_harness.monitor_system_during_stress(duration)
        
        env_harness.stop_all_stress_tests()
        
        # Analyze stability
        system_errors = sum(1 for m in stability_metrics if not m.get("system_responsive", True))
        total_samples = len(stability_metrics)
        
        if total_samples > 0:
            stability_rate = (total_samples - system_errors) / total_samples
            assert stability_rate > 0.95, f"System stability too low: {stability_rate * 100:.1f}%"
        
        print(f"Long duration test: {stability_rate * 100:.1f}% stability over {duration/3600:.1f} hours")
```

### Hardware Configuration Matrix Testing

```python
# tests/hardware/test_hardware_configurations.py

import pytest
from dataclasses import dataclass
from typing import List, Dict, Any
import itertools

@dataclass
class HardwareConfiguration:
    """Hardware configuration specification."""
    pi_model: str
    camera_model: str
    connection_type: str
    power_source: str
    storage_type: str
    network_type: str

class HardwareConfigurationTester:
    """Test matrix of hardware configurations."""
    
    def __init__(self):
        # Define configuration matrix
        self.pi_models = ["Pi 4B 4GB", "Pi 4B 8GB", "Pi Zero 2W"]
        self.camera_models = ["Pi Camera V2", "Pi Camera V3", "USB Camera"]
        self.connection_types = ["GPIO", "USB", "Ethernet"]
        self.power_sources = ["USB-C 5V", "Battery Pack", "PoE"]
        self.storage_types = ["SD Card", "USB Drive", "SSD"]
        self.network_types = ["WiFi", "Ethernet", "4G"]
        
        # Known incompatible combinations
        self.incompatible_combinations = [
            ("Pi Zero 2W", "PoE"),  # Pi Zero doesn't support PoE
            ("USB Camera", "GPIO"),  # USB cameras don't use GPIO
        ]
    
    def generate_test_configurations(self) -> List[HardwareConfiguration]:
        """Generate all valid hardware configurations."""
        configurations = []
        
        # Generate all combinations
        for combination in itertools.product(
            self.pi_models,
            self.camera_models, 
            self.connection_types,
            self.power_sources,
            self.storage_types,
            self.network_types
        ):
            config = HardwareConfiguration(*combination)
            
            # Skip incompatible combinations
            is_compatible = True
            for incompatible in self.incompatible_combinations:
                if all(attr in [config.pi_model, config.camera_model, 
                              config.connection_type, config.power_source] 
                      for attr in incompatible):
                    is_compatible = False
                    break
            
            if is_compatible:
                configurations.append(config)
        
        return configurations
    
    def test_configuration_compatibility(self, config: HardwareConfiguration) -> Dict[str, Any]:
        """Test specific hardware configuration compatibility."""
        test_results = {
            "configuration": config.__dict__,
            "tests": {}
        }
        
        # Test power consumption compatibility
        power_compatible = self._test_power_compatibility(config)
        test_results["tests"]["power_compatibility"] = power_compatible
        
        # Test I/O compatibility
        io_compatible = self._test_io_compatibility(config)
        test_results["tests"]["io_compatibility"] = io_compatible
        
        # Test performance expectations
        performance_adequate = self._test_performance_expectations(config)
        test_results["tests"]["performance_adequate"] = performance_adequate
        
        # Test network functionality
        network_functional = self._test_network_functionality(config)
        test_results["tests"]["network_functional"] = network_functional
        
        # Overall compatibility
        test_results["overall_compatible"] = all([
            power_compatible["compatible"],
            io_compatible["compatible"],
            performance_adequate["adequate"],
            network_functional["functional"]
        ])
        
        return test_results
    
    def _test_power_compatibility(self, config: HardwareConfiguration) -> Dict[str, Any]:
        """Test power source compatibility with hardware."""
        power_requirements = {
            "Pi 4B 4GB": {"min_watts": 15, "max_watts": 25},
            "Pi 4B 8GB": {"min_watts": 18, "max_watts": 28},
            "Pi Zero 2W": {"min_watts": 3, "max_watts": 8}
        }
        
        power_capabilities = {
            "USB-C 5V": {"watts": 15, "stable": True},
            "Battery Pack": {"watts": 20, "stable": False},
            "PoE": {"watts": 25, "stable": True}
        }
        
        pi_requirements = power_requirements.get(config.pi_model, {"min_watts": 20, "max_watts": 30})
        power_capability = power_capabilities.get(config.power_source, {"watts": 10, "stable": False})
        
        sufficient_power = power_capability["watts"] >= pi_requirements["min_watts"]
        
        return {
            "compatible": sufficient_power,
            "power_margin": power_capability["watts"] - pi_requirements["min_watts"],
            "stable_power": power_capability["stable"],
            "requirements": pi_requirements,
            "capability": power_capability
        }
    
    def _test_io_compatibility(self, config: HardwareConfiguration) -> Dict[str, Any]:
        """Test I/O interface compatibility."""
        # Define I/O capabilities by Pi model
        io_capabilities = {
            "Pi 4B 4GB": {"gpio": True, "usb": 4, "ethernet": True, "camera_csi": True},
            "Pi 4B 8GB": {"gpio": True, "usb": 4, "ethernet": True, "camera_csi": True},
            "Pi Zero 2W": {"gpio": True, "usb": 1, "ethernet": False, "camera_csi": True}
        }
        
        # Check camera connection compatibility
        camera_compatible = True
        camera_message = "Compatible"
        
        pi_caps = io_capabilities.get(config.pi_model, {})
        
        if config.camera_model == "Pi Camera V2" or config.camera_model == "Pi Camera V3":
            if not pi_caps.get("camera_csi", False):
                camera_compatible = False
                camera_message = "Pi model doesn't support CSI camera"
        elif config.camera_model == "USB Camera":
            if pi_caps.get("usb", 0) < 1:
                camera_compatible = False
                camera_message = "Pi model doesn't have USB ports"
        
        # Check connection type compatibility
        connection_compatible = True
        connection_message = "Compatible"
        
        if config.connection_type == "Ethernet" and not pi_caps.get("ethernet", False):
            connection_compatible = False
            connection_message = "Pi model doesn't support Ethernet"
        elif config.connection_type == "USB" and pi_caps.get("usb", 0) < 2:
            connection_compatible = False
            connection_message = "Insufficient USB ports"
        
        return {
            "compatible": camera_compatible and connection_compatible,
            "camera_compatible": camera_compatible,
            "camera_message": camera_message,
            "connection_compatible": connection_compatible,
            "connection_message": connection_message,
            "io_capabilities": pi_caps
        }
    
    def _test_performance_expectations(self, config: HardwareConfiguration) -> Dict[str, Any]:
        """Test expected performance for configuration."""
        # Performance baselines by Pi model
        performance_baselines = {
            "Pi 4B 4GB": {"fps": 30, "processing_delay": 50, "concurrent_streams": 2},
            "Pi 4B 8GB": {"fps": 30, "processing_delay": 40, "concurrent_streams": 3},
            "Pi Zero 2W": {"fps": 15, "processing_delay": 100, "concurrent_streams": 1}
        }
        
        # Storage impact on performance
        storage_impact = {
            "SD Card": {"write_speed": 10, "reliability": 0.8},
            "USB Drive": {"write_speed": 30, "reliability": 0.9},
            "SSD": {"write_speed": 100, "reliability": 0.95}
        }
        
        baseline = performance_baselines.get(config.pi_model, {"fps": 15, "processing_delay": 100})
        storage = storage_impact.get(config.storage_type, {"write_speed": 10, "reliability": 0.8})
        
        # Adjust expectations based on storage
        expected_fps = baseline["fps"]
        if storage["write_speed"] < 20:
            expected_fps *= 0.8  # Reduce expected FPS for slow storage
        
        expected_delay = baseline["processing_delay"]
        if storage["write_speed"] < 20:
            expected_delay *= 1.5  # Increase delay for slow storage
        
        adequate_performance = (
            expected_fps >= 10 and  # Minimum viable FPS
            expected_delay <= 200 and  # Maximum acceptable delay
            storage["reliability"] >= 0.7  # Minimum reliability
        )
        
        return {
            "adequate": adequate_performance,
            "expected_fps": round(expected_fps, 1),
            "expected_delay_ms": round(expected_delay, 1),
            "storage_reliability": storage["reliability"],
            "baseline_performance": baseline,
            "storage_impact": storage
        }
    
    def _test_network_functionality(self, config: HardwareConfiguration) -> Dict[str, Any]:
        """Test network functionality for configuration."""
        # Network capabilities by type
        network_capabilities = {
            "WiFi": {"bandwidth_mbps": 100, "latency_ms": 10, "reliability": 0.9},
            "Ethernet": {"bandwidth_mbps": 1000, "latency_ms": 2, "reliability": 0.98},
            "4G": {"bandwidth_mbps": 50, "latency_ms": 50, "reliability": 0.85}
        }
        
        # Check Pi model network support
        network_support = {
            "Pi 4B 4GB": {"WiFi": True, "Ethernet": True, "4G": False},
            "Pi 4B 8GB": {"WiFi": True, "Ethernet": True, "4G": False},
            "Pi Zero 2W": {"WiFi": True, "Ethernet": False, "4G": False}
        }
        
        pi_support = network_support.get(config.pi_model, {})
        network_supported = pi_support.get(config.network_type, False)
        
        if network_supported:
            network_caps = network_capabilities.get(config.network_type, {})
            
            # Check if network meets minimum requirements
            min_bandwidth = 10  # Mbps
            max_latency = 100   # ms
            min_reliability = 0.8
            
            functional = (
                network_caps.get("bandwidth_mbps", 0) >= min_bandwidth and
                network_caps.get("latency_ms", 200) <= max_latency and
                network_caps.get("reliability", 0) >= min_reliability
            )
        else:
            functional = False
            network_caps = {}
        
        return {
            "functional": functional and network_supported,
            "network_supported": network_supported,
            "network_capabilities": network_caps,
            "pi_network_support": pi_support
        }

@pytest.mark.hardware
@pytest.mark.parametrize
class TestHardwareConfigurations:
    """Hardware configuration matrix tests."""
    
    @pytest.fixture
    def config_tester(self):
        """Hardware configuration tester fixture."""
        return HardwareConfigurationTester()
    
    def test_all_configurations_compatibility(self, config_tester):
        """Test compatibility of all hardware configurations."""
        configurations = config_tester.generate_test_configurations()
        
        # Test a sample of configurations (all would be too many)
        sample_size = min(50, len(configurations))
        test_configs = configurations[:sample_size]
        
        results = []
        compatible_count = 0
        
        for config in test_configs:
            result = config_tester.test_configuration_compatibility(config)
            results.append(result)
            
            if result["overall_compatible"]:
                compatible_count += 1
        
        # At least 70% of configurations should be compatible
        compatibility_rate = compatible_count / len(test_configs)
        assert compatibility_rate >= 0.7, f"Too many incompatible configurations: {compatibility_rate * 100:.1f}%"
        
        print(f"Configuration compatibility: {compatible_count}/{len(test_configs)} ({compatibility_rate * 100:.1f}%)")
        
        # Log incompatible configurations for review
        incompatible_configs = [r for r in results if not r["overall_compatible"]]
        for config_result in incompatible_configs[:5]:  # Show first 5
            config = config_result["configuration"]
            print(f"Incompatible: {config['pi_model']} + {config['camera_model']} + {config['power_source']}")
    
    def test_recommended_configurations(self, config_tester):
        """Test recommended hardware configurations."""
        # Define recommended configurations
        recommended_configs = [
            HardwareConfiguration(
                "Pi 4B 4GB", "Pi Camera V3", "GPIO", "USB-C 5V", "SD Card", "WiFi"
            ),
            HardwareConfiguration(
                "Pi 4B 8GB", "Pi Camera V3", "GPIO", "PoE", "SSD", "Ethernet"
            ),
            HardwareConfiguration(
                "Pi 4B 4GB", "USB Camera", "USB", "USB-C 5V", "USB Drive", "WiFi"
            )
        ]
        
        for config in recommended_configs:
            result = config_tester.test_configuration_compatibility(config)
            
            assert result["overall_compatible"], f"Recommended configuration not compatible: {config}"
            
            # Check performance meets high standards
            perf = result["tests"]["performance_adequate"]
            assert perf["expected_fps"] >= 20, f"Recommended config FPS too low: {perf['expected_fps']}"
            assert perf["expected_delay_ms"] <= 100, f"Recommended config delay too high: {perf['expected_delay_ms']}"
            
            print(f"Recommended config validated: {config.pi_model} + {config.camera_model}")
```

This comprehensive hardware integration test plan ensures robust testing of the AI Model Validation Platform's integration with Raspberry Pi devices and various hardware configurations, covering connectivity, performance, environmental conditions, and configuration compatibility.
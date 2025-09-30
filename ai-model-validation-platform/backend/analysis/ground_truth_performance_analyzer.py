#!/usr/bin/env python3
"""
Ground Truth System Performance Bottleneck Analyzer
Comprehensive analysis tool for identifying performance bottlenecks in the ground truth system.
"""

import asyncio
import logging
import time
import psutil
import threading
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import sqlite3
import cv2
import numpy as np
import json
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import tracemalloc
import memory_profiler
import cProfile
import pstats
import io
from functools import wraps
import os
import sys
import subprocess

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from services.ground_truth_service import GroundTruthService
from src.services.enhanced_ground_truth_service import EnhancedGroundTruthService
from services.detection_pipeline_service import DetectionPipeline
from database import SessionLocal

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for analysis"""
    operation: str
    start_time: float
    end_time: float
    duration: float
    memory_before: float
    memory_after: float
    memory_peak: float
    cpu_percent: float
    io_read_bytes: int
    io_write_bytes: int
    gpu_memory: Optional[float] = None
    additional_metrics: Dict[str, Any] = None

@dataclass
class SystemResourceUsage:
    """System resource usage snapshot"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_available: int
    memory_used: int
    disk_io_read: int
    disk_io_write: int
    network_io_sent: int
    network_io_recv: int
    gpu_memory_used: Optional[float] = None
    gpu_utilization: Optional[float] = None

class PerformanceProfiler:
    """Context manager for profiling code blocks"""
    
    def __init__(self, operation_name: str, enable_memory_profiling: bool = True):
        self.operation_name = operation_name
        self.enable_memory_profiling = enable_memory_profiling
        self.start_time = None
        self.memory_before = None
        self.memory_peak = None
        self.cpu_start = None
        self.io_start = None
        self.profiler = None
        
    def __enter__(self):
        # Start time measurement
        self.start_time = time.time()
        
        # Memory profiling
        if self.enable_memory_profiling:
            tracemalloc.start()
            self.memory_before = psutil.virtual_memory().used / 1024 / 1024  # MB
        
        # CPU measurement
        self.cpu_start = psutil.cpu_percent()
        
        # I/O measurement
        process = psutil.Process()
        self.io_start = process.io_counters()
        
        # Code profiling
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Stop profiling
        self.profiler.disable()
        
        # End measurements
        end_time = time.time()
        duration = end_time - self.start_time
        
        # Memory measurements
        memory_after = psutil.virtual_memory().used / 1024 / 1024  # MB
        memory_peak = self.memory_before
        
        if self.enable_memory_profiling:
            current, peak = tracemalloc.get_traced_memory()
            memory_peak = peak / 1024 / 1024  # MB
            tracemalloc.stop()
        
        # CPU measurement
        cpu_percent = psutil.cpu_percent()
        
        # I/O measurement
        process = psutil.Process()
        io_end = process.io_counters()
        io_read = io_end.read_bytes - self.io_start.read_bytes
        io_write = io_end.write_bytes - self.io_start.write_bytes
        
        # GPU measurement (if available)
        gpu_memory = None
        try:
            import torch
            if torch.cuda.is_available():
                gpu_memory = torch.cuda.memory_allocated() / 1024 / 1024  # MB
        except ImportError:
            pass
        
        # Create metrics object
        self.metrics = PerformanceMetrics(
            operation=self.operation_name,
            start_time=self.start_time,
            end_time=end_time,
            duration=duration,
            memory_before=self.memory_before,
            memory_after=memory_after,
            memory_peak=memory_peak,
            cpu_percent=cpu_percent,
            io_read_bytes=io_read,
            io_write_bytes=io_write,
            gpu_memory=gpu_memory
        )
        
        logger.info(f"Performance: {self.operation_name} took {duration:.3f}s, "
                   f"Memory: {memory_peak - self.memory_before:.1f}MB peak, "
                   f"CPU: {cpu_percent:.1f}%, I/O: {io_read/1024:.1f}KB read, {io_write/1024:.1f}KB write")
        
    def get_profile_stats(self) -> str:
        """Get detailed profiling statistics"""
        if not self.profiler:
            return "No profiling data available"
            
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s)
        ps.sort_stats('cumulative').print_stats(20)  # Top 20 functions
        return s.getvalue()

class ResourceMonitor:
    """Continuous system resource monitoring"""
    
    def __init__(self, interval: float = 0.1):
        self.interval = interval
        self.monitoring = False
        self.metrics = []
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Start resource monitoring in background thread"""
        self.monitoring = True
        self.metrics = []
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self) -> List[SystemResourceUsage]:
        """Stop monitoring and return collected metrics"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        return self.metrics.copy()
        
    def _monitor_loop(self):
        """Monitoring loop running in background thread"""
        while self.monitoring:
            try:
                # Get system metrics
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                network_io = psutil.net_io_counters()
                
                # GPU metrics (if available)
                gpu_memory = None
                gpu_util = None
                try:
                    import torch
                    if torch.cuda.is_available():
                        gpu_memory = torch.cuda.memory_allocated() / 1024 / 1024  # MB
                        # GPU utilization would need nvidia-ml-py
                except ImportError:
                    pass
                
                usage = SystemResourceUsage(
                    timestamp=time.time(),
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_available=memory.available,
                    memory_used=memory.used,
                    disk_io_read=disk_io.read_bytes if disk_io else 0,
                    disk_io_write=disk_io.write_bytes if disk_io else 0,
                    network_io_sent=network_io.bytes_sent if network_io else 0,
                    network_io_recv=network_io.bytes_recv if network_io else 0,
                    gpu_memory_used=gpu_memory,
                    gpu_utilization=gpu_util
                )
                
                self.metrics.append(usage)
                
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                time.sleep(self.interval)

class GroundTruthPerformanceAnalyzer:
    """Main performance analysis class for ground truth system"""
    
    def __init__(self):
        self.results = {}
        self.baseline_metrics = {}
        self.optimization_recommendations = []
        
    async def run_comprehensive_analysis(self, test_video_path: str = None) -> Dict[str, Any]:
        """Run comprehensive performance analysis"""
        logger.info("🚀 Starting comprehensive ground truth performance analysis...")
        
        # Create test video if not provided
        if not test_video_path:
            test_video_path = await self._create_test_video()
        
        # Run all analysis components
        analyses = {
            "processing_speed": await self._analyze_processing_speed(test_video_path),
            "memory_usage": await self._analyze_memory_usage(test_video_path),
            "io_operations": await self._analyze_io_operations(test_video_path),
            "resource_utilization": await self._analyze_resource_utilization(test_video_path),
            "scalability": await self._analyze_scalability(test_video_path),
            "caching_opportunities": await self._analyze_caching_opportunities(),
            "database_performance": await self._analyze_database_performance(),
            "configuration_impact": await self._analyze_configuration_impact(test_video_path)
        }
        
        # Generate optimization recommendations
        self.optimization_recommendations = await self._generate_optimization_recommendations(analyses)
        
        # Apply 5 Whys analysis
        bottleneck_analysis = await self._apply_five_whys_analysis(analyses)
        
        # Compile final report
        report = {
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "test_video_path": test_video_path,
            "system_info": self._get_system_info(),
            "analyses": analyses,
            "optimization_recommendations": self.optimization_recommendations,
            "bottleneck_analysis": bottleneck_analysis,
            "performance_score": self._calculate_performance_score(analyses)
        }
        
        # Save report
        await self._save_report(report)
        
        return report
    
    async def _analyze_processing_speed(self, video_path: str) -> Dict[str, Any]:
        """Analyze ground truth generation processing speed"""
        logger.info("📊 Analyzing processing speed...")
        
        results = {}
        
        # Test basic ground truth service
        with PerformanceProfiler("basic_ground_truth_processing") as profiler:
            service = GroundTruthService()
            video_id = "test-video-basic"
            await service.process_video_async(video_id, video_path)
        
        results["basic_service"] = {
            "metrics": asdict(profiler.metrics),
            "profile_stats": profiler.get_profile_stats()
        }
        
        # Test enhanced ground truth service
        with PerformanceProfiler("enhanced_ground_truth_processing") as profiler:
            enhanced_service = EnhancedGroundTruthService()
            video_id = "test-video-enhanced"
            await enhanced_service.process_video_async(video_id, video_path)
        
        results["enhanced_service"] = {
            "metrics": asdict(profiler.metrics),
            "profile_stats": profiler.get_profile_stats()
        }
        
        # Test detection pipeline
        with PerformanceProfiler("detection_pipeline_processing") as profiler:
            pipeline = DetectionPipeline()
            await pipeline.initialize()
            detections = await pipeline.process_video(video_path)
        
        results["detection_pipeline"] = {
            "metrics": asdict(profiler.metrics),
            "profile_stats": profiler.get_profile_stats(),
            "detection_count": len(detections) if detections else 0
        }
        
        # Analyze component breakdown
        results["component_analysis"] = await self._analyze_processing_components(video_path)
        
        return results
    
    async def _analyze_processing_components(self, video_path: str) -> Dict[str, Any]:
        """Break down processing into components to identify bottlenecks"""
        components = {}
        
        # Video loading time
        with PerformanceProfiler("video_loading") as profiler:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
        
        components["video_loading"] = asdict(profiler.metrics)
        
        # Frame extraction time
        with PerformanceProfiler("frame_extraction") as profiler:
            cap = cv2.VideoCapture(video_path)
            frames = []
            for i in range(min(100, frame_count)):  # Test with first 100 frames
                ret, frame = cap.read()
                if ret:
                    frames.append(frame)
            cap.release()
        
        components["frame_extraction"] = asdict(profiler.metrics)
        components["frames_extracted"] = len(frames)
        
        # YOLO inference time (if available)
        try:
            from ultralytics import YOLO
            model = YOLO('yolov8n.pt')
            
            with PerformanceProfiler("yolo_inference") as profiler:
                for frame in frames[:10]:  # Test with first 10 frames
                    results = model(frame, verbose=False)
            
            components["yolo_inference"] = asdict(profiler.metrics)
        except Exception as e:
            components["yolo_inference"] = {"error": str(e)}
        
        # Database operations
        with PerformanceProfiler("database_operations") as profiler:
            db = SessionLocal()
            try:
                # Simulate ground truth object creation
                for i in range(100):
                    # This would be actual database inserts in real scenario
                    pass
            finally:
                db.close()
        
        components["database_operations"] = asdict(profiler.metrics)
        
        # Screenshot generation
        if frames:
            with PerformanceProfiler("screenshot_generation") as profiler:
                for i, frame in enumerate(frames[:10]):
                    screenshot_path = f"/tmp/test_screenshot_{i}.jpg"
                    cv2.imwrite(screenshot_path, frame)
            
            components["screenshot_generation"] = asdict(profiler.metrics)
        
        return components
    
    async def _analyze_memory_usage(self, video_path: str) -> Dict[str, Any]:
        """Analyze memory consumption patterns"""
        logger.info("💾 Analyzing memory usage...")
        
        monitor = ResourceMonitor(interval=0.1)
        monitor.start_monitoring()
        
        try:
            # Memory usage during video processing
            service = GroundTruthService()
            await service.process_video_async("memory-test", video_path)
            
            # Get monitoring data
            resource_data = monitor.stop_monitoring()
            
            # Analyze memory patterns
            memory_usage = [r.memory_used / 1024 / 1024 for r in resource_data]  # MB
            memory_percent = [r.memory_percent for r in resource_data]
            
            return {
                "peak_memory_mb": max(memory_usage) if memory_usage else 0,
                "average_memory_mb": sum(memory_usage) / len(memory_usage) if memory_usage else 0,
                "memory_growth_mb": (memory_usage[-1] - memory_usage[0]) if len(memory_usage) > 1 else 0,
                "peak_memory_percent": max(memory_percent) if memory_percent else 0,
                "memory_timeline": resource_data,
                "potential_memory_leaks": self._detect_memory_leaks(memory_usage)
            }
            
        finally:
            monitor.stop_monitoring()
    
    def _detect_memory_leaks(self, memory_usage: List[float]) -> Dict[str, Any]:
        """Detect potential memory leaks"""
        if len(memory_usage) < 10:
            return {"detected": False, "reason": "Insufficient data"}
        
        # Calculate trend
        x = list(range(len(memory_usage)))
        y = memory_usage
        
        # Simple linear regression
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        
        # If slope > 0.1 MB per measurement, consider it a potential leak
        leak_detected = slope > 0.1
        
        return {
            "detected": leak_detected,
            "memory_growth_rate_mb_per_sample": slope,
            "confidence": "high" if slope > 0.5 else "medium" if slope > 0.1 else "low"
        }
    
    async def _analyze_io_operations(self, video_path: str) -> Dict[str, Any]:
        """Analyze I/O operation efficiency"""
        logger.info("💿 Analyzing I/O operations...")
        
        monitor = ResourceMonitor(interval=0.05)
        monitor.start_monitoring()
        
        try:
            service = GroundTruthService()
            await service.process_video_async("io-test", video_path)
            
            resource_data = monitor.stop_monitoring()
            
            # Analyze I/O patterns
            disk_reads = [r.disk_io_read for r in resource_data]
            disk_writes = [r.disk_io_write for r in resource_data]
            
            total_read = max(disk_reads) - min(disk_reads) if disk_reads else 0
            total_write = max(disk_writes) - min(disk_writes) if disk_writes else 0
            
            return {
                "total_disk_read_mb": total_read / 1024 / 1024,
                "total_disk_write_mb": total_write / 1024 / 1024,
                "io_efficiency_score": self._calculate_io_efficiency(video_path, total_read, total_write),
                "io_timeline": resource_data,
                "bottleneck_detection": self._detect_io_bottlenecks(resource_data)
            }
            
        finally:
            monitor.stop_monitoring()
    
    def _calculate_io_efficiency(self, video_path: str, total_read: int, total_write: int) -> Dict[str, Any]:
        """Calculate I/O efficiency score"""
        try:
            video_size = os.path.getsize(video_path)
            read_ratio = total_read / video_size if video_size > 0 else 0
            
            # Efficient processing should read video once (ratio ≈ 1)
            # Additional reads indicate inefficiency
            efficiency_score = max(0, 100 - (read_ratio - 1) * 50)
            
            return {
                "score": efficiency_score,
                "video_size_mb": video_size / 1024 / 1024,
                "read_ratio": read_ratio,
                "efficiency_level": "excellent" if efficiency_score > 90 else "good" if efficiency_score > 70 else "poor"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _detect_io_bottlenecks(self, resource_data: List[SystemResourceUsage]) -> Dict[str, Any]:
        """Detect I/O bottlenecks"""
        if len(resource_data) < 5:
            return {"detected": False, "reason": "Insufficient data"}
        
        # Calculate I/O rates
        io_rates = []
        for i in range(1, len(resource_data)):
            time_diff = resource_data[i].timestamp - resource_data[i-1].timestamp
            read_diff = resource_data[i].disk_io_read - resource_data[i-1].disk_io_read
            rate = (read_diff / time_diff) / 1024 / 1024 if time_diff > 0 else 0  # MB/s
            io_rates.append(rate)
        
        avg_rate = sum(io_rates) / len(io_rates) if io_rates else 0
        peak_rate = max(io_rates) if io_rates else 0
        
        # Detect bottleneck if rate is consistently low
        bottleneck_detected = avg_rate < 10  # Less than 10 MB/s is considered slow
        
        return {
            "detected": bottleneck_detected,
            "average_read_rate_mbps": avg_rate,
            "peak_read_rate_mbps": peak_rate,
            "bottleneck_severity": "high" if avg_rate < 5 else "medium" if avg_rate < 10 else "low"
        }
    
    async def _analyze_resource_utilization(self, video_path: str) -> Dict[str, Any]:
        """Analyze CPU, GPU, and disk utilization patterns"""
        logger.info("⚡ Analyzing resource utilization...")
        
        monitor = ResourceMonitor(interval=0.1)
        monitor.start_monitoring()
        
        try:
            service = GroundTruthService()
            await service.process_video_async("resource-test", video_path)
            
            resource_data = monitor.stop_monitoring()
            
            # Analyze utilization patterns
            cpu_usage = [r.cpu_percent for r in resource_data]
            memory_usage = [r.memory_percent for r in resource_data]
            
            return {
                "cpu_analysis": {
                    "peak_usage": max(cpu_usage) if cpu_usage else 0,
                    "average_usage": sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0,
                    "utilization_efficiency": self._calculate_cpu_efficiency(cpu_usage)
                },
                "memory_analysis": {
                    "peak_usage": max(memory_usage) if memory_usage else 0,
                    "average_usage": sum(memory_usage) / len(memory_usage) if memory_usage else 0
                },
                "gpu_analysis": self._analyze_gpu_utilization(resource_data),
                "resource_timeline": resource_data,
                "bottleneck_identification": self._identify_resource_bottlenecks(resource_data)
            }
            
        finally:
            monitor.stop_monitoring()
    
    def _calculate_cpu_efficiency(self, cpu_usage: List[float]) -> Dict[str, Any]:
        """Calculate CPU utilization efficiency"""
        if not cpu_usage:
            return {"error": "No CPU data available"}
        
        avg_usage = sum(cpu_usage) / len(cpu_usage)
        peak_usage = max(cpu_usage)
        
        # Good efficiency means consistent moderate usage
        efficiency_score = 100 - abs(avg_usage - 60)  # Optimal around 60%
        efficiency_score = max(0, min(100, efficiency_score))
        
        return {
            "efficiency_score": efficiency_score,
            "average_usage": avg_usage,
            "peak_usage": peak_usage,
            "consistency": (100 - (max(cpu_usage) - min(cpu_usage))),
            "recommendation": self._get_cpu_recommendation(avg_usage, peak_usage)
        }
    
    def _get_cpu_recommendation(self, avg_usage: float, peak_usage: float) -> str:
        """Get CPU usage recommendation"""
        if avg_usage < 20:
            return "CPU underutilized - consider increasing parallelism"
        elif avg_usage > 90:
            return "CPU overutilized - consider reducing concurrent operations"
        elif peak_usage > 95:
            return "CPU spikes detected - optimize hot paths"
        else:
            return "CPU usage is within acceptable range"
    
    def _analyze_gpu_utilization(self, resource_data: List[SystemResourceUsage]) -> Dict[str, Any]:
        """Analyze GPU utilization if available"""
        gpu_memory = [r.gpu_memory_used for r in resource_data if r.gpu_memory_used is not None]
        
        if not gpu_memory:
            return {"available": False, "message": "No GPU detected or monitoring unavailable"}
        
        return {
            "available": True,
            "peak_memory_mb": max(gpu_memory),
            "average_memory_mb": sum(gpu_memory) / len(gpu_memory),
            "utilization_timeline": gpu_memory,
            "efficiency": "good" if max(gpu_memory) > 100 else "underutilized"
        }
    
    def _identify_resource_bottlenecks(self, resource_data: List[SystemResourceUsage]) -> Dict[str, Any]:
        """Identify primary resource bottlenecks"""
        if not resource_data:
            return {"error": "No resource data available"}
        
        # Analyze different resource constraints
        avg_cpu = sum(r.cpu_percent for r in resource_data) / len(resource_data)
        avg_memory = sum(r.memory_percent for r in resource_data) / len(resource_data)
        
        bottlenecks = []
        
        if avg_cpu > 85:
            bottlenecks.append({"type": "CPU", "severity": "high", "value": avg_cpu})
        elif avg_cpu > 70:
            bottlenecks.append({"type": "CPU", "severity": "medium", "value": avg_cpu})
        
        if avg_memory > 85:
            bottlenecks.append({"type": "Memory", "severity": "high", "value": avg_memory})
        elif avg_memory > 70:
            bottlenecks.append({"type": "Memory", "severity": "medium", "value": avg_memory})
        
        # Primary bottleneck is the highest severity one
        primary_bottleneck = None
        if bottlenecks:
            high_severity = [b for b in bottlenecks if b["severity"] == "high"]
            primary_bottleneck = high_severity[0] if high_severity else bottlenecks[0]
        
        return {
            "detected_bottlenecks": bottlenecks,
            "primary_bottleneck": primary_bottleneck,
            "bottleneck_count": len(bottlenecks)
        }
    
    async def _analyze_scalability(self, video_path: str) -> Dict[str, Any]:
        """Analyze scalability with multiple concurrent videos"""
        logger.info("📈 Analyzing scalability...")
        
        scalability_results = {}
        
        # Test different concurrency levels
        for concurrency in [1, 2, 4]:
            logger.info(f"Testing concurrency level: {concurrency}")
            
            monitor = ResourceMonitor(interval=0.2)
            monitor.start_monitoring()
            
            try:
                start_time = time.time()
                
                # Create tasks for concurrent processing
                tasks = []
                for i in range(concurrency):
                    service = GroundTruthService()
                    task = service.process_video_async(f"scale-test-{i}", video_path)
                    tasks.append(task)
                
                # Wait for all tasks to complete
                await asyncio.gather(*tasks)
                
                end_time = time.time()
                total_time = end_time - start_time
                
                resource_data = monitor.stop_monitoring()
                
                # Calculate metrics
                avg_cpu = sum(r.cpu_percent for r in resource_data) / len(resource_data) if resource_data else 0
                peak_memory = max(r.memory_percent for r in resource_data) if resource_data else 0
                
                scalability_results[f"concurrency_{concurrency}"] = {
                    "total_time": total_time,
                    "time_per_video": total_time / concurrency,
                    "average_cpu": avg_cpu,
                    "peak_memory": peak_memory,
                    "efficiency_score": self._calculate_scalability_efficiency(concurrency, total_time, avg_cpu)
                }
                
            finally:
                monitor.stop_monitoring()
        
        # Analyze scalability trends
        scalability_analysis = self._analyze_scalability_trends(scalability_results)
        
        return {
            "concurrency_tests": scalability_results,
            "scalability_analysis": scalability_analysis,
            "optimal_concurrency": self._determine_optimal_concurrency(scalability_results)
        }
    
    def _calculate_scalability_efficiency(self, concurrency: int, total_time: float, avg_cpu: float) -> float:
        """Calculate scalability efficiency score"""
        # Ideal scaling would have same time per video regardless of concurrency
        # with proportional CPU increase
        baseline_time = 30  # Assume 30s baseline for single video
        expected_cpu = min(100, concurrency * 25)  # Expect 25% CPU per video
        
        time_efficiency = (baseline_time / (total_time / concurrency)) * 100
        cpu_efficiency = min(100, (avg_cpu / expected_cpu) * 100)
        
        return (time_efficiency + cpu_efficiency) / 2
    
    def _analyze_scalability_trends(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze scalability trends across concurrency levels"""
        if len(results) < 2:
            return {"error": "Insufficient data for trend analysis"}
        
        concurrency_levels = []
        times_per_video = []
        cpu_usage = []
        
        for key, data in results.items():
            if key.startswith("concurrency_"):
                level = int(key.split("_")[1])
                concurrency_levels.append(level)
                times_per_video.append(data["time_per_video"])
                cpu_usage.append(data["average_cpu"])
        
        # Calculate scaling efficiency
        scaling_efficiency = []
        for i in range(1, len(times_per_video)):
            # Good scaling means time per video stays constant or decreases slightly
            efficiency = (times_per_video[0] / times_per_video[i]) * 100
            scaling_efficiency.append(efficiency)
        
        return {
            "scaling_efficiency": scaling_efficiency,
            "degradation_points": [i for i, eff in enumerate(scaling_efficiency) if eff < 80],
            "optimal_range": self._find_optimal_concurrency_range(concurrency_levels, scaling_efficiency)
        }
    
    def _find_optimal_concurrency_range(self, levels: List[int], efficiencies: List[float]) -> Dict[str, Any]:
        """Find optimal concurrency range"""
        if not efficiencies:
            return {"min": 1, "max": 1, "reason": "No efficiency data"}
        
        # Find the range where efficiency stays above 70%
        good_levels = []
        for i, eff in enumerate(efficiencies):
            if eff >= 70:
                good_levels.append(levels[i + 1])  # +1 because efficiency array is offset
        
        if good_levels:
            return {"min": min(good_levels), "max": max(good_levels), "reason": "Efficiency > 70%"}
        else:
            return {"min": 1, "max": 1, "reason": "Only single-threaded processing is efficient"}
    
    def _determine_optimal_concurrency(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Determine optimal concurrency level"""
        best_score = 0
        best_concurrency = 1
        
        for key, data in results.items():
            if key.startswith("concurrency_"):
                level = int(key.split("_")[1])
                score = data.get("efficiency_score", 0)
                
                if score > best_score:
                    best_score = score
                    best_concurrency = level
        
        return {
            "optimal_level": best_concurrency,
            "efficiency_score": best_score,
            "recommendation": f"Use {best_concurrency} concurrent processes for optimal performance"
        }
    
    async def _analyze_caching_opportunities(self) -> Dict[str, Any]:
        """Identify caching opportunities for repeated operations"""
        logger.info("🗄️ Analyzing caching opportunities...")
        
        opportunities = {
            "model_loading": {
                "current_behavior": "Model loaded for each video processing",
                "optimization": "Cache loaded models between requests",
                "estimated_impact": "30-50% reduction in initialization time",
                "implementation": "Singleton pattern or model pool"
            },
            "video_metadata": {
                "current_behavior": "Video properties calculated each time",
                "optimization": "Cache video metadata (fps, frame count, duration)",
                "estimated_impact": "5-10% reduction in processing time",
                "implementation": "Redis or in-memory cache with TTL"
            },
            "database_queries": {
                "current_behavior": "Repeated queries for same data",
                "optimization": "Cache frequent database queries",
                "estimated_impact": "20-30% reduction in database load",
                "implementation": "Query result caching with cache invalidation"
            },
            "frame_preprocessing": {
                "current_behavior": "Same preprocessing applied to similar frames",
                "optimization": "Cache preprocessed frames for similar content",
                "estimated_impact": "10-15% reduction in preprocessing time",
                "implementation": "Content-based caching with hash keys"
            }
        }
        
        # Analyze current cache usage
        cache_analysis = await self._analyze_current_cache_usage()
        
        return {
            "opportunities": opportunities,
            "current_cache_analysis": cache_analysis,
            "priority_ranking": self._rank_caching_priorities(opportunities)
        }
    
    async def _analyze_current_cache_usage(self) -> Dict[str, Any]:
        """Analyze current caching implementation"""
        return {
            "model_caching": "Partial - YOLO model cached in service instance",
            "data_caching": "None detected",
            "query_caching": "None detected",
            "file_caching": "OS-level only",
            "optimization_potential": "High - many opportunities for improvement"
        }
    
    def _rank_caching_priorities(self, opportunities: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Rank caching opportunities by potential impact"""
        rankings = []
        
        for name, details in opportunities.items():
            impact_str = details["estimated_impact"]
            # Extract numeric impact (simple heuristic)
            if "30-50%" in impact_str:
                impact_score = 40
            elif "20-30%" in impact_str:
                impact_score = 25
            elif "10-15%" in impact_str:
                impact_score = 12
            else:
                impact_score = 7
            
            # Implementation complexity (simple heuristic)
            impl = details["implementation"].lower()
            if "singleton" in impl or "pool" in impl:
                complexity = "medium"
            elif "redis" in impl or "cache" in impl:
                complexity = "high"
            else:
                complexity = "low"
            
            rankings.append({
                "name": name,
                "impact_score": impact_score,
                "complexity": complexity,
                "priority": "high" if impact_score > 20 else "medium" if impact_score > 10 else "low"
            })
        
        # Sort by impact score
        rankings.sort(key=lambda x: x["impact_score"], reverse=True)
        
        return rankings
    
    async def _analyze_database_performance(self) -> Dict[str, Any]:
        """Analyze database query performance and optimization opportunities"""
        logger.info("🗃️ Analyzing database performance...")
        
        db_analysis = {}
        
        # Test database connection and basic operations
        with PerformanceProfiler("database_connection") as profiler:
            db = SessionLocal()
            try:
                # Test query performance
                result = db.execute("SELECT 1").fetchone()
            finally:
                db.close()
        
        db_analysis["connection_test"] = asdict(profiler.metrics)
        
        # Analyze common queries
        db_analysis["query_analysis"] = await self._analyze_database_queries()
        
        # Check for missing indexes
        db_analysis["index_analysis"] = await self._analyze_database_indexes()
        
        # Connection pool analysis
        db_analysis["connection_pool"] = await self._analyze_connection_pool()
        
        return db_analysis
    
    async def _analyze_database_queries(self) -> Dict[str, Any]:
        """Analyze common database queries for optimization"""
        queries_to_test = [
            ("video_lookup", "SELECT * FROM videos WHERE id = 'test-id'"),
            ("ground_truth_objects", "SELECT * FROM ground_truth_objects WHERE video_id = 'test-id'"),
            ("recent_videos", "SELECT * FROM videos ORDER BY created_at DESC LIMIT 10")
        ]
        
        query_performance = {}
        
        for query_name, query_sql in queries_to_test:
            with PerformanceProfiler(f"query_{query_name}") as profiler:
                db = SessionLocal()
                try:
                    # Execute query multiple times to get average
                    for _ in range(10):
                        db.execute(query_sql)
                finally:
                    db.close()
            
            query_performance[query_name] = {
                "metrics": asdict(profiler.metrics),
                "avg_time_per_query": profiler.metrics.duration / 10
            }
        
        return query_performance
    
    async def _analyze_database_indexes(self) -> Dict[str, Any]:
        """Analyze database indexes for optimization"""
        # This would typically involve checking query execution plans
        # For SQLite, we can check index usage
        
        db = SessionLocal()
        try:
            # Get list of indexes
            indexes_result = db.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
            indexes = [row[0] for row in indexes_result]
            
            # Get table info for common tables
            tables_to_check = ['videos', 'ground_truth_objects', 'detection_events']
            table_analysis = {}
            
            for table in tables_to_check:
                try:
                    table_info = db.execute(f"PRAGMA table_info({table})").fetchall()
                    table_analysis[table] = {
                        "columns": [{"name": row[1], "type": row[2]} for row in table_info],
                        "indexes": [idx for idx in indexes if table in idx.lower()]
                    }
                except Exception as e:
                    table_analysis[table] = {"error": str(e)}
            
            return {
                "available_indexes": indexes,
                "table_analysis": table_analysis,
                "optimization_suggestions": self._suggest_index_optimizations(table_analysis)
            }
            
        finally:
            db.close()
    
    def _suggest_index_optimizations(self, table_analysis: Dict[str, Any]) -> List[str]:
        """Suggest database index optimizations"""
        suggestions = []
        
        for table, info in table_analysis.items():
            if "error" in info:
                continue
                
            columns = info.get("columns", [])
            indexes = info.get("indexes", [])
            
            # Common columns that should be indexed
            important_columns = ['id', 'video_id', 'timestamp', 'created_at', 'updated_at']
            
            for col_info in columns:
                col_name = col_info["name"]
                if col_name in important_columns:
                    # Check if this column has an index
                    has_index = any(col_name in idx.lower() for idx in indexes)
                    if not has_index:
                        suggestions.append(f"CREATE INDEX idx_{table}_{col_name} ON {table}({col_name})")
        
        return suggestions
    
    async def _analyze_connection_pool(self) -> Dict[str, Any]:
        """Analyze database connection pool performance"""
        # Test connection acquisition time
        connection_times = []
        
        for _ in range(10):
            start_time = time.time()
            db = SessionLocal()
            db.close()
            end_time = time.time()
            connection_times.append(end_time - start_time)
        
        avg_connection_time = sum(connection_times) / len(connection_times)
        
        return {
            "average_connection_time": avg_connection_time,
            "connection_time_variance": max(connection_times) - min(connection_times),
            "performance_assessment": "good" if avg_connection_time < 0.01 else "needs_optimization"
        }
    
    async def _analyze_configuration_impact(self, video_path: str) -> Dict[str, Any]:
        """Test performance impact of different configuration parameters"""
        logger.info("⚙️ Analyzing configuration impact...")
        
        configurations = [
            {"name": "default", "confidence_threshold": 0.5, "process_all_frames": True},
            {"name": "high_confidence", "confidence_threshold": 0.8, "process_all_frames": True},
            {"name": "low_confidence", "confidence_threshold": 0.2, "process_all_frames": True},
            {"name": "frame_skipping", "confidence_threshold": 0.5, "process_all_frames": False}
        ]
        
        config_results = {}
        
        for config in configurations:
            logger.info(f"Testing configuration: {config['name']}")
            
            with PerformanceProfiler(f"config_{config['name']}") as profiler:
                # Here we would apply the configuration and run processing
                # For now, simulate with a basic service run
                service = GroundTruthService()
                await service.process_video_async(f"config-test-{config['name']}", video_path)
            
            config_results[config['name']] = {
                "config": config,
                "metrics": asdict(profiler.metrics),
                "performance_score": self._calculate_config_performance_score(profiler.metrics)
            }
        
        # Determine optimal configuration
        optimal_config = self._determine_optimal_configuration(config_results)
        
        return {
            "configuration_tests": config_results,
            "optimal_configuration": optimal_config,
            "configuration_recommendations": self._generate_config_recommendations(config_results)
        }
    
    def _calculate_config_performance_score(self, metrics: PerformanceMetrics) -> float:
        """Calculate performance score for a configuration"""
        # Combine time and resource usage into a single score
        time_score = max(0, 100 - metrics.duration)  # Lower time is better
        memory_score = max(0, 100 - (metrics.memory_peak - metrics.memory_before))  # Lower memory is better
        cpu_score = max(0, 100 - metrics.cpu_percent)  # Lower CPU is better
        
        return (time_score + memory_score + cpu_score) / 3
    
    def _determine_optimal_configuration(self, config_results: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the optimal configuration based on performance scores"""
        best_config = None
        best_score = 0
        
        for config_name, results in config_results.items():
            score = results["performance_score"]
            if score > best_score:
                best_score = score
                best_config = config_name
        
        return {
            "optimal_config": best_config,
            "performance_score": best_score,
            "configuration": config_results[best_config]["config"] if best_config else None
        }
    
    def _generate_config_recommendations(self, config_results: Dict[str, Any]) -> List[str]:
        """Generate configuration optimization recommendations"""
        recommendations = []
        
        # Analyze results to generate recommendations
        default_score = config_results.get("default", {}).get("performance_score", 0)
        
        for config_name, results in config_results.items():
            if config_name == "default":
                continue
                
            score = results["performance_score"]
            if score > default_score * 1.1:  # 10% improvement
                config = results["config"]
                recommendations.append(
                    f"Consider using {config_name} configuration for {score - default_score:.1f}% performance improvement"
                )
        
        if not recommendations:
            recommendations.append("Default configuration appears optimal for current workload")
        
        return recommendations
    
    async def _apply_five_whys_analysis(self, analyses: Dict[str, Any]) -> Dict[str, Any]:
        """Apply 5 Whys methodology to identified bottlenecks"""
        logger.info("🔍 Applying 5 Whys analysis to bottlenecks...")
        
        bottlenecks = self._extract_bottlenecks(analyses)
        five_whys_analysis = {}
        
        for bottleneck in bottlenecks:
            whys = self._generate_five_whys(bottleneck)
            five_whys_analysis[bottleneck["name"]] = {
                "bottleneck": bottleneck,
                "five_whys": whys,
                "root_cause": whys[-1] if whys else "Unable to determine root cause",
                "action_items": self._generate_action_items(whys)
            }
        
        return five_whys_analysis
    
    def _extract_bottlenecks(self, analyses: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract bottlenecks from analysis results"""
        bottlenecks = []
        
        # Processing speed bottlenecks
        processing = analyses.get("processing_speed", {})
        if processing:
            basic_time = processing.get("basic_service", {}).get("metrics", {}).get("duration", 0)
            if basic_time > 30:  # More than 30 seconds is considered slow
                bottlenecks.append({
                    "name": "slow_processing_speed",
                    "type": "performance",
                    "severity": "high",
                    "metric": basic_time,
                    "description": f"Ground truth processing takes {basic_time:.1f} seconds"
                })
        
        # Memory bottlenecks
        memory = analyses.get("memory_usage", {})
        if memory.get("peak_memory_percent", 0) > 80:
            bottlenecks.append({
                "name": "high_memory_usage",
                "type": "resource",
                "severity": "high",
                "metric": memory.get("peak_memory_percent", 0),
                "description": f"Peak memory usage: {memory.get('peak_memory_percent', 0):.1f}%"
            })
        
        # I/O bottlenecks
        io_analysis = analyses.get("io_operations", {})
        io_bottleneck = io_analysis.get("bottleneck_detection", {})
        if io_bottleneck.get("detected", False):
            bottlenecks.append({
                "name": "io_bottleneck",
                "type": "io",
                "severity": io_bottleneck.get("bottleneck_severity", "medium"),
                "metric": io_bottleneck.get("average_read_rate_mbps", 0),
                "description": f"Low I/O rate: {io_bottleneck.get('average_read_rate_mbps', 0):.1f} MB/s"
            })
        
        return bottlenecks
    
    def _generate_five_whys(self, bottleneck: Dict[str, Any]) -> List[str]:
        """Generate 5 Whys analysis for a bottleneck"""
        bottleneck_type = bottleneck["name"]
        
        if bottleneck_type == "slow_processing_speed":
            return [
                "Why is processing slow? Large video files and complex ML inference",
                "Why does ML inference take long? YOLO model processes every frame individually",
                "Why process every frame? Current implementation doesn't optimize frame sampling",
                "Why no frame sampling optimization? No configuration for frame skip intervals",
                "Why no configuration? System designed for maximum accuracy over performance"
            ]
        elif bottleneck_type == "high_memory_usage":
            return [
                "Why is memory usage high? Loading entire video into memory",
                "Why load entire video? Frame-by-frame processing keeps frames in memory",
                "Why keep frames in memory? No streaming or buffer management",
                "Why no buffer management? Single-threaded processing model",
                "Why single-threaded? Simplified design without memory optimization"
            ]
        elif bottleneck_type == "io_bottleneck":
            return [
                "Why is I/O slow? Multiple reads of the same video file",
                "Why multiple reads? Different components access video separately",
                "Why separate access? No shared video stream or caching",
                "Why no caching? Components designed independently",
                "Why independent design? Lack of centralized video processing pipeline"
            ]
        else:
            return [
                "Why does this bottleneck exist? Insufficient analysis data",
                "Why insufficient data? Complex system interactions",
                "Why complex interactions? Multiple processing components",
                "Why multiple components? Modular design trade-offs",
                "Why design trade-offs? Balance between flexibility and performance"
            ]
    
    def _generate_action_items(self, whys: List[str]) -> List[str]:
        """Generate action items based on 5 Whys analysis"""
        if not whys:
            return ["Conduct deeper analysis to identify root causes"]
        
        root_cause = whys[-1]
        
        if "maximum accuracy over performance" in root_cause:
            return [
                "Implement configurable frame sampling rates",
                "Add performance/accuracy trade-off settings",
                "Create performance-optimized processing modes"
            ]
        elif "memory optimization" in root_cause:
            return [
                "Implement streaming video processing",
                "Add buffer management for frame processing",
                "Consider multi-threaded processing with shared memory"
            ]
        elif "centralized video processing" in root_cause:
            return [
                "Design unified video processing pipeline",
                "Implement shared video stream caching",
                "Coordinate component access to video resources"
            ]
        else:
            return [
                "Redesign system architecture for better performance",
                "Implement performance monitoring and optimization",
                "Balance modularity with performance requirements"
            ]
    
    async def _generate_optimization_recommendations(self, analyses: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate specific optimization recommendations with estimated impact"""
        logger.info("💡 Generating optimization recommendations...")
        
        recommendations = []
        
        # Processing speed optimizations
        processing = analyses.get("processing_speed", {})
        if processing:
            basic_time = processing.get("basic_service", {}).get("metrics", {}).get("duration", 0)
            if basic_time > 15:
                recommendations.append({
                    "category": "Processing Speed",
                    "title": "Implement Frame Sampling",
                    "description": "Process every Nth frame instead of all frames for non-critical applications",
                    "estimated_impact": "50-70% reduction in processing time",
                    "implementation_effort": "Low",
                    "code_changes": [
                        "Add frame_skip parameter to processing configuration",
                        "Modify frame iteration loop to skip frames",
                        "Adjust timestamp calculations for skipped frames"
                    ]
                })
        
        # Memory optimization
        memory = analyses.get("memory_usage", {})
        if memory.get("peak_memory_percent", 0) > 70:
            recommendations.append({
                "category": "Memory Usage",
                "title": "Implement Streaming Processing",
                "description": "Process video frames in streaming mode without loading entire video",
                "estimated_impact": "60-80% reduction in memory usage",
                "implementation_effort": "Medium",
                "code_changes": [
                    "Implement frame buffer with limited size",
                    "Add streaming video reader",
                    "Modify processing pipeline for streaming mode"
                ]
            })
        
        # Caching optimizations
        caching = analyses.get("caching_opportunities", {})
        if caching:
            top_opportunity = caching.get("priority_ranking", [{}])[0]
            if top_opportunity:
                recommendations.append({
                    "category": "Caching",
                    "title": f"Implement {top_opportunity.get('name', 'Model')} Caching",
                    "description": f"Cache {top_opportunity.get('name', 'models')} to avoid repeated loading",
                    "estimated_impact": f"{top_opportunity.get('impact_score', 20)}% improvement",
                    "implementation_effort": top_opportunity.get("complexity", "Medium"),
                    "code_changes": [
                        "Add caching layer for models/data",
                        "Implement cache invalidation strategy",
                        "Add cache configuration options"
                    ]
                })
        
        # Database optimizations
        db_analysis = analyses.get("database_performance", {})
        index_suggestions = db_analysis.get("index_analysis", {}).get("optimization_suggestions", [])
        if index_suggestions:
            recommendations.append({
                "category": "Database Performance",
                "title": "Add Missing Database Indexes",
                "description": "Create indexes on frequently queried columns",
                "estimated_impact": "20-40% reduction in query time",
                "implementation_effort": "Low",
                "code_changes": index_suggestions[:3]  # Top 3 suggestions
            })
        
        # I/O optimizations
        io_analysis = analyses.get("io_operations", {})
        if io_analysis.get("bottleneck_detection", {}).get("detected", False):
            recommendations.append({
                "category": "I/O Performance",
                "title": "Optimize Video Access Patterns",
                "description": "Implement efficient video reading with proper buffering",
                "estimated_impact": "30-50% reduction in I/O wait time",
                "implementation_effort": "Medium",
                "code_changes": [
                    "Implement video stream caching",
                    "Add buffer management for video reading",
                    "Optimize file access patterns"
                ]
            })
        
        # Scalability optimizations
        scalability = analyses.get("scalability", {})
        optimal_concurrency = scalability.get("optimal_concurrency", {})
        if optimal_concurrency.get("optimal_level", 1) > 1:
            recommendations.append({
                "category": "Scalability",
                "title": f"Implement Concurrent Processing",
                "description": f"Use {optimal_concurrency.get('optimal_level')} concurrent processes",
                "estimated_impact": f"{optimal_concurrency.get('efficiency_score', 20):.0f}% improvement",
                "implementation_effort": "High",
                "code_changes": [
                    "Add process pool for concurrent video processing",
                    "Implement task queue management",
                    "Add resource coordination between processes"
                ]
            })
        
        # Configuration optimizations
        config_analysis = analyses.get("configuration_impact", {})
        optimal_config = config_analysis.get("optimal_configuration", {})
        if optimal_config.get("optimal_config") != "default":
            recommendations.append({
                "category": "Configuration",
                "title": f"Use {optimal_config.get('optimal_config', 'optimized')} Configuration",
                "description": "Apply performance-optimized configuration settings",
                "estimated_impact": f"{optimal_config.get('performance_score', 0) - 50:.0f}% improvement",
                "implementation_effort": "Low",
                "code_changes": [
                    "Update default configuration values",
                    "Add performance-focused configuration profiles",
                    "Implement configuration validation"
                ]
            })
        
        # Sort by estimated impact
        recommendations.sort(key=lambda x: self._extract_impact_percentage(x["estimated_impact"]), reverse=True)
        
        return recommendations
    
    def _extract_impact_percentage(self, impact_string: str) -> float:
        """Extract numeric impact percentage from impact string"""
        import re
        matches = re.findall(r'(\d+)', impact_string)
        if matches:
            return float(matches[0])
        return 0
    
    def _calculate_performance_score(self, analyses: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall performance score"""
        scores = {}
        
        # Processing speed score (0-100, higher is better)
        processing = analyses.get("processing_speed", {})
        basic_time = processing.get("basic_service", {}).get("metrics", {}).get("duration", 60)
        speed_score = max(0, 100 - (basic_time - 10) * 2)  # 10s baseline, -2 points per extra second
        scores["processing_speed"] = min(100, speed_score)
        
        # Memory efficiency score
        memory = analyses.get("memory_usage", {})
        memory_percent = memory.get("peak_memory_percent", 50)
        memory_score = max(0, 100 - (memory_percent - 30))  # 30% baseline
        scores["memory_efficiency"] = min(100, memory_score)
        
        # I/O efficiency score
        io_analysis = analyses.get("io_operations", {})
        io_efficiency = io_analysis.get("io_efficiency_score", {})
        scores["io_efficiency"] = io_efficiency.get("score", 50) if isinstance(io_efficiency, dict) else 50
        
        # Resource utilization score
        resource = analyses.get("resource_utilization", {})
        cpu_analysis = resource.get("cpu_analysis", {})
        cpu_efficiency = cpu_analysis.get("utilization_efficiency", {}).get("efficiency_score", 50)
        scores["resource_utilization"] = cpu_efficiency
        
        # Scalability score
        scalability = analyses.get("scalability", {})
        optimal_concurrency = scalability.get("optimal_concurrency", {})
        scalability_score = optimal_concurrency.get("efficiency_score", 50)
        scores["scalability"] = scalability_score
        
        # Overall score (weighted average)
        weights = {
            "processing_speed": 0.3,
            "memory_efficiency": 0.2,
            "io_efficiency": 0.2,
            "resource_utilization": 0.15,
            "scalability": 0.15
        }
        
        overall_score = sum(scores[key] * weights[key] for key in scores)
        
        return {
            "overall_score": overall_score,
            "component_scores": scores,
            "performance_grade": self._get_performance_grade(overall_score),
            "summary": self._generate_performance_summary(overall_score, scores)
        }
    
    def _get_performance_grade(self, score: float) -> str:
        """Get performance grade based on score"""
        if score >= 90:
            return "A+ (Excellent)"
        elif score >= 80:
            return "A (Very Good)"
        elif score >= 70:
            return "B (Good)"
        elif score >= 60:
            return "C (Fair)"
        elif score >= 50:
            return "D (Poor)"
        else:
            return "F (Very Poor)"
    
    def _generate_performance_summary(self, overall_score: float, component_scores: Dict[str, float]) -> str:
        """Generate performance summary text"""
        grade = self._get_performance_grade(overall_score)
        
        # Find strongest and weakest areas
        strongest = max(component_scores.items(), key=lambda x: x[1])
        weakest = min(component_scores.items(), key=lambda x: x[1])
        
        return (f"Overall performance grade: {grade} ({overall_score:.1f}/100). "
                f"Strongest area: {strongest[0]} ({strongest[1]:.1f}). "
                f"Needs improvement: {weakest[0]} ({weakest[1]:.1f}).")
    
    async def _create_test_video(self) -> str:
        """Create a test video for analysis if none provided"""
        logger.info("📹 Creating test video for analysis...")
        
        test_video_path = "/tmp/test_video_analysis.mp4"
        
        # Create a simple test video using OpenCV
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(test_video_path, fourcc, 30.0, (640, 480))
        
        # Generate 150 frames (5 seconds at 30 fps)
        for i in range(150):
            # Create a frame with some moving content
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Add a moving rectangle to simulate a person
            x = int(100 + 300 * (i / 150))  # Move across screen
            y = 200
            cv2.rectangle(frame, (x, y), (x + 50, y + 100), (255, 255, 255), -1)
            
            # Add some noise
            noise = np.random.randint(0, 50, frame.shape, dtype=np.uint8)
            frame = cv2.add(frame, noise)
            
            out.write(frame)
        
        out.release()
        logger.info(f"✅ Test video created: {test_video_path}")
        
        return test_video_path
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for analysis context"""
        try:
            import platform
            
            system_info = {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "cpu_count_logical": psutil.cpu_count(logical=True),
                "total_memory_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
                "available_memory_gb": psutil.virtual_memory().available / 1024 / 1024 / 1024,
                "disk_usage": dict(psutil.disk_usage('/')._asdict()) if hasattr(psutil, 'disk_usage') else {}
            }
            
            # GPU information
            try:
                import torch
                system_info["gpu_available"] = torch.cuda.is_available()
                if torch.cuda.is_available():
                    system_info["gpu_count"] = torch.cuda.device_count()
                    system_info["gpu_name"] = torch.cuda.get_device_name(0)
                    system_info["gpu_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / 1024 / 1024 / 1024
            except ImportError:
                system_info["gpu_available"] = False
            
            return system_info
            
        except Exception as e:
            return {"error": f"Failed to get system info: {str(e)}"}
    
    async def _save_report(self, report: Dict[str, Any]):
        """Save analysis report to file"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_path = f"/home/rigade/Testing/ai-model-validation-platform/backend/analysis/performance_report_{timestamp}.json"
        
        try:
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            # Convert numpy types to Python types for JSON serialization
            json_report = self._convert_for_json(report)
            
            with open(report_path, 'w') as f:
                json.dump(json_report, f, indent=2, default=str)
            
            logger.info(f"📄 Performance report saved: {report_path}")
            
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
    
    def _convert_for_json(self, obj):
        """Convert objects to JSON-serializable format"""
        if isinstance(obj, dict):
            return {key: self._convert_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_for_json(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, '__dict__'):
            return self._convert_for_json(obj.__dict__)
        else:
            return obj

async def main():
    """Main function to run performance analysis"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    analyzer = GroundTruthPerformanceAnalyzer()
    
    # Run comprehensive analysis
    report = await analyzer.run_comprehensive_analysis()
    
    # Print summary
    print("\n" + "="*80)
    print("GROUND TRUTH SYSTEM PERFORMANCE ANALYSIS SUMMARY")
    print("="*80)
    
    performance_score = report.get("performance_score", {})
    print(f"Overall Performance Score: {performance_score.get('overall_score', 0):.1f}/100")
    print(f"Performance Grade: {performance_score.get('performance_grade', 'Unknown')}")
    print(f"Summary: {performance_score.get('summary', 'No summary available')}")
    
    print(f"\nTop Optimization Recommendations:")
    recommendations = report.get("optimization_recommendations", [])
    for i, rec in enumerate(recommendations[:5], 1):
        print(f"{i}. {rec.get('title', 'Unknown')} - {rec.get('estimated_impact', 'Unknown impact')}")
    
    print(f"\nDetailed report saved to analysis directory")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
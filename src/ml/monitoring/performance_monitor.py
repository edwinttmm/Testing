"""
Performance monitoring for ML pipeline
"""
import asyncio
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import psutil
import threading
import json
from pathlib import Path

try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    
from ..config import ml_config

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    timestamp: float
    inference_time_ms: float
    detections_count: int
    cpu_percent: float
    memory_mb: float
    gpu_percent: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    fps: Optional[float] = None

@dataclass
class SystemInfo:
    """System information"""
    cpu_count: int
    total_memory_gb: float
    gpu_name: Optional[str] = None
    gpu_memory_gb: Optional[float] = None
    cuda_available: bool = False

class PerformanceMonitor:
    """Real-time performance monitoring for ML pipeline"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Performance counters
        self.total_inferences = 0
        self.total_detections = 0
        self.start_time = time.time()
        
        # FPS calculation
        self.frame_timestamps = deque(maxlen=30)  # Last 30 frames for FPS
        
        # System info
        self.system_info = self._get_system_info()
        
        # Threading lock for thread-safe operations
        self._lock = threading.Lock()
        
    def start_monitoring(self):
        """Start performance monitoring"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop performance monitoring"""
        if self.is_monitoring:
            self.is_monitoring = False
            if self.monitor_task:
                self.monitor_task.cancel()
                try:
                    await self.monitor_task
                except asyncio.CancelledError:
                    pass
            logger.info("Performance monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        try:
            while self.is_monitoring:
                await asyncio.sleep(ml_config.metrics_collection_interval)
                await self._collect_system_metrics()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Monitoring loop error: {str(e)}", exc_info=True)
    
    async def _collect_system_metrics(self):
        """Collect system performance metrics"""
        try:
            timestamp = time.time()
            
            # CPU and memory metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_info = psutil.virtual_memory()
            memory_mb = memory_info.used / (1024 * 1024)
            
            # GPU metrics (if available)
            gpu_percent = None
            gpu_memory_mb = None
            
            if GPU_AVAILABLE:
                try:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]  # Use first GPU
                        gpu_percent = gpu.load * 100
                        gpu_memory_mb = gpu.memoryUsed
                except Exception as e:
                    logger.debug(f"GPU metrics collection failed: {str(e)}")
            
            # Calculate current FPS
            current_fps = self._calculate_fps()
            
            # Create metrics entry
            metrics = PerformanceMetrics(
                timestamp=timestamp,
                inference_time_ms=0.0,  # Will be updated by record_inference
                detections_count=0,     # Will be updated by record_inference
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                gpu_percent=gpu_percent,
                gpu_memory_mb=gpu_memory_mb,
                fps=current_fps
            )
            
            with self._lock:
                self.metrics_history.append(metrics)
                
        except Exception as e:
            logger.error(f"System metrics collection failed: {str(e)}")
    
    async def record_inference(self, inference_time_ms: float, detections_count: int):
        """Record inference performance"""
        try:
            timestamp = time.time()
            
            with self._lock:
                self.total_inferences += 1
                self.total_detections += detections_count
                self.frame_timestamps.append(timestamp)
                
                # Update latest metrics with inference data
                if self.metrics_history:
                    latest_metrics = self.metrics_history[-1]
                    latest_metrics.inference_time_ms = inference_time_ms
                    latest_metrics.detections_count = detections_count
                    latest_metrics.fps = self._calculate_fps()
                
        except Exception as e:
            logger.error(f"Inference recording failed: {str(e)}")
    
    def _calculate_fps(self) -> Optional[float]:
        """Calculate current FPS based on recent frames"""
        try:
            if len(self.frame_timestamps) < 2:
                return None
            
            time_span = self.frame_timestamps[-1] - self.frame_timestamps[0]
            if time_span <= 0:
                return None
            
            fps = (len(self.frame_timestamps) - 1) / time_span
            return round(fps, 2)
            
        except Exception:
            return None
    
    def _get_system_info(self) -> SystemInfo:
        """Get system information"""
        try:
            cpu_count = psutil.cpu_count()
            total_memory_gb = psutil.virtual_memory().total / (1024 ** 3)
            
            gpu_name = None
            gpu_memory_gb = None
            cuda_available = False
            
            # Check CUDA availability
            try:
                import torch
                cuda_available = torch.cuda.is_available()
                
                if cuda_available and GPU_AVAILABLE:
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        gpu = gpus[0]
                        gpu_name = gpu.name
                        gpu_memory_gb = gpu.memoryTotal / 1024
            except Exception as e:
                logger.debug(f"GPU info collection failed: {str(e)}")
            
            return SystemInfo(
                cpu_count=cpu_count,
                total_memory_gb=round(total_memory_gb, 2),
                gpu_name=gpu_name,
                gpu_memory_gb=round(gpu_memory_gb, 2) if gpu_memory_gb else None,
                cuda_available=cuda_available
            )
            
        except Exception as e:
            logger.error(f"System info collection failed: {str(e)}")
            return SystemInfo(cpu_count=1, total_memory_gb=0.0)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        try:
            with self._lock:
                runtime_seconds = time.time() - self.start_time
                
                # Calculate averages from recent metrics
                recent_metrics = list(self.metrics_history)[-10:]  # Last 10 measurements
                
                if recent_metrics:
                    avg_inference_time = sum(m.inference_time_ms for m in recent_metrics if m.inference_time_ms > 0) / max(1, len([m for m in recent_metrics if m.inference_time_ms > 0]))
                    avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
                    avg_memory = sum(m.memory_mb for m in recent_metrics) / len(recent_metrics)
                    
                    # GPU averages
                    gpu_metrics = [m for m in recent_metrics if m.gpu_percent is not None]
                    avg_gpu = sum(m.gpu_percent for m in gpu_metrics) / len(gpu_metrics) if gpu_metrics else None
                    avg_gpu_memory = sum(m.gpu_memory_mb for m in gpu_metrics) / len(gpu_metrics) if gpu_metrics else None
                    
                    current_fps = recent_metrics[-1].fps if recent_metrics else None
                else:
                    avg_inference_time = 0.0
                    avg_cpu = 0.0
                    avg_memory = 0.0
                    avg_gpu = None
                    avg_gpu_memory = None
                    current_fps = None
                
                stats = {
                    "performance": {
                        "total_inferences": self.total_inferences,
                        "total_detections": self.total_detections,
                        "runtime_seconds": round(runtime_seconds, 2),
                        "average_inference_time_ms": round(avg_inference_time, 2),
                        "current_fps": current_fps,
                        "detections_per_second": round(self.total_detections / max(runtime_seconds, 1), 2),
                        "target_latency_met": avg_inference_time <= ml_config.max_inference_time_ms if avg_inference_time > 0 else True
                    },
                    "system": {
                        "cpu_percent": round(avg_cpu, 1),
                        "memory_mb": round(avg_memory, 1),
                        "gpu_percent": round(avg_gpu, 1) if avg_gpu is not None else None,
                        "gpu_memory_mb": round(avg_gpu_memory, 1) if avg_gpu_memory is not None else None
                    },
                    "hardware": {
                        "cpu_count": self.system_info.cpu_count,
                        "total_memory_gb": self.system_info.total_memory_gb,
                        "gpu_name": self.system_info.gpu_name,
                        "gpu_memory_gb": self.system_info.gpu_memory_gb,
                        "cuda_available": self.system_info.cuda_available
                    }
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"Stats calculation failed: {str(e)}")
            return {"error": "Failed to calculate stats"}
    
    def get_detailed_metrics(self, last_n: int = 100) -> List[Dict[str, Any]]:
        """Get detailed metrics history"""
        try:
            with self._lock:
                recent_metrics = list(self.metrics_history)[-last_n:]
                
                return [
                    {
                        "timestamp": m.timestamp,
                        "inference_time_ms": m.inference_time_ms,
                        "detections_count": m.detections_count,
                        "cpu_percent": m.cpu_percent,
                        "memory_mb": m.memory_mb,
                        "gpu_percent": m.gpu_percent,
                        "gpu_memory_mb": m.gpu_memory_mb,
                        "fps": m.fps
                    }
                    for m in recent_metrics
                ]
                
        except Exception as e:
            logger.error(f"Detailed metrics retrieval failed: {str(e)}")
            return []
    
    def detect_bottlenecks(self) -> Dict[str, Any]:
        """Detect performance bottlenecks"""
        try:
            stats = self.get_current_stats()
            bottlenecks = []
            recommendations = []
            
            performance = stats.get("performance", {})
            system = stats.get("system", {})
            hardware = stats.get("hardware", {})
            
            # Check inference time
            avg_inference_time = performance.get("average_inference_time_ms", 0)
            if avg_inference_time > ml_config.max_inference_time_ms:
                bottlenecks.append("Inference latency exceeds target")
                recommendations.append("Consider model optimization or hardware upgrade")
            
            # Check CPU usage
            cpu_percent = system.get("cpu_percent", 0)
            if cpu_percent > 90:
                bottlenecks.append("High CPU usage")
                recommendations.append("Reduce concurrent processing or upgrade CPU")
            
            # Check memory usage
            memory_mb = system.get("memory_mb", 0)
            total_memory_gb = hardware.get("total_memory_gb", 1)
            memory_usage_percent = (memory_mb / 1024) / total_memory_gb * 100
            
            if memory_usage_percent > 90:
                bottlenecks.append("High memory usage")
                recommendations.append("Reduce batch size or upgrade RAM")
            
            # Check GPU usage (if available)
            gpu_percent = system.get("gpu_percent")
            if gpu_percent is not None and gpu_percent > 95:
                bottlenecks.append("High GPU usage")
                recommendations.append("Reduce batch size or upgrade GPU")
            
            # Check FPS
            current_fps = performance.get("current_fps")
            if current_fps is not None and current_fps < 10:
                bottlenecks.append("Low frame processing rate")
                recommendations.append("Optimize inference pipeline or reduce input resolution")
            
            return {
                "bottlenecks": bottlenecks,
                "recommendations": recommendations,
                "severity": "high" if len(bottlenecks) > 2 else "medium" if bottlenecks else "low"
            }
            
        except Exception as e:
            logger.error(f"Bottleneck detection failed: {str(e)}")
            return {"bottlenecks": [], "recommendations": [], "severity": "unknown"}
    
    def export_metrics(self, filepath: str) -> bool:
        """Export metrics to JSON file"""
        try:
            with self._lock:
                data = {
                    "system_info": self.system_info.__dict__,
                    "current_stats": self.get_current_stats(),
                    "detailed_metrics": self.get_detailed_metrics(),
                    "export_timestamp": time.time()
                }
                
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                
                logger.info(f"Metrics exported to {filepath}")
                return True
                
        except Exception as e:
            logger.error(f"Metrics export failed: {str(e)}")
            return False
    
    def reset_metrics(self):
        """Reset all metrics"""
        with self._lock:
            self.metrics_history.clear()
            self.frame_timestamps.clear()
            self.total_inferences = 0
            self.total_detections = 0
            self.start_time = time.time()
        
        logger.info("Performance metrics reset")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()
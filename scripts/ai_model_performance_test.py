#!/usr/bin/env python3
"""
AI Model Performance Testing Suite
Tests inference speed, resource utilization, and model optimization opportunities
"""

import time
import psutil
import cv2
import numpy as np
import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import threading
import statistics

@dataclass 
class ModelPerformanceMetric:
    model_name: str
    operation: str
    latency_ms: float
    throughput_fps: float
    memory_usage_mb: float
    cpu_percent: float
    gpu_utilization: float = 0.0
    accuracy: float = 0.0
    model_size_mb: float = 0.0

class AIModelPerformanceTest:
    def __init__(self):
        self.metrics: List[ModelPerformanceMetric] = []
        self.test_results = {}
        
        # Check for AI/ML dependencies
        self.opencv_available = self._check_opencv()
        self.ultralytics_available = self._check_ultralytics()
        
    def _check_opencv(self) -> bool:
        """Check if OpenCV is available"""
        try:
            import cv2
            return True
        except ImportError:
            return False
            
    def _check_ultralytics(self) -> bool:
        """Check if Ultralytics YOLO is available"""
        try:
            from ultralytics import YOLO
            return True
        except ImportError:
            return False
    
    def create_test_data(self, width: int = 640, height: int = 480, count: int = 100) -> List[np.ndarray]:
        """Create synthetic test images for performance testing"""
        test_images = []
        for i in range(count):
            # Create random test image
            image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            
            # Add some synthetic objects (rectangles) to make it more realistic
            for _ in range(np.random.randint(1, 5)):
                x1, y1 = np.random.randint(0, width//2), np.random.randint(0, height//2)
                x2, y2 = x1 + np.random.randint(20, width//4), y1 + np.random.randint(20, height//4)
                color = tuple(np.random.randint(0, 255, 3).tolist())
                cv2.rectangle(image, (x1, y1), (x2, y2), color, -1)
            
            test_images.append(image)
        
        return test_images
    
    def test_opencv_performance(self):
        """Test OpenCV image processing performance"""
        print("\n=== OPENCV PERFORMANCE TESTING ===")
        
        if not self.opencv_available:
            print("OpenCV not available - skipping OpenCV tests")
            return
            
        test_images = self.create_test_data(count=50)
        
        operations = {
            'resize': lambda img: cv2.resize(img, (320, 240)),
            'blur': lambda img: cv2.GaussianBlur(img, (15, 15), 0),
            'edge_detection': lambda img: cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 50, 150),
            'color_conversion': lambda img: cv2.cvtColor(img, cv2.COLOR_BGR2HSV),
            'histogram_equalization': lambda img: cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)),
        }
        
        for op_name, operation in operations.items():
            print(f"\nTesting {op_name}...")
            
            # Memory before
            process = psutil.Process()
            mem_before = process.memory_info().rss / (1024*1024)
            
            start_time = time.time()
            cpu_times = []
            
            for i, image in enumerate(test_images):
                cpu_before = psutil.cpu_percent()
                
                try:
                    result = operation(image)
                    cpu_after = psutil.cpu_percent()
                    cpu_times.append(cpu_after - cpu_before if cpu_after > cpu_before else cpu_after)
                except Exception as e:
                    print(f"  Error in {op_name}: {e}")
                    continue
                    
            end_time = time.time()
            
            # Memory after
            mem_after = process.memory_info().rss / (1024*1024)
            
            total_time = end_time - start_time
            avg_latency = (total_time / len(test_images)) * 1000  # ms
            throughput = len(test_images) / total_time
            avg_cpu = statistics.mean(cpu_times) if cpu_times else 0
            memory_delta = mem_after - mem_before
            
            metric = ModelPerformanceMetric(
                model_name="OpenCV",
                operation=op_name,
                latency_ms=avg_latency,
                throughput_fps=throughput,
                memory_usage_mb=memory_delta,
                cpu_percent=avg_cpu
            )
            
            self.metrics.append(metric)
            
            print(f"  Latency: {avg_latency:.2f}ms per image")
            print(f"  Throughput: {throughput:.1f} images/sec")
            print(f"  Memory Delta: {memory_delta:.2f}MB")
            print(f"  Avg CPU: {avg_cpu:.1f}%")
    
    def test_yolo_performance(self):
        """Test YOLO model performance if available"""
        print("\n=== YOLO MODEL PERFORMANCE TESTING ===")
        
        if not self.ultralytics_available:
            print("Ultralytics YOLO not available - skipping YOLO tests")
            return
            
        try:
            from ultralytics import YOLO
            
            # Try to load YOLOv8n (nano) model - smallest and fastest
            print("Loading YOLOv8n model...")
            model = YOLO('yolov8n.pt')
            
            # Get model size
            model_path = 'yolov8n.pt'
            model_size = os.path.getsize(model_path) / (1024*1024) if os.path.exists(model_path) else 0
            
            # Create test data
            test_images = self.create_test_data(width=640, height=640, count=20)
            
            print(f"Testing YOLO inference on {len(test_images)} images...")
            
            # Warm up the model
            _ = model(test_images[0])
            
            # Performance test
            process = psutil.Process()
            mem_before = process.memory_info().rss / (1024*1024)
            
            latencies = []
            start_time = time.time()
            
            for i, image in enumerate(test_images):
                inference_start = time.time()
                cpu_before = psutil.cpu_percent()
                
                # Run inference
                results = model(image, verbose=False)
                
                inference_end = time.time()
                latency = (inference_end - inference_start) * 1000
                latencies.append(latency)
                
                if i % 5 == 0:
                    print(f"  Processed {i+1}/{len(test_images)} images...")
            
            total_time = time.time() - start_time
            mem_after = process.memory_info().rss / (1024*1024)
            
            avg_latency = statistics.mean(latencies)
            p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 1 else avg_latency
            throughput = len(test_images) / total_time
            memory_delta = mem_after - mem_before
            
            metric = ModelPerformanceMetric(
                model_name="YOLOv8n",
                operation="object_detection",
                latency_ms=avg_latency,
                throughput_fps=throughput,
                memory_usage_mb=memory_delta,
                cpu_percent=psutil.cpu_percent(),
                model_size_mb=model_size
            )
            
            self.metrics.append(metric)
            
            print(f"\nYOLO Performance Results:")
            print(f"  Model Size: {model_size:.1f}MB")
            print(f"  Avg Latency: {avg_latency:.2f}ms")
            print(f"  P95 Latency: {p95_latency:.2f}ms")
            print(f"  Throughput: {throughput:.1f} FPS")
            print(f"  Memory Delta: {memory_delta:.2f}MB")
            
        except Exception as e:
            print(f"YOLO testing failed: {e}")
            print("This is expected if YOLOv8 model files are not available")
    
    def test_video_processing_performance(self):
        """Test video processing pipeline performance"""
        print("\n=== VIDEO PROCESSING PERFORMANCE ===")
        
        if not self.opencv_available:
            print("OpenCV not available - skipping video processing tests")
            return
            
        # Create synthetic video data
        frame_count = 100
        width, height = 640, 480
        fps = 30
        
        print(f"Testing video processing pipeline ({frame_count} frames @ {width}x{height})")
        
        # Simulate video processing pipeline
        process = psutil.Process()
        mem_before = process.memory_info().rss / (1024*1024)
        
        start_time = time.time()
        processed_frames = 0
        
        for frame_idx in range(frame_count):
            # Generate synthetic frame
            frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            
            # Typical video processing operations
            # 1. Resize for processing
            small_frame = cv2.resize(frame, (320, 240))
            
            # 2. Color space conversion
            hsv_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2HSV)
            
            # 3. Background subtraction simulation
            gray_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
            blurred_frame = cv2.GaussianBlur(gray_frame, (21, 21), 0)
            
            # 4. Motion detection simulation (frame differencing)
            if frame_idx > 0:
                frame_delta = cv2.absdiff(prev_frame, gray_frame)
                thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Simulate object tracking
                for contour in contours:
                    if cv2.contourArea(contour) > 500:
                        x, y, w, h = cv2.boundingRect(contour)
                        # Simulate tracking logic
                        pass
            
            prev_frame = gray_frame.copy()
            processed_frames += 1
            
            if frame_idx % 20 == 0:
                print(f"  Processed {processed_frames}/{frame_count} frames...")
        
        end_time = time.time()
        mem_after = process.memory_info().rss / (1024*1024)
        
        total_time = end_time - start_time
        processing_fps = processed_frames / total_time
        avg_latency = (total_time / processed_frames) * 1000
        memory_delta = mem_after - mem_before
        
        metric = ModelPerformanceMetric(
            model_name="Video_Pipeline",
            operation="frame_processing",
            latency_ms=avg_latency,
            throughput_fps=processing_fps,
            memory_usage_mb=memory_delta,
            cpu_percent=psutil.cpu_percent()
        )
        
        self.metrics.append(metric)
        
        print(f"\nVideo Processing Results:")
        print(f"  Processing Speed: {processing_fps:.1f} FPS")
        print(f"  Avg Frame Latency: {avg_latency:.2f}ms")
        print(f"  Memory Usage: {memory_delta:.2f}MB")
        print(f"  Real-time Capability: {'YES' if processing_fps >= fps else 'NO'}")
    
    def test_memory_efficiency(self):
        """Test memory usage patterns and potential leaks"""
        print("\n=== MEMORY EFFICIENCY ANALYSIS ===")
        
        if not self.opencv_available:
            print("OpenCV not available - skipping memory tests")
            return
            
        # Test for memory leaks in image processing
        print("Testing for memory leaks...")
        
        initial_memory = psutil.Process().memory_info().rss / (1024*1024)
        memory_samples = []
        
        for iteration in range(20):
            # Process multiple images
            test_images = self.create_test_data(width=1024, height=768, count=10)
            
            for image in test_images:
                # Perform memory-intensive operations
                resized = cv2.resize(image, (512, 384))
                blurred = cv2.GaussianBlur(resized, (15, 15), 0)
                edges = cv2.Canny(cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY), 50, 150)
                
                # Force garbage collection
                del resized, blurred, edges
            
            # Sample memory usage
            current_memory = psutil.Process().memory_info().rss / (1024*1024)
            memory_samples.append(current_memory)
            
            if iteration % 5 == 0:
                print(f"  Iteration {iteration}: {current_memory:.2f}MB")
            
            del test_images  # Clean up
        
        final_memory = memory_samples[-1]
        memory_trend = final_memory - initial_memory
        
        # Analyze memory trend
        if len(memory_samples) >= 10:
            first_half = statistics.mean(memory_samples[:len(memory_samples)//2])
            second_half = statistics.mean(memory_samples[len(memory_samples)//2:])
            memory_growth = second_half - first_half
        else:
            memory_growth = 0
            
        print(f"\nMemory Analysis Results:")
        print(f"  Initial Memory: {initial_memory:.2f}MB")
        print(f"  Final Memory: {final_memory:.2f}MB")
        print(f"  Total Memory Change: {memory_trend:+.2f}MB")
        print(f"  Memory Growth Rate: {memory_growth:+.2f}MB")
        
        if memory_growth > 10:
            print("  ⚠️  WARNING: Potential memory leak detected")
        elif memory_trend < 5:
            print("  ✅ Memory usage appears stable")
            
        # Add memory efficiency metric
        metric = ModelPerformanceMetric(
            model_name="Memory_Test",
            operation="memory_efficiency",
            latency_ms=0,
            throughput_fps=0,
            memory_usage_mb=memory_trend,
            cpu_percent=0
        )
        self.metrics.append(metric)
    
    def generate_ai_performance_report(self):
        """Generate comprehensive AI performance report"""
        print("\n" + "="*60)
        print("AI MODEL PERFORMANCE REPORT")
        print("="*60)
        
        if not self.metrics:
            print("No performance metrics collected")
            return {}
            
        report_data = {
            "timestamp": time.time(),
            "system_info": {
                "cpu_count": psutil.cpu_count(),
                "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                "memory_total": psutil.virtual_memory().total / (1024*1024*1024),
                "opencv_available": self.opencv_available,
                "ultralytics_available": self.ultralytics_available
            },
            "performance_metrics": [],
            "recommendations": []
        }
        
        # Process metrics by model/operation
        for metric in self.metrics:
            print(f"\n{metric.model_name} - {metric.operation}:")
            print(f"  Latency: {metric.latency_ms:.2f}ms")
            print(f"  Throughput: {metric.throughput_fps:.1f} FPS")
            print(f"  Memory Usage: {metric.memory_usage_mb:.2f}MB")
            print(f"  CPU Usage: {metric.cpu_percent:.1f}%")
            
            if metric.model_size_mb > 0:
                print(f"  Model Size: {metric.model_size_mb:.1f}MB")
                
            metric_data = {
                "model_name": metric.model_name,
                "operation": metric.operation,
                "latency_ms": metric.latency_ms,
                "throughput_fps": metric.throughput_fps,
                "memory_usage_mb": metric.memory_usage_mb,
                "cpu_percent": metric.cpu_percent,
                "model_size_mb": metric.model_size_mb
            }
            report_data["performance_metrics"].append(metric_data)
        
        # Generate recommendations
        recommendations = []
        
        # Check for high latency operations
        high_latency_ops = [m for m in self.metrics if m.latency_ms > 100]
        if high_latency_ops:
            recommendations.append({
                "type": "performance",
                "priority": "high",
                "title": "High Latency Operations Detected",
                "description": f"Found {len(high_latency_ops)} operations with >100ms latency",
                "suggestion": "Consider model optimization, hardware acceleration, or algorithm improvements"
            })
        
        # Check memory usage
        high_memory_ops = [m for m in self.metrics if m.memory_usage_mb > 100]
        if high_memory_ops:
            recommendations.append({
                "type": "memory",
                "priority": "medium",
                "title": "High Memory Usage",
                "description": f"Operations using significant memory: {len(high_memory_ops)}",
                "suggestion": "Implement batch processing, memory pooling, or image downsizing"
            })
        
        # Check real-time capability for video processing
        video_metrics = [m for m in self.metrics if "video" in m.model_name.lower() or "frame" in m.operation]
        for metric in video_metrics:
            if metric.throughput_fps < 30:
                recommendations.append({
                    "type": "realtime",
                    "priority": "high", 
                    "title": "Real-time Processing Issue",
                    "description": f"Video processing at {metric.throughput_fps:.1f} FPS (< 30 FPS)",
                    "suggestion": "Optimize processing pipeline, reduce resolution, or use hardware acceleration"
                })
        
        report_data["recommendations"] = recommendations
        
        # Print recommendations
        if recommendations:
            print(f"\n{'OPTIMIZATION RECOMMENDATIONS'}")
            print("-" * 40)
            for rec in recommendations:
                print(f"🔧 {rec['title']} ({rec['priority']} priority)")
                print(f"   {rec['description']}")
                print(f"   💡 {rec['suggestion']}\n")
        
        # Save report
        report_path = "/workspaces/Testing/docs/ai_model_performance_report.json"
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
        
        print(f"AI performance report saved to: {report_path}")
        return report_data

def main():
    """Run AI model performance tests"""
    tester = AIModelPerformanceTest()
    
    print("Starting AI Model Performance Testing Suite...")
    print("This will test OpenCV operations, YOLO inference (if available), and video processing.\n")
    
    # Run tests
    tester.test_opencv_performance()
    tester.test_yolo_performance()  
    tester.test_video_processing_performance()
    tester.test_memory_efficiency()
    
    # Generate report
    report = tester.generate_ai_performance_report()
    
    print("\n✅ AI model performance testing completed!")
    return report

if __name__ == "__main__":
    main()
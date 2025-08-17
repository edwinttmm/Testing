# ML Pipeline for VRU Detection

## Overview

This ML pipeline provides comprehensive Vulnerable Road User (VRU) detection capabilities using YOLOv8, optimized for <50ms inference latency with real-time performance monitoring.

## Features

### 🚀 Core Capabilities
- **YOLOv8 Detection**: High-performance VRU detection for pedestrians, cyclists, motorcyclists, wheelchairs, and scooters
- **Temporal Tracking**: Kalman filter-based tracking across video frames
- **Performance Monitoring**: Real-time metrics collection and bottleneck analysis
- **Model Management**: Hot-swappable models with versioning and benchmarking
- **Batch Processing**: Efficient processing of multiple videos
- **GPU Acceleration**: CUDA optimization with CPU fallback

### 🎯 VRU Classes Supported
- **Person** (pedestrians, wheelchair users)
- **Bicycle** (cyclists)
- **Motorcycle** (motorcyclists)
- **Additional classes can be configured for specialized VRUs**

### ⚡ Performance Targets
- **Inference Latency**: <50ms per frame
- **GPU Acceleration**: CUDA/OpenCL optimization
- **CPU Fallback**: Automatic fallback for systems without GPU
- **Batch Processing**: Efficient multi-video processing

## Architecture

```
src/ml/
├── inference/          # YOLOv8 detection service
├── models/            # Model management and versioning
├── preprocessing/     # Video processing pipeline
├── tracking/          # Kalman filter tracking
├── monitoring/        # Performance monitoring
├── utils/            # Image processing utilities
├── api/              # FastAPI endpoints
└── integration/      # Backend integration
```

## Installation

### Requirements
```bash
# Install ML pipeline dependencies
pip install -r src/ml/requirements.txt
```

### GPU Support (Optional)
```bash
# For NVIDIA GPU acceleration
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install onnxruntime-gpu
```

## Quick Start

### 1. Initialize ML Services
```python
from src.ml import yolo_service, model_manager, performance_monitor

# Initialize services
await model_manager.initialize_default_model()
await yolo_service.initialize()
performance_monitor.start_monitoring()
```

### 2. Single Frame Detection
```python
import cv2
from src.ml.inference import yolo_service

# Load image
frame = cv2.imread("image.jpg")

# Detect VRUs
detections, annotated_frame = await yolo_service.detect_vru(
    frame, return_annotated=True
)

print(f"Found {len(detections)} VRUs")
for detection in detections:
    print(f"- {detection.class_name}: {detection.confidence:.2f}")
```

### 3. Video Processing
```python
from src.ml.preprocessing import video_processor

# Process video
result = await video_processor.process_video(
    video_path="video.mp4",
    yolo_service=yolo_service,
    enable_tracking=True,
    save_screenshots=True
)

print(f"Processed {result.total_detections} detections")
print(f"Processing time: {result.processing_time_seconds:.2f}s")
print(f"FPS: {result.fps:.1f}")
```

### 4. Performance Monitoring
```python
from src.ml.monitoring import performance_monitor

# Get current stats
stats = performance_monitor.get_current_stats()
print(f"Average inference time: {stats['performance']['average_inference_time_ms']}ms")

# Detect bottlenecks
bottlenecks = performance_monitor.detect_bottlenecks()
if bottlenecks['bottlenecks']:
    print("Performance issues detected:")
    for issue in bottlenecks['bottlenecks']:
        print(f"- {issue}")
```

## Configuration

### ML Configuration
```python
from src.ml.config import ml_config

# Update configuration
ml_config.confidence_threshold = 0.3
ml_config.max_inference_time_ms = 40
ml_config.tracking_enabled = True
```

### Model Management
```python
from src.ml.models import model_manager

# List available models
models = model_manager.version_manager.list_models()

# Hot swap model
await model_manager.hot_swap_model("yolov8s", "v1.0")

# Benchmark model
metrics = await model_manager.benchmark_model("yolov8n", iterations=100)
```

## API Endpoints

### Detection Endpoints
- `POST /api/ml/detect/frame` - Single frame detection
- `POST /api/ml/detect/video` - Async video processing

### Model Management
- `GET /api/ml/models` - List available models
- `POST /api/ml/models/{name}/activate` - Activate model
- `POST /api/ml/models/{name}/benchmark` - Benchmark model

### Monitoring
- `GET /api/ml/status` - Service status
- `GET /api/ml/performance/metrics` - Performance metrics
- `GET /api/ml/tracking/status` - Tracking status

### Configuration
- `GET /api/ml/config` - Get configuration
- `POST /api/ml/config/update` - Update configuration

## Integration with Backend

The ML pipeline integrates seamlessly with the existing backend validation service:

```python
from src.ml.integration import ml_validation_service

# Generate ground truth for video
ground_truth = await ml_validation_service.generate_ground_truth(
    video_path="video.mp4"
)

# Validate detection event
result = await ml_validation_service.validate_detection_event(
    detection_event, ground_truth_objects, tolerance_ms=1000
)

# Calculate session metrics
metrics = await ml_validation_service.calculate_session_metrics(
    detection_events, ground_truth_objects
)
```

## Performance Optimization

### GPU Optimization
- Automatic CUDA device detection
- Half precision inference (FP16)
- Batch processing for multiple frames
- Memory management and caching

### CPU Optimization
- Multi-threaded preprocessing
- Optimized image processing
- Efficient memory usage
- Fallback algorithms

### Inference Optimization
- Model compilation (PyTorch 2.0+)
- TensorRT optimization (optional)
- ONNX Runtime acceleration
- Batch inference

## Monitoring and Metrics

### Real-time Metrics
- Inference latency tracking
- GPU/CPU utilization
- Memory usage monitoring
- FPS calculation
- Detection accuracy

### Performance Analysis
- Bottleneck detection
- Trend analysis
- Resource optimization recommendations
- Automatic scaling suggestions

## Model Versioning

### Model Registration
```python
# Register new model
model_info = model_manager.version_manager.register_model(
    model_path="new_model.pt",
    name="yolov8_custom",
    version="v2.0"
)
```

### Model Benchmarking
```python
# Benchmark model performance
metrics = await model_manager.benchmark_model(
    "yolov8_custom", "v2.0", iterations=100
)
```

## Troubleshooting

### Common Issues

1. **GPU Not Detected**
   - Ensure CUDA drivers are installed
   - Check `torch.cuda.is_available()`
   - Verify GPU memory availability

2. **Slow Inference**
   - Check model size and complexity
   - Monitor GPU utilization
   - Consider model optimization

3. **Memory Issues**
   - Reduce batch size
   - Use half precision
   - Monitor memory usage

### Performance Debugging
```python
# Enable detailed logging
import logging
logging.getLogger('src.ml').setLevel(logging.DEBUG)

# Check system status
status = await ml_validation_service.get_service_status()
print(status)

# Analyze bottlenecks
bottlenecks = performance_monitor.detect_bottlenecks()
print(bottlenecks)
```

## Advanced Features

### Custom Model Training
- Support for custom YOLOv8 models
- Transfer learning capabilities
- Domain-specific optimization

### Multi-Camera Support
- Concurrent processing of multiple video streams
- Camera-specific calibration
- Synchronized detection across cameras

### Edge Deployment
- Optimized for edge devices
- Quantized model support
- Reduced memory footprint

## Contributing

1. Follow the existing code structure
2. Add comprehensive tests for new features
3. Update documentation
4. Ensure performance benchmarks are met
5. Add proper error handling and logging

## License

This ML pipeline is part of the AI Model Validation Platform.
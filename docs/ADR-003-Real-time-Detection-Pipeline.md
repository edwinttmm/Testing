# ADR-003: Real-time Detection Pipeline Architecture

## Status
Proposed

## Context
The current detection pipeline processes videos in a basic manner without real-time streaming capabilities, advanced batching, or performance optimization. For live detection scenarios and efficient video processing, we need a sophisticated pipeline that can handle real-time streams, batch processing, and provide immediate feedback.

## Decision
Implement a multi-stage real-time detection pipeline with:
1. **Asynchronous frame processing** with configurable batch sizes
2. **Queue-based architecture** for managing processing flow
3. **Object tracking** for temporal consistency
4. **Real-time analytics** for performance monitoring
5. **Streaming results** via WebSocket integration

### Key Components:
- `RealTimeDetectionPipeline` with worker-based architecture
- `FramePreprocessor` for input normalization
- `ModelInferenceEngine` with batch processing capabilities
- `ObjectTracker` for temporal object consistency
- `DetectionAnalytics` for performance metrics

## Consequences

### Positive:
- **Real-time processing** enabling live detection scenarios
- **Optimized throughput** through intelligent batching
- **Resource efficiency** with asynchronous processing
- **Temporal consistency** through object tracking
- **Scalable architecture** supporting high video volumes
- **Performance monitoring** with built-in analytics

### Negative:
- **Increased system complexity** with multiple processing stages
- **Memory requirements** for frame queues and batch processing
- **Potential bottlenecks** at inference stage under high load
- **GPU resource management** complexity for ML inference

### Risks:
- **Queue overflow** under high load without proper backpressure
- **Memory leaks** from improper frame buffer management
- **Processing delays** if inference cannot keep up with input rate
- **Accuracy degradation** from aggressive batching or frame dropping

## Alternatives Considered

### 1. Synchronous Frame-by-Frame Processing
**Rejected** - Would not provide real-time capabilities and would be inefficient for batch processing.

### 2. External Streaming Platform (e.g., Apache Kafka)
**Considered** - Would provide robust streaming capabilities but adds infrastructure complexity for the current scale.

### 3. GPU-accelerated Processing Only
**Rejected** - Would limit deployment flexibility and increase infrastructure requirements.

### 4. Simple Threading Approach
**Rejected** - Would not provide the control and optimization capabilities needed for high-performance processing.

## Technical Specifications

### Pipeline Stages:
1. **Frame Reader** - Video decoding and frame extraction
2. **Preprocessor** - Frame normalization and batching
3. **Inference Engine** - ML model processing
4. **Post-processor** - NMS, filtering, and tracking
5. **Result Broadcaster** - WebSocket streaming

### Configuration Parameters:
```python
@dataclass
class PipelineConfig:
    model_name: str = "yolov8n"
    confidence_threshold: float = 0.7
    nms_threshold: float = 0.45
    batch_size: int = 8
    max_queue_size: int = 50
    enable_tracking: bool = True
    enable_analytics: bool = True
```

### Performance Targets:
- **Latency**: < 100ms end-to-end for real-time scenarios
- **Throughput**: > 30 FPS for standard video processing
- **Memory Usage**: < 4GB for typical deployment
- **CPU Utilization**: < 80% under normal load

## Implementation Notes
- Use asyncio queues with size limits to prevent memory overflow
- Implement graceful degradation by dropping frames under high load
- Monitor queue sizes and processing times for bottleneck detection
- Use thread pools for CPU-intensive preprocessing operations
- Consider GPU memory management for batch size optimization
- Implement circuit breaker pattern for inference engine failures
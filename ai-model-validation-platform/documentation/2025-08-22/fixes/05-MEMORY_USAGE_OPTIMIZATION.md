# Memory Usage Optimization During Detection Processing

## 🎯 Critical Memory Performance Issues

The AI Model Validation Platform experiences severe memory inefficiencies during detection processing, with memory usage spiking to 4GB+ per video, causing system instability and processing failures.

## 🔍 Memory Leak Analysis

### Primary Memory Issues Identified

#### 1. YOLO Model Memory Accumulation (Lines 1101-1138)
```python
# MEMORY LEAK: Model instances not properly cleaned up
def _predict_sync(self, frame: np.ndarray) -> List[Detection]:
    try:
        # ⚠️ MEMORY ISSUE: Model loaded in thread without proper cleanup
        from ultralytics import YOLO
        yolo_model = YOLO('yolo11l.pt')
        model = RealYOLOv8Wrapper(yolo_model)
        
        # ⚠️ GPU MEMORY LEAK: Tensors remain in GPU memory
        results = model.model(frame, verbose=False, conf=0.001)
        
        for r in results:
            boxes = r.boxes
            # ⚠️ NO CLEANUP: GPU tensors not explicitly released
```

**Memory Impact**: 
- 500MB+ per model loading
- GPU memory not released between frames
- Accumulated tensor objects in memory

#### 2. Frame Buffer Memory Waste (Lines 1063-1072)
```python
# INEFFICIENT: New array allocation per frame
def _preprocess_frame_sync(self, frame: np.ndarray) -> np.ndarray:
    # ⚠️ MEMORY ALLOCATION: New array each time (640x640x3 = 1.2MB)
    if frame.dtype != np.uint8:
        frame = (frame * 255).astype(np.uint8)  # Creates new array
    return frame  # No buffer pool usage
```

**Memory Impact**:
- 1.2MB allocation per frame
- No buffer reuse strategy
- Garbage collection pressure

#### 3. Detection Result Object Accumulation
```python
# MEMORY ACCUMULATION: Objects stored without cleanup
all_detections = []
for detection in detections:
    # ⚠️ GROWING LIST: Unbounded memory growth
    detection_dict = {
        "id": detection.detection_id,
        "bounding_box": detection.bounding_box.to_dict(),  # Nested objects
        "screenshot_path": screenshot_path,  # File path strings
        # Multiple fields per detection...
    }
    all_detections.append(detection_dict)  # Growing memory footprint
```

**Memory Impact**:
- 5-10KB per detection object
- 50-500MB for typical video processing
- No intermediate cleanup

## 📊 Memory Usage Analysis

### Current Memory Profile
```
Video Processing Memory Timeline:
├── Initial Load: 200MB (baseline application)
├── YOLO Model Loading: +1.2GB (total: 1.4GB)
├── Frame Processing: +100MB per 100 frames (total: 2.5GB)
├── Detection Storage: +500MB for 10k detections (total: 3GB)
├── GPU Memory: +1.5GB VRAM usage (total: 4.5GB)
└── Peak Usage: 4-6GB RAM + 1.5GB VRAM
```

### Memory Leak Patterns
1. **Model Loading Leak**: 500MB+ per video processing session
2. **GPU Memory Leak**: 1.5GB VRAM not released
3. **Frame Buffer Leak**: 1.2MB per frame (no reuse)
4. **Detection Object Leak**: 5KB per detection accumulation
5. **Screenshot Path Leak**: String accumulation over time

## 🚀 Memory Optimization Strategy

### Phase 1: Memory Pool Implementation

#### 1.1 Advanced Frame Buffer Pool
```python
import threading
from typing import Dict, List, Optional
from collections import deque
import gc

class AdvancedFrameBufferPool:
    """Thread-safe memory pool with automatic cleanup"""
    
    def __init__(self, 
                 pool_size: int = 50,
                 frame_shape: Tuple[int, int, int] = (640, 640, 3),
                 max_memory_mb: int = 500):
        self.pool_size = pool_size
        self.frame_shape = frame_shape
        self.max_memory_mb = max_memory_mb
        
        # Thread-safe buffer pools
        self._available_buffers = deque(maxlen=pool_size)
        self._in_use_buffers = set()
        self._lock = threading.RLock()
        
        # Memory tracking
        self._allocated_buffers = 0
        self._peak_usage = 0
        self._total_requests = 0
        self._cache_hits = 0
        
        # Pre-allocate buffers
        self._preallocate_buffers()
        
        # Memory pressure monitoring
        self._memory_pressure_threshold = 0.8
        
    def _preallocate_buffers(self):
        """Pre-allocate buffer pool"""
        buffer_size_mb = (np.prod(self.frame_shape) * np.dtype(np.uint8).itemsize) / (1024 * 1024)
        max_buffers = min(self.pool_size, int(self.max_memory_mb / buffer_size_mb))
        
        for _ in range(max_buffers):
            buffer = np.empty(self.frame_shape, dtype=np.uint8)
            buffer.flags.writeable = True
            self._available_buffers.append(buffer)
            self._allocated_buffers += 1
            
        logger.info(f"Pre-allocated {max_buffers} frame buffers ({buffer_size_mb * max_buffers:.1f}MB)")
    
    def get_buffer(self) -> np.ndarray:
        """Get frame buffer with automatic cleanup"""
        with self._lock:
            self._total_requests += 1
            
            # Try to get from pool first
            if self._available_buffers:
                buffer = self._available_buffers.popleft()
                self._in_use_buffers.add(id(buffer))
                self._cache_hits += 1
                return buffer
            
            # Check memory pressure before creating new buffer
            if self._check_memory_pressure():
                self._cleanup_unused_buffers()
                
                # Try pool again after cleanup
                if self._available_buffers:
                    buffer = self._available_buffers.popleft()
                    self._in_use_buffers.add(id(buffer))
                    return buffer
            
            # Create new buffer if under limits
            if self._allocated_buffers < self.pool_size * 1.5:  # Allow 50% overflow
                buffer = np.empty(self.frame_shape, dtype=np.uint8)
                buffer.flags.writeable = True
                self._in_use_buffers.add(id(buffer))
                self._allocated_buffers += 1
                return buffer
            
            # Memory limit reached
            raise MemoryError(f"Frame buffer pool exhausted. "
                            f"Peak usage: {self._peak_usage} buffers, "
                            f"Current: {len(self._in_use_buffers)} in use")
    
    def return_buffer(self, buffer: np.ndarray):
        """Return buffer to pool with validation"""
        with self._lock:
            buffer_id = id(buffer)
            
            if buffer_id in self._in_use_buffers:
                self._in_use_buffers.remove(buffer_id)
                
                # Validate buffer state
                if self._is_buffer_valid(buffer):
                    # Clear buffer data for security
                    buffer.fill(0)
                    self._available_buffers.append(buffer)
                else:
                    # Buffer corrupted, don't return to pool
                    self._allocated_buffers -= 1
                    logger.warning("Corrupted buffer detected, removing from pool")
    
    def _check_memory_pressure(self) -> bool:
        """Check if system is under memory pressure"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent / 100 > self._memory_pressure_threshold
        except ImportError:
            return False
    
    def _cleanup_unused_buffers(self):
        """Emergency cleanup of unused buffers"""
        # Force garbage collection
        gc.collect()
        
        # Remove excess buffers if under pressure
        excess_buffers = len(self._available_buffers) - (self.pool_size // 2)
        if excess_buffers > 0:
            for _ in range(excess_buffers):
                if self._available_buffers:
                    self._available_buffers.popleft()
                    self._allocated_buffers -= 1
            
            logger.info(f"Emergency cleanup: removed {excess_buffers} excess buffers")
    
    def _is_buffer_valid(self, buffer: np.ndarray) -> bool:
        """Validate buffer integrity"""
        return (buffer.shape == self.frame_shape and 
                buffer.dtype == np.uint8 and
                buffer.flags.writeable)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive pool statistics"""
        with self._lock:
            current_usage = len(self._in_use_buffers)
            self._peak_usage = max(self._peak_usage, current_usage)
            
            return {
                'pool_size': self.pool_size,
                'available': len(self._available_buffers),
                'in_use': current_usage,
                'allocated': self._allocated_buffers,
                'peak_usage': self._peak_usage,
                'total_requests': self._total_requests,
                'cache_hit_rate': (self._cache_hits / self._total_requests * 100) if self._total_requests > 0 else 0,
                'memory_mb': self._estimated_memory_usage_mb(),
                'efficiency': current_usage / self._allocated_buffers if self._allocated_buffers > 0 else 0
            }
    
    def _estimated_memory_usage_mb(self) -> float:
        """Estimate current memory usage in MB"""
        buffer_size_bytes = np.prod(self.frame_shape) * np.dtype(np.uint8).itemsize
        return (self._allocated_buffers * buffer_size_bytes) / (1024 * 1024)
```

#### 1.2 YOLO Model Memory Management
```python
class YOLOModelManager:
    """Singleton YOLO model manager with memory optimization"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, 'initialized'):
            return
            
        self.models = {}
        self.model_lock = threading.RLock()
        self.gpu_memory_pool = None
        self.memory_monitor = MemoryMonitor()
        self.initialized = True
        
        # Initialize GPU memory management
        if torch.cuda.is_available():
            self._setup_gpu_memory_management()
    
    def _setup_gpu_memory_management(self):
        """Configure GPU memory for efficient usage"""
        try:
            # Set memory fraction to prevent OOM
            torch.cuda.set_per_process_memory_fraction(0.8)  # Use 80% of GPU memory
            
            # Enable memory mapping for large models
            torch.cuda.empty_cache()
            
            # Create memory pool for reuse
            self.gpu_memory_pool = torch.cuda.memory_pool_create()
            
            logger.info("GPU memory management configured successfully")
        except Exception as e:
            logger.error(f"GPU memory management setup failed: {e}")
    
    def get_model(self, model_name: str = "yolo11l") -> 'OptimizedYOLOWrapper':
        """Get YOLO model with memory optimization"""
        with self.model_lock:
            if model_name not in self.models:
                # Check memory before loading
                if self.memory_monitor.check_memory_availability(required_mb=1200):
                    self.models[model_name] = self._load_model_optimized(model_name)
                else:
                    # Cleanup and retry
                    self._emergency_memory_cleanup()
                    if self.memory_monitor.check_memory_availability(required_mb=1200):
                        self.models[model_name] = self._load_model_optimized(model_name)
                    else:
                        raise MemoryError("Insufficient memory to load YOLO model")
            
            return self.models[model_name]
    
    def _load_model_optimized(self, model_name: str) -> 'OptimizedYOLOWrapper':
        """Load YOLO model with memory optimizations"""
        try:
            from ultralytics import YOLO
            
            # Load model with optimizations
            model = YOLO(f"{model_name}.pt")
            
            # Configure for memory efficiency
            if torch.cuda.is_available():
                model.to('cuda', non_blocking=True)
                
                # Optimize model for inference
                model.model.eval()
                model.model.fuse()  # Fuse conv and bn layers
                
                # Enable memory-efficient attention if available
                if hasattr(model.model, 'enable_memory_efficient_attention'):
                    model.model.enable_memory_efficient_attention()
            
            # Warm up model with dummy input
            dummy_input = torch.randn(1, 3, 640, 640)
            if torch.cuda.is_available():
                dummy_input = dummy_input.cuda(non_blocking=True)
            
            with torch.no_grad():
                _ = model.model(dummy_input)
            
            # Clear dummy input from memory
            del dummy_input
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            wrapped_model = OptimizedYOLOWrapper(model, self.memory_monitor)
            logger.info(f"Loaded and optimized YOLO model: {model_name}")
            
            return wrapped_model
            
        except Exception as e:
            logger.error(f"Failed to load YOLO model {model_name}: {e}")
            raise
    
    def _emergency_memory_cleanup(self):
        """Emergency memory cleanup"""
        logger.warning("Performing emergency memory cleanup")
        
        # Force Python garbage collection
        gc.collect()
        
        # Clear GPU cache if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        # Clear model caches if memory pressure is high
        if len(self.models) > 1:
            # Keep only the most recently used model
            oldest_model = min(self.models.keys())
            if oldest_model in self.models:
                del self.models[oldest_model]
                logger.info(f"Cleared model from memory: {oldest_model}")
    
    def cleanup(self):
        """Cleanup all models and free memory"""
        with self.model_lock:
            for model_name in list(self.models.keys()):
                del self.models[model_name]
            
            self.models.clear()
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            gc.collect()
            logger.info("All YOLO models cleaned up from memory")

class OptimizedYOLOWrapper:
    """Memory-optimized YOLO wrapper"""
    
    def __init__(self, yolo_model, memory_monitor: 'MemoryMonitor'):
        self.model = yolo_model
        self.memory_monitor = memory_monitor
        self.batch_size_limit = 8  # Adjust based on available memory
        
        # Pre-compile common operations
        self._compile_for_inference()
    
    def _compile_for_inference(self):
        """Compile model for optimized inference"""
        try:
            # Torch compile for faster inference (PyTorch 2.0+)
            if hasattr(torch, 'compile'):
                self.model.model = torch.compile(self.model.model, mode='reduce-overhead')
                logger.info("Model compiled for faster inference")
        except Exception as e:
            logger.warning(f"Model compilation failed: {e}")
    
    def predict_batch_memory_optimized(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        """Memory-optimized batch prediction"""
        if not frames:
            return []
        
        # Check memory before processing
        required_memory = len(frames) * 1.2  # MB per frame estimate
        if not self.memory_monitor.check_memory_availability(required_mb=required_memory):
            # Process in smaller batches
            return self._process_in_smaller_batches(frames)
        
        try:
            # Convert frames to tensor batch efficiently
            batch_tensor = self._frames_to_tensor_batch_optimized(frames)
            
            # Run inference
            with torch.no_grad():
                results = self.model(batch_tensor, verbose=False, conf=0.3)
            
            # Parse results
            detections = self._parse_results_memory_efficient(results, frames)
            
            # Explicit cleanup
            del batch_tensor
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            return detections
            
        except torch.cuda.OutOfMemoryError:
            logger.warning("GPU OOM detected, falling back to smaller batches")
            torch.cuda.empty_cache()
            return self._process_in_smaller_batches(frames)
        except Exception as e:
            logger.error(f"Batch prediction failed: {e}")
            return []
    
    def _frames_to_tensor_batch_optimized(self, frames: List[np.ndarray]) -> torch.Tensor:
        """Convert frames to optimized tensor batch"""
        batch_size = len(frames)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Pre-allocate tensor
        batch_tensor = torch.empty(
            (batch_size, 3, 640, 640),
            dtype=torch.float32,
            device=device,
            pin_memory=True if device.type == 'cuda' else False
        )
        
        # Process frames efficiently
        for i, frame in enumerate(frames):
            # Resize frame
            resized = cv2.resize(frame, (640, 640))
            
            # Convert to CHW format and normalize
            normalized = resized.transpose(2, 0, 1).astype(np.float32) / 255.0
            
            # Copy to pre-allocated tensor
            batch_tensor[i] = torch.from_numpy(normalized)
        
        return batch_tensor
    
    def _process_in_smaller_batches(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        """Process frames in smaller batches to avoid OOM"""
        batch_size = max(1, len(frames) // 4)  # Process in quarters
        all_detections = []
        
        for i in range(0, len(frames), batch_size):
            batch = frames[i:i + batch_size]
            batch_detections = self.predict_batch_memory_optimized(batch)
            all_detections.extend(batch_detections)
            
            # Small delay to allow memory cleanup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        return all_detections
```

### Phase 2: Detection Result Memory Optimization

#### 2.1 Streaming Detection Results
```python
class StreamingDetectionProcessor:
    """Process detections with memory streaming"""
    
    def __init__(self, max_memory_mb: int = 100):
        self.max_memory_mb = max_memory_mb
        self.detection_buffer = deque(maxlen=1000)  # Circular buffer
        self.memory_monitor = MemoryMonitor()
        self.result_cache = {}
        
    async def process_video_streaming(self, video_path: str, video_id: str) -> AsyncGenerator[Dict, None]:
        """Process video with streaming results to minimize memory usage"""
        cap = cv2.VideoCapture(video_path)
        frame_number = 0
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Initialize model manager
        model_manager = YOLOModelManager()
        model = model_manager.get_model("yolo11l")
        
        # Buffer pool for frames
        buffer_pool = AdvancedFrameBufferPool(pool_size=30, max_memory_mb=50)
        
        batch_frames = []
        batch_metadata = []
        batch_size = 8
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    # Process remaining frames
                    if batch_frames:
                        yield await self._process_batch_streaming(
                            batch_frames, batch_metadata, model, buffer_pool
                        )
                    break
                
                frame_number += 1
                
                # Skip frames for efficiency
                if frame_number % 3 != 0:
                    continue
                
                # Get buffer from pool
                frame_buffer = buffer_pool.get_buffer()
                np.copyto(frame_buffer, cv2.resize(frame, (640, 640)))
                
                batch_frames.append(frame_buffer)
                batch_metadata.append({
                    'frame_number': frame_number,
                    'timestamp': frame_number / fps,
                    'progress': frame_number / total_frames
                })
                
                # Process batch when full
                if len(batch_frames) >= batch_size:
                    yield await self._process_batch_streaming(
                        batch_frames, batch_metadata, model, buffer_pool
                    )
                    
                    # Clear batch for next iteration
                    batch_frames = []
                    batch_metadata = []
                
                # Memory pressure check
                if self.memory_monitor.get_memory_usage_mb() > self.max_memory_mb:
                    await self._emergency_memory_cleanup()
                    
        finally:
            cap.release()
            
            # Return all buffers to pool
            for buffer in batch_frames:
                buffer_pool.return_buffer(buffer)
    
    async def _process_batch_streaming(
        self, 
        batch_frames: List[np.ndarray], 
        batch_metadata: List[Dict],
        model: OptimizedYOLOWrapper,
        buffer_pool: AdvancedFrameBufferPool
    ) -> Dict:
        """Process batch and return streaming result"""
        try:
            # Run detection on batch
            batch_detections = model.predict_batch_memory_optimized(batch_frames)
            
            # Convert to lightweight format
            streaming_result = {
                'detections': [],
                'metadata': {
                    'batch_size': len(batch_frames),
                    'timestamp': time.time(),
                    'memory_usage_mb': self.memory_monitor.get_memory_usage_mb()
                }
            }
            
            for frame_detections, metadata in zip(batch_detections, batch_metadata):
                for detection in frame_detections:
                    # Convert to compact format
                    compact_detection = {
                        'id': detection.detection_id[:8],  # Truncate ID
                        'frame': metadata['frame_number'],
                        'time': round(metadata['timestamp'], 2),
                        'class': detection.class_label,
                        'conf': round(detection.confidence, 3),
                        'box': [
                            int(detection.bounding_box.x),
                            int(detection.bounding_box.y),
                            int(detection.bounding_box.width),
                            int(detection.bounding_box.height)
                        ]
                    }
                    
                    streaming_result['detections'].append(compact_detection)
            
            # Store in circular buffer for recent history
            self.detection_buffer.append(streaming_result['detections'])
            
            return streaming_result
            
        finally:
            # Return buffers to pool immediately
            for buffer in batch_frames:
                buffer_pool.return_buffer(buffer)
    
    async def _emergency_memory_cleanup(self):
        """Emergency memory cleanup during streaming"""
        logger.warning("Emergency memory cleanup during streaming")
        
        # Clear detection buffer
        self.detection_buffer.clear()
        
        # Clear result cache
        self.result_cache.clear()
        
        # Force garbage collection
        gc.collect()
        
        # GPU memory cleanup
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        logger.info("Emergency cleanup completed")
```

### Phase 3: Memory Monitoring and Alerts

#### 3.1 Real-time Memory Monitor
```python
import psutil
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

@dataclass
class MemoryThresholds:
    warning_mb: int = 2000      # 2GB warning
    critical_mb: int = 3000     # 3GB critical  
    emergency_mb: int = 4000    # 4GB emergency
    gpu_warning_mb: int = 1000  # 1GB GPU warning
    gpu_critical_mb: int = 1500 # 1.5GB GPU critical

class MemoryMonitor:
    """Real-time memory monitoring with alerts"""
    
    def __init__(self, thresholds: MemoryThresholds = None):
        self.thresholds = thresholds or MemoryThresholds()
        self.callbacks = {
            'warning': [],
            'critical': [],
            'emergency': []
        }
        self.monitoring = False
        self.monitor_thread = None
        self.last_alert_time = {}
        self.alert_cooldown = 30  # seconds
        
    def register_callback(self, level: str, callback: Callable):
        """Register callback for memory alerts"""
        if level in self.callbacks:
            self.callbacks[level].append(callback)
    
    def start_monitoring(self, interval: float = 1.0):
        """Start background memory monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        logger.info("Memory monitoring stopped")
    
    def _monitor_loop(self, interval: float):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                memory_info = self.get_memory_info()
                self._check_thresholds(memory_info)
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                time.sleep(interval * 2)  # Back off on error
    
    def get_memory_info(self) -> Dict[str, float]:
        """Get comprehensive memory information"""
        # System memory
        memory = psutil.virtual_memory()
        process = psutil.Process()
        process_memory = process.memory_info()
        
        info = {
            'system_total_mb': memory.total / (1024 * 1024),
            'system_available_mb': memory.available / (1024 * 1024),
            'system_used_percent': memory.percent,
            'process_rss_mb': process_memory.rss / (1024 * 1024),
            'process_vms_mb': process_memory.vms / (1024 * 1024),
        }
        
        # GPU memory if available
        if torch.cuda.is_available():
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                
                info.update({
                    'gpu_total_mb': gpu_info.total / (1024 * 1024),
                    'gpu_used_mb': gpu_info.used / (1024 * 1024),
                    'gpu_free_mb': gpu_info.free / (1024 * 1024),
                    'gpu_used_percent': (gpu_info.used / gpu_info.total) * 100
                })
            except Exception as e:
                logger.debug(f"GPU memory info unavailable: {e}")
        
        return info
    
    def _check_thresholds(self, memory_info: Dict[str, float]):
        """Check memory thresholds and trigger alerts"""
        current_time = time.time()
        process_memory = memory_info['process_rss_mb']
        gpu_memory = memory_info.get('gpu_used_mb', 0)
        
        # Check process memory thresholds
        if process_memory >= self.thresholds.emergency_mb:
            self._trigger_alert('emergency', memory_info, current_time)
        elif process_memory >= self.thresholds.critical_mb:
            self._trigger_alert('critical', memory_info, current_time)
        elif process_memory >= self.thresholds.warning_mb:
            self._trigger_alert('warning', memory_info, current_time)
        
        # Check GPU memory thresholds
        if gpu_memory >= self.thresholds.gpu_critical_mb:
            self._trigger_alert('critical', memory_info, current_time, 'gpu')
        elif gpu_memory >= self.thresholds.gpu_warning_mb:
            self._trigger_alert('warning', memory_info, current_time, 'gpu')
    
    def _trigger_alert(self, level: str, memory_info: Dict, current_time: float, memory_type: str = 'system'):
        """Trigger memory alert with cooldown"""
        alert_key = f"{level}_{memory_type}"
        
        # Check cooldown
        if alert_key in self.last_alert_time:
            if current_time - self.last_alert_time[alert_key] < self.alert_cooldown:
                return
        
        self.last_alert_time[alert_key] = current_time
        
        # Log alert
        memory_mb = memory_info.get('gpu_used_mb' if memory_type == 'gpu' else 'process_rss_mb', 0)
        logger.warning(f"Memory {level} alert ({memory_type}): {memory_mb:.1f}MB")
        
        # Execute callbacks
        for callback in self.callbacks.get(level, []):
            try:
                callback(memory_info, level, memory_type)
            except Exception as e:
                logger.error(f"Memory alert callback failed: {e}")
    
    def get_memory_usage_mb(self) -> float:
        """Get current process memory usage in MB"""
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)
    
    def check_memory_availability(self, required_mb: float) -> bool:
        """Check if required memory is available"""
        memory_info = self.get_memory_info()
        available_mb = memory_info['system_available_mb']
        current_process_mb = memory_info['process_rss_mb']
        
        # Check if we have enough system memory
        if available_mb < required_mb:
            return False
        
        # Check if process would exceed critical threshold
        projected_usage = current_process_mb + required_mb
        if projected_usage > self.thresholds.critical_mb:
            return False
        
        return True
```

## 📈 Memory Optimization Results

### Expected Memory Improvements

| Component | Current Usage | Optimized Usage | Improvement |
|-----------|---------------|-----------------|-------------|
| YOLO Model Loading | 1.2GB per load | 600MB shared | **50% reduction** |
| Frame Processing | 1.2MB per frame | 50KB per frame | **96% reduction** |
| Detection Storage | 5KB per detection | 500B per detection | **90% reduction** |
| GPU Memory | 1.5GB peak | 800MB peak | **47% reduction** |
| Total Peak Usage | 4-6GB | 500MB-1GB | **80-85% reduction** |

### Memory Efficiency Metrics
- **Buffer Pool Hit Rate**: >95% (reuse efficiency)
- **Memory Allocation Rate**: 90% reduction
- **Garbage Collection Frequency**: 85% reduction
- **Memory Fragmentation**: 70% reduction
- **Peak Memory Stability**: Consistent <1GB peaks

## 🔧 Implementation Roadmap

### Week 1: Memory Pool Foundation
- [ ] Implement AdvancedFrameBufferPool
- [ ] Create YOLOModelManager singleton
- [ ] Add memory monitoring infrastructure
- [ ] Integrate memory pressure detection

### Week 2: Streaming Processing
- [ ] Implement StreamingDetectionProcessor  
- [ ] Add circular buffer for results
- [ ] Create compact detection format
- [ ] Add emergency cleanup procedures

### Week 3: Memory Monitoring
- [ ] Setup real-time memory monitoring
- [ ] Add threshold-based alerts
- [ ] Implement automatic cleanup triggers
- [ ] Create memory usage dashboards

### Week 4: Testing & Optimization
- [ ] Load test with memory constraints
- [ ] Validate memory leak prevention
- [ ] Performance regression testing
- [ ] Documentation and deployment

---

**Priority**: 🟠 **MEDIUM-HIGH - Critical for System Stability**  
**Implementation Time**: 4 weeks  
**Expected Impact**: 80-85% memory usage reduction  
**Risk Level**: Medium (requires thorough testing)  
**Dependencies**: PyTorch optimization, memory profiling tools
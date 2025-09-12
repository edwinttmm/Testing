# Background Tasks and Async Operations

## Overview

The FastAPI application implements comprehensive background task processing for long-running operations including video processing, ML inference, report generation, and hardware communication. The system uses multiple async patterns including ThreadPoolExecutor, AsyncIO, and FastAPI's BackgroundTasks.

## Background Task Architecture

### 1. FastAPI BackgroundTasks Integration

**Basic Pattern**:
```python
@app.post("/api/videos/process")
async def start_video_processing(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    background_tasks.add_task(process_video_task, video_id)
    return {"status": "processing_started", "video_id": video_id}

def process_video_task(video_id: str):
    # Long-running video processing
    with SessionLocal() as db:
        video = db.query(Video).filter(Video.id == video_id).first()
        # Process video...
```

**Features**:
- **Non-blocking**: Request returns immediately
- **Error Isolation**: Task failures don't affect API responses
- **Database Session Management**: Proper session handling in tasks
- **Progress Tracking**: Integration with progress tracking system

### 2. ThreadPoolExecutor for CPU-Intensive Tasks

**Ground Truth Service Implementation**:
```python
class GroundTruthService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    async def process_video_async(self, video_id: str, video_file_path: str):
        """Process video asynchronously to generate ground truth"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self._process_video, video_id, video_file_path)
    
    def _process_video(self, video_id: str, video_file_path: str):
        # CPU-intensive YOLO inference
        # Frame-by-frame processing
        # Database updates
```

**Use Cases**:
- **YOLO Model Inference**: CPU/GPU intensive ML operations
- **Video Frame Processing**: OpenCV operations
- **Large File Processing**: Upload processing and validation
- **Report Generation**: PDF/HTML rendering

### 3. AsyncIO Event Loop Integration

**WebSocket Streaming**:
```python
@app.websocket("/ws/labjack/stream")
async def labjack_websocket_stream(websocket: WebSocket):
    async def safe_send_message(message_data, description="message"):
        try:
            if websocket.application_state.name == "CONNECTED":
                await websocket.send_text(json.dumps(message_data))
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
    
    try:
        while True:
            # 30ms high-frequency data streaming
            await asyncio.sleep(0.030)
            data = await get_labjack_data_async()
            await safe_send_message(data, "labjack_data")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
```

## Service-Level Background Processing

### 1. Video Processing Pipeline

**Video Ingestion Service**:
```python
class VideoIngestionService:
    async def process_uploaded_video(self, video_file: UploadFile, project_id: str):
        # Immediate response to user
        video_id = str(uuid.uuid4())
        
        # Background processing
        asyncio.create_task(self._process_video_pipeline(video_id, video_file))
        
        return {"video_id": video_id, "status": "processing_started"}
    
    async def _process_video_pipeline(self, video_id: str, video_file: UploadFile):
        try:
            # Step 1: File validation and storage
            await self._validate_and_store_video(video_id, video_file)
            
            # Step 2: Metadata extraction
            await self._extract_video_metadata(video_id)
            
            # Step 3: Generate ground truth (if enabled)
            if settings.enable_ground_truth_service:
                await self._generate_ground_truth(video_id)
            
            # Step 4: Update status
            await self._update_video_status(video_id, "completed")
            
        except Exception as e:
            logger.error(f"Video processing failed for {video_id}: {e}")
            await self._update_video_status(video_id, "error")
```

### 2. Detection Pipeline Processing

**Detection Pipeline Service**:
```python
class DetectionPipeline:
    async def process_video_for_detection(
        self, 
        video_path: str, 
        test_session_id: str,
        confidence_threshold: float = 0.4
    ) -> AsyncGenerator[DetectionResult, None]:
        """Process video frames for VRU detection"""
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        async with aiofiles.open(video_path, 'rb') as video_file:
            cap = cv2.VideoCapture(video_path)
            
            frame_number = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process frame in thread pool
                detections = await loop.run_in_executor(
                    self.executor,
                    self._process_frame,
                    frame,
                    frame_number,
                    confidence_threshold
                )
                
                # Store detections in database
                await self._store_detection_results(
                    test_session_id, 
                    detections, 
                    frame_number
                )
                
                yield DetectionResult(
                    detections=detections,
                    frame_number=frame_number,
                    timestamp=frame_number / fps
                )
                
                frame_number += 1
```

### 3. Report Generation Pipeline

**Report Generation Service**:
```python
class ReportGenerationService:
    async def generate_comprehensive_report(
        self,
        test_session_id: str,
        formats: List[str] = ["html", "json"]
    ) -> TestReportResponse:
        
        # Start background report generation
        report_id = str(uuid.uuid4())
        
        asyncio.create_task(
            self._generate_report_background(report_id, test_session_id, formats)
        )
        
        return {"report_id": report_id, "status": "generating"}
    
    async def _generate_report_background(
        self,
        report_id: str,
        test_session_id: str,
        formats: List[str]
    ):
        try:
            # Step 1: Collect test data
            test_data = await self._collect_test_data(test_session_id)
            
            # Step 2: Calculate metrics
            metrics = await self._calculate_metrics(test_data)
            
            # Step 3: Generate failure snapshots
            snapshots = await self._generate_failure_snapshots(test_data)
            
            # Step 4: Generate reports in parallel
            tasks = []
            for format_type in formats:
                task = asyncio.create_task(
                    self._generate_format_report(report_id, test_data, format_type)
                )
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            # Step 5: Update status
            await self._update_report_status(report_id, "completed")
            
        except Exception as e:
            logger.error(f"Report generation failed for {report_id}: {e}")
            await self._update_report_status(report_id, "error")
```

## Queue-Based Processing

### 1. Video Processing Queue

**Video Processing Queue Service**:
```python
class VideoProcessingQueue:
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=100)
        self.workers = []
        self.running = False
    
    async def start_workers(self, num_workers: int = 3):
        """Start background worker tasks"""
        self.running = True
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
    
    async def _worker(self, name: str):
        """Background worker for processing video jobs"""
        while self.running:
            try:
                job = await self.queue.get()
                logger.info(f"{name} processing job: {job['video_id']}")
                
                await self._process_video_job(job)
                
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"{name} error processing job: {e}")
    
    async def add_job(self, video_id: str, processing_config: Dict):
        """Add video processing job to queue"""
        job = {
            "video_id": video_id,
            "config": processing_config,
            "created_at": datetime.utcnow()
        }
        await self.queue.put(job)
```

### 2. Progress Tracking System

**Progress Tracker Service**:
```python
class ProgressTracker:
    def __init__(self):
        self.progress_store = {}  # In production, use Redis
    
    def start_task(self, task_id: str, total_steps: int):
        """Initialize task progress tracking"""
        self.progress_store[task_id] = {
            "current_step": 0,
            "total_steps": total_steps,
            "status": "running",
            "started_at": datetime.utcnow(),
            "messages": []
        }
    
    def update_progress(self, task_id: str, step: int, message: str = None):
        """Update task progress"""
        if task_id in self.progress_store:
            progress = self.progress_store[task_id]
            progress["current_step"] = step
            progress["last_updated"] = datetime.utcnow()
            if message:
                progress["messages"].append({
                    "timestamp": datetime.utcnow(),
                    "message": message
                })
    
    def complete_task(self, task_id: str, result: Any = None):
        """Mark task as completed"""
        if task_id in self.progress_store:
            progress = self.progress_store[task_id]
            progress["status"] = "completed"
            progress["completed_at"] = datetime.utcnow()
            progress["result"] = result
```

## Hardware Integration Background Tasks

### 1. LabJack Data Streaming

**LabJack Service Background Processing**:
```python
class LabJackService:
    def __init__(self):
        self.streaming = False
        self.data_queue = asyncio.Queue()
        
    async def start_continuous_streaming(self, session_id: str):
        """Start continuous LabJack data collection"""
        self.streaming = True
        
        # Start data collection task
        collection_task = asyncio.create_task(
            self._collect_labjack_data(session_id)
        )
        
        # Start data processing task
        processing_task = asyncio.create_task(
            self._process_labjack_data(session_id)
        )
        
        return await asyncio.gather(collection_task, processing_task)
    
    async def _collect_labjack_data(self, session_id: str):
        """Background data collection from LabJack device"""
        while self.streaming:
            try:
                # Read from LabJack (30ms intervals)
                data = await self._read_labjack_async()
                await self.data_queue.put({
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "data": data
                })
                
                await asyncio.sleep(0.030)  # 30ms timing
                
            except Exception as e:
                logger.error(f"LabJack data collection error: {e}")
    
    async def _process_labjack_data(self, session_id: str):
        """Background processing of collected LabJack data"""
        while self.streaming:
            try:
                data_point = await self.data_queue.get()
                
                # Process data point
                processed = await self._analyze_signal_data(data_point)
                
                # Store in database
                await self._store_detection_event(session_id, processed)
                
                # Notify WebSocket clients
                await self._notify_websocket_clients(processed)
                
            except Exception as e:
                logger.error(f"LabJack data processing error: {e}")
```

### 2. Precision Timing Service

**Precision Timing Background Tasks**:
```python
class PrecisionTimingService:
    async def monitor_timing_precision(self, test_session_id: str):
        """Background timing precision monitoring"""
        monitoring_task = asyncio.create_task(
            self._precision_monitoring_loop(test_session_id)
        )
        
        return monitoring_task
    
    async def _precision_monitoring_loop(self, test_session_id: str):
        """Continuous timing precision monitoring"""
        while True:
            try:
                # Measure system timing precision
                precision_data = await self._measure_timing_precision()
                
                # Check if precision degrades
                if precision_data["jitter"] > self.max_acceptable_jitter:
                    await self._handle_timing_degradation(test_session_id, precision_data)
                
                # Store precision metrics
                await self._store_timing_metrics(test_session_id, precision_data)
                
                await asyncio.sleep(1.0)  # Check every second
                
            except Exception as e:
                logger.error(f"Timing precision monitoring error: {e}")
                await asyncio.sleep(5.0)  # Back off on error
```

## Error Handling in Background Tasks

### 1. Retry Mechanisms

**Retry with Exponential Backoff**:
```python
import asyncio
from typing import Callable, Any

async def retry_async(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    *args,
    **kwargs
) -> Any:
    """Async retry with exponential backoff"""
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Max retries exceeded for {func.__name__}: {e}")
                raise
            
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

### 2. Circuit Breaker Pattern

**Circuit Breaker for External Services**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
```

## Resource Management

### 1. Connection Pooling

**Database Connection Management**:
```python
class BackgroundTaskManager:
    def __init__(self):
        self.db_pool = create_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True  # Validate connections
        )
    
    async def execute_with_db(self, task_func: Callable, *args, **kwargs):
        """Execute task with managed database connection"""
        with self.db_pool.connect() as conn:
            with conn.begin():
                try:
                    return await task_func(conn, *args, **kwargs)
                except Exception as e:
                    logger.error(f"Database task failed: {e}")
                    raise
```

### 2. Memory Management

**Memory-Efficient Video Processing**:
```python
async def process_large_video_efficiently(video_path: str):
    """Process large video files with memory management"""
    
    # Process in chunks to manage memory
    chunk_size = 30  # Process 30 frames at a time
    
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    for start_frame in range(0, total_frames, chunk_size):
        end_frame = min(start_frame + chunk_size, total_frames)
        
        # Process chunk
        chunk_results = await process_frame_chunk(
            video_path, start_frame, end_frame
        )
        
        # Store results immediately to free memory
        await store_chunk_results(chunk_results)
        
        # Force garbage collection after each chunk
        import gc
        gc.collect()
        
        # Small delay to prevent overwhelming the system
        await asyncio.sleep(0.1)
```

## Performance Monitoring

### 1. Task Performance Metrics

**Performance Tracking**:
```python
import time
from functools import wraps

def track_performance(func):
    """Decorator to track background task performance"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        task_name = func.__name__
        
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Log performance metrics
            logger.info(f"Task {task_name} completed in {duration:.2f}s")
            
            # Store metrics for monitoring
            await store_task_metrics(task_name, duration, "success")
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Task {task_name} failed after {duration:.2f}s: {e}")
            
            # Store failure metrics
            await store_task_metrics(task_name, duration, "failure")
            raise
    
    return wrapper
```

### 2. Resource Usage Monitoring

**System Resource Monitoring**:
```python
import psutil
import asyncio

class ResourceMonitor:
    def __init__(self):
        self.monitoring = False
    
    async def start_monitoring(self):
        """Start background resource monitoring"""
        self.monitoring = True
        
        while self.monitoring:
            try:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                metrics = {
                    "timestamp": datetime.utcnow(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent,
                    "active_tasks": len(asyncio.all_tasks())
                }
                
                # Alert if resources are high
                if cpu_percent > 80 or memory.percent > 80:
                    await self._send_resource_alert(metrics)
                
                # Store metrics
                await self._store_resource_metrics(metrics)
                
                await asyncio.sleep(10)  # Monitor every 10 seconds
                
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                await asyncio.sleep(30)  # Back off on error
```

## Testing Background Tasks

### 1. Testing Async Tasks

**Async Task Testing**:
```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_video_processing_task():
    """Test video processing background task"""
    
    # Setup test data
    video_id = "test-video-123"
    test_video_path = "test_files/sample.mp4"
    
    # Create mock services
    ground_truth_service = GroundTruthService()
    
    # Execute task
    result = await ground_truth_service.process_video_async(
        video_id, test_video_path
    )
    
    # Assert results
    assert result is not None
    # Verify database updates
    # Check generated files
```

### 2. Mocking Background Services

**Mock Background Services for Testing**:
```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
async def mock_background_services():
    """Mock background services for testing"""
    with patch('services.ground_truth_service.GroundTruthService') as mock_gt:
        mock_gt.return_value.process_video_async = AsyncMock(return_value={"status": "completed"})
        yield mock_gt
```
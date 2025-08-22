# AI Model Validation Platform - System Architecture

## 🏛️ High-Level Architecture

The AI Model Validation Platform is a containerized microservices architecture designed for real-time AI/ML model validation through video processing and annotation.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   ML Pipeline   │
│  (React/TS)     │◄──►│   (FastAPI)     │◄──►│   (PyTorch)     │
│  Port: 3000     │    │   Port: 8000    │    │   YOLO Models   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WebSocket     │    │   PostgreSQL    │    │  File System    │
│  (Socket.IO)    │    │   Port: 5432    │    │  (Uploads/ML)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔄 Component Interaction Flow

### **1. Video Processing Pipeline**
```
Video Upload → Security Validation → Chunked Storage → Metadata Extraction
     ↓
Background Processing → Frame Extraction → YOLO Inference → Detection Storage
     ↓
WebSocket Notification → Frontend Update → User Visualization
```

### **2. Real-time Detection Flow**
```
Live Video Stream → Frame Buffer → ML Inference → Confidence Filter
     ↓
NMS Processing → Tracking Algorithm → Database Storage → WebSocket Broadcast
     ↓
Frontend Overlay → User Annotation → Ground Truth Validation
```

## 🧠 ML Detection Architecture

### **Detection Pipeline Components**

#### **1. Model Management Layer**
```python
ModelRegistry
├── YOLOv8n (6.5MB) - Speed optimized
├── YOLOv11l (51MB) - Accuracy optimized  
├── Model Caching - In-memory model storage
├── Device Selection - GPU/CPU automatic fallback
└── Hot Swapping - Runtime model switching
```

#### **2. Processing Pipeline**
```python
VideoProcessor → FrameExtractor → Preprocessor → YOLOInference
     ↓              ↓              ↓              ↓
FrameBuffer    FrameSkipping   Resize/Norm    Confidence
     ↓              ↓              ↓              ↓
Timestamp      Every5thFrame   640x640        Ultra-low(0.01)
```

#### **3. VRU Detection Classes**
```python
VRU_CLASSES = {
    0: "pedestrian",      # COCO person class
    1: "cyclist",         # COCO bicycle class  
    3: "motorcyclist",    # COCO motorcycle class
    67: "wheelchair_user", # Custom mapping
    # Additional context-based classes
}
```

### **Confidence Processing Strategy**
```python
# Multi-stage confidence filtering
Raw YOLO Output (0.001-1.0)
    ↓
VRU Class Filter (person/bicycle/motorcycle only)
    ↓  
Confidence Threshold (0.01 debug / 0.5 production)
    ↓
Size Validation (min 10x20 pixels)
    ↓
Aspect Ratio Check (1.0-5.0 for pedestrians)
    ↓
NMS Processing (IoU 0.45)
    ↓
Enhancement Boost (+0.05 for children, +0.03 for human ratios)
```

## 🗂️ Service Architecture

### **Backend Services Hierarchy**

#### **Core Services**
1. **DetectionPipelineService** - Main detection orchestration
   - Model registry management
   - Real-time inference coordination
   - VRU classification and mapping
   - Performance monitoring

2. **GroundTruthService** - Automated annotation generation
   - Background video processing
   - ML-based ground truth creation
   - Validation and quality control
   - Database persistence

3. **VideoLibraryService** - Video asset management
   - Upload processing and validation
   - Metadata extraction and indexing
   - Quality assessment
   - Storage optimization

#### **Enhanced Services**
4. **EnhancedDetectionService** - Multi-strategy detection
   - YOLO + OpenCV hybrid approach
   - Fallback detection mechanisms
   - HOG people detector backup

5. **EnhancedMLService** - Advanced ML pipeline
   - Multi-model ensemble
   - Performance benchmarking
   - Advanced preprocessing

6. **VideoProcessingWorkflow** - Workflow orchestration
   - Pipeline coordination
   - Error recovery mechanisms
   - Progress tracking

### **API Router Architecture**
```python
FastAPI Application
├── /api/projects        # ProjectRouter
├── /api/videos         # VideoRouter  
├── /api/detection      # DetectionRouter
├── /api/ground-truth   # GroundTruthRouter
├── /api/test-sessions  # TestSessionRouter
├── /api/dashboard      # DashboardRouter
├── /api/annotations    # AnnotationRouter
└── /health            # HealthRouter
```

## 🎯 Frontend Component Architecture

### **Page Components**
```typescript
App.tsx
├── Dashboard.tsx         # Main analytics dashboard
├── ProjectDetail.tsx     # Project management interface
├── VideoAnnotation.tsx   # Video annotation workspace
├── TestExecution.tsx     # Test running interface
├── Settings.tsx          # Configuration management
└── GroundTruth.tsx      # Ground truth visualization
```

### **Shared Components**
```typescript
components/
├── video/
│   ├── VideoPlayer.tsx           # Custom video player
│   ├── AnnotationOverlay.tsx     # Detection bounding boxes
│   └── FrameControls.tsx         # Frame navigation
├── detection/
│   ├── DetectionResults.tsx      # Detection list/grid
│   ├── ConfidenceSlider.tsx      # Threshold controls
│   └── ClassFilter.tsx           # VRU class filtering
├── ui/
│   ├── ErrorBoundary.tsx         # Error handling
│   ├── LoadingSpinner.tsx        # Loading states
│   └── StatusIndicator.tsx       # System status
└── charts/
    ├── PerformanceChart.tsx      # Performance metrics
    ├── AccuracyChart.tsx         # Detection accuracy
    └── TimelineChart.tsx         # Temporal analysis
```

### **Custom Hooks**
```typescript
hooks/
├── useWebSocket.ts       # WebSocket connection management
├── useDetection.ts       # Detection state management
├── useVideoPlayer.ts     # Video player controls
├── useAnnotation.ts      # Annotation workflow
├── usePerformance.ts     # Performance monitoring
└── useErrorHandling.ts   # Error boundary management
```

## 💾 Data Flow Architecture

### **Upload Pipeline**
```
User Selects Video → FileValidator → ChunkedUploader → MetadataExtractor
     ↓                    ↓             ↓              ↓
SecurityCheck    FormatValidation  ProgressTracking  DatabaseRecord
     ↓                    ↓             ↓              ↓
TempStorage     SizeValidation    WebSocketUpdate   VideoEntity
     ↓                    ↓             ↓              ↓
Processing      PathValidation    UIUpdate        GroundTruthTrigger
```

### **Detection Processing Pipeline**
```
Video Input → Frame Extraction → Batch Processing → Model Inference
     ↓             ↓               ↓                ↓
OpenCV        Every5thFrame    GPU/CPU Queue     YOLO Forward
     ↓             ↓               ↓                ↓
BGR→RGB       Timestamp        Memory Pool       Confidence
     ↓             ↓               ↓                ↓
Resize        Frame Number     Async Exec        BoundingBox
     ↓             ↓               ↓                ↓
Normalize     Buffer Mgmt      Exception         PostProcess
                                Handling             ↓
                                   ↓           Database Store
                              Error Recovery       ↓
                                   ↓           WebSocket Event
                              Retry Logic          ↓
                                              Frontend Update
```

## 🔗 Integration Points

### **Internal Integrations**
1. **Backend ↔ Database**: SQLAlchemy ORM with connection pooling
2. **Backend ↔ ML Pipeline**: Direct Python integration
3. **Frontend ↔ Backend**: Axios HTTP client with error handling
4. **Frontend ↔ WebSocket**: Socket.IO for real-time updates

### **External Integrations**
1. **CVAT Integration**: Computer Vision Annotation Tool
2. **Docker Integration**: Container orchestration
3. **File System**: Video storage and model caching
4. **GPU Support**: CUDA acceleration when available

## ⚡ Performance Architecture

### **Optimization Strategies**
1. **Frame Skipping**: Process every 5th frame (5x speed improvement)
2. **Batch Processing**: Multiple frames per inference call
3. **Model Caching**: In-memory model storage
4. **Connection Pooling**: Database connection optimization
5. **Async Processing**: Non-blocking I/O operations
6. **Memory Pooling**: Efficient memory management

### **Monitoring & Metrics**
```python
PerformanceMonitor
├── Inference Time (<50ms target)
├── Memory Usage (GPU/CPU tracking)
├── Detection Accuracy (confidence distribution)
├── Processing Rate (FPS throughput)
├── Error Rates (failure tracking)
└── Resource Utilization (system monitoring)
```

## 🛡️ Security Architecture

### **Security Layers**
1. **Input Validation**: File type, size, and content validation
2. **Path Security**: Directory traversal prevention
3. **Authentication**: JWT token-based access control
4. **CORS Protection**: Origin validation and header controls
5. **Container Security**: Non-root execution, minimal attack surface

### **Security Implementation**
```python
SecurityValidator
├── FileExtensionCheck (.mp4, .avi, .mov, .mkv)
├── FileSizeLimit (100MB maximum)
├── PathTraversalPrevention (../../../ blocked)
├── ContentTypeValidation (MIME type verification)
└── VirusScanIntegration (placeholder for production)
```

## 📊 Monitoring & Observability

### **System Monitoring**
1. **Health Checks**: Container and service health endpoints
2. **Metrics Collection**: Performance and usage statistics
3. **Log Aggregation**: Centralized logging with correlation IDs
4. **Error Tracking**: Exception monitoring and alerting

### **Business Metrics**
1. **Detection Accuracy**: Per-class accuracy tracking
2. **Processing Throughput**: Videos processed per hour
3. **User Engagement**: Annotation completion rates
4. **System Performance**: Response times and resource usage

## 🔮 Scalability Design

### **Horizontal Scaling Points**
1. **Backend API**: Multiple FastAPI instances behind load balancer
2. **ML Pipeline**: GPU worker pool for parallel inference
3. **Database**: Read replicas for query scaling
4. **File Storage**: Distributed file system or object storage
5. **WebSocket**: Socket.IO clustering for real-time scaling

### **Performance Targets**
- **Inference Time**: <30ms per frame
- **Concurrent Users**: 100+ simultaneous users
- **Video Processing**: 4K resolution support
- **Real-time Processing**: 30fps live streams
- **Database Performance**: <100ms query response times

---

*Architecture Version: 2.4.1*  
*Last Updated: August 22, 2025*  
*Reviewed by: Multi-Agent Swarm Analysis*
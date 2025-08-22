# Adaptable Components for Video Annotation System

## Overview

Based on the Label Studio architecture analysis, this document identifies specific components and patterns that can be adapted for our video annotation and camera validation system. These components provide proven, production-ready solutions that can be modified for video-specific requirements.

## 1. Core Database Models (Adaptable)

### 1.1 Project Management Models

**Directly Adaptable:**
```python
# From Label Studio's Project model
class CameraValidationProject(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    organization = models.ForeignKey('Organization')
    
    # Video-specific configurations
    validation_config = models.JSONField(default=dict)  # Replaces label_config
    camera_feeds = models.ManyToManyField('CameraFeed')
    
    # Inherited patterns
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    is_published = models.BooleanField(default=False)
    maximum_validations = models.IntegerField(default=1)
    
    # Sampling strategies for video validation
    TEMPORAL_SAMPLING = 'temporal'
    RANDOM_SAMPLING = 'random' 
    ANOMALY_SAMPLING = 'anomaly'
    
    sampling = models.CharField(
        max_length=100,
        choices=[
            (TEMPORAL_SAMPLING, 'Sequential temporal sampling'),
            (RANDOM_SAMPLING, 'Random frame sampling'),
            (ANOMALY_SAMPLING, 'Anomaly-driven sampling')
        ],
        default=TEMPORAL_SAMPLING
    )
```

**Key Adaptations:**
- Replace `label_config` with `validation_config` for video validation rules
- Add camera feed relationships
- Implement video-specific sampling strategies
- Maintain user permission and organization patterns

### 1.2 Task Management Models

**Task Model Adaptation:**
```python
# Based on Label Studio's Task model
class VideoValidationTask(models.Model):
    # Core task data - adapted for video
    video_data = models.JSONField(
        help_text='Video segment data including timestamps, camera info, etc.'
    )
    
    # Inherited from Label Studio pattern
    project = models.ForeignKey('CameraValidationProject')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    is_validated = models.BooleanField(default=False)  # Replaces is_labeled
    
    # Video-specific fields
    camera_feed = models.ForeignKey('CameraFeed')
    start_timestamp = models.DateTimeField()
    end_timestamp = models.DateTimeField()
    frame_count = models.IntegerField()
    video_url = models.URLField()
    
    # Performance counters (inherited pattern)
    total_validations = models.IntegerField(default=0)
    total_predictions = models.IntegerField(default=0)
    
    def get_video_segment_url(self):
        """Generate time-bounded video URL"""
        return f"{self.video_url}?t={self.start_timestamp}&duration={self.duration}"
```

**Validation Model (replaces Annotation):**
```python
class VideoValidation(models.Model):
    # Core validation result
    result = models.JSONField(
        help_text='Validation results: detections, classifications, etc.'
    )
    
    task = models.ForeignKey('VideoValidationTask', related_name='validations')
    project = models.ForeignKey('CameraValidationProject')
    
    # User tracking
    validated_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    
    # Validation metadata
    validation_time = models.FloatField(null=True)  # Time spent validating
    confidence_score = models.FloatField(null=True)
    was_skipped = models.BooleanField(default=False)
    
    # Temporal data for video
    frame_annotations = models.JSONField(default=list)
    temporal_segments = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

## 2. Storage Architecture (Highly Adaptable)

### 2.1 Multi-Backend Storage Pattern

**Video Storage Abstraction:**
```python
# Adapted from Label Studio's io_storages pattern
class VideoStorageBackend:
    """Base class for video storage backends"""
    
    def store_video_segment(self, camera_id, timestamp, video_data):
        raise NotImplementedError
    
    def get_video_url(self, camera_id, timestamp, duration=None):
        raise NotImplementedError
    
    def generate_presigned_url(self, video_path, ttl=3600):
        raise NotImplementedError

class S3VideoStorage(VideoStorageBackend):
    """S3-based video storage with HLS streaming support"""
    
    def __init__(self, bucket_name, region):
        self.bucket_name = bucket_name
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)
    
    def store_video_segment(self, camera_id, timestamp, video_data):
        key = f"cameras/{camera_id}/segments/{timestamp}.mp4"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=video_data,
            ContentType='video/mp4'
        )
        return key
    
    def generate_presigned_url(self, video_path, ttl=3600):
        return self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': video_path},
            ExpiresIn=ttl
        )

class LocalVideoStorage(VideoStorageBackend):
    """Local filesystem storage for development"""
    
    def store_video_segment(self, camera_id, timestamp, video_data):
        path = f"{settings.MEDIA_ROOT}/videos/{camera_id}/{timestamp}.mp4"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(video_data)
        return path
```

### 2.2 Video Resolution and Access

**Task URL Resolution (adapted pattern):**
```python
class VideoValidationTask(models.Model):
    # ... other fields
    
    def resolve_video_uri(self):
        """Resolve video URI with proper authentication and streaming"""
        storage = self.get_storage_backend()
        if storage:
            return {
                'streaming_url': storage.get_streaming_url(self.video_path),
                'download_url': storage.generate_presigned_url(self.video_path),
                'thumbnail_url': storage.get_thumbnail_url(self.video_path),
                'hls_manifest': storage.get_hls_manifest(self.video_path)
            }
        return None
```

## 3. ML Integration Architecture (Directly Adaptable)

### 3.1 ML Backend Pattern

**Computer Vision ML Backend:**
```python
# Adapted from Label Studio's MLBackend model
class VisionMLBackend(models.Model):
    project = models.ForeignKey('CameraValidationProject')
    
    # Connection details
    url = models.URLField(help_text='Computer vision model server URL')
    title = models.CharField(max_length=255, default='CV Model')
    model_type = models.CharField(
        max_length=50,
        choices=[
            ('object_detection', 'Object Detection'),
            ('pose_estimation', 'Pose Estimation'),
            ('activity_recognition', 'Activity Recognition'),
            ('anomaly_detection', 'Anomaly Detection'),
            ('face_recognition', 'Face Recognition'),
        ]
    )
    
    # Model configuration
    confidence_threshold = models.FloatField(default=0.5)
    input_resolution = models.CharField(max_length=20, default='640x480')
    batch_size = models.IntegerField(default=1)
    
    # Performance settings
    timeout = models.FloatField(default=30.0)  # Higher for video processing
    max_frames_per_request = models.IntegerField(default=10)
    
    def predict_video_segment(self, task):
        """Predict on video segment"""
        api = VisionMLApi(
            url=self.url,
            timeout=self.timeout,
            model_type=self.model_type
        )
        
        frames = self.extract_frames(task)
        predictions = api.predict_frames(frames, task.project.validation_config)
        
        return self.format_predictions(predictions, task)
    
    def extract_frames(self, task):
        """Extract frames from video segment"""
        # Use OpenCV or similar to extract frames
        import cv2
        cap = cv2.VideoCapture(task.video_url)
        frames = []
        
        frame_interval = (task.end_timestamp - task.start_timestamp).total_seconds() / 10
        current_time = 0
        
        while current_time < task.duration:
            cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
            ret, frame = cap.read()
            if ret:
                frames.append({
                    'timestamp': task.start_timestamp + timedelta(seconds=current_time),
                    'frame_data': cv2.imencode('.jpg', frame)[1].tobytes()
                })
            current_time += frame_interval
        
        return frames
```

### 3.2 Prediction Storage

**Video Prediction Model:**
```python
class VideoPrediction(models.Model):
    task = models.ForeignKey('VideoValidationTask', related_name='predictions')
    project = models.ForeignKey('CameraValidationProject')
    ml_backend = models.ForeignKey('VisionMLBackend')
    
    # Prediction results with temporal data
    result = models.JSONField(help_text='Frame-by-frame predictions')
    confidence_scores = models.JSONField(default=list)
    model_version = models.CharField(max_length=255)
    
    # Temporal tracking
    frame_predictions = models.JSONField(default=list)
    temporal_consistency_score = models.FloatField(null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['task', 'model_version']),
            models.Index(fields=['project', 'created_at']),
        ]
```

## 4. API Architecture (Fully Adaptable)

### 4.1 RESTful API Design

**Video Task API:**
```python
# Adapted from Label Studio's task serializers and views
class VideoValidationTaskSerializer(serializers.ModelSerializer):
    video_urls = serializers.SerializerMethodField()
    prediction_count = serializers.IntegerField(read_only=True)
    validation_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = VideoValidationTask
        fields = [
            'id', 'camera_feed', 'start_timestamp', 'end_timestamp',
            'video_urls', 'is_validated', 'prediction_count',
            'validation_count', 'frame_count'
        ]
    
    def get_video_urls(self, obj):
        """Get streaming and download URLs"""
        return obj.resolve_video_uri()

class VideoValidationTaskViewSet(viewsets.ModelViewSet):
    queryset = VideoValidationTask.objects.all()
    serializer_class = VideoValidationTaskSerializer
    permission_classes = [ProjectPermission]
    
    @action(detail=True, methods=['get'])
    def stream(self, request, pk=None):
        """Get video streaming URL"""
        task = self.get_object()
        urls = task.resolve_video_uri()
        return Response(urls)
    
    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        """Submit validation for video segment"""
        task = self.get_object()
        
        serializer = VideoValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validation = serializer.save(
            task=task,
            validated_by=request.user,
            project=task.project
        )
        
        # Update task status
        task.update_validation_status()
        
        return Response(VideoValidationSerializer(validation).data)
```

### 4.2 Real-time API Endpoints

**WebSocket for Live Feeds:**
```python
# Camera feed WebSocket consumer
class CameraFeedConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.camera_id = self.scope['url_route']['kwargs']['camera_id']
        self.camera_group = f'camera_{self.camera_id}'
        
        # Check permissions
        if not await self.has_camera_permission():
            await self.close()
            return
        
        await self.channel_layer.group_add(
            self.camera_group,
            self.channel_name
        )
        await self.accept()
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data['type'] == 'request_frame':
            # Send current frame
            frame_data = await self.get_current_frame()
            await self.send(text_data=json.dumps({
                'type': 'frame_data',
                'frame': frame_data,
                'timestamp': timezone.now().isoformat()
            }))
        
        elif data['type'] == 'create_task':
            # Create validation task from current video
            task = await self.create_validation_task(data)
            await self.send(text_data=json.dumps({
                'type': 'task_created',
                'task_id': task.id
            }))
```

## 5. Frontend Components (Adaptable with Modifications)

### 5.1 Video Player Component

**Adapted from Label Studio's media components:**
```typescript
// VideoAnnotationPlayer component
interface VideoPlayerProps {
  videoUrl: string;
  annotations: VideoAnnotation[];
  onTimeUpdate: (currentTime: number) => void;
  onAnnotationCreate: (annotation: VideoAnnotation) => void;
}

export const VideoAnnotationPlayer: React.FC<VideoPlayerProps> = ({
  videoUrl, annotations, onTimeUpdate, onAnnotationCreate
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  // Timeline annotation overlay
  const handleTimelineClick = (time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
    }
  };
  
  // Frame-by-frame navigation
  const goToNextFrame = () => {
    if (videoRef.current) {
      const frameRate = 30; // or detect from video
      videoRef.current.currentTime += 1 / frameRate;
    }
  };
  
  return (
    <div className="video-annotation-player">
      <video
        ref={videoRef}
        src={videoUrl}
        onTimeUpdate={(e) => {
          const time = e.currentTarget.currentTime;
          setCurrentTime(time);
          onTimeUpdate(time);
        }}
        controls
      />
      
      <AnnotationTimeline
        duration={videoRef.current?.duration || 0}
        currentTime={currentTime}
        annotations={annotations}
        onTimeClick={handleTimelineClick}
      />
      
      <AnnotationTools
        currentTime={currentTime}
        onAnnotationCreate={onAnnotationCreate}
      />
    </div>
  );
};
```

### 5.2 Task Management Interface

**Adapted from Label Studio's data manager:**
```typescript
// VideoTaskManager component
export const VideoTaskManager: React.FC = () => {
  const [tasks, setTasks] = useState<VideoValidationTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<VideoValidationTask | null>(null);
  
  const { data: tasksData } = useQuery({
    queryKey: ['video-tasks'],
    queryFn: () => api.getVideoTasks()
  });
  
  return (
    <div className="video-task-manager">
      <TaskFilters />
      
      <TaskList
        tasks={tasks}
        onTaskSelect={setSelectedTask}
        columns={[
          'camera_feed',
          'start_timestamp',
          'duration',
          'validation_status',
          'prediction_confidence'
        ]}
      />
      
      {selectedTask && (
        <VideoValidationModal
          task={selectedTask}
          onValidationComplete={(validation) => {
            // Update task status
            // Refresh task list
          }}
        />
      )}
    </div>
  );
};
```

## 6. Authentication & Permissions (Directly Adaptable)

### 6.1 Camera Access Control

**Permission Model:**
```python
class CameraPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    camera_feed = models.ForeignKey('CameraFeed')
    
    # Permission levels
    CAN_VIEW = 'view'
    CAN_VALIDATE = 'validate'
    CAN_MANAGE = 'manage'
    
    permission_level = models.CharField(
        max_length=20,
        choices=[
            (CAN_VIEW, 'Can view live feed'),
            (CAN_VALIDATE, 'Can create validations'),
            (CAN_MANAGE, 'Can manage camera settings'),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'camera_feed']

# DRF Permission class
class CameraAccessPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(obj, CameraFeed):
            return CameraPermission.objects.filter(
                user=request.user,
                camera_feed=obj,
                permission_level__in=[
                    CameraPermission.CAN_VIEW,
                    CameraPermission.CAN_VALIDATE,
                    CameraPermission.CAN_MANAGE
                ]
            ).exists()
        return False
```

## 7. Data Migration Utilities (Adaptable)

### 7.1 Video Import Pipeline

**Batch Video Import (adapted from Label Studio's import system):**
```python
class VideoImportManager:
    def __init__(self, project, storage_backend):
        self.project = project
        self.storage_backend = storage_backend
    
    def import_video_directory(self, directory_path, camera_feed):
        """Import video files from directory structure"""
        
        for video_file in self.find_video_files(directory_path):
            # Extract metadata
            metadata = self.extract_video_metadata(video_file)
            
            # Create validation task
            task = VideoValidationTask.objects.create(
                project=self.project,
                camera_feed=camera_feed,
                start_timestamp=metadata['start_time'],
                end_timestamp=metadata['end_time'],
                frame_count=metadata['frame_count'],
                video_data={
                    'file_path': video_file,
                    'resolution': metadata['resolution'],
                    'codec': metadata['codec'],
                    'fps': metadata['fps']
                }
            )
            
            # Upload to storage
            video_url = self.storage_backend.store_video_segment(
                camera_feed.id,
                metadata['start_time'],
                open(video_file, 'rb').read()
            )
            
            task.video_url = video_url
            task.save()
            
            # Generate ML predictions if backend is configured
            if self.project.ml_backends.exists():
                for ml_backend in self.project.ml_backends.all():
                    ml_backend.predict_video_segment(task)
```

## 8. Performance Optimizations (Directly Applicable)

### 8.1 Database Optimizations

**Query Optimization Patterns:**
```python
# Efficient task querying with prefetch
class VideoValidationTaskQuerySet(models.QuerySet):
    def with_validation_counts(self):
        return self.annotate(
            validation_count=Count('validations'),
            prediction_count=Count('predictions'),
            avg_confidence=Avg('predictions__confidence_scores')
        )
    
    def for_camera(self, camera_feed):
        return self.filter(camera_feed=camera_feed)
    
    def pending_validation(self):
        return self.filter(is_validated=False)
    
    def with_temporal_range(self, start_time, end_time):
        return self.filter(
            start_timestamp__gte=start_time,
            end_timestamp__lte=end_time
        )

# Efficient bulk operations
def bulk_create_tasks_from_video_stream(camera_feed, video_segments):
    """Create multiple tasks efficiently"""
    tasks = []
    for segment in video_segments:
        tasks.append(VideoValidationTask(
            project=camera_feed.project,
            camera_feed=camera_feed,
            **segment
        ))
    
    VideoValidationTask.objects.bulk_create(tasks, batch_size=100)
```

### 8.2 Caching Strategy

**Redis Caching for Video Metadata:**
```python
class VideoTaskCache:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL)
    
    def cache_video_metadata(self, task_id, metadata):
        """Cache video metadata for fast access"""
        key = f"video_metadata:{task_id}"
        self.redis_client.setex(
            key,
            3600,  # 1 hour TTL
            json.dumps(metadata)
        )
    
    def get_cached_metadata(self, task_id):
        """Get cached video metadata"""
        key = f"video_metadata:{task_id}"
        data = self.redis_client.get(key)
        return json.loads(data) if data else None
    
    def cache_ml_predictions(self, task_id, predictions):
        """Cache ML predictions to avoid recomputation"""
        key = f"ml_predictions:{task_id}"
        self.redis_client.setex(
            key,
            7200,  # 2 hours TTL
            json.dumps(predictions)
        )
```

## 9. Summary of Adaptable Components

### Directly Usable (Minimal Changes):
1. **Organization/User Management** - Multi-tenancy patterns
2. **Permission System** - Role-based access control
3. **API Architecture** - DRF patterns and serializers
4. **Storage Abstraction** - Multi-backend storage pattern
5. **ML Integration Pattern** - Pluggable ML backends
6. **Caching Strategy** - Redis-based performance optimization

### Adaptable (Moderate Changes):
1. **Task Management Models** - Replace text/image focus with video
2. **Annotation Storage** - Adapt for temporal/video annotations
3. **Frontend Components** - Adapt UI components for video
4. **Import/Export System** - Modify for video file handling
5. **Quality Control** - Adapt agreement metrics for video validation

### Video-Specific Additions Needed:
1. **Real-time Streaming** - WebSocket/WebRTC for live feeds
2. **Temporal Annotation** - Frame-by-frame and segment annotation
3. **Video Processing** - Frame extraction, encoding, streaming
4. **Camera Management** - Live feed management and monitoring
5. **Alert System** - Real-time anomaly detection and notifications

This analysis provides a clear roadmap for implementing our video annotation system by leveraging Label Studio's proven architectural patterns while adapting them for video-specific requirements.
# SPARC PSEUDOCODE PHASE
## Algorithm Design for Video Playback and Detection Integration Fixes

### Algorithm 1: Video Playback Frame Rate Fix

```pseudocode
FUNCTION fixVideoPlaybackFrameRate(video, videoRef):
    // Get accurate video metadata
    videoMetadata = await getVideoMetadata(video.url)
    actualFPS = videoMetadata.frameRate || extractFPSFromHeaders(video.url)
    actualDuration = videoMetadata.duration
    totalFrames = videoMetadata.frameCount
    
    // Update component state with accurate values
    setFrameRate(actualFPS)
    setDuration(actualDuration) 
    setTotalFrames(totalFrames)
    
    // Configure video element with proper settings
    videoElement = videoRef.current
    videoElement.setAttribute('preload', 'metadata')
    videoElement.setAttribute('playsinline', true)
    
    // Add error recovery for loading failures
    videoElement.addEventListener('error', handleVideoError)
    videoElement.addEventListener('stalled', handleVideoStall)
    videoElement.addEventListener('loadedmetadata', onMetadataLoaded)
    
    // Progressive loading strategy
    IF video.size > LARGE_VIDEO_THRESHOLD:
        enableProgressiveLoading(videoElement)
    
    RETURN {fps: actualFPS, duration: actualDuration, frames: totalFrames}

FUNCTION handleVideoError(event):
    errorType = event.target.error.code
    SWITCH errorType:
        CASE MEDIA_ERR_NETWORK:
            retryVideoLoad(event.target, 3)
        CASE MEDIA_ERR_DECODE:
            fallbackToCompatibleFormat(event.target)
        CASE MEDIA_ERR_SRC_NOT_SUPPORTED:
            showUnsupportedFormatError()
        DEFAULT:
            showGenericVideoError()

FUNCTION retryVideoLoad(videoElement, maxRetries):
    FOR attempt = 1 to maxRetries:
        await delay(attempt * 1000) // Exponential backoff
        videoElement.load()
        IF videoElement.readyState >= HAVE_METADATA:
            RETURN SUCCESS
    RETURN FAILURE
```

### Algorithm 2: Pydantic VideoId Validation Fix

```pseudocode
FUNCTION createFlexibleVideoIdValidator():
    // Create Pydantic field that accepts multiple formats
    
    DEFINE VideoIdField AS Field:
        validation_alias = AliasChoices('videoId', 'video_id', 'id')
        serialization_alias = 'videoId'
        description = "Video identifier (accepts videoId, video_id, or id)"
    
    DEFINE DetectionRequestModel AS BaseModel:
        video_id: str = VideoIdField
        
        // Custom validator for backward compatibility
        @field_validator('video_id', mode='before')
        FUNCTION validate_video_id(cls, value, info):
            IF isinstance(value, dict):
                // Extract from nested object if needed
                RETURN value.get('videoId') OR value.get('video_id') OR value.get('id')
            RETURN value
        
        // Ensure output consistency  
        @field_serializer('video_id')
        FUNCTION serialize_video_id(value):
            RETURN {'videoId': value, 'video_id': value}

FUNCTION updateApiEndpoints():
    // Frontend API calls normalization
    FUNCTION callDetectionAPI(videoData):
        // Normalize video identifier across all API calls
        normalizedRequest = {
            'videoId': videoData.id || videoData.videoId || videoData.video_id,
            'video_id': videoData.id || videoData.videoId || videoData.video_id,
            ...otherFields
        }
        
        TRY:
            response = await api.post('/detection/process', normalizedRequest)
            RETURN response.data
        CATCH ValidationError as e:
            // Log validation details for debugging
            logValidationError(e, normalizedRequest)
            THROW new ApiValidationError(e.message, e.field_errors)

FUNCTION migrateExistingData():
    // Database migration to ensure consistency
    FOR record IN detection_events_table:
        IF record.video_id IS NOT NULL AND record.videoId IS NULL:
            UPDATE detection_events SET videoId = record.video_id WHERE id = record.id
        ELSE IF record.videoId IS NOT NULL AND record.video_id IS NULL:
            UPDATE detection_events SET video_id = record.videoId WHERE id = record.id
```

### Algorithm 3: Session Statistics Synchronization

```pseudocode
FUNCTION synchronizeSessionStatistics(testSessionId):
    // Query all related data sources
    detectionEvents = await queryDetectionEvents(testSessionId)
    annotations = await queryAnnotations(testSessionId) 
    groundTruthObjects = await queryGroundTruthObjects(testSessionId)
    
    // Create unified annotation count
    totalAnnotations = 0
    annotationsByType = {}
    
    // Count detection events as annotations
    FOR event IN detectionEvents:
        totalAnnotations += 1
        vruType = event.vru_type || event.class_label
        annotationsByType[vruType] = annotationsByType[vruType] + 1 || 1
    
    // Include manual annotations
    FOR annotation IN annotations:
        IF NOT hasCorrespondingDetectionEvent(annotation):
            totalAnnotations += 1
            annotationsByType[annotation.vru_type] += 1
    
    // Update session statistics table
    sessionStats = {
        test_session_id: testSessionId,
        total_annotations: totalAnnotations,
        annotations_by_type: annotationsByType,
        detection_events_count: detectionEvents.length,
        manual_annotations_count: annotations.length,
        ground_truth_count: groundTruthObjects.length,
        updated_at: now()
    }
    
    await upsertSessionStatistics(sessionStats)
    RETURN sessionStats

FUNCTION linkDetectionEventsToAnnotations():
    // Create bidirectional links between detection events and annotations
    
    FOR detectionEvent IN unlinked_detection_events:
        // Try to find corresponding annotation
        matchingAnnotation = findAnnotationByTimeAndBounds(
            detectionEvent.timestamp,
            detectionEvent.bounding_box,
            tolerance_ms = 100
        )
        
        IF matchingAnnotation:
            // Link existing annotation to detection event
            UPDATE annotations SET detection_event_id = detectionEvent.id 
            WHERE id = matchingAnnotation.id
        ELSE:
            // Create annotation from detection event
            newAnnotation = {
                id: generateUUID(),
                video_id: detectionEvent.test_session.video_id,
                frame_number: detectionEvent.frame_number,
                timestamp: detectionEvent.timestamp,
                vru_type: detectionEvent.vru_type,
                bounding_box: {
                    x: detectionEvent.bounding_box_x,
                    y: detectionEvent.bounding_box_y,
                    width: detectionEvent.bounding_box_width,
                    height: detectionEvent.bounding_box_height
                },
                confidence: detectionEvent.confidence,
                detection_event_id: detectionEvent.id,
                validated: false,
                created_at: now()
            }
            await createAnnotation(newAnnotation)

FUNCTION createRealTimeStatsUpdate():
    // WebSocket-based real-time statistics updates
    
    FUNCTION onDetectionEvent(event):
        // Update statistics immediately when detection occurs
        currentStats = await getSessionStatistics(event.test_session_id)
        currentStats.total_annotations += 1
        currentStats.annotations_by_type[event.vru_type] += 1
        
        await updateSessionStatistics(currentStats)
        
        // Broadcast update to connected clients
        websocket.broadcast('session_stats_updated', {
            session_id: event.test_session_id,
            stats: currentStats
        })
    
    // Set up event listeners for real-time updates
    eventBus.on('detection_event_created', onDetectionEvent)
    eventBus.on('annotation_created', onAnnotationEvent)
    eventBus.on('annotation_deleted', onAnnotationDeleted)
```

### Algorithm 4: Dataset Management Population Fix

```pseudocode
FUNCTION populateDatasetManagement():
    // Comprehensive query to get all processed video data
    
    FUNCTION getProcessedVideosWithDetections():
        query = `
        SELECT 
            v.id, v.filename, v.duration, v.fps,
            p.name as project_name, p.id as project_id,
            COUNT(de.id) as detection_count,
            COUNT(DISTINCT de.vru_type) as vru_types_count,
            ts.status as processing_status,
            v.created_at, v.updated_at
        FROM videos v
        LEFT JOIN projects p ON v.project_id = p.id  
        LEFT JOIN test_sessions ts ON ts.video_id = v.id
        LEFT JOIN detection_events de ON de.test_session_id = ts.id
        WHERE v.status = 'uploaded' OR v.status = 'processed'
        GROUP BY v.id, p.id, ts.id
        ORDER BY v.updated_at DESC
        `
        
        RETURN await database.execute(query)
    
    FUNCTION enrichVideoData(videos):
        FOR video IN videos:
            // Get additional metadata
            video.annotations = await getAnnotationSummary(video.id)
            video.ground_truth_objects = await getGroundTruthSummary(video.id)
            video.recent_sessions = await getRecentTestSessions(video.id, limit=5)
            
            // Calculate dataset readiness score
            video.dataset_readiness = calculateDatasetReadiness(video)
            
            // Get file existence and health status
            video.file_status = await checkVideoFileHealth(video.file_path)
        
        RETURN videos
    
    FUNCTION calculateDatasetReadiness(video):
        score = 0
        maxScore = 100
        
        // Scoring criteria
        IF video.detection_count > 0: score += 25
        IF video.annotations.validated_count > 0: score += 25  
        IF video.ground_truth_objects.count > 0: score += 25
        IF video.project_id IS NOT NULL: score += 15
        IF video.file_status === 'healthy': score += 10
        
        RETURN {
            score: score,
            percentage: (score / maxScore) * 100,
            criteria: {
                hasDetections: video.detection_count > 0,
                hasValidatedAnnotations: video.annotations.validated_count > 0,
                hasGroundTruth: video.ground_truth_objects.count > 0,
                hasProject: video.project_id IS NOT NULL,
                fileHealthy: video.file_status === 'healthy'
            }
        }

FUNCTION setupDatasetFiltering():
    // Advanced filtering for dataset management
    
    FUNCTION applyDatasetFilters(filters):
        baseQuery = getProcessedVideosWithDetections()
        
        IF filters.project_id:
            baseQuery.WHERE('v.project_id = ?', filters.project_id)
        
        IF filters.min_detections:
            baseQuery.HAVING('COUNT(de.id) >= ?', filters.min_detections)
        
        IF filters.vru_types:
            baseQuery.WHERE('de.vru_type IN (?)', filters.vru_types)
        
        IF filters.date_range:
            baseQuery.WHERE('v.created_at BETWEEN ? AND ?', 
                filters.date_range.start, filters.date_range.end)
        
        IF filters.dataset_readiness_min:
            // Add subquery for readiness score
            baseQuery.WHERE('dataset_readiness_score >= ?', filters.dataset_readiness_min)
        
        RETURN await baseQuery.execute()
```

### Algorithm 5: Project Association Restoration

```pseudocode
FUNCTION restoreProjectAssociations():
    // Fix missing or broken project associations
    
    FUNCTION createDefaultProject():
        defaultProject = {
            id: 'default-project-uuid',
            name: 'Default Project',
            description: 'Default project for videos without explicit project assignment',
            camera_model: 'Generic',
            camera_view: 'Front-facing VRU',
            signal_type: 'Network Packet',
            status: 'Active',
            owner_id: 'system',
            created_at: now()
        }
        
        existingDefault = await findProjectByName('Default Project')
        IF existingDefault IS NULL:
            await createProject(defaultProject)
            RETURN defaultProject.id
        ELSE:
            RETURN existingDefault.id
    
    FUNCTION assignMissingProjects():
        defaultProjectId = await createDefaultProject()
        
        orphanedVideos = await findVideosWithoutProject()
        
        FOR video IN orphanedVideos:
            // Try to infer project from video metadata or filename
            inferredProjectId = await inferProjectFromVideo(video)
            
            IF inferredProjectId:
                await updateVideoProject(video.id, inferredProjectId)
            ELSE:
                await updateVideoProject(video.id, defaultProjectId)
            
            // Update related test sessions
            await updateTestSessionsProject(video.id, inferredProjectId || defaultProjectId)
    
    FUNCTION inferProjectFromVideo(video):
        // Try to extract project info from filename patterns
        patterns = [
            /project-([a-f0-9-]{36})/i,  // UUID pattern
            /proj_([a-zA-Z0-9_]+)/i,     // Project name pattern  
            /([a-zA-Z0-9_]+)_video/i     // Prefix pattern
        ]
        
        FOR pattern IN patterns:
            match = video.filename.match(pattern)
            IF match:
                projectIdentifier = match[1]
                
                // Try to find existing project
                project = await findProjectByIdOrName(projectIdentifier)
                IF project:
                    RETURN project.id
        
        // Try to infer from upload metadata or user session
        IF video.uploader_id:
            userDefaultProject = await getUserDefaultProject(video.uploader_id)
            IF userDefaultProject:
                RETURN userDefaultProject.id
        
        RETURN null

FUNCTION setupProjectAutoAssignment():
    // Automatic project assignment for new uploads
    
    FUNCTION onVideoUpload(videoData, userContext):
        projectId = null
        
        // Priority 1: Explicit project ID in upload request
        IF videoData.project_id:
            projectId = videoData.project_id
        
        // Priority 2: User's current active project
        ELSE IF userContext.active_project_id:
            projectId = userContext.active_project_id
        
        // Priority 3: User's default project
        ELSE IF userContext.default_project_id:
            projectId = userContext.default_project_id
        
        // Priority 4: System default project
        ELSE:
            projectId = await getOrCreateDefaultProject()
        
        // Validate project exists and user has access
        project = await validateProjectAccess(projectId, userContext.user_id)
        IF NOT project:
            projectId = await getOrCreateDefaultProject()
        
        // Create video with proper project association
        video = await createVideo({
            ...videoData,
            project_id: projectId
        })
        
        // Log project assignment for audit trail
        await logProjectAssignment(video.id, projectId, 'auto_assignment')
        
        RETURN video
```

### Algorithm 6: Detection Start/Stop Controls

```pseudocode
FUNCTION implementDetectionControls():
    // State management for detection control
    
    FUNCTION DetectionControlState():
        state = {
            isDetectionRunning: false,
            isPaused: false,
            progress: {
                currentFrame: 0,
                totalFrames: 0,
                percentage: 0
            },
            detectionResults: [],
            errors: []
        }
        
        FUNCTION startDetection(videoId, config):
            IF state.isDetectionRunning:
                THROW new Error('Detection already running')
            
            state.isDetectionRunning = true
            state.isPaused = false
            state.progress = {currentFrame: 0, totalFrames: 0, percentage: 0}
            state.errors = []
            
            // Initialize WebSocket connection for real-time updates
            websocket = new DetectionWebSocket(videoId)
            websocket.onProgress = updateProgress
            websocket.onDetection = onDetectionFound
            websocket.onError = onDetectionError
            websocket.onComplete = onDetectionComplete
            
            // Start detection process
            await api.post('/detection/start', {
                videoId: videoId,
                config: config
            })
        
        FUNCTION pauseDetection():
            IF NOT state.isDetectionRunning:
                RETURN
            
            state.isPaused = true
            await api.post('/detection/pause')
        
        FUNCTION resumeDetection():
            IF NOT state.isDetectionRunning OR NOT state.isPaused:
                RETURN
            
            state.isPaused = false
            await api.post('/detection/resume')
        
        FUNCTION stopDetection():
            state.isDetectionRunning = false
            state.isPaused = false
            
            IF websocket:
                websocket.close()
            
            await api.post('/detection/stop')
        
        FUNCTION updateProgress(progressData):
            state.progress = {
                currentFrame: progressData.currentFrame,
                totalFrames: progressData.totalFrames,
                percentage: (progressData.currentFrame / progressData.totalFrames) * 100
            }
            
            // Trigger UI update
            notifyStateChange()
        
        FUNCTION onDetectionFound(detection):
            state.detectionResults.push(detection)
            notifyDetectionUpdate(detection)
        
        FUNCTION onDetectionError(error):
            state.errors.push(error)
            notifyErrorUpdate(error)
        
        FUNCTION onDetectionComplete(summary):
            state.isDetectionRunning = false
            state.isPaused = false
            notifyDetectionComplete(summary)

FUNCTION createDetectionControlUI():
    // React component for detection controls
    
    FUNCTION DetectionControlPanel({videoId, onDetectionUpdate}):
        [detectionState, setDetectionState] = useState(new DetectionControlState())
        
        FUNCTION handleStartDetection():
            TRY:
                await detectionState.startDetection(videoId, {
                    confidence_threshold: 0.4,
                    nms_threshold: 0.5,
                    max_detections: 100
                })
            CATCH error:
                showErrorMessage(error.message)
        
        FUNCTION handlePauseResume():
            IF detectionState.isPaused:
                await detectionState.resumeDetection()
            ELSE:
                await detectionState.pauseDetection()
        
        FUNCTION handleStopDetection():
            await detectionState.stopDetection()
        
        RETURN (
            <DetectionControlsContainer>
                <Button 
                    onClick={handleStartDetection}
                    disabled={detectionState.isDetectionRunning}
                    variant="primary"
                >
                    Start Detection
                </Button>
                
                <Button
                    onClick={handlePauseResume}
                    disabled={!detectionState.isDetectionRunning}
                    variant="secondary"
                >
                    {detectionState.isPaused ? 'Resume' : 'Pause'}
                </Button>
                
                <Button
                    onClick={handleStopDetection}
                    disabled={!detectionState.isDetectionRunning}
                    variant="danger"
                >
                    Stop
                </Button>
                
                <ProgressBar 
                    value={detectionState.progress.percentage}
                    label={`${detectionState.progress.currentFrame}/${detectionState.progress.totalFrames} frames`}
                />
                
                <DetectionResults 
                    detections={detectionState.detectionResults}
                    onDetectionSelect={onDetectionUpdate}
                />
            </DetectionControlsContainer>
        )

FUNCTION setupBackendDetectionControl():
    // Backend API endpoints for detection control
    
    detectionSessions = new Map() // sessionId -> DetectionSession
    
    FUNCTION POST_startDetection(request):
        sessionId = generateUUID()
        videoId = request.videoId
        config = request.config
        
        // Validate video exists and is accessible
        video = await getVideo(videoId)
        IF NOT video:
            THROW new NotFoundError('Video not found')
        
        // Create detection session
        session = {
            id: sessionId,
            videoId: videoId,
            config: config,
            status: 'running',
            startedAt: now(),
            currentFrame: 0,
            totalFrames: await getVideoFrameCount(video.file_path),
            detections: [],
            websocket: null
        }
        
        detectionSessions.set(sessionId, session)
        
        // Start background detection task
        asyncio.create_task(runDetectionProcess(session))
        
        RETURN {sessionId: sessionId, status: 'started'}
    
    FUNCTION POST_pauseDetection(sessionId):
        session = detectionSessions.get(sessionId)
        IF NOT session:
            THROW new NotFoundError('Detection session not found')
        
        session.status = 'paused'
        RETURN {status: 'paused'}
    
    FUNCTION POST_resumeDetection(sessionId):
        session = detectionSessions.get(sessionId)
        IF NOT session:
            THROW new NotFoundError('Detection session not found')
        
        session.status = 'running'
        RETURN {status: 'resumed'}
    
    FUNCTION POST_stopDetection(sessionId):
        session = detectionSessions.get(sessionId)
        IF NOT session:
            THROW new NotFoundError('Detection session not found')
        
        session.status = 'stopped'
        detectionSessions.delete(sessionId)
        RETURN {status: 'stopped'}
    
    FUNCTION runDetectionProcess(session):
        TRY:
            pipeline = DetectionPipeline()
            await pipeline.initialize()
            
            video = cv2.VideoCapture(session.video.file_path)
            
            WHILE session.status === 'running':
                ret, frame = video.read()
                IF NOT ret:
                    BREAK
                
                session.currentFrame += 1
                
                // Send progress update
                IF session.websocket:
                    session.websocket.send_progress({
                        currentFrame: session.currentFrame,
                        totalFrames: session.totalFrames
                    })
                
                // Run detection on frame
                detections = await pipeline.process_frame(frame)
                
                // Send detection results
                FOR detection IN detections:
                    session.detections.append(detection)
                    IF session.websocket:
                        session.websocket.send_detection(detection)
                
                // Pause if requested
                WHILE session.status === 'paused':
                    await asyncio.sleep(0.1)
                
                // Stop if requested
                IF session.status === 'stopped':
                    BREAK
            
            video.release()
            session.status = 'completed'
            
            // Send completion notification
            IF session.websocket:
                session.websocket.send_complete({
                    totalDetections: len(session.detections),
                    processingTime: now() - session.startedAt
                })
        
        CATCH Exception as e:
            session.status = 'error'
            IF session.websocket:
                session.websocket.send_error({
                    message: str(e),
                    frame: session.currentFrame
                })
```

### Algorithm Complexity Analysis

#### Time Complexity
- **Video Playback Fix**: O(1) - Metadata loading and configuration
- **Pydantic Validation**: O(1) - Field validation per request
- **Session Statistics**: O(n) - Where n is number of detections/annotations
- **Dataset Population**: O(n*m) - Where n is videos, m is average detections per video  
- **Project Association**: O(n) - Where n is orphaned videos
- **Detection Controls**: O(k) - Where k is frames processed

#### Space Complexity
- **Video Metadata**: O(1) - Fixed size metadata storage
- **Validation Models**: O(1) - Constant model size
- **Statistics Cache**: O(n) - Linear with number of sessions
- **Dataset Cache**: O(n*m) - Videos with enriched metadata
- **Project Mapping**: O(n) - Linear with number of videos
- **Detection Sessions**: O(k) - Active detection sessions

#### Performance Optimizations
1. **Lazy Loading**: Load video metadata only when needed
2. **Caching**: Cache validation results and statistics
3. **Batch Processing**: Process multiple detections in single database transaction
4. **Indexing**: Database indexes on foreign keys and commonly queried fields
5. **WebSocket Throttling**: Limit update frequency to prevent UI flooding
6. **Background Tasks**: Run heavy processing in background threads/tasks

### Error Handling Strategies

#### Graceful Degradation
- Fallback to lower quality video if high quality fails
- Show cached statistics if real-time calculation fails
- Use default project if project inference fails
- Continue detection with reduced features if WebSocket fails

#### Recovery Mechanisms
- Automatic retry with exponential backoff
- State persistence for detection resumption
- Database transaction rollback on failures
- User notification with actionable next steps

#### Monitoring and Alerting
- Performance metrics for each algorithm
- Error rate tracking by component
- User experience monitoring
- System health dashboards
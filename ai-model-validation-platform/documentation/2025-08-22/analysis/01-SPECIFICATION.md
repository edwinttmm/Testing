# SPARC SPECIFICATION PHASE
## Video Playback and Detection Integration Issues Analysis

### Project Context
- **System**: AI Model Validation Platform
- **Branch**: v4 
- **Components**: Frontend (React/TypeScript) + Backend (Python/FastAPI)
- **Core Issue**: Integration failures between video playback and detection pipeline

### Issue Analysis

#### Issue 1: Video Playback Failure After 3 Seconds
**SYMPTOMS:**
- Video: 5.04 seconds duration, 121 frames, 24fps
- Playback stops at 3 seconds
- Frontend VideoAnnotationPlayer component affected

**ROOT CAUSE ANALYSIS:**
- Frame rate mismatch: Video is 24fps but player defaults to 30fps
- Buffer management issues in video loading
- Potential race conditions in video initialization
- Error handling not properly catching video stream issues

**IMPACT:** 
- Users cannot view complete video content
- Detection annotations cannot be properly reviewed
- Quality assurance workflow broken

#### Issue 2: Pydantic videoId Missing Field Errors
**SYMPTOMS:**
- ValidationError: Field 'videoId' is required
- Detection pipeline API calls failing
- Backend unable to process detection requests

**ROOT CAUSE ANALYSIS:**
- API schema mismatch between frontend and backend
- Frontend sending 'video_id' but backend expects 'videoId'  
- Pydantic model validation strict about field names
- Detection processing bypassing validation in some code paths

**IMPACT:**
- Detection pipeline cannot process videos
- API requests fail silently or with unclear errors
- Data consistency issues between frontend and backend

#### Issue 3: Session Stats Show 0 Annotations Despite 24 Detections
**SYMPTOMS:**
- Backend reports 24 successful detections
- Frontend session stats display 0 annotations
- Data persistence gap between detection and annotation storage

**ROOT CAUSE ANALYSIS:**
- Detection events stored in `detection_events` table
- Annotations stored in separate `annotations` table  
- No automatic linking between DetectionEvent and Annotation records
- Session statistics querying wrong table or using wrong foreign keys

**IMPACT:**
- Loss of detection data visibility
- Incorrect performance metrics
- User confusion about system functionality

#### Issue 4: Dataset Management Empty After Processing
**SYMPTOMS:**
- Videos processed successfully
- Detection data exists in database
- Dataset management interface shows no data

**ROOT CAUSE ANALYSIS:**
- Dataset queries not including processed detection data
- UI filtering by wrong status or project fields
- Foreign key relationships not properly established
- Project association missing during video upload

**IMPACT:**
- Data appears lost to users
- Cannot build training datasets from processed videos
- Workflow continuity broken

#### Issue 5: Video Information Shows "Unknown Project"
**SYMPTOMS:**
- Videos uploaded and processed
- Video details display "Unknown Project"
- Project association appears broken

**ROOT CAUSE ANALYSIS:**
- Project foreign key null or pointing to non-existent project
- Default project creation not working
- Video upload process not properly associating with project
- Database migration issues with project relationships

**IMPACT:**
- Data organization compromised
- Cannot filter or group videos by project
- Reporting and analytics broken

#### Issue 6: Missing Start/Stop Controls for Detection
**SYMPTOMS:**
- Detection starts automatically on video load
- No user control over when detection runs
- Cannot pause/resume detection process

**ROOT CAUSE ANALYSIS:**
- Detection triggered on video mount in React component
- No state management for detection control
- WebSocket connection auto-starts on component initialization
- Missing UI controls for detection lifecycle

**IMPACT:**
- Poor user experience
- Unwanted resource consumption
- Cannot selectively run detection on specific video segments

### Requirements Analysis

#### Functional Requirements
1. **Video Playback**
   - Support full video duration playback (5.04s)
   - Accurate frame rate detection and display (24fps)
   - Synchronized timestamp and frame number display
   - Error recovery for video loading failures

2. **API Validation**
   - Consistent field naming between frontend and backend
   - Robust Pydantic validation with clear error messages  
   - Support for both 'videoId' and 'video_id' formats
   - Backward compatibility during migration

3. **Data Persistence**
   - Link detection events to annotation records
   - Accurate session statistics reflecting all data
   - Proper foreign key relationships
   - Atomic transactions for data consistency

4. **Project Management**
   - Automatic project association during upload
   - Default project creation when none exists
   - Proper project-video-detection relationships
   - Migration scripts for existing data

5. **User Controls**
   - Start/stop buttons for detection process
   - Pause/resume detection capabilities
   - Progress indicators for detection status
   - Error handling and user feedback

#### Non-Functional Requirements
1. **Performance**
   - Video loading < 2 seconds
   - Detection processing real-time (24fps)
   - UI responsive during detection
   - Memory usage optimization

2. **Reliability**
   - 99.9% video playback success rate
   - Zero data loss during processing
   - Graceful error handling
   - Recovery from network failures

3. **Usability**
   - Intuitive start/stop controls
   - Clear progress indicators
   - Meaningful error messages
   - Consistent UI behavior

### Acceptance Criteria

#### AC1: Video Playback Restoration
- GIVEN a 5.04s video with 24fps
- WHEN user loads video in annotation player
- THEN video plays completely from 0s to 5.04s
- AND frame counter shows accurate progression
- AND timestamp displays correctly

#### AC2: API Validation Fix
- GIVEN detection request with video identifier
- WHEN backend processes the request  
- THEN accepts both 'videoId' and 'video_id' fields
- AND returns clear error for missing fields
- AND processes detection successfully

#### AC3: Session Statistics Accuracy
- GIVEN video with 24 detections processed
- WHEN user views session statistics
- THEN displays 24 annotations/detections
- AND shows correct counts by VRU type
- AND updates in real-time during processing

#### AC4: Dataset Management Population
- GIVEN processed videos with detection data
- WHEN user opens dataset management
- THEN displays all processed videos
- AND shows detection counts per video
- AND allows filtering by project/status

#### AC5: Project Association Fix
- GIVEN video upload to system
- WHEN video is processed and stored
- THEN appears under correct project
- AND displays project name accurately
- AND maintains association through all operations

#### AC6: Detection Control Implementation
- GIVEN video loaded in annotation player
- WHEN user wants to run detection
- THEN sees start/stop/pause buttons
- AND can control detection timing
- AND receives progress feedback

### Edge Cases and Constraints

#### Edge Cases
1. **Network Interruption**
   - Video upload interrupted mid-process
   - Detection processing network failure
   - WebSocket connection drops

2. **Large Video Files**
   - Videos > 100MB size
   - Videos > 30 seconds duration
   - High resolution videos (4K+)

3. **Concurrent Users**
   - Multiple users processing same video
   - Simultaneous detection requests
   - Database lock contention

#### Constraints
1. **Technical Constraints**
   - Browser memory limitations for video playback
   - Python asyncio limitations for concurrent processing
   - SQLite/PostgreSQL transaction limits

2. **Business Constraints**
   - Processing time budget per video
   - Storage space for screenshots/annotations
   - User session timeout limits

### Dependencies and Integration Points

#### Frontend Dependencies
- VideoAnnotationPlayer component
- useVideoPlayer hook
- Detection WebSocket service
- Session statistics API

#### Backend Dependencies  
- Detection pipeline service
- Video processing workflow
- Pydantic validation models
- Database ORM relationships

#### Integration Points
- Video file upload and storage
- Real-time detection WebSocket
- Annotation data persistence
- Session management state

### Risk Assessment

#### High Risk
- Data loss during migration to fix foreign keys
- Performance degradation during video processing
- Breaking changes to API contracts

#### Medium Risk
- User experience issues during transition
- Temporary inconsistencies in data display
- Browser compatibility with video formats

#### Low Risk
- Minor UI layout adjustments
- Configuration changes for default projects
- Logging and monitoring improvements

### Success Metrics

#### Technical Metrics
- Video playback success rate: 99.9%
- API validation error rate: < 0.1%
- Detection processing latency: < 100ms per frame
- Data consistency rate: 100%

#### User Experience Metrics
- Time to start detection: < 3 seconds
- User error recovery rate: 95%
- Task completion rate: 98%
- User satisfaction score: 4.5/5

### Next Steps for SPARC Process
1. **PSEUDOCODE**: Design algorithms for each fix
2. **ARCHITECTURE**: Plan component interactions and data flow
3. **REFINEMENT**: Implement with TDD approach
4. **COMPLETION**: Integration testing and deployment
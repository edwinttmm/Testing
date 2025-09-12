# SPARC Specification: Annotation System

## 1. System Overview

### 1.1 Purpose
The Annotation System provides comprehensive CRUD operations for video annotations, enabling users to create, manage, and validate bounding boxes, labels, and timestamps for VRU (Vulnerable Road User) detection in video content.

### 1.2 Scope
- Video frame annotation with temporal tracking
- Multi-type VRU labeling (pedestrian, cyclist, motorcyclist, etc.)
- Collaborative annotation sessions
- Validation and quality control workflows
- Export capabilities for multiple formats

### 1.3 Key Components
- Annotation Canvas with drawing tools
- Frame-by-frame navigation
- Bounding box management
- Label classification system
- Session tracking and history

## 2. Functional Requirements

### 2.1 Core Annotation Operations

#### FR-A-2.1.1 Create Annotations
- **Description**: System shall allow users to create new annotations on video frames
- **Priority**: High
- **Acceptance Criteria**:
  - Users can draw bounding boxes on video frames
  - Users can assign VRU type classifications
  - System assigns unique detection IDs (format: DET_[TYPE]_[SEQUENCE])
  - Annotations include frame number and timestamp
  - System validates bounding box coordinates are within frame bounds
- **Input Validation**:
  - Frame number: Integer ≥ 0
  - Timestamp: Float ≥ 0
  - Bounding box: x,y,width,height all > 0
  - VRU type: Must match predefined enum values

#### FR-A-2.1.2 Read/Retrieve Annotations
- **Description**: System shall provide efficient retrieval of annotations
- **Priority**: High
- **Acceptance Criteria**:
  - Retrieve annotations by video ID
  - Filter by frame range, timestamp range, VRU type
  - Support pagination for large datasets
  - Return annotation metadata and bounding box data
  - Include validation status and annotator information
- **Performance Requirements**:
  - Response time < 200ms for frame-based queries
  - Support concurrent access for multiple annotators

#### FR-A-2.1.3 Update Annotations
- **Description**: System shall allow modification of existing annotations
- **Priority**: High
- **Acceptance Criteria**:
  - Users can modify bounding box coordinates
  - Users can change VRU type classification
  - Users can update validation status
  - System tracks modification history with timestamps
  - Only authorized users can validate annotations
- **Business Rules**:
  - Validated annotations require special permission to modify
  - Original annotator and validators can modify annotations
  - All changes logged for audit purposes

#### FR-A-2.1.4 Delete Annotations
- **Description**: System shall support safe deletion of annotations
- **Priority**: Medium
- **Acceptance Criteria**:
  - Soft delete with recovery capability
  - Hard delete for administrative purposes
  - Cascade deletion affects related detection events
  - Audit trail maintained for deleted annotations
  - Confirmation required for batch deletions

### 2.2 Collaborative Annotation

#### FR-A-2.2.1 Annotation Sessions
- **Description**: System shall manage collaborative annotation sessions
- **Priority**: High
- **Acceptance Criteria**:
  - Multiple users can work on same video with conflict resolution
  - Session state persistence across browser refreshes
  - Progress tracking (frames completed, annotations validated)
  - Session handoff between annotators
- **Session Management**:
  - Automatic session creation on video access
  - Session timeout and recovery mechanisms
  - Session statistics and progress metrics

#### FR-A-2.2.2 Real-time Collaboration
- **Description**: System shall provide real-time annotation updates
- **Priority**: Medium
- **Acceptance Criteria**:
  - Live cursor tracking for active annotators
  - Real-time annotation updates via WebSocket
  - Conflict detection and resolution for simultaneous edits
  - Visual indicators for other users' work areas

### 2.3 Validation and Quality Control

#### FR-A-2.3.1 Annotation Validation
- **Description**: System shall provide validation workflows
- **Priority**: High
- **Acceptance Criteria**:
  - Two-stage validation process (annotate → validate)
  - Validation status tracking (pending, approved, rejected)
  - Quality metrics per annotator
  - Validation comments and feedback
- **Quality Metrics**:
  - Inter-annotator agreement calculation
  - Annotation consistency scoring
  - Validation completion rates

#### FR-A-2.3.2 Quality Assurance
- **Description**: System shall detect annotation quality issues
- **Priority**: Medium
- **Acceptance Criteria**:
  - Automatic detection of malformed bounding boxes
  - Consistency checks against ground truth data
  - Flagging of outlier annotations
  - Quality score calculation per annotation

### 2.4 Export and Integration

#### FR-A-2.4.1 Export Formats
- **Description**: System shall export annotations in multiple formats
- **Priority**: Medium
- **Acceptance Criteria**:
  - JSON export with complete metadata
  - COCO format for ML training
  - YOLO format for object detection
  - Pascal VOC format for compatibility
- **Export Options**:
  - Filter by validation status
  - Include/exclude metadata
  - Batch export for multiple videos

#### FR-A-2.4.2 API Integration
- **Description**: System shall provide RESTful API access
- **Priority**: High
- **Acceptance Criteria**:
  - Full CRUD operations via REST API
  - Bulk operations for efficiency
  - Authentication and authorization
  - Rate limiting and error handling

## 3. Non-Functional Requirements

### 3.1 Performance
- **NFR-A-3.1.1**: API response time < 200ms for 95% of requests
- **NFR-A-3.1.2**: Support 50 concurrent annotators
- **NFR-A-3.1.3**: Canvas rendering at 60fps for smooth interaction
- **NFR-A-3.1.4**: Database queries optimized with proper indexing

### 3.2 Usability
- **NFR-A-3.2.1**: Keyboard shortcuts for all drawing tools
- **NFR-A-3.2.2**: Undo/redo functionality with 50-step history
- **NFR-A-3.2.3**: Auto-save every 30 seconds
- **NFR-A-3.2.4**: Responsive design for various screen sizes

### 3.3 Data Integrity
- **NFR-A-3.3.1**: ACID compliance for all database operations
- **NFR-A-3.3.2**: Data validation at API and database levels
- **NFR-A-3.3.3**: Backup and recovery capabilities
- **NFR-A-3.3.4**: Audit logging for all modifications

### 3.4 Security
- **NFR-A-3.4.1**: Role-based access control (RBAC)
- **NFR-A-3.4.2**: Input sanitization and XSS prevention
- **NFR-A-3.4.3**: SQL injection prevention
- **NFR-A-3.4.4**: Secure file upload handling

## 4. Technical Constraints

### 4.1 Technology Stack
- **Frontend**: React with TypeScript
- **Backend**: FastAPI with Python
- **Database**: PostgreSQL with proper indexing
- **Real-time**: Socket.IO for collaboration

### 4.2 Integration Constraints
- Must integrate with existing Video and Project models
- Compatible with Ground Truth generation pipeline
- Support existing authentication system
- Maintain backward compatibility with current API

### 4.3 Data Constraints
- Maximum 10,000 annotations per video
- Bounding box coordinates as normalized floats (0-1)
- UTF-8 encoding for all text fields
- JSON format for complex data structures

## 5. API Endpoint Specifications

### 5.1 Annotation CRUD Operations

```yaml
paths:
  /api/videos/{video_id}/annotations:
    get:
      summary: Retrieve annotations for a video
      parameters:
        - name: video_id
          in: path
          required: true
          schema:
            type: string
        - name: frame_start
          in: query
          schema:
            type: integer
        - name: frame_end
          in: query
          schema:
            type: integer
        - name: vru_type
          in: query
          schema:
            type: string
            enum: [pedestrian, cyclist, motorcyclist, wheelchair, scooter]
        - name: validated
          in: query
          schema:
            type: boolean
      responses:
        200:
          description: List of annotations
          content:
            application/json:
              schema:
                type: object
                properties:
                  annotations:
                    type: array
                    items:
                      $ref: '#/components/schemas/AnnotationResponse'
                  total:
                    type: integer
                  page:
                    type: integer
                  page_size:
                    type: integer
    
    post:
      summary: Create new annotation
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AnnotationCreate'
      responses:
        201:
          description: Annotation created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AnnotationResponse'
        400:
          description: Validation error
        409:
          description: Conflict with existing annotation

  /api/annotations/{annotation_id}:
    get:
      summary: Get specific annotation
      parameters:
        - name: annotation_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Annotation details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AnnotationResponse'
        404:
          description: Annotation not found
    
    put:
      summary: Update annotation
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AnnotationUpdate'
      responses:
        200:
          description: Annotation updated
        404:
          description: Annotation not found
        409:
          description: Validation conflict
    
    delete:
      summary: Delete annotation
      responses:
        204:
          description: Annotation deleted
        404:
          description: Annotation not found
```

### 5.2 Bulk Operations

```yaml
  /api/videos/{video_id}/annotations/bulk:
    post:
      summary: Bulk create annotations
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                annotations:
                  type: array
                  items:
                    $ref: '#/components/schemas/AnnotationCreate'
                validate_immediately:
                  type: boolean
                  default: false
      responses:
        201:
          description: Bulk operation results
          content:
            application/json:
              schema:
                type: object
                properties:
                  created:
                    type: integer
                  failed:
                    type: integer
                  errors:
                    type: array
                    items:
                      type: object
                      properties:
                        index:
                          type: integer
                        error:
                          type: string
    
    put:
      summary: Bulk update annotations
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                updates:
                  type: array
                  items:
                    type: object
                    properties:
                      annotation_id:
                        type: string
                      updates:
                        $ref: '#/components/schemas/AnnotationUpdate'
      responses:
        200:
          description: Bulk update results
```

### 5.3 Session Management

```yaml
  /api/videos/{video_id}/annotation-sessions:
    post:
      summary: Start annotation session
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AnnotationSessionCreate'
      responses:
        201:
          description: Session created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AnnotationSessionResponse'
    
    get:
      summary: Get active sessions
      responses:
        200:
          description: List of active sessions
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/AnnotationSessionResponse'

  /api/annotation-sessions/{session_id}:
    get:
      summary: Get session details
    put:
      summary: Update session progress
    delete:
      summary: End session
```

## 6. Database Schema Requirements

### 6.1 Annotations Table Enhancement
```sql
-- Enhanced annotations table with performance indexes
CREATE TABLE annotations (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    video_id VARCHAR(36) NOT NULL,
    detection_id VARCHAR(36), -- DET_PED_0001, etc.
    frame_number INTEGER NOT NULL,
    timestamp FLOAT NOT NULL,
    end_timestamp FLOAT, -- For temporal annotations
    vru_type VARCHAR(20) NOT NULL,
    bounding_box JSON NOT NULL, -- {x, y, width, height, confidence}
    occluded BOOLEAN DEFAULT FALSE,
    truncated BOOLEAN DEFAULT FALSE,
    difficult BOOLEAN DEFAULT FALSE,
    notes TEXT,
    annotator VARCHAR(36),
    validated BOOLEAN DEFAULT FALSE,
    validator VARCHAR(36), -- Who validated this annotation
    validation_notes TEXT,
    confidence_score FLOAT, -- AI confidence if auto-generated
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    
    -- Indexes for performance
    INDEX idx_annotation_video_frame (video_id, frame_number),
    INDEX idx_annotation_video_timestamp (video_id, timestamp),
    INDEX idx_annotation_video_validated (video_id, validated),
    INDEX idx_annotation_detection_id (detection_id),
    INDEX idx_annotation_vru_validated (vru_type, validated),
    INDEX idx_annotation_annotator (annotator),
    INDEX idx_annotation_validator (validator),
    INDEX idx_annotation_temporal_range (timestamp, end_timestamp)
);
```

### 6.2 Annotation Sessions Table
```sql
CREATE TABLE annotation_sessions (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    video_id VARCHAR(36) NOT NULL,
    project_id VARCHAR(36) NOT NULL,
    annotator_id VARCHAR(36),
    status ENUM('active', 'paused', 'completed', 'aborted') DEFAULT 'active',
    total_detections INTEGER DEFAULT 0,
    validated_detections INTEGER DEFAULT 0,
    current_frame INTEGER DEFAULT 0,
    total_frames INTEGER,
    progress_percentage FLOAT DEFAULT 0.0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    session_metadata JSON, -- Tool preferences, canvas settings, etc.
    
    -- Foreign key constraints
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_session_video_status (video_id, status),
    INDEX idx_session_annotator_active (annotator_id, status),
    INDEX idx_session_project_progress (project_id, progress_percentage)
);
```

### 6.3 Annotation History Table
```sql
CREATE TABLE annotation_history (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    annotation_id VARCHAR(36) NOT NULL,
    action_type ENUM('created', 'updated', 'validated', 'deleted') NOT NULL,
    old_values JSON, -- Previous state
    new_values JSON, -- New state
    changed_by VARCHAR(36),
    change_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (annotation_id) REFERENCES annotations(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_history_annotation (annotation_id),
    INDEX idx_history_action_time (action_type, created_at),
    INDEX idx_history_changed_by (changed_by)
);
```

## 7. User Workflow Specifications

### 7.1 Basic Annotation Workflow
1. **Video Selection**: User selects video from project
2. **Session Initialization**: System creates annotation session
3. **Frame Navigation**: User navigates to target frame
4. **Annotation Creation**: User draws bounding box and assigns label
5. **Validation**: User or validator reviews and approves
6. **Session Completion**: User marks section/video as complete

### 7.2 Collaborative Annotation Workflow
1. **Multi-user Access**: Multiple annotators access same video
2. **Work Distribution**: System suggests frame ranges per user
3. **Conflict Detection**: Real-time detection of overlapping work
4. **Merge Resolution**: Automated or manual resolution of conflicts
5. **Quality Review**: Designated validators review all work
6. **Final Approval**: Project manager approves completed annotations

### 7.3 Quality Assurance Workflow
1. **Auto QA Checks**: System runs automated quality checks
2. **Flagging**: System flags potential issues for review
3. **Manual Review**: Human reviewer validates flagged items
4. **Correction**: Issues are corrected or approved as-is
5. **Metrics Collection**: Quality metrics are updated
6. **Reporting**: QA reports generated for project tracking

## 8. Integration Points

### 8.1 Existing System Integration
- **Video Management**: Annotations tied to Video entities
- **Project Management**: Annotations grouped by Projects
- **Ground Truth Pipeline**: Annotations feed ML training data
- **Detection Events**: Annotations validate detection results
- **User Management**: Annotator and validator role assignments

### 8.2 External System Integration
- **ML Training Pipeline**: Export validated annotations
- **Analytics Dashboard**: Provide annotation statistics
- **Quality Metrics**: Feed into project quality assessments
- **Audit System**: Log all annotation activities

## 9. Security Requirements

### 9.1 Authentication and Authorization
- **User Authentication**: JWT token-based authentication
- **Role-Based Access**: Annotator, Validator, Admin roles
- **Resource Access**: Users can only access assigned projects
- **Action Permissions**: Specific permissions for create/update/delete/validate

### 9.2 Data Protection
- **Input Validation**: All inputs validated against schema
- **SQL Injection Prevention**: Parameterized queries only
- **XSS Prevention**: Output encoding for user content
- **File Upload Security**: Strict validation of uploaded content

### 9.3 Privacy and Compliance
- **Data Anonymization**: Option to anonymize annotator information
- **Audit Logging**: Complete audit trail for compliance
- **Data Retention**: Configurable retention policies
- **Access Logging**: Log all data access for monitoring

## 10. Success Metrics

### 10.1 Performance Metrics
- API response time: < 200ms for 95% of requests
- Canvas responsiveness: 60fps rendering
- Concurrent users: Support 50 simultaneous annotators
- Data throughput: Handle 1000 annotations per minute

### 10.2 Quality Metrics
- Annotation accuracy: > 95% validation pass rate
- Inter-annotator agreement: > 90% consistency
- Completion rate: > 98% of assigned work completed
- Error rate: < 2% of annotations require correction

### 10.3 User Experience Metrics
- User satisfaction: > 4.5/5 rating
- Training time: < 2 hours for new annotators
- Productivity: 20% improvement over manual processes
- Support requests: < 1% of annotations require support

---

This specification provides the foundation for implementing a comprehensive annotation system that meets the requirements for VRU detection validation in the AI model validation platform.
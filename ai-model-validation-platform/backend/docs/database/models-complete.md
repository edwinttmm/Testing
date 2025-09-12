# Complete Database Models Documentation

## Overview

This document provides a comprehensive analysis of all SQLAlchemy models in the AI Model Validation Platform. The database schema supports video-based VRU (Vulnerable Road User) detection validation with LabJack hardware timing integration.

## Table of Contents

1. [Authentication Models](#authentication-models)
2. [Core Project Models](#core-project-models)
3. [Video Management Models](#video-management-models)
4. [Ground Truth and Annotation Models](#ground-truth-and-annotation-models)
5. [Test Session and Detection Models](#test-session-and-detection-models)
6. [Results and Reporting Models](#results-and-reporting-models)
7. [Video Validation System Models](#video-validation-system-models)
8. [Audit and Tracking Models](#audit-and-tracking-models)

---

## Authentication Models

### AuthUser Model
**Table:** `auth_users`

Core authentication table for secure user access control.

**Columns:**
- `id` (String, PK): UUID primary key
- `email` (String, Unique, Indexed): User email address
- `username` (String, Unique, Indexed): Unique username
- `full_name` (String, Optional): User's full name
- `hashed_password` (String, Required): bcrypt hashed password
- `is_active` (Boolean, Default: True, Indexed): Account activation status
- `is_superuser` (Boolean, Default: False, Indexed): Admin privileges flag
- `is_verified` (Boolean, Default: False, Indexed): Email verification status
- `last_login` (DateTime, Optional, Indexed): Last login timestamp
- `created_at` (DateTime, Auto, Indexed): Account creation timestamp
- `updated_at` (DateTime, Auto-update): Last modification timestamp

**Methods:**
- `verify_password(password: str) -> bool`: Verify password against hash
- `get_password_hash(password: str) -> str`: Generate bcrypt hash (class method)
- `set_password(password: str) -> None`: Set new hashed password

**Indexes (7 composite):**
1. `idx_auth_user_email_active` (email, is_active)
2. `idx_auth_user_username_active` (username, is_active)
3. `idx_auth_user_active_verified` (is_active, is_verified)
4. `idx_auth_user_superuser_active` (is_superuser, is_active)
5. `idx_auth_user_created_active` (created_at, is_active)
6. `idx_auth_user_last_login` (last_login)

### UserSession Model
**Table:** `user_sessions`

Tracks active user sessions for security and session management.

**Columns:**
- `id` (String, PK): UUID primary key
- `user_id` (String, FK→auth_users.id, Indexed): Foreign key to user
- `session_token` (String, Unique, Indexed): Unique session identifier
- `ip_address` (String, Indexed): Client IP address
- `user_agent` (Text): Client browser/app identification
- `is_active` (Boolean, Default: True, Indexed): Session active status
- `expires_at` (DateTime, Required, Indexed): Session expiration time
- `created_at` (DateTime, Auto, Indexed): Session creation time
- `last_activity` (DateTime, Auto-update, Indexed): Last activity timestamp

**Relationships:**
- `user` → AuthUser (many-to-one, CASCADE DELETE)

**Indexes (6 composite):**
1. `idx_session_user_active` (user_id, is_active)
2. `idx_session_token_active` (session_token, is_active)
3. `idx_session_expires_active` (expires_at, is_active)
4. `idx_session_user_activity` (user_id, last_activity)
5. `idx_session_ip_activity` (ip_address, last_activity)
6. `idx_session_cleanup` (expires_at, is_active) - for cleanup jobs

---

## Core Project Models

### Project Model
**Table:** `projects`

Central project container for organizing validation test campaigns.

**Columns:**
- `id` (String, PK): UUID primary key
- `name` (String, Required, Indexed): Project name for search
- `description` (Text, Optional): Project description
- `camera_model` (String, Required): Camera hardware model
- `camera_view` (String, Required): Camera view type enum
  - Values: 'Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior'
- `lens_type` (String, Optional): Lens specification
- `resolution` (String, Optional): Video resolution setting
- `frame_rate` (Integer, Optional): Video frame rate
- `signal_type` (String, Required): Signal detection type enum
  - Values: 'GPIO', 'Network Packet', 'Serial'
- `status` (String, Default: "Active", Indexed): Project status for filtering
  - Values: 'Active', 'Completed', 'Draft'
- `owner_id` (String, Default: "anonymous", Indexed): User ownership
- `created_at` (DateTime, Auto, Indexed): Creation timestamp
- `updated_at` (DateTime, Auto-update): Last modification timestamp

**Relationships:**
- `videos` → Video (one-to-many, CASCADE delete-orphan)
- `test_sessions` → TestSession (one-to-many, CASCADE delete-orphan)
- `annotation_sessions` → AnnotationSession (one-to-many, CASCADE delete-orphan)
- `video_links` → VideoProjectLink (one-to-many, CASCADE delete-orphan)

---

## Video Management Models

### Video Model
**Table:** `videos`

Core video asset storage with comprehensive validation workflow support.

**Columns:**

*Basic Video Properties:*
- `id` (String, PK): UUID primary key
- `filename` (String, Required, Indexed): Video filename for search
- `file_path` (String, Required): Absolute file system path
- `file_size` (Integer): File size in bytes
- `duration` (Float): Video duration in seconds
- `fps` (Float): Frames per second
- `resolution` (String): Video resolution

*Unified Status System:*
- `status` (String, Default: "uploaded", Indexed): Primary status field
  - Values: VideoValidationStatus enum values
- `validation_status` (String, Default: "pending", Indexed): Validation workflow status
- `validation_type` (String, Optional): 'automatic', 'manual', 'hybrid'
- `validated_at` (DateTime, Optional, Indexed): Validation completion timestamp
- `validated_by` (String, Optional): User ID who validated

*Ground Truth Fields:*
- `ground_truth_generated` (Boolean, Default: False, Indexed): Legacy compatibility
- `ground_truth_count` (Integer, Default: 0): Number of ground truth objects
- `ground_truth_quality_score` (Float, Optional): Quality assessment score
- `ground_truth_completed_at` (DateTime, Optional): GT completion timestamp

*Testing Readiness Fields:*
- `hil_testing_ready` (Boolean, Default: False, Indexed): Ready for HIL testing
- `hil_testing_approved_by` (String, Optional): Approver user ID
- `hil_testing_approved_at` (DateTime, Optional): Approval timestamp

*Legacy Compatibility:*
- `processing_status` (String, Default: "pending", Indexed): Computed from status

*Metadata:*
- `project_id` (String, FK→projects.id, Required, Indexed): Project association
- `created_at` (DateTime, Auto, Indexed): Upload timestamp
- `updated_at` (DateTime, Auto-update): Last modification

**Properties:**
- `uploaded_at`: Backward compatibility property → maps to created_at

**Relationships:**
- `project` → Project (many-to-one)
- `ground_truth_objects` → GroundTruthObject (one-to-many, CASCADE delete-orphan)
- `annotations` → Annotation (one-to-many, CASCADE delete-orphan)
- `annotation_sessions` → AnnotationSession (one-to-many, CASCADE delete-orphan)
- `project_links` → VideoProjectLink (one-to-many, CASCADE delete-orphan)

**Indexes (9 composite):**
1. `idx_video_status_validation` (status, validation_status)
2. `idx_video_hil_ready` (hil_testing_ready, status)
3. `idx_video_validation_completed` (validated_at, validation_type)
4. `idx_video_ground_truth_quality` (ground_truth_quality_score, ground_truth_count)
5. `idx_video_testing_workflow` (status, hil_testing_ready, validated_at)
6. `idx_video_project_status` (project_id, status)
7. `idx_video_project_created` (project_id, created_at)
8. `idx_video_ground_truth_status` (ground_truth_generated, processing_status)
9. Plus additional metadata and performance indexes

### VideoProjectLink Model
**Table:** `video_project_links`

Junction table implementing many-to-many relationship between videos and projects.

**Columns:**
- `id` (String, PK): UUID primary key
- `video_id` (String, FK→videos.id, Required, Indexed): Video foreign key
- `project_id` (String, FK→projects.id, Required, Indexed): Project foreign key
- `assignment_reason` (Text, Optional): Reason for assignment
- `intelligent_match` (Boolean, Default: True): AI-based assignment flag
- `confidence_score` (Float, Optional): Assignment confidence
- `created_at` (DateTime, Auto, Indexed): Assignment timestamp

**Relationships:**
- `video` → Video (many-to-one, CASCADE DELETE)
- `project` → Project (many-to-one, CASCADE DELETE)

**Indexes (4 composite):**
1. `idx_video_project_unique` (video_id, project_id) - UNIQUE constraint
2. `idx_video_project_intelligent` (intelligent_match, confidence_score)
3. `idx_video_project_link_created` (project_id, created_at)
4. `idx_video_assignment_confidence` (confidence_score)

---

## Ground Truth and Annotation Models

### GroundTruthObject Model
**Table:** `ground_truth_objects`

Stores validated VRU detection ground truth data with spatial and temporal coordinates.

**Columns:**

*Identification:*
- `id` (String, PK): UUID primary key
- `video_id` (String, FK→videos.id, Required, Indexed): Parent video
- `tracking_id` (String, Optional, Indexed): Persistent VRU tracking across frames

*Temporal Data:*
- `frame_number` (Integer, Optional, Indexed): Frame number for video sync
- `timestamp` (Float, Required, Indexed): Temporal position in seconds

*Classification:*
- `class_label` (String, Required, Indexed): VRU type ('pedestrian', 'cyclist', etc.)

*Spatial Data (Bounding Box):*
- `x` (Float, Required): Bounding box x coordinate
- `y` (Float, Required): Bounding box y coordinate
- `width` (Float, Required): Bounding box width
- `height` (Float, Required): Bounding box height
- `bounding_box` (JSON, Deprecated): Legacy bounding box storage

*Quality Metrics:*
- `confidence` (Float, Indexed): Detection confidence score
- `validated` (Boolean, Default: False, Indexed): Manual validation flag
- `difficult` (Boolean, Default: False): Difficult detection flag

*Metadata:*
- `created_at` (DateTime, Auto): Creation timestamp

**Relationships:**
- `video` → Video (many-to-one)

**Indexes (10 composite):**
1. `idx_gt_video_timestamp` (video_id, timestamp)
2. `idx_gt_video_class` (video_id, class_label)
3. `idx_gt_timestamp_class` (timestamp, class_label)
4. `idx_gt_video_frame` (video_id, frame_number)
5. `idx_gt_video_confidence` (video_id, confidence)
6. `idx_gt_validated_class` (validated, class_label)
7. `idx_gt_spatial_bounds` (x, y, width, height)
8. `idx_gt_video_validated_timestamp` (video_id, validated, timestamp)
9. `idx_gt_video_tracking_id` (video_id, tracking_id)
10. `idx_gt_tracking_timestamp` (tracking_id, timestamp)

### Annotation Model
**Table:** `annotations`

Ground truth annotation model with detection ID tracking for collaborative annotation.

**Columns:**

*Identification:*
- `id` (String, PK): UUID primary key
- `video_id` (String, FK→videos.id, Required, Indexed): Parent video
- `detection_id` (String, Optional, Indexed): Detection identifier (DET_PED_0001, etc.)

*Temporal Data:*
- `frame_number` (Integer, Required, Indexed): Frame number
- `timestamp` (Float, Required, Indexed): Start timestamp
- `end_timestamp` (Float, Optional): End timestamp for temporal annotations

*Classification and Geometry:*
- `vru_type` (String, Required, Indexed): VRU type (pedestrian, cyclist, etc.)
- `bounding_box` (JSON, Required): Bounding box coordinates

*Quality Flags:*
- `occluded` (Boolean, Default: False): Occlusion flag
- `truncated` (Boolean, Default: False): Truncation flag
- `difficult` (Boolean, Default: False): Difficulty flag

*Annotation Metadata:*
- `notes` (Text, Optional): Annotator notes
- `annotator` (String, Optional): Annotator identifier
- `validated` (Boolean, Default: False, Indexed): Validation status
- `created_at` (DateTime, Auto, Indexed): Creation timestamp
- `updated_at` (DateTime, Auto-update): Last modification timestamp

**Relationships:**
- `video` → Video (many-to-one)

**Indexes (11 comprehensive):**
1. `idx_annotation_video_frame` (video_id, frame_number)
2. `idx_annotation_video_timestamp` (video_id, timestamp)
3. `idx_annotation_video_validated` (video_id, validated)
4. `idx_annotation_detection_id` (detection_id)
5. `idx_annotation_vru_validated` (vru_type, validated)
6. `idx_annotation_video_vru_frame` (video_id, vru_type, frame_number)
7. `idx_annotation_annotator_validated` (annotator, validated)
8. `idx_annotation_temporal_range` (timestamp, end_timestamp)
9. `idx_annotation_video_annotator_created` (video_id, annotator, created_at)
10. `idx_annotation_vru_timestamp_validated` (vru_type, timestamp, validated)
11. Plus additional quality and coverage analysis indexes

### AnnotationSession Model
**Table:** `annotation_sessions`

Tracks annotation session progress for collaborative annotation workflows.

**Columns:**
- `id` (String, PK): UUID primary key
- `video_id` (String, FK→videos.id, Required, Indexed): Target video
- `project_id` (String, FK→projects.id, Required, Indexed): Parent project
- `annotator_id` (String, Optional, Indexed): Annotator identifier
- `status` (String, Default: "active", Indexed): Session status
  - Values: 'active', 'paused', 'completed'
- `total_detections` (Integer, Default: 0): Total detections to annotate
- `validated_detections` (Integer, Default: 0): Completed detections
- `current_frame` (Integer, Default: 0): Current annotation position
- `total_frames` (Integer): Total frames in video
- `created_at` (DateTime, Auto, Indexed): Session start timestamp
- `updated_at` (DateTime, Auto-update): Last activity timestamp

**Relationships:**
- `video` → Video (many-to-one)
- `project` → Project (many-to-one)

---

## Test Session and Detection Models

### TestSession Model
**Table:** `test_sessions`

Test execution container for organizing detection validation campaigns.

**Columns:**

*Basic Properties:*
- `id` (String, PK): UUID primary key
- `name` (String, Required, Indexed): Session name for search
- `project_id` (String, FK→projects.id, Required, Indexed): Parent project
- `video_id` (String, FK→videos.id, Required, Indexed): Target video
- `tolerance_ms` (Integer, Default: 100): Timing tolerance threshold

*Session Management:*
- `status` (String, Default: "created", Indexed): Session status
  - Values: 'created', 'running', 'completed', 'failed'
- `session_type` (String, Default: "user_created", Indexed): Session origin
  - Values: 'user_created', 'auto_generated', 'system_test'
- `started_at` (DateTime, Optional, Indexed): Session start time
- `completed_at` (DateTime, Optional, Indexed): Session completion time
- `created_at` (DateTime, Auto, Indexed): Creation timestamp
- `updated_at` (DateTime, Auto-update): Last modification

*LabJack Timing Integration:*
- `latency_threshold_ms` (Integer, Default: 100, Indexed): Pass/fail threshold
- `video_start_timestamp` (Float, Optional, Indexed): Video timing reference

**Relationships:**
- `project` → Project (many-to-one)
- `detection_events` → DetectionEvent (one-to-many, CASCADE delete-orphan)
- `results` → TestResult (one-to-many, CASCADE delete-orphan)
- `detection_comparisons` → DetectionComparison (one-to-many, CASCADE delete-orphan)

**Indexes (5 composite):**
1. `idx_testsession_project_status` (project_id, status)
2. `idx_testsession_project_created` (project_id, created_at)
3. `idx_testsession_type_status` (session_type, status)
4. `idx_testsession_type_created` (session_type, created_at)
5. `idx_testsession_user_sessions` (session_type, status, created_at)

### DetectionEvent Model
**Table:** `detection_events`

Individual detection event records with comprehensive LabJack timing validation support.

**Columns:**

*Basic Event Data:*
- `id` (String, PK): UUID primary key
- `test_session_id` (String, FK→test_sessions.id, Required, Indexed): Parent session
- `video_id` (String, FK→videos.id, Optional, Indexed): Associated video
- `timestamp` (Float, Required, Indexed): Event timestamp
- `validation_result` (String, Indexed): Validation outcome
  - Values: 'Pass', 'Fail'
- `ground_truth_match_id` (String, FK→ground_truth_objects.id, Optional): GT matching
- `created_at` (DateTime, Auto, Indexed): Event creation time

*LabJack Timing Fields (Primary):*
- `latency_ms` (Float, Optional, Indexed): Calculated latency
- `labjack_timestamp` (Float, Optional, Indexed): LabJack signal timestamp
- `video_start_time` (Float, Optional, Indexed): Video reference time
- `labjack_voltage` (Float, Optional): LabJack voltage reading
- `latency_threshold_ms` (Float, Optional): Threshold for validation
- `latency_result` (String, Optional, Indexed): Latency validation result
  - Values: 'pass', 'fail', 'error', 'timeout'
- `voltage_level` (Float, Optional): Trigger voltage level
- `detection_channel` (String, Optional): LabJack channel identifier

*Legacy AI Fields (Deprecated):*
- `confidence` (Float, Optional, Indexed): Detection confidence
- `class_label` (String, Optional, Indexed): Detection class

*Enhanced Detection Storage:*
- `detection_id` (String, Optional, Indexed): Unique detection identifier
- `frame_number` (Integer, Optional, Indexed): Frame correlation
- `vru_type` (String, Optional, Indexed): VRU classification

*Spatial Data (Deprecated for LabJack):*
- `bounding_box_x` (Float, Optional): X coordinate
- `bounding_box_y` (Float, Optional): Y coordinate
- `bounding_box_width` (Float, Optional): Width
- `bounding_box_height` (Float, Optional): Height

**Properties:**
- `bounding_box`: Constructs dict from individual bbox fields for API compatibility

*Visual Evidence:*
- `screenshot_path` (String, Optional): Full frame screenshot
- `screenshot_zoom_path` (String, Optional): Zoomed region screenshot

*Processing Metadata:*
- `processing_time_ms` (Float, Optional): Detection processing time
- `model_version` (String, Optional): ML model version

*Source Classification:*
- `source` (String, Default: 'ai', Indexed): Detection source ('ai' or 'manual')
- `detection_type` (String, Default: 'automatic', Indexed): Detection type

**Relationships:**
- `test_session` → TestSession (many-to-one)
- `video` → Video (many-to-one)
- `ground_truth_match` → GroundTruthObject (many-to-one, SET NULL)

**Indexes (15+ comprehensive):**

*LabJack Timing Indexes:*
1. `idx_detection_latency_validation` (latency_ms, validation_result)
2. `idx_detection_labjack_timestamp` (labjack_timestamp)
3. `idx_detection_session_latency` (test_session_id, latency_ms)
4. `idx_detection_video_start_time` (video_start_time)
5. `idx_detection_labjack_voltage` (labjack_voltage)
6. `idx_detection_session_labjack_validation` (test_session_id, validation_result, latency_ms)

*Core Indexes:*
7. `idx_detection_session_timestamp` (test_session_id, timestamp)
8. `idx_detection_session_validation` (test_session_id, validation_result)
9. `idx_detection_video_timestamp` (video_id, timestamp)
10. `idx_detection_video_validation` (video_id, validation_result)

*Legacy and Performance Indexes:*
11. Plus 10+ additional indexes for legacy compatibility and performance

---

## Results and Reporting Models

### TestResult Model
**Table:** `test_results`

Enhanced test results with LabJack timing-based validation metrics.

**Columns:**

*Primary LabJack Timing Metrics:*
- `id` (String, PK): UUID primary key
- `test_session_id` (String, FK→test_sessions.id, Required, Indexed): Parent session
- `pass_rate` (Float, Indexed): Percentage passing latency threshold
- `avg_latency_ms` (Float, Indexed): Average latency across all detections
- `max_latency_ms` (Float, Indexed): Maximum latency detected
- `min_latency_ms` (Float, Indexed): Minimum latency detected
- `median_latency_ms` (Float, Indexed): Median latency
- `std_dev_latency_ms` (Float, Indexed): Standard deviation of latency
- `total_detections` (Integer, Indexed): Total detection event count
- `passed_detections` (Integer, Indexed): Count passing threshold
- `failed_detections` (Integer, Indexed): Count failing threshold
- `threshold_ms` (Integer, Indexed): Latency threshold used
- `latency_distribution` (JSON): Histogram distribution data

*Validation Metadata:*
- `validation_type` (String, Default: "latency_based", Indexed): Validation type
- `test_duration_seconds` (Float): Total test duration
- `detection_rate_hz` (Float): Detections per second

*Legacy AI Metrics (Compatibility):*
- `accuracy` (Float): Maps to pass_rate
- `precision` (Float): Maps to pass_rate
- `recall` (Float): Maps to pass_rate
- `f1_score` (Float): Maps to pass_rate
- `true_positives` (Integer): Maps to passed_detections
- `false_positives` (Integer): Maps to failed_detections
- `false_negatives` (Integer, Default: 0): Not applicable for latency
- `statistical_analysis` (JSON): Detailed latency metrics and histogram
- `confidence_intervals` (JSON): Statistical confidence data

*Timestamps:*
- `created_at` (DateTime, Auto, Indexed): Result generation time

**Relationships:**
- `test_session` → TestSession (many-to-one)

**Indexes (7 LabJack timing analysis):**
1. `idx_testresult_session_pass_rate` (test_session_id, pass_rate)
2. `idx_testresult_avg_latency` (avg_latency_ms)
3. `idx_testresult_max_latency` (max_latency_ms)
4. `idx_testresult_total_detections` (total_detections)
5. `idx_testresult_session_created` (test_session_id, created_at)
6. `idx_testresult_latency_range` (min_latency_ms, max_latency_ms)
7. `idx_testresult_pass_fail_counts` (passed_detections, failed_detections)

### TestReport Model
**Table:** `test_reports`

Test report metadata storage for PRD Module 4.2 report generation.

**Columns:**

*Basic Report Info:*
- `id` (String, PK): UUID primary key
- `test_session_id` (String, FK→test_sessions.id, Required, Indexed): Source session
- `report_name` (String, Required, Indexed): Report identifier
- `report_type` (String, Required, Indexed): Report type
  - Values: 'comprehensive', 'summary', 'failure_analysis'
- `formats_generated` (JSON): Generated format list (['html', 'pdf', 'json'])

*Metrics Snapshot:*
- `total_events` (Integer, Default: 0): Total detection events
- `passed_events` (Integer, Default: 0): Passed events count
- `failed_events` (Integer, Default: 0): Failed events count
- `pass_rate_percent` (Float, Indexed): Pass rate percentage
- `average_latency_ms` (Float, Indexed): Average latency
- `test_outcome` (String, Indexed): Overall test outcome
  - Values: 'PASS', 'FAIL', 'NO_DATA'

*File Paths:*
- `html_report_path` (String): HTML report file path
- `pdf_report_path` (String): PDF report file path
- `json_report_path` (String): JSON report file path
- `csv_summary_path` (String): CSV summary file path

*Snapshot Metadata:*
- `failure_snapshots_count` (Integer, Default: 0): Number of failure snapshots
- `snapshots_storage_path` (String): Storage directory path
- `total_snapshot_size_bytes` (Integer, Default: 0): Total snapshot storage size

*Generation Metadata:*
- `generated_at` (DateTime, Auto, Indexed): Report generation timestamp
- `generation_time_ms` (Float): Time taken to generate report
- `generated_by` (String, Default: "system"): Report generator identifier

**Relationships:**
- `test_session` → TestSession (many-to-one, backref="reports")

**Indexes (5 report queries):**
1. `idx_report_session_type` (test_session_id, report_type)
2. `idx_report_generated_outcome` (generated_at, test_outcome)
3. `idx_report_pass_rate` (pass_rate_percent)
4. `idx_report_session_generated` (test_session_id, generated_at)
5. `idx_report_type_outcome` (report_type, test_outcome)

### ReportSnapshot Model
**Table:** `report_snapshots`

Failure snapshot metadata for visual evidence in reports.

**Columns:**

*Basic Snapshot Info:*
- `id` (String, PK): UUID primary key
- `report_id` (String, FK→test_reports.id, Required, Indexed): Parent report
- `detection_event_id` (String, FK→detection_events.id, Required, Indexed): Source event
- `video_id` (String, FK→videos.id, Optional, Indexed): Associated video

*Failure Details:*
- `failure_type` (String, Required, Indexed): Failure classification
  - Values: 'HIGH_LATENCY', 'MISSED_DETECTION'
- `timestamp_ms` (Float, Required, Indexed): Failure timestamp
- `frame_number` (Integer, Optional, Indexed): Frame number

*File Information:*
- `snapshot_filename` (String, Required): Generated filename
- `snapshot_path` (String, Required): Full file path
- `file_size_bytes` (Integer): File size

*Video Properties at Capture:*
- `video_fps` (Float): Video frame rate at capture
- `video_total_frames` (Integer): Total frames in video

*Capture Metadata:*
- `captured_at` (DateTime, Auto, Indexed): Capture timestamp
- `capture_success` (Boolean, Default: True, Indexed): Capture success flag
- `error_message` (Text, Optional): Error details if capture failed

**Relationships:**
- `report` → TestReport (many-to-one, backref="snapshots")
- `detection_event` → DetectionEvent (many-to-one)
- `video` → Video (many-to-one)

**Indexes (6 snapshot queries):**
1. `idx_snapshot_report_failure` (report_id, failure_type)
2. `idx_snapshot_event_timestamp` (detection_event_id, timestamp_ms)
3. `idx_snapshot_video_frame` (video_id, frame_number)
4. `idx_snapshot_failure_captured` (failure_type, captured_at)
5. `idx_snapshot_success_type` (capture_success, failure_type)
6. `idx_snapshot_report_timestamp` (report_id, timestamp_ms)

### DetectionComparison Model
**Table:** `detection_comparisons`

Detection comparison data for ground truth validation analysis.

**Columns:**
- `id` (String, PK): UUID primary key
- `test_session_id` (String, FK→test_sessions.id, Required, Indexed): Parent session
- `ground_truth_id` (String, FK→annotations.id, Optional): Ground truth reference
- `detection_event_id` (String, FK→detection_events.id, Optional): Detection reference
- `match_type` (String, Required, Indexed): Match classification
  - Values: 'TP', 'FP', 'FN', 'TN'
- `iou_score` (Float): Intersection over Union score
- `distance_error` (Float): Spatial distance error
- `temporal_offset` (Float): Temporal offset between GT and detection
- `notes` (Text, Optional): Analysis notes
- `created_at` (DateTime, Auto, Indexed): Comparison timestamp

**Relationships:**
- `test_session` → TestSession (many-to-one)
- `ground_truth` → Annotation (many-to-one)
- `detection_event` → DetectionEvent (many-to-one)

**Indexes (6 analysis indexes):**
1. `idx_comparison_session_match` (test_session_id, match_type)
2. `idx_comparison_iou_temporal` (iou_score, temporal_offset)
3. `idx_comparison_session_ground_truth` (test_session_id, ground_truth_id)
4. `idx_comparison_session_detection` (test_session_id, detection_event_id)
5. `idx_comparison_match_iou` (match_type, iou_score)
6. `idx_comparison_temporal_distance` (temporal_offset, distance_error)

---

## Video Validation System Models

### VideoValidationCriteria Model
**Table:** `video_validation_criteria`

Configurable validation criteria per project or globally.

**Columns:**

*Basic Info:*
- `id` (String, PK): UUID primary key
- `project_id` (String, FK→projects.id, Optional): Project scope (NULL = global)

*Ground Truth Quality Requirements:*
- `min_detection_count` (Integer, Default: 5): Minimum required detections
- `min_confidence_threshold` (Float, Default: 0.7): Minimum confidence score
- `min_frame_coverage_percent` (Float, Default: 80.0): Frame coverage requirement

*Technical Requirements:*
- `min_duration_seconds` (Float, Default: 10.0): Minimum video duration
- `max_duration_seconds` (Float, Default: 300.0): Maximum video duration
- `required_resolution_min` (String, Default: "640x480"): Minimum resolution
- `min_fps` (Float, Default: 24.0): Minimum frame rate

*Content Requirements:*
- `required_vru_types` (JSON): Required VRU types (['pedestrian', 'cyclist'])
- `min_scene_complexity_score` (Float, Default: 0.5): Scene complexity threshold

*Timestamps:*
- `created_at` (DateTime, Auto): Creation timestamp
- `updated_at` (DateTime, Auto-update): Last modification

**Relationships:**
- `project` → Project (many-to-one, backref="validation_criteria")

**Indexes (3 criteria queries):**
1. `idx_validation_criteria_project` (project_id)
2. `idx_validation_criteria_created` (created_at)
3. `idx_validation_criteria_thresholds` (min_detection_count, min_confidence_threshold)

### VideoValidationResult Model
**Table:** `video_validation_results`

Results of video validation processes.

**Columns:**

*Basic Result Info:*
- `id` (String, PK): UUID primary key
- `video_id` (String, FK→videos.id, Required, Indexed): Target video
- `validation_criteria_id` (String, FK→video_validation_criteria.id, Required): Criteria used

*Validation Results:*
- `validation_type` (String, Required, Indexed): Validation method
  - Values: 'automatic', 'manual'
- `overall_result` (String, Required, Indexed): Final validation result
  - Values: 'passed', 'failed', 'needs_review'

*Detailed Scoring:*
- `ground_truth_score` (Float): Ground truth quality score
- `technical_score` (Float): Technical requirements score
- `content_score` (Float): Content requirements score
- `overall_score` (Float, Indexed): Combined overall score

*Validation Details:*
- `criteria_met` (JSON): Detailed criteria pass/fail breakdown
- `validation_notes` (Text): Validation notes
- `validated_by` (String, Optional): Validator identifier

*Timestamp:*
- `created_at` (DateTime, Auto, Indexed): Validation completion time

**Relationships:**
- `video` → Video (many-to-one, backref="validation_results")
- `validation_criteria` → VideoValidationCriteria (many-to-one, backref="validation_results")

**Indexes (7 validation queries):**
1. `idx_validation_result_video` (video_id)
2. `idx_validation_result_type` (validation_type)
3. `idx_validation_result_overall` (overall_result)
4. `idx_validation_result_score` (overall_score)
5. `idx_validation_result_created` (created_at)
6. `idx_validation_result_video_created` (video_id, created_at)
7. `idx_validation_result_type_result` (validation_type, overall_result)

### VideoStatusTransition Model
**Table:** `video_status_transitions`

Audit trail for video status changes.

**Columns:**
- `id` (String, PK): UUID primary key
- `video_id` (String, FK→videos.id, Required, Indexed): Target video
- `from_status` (String, Required, Indexed): Previous status
- `to_status` (String, Required, Indexed): New status
- `transition_reason` (String, Required): Reason for transition
- `triggered_by` (String, Optional): User ID or 'system'
- `transition_metadata` (JSON, Optional): Additional context data
- `created_at` (DateTime, Auto, Indexed): Transition timestamp

**Relationships:**
- `video` → Video (many-to-one, backref="status_transitions")

**Indexes (6 audit queries):**
1. `idx_status_transition_video` (video_id)
2. `idx_status_transition_video_time` (video_id, created_at)
3. `idx_status_transition_from_to` (from_status, to_status)
4. `idx_status_transition_created` (created_at)
5. `idx_status_transition_reason` (transition_reason)
6. `idx_status_transition_triggered_by` (triggered_by)

---

## Audit and Tracking Models

### AuditLog Model
**Table:** `audit_logs`

Comprehensive audit logging for security and compliance.

**Columns:**
- `id` (String, PK): UUID primary key
- `user_id` (String, Default: "anonymous", Indexed): User performing action
- `event_type` (String, Required, Indexed): Event classification
- `event_data` (JSON, Optional): Additional event details
- `ip_address` (String, Optional, Indexed): Client IP address
- `user_agent` (String, Optional): Client browser/app identification
- `created_at` (DateTime, Auto, Indexed): Event timestamp

**Indexes (5 comprehensive audit tracking):**
1. `idx_audit_user_event` (user_id, event_type)
2. `idx_audit_created_event` (created_at, event_type)
3. `idx_audit_ip_event_time` (ip_address, event_type, created_at)
4. `idx_audit_user_time_range` (user_id, created_at)
5. `idx_audit_event_data_analysis` (event_type, created_at)

---

## Additional Models

### Detection Session, StoredDetectionEvent, VideoEvent
**Source:** `src.models.detection_session`

These models are imported for simple detection workflows and provide additional detection storage capabilities beyond the main DetectionEvent model.

---

## Database Design Principles

### Index Strategy
The database employs a comprehensive indexing strategy:

1. **Single Column Indexes**: On frequently queried fields (status, timestamps, foreign keys)
2. **Composite Indexes**: For common query patterns (video_id + timestamp, project_id + status)
3. **Unique Constraints**: Prevent data duplication (email, session_token, video-project links)
4. **Performance Indexes**: For analytics and reporting queries

### Relationship Management
- **CASCADE DELETE**: Used for parent-child relationships to maintain referential integrity
- **SET NULL**: Used for optional relationships where parent deletion shouldn't delete child
- **Many-to-Many**: Implemented via junction tables with metadata (VideoProjectLink)

### Data Types
- **UUID Strings**: All primary keys use string UUIDs for better distributed system support
- **JSON Columns**: Used for flexible, structured data storage
- **Datetime with Timezone**: All timestamps include timezone information
- **Float**: Used for precise timing measurements (latency, timestamps)

### Performance Considerations
- **Pool Configuration**: Enhanced connection pooling for high-concurrency access
- **Index Maintenance**: Comprehensive indexing strategy for query performance
- **Query Optimization**: Composite indexes designed for common query patterns
- **Legacy Compatibility**: Maintains backward compatibility while supporting new features

This comprehensive database schema supports the full VRU detection validation workflow from video upload through ground truth generation, test execution, LabJack timing validation, and comprehensive reporting.
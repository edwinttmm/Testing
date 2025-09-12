# SPARC Pseudocode Phase: Ground Truth Management Algorithms

## Overview
Comprehensive algorithms for ground truth data processing, validation, export workflows, and integrity management.

## 1. GROUND TRUTH PROCESSING ALGORITHMS

### 1.1 Ground Truth Generation Algorithm

```
ALGORITHM: GenerateGroundTruth
INPUT: video_id (string), processing_config (GroundTruthConfig), user_id (string)
OUTPUT: ground_truth_result (GroundTruthResult) or error (ErrorResponse)

PRECONDITIONS:
    - video_id exists and is accessible
    - video file is available and readable
    - ML inference engine is available

BEGIN
    // Phase 1: Video Validation and Preprocessing
    video ← Database.GetVideo(video_id)
    IF video is null THEN
        RETURN NotFoundError("Video not found")
    END IF
    
    IF NOT FileExists(video.file_path) THEN
        RETURN FileNotFoundError("Video file not accessible")
    END IF
    
    // Check authorization
    access_granted ← CheckVideoAccess(user_id, video.project_id, "PROCESS")
    IF NOT access_granted THEN
        AuditLog.Log(user_id, "GT_GENERATION_UNAUTHORIZED", video_id)
        RETURN UnauthorizedError("Access denied")
    END IF
    
    // Phase 2: Processing Status Management
    IF video.processing_status == "processing" THEN
        RETURN ConflictError("Video is already being processed")
    END IF
    
    transaction ← Database.BeginTransaction()
    TRY
        // Set processing status
        video.processing_status ← "processing"
        video.updated_at ← CurrentTimestamp()
        Database.Update(video)
        transaction.Commit()
    CATCH database_error
        transaction.Rollback()
        RETURN DatabaseError("Failed to update processing status")
    END TRY
    
    // Phase 3: Video Analysis and Frame Extraction
    processing_start_time ← CurrentTimestamp()
    
    TRY
        video_metadata ← ExtractVideoMetadata(video.file_path)
        frame_count ← video_metadata.total_frames
        fps ← video_metadata.fps
        duration ← video_metadata.duration
        
        // Update video metadata if not already set
        IF video.duration is null OR video.fps is null THEN
            video.duration ← duration
            video.fps ← fps
            Database.Update(video)
        END IF
        
        // Phase 4: ML Inference Configuration
        inference_config ← ConfigureInference(processing_config, video_metadata)
        
        // Initialize progress tracking
        progress_tracker ← CreateProgressTracker(video_id, user_id, frame_count)
        
        // Phase 5: Frame-by-Frame Processing
        detections ← EmptyList()
        frame_interval ← CalculateFrameInterval(fps, processing_config.sampling_rate)
        
        FOR frame_number FROM 0 TO frame_count STEP frame_interval DO
            // Extract frame
            frame_data ← ExtractFrame(video.file_path, frame_number)
            frame_timestamp ← frame_number / fps
            
            // Run ML inference
            inference_result ← RunInference(frame_data, inference_config)
            
            // Process detections
            FOR EACH detection IN inference_result.detections DO
                IF detection.confidence >= processing_config.confidence_threshold THEN
                    
                    // Filter by target classes
                    IF detection.class_label IN processing_config.target_classes THEN
                        
                        // Create ground truth object
                        ground_truth_object ← CreateGroundTruthObject{
                            video_id: video_id,
                            frame_number: frame_number,
                            timestamp: frame_timestamp,
                            class_label: detection.class_label,
                            x: detection.bounding_box.x,
                            y: detection.bounding_box.y,
                            width: detection.bounding_box.width,
                            height: detection.bounding_box.height,
                            confidence: detection.confidence,
                            validated: false,  // Requires human validation
                            difficult: DetermineIfDifficult(detection)
                        }
                        
                        detections.Add(ground_truth_object)
                    END IF
                END IF
            END FOR
            
            // Update progress
            progress_tracker.UpdateProgress(frame_number, detections.Length)
            
            // Send progress update via WebSocket
            IF frame_number % PROGRESS_UPDATE_INTERVAL == 0 THEN
                progress_data ← {
                    video_id: video_id,
                    processed_frames: frame_number,
                    total_frames: frame_count,
                    detections_count: detections.Length,
                    progress_percentage: (frame_number / frame_count) * 100
                }
                
                WebSocket.Broadcast("gt_processing_progress", progress_data)
            END IF
        END FOR
        
        // Phase 6: Batch Database Insert with Optimization
        batch_size ← 1000
        detection_batches ← SplitIntoBatches(detections, batch_size)
        total_inserted ← 0
        
        transaction ← Database.BeginTransaction()
        TRY
            FOR EACH batch IN detection_batches DO
                Database.BulkInsert("ground_truth_objects", batch)
                total_inserted += batch.Length
            END FOR
            
            // Update video status
            video.processing_status ← "completed"
            video.ground_truth_generated ← true
            video.updated_at ← CurrentTimestamp()
            Database.Update(video)
            
            transaction.Commit()
        CATCH database_error
            transaction.Rollback()
            THROW database_error
        END TRY
        
        // Phase 7: Post-Processing Analysis
        processing_end_time ← CurrentTimestamp()
        processing_duration ← processing_end_time - processing_start_time
        
        analysis_result ← AnalyzeGroundTruthQuality(video_id, detections)
        
        // Phase 8: Result Assembly and Notification
        result ← GroundTruthResult{
            video_id: video_id,
            total_detections: total_inserted,
            processing_time: processing_duration,
            frames_processed: frame_count / frame_interval,
            quality_metrics: analysis_result,
            confidence_distribution: CalculateConfidenceDistribution(detections),
            class_distribution: CalculateClassDistribution(detections)
        }
        
        AuditLog.Log(user_id, "GT_GENERATION_COMPLETED", {
            video_id: video_id,
            total_detections: total_inserted,
            processing_time: processing_duration
        })
        
        WebSocket.Broadcast("gt_generation_completed", {
            video_id: video_id,
            result: result
        })
        
        RETURN result
        
    CATCH processing_error
        // Handle processing failure
        video.processing_status ← "failed"
        video.updated_at ← CurrentTimestamp()
        Database.Update(video)
        
        AuditLog.Log(user_id, "GT_GENERATION_FAILED", {
            video_id: video_id,
            error: processing_error.message
        })
        
        RETURN ProcessingError("Ground truth generation failed", processing_error)
    END TRY
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n * m) where n = frames, m = average detections per frame
    Space Complexity: O(k) where k = batch size for database operations
    I/O Operations: Video file reading, frame extraction, ML inference
    Database Operations: Bulk inserts with batch optimization
```

### 1.2 Ground Truth Validation Algorithm

```
ALGORITHM: ValidateGroundTruth
INPUT: video_id (string), validation_criteria (ValidationCriteria), user_id (string)
OUTPUT: validation_result (ValidationResult) or error (ErrorResponse)

BEGIN
    // Phase 1: Authorization and Data Retrieval
    access_granted ← CheckVideoAccess(user_id, video_id, "VALIDATE")
    IF NOT access_granted THEN
        RETURN UnauthorizedError("Access denied")
    END IF
    
    ground_truth_objects ← Database.GetGroundTruthObjects(video_id)
    IF ground_truth_objects.IsEmpty() THEN
        RETURN NotFoundError("No ground truth data available for validation")
    END IF
    
    video ← Database.GetVideo(video_id)
    
    // Phase 2: Initialize Validation Metrics
    validation_metrics ← ValidationMetrics{
        total_objects: ground_truth_objects.Length,
        validated_objects: 0,
        confidence_issues: 0,
        geometric_issues: 0,
        temporal_consistency_issues: 0,
        class_distribution_issues: 0
    }
    
    issues ← EmptyList()
    
    // Phase 3: Individual Object Validation
    FOR EACH gt_object IN ground_truth_objects DO
        object_issues ← ValidateGroundTruthObject(gt_object, validation_criteria)
        
        IF object_issues.IsEmpty() THEN
            validation_metrics.validated_objects += 1
        ELSE
            issues.AddAll(object_issues)
            
            // Categorize issues
            FOR EACH issue IN object_issues DO
                CASE issue.type OF
                    "LOW_CONFIDENCE": validation_metrics.confidence_issues += 1
                    "INVALID_GEOMETRY": validation_metrics.geometric_issues += 1
                    "TEMPORAL_INCONSISTENCY": validation_metrics.temporal_consistency_issues += 1
                    "CLASS_DISTRIBUTION": validation_metrics.class_distribution_issues += 1
                END CASE
            END FOR
        END IF
    END FOR
    
    // Phase 4: Global Validation Checks
    global_issues ← ValidateGlobalConsistency(ground_truth_objects, validation_criteria)
    issues.AddAll(global_issues)
    
    // Phase 5: Statistical Analysis
    statistical_analysis ← PerformStatisticalAnalysis(ground_truth_objects)
    
    // Phase 6: Quality Score Calculation
    quality_score ← CalculateQualityScore(validation_metrics, statistical_analysis)
    
    // Phase 7: Generate Recommendations
    recommendations ← GenerateValidationRecommendations(issues, validation_metrics)
    
    // Phase 8: Result Assembly
    validation_result ← ValidationResult{
        video_id: video_id,
        validation_timestamp: CurrentTimestamp(),
        quality_score: quality_score,
        metrics: validation_metrics,
        issues: issues,
        statistical_analysis: statistical_analysis,
        recommendations: recommendations,
        passed_validation: quality_score >= validation_criteria.minimum_quality_score
    }
    
    // Phase 9: Update Database and Notifications
    IF validation_result.passed_validation THEN
        // Mark ground truth as validated
        Database.UpdateGroundTruthValidationStatus(video_id, true, quality_score)
        
        AuditLog.Log(user_id, "GT_VALIDATION_PASSED", {
            video_id: video_id,
            quality_score: quality_score
        })
    ELSE
        AuditLog.Log(user_id, "GT_VALIDATION_FAILED", {
            video_id: video_id,
            quality_score: quality_score,
            issues_count: issues.Length
        })
    END IF
    
    WebSocket.Broadcast("gt_validation_completed", validation_result)
    
    RETURN validation_result
END

SUBROUTINE: ValidateGroundTruthObject
INPUT: gt_object (GroundTruthObject), criteria (ValidationCriteria)
OUTPUT: issues (List<ValidationIssue>)

BEGIN
    issues ← EmptyList()
    
    // Confidence validation
    IF gt_object.confidence < criteria.minimum_confidence THEN
        issues.Add(ValidationIssue{
            type: "LOW_CONFIDENCE",
            severity: "WARNING",
            message: "Detection confidence below threshold",
            object_id: gt_object.id,
            value: gt_object.confidence,
            threshold: criteria.minimum_confidence
        })
    END IF
    
    // Geometric validation
    bbox_area ← gt_object.width * gt_object.height
    
    IF bbox_area < criteria.minimum_bbox_area THEN
        issues.Add(ValidationIssue{
            type: "INVALID_GEOMETRY",
            severity: "ERROR",
            message: "Bounding box too small",
            object_id: gt_object.id,
            value: bbox_area,
            threshold: criteria.minimum_bbox_area
        })
    END IF
    
    IF bbox_area > criteria.maximum_bbox_area THEN
        issues.Add(ValidationIssue{
            type: "INVALID_GEOMETRY",
            severity: "WARNING",
            message: "Bounding box very large",
            object_id: gt_object.id,
            value: bbox_area,
            threshold: criteria.maximum_bbox_area
        })
    END IF
    
    // Boundary validation
    IF gt_object.x < 0 OR gt_object.y < 0 OR 
       (gt_object.x + gt_object.width) > 1 OR 
       (gt_object.y + gt_object.height) > 1 THEN
        issues.Add(ValidationIssue{
            type: "INVALID_GEOMETRY",
            severity: "ERROR",
            message: "Bounding box extends beyond image boundaries",
            object_id: gt_object.id
        })
    END IF
    
    RETURN issues
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n + g) where n = ground truth objects, g = global validation complexity
    Space Complexity: O(n) for validation results
    Database Operations: 2-3 queries (read objects, update status)
```

### 1.3 Ground Truth Export Algorithm

```
ALGORITHM: ExportGroundTruth
INPUT: video_id (string), export_format (ExportFormat), export_options (ExportOptions), user_id (string)
OUTPUT: export_result (ExportResult) or error (ErrorResponse)

BEGIN
    // Phase 1: Authorization and Validation
    access_granted ← CheckVideoAccess(user_id, video_id, "EXPORT")
    IF NOT access_granted THEN
        RETURN UnauthorizedError("Access denied")
    END IF
    
    video ← Database.GetVideo(video_id)
    IF video is null THEN
        RETURN NotFoundError("Video not found")
    END IF
    
    IF NOT video.ground_truth_generated THEN
        RETURN ConflictError("Ground truth not generated for this video")
    END IF
    
    // Phase 2: Data Retrieval with Filtering
    query_builder ← BuildGroundTruthQuery(video_id, export_options.filters)
    ground_truth_objects ← Database.Execute(query_builder)
    
    IF ground_truth_objects.IsEmpty() THEN
        RETURN NotFoundError("No ground truth data matches the export criteria")
    END IF
    
    // Phase 3: Format-Specific Export Processing
    export_start_time ← CurrentTimestamp()
    
    CASE export_format OF
        "COCO":
            export_data ← ExportToCOCO(ground_truth_objects, video, export_options)
        "YOLO":
            export_data ← ExportToYOLO(ground_truth_objects, video, export_options)
        "PASCAL_VOC":
            export_data ← ExportToPascalVOC(ground_truth_objects, video, export_options)
        "CSV":
            export_data ← ExportToCSV(ground_truth_objects, video, export_options)
        "JSON":
            export_data ← ExportToJSON(ground_truth_objects, video, export_options)
        DEFAULT:
            RETURN UnsupportedFormatError("Export format not supported: " + export_format)
    END CASE
    
    // Phase 4: File Generation and Storage
    export_filename ← GenerateExportFilename(video, export_format, export_options)
    export_path ← CreateExportFile(export_filename, export_data)
    
    // Phase 5: Metadata Generation
    export_metadata ← GenerateExportMetadata(
        video_id, export_format, ground_truth_objects.Length, 
        export_options, user_id
    )
    
    // Phase 6: Database Recording
    transaction ← Database.BeginTransaction()
    TRY
        export_record ← ExportRecord{
            id: GenerateUUID(),
            video_id: video_id,
            export_format: export_format,
            file_path: export_path,
            file_size: GetFileSize(export_path),
            exported_objects_count: ground_truth_objects.Length,
            export_options: export_options,
            metadata: export_metadata,
            created_by: user_id,
            created_at: CurrentTimestamp()
        }
        
        Database.Insert("export_records", export_record)
        transaction.Commit()
    CATCH database_error
        transaction.Rollback()
        // Clean up created file
        DeleteFile(export_path)
        RETURN DatabaseError("Failed to record export")
    END TRY
    
    // Phase 7: Result Assembly
    export_end_time ← CurrentTimestamp()
    processing_time ← export_end_time - export_start_time
    
    export_result ← ExportResult{
        export_id: export_record.id,
        video_id: video_id,
        export_format: export_format,
        file_path: export_path,
        download_url: GenerateDownloadURL(export_record.id),
        file_size: export_record.file_size,
        exported_objects_count: ground_truth_objects.Length,
        processing_time: processing_time,
        metadata: export_metadata,
        expires_at: CurrentTimestamp() + EXPORT_FILE_RETENTION_PERIOD
    }
    
    // Phase 8: Audit and Notification
    AuditLog.Log(user_id, "GT_EXPORT_COMPLETED", {
        video_id: video_id,
        export_format: export_format,
        objects_count: ground_truth_objects.Length,
        file_size: export_record.file_size
    })
    
    WebSocket.Broadcast("gt_export_completed", {
        video_id: video_id,
        export_result: export_result
    })
    
    RETURN export_result
END

SUBROUTINE: ExportToCOCO
INPUT: ground_truth_objects (List<GroundTruthObject>), video (Video), options (ExportOptions)
OUTPUT: coco_data (COCOFormat)

BEGIN
    // COCO format structure
    coco_data ← {
        info: {
            description: "AI Model Validation Platform Ground Truth Export",
            version: "1.0",
            year: CurrentYear(),
            contributor: "AI Model Validation Platform",
            date_created: CurrentISODateTime()
        },
        licenses: [
            {
                id: 1,
                name: "Attribution License",
                url: "https://creativecommons.org/licenses/by/4.0/"
            }
        ],
        images: [],
        annotations: [],
        categories: []
    }
    
    // Create image entry
    image_entry ← {
        id: 1,
        width: ExtractImageWidth(video),
        height: ExtractImageHeight(video),
        file_name: video.filename,
        license: 1,
        date_captured: video.created_at
    }
    coco_data.images.Add(image_entry)
    
    // Create category mappings
    unique_classes ← GetUniqueClasses(ground_truth_objects)
    category_id_map ← EmptyMap()
    
    FOR i FROM 0 TO unique_classes.Length - 1 DO
        category ← {
            id: i + 1,
            name: unique_classes[i],
            supercategory: "vru"
        }
        coco_data.categories.Add(category)
        category_id_map[unique_classes[i]] ← i + 1
    END FOR
    
    // Create annotations
    FOR EACH gt_object IN ground_truth_objects DO
        // Convert normalized coordinates to pixel coordinates
        image_width ← image_entry.width
        image_height ← image_entry.height
        
        x_pixel ← gt_object.x * image_width
        y_pixel ← gt_object.y * image_height
        width_pixel ← gt_object.width * image_width
        height_pixel ← gt_object.height * image_height
        
        annotation ← {
            id: gt_object.id,
            image_id: 1,
            category_id: category_id_map[gt_object.class_label],
            bbox: [x_pixel, y_pixel, width_pixel, height_pixel],
            area: width_pixel * height_pixel,
            iscrowd: 0,
            confidence: gt_object.confidence,
            timestamp: gt_object.timestamp,
            frame_number: gt_object.frame_number
        }
        
        coco_data.annotations.Add(annotation)
    END FOR
    
    RETURN coco_data
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n + f) where n = ground truth objects, f = format processing complexity
    Space Complexity: O(n) for export data structure
    I/O Operations: File creation and writing
    Database Operations: 2-3 queries (read data, insert export record)
```

## 2. GROUND TRUTH INTEGRITY ALGORITHMS

### 2.1 Data Integrity Validation Algorithm

```
ALGORITHM: ValidateGroundTruthIntegrity
INPUT: video_id (string), integrity_checks (IntegrityCheckConfig)
OUTPUT: integrity_result (IntegrityResult)

BEGIN
    integrity_issues ← EmptyList()
    
    // Phase 1: Referential Integrity
    orphaned_objects ← Database.Query(`
        SELECT gt.id, gt.video_id 
        FROM ground_truth_objects gt 
        LEFT JOIN videos v ON gt.video_id = v.id 
        WHERE v.id IS NULL AND gt.video_id = ?
    `, video_id)
    
    FOR EACH orphaned IN orphaned_objects DO
        integrity_issues.Add(IntegrityIssue{
            type: "ORPHANED_OBJECT",
            severity: "ERROR",
            message: "Ground truth object references non-existent video",
            object_id: orphaned.id
        })
    END FOR
    
    // Phase 2: Temporal Consistency
    ground_truth_objects ← Database.GetGroundTruthObjects(video_id, order_by: "timestamp")
    
    FOR i FROM 1 TO ground_truth_objects.Length - 1 DO
        current ← ground_truth_objects[i]
        previous ← ground_truth_objects[i-1]
        
        // Check timestamp ordering
        IF current.timestamp < previous.timestamp THEN
            integrity_issues.Add(IntegrityIssue{
                type: "TEMPORAL_DISORDER",
                severity: "WARNING",
                message: "Timestamps not in chronological order",
                object_id: current.id
            })
        END IF
        
        // Check frame number consistency with timestamp
        video ← Database.GetVideo(video_id)
        expected_frame ← current.timestamp * video.fps
        frame_difference ← ABS(current.frame_number - expected_frame)
        
        IF frame_difference > FRAME_TIMESTAMP_TOLERANCE THEN
            integrity_issues.Add(IntegrityIssue{
                type: "FRAME_TIMESTAMP_MISMATCH",
                severity: "WARNING",
                message: "Frame number doesn't match timestamp",
                object_id: current.id,
                expected_frame: expected_frame,
                actual_frame: current.frame_number
            })
        END IF
    END FOR
    
    // Phase 3: Geometric Consistency
    FOR EACH gt_object IN ground_truth_objects DO
        // Check coordinate bounds
        IF gt_object.x < 0 OR gt_object.y < 0 OR
           gt_object.x > 1 OR gt_object.y > 1 OR
           (gt_object.x + gt_object.width) > 1 OR
           (gt_object.y + gt_object.height) > 1 THEN
            integrity_issues.Add(IntegrityIssue{
                type: "INVALID_COORDINATES",
                severity: "ERROR",
                message: "Bounding box coordinates out of bounds",
                object_id: gt_object.id
            })
        END IF
        
        // Check bounding box dimensions
        IF gt_object.width <= 0 OR gt_object.height <= 0 THEN
            integrity_issues.Add(IntegrityIssue{
                type: "INVALID_DIMENSIONS",
                severity: "ERROR",
                message: "Bounding box has invalid dimensions",
                object_id: gt_object.id
            })
        END IF
    END FOR
    
    // Phase 4: Class Label Validation
    valid_classes ← GetValidVRUClasses()
    FOR EACH gt_object IN ground_truth_objects DO
        IF gt_object.class_label NOT IN valid_classes THEN
            integrity_issues.Add(IntegrityIssue{
                type: "INVALID_CLASS_LABEL",
                severity: "ERROR",
                message: "Invalid class label: " + gt_object.class_label,
                object_id: gt_object.id
            })
        END IF
    END FOR
    
    // Phase 5: Statistical Outlier Detection
    confidence_values ← ground_truth_objects.Map(obj → obj.confidence)
    outliers ← DetectStatisticalOutliers(confidence_values)
    
    FOR EACH outlier_index IN outliers DO
        gt_object ← ground_truth_objects[outlier_index]
        integrity_issues.Add(IntegrityIssue{
            type: "CONFIDENCE_OUTLIER",
            severity: "WARNING",
            message: "Confidence value is statistical outlier",
            object_id: gt_object.id,
            confidence: gt_object.confidence
        })
    END FOR
    
    RETURN IntegrityResult{
        video_id: video_id,
        total_objects_checked: ground_truth_objects.Length,
        issues_found: integrity_issues.Length,
        issues: integrity_issues,
        integrity_score: CalculateIntegrityScore(integrity_issues),
        passed_integrity: integrity_issues.Where(issue → issue.severity == "ERROR").IsEmpty()
    }
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n log n + m) where n = ground truth objects, m = integrity checks
    Space Complexity: O(n) for issue tracking
    Database Operations: 3-4 queries for different integrity checks
```

## 3. ALGORITHM PERFORMANCE METRICS

```
PERFORMANCE_TARGETS:
    GT_GENERATION_RATE = 30          // frames per second processing
    GT_VALIDATION_TIME = 2000        // milliseconds for full validation
    GT_EXPORT_TIME_PER_1K = 500      // milliseconds per 1000 objects
    INTEGRITY_CHECK_TIME = 1000      // milliseconds for full integrity check

MEMORY_LIMITS:
    MAX_BATCH_SIZE = 1000            // objects per database batch
    MAX_MEMORY_USAGE = 500           // MB during processing
    FRAME_CACHE_SIZE = 100           // frames to keep in memory

QUALITY_THRESHOLDS:
    MIN_CONFIDENCE_THRESHOLD = 0.3   // minimum detection confidence
    MIN_BBOX_AREA = 0.0001          // minimum bounding box area (normalized)
    MAX_BBOX_AREA = 0.5             // maximum bounding box area (normalized)
    FRAME_TIMESTAMP_TOLERANCE = 2    // frames tolerance for timestamp matching
    IOU_DUPLICATE_THRESHOLD = 0.9    // IoU threshold for duplicate detection
```

This comprehensive pseudocode provides the algorithmic foundation for robust ground truth management with proper data processing, validation, export capabilities, and integrity checking.
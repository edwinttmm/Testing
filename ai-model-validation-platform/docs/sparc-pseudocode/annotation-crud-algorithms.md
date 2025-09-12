# SPARC Pseudocode Phase: Annotation CRUD Algorithms

## Overview
Comprehensive implementation algorithms for annotation management with validation, security, and performance optimization.

## 1. ANNOTATION CRUD ALGORITHMS

### 1.1 Create Annotation Algorithm

```
ALGORITHM: CreateAnnotation
INPUT: annotation_data (AnnotationCreateRequest), user_id (string), session_info (SessionContext)
OUTPUT: annotation (Annotation) or error (ErrorResponse)

PRECONDITIONS:
    - annotation_data is valid JSON object
    - user_id is authenticated and authorized
    - video_id exists in database

BEGIN
    // Phase 1: Input Validation and Sanitization
    validation_result ← ValidateAnnotationInput(annotation_data)
    IF validation_result.has_errors THEN
        RETURN ValidationError(validation_result.errors)
    END IF
    
    sanitized_data ← SanitizeAnnotationData(annotation_data)
    
    // Phase 2: Authorization Check
    video ← Database.GetVideo(sanitized_data.video_id)
    IF video is null THEN
        AuditLog.Log(user_id, "ANNOTATION_CREATE_FAILED", "video_not_found")
        RETURN NotFoundError("Video not found")
    END IF
    
    access_granted ← CheckVideoAccess(user_id, video.project_id, "ANNOTATE")
    IF NOT access_granted THEN
        AuditLog.Log(user_id, "ANNOTATION_CREATE_UNAUTHORIZED", video.id)
        RETURN UnauthorizedError("Access denied to video")
    END IF
    
    // Phase 3: Business Logic Validation
    conflict_check ← CheckAnnotationConflict(
        sanitized_data.video_id,
        sanitized_data.frame_number,
        sanitized_data.bounding_box
    )
    
    IF conflict_check.has_conflicts THEN
        RETURN ConflictError("Overlapping annotation detected", conflict_check.conflicts)
    END IF
    
    // Phase 4: Detection ID Generation
    detection_id ← GenerateDetectionID(
        sanitized_data.vru_type,
        sanitized_data.frame_number
    )
    
    // Phase 5: Database Transaction
    transaction ← Database.BeginTransaction()
    TRY
        // Create annotation record
        annotation_record ← Annotation.Create({
            id: GenerateUUID(),
            video_id: sanitized_data.video_id,
            detection_id: detection_id,
            frame_number: sanitized_data.frame_number,
            timestamp: sanitized_data.timestamp,
            end_timestamp: sanitized_data.end_timestamp,
            vru_type: sanitized_data.vru_type,
            bounding_box: sanitized_data.bounding_box,
            occluded: sanitized_data.occluded,
            truncated: sanitized_data.truncated,
            difficult: sanitized_data.difficult,
            notes: sanitized_data.notes,
            annotator: user_id,
            validated: false,
            created_at: CurrentTimestamp(),
            updated_at: CurrentTimestamp()
        })
        
        // Update video ground truth status
        video.ground_truth_generated ← true
        video.updated_at ← CurrentTimestamp()
        Database.Update(video)
        
        // Create annotation session if not exists
        annotation_session ← GetOrCreateAnnotationSession(
            sanitized_data.video_id,
            video.project_id,
            user_id
        )
        
        annotation_session.total_detections ← annotation_session.total_detections + 1
        annotation_session.current_frame ← MAX(annotation_session.current_frame, sanitized_data.frame_number)
        annotation_session.updated_at ← CurrentTimestamp()
        Database.Update(annotation_session)
        
        transaction.Commit()
        
        // Phase 6: Post-Processing
        AuditLog.Log(user_id, "ANNOTATION_CREATED", {
            annotation_id: annotation_record.id,
            video_id: sanitized_data.video_id,
            detection_id: detection_id
        })
        
        // Trigger real-time updates
        WebSocket.Broadcast("annotation_created", {
            annotation: annotation_record,
            video_id: sanitized_data.video_id,
            project_id: video.project_id
        })
        
        RETURN AnnotationResponse.FromModel(annotation_record)
        
    CATCH database_error
        transaction.Rollback()
        AuditLog.Log(user_id, "ANNOTATION_CREATE_FAILED", {
            error: database_error.message,
            video_id: sanitized_data.video_id
        })
        RETURN DatabaseError("Failed to create annotation", database_error)
        
    FINALLY
        transaction.Close()
    END TRY
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(log n + m) where n = annotations in video, m = validation rules
    Space Complexity: O(1) for annotation data, O(k) for validation results
    Database Operations: 4-6 queries (read video, check conflicts, insert annotation, update video, session)
```

### 1.2 Read Annotation Algorithm

```
ALGORITHM: GetAnnotations
INPUT: video_id (string), filters (FilterOptions), pagination (PaginationOptions), user_id (string)
OUTPUT: annotations (List<Annotation>) or error (ErrorResponse)

BEGIN
    // Phase 1: Authorization Check
    video ← Database.GetVideo(video_id)
    IF video is null THEN
        RETURN NotFoundError("Video not found")
    END IF
    
    access_granted ← CheckVideoAccess(user_id, video.project_id, "READ")
    IF NOT access_granted THEN
        AuditLog.Log(user_id, "ANNOTATION_READ_UNAUTHORIZED", video_id)
        RETURN UnauthorizedError("Access denied")
    END IF
    
    // Phase 2: Build Optimized Query
    query_builder ← QueryBuilder.New("annotations")
    query_builder.Where("video_id", "=", video_id)
    
    // Apply filters with index optimization
    IF filters.vru_type is not null THEN
        query_builder.Where("vru_type", "=", filters.vru_type)
    END IF
    
    IF filters.frame_range is not null THEN
        query_builder.WhereBetween("frame_number", 
            filters.frame_range.start, 
            filters.frame_range.end)
    END IF
    
    IF filters.timestamp_range is not null THEN
        query_builder.WhereBetween("timestamp",
            filters.timestamp_range.start,
            filters.timestamp_range.end)
    END IF
    
    IF filters.validated is not null THEN
        query_builder.Where("validated", "=", filters.validated)
    END IF
    
    IF filters.annotator is not null THEN
        query_builder.Where("annotator", "=", filters.annotator)
    END IF
    
    // Apply sorting for consistent results
    sort_column ← filters.sort_by OR "timestamp"
    sort_direction ← filters.sort_direction OR "ASC"
    query_builder.OrderBy(sort_column, sort_direction)
    
    // Apply pagination
    offset ← pagination.page * pagination.limit
    query_builder.Offset(offset).Limit(pagination.limit)
    
    // Phase 3: Execute Query with Performance Monitoring
    start_time ← GetCurrentTime()
    annotations ← Database.Execute(query_builder)
    query_time ← GetCurrentTime() - start_time
    
    // Log slow queries for optimization
    IF query_time > SLOW_QUERY_THRESHOLD THEN
        AuditLog.Log(user_id, "SLOW_QUERY", {
            query_type: "get_annotations",
            execution_time: query_time,
            video_id: video_id,
            filters: filters
        })
    END IF
    
    // Phase 4: Get total count for pagination
    count_query ← QueryBuilder.New("annotations")
    count_query.Where("video_id", "=", video_id)
    ApplyFiltersToQuery(count_query, filters)
    total_count ← Database.Count(count_query)
    
    // Phase 5: Response Assembly
    response ← AnnotationListResponse{
        annotations: annotations.map(AnnotationResponse.FromModel),
        pagination: {
            page: pagination.page,
            limit: pagination.limit,
            total: total_count,
            has_next: (offset + pagination.limit) < total_count
        },
        metadata: {
            video_id: video_id,
            query_time: query_time,
            filters_applied: filters
        }
    }
    
    RETURN response
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(log n + k) where n = total annotations, k = returned results
    Space Complexity: O(k) for results
    Database Operations: 1-2 queries (annotations + count)
```

### 1.3 Update Annotation Algorithm

```
ALGORITHM: UpdateAnnotation
INPUT: annotation_id (string), update_data (AnnotationUpdateRequest), user_id (string)
OUTPUT: annotation (Annotation) or error (ErrorResponse)

BEGIN
    // Phase 1: Retrieve and Validate Existing Annotation
    existing_annotation ← Database.GetAnnotation(annotation_id)
    IF existing_annotation is null THEN
        RETURN NotFoundError("Annotation not found")
    END IF
    
    // Phase 2: Authorization Check
    video ← Database.GetVideo(existing_annotation.video_id)
    access_granted ← CheckVideoAccess(user_id, video.project_id, "ANNOTATE")
    
    IF NOT access_granted THEN
        AuditLog.Log(user_id, "ANNOTATION_UPDATE_UNAUTHORIZED", annotation_id)
        RETURN UnauthorizedError("Access denied")
    END IF
    
    // Check if user can edit this specific annotation
    IF existing_annotation.annotator != user_id AND NOT HasRole(user_id, "ADMIN") THEN
        RETURN UnauthorizedError("Can only edit your own annotations")
    END IF
    
    // Phase 3: Input Validation
    validation_result ← ValidateAnnotationUpdate(update_data, existing_annotation)
    IF validation_result.has_errors THEN
        RETURN ValidationError(validation_result.errors)
    END IF
    
    // Phase 4: Conflict Detection for Geometry Changes
    IF update_data.HasGeometryChanges() THEN
        new_bounding_box ← update_data.bounding_box OR existing_annotation.bounding_box
        new_frame_number ← update_data.frame_number OR existing_annotation.frame_number
        
        conflict_check ← CheckAnnotationConflict(
            existing_annotation.video_id,
            new_frame_number,
            new_bounding_box,
            exclude_id: annotation_id
        )
        
        IF conflict_check.has_conflicts THEN
            RETURN ConflictError("Update would create overlapping annotations", 
                conflict_check.conflicts)
        END IF
    END IF
    
    // Phase 5: Database Transaction
    transaction ← Database.BeginTransaction()
    TRY
        // Store original for audit trail
        original_values ← existing_annotation.ToDict()
        
        // Apply updates
        updated_annotation ← existing_annotation.Clone()
        ApplyUpdates(updated_annotation, update_data)
        updated_annotation.updated_at ← CurrentTimestamp()
        
        // If validation status changed, update metrics
        IF update_data.validated != existing_annotation.validated THEN
            annotation_session ← GetAnnotationSession(
                existing_annotation.video_id,
                user_id
            )
            
            IF update_data.validated THEN
                annotation_session.validated_detections += 1
            ELSE
                annotation_session.validated_detections -= 1
            END IF
            
            Database.Update(annotation_session)
        END IF
        
        Database.Update(updated_annotation)
        transaction.Commit()
        
        // Phase 6: Post-Processing
        changes ← CalculateChanges(original_values, updated_annotation.ToDict())
        
        AuditLog.Log(user_id, "ANNOTATION_UPDATED", {
            annotation_id: annotation_id,
            video_id: existing_annotation.video_id,
            changes: changes
        })
        
        // Real-time update notification
        WebSocket.Broadcast("annotation_updated", {
            annotation: updated_annotation,
            changes: changes,
            video_id: existing_annotation.video_id
        })
        
        RETURN AnnotationResponse.FromModel(updated_annotation)
        
    CATCH database_error
        transaction.Rollback()
        AuditLog.Log(user_id, "ANNOTATION_UPDATE_FAILED", {
            annotation_id: annotation_id,
            error: database_error.message
        })
        RETURN DatabaseError("Failed to update annotation", database_error)
        
    FINALLY
        transaction.Close()
    END TRY
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(log n) for database operations, O(1) for updates
    Space Complexity: O(1) for single annotation
    Database Operations: 3-5 queries (read, conflict check, update, session update)
```

### 1.4 Delete Annotation Algorithm

```
ALGORITHM: DeleteAnnotation
INPUT: annotation_id (string), user_id (string), options (DeleteOptions)
OUTPUT: success (boolean) or error (ErrorResponse)

BEGIN
    // Phase 1: Retrieve and Validate
    annotation ← Database.GetAnnotation(annotation_id)
    IF annotation is null THEN
        RETURN NotFoundError("Annotation not found")
    END IF
    
    // Phase 2: Authorization Check
    video ← Database.GetVideo(annotation.video_id)
    access_granted ← CheckVideoAccess(user_id, video.project_id, "ANNOTATE")
    
    IF NOT access_granted THEN
        AuditLog.Log(user_id, "ANNOTATION_DELETE_UNAUTHORIZED", annotation_id)
        RETURN UnauthorizedError("Access denied")
    END IF
    
    // Check ownership or admin rights
    IF annotation.annotator != user_id AND NOT HasRole(user_id, "ADMIN") THEN
        RETURN UnauthorizedError("Can only delete your own annotations")
    END IF
    
    // Phase 3: Dependency Check
    dependencies ← CheckAnnotationDependencies(annotation_id)
    IF dependencies.has_dependencies AND NOT options.force_delete THEN
        RETURN ConflictError("Annotation has dependencies", dependencies)
    END IF
    
    // Phase 4: Soft vs Hard Delete Decision
    delete_type ← DetermineDeleteType(annotation, options)
    
    transaction ← Database.BeginTransaction()
    TRY
        IF delete_type == "SOFT" THEN
            // Soft delete - mark as deleted but keep data
            annotation.deleted_at ← CurrentTimestamp()
            annotation.deleted_by ← user_id
            annotation.updated_at ← CurrentTimestamp()
            Database.Update(annotation)
        ELSE
            // Hard delete - remove from database
            Database.Delete(annotation)
            
            // Clean up related data if specified
            IF options.cleanup_related THEN
                CleanupRelatedData(annotation_id)
            END IF
        END IF
        
        // Update annotation session metrics
        annotation_session ← GetAnnotationSession(annotation.video_id, user_id)
        annotation_session.total_detections -= 1
        
        IF annotation.validated THEN
            annotation_session.validated_detections -= 1
        END IF
        
        Database.Update(annotation_session)
        
        // Update video ground truth status if no annotations left
        remaining_count ← CountAnnotations(annotation.video_id, exclude_deleted: true)
        IF remaining_count == 0 THEN
            video.ground_truth_generated ← false
            Database.Update(video)
        END IF
        
        transaction.Commit()
        
        // Phase 5: Post-Processing
        AuditLog.Log(user_id, "ANNOTATION_DELETED", {
            annotation_id: annotation_id,
            video_id: annotation.video_id,
            delete_type: delete_type,
            detection_id: annotation.detection_id
        })
        
        // Real-time notification
        WebSocket.Broadcast("annotation_deleted", {
            annotation_id: annotation_id,
            video_id: annotation.video_id,
            delete_type: delete_type
        })
        
        RETURN SuccessResponse{
            deleted: true,
            annotation_id: annotation_id,
            delete_type: delete_type
        }
        
    CATCH database_error
        transaction.Rollback()
        AuditLog.Log(user_id, "ANNOTATION_DELETE_FAILED", {
            annotation_id: annotation_id,
            error: database_error.message
        })
        RETURN DatabaseError("Failed to delete annotation", database_error)
        
    FINALLY
        transaction.Close()
    END TRY
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(log n) for database operations
    Space Complexity: O(1) for single annotation
    Database Operations: 4-6 queries (read, dependencies, delete/update, session update, video update)
```

## 2. SUPPORTING ALGORITHMS

### 2.1 Annotation Validation Algorithm

```
ALGORITHM: ValidateAnnotationInput
INPUT: annotation_data (AnnotationCreateRequest)
OUTPUT: validation_result (ValidationResult)

BEGIN
    errors ← EmptyList()
    warnings ← EmptyList()
    
    // Video ID validation
    IF annotation_data.video_id is null OR IsEmpty(annotation_data.video_id) THEN
        errors.Add("video_id is required")
    ELSE IF NOT IsValidUUID(annotation_data.video_id) THEN
        errors.Add("video_id must be a valid UUID")
    END IF
    
    // Frame number validation
    IF annotation_data.frame_number is null THEN
        errors.Add("frame_number is required")
    ELSE IF annotation_data.frame_number < 0 THEN
        errors.Add("frame_number must be non-negative")
    END IF
    
    // Timestamp validation
    IF annotation_data.timestamp is null THEN
        errors.Add("timestamp is required")
    ELSE IF annotation_data.timestamp < 0 THEN
        errors.Add("timestamp must be non-negative")
    END IF
    
    // End timestamp validation (if provided)
    IF annotation_data.end_timestamp is not null THEN
        IF annotation_data.end_timestamp <= annotation_data.timestamp THEN
            errors.Add("end_timestamp must be greater than timestamp")
        END IF
    END IF
    
    // VRU type validation
    valid_vru_types ← ["pedestrian", "cyclist", "motorcyclist", "wheelchair", "scooter"]
    IF annotation_data.vru_type is null OR IsEmpty(annotation_data.vru_type) THEN
        errors.Add("vru_type is required")
    ELSE IF annotation_data.vru_type NOT IN valid_vru_types THEN
        errors.Add("vru_type must be one of: " + Join(valid_vru_types, ", "))
    END IF
    
    // Bounding box validation
    IF annotation_data.bounding_box is null THEN
        errors.Add("bounding_box is required")
    ELSE
        bbox ← annotation_data.bounding_box
        
        // Required fields
        required_fields ← ["x", "y", "width", "height"]
        FOR EACH field IN required_fields DO
            IF bbox[field] is null THEN
                errors.Add("bounding_box." + field + " is required")
            ELSE IF NOT IsNumeric(bbox[field]) THEN
                errors.Add("bounding_box." + field + " must be numeric")
            END IF
        END FOR
        
        // Geometric constraints
        IF bbox.width <= 0 THEN
            errors.Add("bounding_box.width must be positive")
        END IF
        
        IF bbox.height <= 0 THEN
            errors.Add("bounding_box.height must be positive")
        END IF
        
        // Coordinate bounds (assuming normalized coordinates)
        IF bbox.x < 0 OR bbox.x > 1 THEN
            errors.Add("bounding_box.x must be between 0 and 1")
        END IF
        
        IF bbox.y < 0 OR bbox.y > 1 THEN
            errors.Add("bounding_box.y must be between 0 and 1")
        END IF
        
        IF (bbox.x + bbox.width) > 1 THEN
            errors.Add("bounding_box extends beyond image width")
        END IF
        
        IF (bbox.y + bbox.height) > 1 THEN
            errors.Add("bounding_box extends beyond image height")
        END IF
        
        // Size validation
        min_size ← 0.001  // 0.1% of image
        max_size ← 0.8    // 80% of image
        
        IF (bbox.width * bbox.height) < min_size THEN
            warnings.Add("Bounding box is very small, may be difficult to validate")
        END IF
        
        IF (bbox.width * bbox.height) > max_size THEN
            warnings.Add("Bounding box is very large, may contain multiple objects")
        END IF
    END IF
    
    // Notes validation (if provided)
    IF annotation_data.notes is not null THEN
        IF Length(annotation_data.notes) > 1000 THEN
            errors.Add("notes cannot exceed 1000 characters")
        END IF
        
        // Check for potentially harmful content
        IF ContainsHarmfulContent(annotation_data.notes) THEN
            errors.Add("notes contain inappropriate content")
        END IF
    END IF
    
    RETURN ValidationResult{
        has_errors: errors.Length > 0,
        has_warnings: warnings.Length > 0,
        errors: errors,
        warnings: warnings
    }
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(1) - constant time validation
    Space Complexity: O(1) - bounded by validation rules
```

### 2.2 Annotation Conflict Detection Algorithm

```
ALGORITHM: CheckAnnotationConflict
INPUT: video_id (string), frame_number (int), bounding_box (BoundingBox), exclude_id (string, optional)
OUTPUT: conflict_result (ConflictResult)

BEGIN
    // Phase 1: Get potentially conflicting annotations
    query ← QueryBuilder.New("annotations")
    query.Where("video_id", "=", video_id)
    query.Where("frame_number", "=", frame_number)
    
    IF exclude_id is not null THEN
        query.Where("id", "!=", exclude_id)
    END IF
    
    existing_annotations ← Database.Execute(query)
    
    conflicts ← EmptyList()
    
    // Phase 2: Check spatial overlap
    FOR EACH existing IN existing_annotations DO
        overlap_result ← CalculateBoundingBoxOverlap(bounding_box, existing.bounding_box)
        
        IF overlap_result.iou > IOU_THRESHOLD THEN
            conflict ← ConflictInfo{
                annotation_id: existing.id,
                conflict_type: "SPATIAL_OVERLAP",
                iou_score: overlap_result.iou,
                overlap_percentage: overlap_result.overlap_percentage,
                severity: DetermineConflictSeverity(overlap_result.iou)
            }
            conflicts.Add(conflict)
        END IF
    END FOR
    
    // Phase 3: Check for temporal conflicts (if applicable)
    // This is more complex for video annotations with duration
    
    RETURN ConflictResult{
        has_conflicts: conflicts.Length > 0,
        conflicts: conflicts,
        total_conflicts: conflicts.Length
    }
END

SUBROUTINE: CalculateBoundingBoxOverlap
INPUT: bbox1 (BoundingBox), bbox2 (BoundingBox)
OUTPUT: overlap_result (OverlapResult)

BEGIN
    // Calculate intersection rectangle
    x_left ← MAX(bbox1.x, bbox2.x)
    y_top ← MAX(bbox1.y, bbox2.y)
    x_right ← MIN(bbox1.x + bbox1.width, bbox2.x + bbox2.width)
    y_bottom ← MIN(bbox1.y + bbox1.height, bbox2.y + bbox2.height)
    
    // Check if there's any intersection
    IF x_right <= x_left OR y_bottom <= y_top THEN
        RETURN OverlapResult{
            iou: 0.0,
            overlap_percentage: 0.0,
            intersection_area: 0.0
        }
    END IF
    
    // Calculate areas
    intersection_area ← (x_right - x_left) * (y_bottom - y_top)
    bbox1_area ← bbox1.width * bbox1.height
    bbox2_area ← bbox2.width * bbox2.height
    union_area ← bbox1_area + bbox2_area - intersection_area
    
    // Calculate IoU (Intersection over Union)
    iou ← intersection_area / union_area
    
    // Calculate overlap percentage (intersection over smaller box)
    smaller_area ← MIN(bbox1_area, bbox2_area)
    overlap_percentage ← intersection_area / smaller_area
    
    RETURN OverlapResult{
        iou: iou,
        overlap_percentage: overlap_percentage,
        intersection_area: intersection_area
    }
END

COMPLEXITY ANALYSIS:
    Time Complexity: O(n) where n = annotations in same frame
    Space Complexity: O(n) for conflict results
    Database Operations: 1 query to get existing annotations
```

## 3. ALGORITHM CONSTANTS AND CONFIGURATIONS

```
CONSTANTS:
    IOU_THRESHOLD = 0.3              // Minimum IoU to consider conflict
    SLOW_QUERY_THRESHOLD = 1000      // Milliseconds
    MAX_ANNOTATION_NOTES_LENGTH = 1000
    MIN_BBOX_SIZE = 0.001            // Minimum bounding box size (normalized)
    MAX_BBOX_SIZE = 0.8              // Maximum bounding box size (normalized)
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 200

PERFORMANCE_TARGETS:
    CREATE_ANNOTATION_TIME_TARGET = 100    // milliseconds
    READ_ANNOTATIONS_TIME_TARGET = 50      // milliseconds
    UPDATE_ANNOTATION_TIME_TARGET = 75     // milliseconds
    DELETE_ANNOTATION_TIME_TARGET = 50     // milliseconds

ERROR_CODES:
    ANNOTATION_NOT_FOUND = "ANN_001"
    INVALID_BOUNDING_BOX = "ANN_002"
    SPATIAL_CONFLICT = "ANN_003"
    UNAUTHORIZED_ACCESS = "ANN_004"
    VALIDATION_FAILED = "ANN_005"
    DATABASE_ERROR = "ANN_006"
```

This comprehensive pseudocode provides the algorithmic foundation for implementing robust annotation CRUD operations with proper validation, security, and performance considerations.
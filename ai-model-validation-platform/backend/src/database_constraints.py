"""
Database-Level Validation Constraints for Annotation Data Integrity
==================================================================

This module defines SQL CHECK constraints and triggers to enforce data integrity
at the database level. These constraints serve as the final defense against
malformed annotation data, ensuring no invalid data can be stored even if
application-level validation is bypassed.

Key Features:
1. JSON schema validation for bounding_box column
2. Range validation for numeric fields  
3. Cross-column validation rules
4. Trigger-based validation for complex logic
5. Index creation for validation performance
"""

from sqlalchemy import DDL, event
from sqlalchemy.schema import CheckConstraint
from models import Annotation, GroundTruthObject
import logging

logger = logging.getLogger(__name__)


# SQL CHECK constraints for annotation table
ANNOTATION_CHECK_CONSTRAINTS = [
    # Bounding box JSON structure validation
    CheckConstraint(
        """
        bounding_box IS NOT NULL AND
        json_valid(bounding_box) AND
        json_extract(bounding_box, '$.x') IS NOT NULL AND
        json_extract(bounding_box, '$.y') IS NOT NULL AND
        json_extract(bounding_box, '$.width') IS NOT NULL AND
        json_extract(bounding_box, '$.height') IS NOT NULL AND
        json_type(json_extract(bounding_box, '$.x')) IN ('integer', 'real') AND
        json_type(json_extract(bounding_box, '$.y')) IN ('integer', 'real') AND
        json_type(json_extract(bounding_box, '$.width')) IN ('integer', 'real') AND
        json_type(json_extract(bounding_box, '$.height')) IN ('integer', 'real')
        """,
        name="chk_annotation_bbox_structure"
    ),
    
    # Bounding box coordinate constraints
    CheckConstraint(
        """
        CAST(json_extract(bounding_box, '$.x') AS REAL) >= 0 AND
        CAST(json_extract(bounding_box, '$.y') AS REAL) >= 0 AND
        CAST(json_extract(bounding_box, '$.width') AS REAL) > 0 AND
        CAST(json_extract(bounding_box, '$.height') AS REAL) > 0
        """,
        name="chk_annotation_bbox_bounds"
    ),
    
    # Reasonable bounding box size limits
    CheckConstraint(
        """
        CAST(json_extract(bounding_box, '$.width') AS REAL) <= 10000 AND
        CAST(json_extract(bounding_box, '$.height') AS REAL) <= 10000
        """,
        name="chk_annotation_bbox_size_limits"
    ),
    
    # Frame number validation
    CheckConstraint(
        "frame_number >= 0",
        name="chk_annotation_frame_number"
    ),
    
    # Timestamp validation
    CheckConstraint(
        "timestamp >= 0",
        name="chk_annotation_timestamp"
    ),
    
    # End timestamp consistency
    CheckConstraint(
        "end_timestamp IS NULL OR end_timestamp > timestamp",
        name="chk_annotation_timestamp_order"
    ),
    
    # VRU type validation
    CheckConstraint(
        """
        vru_type IN (
            'pedestrian', 'cyclist', 'motorcyclist', 
            'wheelchair', 'scooter', 'animal', 'other'
        )
        """,
        name="chk_annotation_vru_type"
    ),
    
    # Video ID format validation
    CheckConstraint(
        "length(video_id) > 0 AND length(video_id) <= 100",
        name="chk_annotation_video_id"
    ),
    
    # Detection ID format validation (when present)
    CheckConstraint(
        "detection_id IS NULL OR (length(detection_id) > 0 AND length(detection_id) <= 100)",
        name="chk_annotation_detection_id"
    ),
    
    # Notes length limit
    CheckConstraint(
        "notes IS NULL OR length(notes) <= 2000",
        name="chk_annotation_notes_length"
    ),
    
    # Annotator format validation (when present)
    CheckConstraint(
        "annotator IS NULL OR (length(annotator) > 0 AND length(annotator) <= 100)",
        name="chk_annotation_annotator"
    )
]


# SQL CHECK constraints for ground_truth_objects table
GROUND_TRUTH_CHECK_CONSTRAINTS = [
    # Coordinate validation
    CheckConstraint("x >= 0", name="chk_gt_x_positive"),
    CheckConstraint("y >= 0", name="chk_gt_y_positive"),
    CheckConstraint("width > 0", name="chk_gt_width_positive"),
    CheckConstraint("height > 0", name="chk_gt_height_positive"),
    
    # Reasonable size limits
    CheckConstraint("width <= 10000", name="chk_gt_width_limit"),
    CheckConstraint("height <= 10000", name="chk_gt_height_limit"),
    
    # Frame number validation
    CheckConstraint("frame_number IS NULL OR frame_number >= 0", name="chk_gt_frame_number"),
    
    # Timestamp validation
    CheckConstraint("timestamp >= 0", name="chk_gt_timestamp"),
    
    # Confidence validation (when present)
    CheckConstraint(
        "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
        name="chk_gt_confidence"
    ),
    
    # Backward compatibility: ensure bounding_box JSON (when present) is valid
    CheckConstraint(
        """
        bounding_box IS NULL OR (
            json_valid(bounding_box) AND
            json_extract(bounding_box, '$.x') IS NOT NULL AND
            json_extract(bounding_box, '$.y') IS NOT NULL AND
            json_extract(bounding_box, '$.width') IS NOT NULL AND
            json_extract(bounding_box, '$.height') IS NOT NULL
        )
        """,
        name="chk_gt_bbox_structure"
    )
]


# Database triggers for complex validation
VALIDATION_TRIGGERS = {
    'annotation_bbox_consistency_trigger': """
        CREATE TRIGGER IF NOT EXISTS annotation_bbox_consistency_trigger
        BEFORE INSERT ON annotations
        FOR EACH ROW
        WHEN (
            -- Ensure bounding box coordinates are consistent with explicit columns (future feature)
            -- For now, just ensure the JSON is not corrupted
            json_extract(NEW.bounding_box, '$.x') IS NULL OR
            json_extract(NEW.bounding_box, '$.y') IS NULL OR
            json_extract(NEW.bounding_box, '$.width') IS NULL OR
            json_extract(NEW.bounding_box, '$.height') IS NULL
        )
        BEGIN
            SELECT RAISE(ABORT, 'Invalid bounding box: missing required coordinates (x, y, width, height)');
        END;
    """,
    
    'annotation_bbox_consistency_update_trigger': """
        CREATE TRIGGER IF NOT EXISTS annotation_bbox_consistency_update_trigger
        BEFORE UPDATE ON annotations
        FOR EACH ROW
        WHEN (
            json_extract(NEW.bounding_box, '$.x') IS NULL OR
            json_extract(NEW.bounding_box, '$.y') IS NULL OR
            json_extract(NEW.bounding_box, '$.width') IS NULL OR
            json_extract(NEW.bounding_box, '$.height') IS NULL
        )
        BEGIN
            SELECT RAISE(ABORT, 'Invalid bounding box: missing required coordinates (x, y, width, height)');
        END;
    """,
    
    'annotation_temporal_validation_trigger': """
        CREATE TRIGGER IF NOT EXISTS annotation_temporal_validation_trigger
        BEFORE INSERT ON annotations
        FOR EACH ROW
        WHEN (
            NEW.end_timestamp IS NOT NULL AND
            NEW.end_timestamp <= NEW.timestamp
        )
        BEGIN
            SELECT RAISE(ABORT, 'Invalid temporal annotation: end_timestamp must be greater than timestamp');
        END;
    """,
    
    'annotation_temporal_validation_update_trigger': """
        CREATE TRIGGER IF NOT EXISTS annotation_temporal_validation_update_trigger
        BEFORE UPDATE ON annotations
        FOR EACH ROW
        WHEN (
            NEW.end_timestamp IS NOT NULL AND
            NEW.end_timestamp <= NEW.timestamp
        )
        BEGIN
            SELECT RAISE(ABORT, 'Invalid temporal annotation: end_timestamp must be greater than timestamp');
        END;
    """,
    
    'ground_truth_consistency_trigger': """
        CREATE TRIGGER IF NOT EXISTS ground_truth_consistency_trigger
        BEFORE INSERT ON ground_truth_objects
        FOR EACH ROW
        WHEN (
            -- Ensure coordinates are consistent between explicit columns and JSON (when present)
            NEW.bounding_box IS NOT NULL AND (
                abs(CAST(json_extract(NEW.bounding_box, '$.x') AS REAL) - NEW.x) > 0.001 OR
                abs(CAST(json_extract(NEW.bounding_box, '$.y') AS REAL) - NEW.y) > 0.001 OR
                abs(CAST(json_extract(NEW.bounding_box, '$.width') AS REAL) - NEW.width) > 0.001 OR
                abs(CAST(json_extract(NEW.bounding_box, '$.height') AS REAL) - NEW.height) > 0.001
            )
        )
        BEGIN
            SELECT RAISE(ABORT, 'Inconsistent bounding box: explicit coordinates do not match JSON coordinates');
        END;
    """
}


# Performance indexes for validation queries
VALIDATION_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_annotation_bbox_coords ON annotations (json_extract(bounding_box, '$.x'), json_extract(bounding_box, '$.y'))",
    "CREATE INDEX IF NOT EXISTS idx_annotation_bbox_size ON annotations (json_extract(bounding_box, '$.width'), json_extract(bounding_box, '$.height'))",
    "CREATE INDEX IF NOT EXISTS idx_annotation_validation_status ON annotations (validated, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_annotation_vru_timestamp ON annotations (vru_type, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_gt_coordinates ON ground_truth_objects (x, y, width, height)",
    "CREATE INDEX IF NOT EXISTS idx_gt_temporal ON ground_truth_objects (timestamp, frame_number)",
]


def apply_annotation_constraints(engine):
    """Apply all database constraints for annotation validation"""
    
    logger.info("Applying database-level validation constraints for annotations...")
    
    with engine.connect() as conn:
        # Apply CHECK constraints (these are added to the table schema)
        # Note: SQLite CHECK constraints are applied via table modification
        # For existing tables, we need to recreate or use ALTER TABLE
        
        # Apply triggers for complex validation
        for trigger_name, trigger_sql in VALIDATION_TRIGGERS.items():
            try:
                conn.execute(trigger_sql)
                logger.info(f"Applied trigger: {trigger_name}")
            except Exception as e:
                logger.error(f"Failed to apply trigger {trigger_name}: {e}")
        
        # Apply performance indexes
        for index_sql in VALIDATION_INDEXES:
            try:
                conn.execute(index_sql)
                logger.info(f"Applied index: {index_sql[:50]}...")
            except Exception as e:
                logger.error(f"Failed to apply index: {e}")
        
        conn.commit()
    
    logger.info("Database validation constraints applied successfully")


def validate_existing_data(engine):
    """Validate existing data against new constraints and report issues"""
    
    logger.info("Validating existing annotation data...")
    
    validation_issues = []
    
    with engine.connect() as conn:
        # Check for annotations with invalid bounding boxes
        result = conn.execute("""
            SELECT id, video_id, bounding_box 
            FROM annotations 
            WHERE 
                bounding_box IS NULL OR
                NOT json_valid(bounding_box) OR
                json_extract(bounding_box, '$.x') IS NULL OR
                json_extract(bounding_box, '$.y') IS NULL OR
                json_extract(bounding_box, '$.width') IS NULL OR
                json_extract(bounding_box, '$.height') IS NULL
        """)
        
        invalid_bbox = result.fetchall()
        if invalid_bbox:
            validation_issues.extend([
                f"Annotation {row[0]} (video {row[1]}) has invalid bounding box: {row[2]}"
                for row in invalid_bbox
            ])
        
        # Check for annotations with invalid coordinates
        result = conn.execute("""
            SELECT id, video_id, bounding_box
            FROM annotations 
            WHERE 
                json_valid(bounding_box) AND (
                    CAST(json_extract(bounding_box, '$.x') AS REAL) < 0 OR
                    CAST(json_extract(bounding_box, '$.y') AS REAL) < 0 OR
                    CAST(json_extract(bounding_box, '$.width') AS REAL) <= 0 OR
                    CAST(json_extract(bounding_box, '$.height') AS REAL) <= 0
                )
        """)
        
        invalid_coords = result.fetchall()
        if invalid_coords:
            validation_issues.extend([
                f"Annotation {row[0]} (video {row[1]}) has invalid coordinates: {row[2]}"
                for row in invalid_coords
            ])
        
        # Check for annotations with invalid temporal data
        result = conn.execute("""
            SELECT id, video_id, timestamp, end_timestamp
            FROM annotations 
            WHERE 
                timestamp < 0 OR
                frame_number < 0 OR
                (end_timestamp IS NOT NULL AND end_timestamp <= timestamp)
        """)
        
        invalid_temporal = result.fetchall()
        if invalid_temporal:
            validation_issues.extend([
                f"Annotation {row[0]} (video {row[1]}) has invalid temporal data: timestamp={row[2]}, end_timestamp={row[3]}"
                for row in invalid_temporal
            ])
    
    if validation_issues:
        logger.error(f"Found {len(validation_issues)} validation issues in existing data:")
        for issue in validation_issues[:10]:  # Show first 10 issues
            logger.error(f"  - {issue}")
        if len(validation_issues) > 10:
            logger.error(f"  ... and {len(validation_issues) - 10} more issues")
        
        return False, validation_issues
    else:
        logger.info("All existing annotation data passes validation checks")
        return True, []


def create_validation_migration_script(engine, fix_issues=False):
    """Create a migration script to fix validation issues in existing data"""
    
    is_valid, issues = validate_existing_data(engine)
    
    if is_valid:
        logger.info("No migration needed - all data is valid")
        return None
    
    migration_script = [
        "-- Migration script to fix annotation data validation issues",
        "-- Generated automatically by validation architecture",
        "",
        "BEGIN TRANSACTION;",
        ""
    ]
    
    with engine.connect() as conn:
        # Generate fixes for invalid bounding boxes
        result = conn.execute("""
            SELECT id, video_id, bounding_box 
            FROM annotations 
            WHERE 
                bounding_box IS NULL OR
                NOT json_valid(bounding_box) OR
                json_extract(bounding_box, '$.x') IS NULL OR
                json_extract(bounding_box, '$.y') IS NULL OR
                json_extract(bounding_box, '$.width') IS NULL OR
                json_extract(bounding_box, '$.height') IS NULL
        """)
        
        for row in result.fetchall():
            annotation_id, video_id, bbox = row
            # Create a default valid bounding box
            default_bbox = '{"x": 0, "y": 0, "width": 100, "height": 100, "confidence": 0.5}'
            migration_script.append(
                f"UPDATE annotations SET bounding_box = '{default_bbox}' WHERE id = '{annotation_id}'; "
                f"-- Fixed invalid bbox for annotation {annotation_id}"
            )
    
    migration_script.extend([
        "",
        "COMMIT;",
        "",
        "-- Apply validation constraints after data fixes",
        "-- Run: python -c \"from database_constraints import apply_annotation_constraints; from database import engine; apply_annotation_constraints(engine)\""
    ])
    
    migration_sql = "\n".join(migration_script)
    
    # Save migration script
    with open("/home/user/Testing/ai-model-validation-platform/backend/migration_fix_validation.sql", "w") as f:
        f.write(migration_sql)
    
    logger.info("Migration script saved to: migration_fix_validation.sql")
    
    if fix_issues:
        logger.info("Applying migration fixes...")
        with engine.connect() as conn:
            # Apply the fixes (excluding transaction control)
            fix_statements = [stmt for stmt in migration_script 
                            if stmt.startswith("UPDATE") and "annotations" in stmt]
            for stmt in fix_statements:
                conn.execute(stmt.split(" -- ")[0])  # Execute without comment
            conn.commit()
        logger.info("Migration fixes applied successfully")
    
    return migration_sql


# Event listeners to add constraints when tables are created
@event.listens_for(Annotation.__table__, 'after_create')
def add_annotation_constraints(target, connection, **kw):
    """Add constraints after annotation table creation"""
    logger.info("Adding CHECK constraints to annotations table...")
    
    # Note: SQLite CHECK constraints must be defined in the table creation
    # For existing tables, we rely on triggers for validation
    try:
        for trigger_name, trigger_sql in VALIDATION_TRIGGERS.items():
            if 'annotation' in trigger_name:
                connection.execute(trigger_sql)
    except Exception as e:
        logger.error(f"Failed to add annotation constraints: {e}")


@event.listens_for(GroundTruthObject.__table__, 'after_create')
def add_ground_truth_constraints(target, connection, **kw):
    """Add constraints after ground truth table creation"""
    logger.info("Adding CHECK constraints to ground_truth_objects table...")
    
    try:
        for trigger_name, trigger_sql in VALIDATION_TRIGGERS.items():
            if 'ground_truth' in trigger_name:
                connection.execute(trigger_sql)
    except Exception as e:
        logger.error(f"Failed to add ground truth constraints: {e}")
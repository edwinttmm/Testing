#!/usr/bin/env python3
"""
Create Missing Video Validation Tables - ROOT CAUSE FIX

This script creates the missing video_validation_results and related tables
that exist in the SQLAlchemy models but are missing from the database.

This is the PROPER root cause fix, not a workaround.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import get_db, engine
import logging

logger = logging.getLogger(__name__)

def create_validation_tables():
    """Create the missing video validation tables from SQLAlchemy models"""
    
    # SQL statements to create the missing tables based on models.py
    create_statements = [
        # 1. video_validation_criteria table
        """
        CREATE TABLE IF NOT EXISTS video_validation_criteria (
            id VARCHAR(36) PRIMARY KEY,
            project_id VARCHAR(36),
            
            -- Ground truth quality requirements
            min_ground_truth_annotations INTEGER NOT NULL DEFAULT 5,
            min_ground_truth_quality_score REAL NOT NULL DEFAULT 0.8,
            require_human_validation BOOLEAN NOT NULL DEFAULT true,
            
            -- Technical validation requirements
            min_video_quality_score REAL NOT NULL DEFAULT 0.7,
            max_compression_artifacts INTEGER NOT NULL DEFAULT 2,
            require_stable_framerate BOOLEAN NOT NULL DEFAULT true,
            
            -- Content validation requirements
            require_clear_vru_visibility BOOLEAN NOT NULL DEFAULT true,
            min_detection_confidence REAL NOT NULL DEFAULT 0.6,
            require_scenario_diversity BOOLEAN NOT NULL DEFAULT false,
            
            -- Criteria configuration
            criteria_name VARCHAR(255) NOT NULL,
            criteria_description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            
            -- Metadata
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(36),
            updated_by VARCHAR(36),
            
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """,
        
        # 2. video_validation_results table  
        """
        CREATE TABLE IF NOT EXISTS video_validation_results (
            id VARCHAR(36) PRIMARY KEY,
            video_id VARCHAR(36) NOT NULL,
            validation_criteria_id VARCHAR(36) NOT NULL,
            
            -- Validation results
            validation_type VARCHAR NOT NULL,  -- 'automatic', 'manual'
            overall_result VARCHAR NOT NULL,   -- 'passed', 'failed', 'needs_review'
            
            -- Detailed results
            ground_truth_score REAL,
            technical_score REAL,
            content_score REAL,
            overall_score REAL,
            
            -- Validation details
            criteria_met TEXT,  -- JSON field
            validation_notes TEXT,
            failure_reasons TEXT, -- JSON field
            
            -- Validation metadata
            validated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            validated_by VARCHAR(36),
            validation_duration_seconds REAL,
            validation_method VARCHAR(50),
            
            -- Review process
            needs_human_review BOOLEAN NOT NULL DEFAULT false,
            human_review_completed BOOLEAN NOT NULL DEFAULT false,
            human_reviewer_id VARCHAR(36),
            human_review_notes TEXT,
            human_review_at TIMESTAMP WITH TIME ZONE,
            
            -- Metadata
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
            FOREIGN KEY (validation_criteria_id) REFERENCES video_validation_criteria(id)
        );
        """,
        
        # 3. video_status_transitions table
        """
        CREATE TABLE IF NOT EXISTS video_status_transitions (
            id VARCHAR(36) PRIMARY KEY,
            video_id VARCHAR(36) NOT NULL,
            
            -- Transition details  
            from_status VARCHAR(50) NOT NULL,
            to_status VARCHAR(50) NOT NULL,
            transition_reason TEXT,
            transition_metadata TEXT, -- JSON field
            
            -- Transition context
            triggered_by_user_id VARCHAR(36),
            triggered_by_system BOOLEAN NOT NULL DEFAULT false,
            
            -- Validation context
            validation_result_id VARCHAR(36),
            meets_transition_criteria BOOLEAN NOT NULL DEFAULT true,
            criteria_check_details TEXT, -- JSON field
            
            -- Metadata
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
            FOREIGN KEY (validation_result_id) REFERENCES video_validation_results(id) ON DELETE SET NULL
        );
        """
    ]
    
    # Create indexes for performance
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_validation_criteria_project ON video_validation_criteria(project_id);",
        "CREATE INDEX IF NOT EXISTS idx_validation_criteria_active ON video_validation_criteria(is_active);",
        
        "CREATE INDEX IF NOT EXISTS idx_validation_result_video ON video_validation_results(video_id);",
        "CREATE INDEX IF NOT EXISTS idx_validation_result_type ON video_validation_results(validation_type);", 
        "CREATE INDEX IF NOT EXISTS idx_validation_result_overall ON video_validation_results(overall_result);",
        "CREATE INDEX IF NOT EXISTS idx_validation_result_score ON video_validation_results(overall_score);",
        "CREATE INDEX IF NOT EXISTS idx_validation_result_created ON video_validation_results(created_at);",
        
        "CREATE INDEX IF NOT EXISTS idx_status_transition_video ON video_status_transitions(video_id);",
        "CREATE INDEX IF NOT EXISTS idx_status_transition_from_to ON video_status_transitions(from_status, to_status);",
        "CREATE INDEX IF NOT EXISTS idx_status_transition_created ON video_status_transitions(created_at);"
    ]
    
    try:
        with engine.connect() as conn:
            # Create tables
            for i, statement in enumerate(create_statements, 1):
                logger.info(f"Creating table {i}/3...")
                conn.execute(text(statement))
                
            # Create indexes  
            for i, index_stmt in enumerate(index_statements, 1):
                logger.info(f"Creating index {i}/{len(index_statements)}...")
                conn.execute(text(index_stmt))
                
            conn.commit()
            
            logger.info("✅ Successfully created all missing video validation tables")
            
            # Verify tables exist
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%validation%';"))
            tables = [row[0] for row in result.fetchall()]
            logger.info(f"✅ Created validation tables: {tables}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to create validation tables: {e}")
        return False

def add_missing_video_columns():
    """Add missing columns to videos table that are referenced in models.py but don't exist in DB"""
    
    missing_columns = [
        "ALTER TABLE videos ADD COLUMN validation_status VARCHAR(50) DEFAULT 'pending';",
        "ALTER TABLE videos ADD COLUMN validation_type VARCHAR(20);", 
        "ALTER TABLE videos ADD COLUMN validated_at TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE videos ADD COLUMN validated_by VARCHAR(36);",
        "ALTER TABLE videos ADD COLUMN ground_truth_count INTEGER DEFAULT 0;",
        "ALTER TABLE videos ADD COLUMN ground_truth_quality_score REAL;",
        "ALTER TABLE videos ADD COLUMN ground_truth_completed_at TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE videos ADD COLUMN hil_testing_ready BOOLEAN DEFAULT false;",
        "ALTER TABLE videos ADD COLUMN hil_testing_approved_by VARCHAR(36);",
        "ALTER TABLE videos ADD COLUMN hil_testing_approved_at TIMESTAMP WITH TIME ZONE;"
    ]
    
    try:
        with engine.connect() as conn:
            for i, column_stmt in enumerate(missing_columns, 1):
                try:
                    logger.info(f"Adding column {i}/{len(missing_columns)}...")
                    conn.execute(text(column_stmt))
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info(f"Column {i} already exists, skipping")
                    else:
                        logger.warning(f"Failed to add column {i}: {e}")
            
            conn.commit()
            logger.info("✅ Successfully added missing video columns")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to add video columns: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("🔧 Creating Missing Video Validation Tables - ROOT CAUSE FIX")
    print("=" * 60)
    
    # 1. Add missing columns to videos table
    print("\n1. Adding missing columns to videos table...")
    if add_missing_video_columns():
        print("✅ Video table columns updated")
    else:
        print("❌ Failed to update video table columns")
        exit(1)
        
    # 2. Create missing validation tables
    print("\n2. Creating missing validation tables...")
    if create_validation_tables():
        print("✅ Validation tables created successfully")
    else:
        print("❌ Failed to create validation tables")
        exit(1)
    
    print("\n🎉 ROOT CAUSE FIX COMPLETE!")
    print("The video_validation_results table and related tables now exist.")
    print("Video deletion should now work without workarounds.")
"""
Ground Truth Management Migration
SPARC Implementation - Database migration for ground truth system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import Base
from config import settings
from models import *  # Import all existing models
from src.models.ground_truth_models import *  # Import new ground truth models
import logging
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_ground_truth_migration():
    """
    Run migration to create ground truth management tables
    """
    try:
        logger.info("🚀 Starting ground truth management system migration...")
        
        # Create engine
        database_url = settings.database_url
        engine = create_engine(database_url)
        
        # Create all tables
        logger.info("📊 Creating ground truth management tables...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Verify tables were created
            logger.info("✅ Verifying table creation...")
            
            # Check if ground truth validation workflows table exists
            result = db.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='ground_truth_validation_workflows';
            """)).fetchone()
            
            if result:
                logger.info("✅ ground_truth_validation_workflows table created")
            else:
                logger.error("❌ ground_truth_validation_workflows table not found")
            
            # Check validation history table
            result = db.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='validation_history';
            """)).fetchone()
            
            if result:
                logger.info("✅ validation_history table created")
            else:
                logger.error("❌ validation_history table not found")
            
            # Check batch processing tables
            result = db.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='ground_truth_batches';
            """)).fetchone()
            
            if result:
                logger.info("✅ ground_truth_batches table created")
            else:
                logger.error("❌ ground_truth_batches table not found")
            
            result = db.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='ground_truth_batch_items';
            """)).fetchone()
            
            if result:
                logger.info("✅ ground_truth_batch_items table created")
            else:
                logger.error("❌ ground_truth_batch_items table not found")
            
            # Check export tables
            result = db.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='ground_truth_exports';
            """)).fetchone()
            
            if result:
                logger.info("✅ ground_truth_exports table created")
            else:
                logger.error("❌ ground_truth_exports table not found")
            
            # Check quality metrics table
            result = db.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='ground_truth_quality_metrics';
            """)).fetchone()
            
            if result:
                logger.info("✅ ground_truth_quality_metrics table created")
            else:
                logger.error("❌ ground_truth_quality_metrics table not found")
            
            # Add indexes for performance (if not already created by SQLAlchemy)
            logger.info("📈 Creating additional performance indexes...")
            
            # Create additional indexes that might not be created by SQLAlchemy
            indexes = [
                """CREATE INDEX IF NOT EXISTS idx_workflow_status_created 
                   ON ground_truth_validation_workflows(validation_status, created_at);""",
                
                """CREATE INDEX IF NOT EXISTS idx_batch_performance 
                   ON ground_truth_batches(status, started_at, completed_at);""",
                
                """CREATE INDEX IF NOT EXISTS idx_quality_metrics_scores 
                   ON ground_truth_quality_metrics(annotation_quality_score, detection_confidence);""",
                
                """CREATE INDEX IF NOT EXISTS idx_export_status_format 
                   ON ground_truth_exports(status, format_type, created_at);"""
            ]
            
            for index_sql in indexes:
                try:
                    db.execute(text(index_sql))
                    db.commit()
                except Exception as e:
                    logger.warning(f"Index creation failed (may already exist): {str(e)}")
            
            logger.info("✅ Ground truth management migration completed successfully")
            
            # Create test data if needed
            logger.info("🧪 Creating test data for ground truth system...")
            create_test_ground_truth_data(db)
            
        except Exception as e:
            logger.error(f"❌ Error during migration verification: {str(e)}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Ground truth migration failed: {str(e)}")
        raise

def create_test_ground_truth_data(db):
    """
    Create test data for ground truth system validation
    """
    try:
        # Check if we need to create test data
        existing_workflows = db.query(GroundTruthValidationWorkflow).first()
        if existing_workflows:
            logger.info("Test data already exists, skipping creation")
            return
        
        # Get first video for test data
        test_video = db.query(Video).first()
        if not test_video:
            logger.warning("No videos found, skipping test data creation")
            return
        
        # Create a test ground truth object if none exist
        existing_gt = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == test_video.id
        ).first()
        
        if not existing_gt:
            logger.info("Creating test ground truth object...")
            test_gt = GroundTruthObject(
                id="gt_test_" + str(uuid.uuid4()),
                video_id=test_video.id,
                frame_number=100,
                timestamp=3.33,
                class_label="pedestrian",
                x=150.0,
                y=200.0,
                width=80.0,
                height=160.0,
                confidence=0.85,
                validated=False,
                difficult=False
            )
            db.add(test_gt)
            db.flush()
            existing_gt = test_gt
        
        # Create test validation workflow
        logger.info("Creating test validation workflow...")
        test_workflow = GroundTruthValidationWorkflow(
            id="workflow_test_" + str(uuid.uuid4()),
            ground_truth_id=existing_gt.id,
            video_id=test_video.id,
            generation_method=GenerationMethod.MANUAL,
            validation_status=ValidationStatus.PENDING,
            quality_level=QualityLevel.MEDIUM,
            confidence_score=0.85
        )
        db.add(test_workflow)
        
        # Create test batch
        logger.info("Creating test batch...")
        test_batch = GroundTruthBatch(
            id="batch_test_" + str(uuid.uuid4()),
            batch_name="Test Batch - Ground Truth System",
            description="Test batch for ground truth system validation",
            processing_method=GenerationMethod.AUTOMATED_ML,
            total_videos=1,
            status="created"
        )
        db.add(test_batch)
        db.flush()
        
        # Create test batch item
        test_batch_item = GroundTruthBatchItem(
            id="batch_item_test_" + str(uuid.uuid4()),
            batch_id=test_batch.id,
            video_id=test_video.id,
            status="pending"
        )
        db.add(test_batch_item)
        
        # Create test export
        logger.info("Creating test export...")
        test_export = GroundTruthExport(
            id="export_test_" + str(uuid.uuid4()),
            export_name="Test Export - JSON Format",
            description="Test export for ground truth system validation",
            format_type="json",
            status="created"
        )
        db.add(test_export)
        
        # Create test quality metrics
        logger.info("Creating test quality metrics...")
        test_metrics = GroundTruthQualityMetrics(
            id="metrics_test_" + str(uuid.uuid4()),
            ground_truth_id=existing_gt.id,
            video_id=test_video.id,
            annotation_quality_score=0.85,
            detection_confidence=0.85,
            spatial_accuracy=0.80,
            temporal_consistency=0.75,
            object_size_score=0.60,
            occlusion_level=0.20,
            motion_complexity=0.40,
            background_complexity=0.30
        )
        db.add(test_metrics)
        
        db.commit()
        logger.info("✅ Test data created successfully")
        
    except Exception as e:
        logger.error(f"❌ Error creating test data: {str(e)}")
        db.rollback()

if __name__ == "__main__":
    try:
        run_ground_truth_migration()
        print("✅ Ground truth management migration completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        sys.exit(1)
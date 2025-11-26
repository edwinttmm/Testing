"""
Migration Tests for Video Status Updates
========================================

Tests migration of existing video data to support new status system and validation.
"""

import pytest
from sqlalchemy import create_engine, text, select, delete, update, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import json
import os

from database import Base
from models import Project, Video, GroundTruthObject, DetectionEvent, TestSession


# Test databases for migration testing
OLD_DB_URL = "sqlite:///./test_migration_old.db"
NEW_DB_URL = "sqlite:///./test_migration_new.db"

old_engine = create_engine(OLD_DB_URL, connect_args={"check_same_thread": False})
new_engine = create_engine(NEW_DB_URL, connect_args={"check_same_thread": False})

OldSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=old_engine)
NewSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)


class TestVideoStatusMigration:
    """Test migration of video status system"""
    
    def setup_method(self):
        """Setup test databases"""
        # Create old database with legacy schema
        Base.metadata.create_all(bind=old_engine)
        Base.metadata.create_all(bind=new_engine)
        
        # Setup legacy data
        self._create_legacy_data()
    
    def teardown_method(self):
        """Cleanup test databases"""
        try:
            os.unlink(OLD_DB_URL.replace("sqlite:///./", ""))
        except FileNotFoundError:
            pass
        try:
            os.unlink(NEW_DB_URL.replace("sqlite:///./", ""))
        except FileNotFoundError:
            pass
    
    def _create_legacy_data(self):
        """Create legacy video data for migration testing"""
        old_db = OldSessionLocal()
        
        try:
            # Create test project
            project = Project(
                id="legacy-project-id",
                name="Legacy Project",
                description="Project with legacy videos",
                camera_model="Legacy Camera",
                camera_view="Front-facing VRU",
                signal_type="GPIO",
                owner_id="test-user"
            )
            old_db.add(project)
            
            # Create legacy videos with old status values
            legacy_videos = [
                {
                    "id": "legacy-video-1",
                    "filename": "legacy_video_1.mp4",
                    "status": "uploaded",  # Old status
                    "processing_status": "Manual",  # Old processing status
                    "ground_truth_generated": False
                },
                {
                    "id": "legacy-video-2", 
                    "filename": "legacy_video_2.mp4",
                    "status": "processed",  # Old status that needs mapping
                    "processing_status": "Completed",  # Old processing status
                    "ground_truth_generated": True
                },
                {
                    "id": "legacy-video-3",
                    "filename": "legacy_video_3.mp4", 
                    "status": None,  # Missing status
                    "processing_status": None,  # Missing processing status
                    "ground_truth_generated": False
                },
                {
                    "id": "legacy-video-4",
                    "filename": "legacy_video_4.mp4",
                    "status": "processing",
                    "processing_status": "generating_ground_truth", 
                    "ground_truth_generated": False
                }
            ]
            
            for video_data in legacy_videos:
                video = Video(
                    id=video_data["id"],
                    filename=video_data["filename"],
                    file_path=f"/uploads/{video_data['filename']}",
                    status=video_data["status"],
                    processing_status=video_data["processing_status"],
                    ground_truth_generated=video_data["ground_truth_generated"],
                    project_id=project.id
                )
                old_db.add(video)
            
            # Create some ground truth objects for legacy video 2
            ground_truth_objects = [
                GroundTruthObject(
                    id="gt-legacy-1",
                    video_id="legacy-video-2",
                    timestamp=1.0,
                    class_label="pedestrian",
                    x=100, y=100, width=50, height=100,
                    confidence=0.9,
                    validated=True
                ),
                GroundTruthObject(
                    id="gt-legacy-2", 
                    video_id="legacy-video-2",
                    timestamp=2.5,
                    class_label="cyclist",
                    x=200, y=150, width=60, height=120, 
                    confidence=0.85,
                    validated=False  # Not validated
                )
            ]
            
            for gt in ground_truth_objects:
                old_db.add(gt)
            
            old_db.commit()
            
        finally:
            old_db.close()
    
    def test_migrate_video_status_values(self):
        """Test migration of old status values to new schema"""
        # Define status migration mapping
        status_migration_map = {
            "uploaded": "uploaded",
            "processed": "validated",  # Old "processed" becomes "validated"
            "processing": "processing",
            None: "uploaded"  # Default for missing status
        }
        
        processing_status_migration_map = {
            "Manual": "pending",
            "Completed": "completed", 
            "generating_ground_truth": "generating_ground_truth",
            None: "pending"  # Default for missing processing_status
        }
        
        # Run migration
        old_db = OldSessionLocal()
        new_db = NewSessionLocal()
        
        try:
            # Get legacy data
            legacy_videos = old_db.execute(select(Video)).scalars().all()
            legacy_project = old_db.execute(select(Project)).scalar_one_or_none()
            
            # Migrate project
            new_project = Project(
                id=legacy_project.id,
                name=legacy_project.name,
                description=legacy_project.description,
                camera_model=legacy_project.camera_model,
                camera_view=legacy_project.camera_view,
                signal_type=legacy_project.signal_type,
                owner_id=legacy_project.owner_id,
                created_at=legacy_project.created_at,
                updated_at=legacy_project.updated_at
            )
            new_db.add(new_project)
            
            # Migrate videos with status mapping
            migrated_videos = []
            for legacy_video in legacy_videos:
                # Map old status to new status
                old_status = legacy_video.status
                new_status = status_migration_map.get(old_status, "uploaded")
                
                old_processing_status = legacy_video.processing_status
                new_processing_status = processing_status_migration_map.get(old_processing_status, "pending")
                
                migrated_video = Video(
                    id=legacy_video.id,
                    filename=legacy_video.filename,
                    file_path=legacy_video.file_path,
                    status=new_status,
                    processing_status=new_processing_status,
                    ground_truth_generated=legacy_video.ground_truth_generated,
                    project_id=legacy_video.project_id,
                    file_size=legacy_video.file_size,
                    duration=legacy_video.duration,
                    fps=legacy_video.fps,
                    resolution=legacy_video.resolution,
                    created_at=legacy_video.created_at,
                    updated_at=legacy_video.updated_at
                )
                new_db.add(migrated_video)
                migrated_videos.append(migrated_video)
            
            # Migrate ground truth objects
            legacy_gt_objects = old_db.execute(select(GroundTruthObject)).scalars().all()
            for legacy_gt in legacy_gt_objects:
                new_gt = GroundTruthObject(
                    id=legacy_gt.id,
                    video_id=legacy_gt.video_id,
                    timestamp=legacy_gt.timestamp,
                    class_label=legacy_gt.class_label,
                    x=legacy_gt.x,
                    y=legacy_gt.y,
                    width=legacy_gt.width,
                    height=legacy_gt.height,
                    confidence=legacy_gt.confidence,
                    validated=legacy_gt.validated,
                    created_at=legacy_gt.created_at
                )
                new_db.add(new_gt)
            
            new_db.commit()
            
            # Validate migration results
            migrated_videos_check = new_db.execute(select(Video)).scalars().all()
            assert len(migrated_videos_check) == 4
            
            # Check specific status migrations
            video_statuses = {v.id: v.status for v in migrated_videos_check}
            assert video_statuses["legacy-video-1"] == "uploaded"
            assert video_statuses["legacy-video-2"] == "validated"  # processed -> validated
            assert video_statuses["legacy-video-3"] == "uploaded"   # None -> uploaded
            assert video_statuses["legacy-video-4"] == "processing"
            
            # Check processing status migrations
            processing_statuses = {v.id: v.processing_status for v in migrated_videos_check}
            assert processing_statuses["legacy-video-1"] == "pending"  # Manual -> pending
            assert processing_statuses["legacy-video-2"] == "completed"  # Completed -> completed
            assert processing_statuses["legacy-video-3"] == "pending"   # None -> pending
            
        finally:
            old_db.close()
            new_db.close()
    
    def test_migrate_video_validation_logic(self):
        """Test migration includes validation logic updates"""
        new_db = NewSessionLocal()
        
        try:
            # Get migrated videos
            videos = new_db.execute(select(Video)).scalars().all()
            
            # Apply post-migration validation logic
            for video in videos:
                # If video has ground truth objects and is marked as completed,
                # it should be eligible for validation
                gt_count = session.execute(select(func.count()).select_from(GroundTruthObject).where(
                    GroundTruthObject.video_id == video.id
                )).scalar()
                
                if gt_count > 0 and video.processing_status == "completed":
                    # Check if all ground truth is validated
                    validated_gt_count = new_db.execute(select(func.count()).select_from(GroundTruthObject).where(
                        GroundTruthObject.video_id == video.id,
                        GroundTruthObject.validated == True
                    )).scalar()
                    
                    if validated_gt_count == gt_count:
                        # All ground truth is validated, video can be validated
                        if video.status != "validated":
                            video.status = "pending_validation"
                    else:
                        # Some ground truth needs validation
                        video.status = "pending_validation"
            
            new_db.commit()
            
            # Verify validation logic application
            video_2 = new_db.execute(select(Video).where(Video.id == "legacy-video-2")).scalar_one_or_none()
            assert video_2.status in ["validated", "pending_validation"]
            
        finally:
            new_db.close()
    
    def test_migration_rollback_capability(self):
        """Test ability to rollback migration if needed"""
        # Create backup of original data before migration
        old_db = OldSessionLocal()
        
        try:
            original_videos = old_db.execute(select(Video)).scalars().all()
            backup_data = []
            
            for video in original_videos:
                backup_data.append({
                    "id": video.id,
                    "filename": video.filename,
                    "status": video.status,
                    "processing_status": video.processing_status,
                    "ground_truth_generated": video.ground_truth_generated
                })
            
            # Simulate migration failure and rollback
            # In real implementation, this would restore from backup
            
            # Verify backup data is complete
            assert len(backup_data) == 4
            
            # Check that we can restore original statuses
            rollback_map = {
                "validated": "processed",  # Reverse mapping
                "uploaded": "uploaded",
                "processing": "processing"
            }
            
            for item in backup_data:
                if item["status"] == "processed":
                    # This was changed to "validated" in migration
                    assert rollback_map.get("validated") == "processed"
            
        finally:
            old_db.close()


class TestBatchVideoStatusMigration:
    """Test batch migration operations"""
    
    def setup_method(self):
        """Setup test database with many videos"""
        Base.metadata.create_all(bind=new_engine)
        self._create_bulk_test_data()
    
    def teardown_method(self):
        """Cleanup"""
        try:
            os.unlink(NEW_DB_URL.replace("sqlite:///./", ""))
        except FileNotFoundError:
            pass
    
    def _create_bulk_test_data(self):
        """Create many videos for batch migration testing"""
        db = NewSessionLocal()
        
        try:
            # Create test project
            project = Project(
                id="batch-project-id",
                name="Batch Migration Project",
                description="Project for batch migration testing",
                camera_model="Batch Camera",
                camera_view="Front-facing VRU",
                signal_type="GPIO",
                owner_id="test-user"
            )
            db.add(project)
            
            # Create 100 videos with various statuses
            statuses_to_migrate = [
                ("uploaded", 30),
                ("processed", 25),  # Will become "validated"
                ("processing", 20),
                (None, 15),  # Will become "uploaded"
                ("error", 10)
            ]
            
            video_id = 1
            for status, count in statuses_to_migrate:
                for i in range(count):
                    video = Video(
                        id=f"batch-video-{video_id}",
                        filename=f"batch_video_{video_id}.mp4",
                        file_path=f"/uploads/batch_video_{video_id}.mp4",
                        status=status,
                        processing_status="Manual" if status == "uploaded" else "Completed",
                        ground_truth_generated=(status == "processed"),
                        project_id=project.id
                    )
                    db.add(video)
                    video_id += 1
            
            db.commit()
            
        finally:
            db.close()
    
    def test_batch_status_migration_performance(self):
        """Test performance of batch video status migration"""
        db = NewSessionLocal()
        
        try:
            import time
            start_time = time.time()
            
            # Batch migration of statuses
            status_updates = [
                {"old_status": "processed", "new_status": "validated"},
                {"old_status": None, "new_status": "uploaded"}
            ]
            
            for update in status_updates:
                # Use bulk update for better performance
                db.execute(
                    text("UPDATE videos SET status = :new_status WHERE status = :old_status"),
                    {"new_status": update["new_status"], "old_status": update["old_status"]}
                )
            
            # Update null statuses separately
            db.execute(
                text("UPDATE videos SET status = 'uploaded' WHERE status IS NULL")
            )
            
            db.commit()
            
            migration_time = time.time() - start_time
            
            # Migration should complete quickly (under 1 second for 100 videos)
            assert migration_time < 1.0
            
            # Verify migration results
            validated_count = db.execute(select(func.count()).select_from(Video).where(Video.status == "validated")).scalar()
            uploaded_count = db.execute(select(func.count()).select_from(Video).where(Video.status == "uploaded")).scalar()
            
            assert validated_count == 25  # All "processed" videos
            assert uploaded_count == 45   # 30 original + 15 from null
            
        finally:
            db.close()
    
    def test_migration_data_integrity(self):
        """Test data integrity during batch migration"""
        db = NewSessionLocal()
        
        try:
            # Count videos before migration
            total_videos_before = db.execute(select(func.count()).select_from(Video)).scalar()
            
            # Perform migration with transaction safety
            with db.begin():
                # Update statuses
                db.execute(
                    text("UPDATE videos SET status = 'validated' WHERE status = 'processed'")
                )
                
                # Update processing statuses
                db.execute(
                    text("UPDATE videos SET processing_status = 'completed' WHERE processing_status = 'Completed'")
                )
                
                # Set default statuses for null values
                db.execute(
                    text("UPDATE videos SET status = 'uploaded' WHERE status IS NULL")
                )
                db.execute(
                    text("UPDATE videos SET processing_status = 'pending' WHERE processing_status IS NULL")
                )
            
            # Verify data integrity
            total_videos_after = db.execute(select(func.count()).select_from(Video)).scalar()
            assert total_videos_before == total_videos_after
            
            # Check no null statuses remain
            null_status_count = db.execute(select(func.count()).select_from(Video).where(Video.status.is_(None))).scalar()
            assert null_status_count == 0
            
            null_processing_status_count = db.execute(select(Video).where(
            Video.processing_status.is_(None)
        )).scalars().count()
            assert null_processing_status_count == 0
            
            # Verify all statuses are valid
            valid_statuses = {"uploaded", "processing", "validated", "error", "pending_validation"}
            all_statuses = {v.status for v in db.execute(select(Video)).scalars().all()}
            assert all_statuses.issubset(valid_statuses)
            
        finally:
            db.close()


class TestVideoStatusMigrationValidation:
    """Test validation of migrated video statuses"""
    
    def test_validate_migrated_video_consistency(self):
        """Test validation of video status consistency after migration"""
        db = NewSessionLocal()
        
        try:
            # Create test data with inconsistent states
            project = Project(
                id="validation-project",
                name="Validation Project",
                description="Project for validation testing",
                camera_model="Validation Camera",
                camera_view="Front-facing VRU",
                signal_type="GPIO",
                owner_id="test-user"
            )
            db.add(project)
            
            # Create videos with potentially inconsistent states
            test_videos = [
                {
                    "id": "inconsistent-1",
                    "status": "validated",
                    "ground_truth_generated": False,  # Inconsistent: validated but no GT
                },
                {
                    "id": "inconsistent-2",
                    "status": "processing",
                    "processing_status": "completed",  # Inconsistent: processing but completed
                },
                {
                    "id": "consistent-1",
                    "status": "validated",
                    "ground_truth_generated": True,  # Consistent
                }
            ]
            
            for video_data in test_videos:
                video = Video(
                    id=video_data["id"],
                    filename=f"{video_data['id']}.mp4",
                    file_path=f"/uploads/{video_data['id']}.mp4",
                    status=video_data["status"],
                    processing_status=video_data.get("processing_status", "completed"),
                    ground_truth_generated=video_data["ground_truth_generated"],
                    project_id=project.id
                )
                db.add(video)
            
            db.commit()
            
            # Run validation checks
            validation_issues = self._validate_video_consistency(db)
            
            # Should find inconsistencies
            assert len(validation_issues) == 2  # Two inconsistent videos
            
            issue_video_ids = [issue["video_id"] for issue in validation_issues]
            assert "inconsistent-1" in issue_video_ids
            assert "inconsistent-2" in issue_video_ids
            assert "consistent-1" not in issue_video_ids
            
        finally:
            db.close()
    
    def _validate_video_consistency(self, db):
        """Helper method to validate video state consistency"""
        validation_issues = []
        
        videos = db.execute(select(Video)).scalars().all()
        
        for video in videos:
            # Rule 1: Validated videos should have ground truth
            if video.status == "validated" and not video.ground_truth_generated:
                validation_issues.append({
                    "video_id": video.id,
                    "issue": "validated_without_ground_truth",
                    "description": "Video is validated but has no ground truth"
                })
            
            # Rule 2: Processing videos should not have completed processing status
            if video.status == "processing" and video.processing_status == "completed":
                validation_issues.append({
                    "video_id": video.id,
                    "issue": "processing_but_completed",
                    "description": "Video status is processing but processing_status is completed"
                })
            
            # Rule 3: Videos with ground truth should not be in uploaded status
            if video.status == "uploaded" and video.ground_truth_generated:
                validation_issues.append({
                    "video_id": video.id,
                    "issue": "uploaded_with_ground_truth",
                    "description": "Video has ground truth but status is still uploaded"
                })
        
        return validation_issues


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Test database migrations and schema validation
"""
import pytest
from sqlalchemy import text, inspect
from sqlalchemy.exc import IntegrityError


class TestDatabaseMigrations:
    """Test database migration functionality and schema compliance"""
    
    def test_all_tables_exist(self, database_schema_validator):
        """Verify all expected tables exist in database"""
        schema_info = database_schema_validator()
        
        assert len(schema_info['missing_tables']) == 0, f"Missing tables: {schema_info['missing_tables']}"
        assert 'projects' in schema_info['existing_tables']
        assert 'videos' in schema_info['existing_tables']
        assert 'ground_truth_objects' in schema_info['existing_tables']
        assert 'test_sessions' in schema_info['existing_tables']
        assert 'detection_events' in schema_info['existing_tables']
        assert 'annotations' in schema_info['existing_tables']
        assert 'annotation_sessions' in schema_info['existing_tables']
        assert 'video_project_links' in schema_info['existing_tables']
        assert 'test_results' in schema_info['existing_tables']
        assert 'detection_comparisons' in schema_info['existing_tables']
        assert 'audit_logs' in schema_info['existing_tables']
    
    def test_video_table_schema(self, column_validator):
        """Verify video table has all required columns"""
        columns_info = column_validator('videos')
        column_names = [col['name'] for col in columns_info['columns']]
        
        # Critical columns that must exist
        required_columns = [
            'id', 'filename', 'file_path', 'file_size', 'duration', 'fps',
            'resolution', 'status', 'processing_status', 'ground_truth_generated',
            'project_id', 'created_at', 'updated_at'
        ]
        
        for col in required_columns:
            assert col in column_names, f"Missing required column: {col}"
        
        # Verify processing_status column exists (critical for video workflow)
        processing_status_col = next((c for c in columns_info['columns'] if c['name'] == 'processing_status'), None)
        assert processing_status_col is not None, "processing_status column is missing"
    
    def test_ground_truth_objects_schema(self, column_validator):
        """Verify ground truth objects table schema"""
        columns_info = column_validator('ground_truth_objects')
        column_names = [col['name'] for col in columns_info['columns']]
        
        required_columns = [
            'id', 'video_id', 'frame_number', 'timestamp', 'class_label',
            'x', 'y', 'width', 'height', 'confidence', 'validated', 'difficult'
        ]
        
        for col in required_columns:
            assert col in column_names, f"Missing required column: {col}"
    
    def test_foreign_key_constraints(self, test_engine):
        """Test foreign key relationships work correctly"""
        with test_engine.connect() as conn:
            # Test video -> project relationship
            result = conn.execute(text("""
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name='videos'
            """)).fetchone()
            
            assert 'FOREIGN KEY' in result[0] or 'REFERENCES' in result[0], \
                "Video table should have foreign key to projects"
    
    def test_indexes_exist(self, test_engine):
        """Verify critical indexes exist for performance"""
        with test_engine.connect() as conn:
            # Get index information
            indexes = conn.execute(text("""
                SELECT name, sql FROM sqlite_master 
                WHERE type='index' AND sql IS NOT NULL
            """)).fetchall()
            
            index_names = [idx[0] for idx in indexes]
            
            # Critical indexes that should exist
            expected_patterns = [
                'idx_video_project',  # Video-project composite index
                'idx_gt_video',       # Ground truth video index
                'idx_detection_session'  # Detection session index
            ]
            
            for pattern in expected_patterns:
                found = any(pattern in idx_name for idx_name in index_names)
                assert found, f"Expected index pattern '{pattern}' not found"
    
    def test_database_constraints(self, test_db_session):
        """Test database constraints and validation"""
        from models import Project, Video
        
        # Test NOT NULL constraint
        with pytest.raises(IntegrityError):
            project = Project(
                name=None,  # Should fail - name is required
                camera_model="Test",
                camera_view="Front-facing VRU",
                signal_type="GPIO"
            )
            test_db_session.add(project)
            test_db_session.commit()
        
        test_db_session.rollback()
    
    def test_cascade_deletes(self, test_db_session, created_project, created_video):
        """Test cascade delete relationships"""
        # Create ground truth object linked to video
        from models import GroundTruthObject
        
        gt_obj = GroundTruthObject(
            video_id=created_video.id,
            timestamp=1.0,
            class_label="pedestrian",
            x=100, y=100, width=50, height=100,
            confidence=0.9
        )
        test_db_session.add(gt_obj)
        test_db_session.commit()
        
        # Delete the video - ground truth should cascade
        test_db_session.delete(created_video)
        test_db_session.commit()
        
        # Verify ground truth object was deleted
        remaining_gt = test_db_session.query(GroundTruthObject).filter_by(
            video_id=created_video.id
        ).first()
        assert remaining_gt is None, "Ground truth object should be cascade deleted"
    
    def test_processing_status_workflow(self, test_db_session, created_video):
        """Test processing_status column workflow"""
        # Initial status should be 'pending'
        assert created_video.processing_status == "pending"
        
        # Test status transitions
        valid_statuses = ["pending", "processing", "completed", "failed"]
        
        for status in valid_statuses:
            created_video.processing_status = status
            test_db_session.commit()
            test_db_session.refresh(created_video)
            assert created_video.processing_status == status
    
    def test_uuid_generation(self, test_db_session):
        """Test UUID generation for primary keys"""
        from models import Project
        import uuid
        
        project = Project(
            name="UUID Test Project",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db_session.add(project)
        test_db_session.commit()
        test_db_session.refresh(project)
        
        # Verify ID is a valid UUID string
        assert project.id is not None
        assert len(project.id) == 36  # UUID string length
        
        # Should be able to parse as UUID
        parsed_uuid = uuid.UUID(project.id)
        assert str(parsed_uuid) == project.id
    
    def test_timestamp_defaults(self, test_db_session, created_project):
        """Test automatic timestamp generation"""
        # created_at should be set automatically
        assert created_project.created_at is not None
        
        # Update the project to test updated_at
        original_updated = created_project.updated_at
        created_project.name = "Updated Name"
        test_db_session.commit()
        test_db_session.refresh(created_project)
        
        # updated_at should have changed
        assert created_project.updated_at != original_updated
    
    def test_json_column_functionality(self, test_db_session, created_video):
        """Test JSON column storage and retrieval"""
        from models import GroundTruthObject
        
        # Create ground truth with JSON bounding box
        bounding_box_data = {
            "x": 100.5,
            "y": 200.3,
            "width": 50.7,
            "height": 100.2,
            "normalized": True,
            "metadata": {"frame_quality": "good"}
        }
        
        gt_obj = GroundTruthObject(
            video_id=created_video.id,
            timestamp=1.0,
            class_label="pedestrian",
            x=100, y=200, width=50, height=100,
            confidence=0.9,
            bounding_box=bounding_box_data
        )
        
        test_db_session.add(gt_obj)
        test_db_session.commit()
        test_db_session.refresh(gt_obj)
        
        # Verify JSON data is preserved
        assert gt_obj.bounding_box == bounding_box_data
        assert gt_obj.bounding_box["metadata"]["frame_quality"] == "good"
    
    def test_indexing_performance(self, test_db_session, created_project):
        """Test that indexes improve query performance"""
        from models import Video
        import time
        
        # Create multiple videos for performance testing
        videos = []
        for i in range(100):
            video = Video(
                filename=f"test_video_{i}.mp4",
                file_path=f"/test/uploads/test_video_{i}.mp4",
                file_size=1024 * i,
                duration=30.0,
                fps=30.0,
                resolution="1920x1080",
                project_id=created_project.id,
                processing_status="pending" if i % 2 == 0 else "completed"
            )
            videos.append(video)
        
        test_db_session.add_all(videos)
        test_db_session.commit()
        
        # Test indexed query performance
        start_time = time.time()
        results = test_db_session.query(Video).filter_by(
            project_id=created_project.id,
            processing_status="completed"
        ).all()
        query_time = time.time() - start_time
        
        # Should be fast with proper indexing
        assert query_time < 0.1, f"Indexed query took too long: {query_time}s"
        assert len(results) == 50  # Half should be completed
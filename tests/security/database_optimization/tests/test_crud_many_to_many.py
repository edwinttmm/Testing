"""
Test suite for many-to-many CRUD operations refactoring

This test suite validates that the refactored CRUD operations work correctly
with the new Project-Video many-to-many relationship structure.
"""
import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

# Import the models and CRUD operations
import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from database import Base
from models import Project, Video, VideoProjectLink
import crud
from schemas import ProjectCreate

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_many_to_many.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_user():
    """Sample user ID for testing"""
    return "test-user-123"


@pytest.fixture
def sample_project(db_session, sample_user):
    """Create a sample project for testing"""
    project_data = ProjectCreate(
        name="Test Project",
        description="Test project for many-to-many relationship testing",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO"
    )
    return crud.create_project(db_session, project_data, sample_user)


class TestManyToManyVideoOperations:
    """Test video operations with many-to-many relationships"""
    
    def test_create_video_without_project(self, db_session):
        """Test creating a video without direct project assignment"""
        video = crud.create_video(db_session, "test_video.mp4", "/uploads/test_video.mp4", 1024000)
        
        assert video.filename == "test_video.mp4"
        assert video.file_path == "/uploads/test_video.mp4"
        assert video.file_size == 1024000
        assert video.project_id is None  # No direct project relationship
    
    def test_create_video_with_projects(self, db_session, sample_project, sample_user):
        """Test creating a video and assigning to multiple projects"""
        # Create a second project
        project2_data = ProjectCreate(
            name="Second Project",
            description="Second test project",
            camera_model="Test Camera 2",
            camera_view="Rear-facing VRU",
            signal_type="Network Packet"
        )
        project2 = crud.create_project(db_session, project2_data, sample_user)
        
        # Create video with multiple project assignments
        video = crud.create_video(
            db_session,
            "multi_project_video.mp4",
            "/uploads/multi_project_video.mp4",
            2048000,
            project_ids=[sample_project.id, project2.id]
        )
        
        assert video.filename == "multi_project_video.mp4"
        
        # Check video is assigned to both projects
        video_projects = crud.get_video_projects(db_session, video.id, sample_user)
        assert len(video_projects) == 2
        project_names = {p.name for p in video_projects}
        assert "Test Project" in project_names
        assert "Second Project" in project_names
    
    def test_assign_video_to_project(self, db_session, sample_project, sample_user):
        """Test assigning an existing video to a project"""
        video = crud.create_video(db_session, "standalone_video.mp4")
        
        # Assign video to project
        link = crud.assign_video_to_project(db_session, video.id, sample_project.id, "manual_assignment")
        
        assert link.video_id == video.id
        assert link.project_id == sample_project.id
        assert link.assignment_reason == "manual_assignment"
        
        # Verify assignment works
        project_videos = crud.get_project_videos(db_session, sample_project.id, sample_user)
        assert len(project_videos) == 1
        assert project_videos[0].id == video.id
    
    def test_remove_video_from_project(self, db_session, sample_project, sample_user):
        """Test removing a video from a project"""
        video = crud.create_video(db_session, "removable_video.mp4", project_ids=[sample_project.id])
        
        # Verify video is assigned
        project_videos = crud.get_project_videos(db_session, sample_project.id, sample_user)
        assert len(project_videos) == 1
        
        # Remove video from project
        success = crud.remove_video_from_project(db_session, video.id, sample_project.id, sample_user)
        assert success is True
        
        # Verify video is no longer assigned
        project_videos = crud.get_project_videos(db_session, sample_project.id, sample_user)
        assert len(project_videos) == 0
    
    def test_get_videos_with_project_filter(self, db_session, sample_project, sample_user):
        """Test getting videos filtered by project"""
        # Create videos and assign to projects
        video1 = crud.create_video(db_session, "video1.mp4", project_ids=[sample_project.id])
        video2 = crud.create_video(db_session, "video2.mp4", project_ids=[sample_project.id])
        video3 = crud.create_video(db_session, "video3.mp4")  # Not assigned to any project
        
        # Get videos for the project
        project_videos = crud.get_videos(db_session, sample_project.id, sample_user)
        assert len(project_videos) == 2
        
        video_names = {v.filename for v in project_videos}
        assert "video1.mp4" in video_names
        assert "video2.mp4" in video_names
        assert "video3.mp4" not in video_names
    
    def test_get_all_user_videos(self, db_session, sample_project, sample_user):
        """Test getting all videos accessible to a user across all projects"""
        # Create another project
        project2_data = ProjectCreate(
            name="Another Project",
            description="Another test project",
            camera_model="Another Camera",
            camera_view="In-Cab Driver Behavior",
            signal_type="Serial"
        )
        project2 = crud.create_project(db_session, project2_data, sample_user)
        
        # Create videos in different projects
        video1 = crud.create_video(db_session, "video1.mp4", project_ids=[sample_project.id])
        video2 = crud.create_video(db_session, "video2.mp4", project_ids=[project2.id])
        video3 = crud.create_video(db_session, "video3.mp4", project_ids=[sample_project.id, project2.id])
        
        # Get all videos for user (no project filter)
        all_videos = crud.get_videos(db_session, None, sample_user)
        
        # Should get 3 unique videos (video3 should not be duplicated)
        assert len(all_videos) == 3
        video_names = {v.filename for v in all_videos}
        assert "video1.mp4" in video_names
        assert "video2.mp4" in video_names
        assert "video3.mp4" in video_names


class TestManyToManyProjectOperations:
    """Test project operations with many-to-many relationships"""
    
    def test_get_project_with_videos(self, db_session, sample_project, sample_user):
        """Test getting a project with associated videos loaded"""
        # Create and assign videos
        video1 = crud.create_video(db_session, "project_video1.mp4", project_ids=[sample_project.id])
        video2 = crud.create_video(db_session, "project_video2.mp4", project_ids=[sample_project.id])
        
        # Load project with videos
        loaded_project = crud.get_project(db_session, sample_project.id, sample_user, load_videos=True)
        
        assert loaded_project is not None
        assert loaded_project.name == "Test Project"
        
        # Check video links are loaded
        assert hasattr(loaded_project, 'video_links')
        # Note: The actual video access would depend on how the relationships are configured
    
    def test_delete_project_with_shared_videos(self, db_session, sample_user):
        """Test deleting a project when videos are shared with other projects"""
        # Create two projects
        project1_data = ProjectCreate(
            name="Project 1",
            description="First project",
            camera_model="Camera 1",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        project1 = crud.create_project(db_session, project1_data, sample_user)
        
        project2_data = ProjectCreate(
            name="Project 2",
            description="Second project",
            camera_model="Camera 2",
            camera_view="Rear-facing VRU",
            signal_type="Network Packet"
        )
        project2 = crud.create_project(db_session, project2_data, sample_user)
        
        # Create videos: one exclusive to project1, one shared
        exclusive_video = crud.create_video(db_session, "exclusive.mp4", project_ids=[project1.id])
        shared_video = crud.create_video(db_session, "shared.mp4", project_ids=[project1.id, project2.id])
        
        # Mock file system operations
        with patch('os.path.exists', return_value=False), \
             patch('os.remove') as mock_remove:
            
            # Delete project1
            success = crud.delete_project(db_session, project1.id, sample_user)
            assert success is True
            
            # Verify project1 is deleted
            deleted_project = crud.get_project(db_session, project1.id, sample_user)
            assert deleted_project is None
            
            # Verify exclusive video is deleted (not in other projects)
            deleted_video = db_session.query(Video).filter(Video.id == exclusive_video.id).first()
            assert deleted_video is None
            
            # Verify shared video still exists (it's in project2)
            existing_video = db_session.query(Video).filter(Video.id == shared_video.id).first()
            assert existing_video is not None
            
            # Verify shared video is still accessible in project2
            project2_videos = crud.get_project_videos(db_session, project2.id, sample_user)
            assert len(project2_videos) == 1
            assert project2_videos[0].id == shared_video.id


class TestBulkOperations:
    """Test bulk operations for many-to-many relationships"""
    
    def test_bulk_assign_videos(self, db_session, sample_project, sample_user):
        """Test bulk assignment of videos to a project"""
        # Create multiple videos
        video1 = crud.create_video(db_session, "bulk1.mp4")
        video2 = crud.create_video(db_session, "bulk2.mp4")
        video3 = crud.create_video(db_session, "bulk3.mp4")
        
        video_ids = [video1.id, video2.id, video3.id]
        
        # Bulk assign to project
        links = crud.bulk_assign_videos_to_project(db_session, sample_project.id, video_ids, sample_user)
        
        assert len(links) == 3
        for link in links:
            assert link.project_id == sample_project.id
            assert link.video_id in video_ids
            assert link.assignment_reason == "bulk_assignment"
        
        # Verify all videos are accessible in the project
        project_videos = crud.get_project_videos(db_session, sample_project.id, sample_user)
        assert len(project_videos) == 3
    
    def test_bulk_remove_videos(self, db_session, sample_project, sample_user):
        """Test bulk removal of videos from a project"""
        # Create and assign videos
        video_ids = []
        for i in range(3):
            video = crud.create_video(db_session, f"remove{i}.mp4", project_ids=[sample_project.id])
            video_ids.append(video.id)
        
        # Verify videos are assigned
        project_videos = crud.get_project_videos(db_session, sample_project.id, sample_user)
        assert len(project_videos) == 3
        
        # Bulk remove
        removed_count = crud.bulk_remove_videos_from_project(db_session, sample_project.id, video_ids, sample_user)
        assert removed_count == 3
        
        # Verify videos are no longer in the project
        project_videos = crud.get_project_videos(db_session, sample_project.id, sample_user)
        assert len(project_videos) == 0


class TestSecurityAndIntegrity:
    """Test security and data integrity with many-to-many relationships"""
    
    def test_user_isolation(self, db_session):
        """Test that users can only access their own videos and projects"""
        user1 = "user1"
        user2 = "user2"
        
        # Create projects for different users
        project1_data = ProjectCreate(
            name="User1 Project",
            description="Project for user 1",
            camera_model="Camera 1",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        project1 = crud.create_project(db_session, project1_data, user1)
        
        project2_data = ProjectCreate(
            name="User2 Project",
            description="Project for user 2",
            camera_model="Camera 2",
            camera_view="Rear-facing VRU",
            signal_type="Network Packet"
        )
        project2 = crud.create_project(db_session, project2_data, user2)
        
        # Create videos for each user's project
        video1 = crud.create_video(db_session, "user1_video.mp4", project_ids=[project1.id])
        video2 = crud.create_video(db_session, "user2_video.mp4", project_ids=[project2.id])
        
        # Test that user1 cannot access user2's videos and vice versa
        user1_videos = crud.get_videos(db_session, None, user1)
        user2_videos = crud.get_videos(db_session, None, user2)
        
        assert len(user1_videos) == 1
        assert len(user2_videos) == 1
        assert user1_videos[0].filename == "user1_video.mp4"
        assert user2_videos[0].filename == "user2_video.mp4"
        
        # Test that user1 cannot access user2's specific video
        user1_access_to_user2_video = crud.get_video(db_session, video2.id, user1)
        assert user1_access_to_user2_video is None
        
        # Test that user2 cannot access user1's specific video
        user2_access_to_user1_video = crud.get_video(db_session, video1.id, user2)
        assert user2_access_to_user1_video is None
    
    def test_dashboard_stats_accuracy(self, db_session, sample_user):
        """Test dashboard statistics with many-to-many relationships"""
        # Create projects and videos with shared relationships
        project1_data = ProjectCreate(
            name="Stats Project 1",
            description="First stats project",
            camera_model="Camera 1",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        project1 = crud.create_project(db_session, project1_data, sample_user)
        
        project2_data = ProjectCreate(
            name="Stats Project 2",
            description="Second stats project",
            camera_model="Camera 2",
            camera_view="Rear-facing VRU",
            signal_type="Network Packet"
        )
        project2 = crud.create_project(db_session, project2_data, sample_user)
        
        # Create videos: some exclusive, some shared
        video1 = crud.create_video(db_session, "exclusive1.mp4", project_ids=[project1.id])
        video2 = crud.create_video(db_session, "exclusive2.mp4", project_ids=[project2.id])
        video3 = crud.create_video(db_session, "shared.mp4", project_ids=[project1.id, project2.id])
        
        # Get dashboard stats
        stats = crud.get_dashboard_stats(db_session, sample_user)
        
        assert stats["project_count"] == 2  # 2 projects
        assert stats["video_count"] == 3   # 3 unique videos (shared video counted once)


class TestUtilityFunctions:
    """Test utility functions for many-to-many management"""
    
    def test_validate_relationships(self, db_session, sample_project, sample_user):
        """Test relationship validation function"""
        # Create some test data
        video = crud.create_video(db_session, "validation_test.mp4", project_ids=[sample_project.id])
        
        # Run validation
        issues = crud.validate_project_video_relationships(db_session, sample_user)
        
        assert isinstance(issues, dict)
        assert "orphaned_videos" in issues
        assert "invalid_links" in issues
        assert "legacy_relationships" in issues
        assert "duplicate_links" in issues
        
        # Should have no issues with clean data
        assert issues["orphaned_videos"] == 0
        assert issues["invalid_links"] == 0
        assert issues["duplicate_links"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
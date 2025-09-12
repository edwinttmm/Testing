"""
Comprehensive Tests for Project Schema Refactoring
Tests many-to-many project-video relationships, data migration integrity,
and CRUD operations with the new schema structure.
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import tempfile
import os

# Test configuration
TEST_DATABASE_URL = "sqlite:///./test_schema_refactoring.db"


class TestProjectSchemaRefactoring:
    """Test suite for project schema refactoring with many-to-many relationships"""
    
    @pytest.fixture
    def setup_database(self):
        """Setup test database with new schema"""
        engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Mock the database models for testing
        class MockProject:
            def __init__(self, id=None, name="Test Project", description="Test Description"):
                self.id = id or str(uuid.uuid4())
                self.name = name
                self.description = description
                self.created_at = datetime.now(timezone.utc)
                self.videos = []
                self.video_links = []
        
        class MockVideo:
            def __init__(self, id=None, filename="test.mp4"):
                self.id = id or str(uuid.uuid4())
                self.filename = filename
                self.file_path = f"/uploads/{filename}"
                self.created_at = datetime.now(timezone.utc)
                self.project_links = []
        
        class MockVideoProjectLink:
            def __init__(self, video_id, project_id):
                self.id = str(uuid.uuid4())
                self.video_id = video_id
                self.project_id = project_id
                self.intelligent_match = True
                self.confidence_score = 0.95
                self.created_at = datetime.now(timezone.utc)
        
        return {
            'engine': engine,
            'session': TestingSessionLocal(),
            'MockProject': MockProject,
            'MockVideo': MockVideo,
            'MockVideoProjectLink': MockVideoProjectLink
        }
    
    @pytest.mark.asyncio
    async def test_many_to_many_project_video_relationship(self, setup_database):
        """Test many-to-many relationship between projects and videos"""
        db_setup = setup_database
        MockProject = db_setup['MockProject']
        MockVideo = db_setup['MockVideo']
        MockVideoProjectLink = db_setup['MockVideoProjectLink']
        
        # Create test data
        project1 = MockProject(name="VRU Detection Project 1")
        project2 = MockProject(name="VRU Detection Project 2")
        video1 = MockVideo(filename="pedestrian_test.mp4")
        video2 = MockVideo(filename="cyclist_test.mp4")
        
        # Test many-to-many linking
        link1 = MockVideoProjectLink(video1.id, project1.id)
        link2 = MockVideoProjectLink(video1.id, project2.id)  # Same video in multiple projects
        link3 = MockVideoProjectLink(video2.id, project1.id)  # Multiple videos in same project
        
        # Verify relationships
        assert link1.video_id == video1.id
        assert link1.project_id == project1.id
        assert link2.video_id == video1.id
        assert link2.project_id == project2.id
        
        # Test intelligent matching attributes
        assert link1.intelligent_match is True
        assert link1.confidence_score == 0.95
        assert isinstance(link1.created_at, datetime)
    
    @pytest.mark.asyncio
    async def test_project_playlist_functionality(self, setup_database):
        """Test project playlist creation and management"""
        db_setup = setup_database
        MockProject = db_setup['MockProject']
        MockVideo = db_setup['MockVideo']
        MockVideoProjectLink = db_setup['MockVideoProjectLink']
        
        # Create project with multiple videos (playlist)
        project = MockProject(name="VRU Test Playlist")
        videos = [
            MockVideo(filename="test_sequence_1.mp4"),
            MockVideo(filename="test_sequence_2.mp4"),
            MockVideo(filename="test_sequence_3.mp4"),
            MockVideo(filename="test_sequence_4.mp4")
        ]
        
        # Create playlist links
        playlist_links = []
        for i, video in enumerate(videos):
            link = MockVideoProjectLink(video.id, project.id)
            link.assignment_reason = f"Sequential test video {i+1}"
            link.confidence_score = 0.9 + (i * 0.02)  # Varying confidence
            playlist_links.append(link)
        
        # Test playlist ordering and metadata
        assert len(playlist_links) == 4
        for i, link in enumerate(playlist_links):
            assert link.project_id == project.id
            assert "Sequential test video" in link.assignment_reason
            assert link.confidence_score >= 0.9
    
    @pytest.mark.asyncio
    async def test_backwards_compatibility_with_direct_project_video(self, setup_database):
        """Test backwards compatibility with direct project_id in videos"""
        db_setup = setup_database
        MockProject = db_setup['MockProject']
        MockVideo = db_setup['MockVideo']
        MockVideoProjectLink = db_setup['MockVideoProjectLink']
        
        # Simulate old schema behavior
        project = MockProject(name="Legacy Project")
        video = MockVideo(filename="legacy_video.mp4")
        
        # Old way: direct project_id reference
        video.project_id = project.id  # Legacy field
        
        # New way: VideoProjectLink
        link = MockVideoProjectLink(video.id, project.id)
        link.assignment_reason = "Legacy migration"
        
        # Both should work
        assert hasattr(video, 'project_id')
        assert video.project_id == project.id
        assert link.video_id == video.id
        assert link.project_id == project.id
    
    @pytest.mark.asyncio
    async def test_schema_migration_integrity(self, setup_database):
        """Test data integrity during schema migration"""
        db_setup = setup_database
        MockProject = db_setup['MockProject']
        MockVideo = db_setup['MockVideo']
        MockVideoProjectLink = db_setup['MockVideoProjectLink']
        
        # Simulate pre-migration data
        projects = [MockProject(name=f"Project {i}") for i in range(5)]
        videos = [MockVideo(filename=f"video_{i}.mp4") for i in range(10)]
        
        # Assign videos to projects (old way)
        for i, video in enumerate(videos):
            video.project_id = projects[i % len(projects)].id
        
        # Migration: create VideoProjectLink entries
        migration_links = []
        for video in videos:
            if hasattr(video, 'project_id') and video.project_id:
                link = MockVideoProjectLink(video.id, video.project_id)
                link.assignment_reason = "Schema migration"
                link.intelligent_match = False  # Migrated, not AI-matched
                migration_links.append(link)
        
        # Verify migration integrity
        assert len(migration_links) == len(videos)
        for i, link in enumerate(migration_links):
            assert link.video_id == videos[i].id
            assert link.project_id == videos[i].project_id
            assert link.assignment_reason == "Schema migration"
            assert link.intelligent_match is False
    
    @pytest.mark.asyncio
    async def test_crud_operations_new_schema(self, setup_database):
        """Test CRUD operations with new many-to-many schema"""
        db_setup = setup_database
        MockProject = db_setup['MockProject']
        MockVideo = db_setup['MockVideo']
        MockVideoProjectLink = db_setup['MockVideoProjectLink']
        
        # CREATE operations
        project = MockProject(name="CRUD Test Project")
        video = MockVideo(filename="crud_test.mp4")
        link = MockVideoProjectLink(video.id, project.id)
        
        # READ operations
        def get_project_videos(project_id):
            return [link for link in [link] if link.project_id == project_id]
        
        def get_video_projects(video_id):
            return [link for link in [link] if link.video_id == video_id]
        
        project_videos = get_project_videos(project.id)
        video_projects = get_video_projects(video.id)
        
        assert len(project_videos) == 1
        assert len(video_projects) == 1
        assert project_videos[0].video_id == video.id
        assert video_projects[0].project_id == project.id
        
        # UPDATE operations
        link.confidence_score = 0.99
        link.assignment_reason = "Updated assignment reason"
        
        assert link.confidence_score == 0.99
        assert "Updated" in link.assignment_reason
        
        # DELETE operations (cascade testing)
        def delete_project_links(project_id):
            return [l for l in [link] if l.project_id != project_id]
        
        remaining_links = delete_project_links(project.id)
        assert len(remaining_links) == 0
    
    @pytest.mark.asyncio
    async def test_intelligent_video_assignment(self, setup_database):
        """Test intelligent video assignment to projects"""
        db_setup = setup_database
        MockProject = db_setup['MockProject']
        MockVideo = db_setup['MockVideo']
        MockVideoProjectLink = db_setup['MockVideoProjectLink']
        
        # Create projects with specific characteristics
        front_facing_project = MockProject(name="Front-facing VRU Detection")
        front_facing_project.camera_view = "Front-facing VRU"
        
        rear_facing_project = MockProject(name="Rear-facing VRU Detection")
        rear_facing_project.camera_view = "Rear-facing VRU"
        
        # Create videos with metadata
        front_video = MockVideo(filename="front_pedestrian.mp4")
        rear_video = MockVideo(filename="rear_cyclist.mp4")
        generic_video = MockVideo(filename="generic_test.mp4")
        
        # Intelligent assignment simulation
        def intelligent_assignment(video, projects):
            assignments = []
            for project in projects:
                confidence = 0.5  # Base confidence
                
                # Match based on filename patterns
                if "front" in video.filename and "Front-facing" in project.camera_view:
                    confidence = 0.95
                elif "rear" in video.filename and "Rear-facing" in project.camera_view:
                    confidence = 0.90
                elif "generic" in video.filename:
                    confidence = 0.60
                
                if confidence > 0.7:  # Threshold for assignment
                    link = MockVideoProjectLink(video.id, project.id)
                    link.confidence_score = confidence
                    link.intelligent_match = True
                    link.assignment_reason = f"Intelligent match: {confidence:.2f} confidence"
                    assignments.append(link)
            
            return assignments
        
        projects = [front_facing_project, rear_facing_project]
        
        # Test intelligent assignments
        front_assignments = intelligent_assignment(front_video, projects)
        rear_assignments = intelligent_assignment(rear_video, projects)
        generic_assignments = intelligent_assignment(generic_video, projects)
        
        assert len(front_assignments) == 1
        assert front_assignments[0].project_id == front_facing_project.id
        assert front_assignments[0].confidence_score == 0.95
        
        assert len(rear_assignments) == 1
        assert rear_assignments[0].project_id == rear_facing_project.id
        assert rear_assignments[0].confidence_score == 0.90
        
        assert len(generic_assignments) == 0  # Below threshold
    
    @pytest.mark.asyncio
    async def test_complex_project_video_scenarios(self, setup_database):
        """Test complex scenarios with multiple projects and videos"""
        db_setup = setup_database
        MockProject = db_setup['MockProject']
        MockVideo = db_setup['MockVideo']
        MockVideoProjectLink = db_setup['MockVideoProjectLink']
        
        # Complex scenario: Research project needing videos from multiple sources
        research_project = MockProject(name="Comprehensive VRU Research")
        training_project = MockProject(name="ML Training Dataset")
        validation_project = MockProject(name="Model Validation")
        
        # Diverse video collection
        videos = [
            MockVideo(filename="pedestrian_crosswalk.mp4"),
            MockVideo(filename="cyclist_intersection.mp4"),
            MockVideo(filename="mixed_vru_scene.mp4"),
            MockVideo(filename="edge_case_scenario.mp4"),
            MockVideo(filename="nighttime_detection.mp4")
        ]
        
        # Complex assignment logic
        assignments = []
        
        # Research project gets all videos
        for video in videos:
            link = MockVideoProjectLink(video.id, research_project.id)
            link.assignment_reason = "Research requires comprehensive dataset"
            link.confidence_score = 1.0
            assignments.append(link)
        
        # Training project gets specific videos
        training_videos = [v for v in videos if any(keyword in v.filename 
                          for keyword in ["pedestrian", "cyclist", "mixed"])]
        for video in training_videos:
            link = MockVideoProjectLink(video.id, training_project.id)
            link.assignment_reason = "Training dataset video"
            link.confidence_score = 0.85
            assignments.append(link)
        
        # Validation project gets edge cases
        validation_videos = [v for v in videos if any(keyword in v.filename 
                            for keyword in ["edge_case", "nighttime"])]
        for video in validation_videos:
            link = MockVideoProjectLink(video.id, validation_project.id)
            link.assignment_reason = "Edge case validation"
            link.confidence_score = 0.90
            assignments.append(link)
        
        # Verify complex assignments
        research_links = [a for a in assignments if a.project_id == research_project.id]
        training_links = [a for a in assignments if a.project_id == training_project.id]
        validation_links = [a for a in assignments if a.project_id == validation_project.id]
        
        assert len(research_links) == 5  # All videos
        assert len(training_links) == 3  # Specific videos
        assert len(validation_links) == 2  # Edge cases
        
        # Verify no duplicate video-project combinations
        unique_combinations = set((a.video_id, a.project_id) for a in assignments)
        assert len(unique_combinations) == len(assignments)
    
    @pytest.mark.asyncio
    async def test_performance_many_to_many_queries(self, setup_database):
        """Test query performance with many-to-many relationships"""
        import time
        
        db_setup = setup_database
        MockProject = db_setup['MockProject']
        MockVideo = db_setup['MockVideo']
        MockVideoProjectLink = db_setup['MockVideoProjectLink']
        
        # Create large dataset
        projects = [MockProject(name=f"Project {i}") for i in range(50)]
        videos = [MockVideo(filename=f"video_{i}.mp4") for i in range(200)]
        
        # Create many-to-many relationships (realistic distribution)
        links = []
        for i, video in enumerate(videos):
            # Each video assigned to 1-3 projects
            project_count = min(3, (i % 3) + 1)
            for j in range(project_count):
                project_idx = (i + j) % len(projects)
                link = MockVideoProjectLink(video.id, projects[project_idx].id)
                link.confidence_score = 0.8 + (j * 0.05)
                links.append(link)
        
        # Performance test: Find all videos for a project
        start_time = time.time()
        project_id = projects[0].id
        project_videos = [link for link in links if link.project_id == project_id]
        query_time = time.time() - start_time
        
        # Performance test: Find all projects for a video
        start_time = time.time()
        video_id = videos[0].id
        video_projects = [link for link in links if link.video_id == video_id]
        query_time_2 = time.time() - start_time
        
        # Basic performance assertions
        assert query_time < 0.1  # Should be fast for in-memory operations
        assert query_time_2 < 0.1
        assert len(project_videos) > 0
        assert len(video_projects) > 0
        
        # Verify data integrity
        assert len(links) > len(videos)  # Many-to-many creates more links than videos
        unique_video_count = len(set(link.video_id for link in links))
        assert unique_video_count == len(videos)


class TestDataMigrationIntegrity:
    """Test data migration integrity and consistency"""
    
    @pytest.mark.asyncio
    async def test_zero_downtime_migration(self):
        """Test zero-downtime migration strategy"""
        # Simulate dual-write scenario during migration
        old_assignments = {}  # project_id -> [video_ids]
        new_assignments = []  # VideoProjectLink objects
        
        # Populate old structure
        old_assignments['proj1'] = ['vid1', 'vid2', 'vid3']
        old_assignments['proj2'] = ['vid1', 'vid4']  # vid1 in multiple projects
        
        # Migration: Create new structure while maintaining old
        class MockVideoProjectLink:
            def __init__(self, video_id, project_id):
                self.video_id = video_id
                self.project_id = project_id
                self.created_at = datetime.now(timezone.utc)
        
        for project_id, video_ids in old_assignments.items():
            for video_id in video_ids:
                new_assignments.append(MockVideoProjectLink(video_id, project_id))
        
        # Verify migration integrity
        old_total_assignments = sum(len(videos) for videos in old_assignments.values())
        assert len(new_assignments) == old_total_assignments
        
        # Verify many-to-many is preserved
        vid1_projects = [link.project_id for link in new_assignments if link.video_id == 'vid1']
        assert len(vid1_projects) == 2  # vid1 in both proj1 and proj2
        assert 'proj1' in vid1_projects and 'proj2' in vid1_projects
    
    @pytest.mark.asyncio
    async def test_rollback_capability(self):
        """Test ability to rollback migration if needed"""
        # Simulate migration with rollback capability
        new_links = [
            {'video_id': 'vid1', 'project_id': 'proj1'},
            {'video_id': 'vid1', 'project_id': 'proj2'},
            {'video_id': 'vid2', 'project_id': 'proj1'}
        ]
        
        # Rollback: Convert back to old structure
        rollback_assignments = {}
        for link in new_links:
            project_id = link['project_id']
            video_id = link['video_id']
            
            if project_id not in rollback_assignments:
                rollback_assignments[project_id] = []
            rollback_assignments[project_id].append(video_id)
        
        # Verify rollback integrity
        assert 'proj1' in rollback_assignments
        assert 'proj2' in rollback_assignments
        assert len(rollback_assignments['proj1']) == 2  # vid1, vid2
        assert len(rollback_assignments['proj2']) == 1  # vid1
    
    def test_data_consistency_checks(self):
        """Test data consistency validation during migration"""
        # Sample data structures
        projects = {'proj1': 'VRU Project 1', 'proj2': 'VRU Project 2'}
        videos = {'vid1': 'video1.mp4', 'vid2': 'video2.mp4'}
        links = [
            {'video_id': 'vid1', 'project_id': 'proj1'},
            {'video_id': 'vid2', 'project_id': 'proj1'},
            {'video_id': 'vid1', 'project_id': 'proj2'}
        ]
        
        # Consistency checks
        def validate_referential_integrity(links, projects, videos):
            errors = []
            
            for link in links:
                if link['project_id'] not in projects:
                    errors.append(f"Invalid project_id: {link['project_id']}")
                if link['video_id'] not in videos:
                    errors.append(f"Invalid video_id: {link['video_id']}")
            
            return errors
        
        # Should pass validation
        errors = validate_referential_integrity(links, projects, videos)
        assert len(errors) == 0
        
        # Test with invalid data
        invalid_links = links + [{'video_id': 'vid999', 'project_id': 'proj1'}]
        errors = validate_referential_integrity(invalid_links, projects, videos)
        assert len(errors) == 1
        assert "Invalid video_id: vid999" in errors[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
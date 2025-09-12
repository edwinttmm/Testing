"""
Comprehensive Security Authorization Tests

Tests the multi-tenant authorization system to ensure proper data isolation
and prevent unauthorized access to user resources.

Test Categories:
1. Project access authorization
2. Video access authorization  
3. Test session access authorization
4. Detection event access authorization
5. Cross-user access prevention
6. Audit logging verification

Author: Security Engineering Team
Created: 2025-01-09
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch
import uuid
from datetime import datetime

from main import app
from database import get_db, SessionLocal
from models import AuthUser, Project, Video, TestSession, DetectionEvent, AuditLog
from security.authorization import authorization_service, AuthorizationError
from auth_dependencies import get_current_user

# Test client setup
client = TestClient(app)

# Test database session
@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Test users
@pytest.fixture
def test_user_1():
    return AuthUser(
        id=str(uuid.uuid4()),
        email="user1@test.com",
        username="testuser1", 
        full_name="Test User 1",
        hashed_password="hashed_password_1",
        is_active=True,
        is_verified=True
    )

@pytest.fixture
def test_user_2():
    return AuthUser(
        id=str(uuid.uuid4()),
        email="user2@test.com", 
        username="testuser2",
        full_name="Test User 2",
        hashed_password="hashed_password_2",
        is_active=True,
        is_verified=True
    )

# Test data fixtures
@pytest.fixture
def user1_project(test_user_1):
    return Project(
        id=str(uuid.uuid4()),
        name="User 1 Project",
        description="Test project for user 1",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO",
        owner_id=test_user_1.id
    )

@pytest.fixture  
def user2_project(test_user_2):
    return Project(
        id=str(uuid.uuid4()),
        name="User 2 Project", 
        description="Test project for user 2",
        camera_model="Test Camera",
        camera_view="Front-facing VRU", 
        signal_type="GPIO",
        owner_id=test_user_2.id
    )

class TestProjectAuthorization:
    """Test project access authorization"""
    
    def test_user_can_access_own_project(self, db_session, test_user_1, user1_project):
        """Test that users can access their own projects"""
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(user1_project)
        db_session.commit()
        
        # Test authorization
        result = authorization_service.validate_project_access(
            db_session, user1_project.id, test_user_1.id
        )
        
        assert result == True
    
    def test_user_cannot_access_other_user_project(self, db_session, test_user_1, test_user_2, user2_project):
        """Test that users cannot access projects owned by other users"""
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(test_user_2)
        db_session.add(user2_project)
        db_session.commit()
        
        # Test authorization - user 1 trying to access user 2's project
        with pytest.raises(AuthorizationError):
            authorization_service.validate_project_access(
                db_session, user2_project.id, test_user_1.id
            )
    
    def test_get_user_projects_returns_only_owned_projects(self, db_session, test_user_1, test_user_2, user1_project, user2_project):
        """Test that get_user_projects only returns projects owned by the user"""
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(test_user_2)
        db_session.add(user1_project)
        db_session.add(user2_project)
        db_session.commit()
        
        # Get projects for user 1
        user1_projects = authorization_service.get_user_projects(db_session, test_user_1.id)
        
        # Should only return user 1's project
        assert len(user1_projects) == 1
        assert user1_projects[0].id == user1_project.id
        assert user1_projects[0].owner_id == test_user_1.id
    
    def test_nonexistent_project_access_denied(self, db_session, test_user_1):
        """Test that access to nonexistent projects is denied"""
        # Add test user to database
        db_session.add(test_user_1)
        db_session.commit()
        
        # Test authorization for nonexistent project
        fake_project_id = str(uuid.uuid4())
        with pytest.raises(AuthorizationError):
            authorization_service.validate_project_access(
                db_session, fake_project_id, test_user_1.id
            )

class TestVideoAuthorization:
    """Test video access authorization"""
    
    def test_user_can_access_video_in_own_project(self, db_session, test_user_1, user1_project):
        """Test that users can access videos in their own projects"""
        # Create test video
        test_video = Video(
            id=str(uuid.uuid4()),
            filename="test_video.mp4",
            file_path="/test/path",
            project_id=user1_project.id
        )
        
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(user1_project)
        db_session.add(test_video)
        db_session.commit()
        
        # Test authorization
        result = authorization_service.validate_video_access(
            db_session, test_video.id, test_user_1.id
        )
        
        assert result == True
    
    def test_user_cannot_access_video_in_other_user_project(self, db_session, test_user_1, test_user_2, user2_project):
        """Test that users cannot access videos in projects owned by other users"""
        # Create test video in user 2's project
        test_video = Video(
            id=str(uuid.uuid4()),
            filename="test_video.mp4", 
            file_path="/test/path",
            project_id=user2_project.id
        )
        
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(test_user_2)
        db_session.add(user2_project)
        db_session.add(test_video)
        db_session.commit()
        
        # Test authorization - user 1 trying to access video in user 2's project
        with pytest.raises(AuthorizationError):
            authorization_service.validate_video_access(
                db_session, test_video.id, test_user_1.id
            )

class TestTestSessionAuthorization:
    """Test test session access authorization"""
    
    def test_user_can_access_session_in_own_project(self, db_session, test_user_1, user1_project):
        """Test that users can access test sessions in their own projects"""
        # Create test video and session
        test_video = Video(
            id=str(uuid.uuid4()),
            filename="test_video.mp4",
            file_path="/test/path", 
            project_id=user1_project.id
        )
        
        test_session = TestSession(
            id=str(uuid.uuid4()),
            name="Test Session",
            project_id=user1_project.id,
            video_id=test_video.id
        )
        
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(user1_project)
        db_session.add(test_video)
        db_session.add(test_session)
        db_session.commit()
        
        # Test authorization
        result = authorization_service.validate_session_access(
            db_session, test_session.id, test_user_1.id
        )
        
        assert result == True
    
    def test_user_cannot_access_session_in_other_user_project(self, db_session, test_user_1, test_user_2, user2_project):
        """Test that users cannot access test sessions in projects owned by other users"""
        # Create test video and session in user 2's project
        test_video = Video(
            id=str(uuid.uuid4()),
            filename="test_video.mp4",
            file_path="/test/path",
            project_id=user2_project.id
        )
        
        test_session = TestSession(
            id=str(uuid.uuid4()),
            name="Test Session",
            project_id=user2_project.id,
            video_id=test_video.id
        )
        
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(test_user_2)
        db_session.add(user2_project)
        db_session.add(test_video)
        db_session.add(test_session)
        db_session.commit()
        
        # Test authorization - user 1 trying to access session in user 2's project
        with pytest.raises(AuthorizationError):
            authorization_service.validate_session_access(
                db_session, test_session.id, test_user_1.id
            )

class TestAuditLogging:
    """Test audit logging for authorization events"""
    
    def test_successful_access_logged(self, db_session, test_user_1, user1_project):
        """Test that successful access attempts are logged"""
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(user1_project)
        db_session.commit()
        
        # Clear existing audit logs
        db_session.query(AuditLog).delete()
        db_session.commit()
        
        # Test authorization (should succeed and log)
        authorization_service.validate_project_access(
            db_session, user1_project.id, test_user_1.id
        )
        
        # Check audit log was created
        audit_logs = db_session.query(AuditLog).filter(
            AuditLog.user_id == test_user_1.id,
            AuditLog.event_type == "resource_access_granted"
        ).all()
        
        assert len(audit_logs) == 1
        assert audit_logs[0].event_data["resource_type"] == "project"
        assert audit_logs[0].event_data["resource_id"] == user1_project.id
        assert audit_logs[0].event_data["result"] == "granted"
    
    def test_failed_access_logged(self, db_session, test_user_1, test_user_2, user2_project):
        """Test that failed access attempts are logged"""
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(test_user_2)
        db_session.add(user2_project)
        db_session.commit()
        
        # Clear existing audit logs
        db_session.query(AuditLog).delete()
        db_session.commit()
        
        # Test authorization (should fail and log)
        with pytest.raises(AuthorizationError):
            authorization_service.validate_project_access(
                db_session, user2_project.id, test_user_1.id
            )
        
        # Check audit log was created
        audit_logs = db_session.query(AuditLog).filter(
            AuditLog.user_id == test_user_1.id,
            AuditLog.event_type == "resource_access_denied"
        ).all()
        
        assert len(audit_logs) == 1
        assert audit_logs[0].event_data["resource_type"] == "project"
        assert audit_logs[0].event_data["resource_id"] == user2_project.id
        assert audit_logs[0].event_data["result"] == "denied"

class TestAPIEndpointSecurity:
    """Test API endpoint security integration"""
    
    def test_secure_projects_endpoint_authentication_required(self):
        """Test that secure project endpoints require authentication"""
        response = client.get("/api/secure/projects")
        assert response.status_code == 401
    
    def test_secure_videos_endpoint_authentication_required(self):
        """Test that secure video endpoints require authentication"""
        response = client.get("/api/secure/videos")
        assert response.status_code == 401
    
    def test_secure_sessions_endpoint_authentication_required(self):
        """Test that secure test session endpoints require authentication"""
        response = client.get("/api/secure/test-sessions")
        assert response.status_code == 401
    
    @patch('auth_dependencies.get_current_user')
    def test_secure_projects_endpoint_returns_user_projects_only(self, mock_get_current_user, db_session, test_user_1, user1_project):
        """Test that secure project endpoint returns only user's projects"""
        # Mock authentication
        mock_get_current_user.return_value = test_user_1
        
        # Add test data to database
        db_session.add(test_user_1)
        db_session.add(user1_project)
        db_session.commit()
        
        # Override database dependency
        app.dependency_overrides[get_db] = lambda: db_session
        
        try:
            response = client.get("/api/secure/projects", headers={"Authorization": "Bearer fake-token"})
            
            assert response.status_code == 200
            projects = response.json()
            
            # Should only return user's project
            assert len(projects) == 1
            assert projects[0]["id"] == user1_project.id
            assert projects[0]["owner_id"] == test_user_1.id
            
        finally:
            app.dependency_overrides = {}

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
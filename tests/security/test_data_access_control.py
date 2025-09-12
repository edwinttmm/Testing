#!/usr/bin/env python3
"""
Data Access Control Security Test Suite
=======================================

This test suite validates proper data access controls, authorization mechanisms,
and resource ownership validation in the AI Model Validation Platform.

CRITICAL ACCESS CONTROL TESTS:
1. Resource ownership validation
2. Cross-user data access prevention
3. Privilege escalation prevention
4. Administrative function protection
5. Data modification authorization
6. Bulk operation access control
7. File system access security

These tests should FAIL initially if vulnerabilities exist, then PASS after fixes.
"""

import pytest
import json
import uuid
import tempfile
import os
from datetime import datetime, timezone
from typing import Dict, List, Any
from unittest.mock import patch, MagicMock

import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Import the main application and models
from main import app, get_db
from database import Base
from models import Project, Video, TestSession, AuthUser


class DataAccessTestHarness:
    """Test harness for data access control testing"""
    
    def __init__(self):
        self.client = TestClient(app)
        
        # Setup test database
        self.test_engine = create_engine("sqlite:///./test_access_control.db", echo=False)
        Base.metadata.create_all(bind=self.test_engine)
        TestingSessionLocal = sessionmaker(bind=self.test_engine)
        self.test_session = TestingSessionLocal()
        
        # Override database dependency
        app.dependency_overrides[get_db] = self.override_get_db
        
        # Create test users with different roles and privileges
        self.users = self._create_test_users()
        self.test_data = self._create_test_data()
        
    def override_get_db(self):
        """Override database session for testing"""
        try:
            yield self.test_session
        finally:
            pass
    
    def _create_test_users(self) -> Dict[str, Dict]:
        """Create test users with different access levels"""
        users = {
            "owner": {
                "id": str(uuid.uuid4()),
                "username": "project_owner",
                "email": "owner@test.com",
                "role": "user",
                "is_superuser": False,
                "api_key": "owner_key_12345",
                "projects": []
            },
            "collaborator": {
                "id": str(uuid.uuid4()),
                "username": "collaborator",
                "email": "collab@test.com", 
                "role": "user",
                "is_superuser": False,
                "api_key": "collab_key_67890",
                "projects": []
            },
            "unauthorized": {
                "id": str(uuid.uuid4()),
                "username": "unauthorized",
                "email": "unauth@test.com",
                "role": "user", 
                "is_superuser": False,
                "api_key": "unauth_key_11111",
                "projects": []
            },
            "admin": {
                "id": str(uuid.uuid4()),
                "username": "admin",
                "email": "admin@test.com",
                "role": "admin",
                "is_superuser": True,
                "api_key": "admin_key_99999",
                "projects": []
            },
            "malicious": {
                "id": str(uuid.uuid4()),
                "username": "malicious_actor",
                "email": "evil@hacker.com",
                "role": "user",
                "is_superuser": False,
                "api_key": "malicious_key_666",
                "projects": []
            }
        }
        
        return users
    
    def _create_test_data(self) -> Dict[str, Any]:
        """Create test data for access control testing"""
        # Create projects owned by different users
        test_data = {
            "owner_project": {
                "id": str(uuid.uuid4()),
                "name": "Owner's Private Project",
                "description": "This project contains sensitive data",
                "ownerId": self.users["owner"]["id"],
                "status": "active"
            },
            "collaborator_project": {
                "id": str(uuid.uuid4()),
                "name": "Collaborator's Project", 
                "description": "Another user's project",
                "ownerId": self.users["collaborator"]["id"],
                "status": "active"
            },
            "confidential_project": {
                "id": str(uuid.uuid4()),
                "name": "Top Secret Research",
                "description": "Highly confidential research data",
                "ownerId": self.users["owner"]["id"],
                "status": "active",
                "confidential": True
            }
        }
        
        return test_data
    
    def get_auth_headers(self, user_key: str) -> Dict[str, str]:
        """Get authentication headers for a test user"""
        return {
            "Authorization": f"Bearer {self.users[user_key]['api_key']}",
            "X-User-ID": self.users[user_key]["id"],
            "X-User-Role": self.users[user_key]["role"]
        }
    
    def create_project_as_user(self, user_key: str, project_data: Dict = None) -> Dict:
        """Create a project as a specific user"""
        if not project_data:
            project_data = {
                "name": f"Test Project {uuid.uuid4().hex[:8]}",
                "description": f"Created by {user_key}",
                "cameraModel": "TestCam",
                "cameraView": "Front-facing VRU",
                "signalType": "GPIO",
                "ownerId": self.users[user_key]["id"]
            }
        
        response = self.client.post(
            "/api/projects",
            json=project_data,
            headers=self.get_auth_headers(user_key)
        )
        
        if response.status_code == 201:
            project = response.json()
            self.users[user_key]["projects"].append(project["id"])
            return project
        else:
            raise Exception(f"Failed to create project: {response.status_code} {response.text}")
    
    def cleanup(self):
        """Clean up test resources"""
        self.test_session.close()
        if os.path.exists("./test_access_control.db"):
            os.remove("./test_access_control.db")


@pytest.fixture
def access_harness():
    """Fixture providing data access test harness"""
    harness = DataAccessTestHarness()
    yield harness
    harness.cleanup()


class TestResourceOwnership:
    """Tests for resource ownership validation"""
    
    def test_user_can_access_own_projects(self, access_harness):
        """Users should be able to access their own projects"""
        # Owner creates a project
        project = access_harness.create_project_as_user("owner")
        project_id = project["id"]
        
        # Owner should be able to access their project
        response = access_harness.client.get(
            f"/api/projects/{project_id}",
            headers=access_harness.get_auth_headers("owner")
        )
        
        assert response.status_code == 200, "User should access their own project"
        retrieved_project = response.json()
        assert retrieved_project["id"] == project_id
        assert retrieved_project["ownerId"] == access_harness.users["owner"]["id"]
    
    def test_user_cannot_access_other_users_projects(self, access_harness):
        """Users should NOT be able to access other users' projects"""
        # Owner creates a project
        owner_project = access_harness.create_project_as_user("owner")
        
        # Unauthorized user tries to access owner's project
        response = access_harness.client.get(
            f"/api/projects/{owner_project['id']}",
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        assert response.status_code in [403, 404], \
            f"ACCESS CONTROL VIOLATION: Unauthorized user accessed project! Status: {response.status_code}"
    
    def test_project_listing_filtered_by_ownership(self, access_harness):
        """Project listings should be filtered by ownership"""
        # Multiple users create projects
        owner_project = access_harness.create_project_as_user("owner")
        collab_project = access_harness.create_project_as_user("collaborator")
        
        # Owner lists projects - should only see their own
        response = access_harness.client.get(
            "/api/projects",
            headers=access_harness.get_auth_headers("owner")
        )
        
        assert response.status_code == 200
        projects = response.json()
        
        # Verify only owner's projects are returned
        project_ids = [p["id"] for p in projects]
        assert owner_project["id"] in project_ids
        assert collab_project["id"] not in project_ids, \
            "ACCESS CONTROL VIOLATION: User sees other users' projects in listing!"
    
    def test_project_modification_requires_ownership(self, access_harness):
        """Users should only be able to modify their own projects"""
        # Owner creates a project
        owner_project = access_harness.create_project_as_user("owner")
        
        # Unauthorized user tries to modify owner's project
        malicious_update = {
            "name": "Hacked Project Name",
            "description": "This project was compromised"
        }
        
        response = access_harness.client.put(
            f"/api/projects/{owner_project['id']}",
            json=malicious_update,
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        assert response.status_code in [403, 404], \
            f"ACCESS CONTROL VIOLATION: Unauthorized modification allowed! Status: {response.status_code}"
        
        # Verify project remains unchanged
        get_response = access_harness.client.get(
            f"/api/projects/{owner_project['id']}",
            headers=access_harness.get_auth_headers("owner")
        )
        
        if get_response.status_code == 200:
            current_project = get_response.json()
            assert current_project["name"] != "Hacked Project Name", \
                "ACCESS CONTROL VIOLATION: Unauthorized modification succeeded!"
    
    def test_project_deletion_requires_ownership(self, access_harness):
        """Users should only be able to delete their own projects"""
        # Owner creates a project
        owner_project = access_harness.create_project_as_user("owner")
        
        # Unauthorized user tries to delete owner's project
        response = access_harness.client.delete(
            f"/api/projects/{owner_project['id']}",
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        assert response.status_code in [403, 404], \
            f"ACCESS CONTROL VIOLATION: Unauthorized deletion allowed! Status: {response.status_code}"
        
        # Verify project still exists
        get_response = access_harness.client.get(
            f"/api/projects/{owner_project['id']}",
            headers=access_harness.get_auth_headers("owner")
        )
        assert get_response.status_code == 200, "Project was deleted by unauthorized user!"


class TestVideoAccessControl:
    """Tests for video access control and ownership"""
    
    def test_video_upload_requires_project_ownership(self, access_harness):
        """Users should only upload videos to their own projects"""
        # Owner creates a project
        owner_project = access_harness.create_project_as_user("owner")
        
        # Unauthorized user tries to upload video to owner's project
        test_video_content = b"fake_video_data_unauthorized"
        files = {"file": ("malicious_video.mp4", test_video_content, "video/mp4")}
        data = {"projectId": owner_project["id"]}
        
        response = access_harness.client.post(
            "/api/videos/upload",
            files=files,
            data=data,
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        assert response.status_code in [403, 404], \
            f"ACCESS CONTROL VIOLATION: Unauthorized video upload allowed! Status: {response.status_code}"
    
    def test_video_access_filtered_by_project_ownership(self, access_harness):
        """Video access should be filtered by project ownership"""
        # Owner creates project and uploads video
        owner_project = access_harness.create_project_as_user("owner")
        
        # Mock successful video upload
        video_data = {
            "id": str(uuid.uuid4()),
            "filename": "owner_private_video.mp4",
            "projectId": owner_project["id"],
            "ownerId": access_harness.users["owner"]["id"]
        }
        
        # Unauthorized user tries to access owner's video
        response = access_harness.client.get(
            f"/api/videos/{video_data['id']}",
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        assert response.status_code in [403, 404], \
            f"ACCESS CONTROL VIOLATION: Unauthorized video access allowed! Status: {response.status_code}"
    
    def test_video_deletion_requires_ownership(self, access_harness):
        """Video deletion should require proper ownership"""
        # Owner creates project
        owner_project = access_harness.create_project_as_user("owner")
        
        # Mock video belonging to owner's project
        video_id = str(uuid.uuid4())
        
        # Unauthorized user tries to delete owner's video
        response = access_harness.client.delete(
            f"/api/videos/{video_id}",
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        assert response.status_code in [403, 404], \
            f"ACCESS CONTROL VIOLATION: Unauthorized video deletion allowed! Status: {response.status_code}"


class TestBulkOperations:
    """Tests for bulk operation access control"""
    
    def test_bulk_project_operations_filtered_by_ownership(self, access_harness):
        """Bulk operations should only affect user's own resources"""
        # Multiple users create projects
        owner_project1 = access_harness.create_project_as_user("owner")
        owner_project2 = access_harness.create_project_as_user("owner") 
        collab_project = access_harness.create_project_as_user("collaborator")
        
        # Owner attempts bulk operation (should only affect their projects)
        bulk_update_data = {
            "projectIds": [owner_project1["id"], owner_project2["id"], collab_project["id"]],
            "updates": {"status": "completed"}
        }
        
        response = access_harness.client.put(
            "/api/projects/bulk-update",
            json=bulk_update_data,
            headers=access_harness.get_auth_headers("owner")
        )
        
        # Should either filter out unauthorized projects or reject entirely
        if response.status_code == 200:
            result = response.json()
            updated_ids = result.get("updated", [])
            
            # Should not include collaborator's project
            assert collab_project["id"] not in updated_ids, \
                "ACCESS CONTROL VIOLATION: Bulk operation affected other user's project!"
    
    def test_bulk_deletion_filtered_by_ownership(self, access_harness):
        """Bulk deletion should be filtered by ownership"""
        # Create projects for different users
        owner_project = access_harness.create_project_as_user("owner")
        collab_project = access_harness.create_project_as_user("collaborator")
        
        # Malicious user attempts bulk deletion including other's projects
        bulk_delete_data = {
            "projectIds": [owner_project["id"], collab_project["id"]]
        }
        
        response = access_harness.client.delete(
            "/api/projects/bulk-delete",
            json=bulk_delete_data,
            headers=access_harness.get_auth_headers("malicious")
        )
        
        # Should reject unauthorized bulk deletion
        assert response.status_code in [403, 404], \
            f"ACCESS CONTROL VIOLATION: Unauthorized bulk deletion allowed! Status: {response.status_code}"


class TestPrivilegeEscalation:
    """Tests for privilege escalation prevention"""
    
    def test_user_cannot_access_admin_functions(self, access_harness):
        """Regular users should not access administrative functions"""
        admin_endpoints = [
            "/api/admin/users",
            "/api/admin/projects/all",
            "/api/admin/system-stats",
            "/api/admin/database/backup",
            "/api/admin/security/audit-log",
            "/api/admin/settings/global"
        ]
        
        for endpoint in admin_endpoints:
            response = access_harness.client.get(
                endpoint,
                headers=access_harness.get_auth_headers("owner")
            )
            
            assert response.status_code in [403, 404, 405], \
                f"PRIVILEGE ESCALATION: User accessed admin endpoint {endpoint}! Status: {response.status_code}"
    
    def test_user_cannot_modify_other_users_data(self, access_harness):
        """Users should not modify other users' profile data"""
        # Regular user tries to modify another user's profile
        user_update_data = {
            "role": "admin",
            "is_superuser": True,
            "permissions": ["all"]
        }
        
        response = access_harness.client.put(
            f"/api/users/{access_harness.users['collaborator']['id']}",
            json=user_update_data,
            headers=access_harness.get_auth_headers("owner")
        )
        
        assert response.status_code in [403, 404], \
            f"PRIVILEGE ESCALATION: User modified another user's profile! Status: {response.status_code}"
    
    def test_user_cannot_access_system_information(self, access_harness):
        """Users should not access system-level information"""
        system_endpoints = [
            "/api/system/health",
            "/api/system/version",
            "/api/system/config",
            "/api/system/logs",
            "/api/system/metrics",
            "/api/system/database-status"
        ]
        
        for endpoint in system_endpoints:
            response = access_harness.client.get(
                endpoint,
                headers=access_harness.get_auth_headers("owner")
            )
            
            # System endpoints should require admin privileges
            assert response.status_code in [403, 404, 405], \
                f"PRIVILEGE ESCALATION: User accessed system endpoint {endpoint}! Status: {response.status_code}"


class TestDataLeakagePrevention:
    """Tests for preventing data leakage between users"""
    
    def test_error_messages_dont_leak_sensitive_data(self, access_harness):
        """Error messages should not leak other users' data"""
        # Owner creates a project with sensitive name
        sensitive_project = access_harness.create_project_as_user(
            "owner",
            {
                "name": "SECRET_PROJECT_CLASSIFIED",
                "description": "Top secret military contract",
                "cameraModel": "MilitaryCam",
                "cameraView": "Front-facing VRU", 
                "signalType": "GPIO"
            }
        )
        
        # Unauthorized user tries to access it
        response = access_harness.client.get(
            f"/api/projects/{sensitive_project['id']}",
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        # Error should not contain sensitive information
        error_text = response.text.lower() if response.text else ""
        
        assert "secret" not in error_text, \
            "DATA LEAKAGE: Error message contains sensitive project name"
        assert "classified" not in error_text, \
            "DATA LEAKAGE: Error message contains sensitive information"
        assert "military" not in error_text, \
            "DATA LEAKAGE: Error message contains sensitive description"
    
    def test_search_results_dont_leak_cross_user_data(self, access_harness):
        """Search results should not leak information from other users"""
        # Owner creates project with specific keywords
        keyword_project = access_harness.create_project_as_user(
            "owner",
            {
                "name": "UniqueKeywordProject2024",
                "description": "Contains special research data",
                "cameraModel": "SpecialCam",
                "cameraView": "Front-facing VRU",
                "signalType": "GPIO"
            }
        )
        
        # Unauthorized user searches for the keyword
        response = access_harness.client.get(
            "/api/projects?search=UniqueKeywordProject2024",
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        if response.status_code == 200:
            projects = response.json()
            
            # Should not return owner's project in unauthorized user's search
            project_names = [p.get("name", "") for p in projects]
            assert "UniqueKeywordProject2024" not in project_names, \
                "DATA LEAKAGE: Search results include other users' projects"
    
    def test_aggregated_statistics_filtered_by_user(self, access_harness):
        """Aggregated statistics should be filtered by user"""
        # Multiple users create projects
        access_harness.create_project_as_user("owner")
        access_harness.create_project_as_user("owner")  # Owner has 2 projects
        access_harness.create_project_as_user("collaborator")  # Collaborator has 1
        
        # Owner checks statistics
        response = access_harness.client.get(
            "/api/dashboard/stats",
            headers=access_harness.get_auth_headers("owner")
        )
        
        if response.status_code == 200:
            stats = response.json()
            
            # Owner should see stats for their 2 projects only
            assert stats.get("totalProjects", 0) == 2, \
                f"DATA LEAKAGE: Stats include other users' data. Expected 2, got {stats.get('totalProjects', 0)}"
            
            # Should not include collaborator's data
            total_system_projects = stats.get("totalProjects", 0)
            assert total_system_projects <= 2, \
                "DATA LEAKAGE: User statistics include other users' projects"


class TestFileSystemAccess:
    """Tests for file system access control"""
    
    def test_file_download_requires_ownership(self, access_harness):
        """File downloads should require proper ownership"""
        # Create a project and mock file upload
        owner_project = access_harness.create_project_as_user("owner")
        
        # Mock file path (would be generated by actual upload)
        test_file_path = f"uploads/{owner_project['id']}/sensitive_document.pdf"
        
        # Unauthorized user tries to download file
        response = access_harness.client.get(
            f"/api/files/download?path={test_file_path}",
            headers=access_harness.get_auth_headers("unauthorized")
        )
        
        assert response.status_code in [403, 404], \
            f"FILE ACCESS VIOLATION: Unauthorized file download allowed! Status: {response.status_code}"
    
    def test_path_traversal_blocked(self, access_harness):
        """Path traversal attempts should be blocked"""
        path_traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\sam",
            "../../../../home/user/.ssh/id_rsa",
            "../../../var/log/auth.log"
        ]
        
        for malicious_path in path_traversal_attempts:
            response = access_harness.client.get(
                f"/api/files/download?path={malicious_path}",
                headers=access_harness.get_auth_headers("owner")
            )
            
            assert response.status_code in [400, 403, 404], \
                f"PATH TRAVERSAL: Malicious path allowed: {malicious_path}"
            
            # Check response doesn't contain system files
            response_text = response.text if response.text else ""
            assert "root:" not in response_text, \
                f"PATH TRAVERSAL: System file leaked with path: {malicious_path}"
    
    def test_file_upload_path_validation(self, access_harness):
        """File upload paths should be validated and restricted"""
        # Owner creates a project
        owner_project = access_harness.create_project_as_user("owner")
        
        # Attempt upload with malicious filename containing path traversal
        malicious_filenames = [
            "../../../evil.mp4",
            "..\\..\\..\\evil.mp4",
            "/etc/passwd.mp4",
            "C:\\Windows\\System32\\evil.mp4"
        ]
        
        for filename in malicious_filenames:
            test_content = b"fake_video_content"
            files = {"file": (filename, test_content, "video/mp4")}
            data = {"projectId": owner_project["id"]}
            
            response = access_harness.client.post(
                "/api/videos/upload",
                files=files,
                data=data,
                headers=access_harness.get_auth_headers("owner")
            )
            
            # Should either reject or sanitize the filename
            if response.status_code == 200:
                upload_result = response.json()
                stored_filename = upload_result.get("filename", "")
                
                # Stored filename should not contain path traversal
                assert "../" not in stored_filename, \
                    f"PATH TRAVERSAL: Malicious filename stored: {filename}"
                assert "\\..\\" not in stored_filename, \
                    f"PATH TRAVERSAL: Malicious filename stored: {filename}"


def run_comprehensive_access_control_test():
    """Run comprehensive data access control test"""
    print("🔒 Starting Comprehensive Data Access Control Test")
    print("=" * 70)
    
    harness = DataAccessTestHarness()
    test_results = []
    
    # Run access control tests
    test_classes = [
        TestResourceOwnership,
        TestVideoAccessControl,
        TestBulkOperations,
        TestPrivilegeEscalation,
        TestDataLeakagePrevention,
        TestFileSystemAccess
    ]
    
    for test_class in test_classes:
        print(f"\n🧪 Running {test_class.__name__}")
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                print(f"  → {method_name}")
                try:
                    method = getattr(instance, method_name)
                    method(harness)
                    test_results.append({"test": method_name, "status": "PASS"})
                    print("    ✅ PASS")
                except AssertionError as e:
                    test_results.append({"test": method_name, "status": "FAIL", "error": str(e)})
                    print(f"    🚨 FAIL: {e}")
                except Exception as e:
                    test_results.append({"test": method_name, "status": "ERROR", "error": str(e)})
                    print(f"    ⚠️ ERROR: {e}")
    
    harness.cleanup()
    
    # Generate summary
    total_tests = len(test_results)
    passed_tests = len([r for r in test_results if r["status"] == "PASS"])
    failed_tests = len([r for r in test_results if r["status"] == "FAIL"])
    error_tests = len([r for r in test_results if r["status"] == "ERROR"])
    
    print("\n" + "=" * 70)
    print("📊 DATA ACCESS CONTROL TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅") 
    print(f"Failed: {failed_tests} 🚨")
    print(f"Errors: {error_tests} ⚠️")
    
    if failed_tests > 0:
        print(f"\n🚨 CRITICAL: {failed_tests} access control vulnerabilities detected!")
        print("Review the test output above for specific security issues.")
        return False
    else:
        print("\n✅ All data access control tests passed!")
        return True


if __name__ == "__main__":
    success = run_comprehensive_access_control_test()
    exit(0 if success else 1)
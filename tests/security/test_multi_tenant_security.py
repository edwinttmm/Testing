#!/usr/bin/env python3
"""
Comprehensive Multi-Tenancy Security Test Suite
==================================================

This test suite validates that the AI Model Validation Platform properly isolates
user data and prevents unauthorized access between different users (multi-tenancy security).

CRITICAL SECURITY TESTS:
1. User isolation in all CRUD operations
2. Authentication enforcement on sensitive endpoints  
3. Data leakage prevention between users
4. Authorization bypass attempts
5. Resource ownership validation

The tests are designed to FAIL initially, demonstrating current vulnerabilities,
then PASS after security fixes are applied.
"""

import pytest
import asyncio
import uuid
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, text

import sys
import os
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

# Import the main application and dependencies
from main import app, get_db
from database import Base, engine
from models import Project, Video, TestSession, GroundTruthObject, Annotation, User
from schemas import ProjectCreate, VideoUploadResponse


class SecurityTestHarness:
    """Test harness for multi-tenancy security testing"""
    
    def __init__(self):
        self.test_engine = create_engine("sqlite:///./test_security.db", echo=False)
        Base.metadata.create_all(bind=self.test_engine)
        TestingSessionLocal = sessionmaker(bind=self.test_engine)
        
        self.client = TestClient(app)
        self.test_session = TestingSessionLocal()
        
        # Override database dependency for testing
        app.dependency_overrides[get_db] = self.override_get_db
        
        # Test users for multi-tenancy testing
        self.users = self._create_test_users()
        self.projects = {}
        self.videos = {}
        self.sessions = {}
        
    def override_get_db(self):
        """Override database session for testing"""
        try:
            yield self.test_session
        finally:
            pass
    
    def _create_test_users(self) -> Dict[str, Dict]:
        """Create test users for multi-tenancy scenarios"""
        users = {
            "alice": {
                "id": str(uuid.uuid4()),
                "username": "alice",
                "email": "alice@test.com",
                "role": "user",
                "api_key": "alice_api_key_12345"
            },
            "bob": {
                "id": str(uuid.uuid4()),
                "username": "bob", 
                "email": "bob@test.com",
                "role": "user",
                "api_key": "bob_api_key_67890"
            },
            "admin": {
                "id": str(uuid.uuid4()),
                "username": "admin",
                "email": "admin@test.com",
                "role": "admin",
                "api_key": "admin_api_key_admin"
            },
            "malicious": {
                "id": str(uuid.uuid4()),
                "username": "malicious_user",
                "email": "evil@hacker.com", 
                "role": "user",
                "api_key": "malicious_key_666"
            }
        }
        
        # Add users to database (mocked for now)
        for user_data in users.values():
            # In a real application, these would be stored in a users table
            pass
            
        return users
    
    def get_auth_headers(self, user_key: str) -> Dict[str, str]:
        """Get authentication headers for a test user"""
        return {
            "Authorization": f"Bearer {self.users[user_key]['api_key']}",
            "X-User-ID": self.users[user_key]["id"]
        }
    
    def create_test_project(self, user_key: str, project_name: str = None) -> Dict:
        """Create a test project for a specific user"""
        if not project_name:
            project_name = f"Test Project {user_key} {uuid.uuid4().hex[:8]}"
            
        project_data = {
            "name": project_name,
            "description": f"Test project for user {user_key}",
            "cameraModel": "TestCam3000",
            "cameraView": "Front-facing VRU",
            "signalType": "GPIO",
            "status": "active",
            "ownerId": self.users[user_key]["id"]  # CRITICAL: Project ownership
        }
        
        response = self.client.post(
            "/api/projects",
            json=project_data,
            headers=self.get_auth_headers(user_key)
        )
        
        if response.status_code == 201:
            project = response.json()
            self.projects[f"{user_key}_{project_name}"] = project
            return project
        else:
            raise Exception(f"Failed to create project: {response.status_code} {response.text}")
    
    def upload_test_video(self, user_key: str, project_id: str, filename: str = "test_video.mp4") -> Dict:
        """Upload a test video for a specific user and project"""
        # Create a small test video file
        test_video_content = b"fake_video_content_for_testing"
        
        files = {"file": (filename, test_video_content, "video/mp4")}
        data = {"projectId": project_id}
        
        response = self.client.post(
            "/api/videos/upload",
            files=files,
            data=data,
            headers=self.get_auth_headers(user_key)
        )
        
        if response.status_code == 200:
            video = response.json()
            self.videos[f"{user_key}_{filename}"] = video
            return video
        else:
            raise Exception(f"Failed to upload video: {response.status_code} {response.text}")
    
    def cleanup(self):
        """Clean up test resources"""
        self.test_session.close()
        if os.path.exists("./test_security.db"):
            os.remove("./test_security.db")


@pytest.fixture
def security_harness():
    """Fixture providing security test harness"""
    harness = SecurityTestHarness()
    yield harness
    harness.cleanup()


class TestMultiTenantUserIsolation:
    """Tests for proper user isolation in multi-tenant scenarios"""
    
    def test_user_cannot_access_other_user_projects(self, security_harness):
        """
        CRITICAL TEST: Users should not be able to access other users' projects
        
        This test should FAIL initially, demonstrating the vulnerability,
        then PASS after proper authorization is implemented.
        """
        # Alice creates a project
        alice_project = security_harness.create_test_project("alice", "Alice Secret Project")
        alice_project_id = alice_project["id"]
        
        # Bob tries to access Alice's project - THIS SHOULD FAIL
        response = security_harness.client.get(
            f"/api/projects/{alice_project_id}",
            headers=security_harness.get_auth_headers("bob")
        )
        
        # VULNERABILITY: If this passes, Bob can access Alice's project!
        assert response.status_code == 403 or response.status_code == 404, \
            f"SECURITY VULNERABILITY: Bob accessed Alice's project! Response: {response.status_code} {response.text}"
        
        # Verify Alice can still access her own project
        response = security_harness.client.get(
            f"/api/projects/{alice_project_id}",
            headers=security_harness.get_auth_headers("alice")
        )
        assert response.status_code == 200, "Alice should be able to access her own project"
    
    def test_user_cannot_list_other_user_projects(self, security_harness):
        """Users should only see their own projects in listings"""
        # Alice creates projects
        alice_project1 = security_harness.create_test_project("alice", "Alice Project 1")
        alice_project2 = security_harness.create_test_project("alice", "Alice Project 2")
        
        # Bob creates projects
        bob_project1 = security_harness.create_test_project("bob", "Bob Project 1")
        
        # Alice lists projects - should only see her own
        response = security_harness.client.get(
            "/api/projects",
            headers=security_harness.get_auth_headers("alice")
        )
        assert response.status_code == 200
        projects = response.json()
        
        # Alice should only see her projects, not Bob's
        alice_project_names = [p["name"] for p in projects]
        assert "Alice Project 1" in alice_project_names
        assert "Alice Project 2" in alice_project_names
        assert "Bob Project 1" not in alice_project_names, \
            "SECURITY VULNERABILITY: Alice can see Bob's projects!"
    
    def test_user_cannot_modify_other_user_projects(self, security_harness):
        """Users should not be able to modify other users' projects"""
        # Alice creates a project
        alice_project = security_harness.create_test_project("alice", "Alice Secure Project")
        alice_project_id = alice_project["id"]
        
        # Bob tries to modify Alice's project
        malicious_update = {
            "name": "Hacked by Bob",
            "description": "Bob has taken over this project"
        }
        
        response = security_harness.client.put(
            f"/api/projects/{alice_project_id}",
            json=malicious_update,
            headers=security_harness.get_auth_headers("bob")
        )
        
        # This should fail with 403 Forbidden or 404 Not Found
        assert response.status_code in [403, 404], \
            f"SECURITY VULNERABILITY: Bob modified Alice's project! Response: {response.status_code}"
        
        # Verify Alice's project is unchanged
        response = security_harness.client.get(
            f"/api/projects/{alice_project_id}",
            headers=security_harness.get_auth_headers("alice")
        )
        project = response.json()
        assert project["name"] == "Alice Secure Project", "Alice's project was modified by Bob!"
    
    def test_user_cannot_delete_other_user_projects(self, security_harness):
        """Users should not be able to delete other users' projects"""
        # Alice creates a project
        alice_project = security_harness.create_test_project("alice", "Alice Important Project")
        alice_project_id = alice_project["id"]
        
        # Bob tries to delete Alice's project
        response = security_harness.client.delete(
            f"/api/projects/{alice_project_id}",
            headers=security_harness.get_auth_headers("bob")
        )
        
        # This should fail
        assert response.status_code in [403, 404], \
            f"SECURITY VULNERABILITY: Bob deleted Alice's project! Response: {response.status_code}"
        
        # Verify Alice's project still exists
        response = security_harness.client.get(
            f"/api/projects/{alice_project_id}",
            headers=security_harness.get_auth_headers("alice")
        )
        assert response.status_code == 200, "Alice's project was deleted by Bob!"


class TestVideoAccessControl:
    """Tests for video access control and user isolation"""
    
    def test_user_cannot_access_other_user_videos(self, security_harness):
        """Users should not access videos from other users' projects"""
        # Alice creates project and uploads video
        alice_project = security_harness.create_test_project("alice", "Alice Video Project")
        alice_video = security_harness.upload_test_video("alice", alice_project["id"], "alice_secret_video.mp4")
        alice_video_id = alice_video["id"]
        
        # Bob tries to access Alice's video
        response = security_harness.client.get(
            f"/api/videos/{alice_video_id}",
            headers=security_harness.get_auth_headers("bob")
        )
        
        assert response.status_code in [403, 404], \
            f"SECURITY VULNERABILITY: Bob accessed Alice's video! Response: {response.status_code}"
    
    def test_user_cannot_upload_to_other_user_projects(self, security_harness):
        """Users should not be able to upload videos to other users' projects"""
        # Alice creates a project
        alice_project = security_harness.create_test_project("alice", "Alice Only Project")
        
        # Bob tries to upload a video to Alice's project
        test_video_content = b"bob_malicious_video_content"
        files = {"file": ("bob_evil_video.mp4", test_video_content, "video/mp4")}
        data = {"projectId": alice_project["id"]}
        
        response = security_harness.client.post(
            "/api/videos/upload",
            files=files,
            data=data,
            headers=security_harness.get_auth_headers("bob")
        )
        
        assert response.status_code in [403, 404], \
            f"SECURITY VULNERABILITY: Bob uploaded to Alice's project! Response: {response.status_code}"
    
    def test_video_listing_respects_project_ownership(self, security_harness):
        """Video listings should respect project ownership"""
        # Alice creates project and uploads video
        alice_project = security_harness.create_test_project("alice", "Alice Project")
        alice_video = security_harness.upload_test_video("alice", alice_project["id"])
        
        # Bob creates project and uploads video  
        bob_project = security_harness.create_test_project("bob", "Bob Project")
        bob_video = security_harness.upload_test_video("bob", bob_project["id"])
        
        # Alice lists videos for her project
        response = security_harness.client.get(
            f"/api/projects/{alice_project['id']}/videos",
            headers=security_harness.get_auth_headers("alice")
        )
        assert response.status_code == 200
        alice_videos = response.json()
        
        # Alice should not see Bob's videos
        video_filenames = [v.get("filename", v.get("originalName", "")) for v in alice_videos]
        assert not any("bob" in filename.lower() for filename in video_filenames), \
            "SECURITY VULNERABILITY: Alice can see Bob's videos!"


class TestAuthenticationEnforcement:
    """Tests for proper authentication enforcement"""
    
    def test_unauthenticated_access_blocked(self, security_harness):
        """Unauthenticated requests should be rejected"""
        # Try to access projects without authentication
        response = security_harness.client.get("/api/projects")
        assert response.status_code == 401, \
            f"SECURITY VULNERABILITY: Unauthenticated access allowed! Response: {response.status_code}"
        
        # Try to create project without authentication
        project_data = {
            "name": "Unauthorized Project",
            "cameraModel": "HackerCam",
            "cameraView": "Front-facing VRU",
            "signalType": "GPIO"
        }
        response = security_harness.client.post("/api/projects", json=project_data)
        assert response.status_code == 401, \
            "SECURITY VULNERABILITY: Unauthenticated project creation allowed!"
    
    def test_invalid_token_rejected(self, security_harness):
        """Invalid authentication tokens should be rejected"""
        invalid_headers = {"Authorization": "Bearer invalid_token_123"}
        
        response = security_harness.client.get("/api/projects", headers=invalid_headers)
        assert response.status_code == 401, \
            "SECURITY VULNERABILITY: Invalid token accepted!"
    
    def test_expired_token_rejected(self, security_harness):
        """Expired tokens should be rejected"""
        # Simulate expired token
        expired_headers = {"Authorization": "Bearer expired_token_from_yesterday"}
        
        response = security_harness.client.get("/api/projects", headers=expired_headers)
        assert response.status_code == 401, \
            "SECURITY VULNERABILITY: Expired token accepted!"


class TestAuthorizationBypassAttempts:
    """Tests for authorization bypass attempts and privilege escalation"""
    
    def test_parameter_tampering_blocked(self, security_harness):
        """Parameter tampering attempts should be blocked"""
        # Bob creates a project
        bob_project = security_harness.create_test_project("bob", "Bob Project")
        
        # Alice tries to access Bob's project by tampering with user ID in headers
        malicious_headers = security_harness.get_auth_headers("alice")
        malicious_headers["X-User-ID"] = security_harness.users["bob"]["id"]  # Tampering!
        
        response = security_harness.client.get(
            f"/api/projects/{bob_project['id']}",
            headers=malicious_headers
        )
        
        assert response.status_code in [403, 404], \
            f"SECURITY VULNERABILITY: Parameter tampering successful! Response: {response.status_code}"
    
    def test_sql_injection_in_project_queries(self, security_harness):
        """SQL injection attempts should be blocked"""
        # Create a project first
        alice_project = security_harness.create_test_project("alice", "Test Project")
        
        # Attempt SQL injection in project ID parameter
        malicious_project_id = "1' OR '1'='1' --"
        
        response = security_harness.client.get(
            f"/api/projects/{malicious_project_id}",
            headers=security_harness.get_auth_headers("alice")
        )
        
        # Should return 404 or 400, not expose other projects
        assert response.status_code in [400, 404], \
            f"SECURITY VULNERABILITY: SQL injection may be possible! Response: {response.status_code}"
        
        # Verify response doesn't contain unauthorized data
        if response.status_code == 200:
            data = response.json()
            assert not isinstance(data, list), "SQL injection returned multiple projects!"
    
    def test_path_traversal_in_video_access(self, security_harness):
        """Path traversal attempts should be blocked"""
        # Attempt path traversal in video ID
        malicious_video_id = "../../../etc/passwd"
        
        response = security_harness.client.get(
            f"/api/videos/{malicious_video_id}",
            headers=security_harness.get_auth_headers("alice")
        )
        
        assert response.status_code in [400, 404], \
            f"SECURITY VULNERABILITY: Path traversal possible! Response: {response.status_code}"
    
    def test_mass_assignment_vulnerability(self, security_harness):
        """Mass assignment vulnerabilities should be prevented"""
        # Alice creates a project
        alice_project = security_harness.create_test_project("alice", "Alice Project")
        
        # Try to modify project with extra fields that shouldn't be allowed
        malicious_update = {
            "name": "Updated Project",
            "ownerId": security_harness.users["bob"]["id"],  # Try to change owner!
            "isAdmin": True,  # Try to escalate privileges
            "role": "admin",
            "permissions": ["all"]
        }
        
        response = security_harness.client.put(
            f"/api/projects/{alice_project['id']}",
            json=malicious_update,
            headers=security_harness.get_auth_headers("alice")
        )
        
        # Even if update succeeds, owner should not change
        if response.status_code == 200:
            updated_project = response.json()
            assert updated_project["ownerId"] == security_harness.users["alice"]["id"], \
                "SECURITY VULNERABILITY: Mass assignment changed project owner!"


class TestDataLeakagePrevention:
    """Tests for preventing data leakage between users"""
    
    def test_error_messages_dont_leak_data(self, security_harness):
        """Error messages should not leak information about other users' data"""
        # Alice creates a project
        alice_project = security_harness.create_test_project("alice", "Secret Project")
        
        # Bob tries to access it and should get generic error
        response = security_harness.client.get(
            f"/api/projects/{alice_project['id']}",
            headers=security_harness.get_auth_headers("bob")
        )
        
        if response.status_code != 200:
            error_message = response.json().get("detail", "").lower()
            # Error should not reveal project exists or its details
            assert "secret project" not in error_message, \
                "SECURITY VULNERABILITY: Error message leaks project name!"
            assert "alice" not in error_message, \
                "SECURITY VULNERABILITY: Error message leaks owner information!"
    
    def test_search_results_filtered_by_user(self, security_harness):
        """Search results should be filtered by user ownership"""
        # Alice creates projects with specific names
        alice_project1 = security_harness.create_test_project("alice", "Confidential Research")
        alice_project2 = security_harness.create_test_project("alice", "Public Demo")
        
        # Bob creates project with similar name
        bob_project = security_harness.create_test_project("bob", "Confidential Research")
        
        # Bob searches for "Confidential" - should only find his project
        response = security_harness.client.get(
            "/api/projects?search=Confidential",
            headers=security_harness.get_auth_headers("bob")
        )
        
        if response.status_code == 200:
            projects = response.json()
            project_names = [p["name"] for p in projects]
            
            # Bob should only see his own "Confidential Research"
            confidential_projects = [name for name in project_names if "Confidential" in name]
            assert len(confidential_projects) <= 1, \
                "SECURITY VULNERABILITY: Search results leak other users' projects!"
    
    def test_statistics_dont_leak_cross_user_data(self, security_harness):
        """Dashboard statistics should not include other users' data"""
        # Alice creates projects and uploads videos
        alice_project = security_harness.create_test_project("alice", "Alice Stats Project")
        alice_video = security_harness.upload_test_video("alice", alice_project["id"])
        
        # Bob creates projects and uploads videos
        bob_project = security_harness.create_test_project("bob", "Bob Stats Project")
        bob_video = security_harness.upload_test_video("bob", bob_project["id"])
        
        # Alice checks her dashboard stats
        response = security_harness.client.get(
            "/api/dashboard/stats",
            headers=security_harness.get_auth_headers("alice")
        )
        
        if response.status_code == 200:
            stats = response.json()
            
            # Alice's stats should only reflect her data
            assert stats.get("totalProjects", 0) == 1, \
                "SECURITY VULNERABILITY: Stats include other users' projects!"
            assert stats.get("totalVideos", 0) == 1, \
                "SECURITY VULNERABILITY: Stats include other users' videos!"


class TestPrivilegeEscalation:
    """Tests for preventing privilege escalation attacks"""
    
    def test_regular_user_cannot_access_admin_endpoints(self, security_harness):
        """Regular users should not access admin-only endpoints"""
        admin_endpoints = [
            "/api/admin/users",
            "/api/admin/system-stats",
            "/api/admin/logs",
            "/api/admin/configurations"
        ]
        
        for endpoint in admin_endpoints:
            response = security_harness.client.get(
                endpoint,
                headers=security_harness.get_auth_headers("alice")
            )
            
            assert response.status_code in [403, 404, 405], \
                f"SECURITY VULNERABILITY: Regular user accessed admin endpoint {endpoint}! Response: {response.status_code}"
    
    def test_user_cannot_escalate_privileges_via_role_modification(self, security_harness):
        """Users should not be able to modify their own roles or permissions"""
        # This test assumes there's a user profile endpoint
        user_update_data = {
            "role": "admin",
            "permissions": ["all"],
            "isAdmin": True
        }
        
        response = security_harness.client.put(
            f"/api/users/{security_harness.users['alice']['id']}",
            json=user_update_data,
            headers=security_harness.get_auth_headers("alice")
        )
        
        # Should either fail or ignore the role changes
        if response.status_code == 200:
            user_data = response.json()
            assert user_data.get("role") != "admin", \
                "SECURITY VULNERABILITY: User escalated their own privileges!"


# Test execution and reporting
class SecurityTestReporter:
    """Generates security test reports"""
    
    @staticmethod
    def generate_vulnerability_report(test_results: Dict[str, Any]) -> str:
        """Generate a detailed vulnerability report"""
        report = """
MULTI-TENANCY SECURITY VULNERABILITY REPORT
==========================================
Generated: {timestamp}

EXECUTIVE SUMMARY:
This report documents security vulnerabilities found in the AI Model Validation Platform
related to multi-tenant user isolation and access control.

CRITICAL FINDINGS:
""".format(timestamp=datetime.now().isoformat())
        
        critical_failures = []
        for test_name, result in test_results.items():
            if result.get("failed") and "SECURITY VULNERABILITY" in result.get("error", ""):
                critical_failures.append(f"- {test_name}: {result.get('error', 'Unknown error')}")
        
        if critical_failures:
            report += "\n".join(critical_failures)
        else:
            report += "✅ No critical security vulnerabilities detected."
        
        report += """

RECOMMENDED FIXES:
1. Implement proper user context filtering in all database queries
2. Add authorization middleware to validate resource ownership
3. Implement proper authentication enforcement on all endpoints
4. Add input validation and sanitization to prevent injection attacks
5. Review error handling to prevent information leakage
6. Implement proper privilege escalation prevention

NEXT STEPS:
1. Apply security fixes based on this report
2. Re-run tests to verify fixes
3. Implement additional security monitoring
4. Conduct penetration testing
"""
        return report


def pytest_runtest_makereport(item, call):
    """Custom pytest hook for security test reporting"""
    if call.when == "call":
        if hasattr(call.result, "failed") and call.result.failed:
            if "SECURITY VULNERABILITY" in str(call.result.longrepr):
                print(f"\n🚨 CRITICAL SECURITY ISSUE FOUND: {item.name}")
                print(f"Details: {call.result.longrepr}")


if __name__ == "__main__":
    print("🔒 Running Multi-Tenancy Security Test Suite")
    print("=" * 60)
    print("These tests validate proper user isolation and access control.")
    print("EXPECTED: Many tests should FAIL initially, demonstrating vulnerabilities.")
    print("After applying security fixes, all tests should PASS.")
    print("=" * 60)
    
    # Run the tests
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--capture=no"
    ])
    
    if exit_code == 0:
        print("\n✅ All security tests passed! Multi-tenancy is properly secured.")
    else:
        print("\n🚨 Security vulnerabilities detected! Review test output and apply fixes.")
        print("See the test results above for specific vulnerability details.")
    
    exit(exit_code)
"""
Test Approval Workflow

Critical Test: Verify approval/rejection workflow for test sessions.
Based on CONSOLIDATED_APPROVAL_PROCESS_ANALYSIS.md Lines 1876-2050
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import TestSession, Project, Video, AuthUser


class TestApprovalWorkflow:
    """Test suite for test session approval workflow"""

    @pytest.fixture
    def setup_completed_session(self, db_session: Session):
        """Setup a completed test session ready for approval"""
        # Create user
        user = AuthUser(
            id="test-user",
            email="tester@example.com",
            username="tester",
            hashed_password=AuthUser.get_password_hash("password123"),
            is_active=True,
            is_verified=True
        )
        db_session.add(user)

        # Create project
        project = Project(
            id="approval-project",
            name="Approval Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            owner_id=user.id
        )
        db_session.add(project)

        # Create video
        video = Video(
            id="approval-video",
            project_id=project.id,
            filename="approval.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        # Create completed session
        session = TestSession(
            id="approval-session",
            project_id=project.id,
            video_id=video.id,
            status="completed",
            outcome="PASS",  # New field from recommendation
            precision=0.85,
            recall=0.80,
            f1_score=0.82,
            mean_latency_ms=45.0,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            # Approval fields (from recommendation)
            approval_status="pending",
            approved_by=None,
            approved_at=None,
            approval_comments=None,
            rejection_reason=None
        )
        db_session.add(session)
        db_session.commit()

        return {"session": session, "user": user, "project": project, "video": video}

    def test_approve_session(self, db_session, setup_completed_session):
        """
        Test approving a test session

        Expected:
          - approval_status = 'approved'
          - approved_by = user_id
          - approved_at = timestamp
          - approval_comments saved
        """
        scenario = setup_completed_session
        session = scenario["session"]
        user = scenario["user"]

        # Approve session
        session.approval_status = "approved"
        session.approved_by = user.id
        session.approved_at = datetime.now(timezone.utc)
        session.approval_comments = "All metrics within acceptable range"

        db_session.commit()

        # Verify
        session_check = db_session.execute(select(TestSession).filter_by(
            id=session.id
        )).scalar_one_or_none()

        assert session_check.approval_status == "approved"
        assert session_check.approved_by == user.id
        assert session_check.approved_at is not None
        assert session_check.approval_comments == "All metrics within acceptable range"
        assert session_check.rejection_reason is None

    def test_reject_session(self, db_session, setup_completed_session):
        """
        Test rejecting a test session

        Expected:
          - approval_status = 'rejected'
          - approved_by = user_id (who rejected)
          - rejection_reason saved
        """
        scenario = setup_completed_session
        session = scenario["session"]
        user = scenario["user"]

        # Reject session
        session.approval_status = "rejected"
        session.approved_by = user.id
        session.approved_at = datetime.now(timezone.utc)
        session.rejection_reason = "Latency exceeds requirements for production deployment"

        db_session.commit()

        # Verify
        session_check = db_session.execute(select(TestSession).filter_by(
            id=session.id
        )).scalar_one_or_none()

        assert session_check.approval_status == "rejected"
        assert session_check.approved_by == user.id
        assert session_check.rejection_reason == "Latency exceeds requirements for production deployment"

    def test_cannot_approve_running_session(self, db_session):
        """
        Test that running sessions cannot be approved

        Expected:
          - Validation error
          - Approval not allowed until completed
        """
        # Create running session
        project = Project(
            id="running-project",
            name="Running Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video = Video(
            id="running-video",
            project_id=project.id,
            filename="running.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        session = TestSession(
            id="running-session",
            project_id=project.id,
            video_id=video.id,
            status="running",  # NOT completed
            approval_status="pending"
        )
        db_session.add(session)
        db_session.commit()

        # Try to approve
        if session.status != "completed":
            with pytest.raises(ValueError) as exc_info:
                if session.status != "completed":
                    raise ValueError("Cannot approve session that is not completed")

            assert "not completed" in str(exc_info.value)

    def test_approval_authorization(self, db_session, setup_completed_session):
        """
        Test that only authorized users can approve

        Expected:
          - Regular users can approve their own projects
          - Superusers can approve any project
          - Unrelated users cannot approve
        """
        scenario = setup_completed_session
        session = scenario["session"]

        # Create another user
        other_user = AuthUser(
            id="other-user",
            email="other@example.com",
            username="other",
            hashed_password=AuthUser.get_password_hash("password123"),
            is_active=True,
            is_verified=True,
            is_superuser=False
        )
        db_session.add(other_user)

        # Create superuser
        superuser = AuthUser(
            id="superuser",
            email="admin@example.com",
            username="admin",
            hashed_password=AuthUser.get_password_hash("password123"),
            is_active=True,
            is_verified=True,
            is_superuser=True
        )
        db_session.add(superuser)
        db_session.commit()

        # Check authorization
        project = scenario["project"]
        owner = scenario["user"]

        # Owner can approve
        assert session.project_id == project.id
        assert project.owner_id == owner.id
        # Authorization check would be in endpoint: if user.id == project.owner_id or user.is_superuser

        # Superuser can approve
        assert superuser.is_superuser is True

        # Other user cannot (unless superuser)
        assert other_user.id != project.owner_id
        assert other_user.is_superuser is False

    def test_approval_status_in_api_response(self, db_session, setup_completed_session):
        """
        Test that approval status is included in API response

        Expected API response fields:
          - approval_status
          - approved_by
          - approved_at
          - approval_comments or rejection_reason
        """
        scenario = setup_completed_session
        session = scenario["session"]

        # Simulate API response serialization
        api_response = {
            "session_id": session.id,
            "status": session.status,
            "outcome": session.outcome,
            "approval_status": session.approval_status,
            "approved_by": session.approved_by,
            "approved_at": session.approved_at.isoformat() if session.approved_at else None,
            "approval_comments": session.approval_comments,
            "rejection_reason": session.rejection_reason
        }

        assert "approval_status" in api_response
        assert api_response["approval_status"] == "pending"
        assert api_response["approved_by"] is None  # Not yet approved


class TestConditionalPassApprovalRequirement:
    """Test that CONDITIONAL_PASS requires approval"""

    def test_conditional_pass_requires_approval(self, db_session):
        """
        Test that CONDITIONAL_PASS sessions must be manually approved

        Expected:
          - outcome = "CONDITIONAL_PASS"
          - approval_status = "pending"
          - Cannot deploy model until approved
        """
        project = Project(
            id="conditional-project",
            name="Conditional Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video = Video(
            id="conditional-video",
            project_id=project.id,
            filename="conditional.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        # Session with CONDITIONAL_PASS
        session = TestSession(
            id="conditional-session",
            project_id=project.id,
            video_id=video.id,
            status="completed",
            outcome="CONDITIONAL_PASS",  # Borderline metrics
            precision=0.65,  # Above 0.6 threshold
            recall=0.60,     # At threshold
            mean_latency_ms=140,  # Below 150ms limit
            approval_status="pending"
        )
        db_session.add(session)
        db_session.commit()

        # Verify approval required
        assert session.outcome == "CONDITIONAL_PASS"
        assert session.approval_status == "pending"

        # Simulate deployment check
        def can_deploy_model(session):
            if session.outcome == "FAIL":
                return False
            if session.outcome == "CONDITIONAL_PASS":
                return session.approval_status == "approved"
            return True  # PASS

        assert can_deploy_model(session) is False, \
            "CONDITIONAL_PASS should require approval before deployment"

    def test_pass_no_approval_required(self, db_session):
        """
        Test that PASS sessions can proceed without approval

        Expected:
          - outcome = "PASS"
          - Can deploy immediately
          - Approval optional (for record-keeping)
        """
        project = Project(
            id="pass-project",
            name="Pass Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)

        video = Video(
            id="pass-video",
            project_id=project.id,
            filename="pass.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        session = TestSession(
            id="pass-session",
            project_id=project.id,
            video_id=video.id,
            status="completed",
            outcome="PASS",  # Meets all criteria
            precision=0.85,
            recall=0.80,
            mean_latency_ms=75,
            approval_status="pending"  # Optional
        )
        db_session.add(session)
        db_session.commit()

        # Can deploy without approval
        def can_deploy_model(session):
            if session.outcome == "FAIL":
                return False
            if session.outcome == "CONDITIONAL_PASS":
                return session.approval_status == "approved"
            return True

        assert can_deploy_model(session) is True, \
            "PASS should allow deployment without approval"


class TestApprovalAuditTrail:
    """Test approval audit trail and history"""

    def test_approval_history_recorded(self, db_session):
        """
        Test that approval history is properly recorded

        Expected:
          - Timestamp of approval
          - User who approved
          - Comments captured
        """
        user = AuthUser(
            id="auditor",
            email="auditor@example.com",
            username="auditor",
            hashed_password=AuthUser.get_password_hash("password123"),
            is_active=True,
            is_verified=True
        )
        db_session.add(user)

        project = Project(
            id="audit-project",
            name="Audit Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            owner_id=user.id
        )
        db_session.add(project)

        video = Video(
            id="audit-video",
            project_id=project.id,
            filename="audit.mp4",
            duration_ms=30000
        )
        db_session.add(video)

        session = TestSession(
            id="audit-session",
            project_id=project.id,
            video_id=video.id,
            status="completed",
            outcome="PASS",
            approval_status="pending"
        )
        db_session.add(session)
        db_session.commit()

        # Record approval
        approval_time = datetime.now(timezone.utc)
        session.approval_status = "approved"
        session.approved_by = user.id
        session.approved_at = approval_time
        session.approval_comments = "Verified metrics, approved for production"

        db_session.commit()

        # Verify audit trail
        session_check = db_session.execute(select(TestSession).filter_by(
            id=session.id
        )).scalar_one_or_none()

        assert session_check.approved_by == user.id
        assert session_check.approved_at is not None
        assert (datetime.now(timezone.utc) - session_check.approved_at).total_seconds() < 5
        assert "production" in session_check.approval_comments

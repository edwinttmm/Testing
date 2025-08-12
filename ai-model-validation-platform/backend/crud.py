from sqlalchemy.orm import Session
from typing import List, Optional

from models import Project, Video, TestSession, DetectionEvent, GroundTruthObject, AuditLog
from schemas import (
    ProjectCreate, ProjectUpdate,
    TestSessionCreate,
    DetectionEvent as DetectionEventSchema,
    AuditLogCreate
)


# Project CRUD
def create_project(db: Session, project: ProjectCreate, user_id: str = "anonymous") -> Project:
    # Use model_dump instead of deprecated dict() method
    project_data = project.model_dump(by_alias=True)
    db_project = Project(
        **project_data,
        owner_id=user_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def get_projects(db: Session, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[Project]:
    # Return all projects when no auth is needed  
    return db.query(Project).offset(skip).limit(limit).all()

def get_project(db: Session, project_id: str, user_id: str = "anonymous") -> Optional[Project]:
    # Return any project when no auth is needed
    return db.query(Project).filter(Project.id == project_id).first()

def update_project(db: Session, project_id: str, project_update: ProjectUpdate, user_id: str) -> Optional[Project]:
    db_project = get_project(db, project_id, user_id)
    if db_project:
        update_data = project_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_project, field, value)
        db.commit()
        db.refresh(db_project)
    return db_project

# Video CRUD
def create_video(db: Session, project_id: str, filename: str, file_path: str = None, file_size: int = None) -> Video:
    db_video = Video(
        filename=filename,
        file_path=file_path or f"/uploads/{filename}",
        file_size=file_size,
        project_id=project_id
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video

def get_videos(db: Session, project_id: str = None, skip: int = 0, limit: int = 100) -> List[Video]:
    query = db.query(Video)
    if project_id:
        query = query.filter(Video.project_id == project_id)
    return query.offset(skip).limit(limit).all()

def get_video(db: Session, video_id: str) -> Optional[Video]:
    return db.query(Video).filter(Video.id == video_id).first()

def update_video_status(db: Session, video_id: str, status: str, duration: float = None) -> Optional[Video]:
    db_video = get_video(db, video_id)
    if db_video:
        db_video.status = status
        if duration:
            db_video.duration = duration
        db.commit()
        db.refresh(db_video)
    return db_video

# Ground Truth CRUD
def create_ground_truth_object(db: Session, video_id: str, timestamp: float, 
                              class_label: str, bounding_box: dict, confidence: float) -> GroundTruthObject:
    db_object = GroundTruthObject(
        video_id=video_id,
        timestamp=timestamp,
        class_label=class_label,
        bounding_box=bounding_box,
        confidence=confidence
    )
    db.add(db_object)
    db.commit()
    db.refresh(db_object)
    return db_object

def get_ground_truth_objects(db: Session, video_id: str) -> List[GroundTruthObject]:
    return db.query(GroundTruthObject).filter(GroundTruthObject.video_id == video_id).all()

# Test Session CRUD
def create_test_session(db: Session, test_session: TestSessionCreate, user_id: str) -> TestSession:
    db_session = TestSession(**test_session.model_dump())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_test_sessions(db: Session, project_id: str = None, skip: int = 0, limit: int = 100) -> List[TestSession]:
    query = db.query(TestSession)
    if project_id:
        query = query.filter(TestSession.project_id == project_id)
    return query.offset(skip).limit(limit).all()

def get_test_session(db: Session, session_id: str) -> Optional[TestSession]:
    return db.query(TestSession).filter(TestSession.id == session_id).first()

# Detection Event CRUD
def create_detection_event(db: Session, detection: DetectionEventSchema) -> DetectionEvent:
    db_detection = DetectionEvent(**detection.model_dump())
    db.add(db_detection)
    db.commit()
    db.refresh(db_detection)
    return db_detection

def get_detection_events(db: Session, test_session_id: str) -> List[DetectionEvent]:
    return db.query(DetectionEvent).filter(DetectionEvent.test_session_id == test_session_id).all()

# Audit Log CRUD
def create_audit_log(db: Session, audit_log: AuditLogCreate, user_id: str = None) -> AuditLog:
    db_log = AuditLog(
        **audit_log.model_dump(),
        user_id=user_id
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_audit_logs(db: Session, user_id: str = None, event_type: str = None, 
                   skip: int = 0, limit: int = 100) -> List[AuditLog]:
    query = db.query(AuditLog)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    return query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

# Dashboard CRUD
def get_dashboard_stats(db: Session, user_id: str):
    """Get dashboard statistics for a user"""
    from sqlalchemy import func
    
    project_count = db.query(func.count(Project.id)).filter(Project.owner_id == user_id).scalar() or 0
    
    # Get video count for user's projects
    video_count = db.query(func.count(Video.id)).join(Project).filter(Project.owner_id == user_id).scalar() or 0
    
    # Get test session count for user's projects
    test_session_count = db.query(func.count(TestSession.id)).join(Project).filter(Project.owner_id == user_id).scalar() or 0
    
    # Get detection event count for user's test sessions
    detection_event_count = db.query(func.count(DetectionEvent.id)).join(TestSession).join(Project).filter(Project.owner_id == user_id).scalar() or 0
    
    return {
        "project_count": project_count,
        "video_count": video_count,
        "test_session_count": test_session_count,
        "detection_event_count": detection_event_count
    }
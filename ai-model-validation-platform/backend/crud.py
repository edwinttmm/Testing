from sqlalchemy.orm import Session
from typing import List, Optional

from models import Project, Video, TestSession, DetectionEvent, GroundTruthObject, AuditLog, VideoProjectLink
from schemas import (
    ProjectCreate, ProjectUpdate,
    TestSessionCreate,
    DetectionEvent as DetectionEventSchema,
    AuditLogCreate
)


# Project CRUD
def create_project(db: Session, project: ProjectCreate, user_id: str = "anonymous") -> Project:
    # Use model_dump without by_alias to get snake_case field names for database
    project_data = project.model_dump()
    db_project = Project(
        **project_data,
        owner_id=user_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def get_projects(db: Session, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[Project]:
    # SECURITY FIX: Filter by user ownership - each user sees only their projects
    # Lightweight loading - projects are now playlist-like containers
    return db.query(Project).filter(Project.owner_id == user_id).offset(skip).limit(limit).all()

def get_project(db: Session, project_id: str, user_id: str = "anonymous", load_videos: bool = False) -> Optional[Project]:
    # SECURITY FIX: Filter by both project ID and user ownership
    if load_videos:
        # Load project with associated videos via junction table
        from sqlalchemy.orm import joinedload
        return db.query(Project).options(
            joinedload(Project.video_links).joinedload(VideoProjectLink.video)
        ).filter(
            Project.id == project_id,
            Project.owner_id == user_id
        ).first()
    else:
        # Lightweight loading without videos
        return db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == user_id
        ).first()

def update_project(db: Session, project_id: str, project_update: ProjectUpdate, user_id: str) -> Optional[Project]:
    db_project = get_project(db, project_id, user_id)
    if db_project:
        # Use model_dump without by_alias to get snake_case field names for database
        update_data = project_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_project, field, value)
        db.commit()
        db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id: str, user_id: str = "anonymous") -> bool:
    """
    Delete a project with many-to-many relationship handling.
    Only deletes videos if they're not in other projects.
    Returns True if deleted, False if not found
    """
    db_project = get_project(db, project_id, user_id, load_videos=True)
    if not db_project:
        return False
    
    try:
        import os
        
        # Handle video deletion carefully in many-to-many structure
        project_videos = get_project_videos(db, project_id, user_id)
        
        for video in project_videos:
            # Check if video is in other projects
            other_projects = db.query(VideoProjectLink).filter(
                VideoProjectLink.video_id == video.id,
                VideoProjectLink.project_id != project_id
            ).count()
            
            # Only delete video if it's not in other projects
            if other_projects == 0:
                # Clean up physical file
                if video.file_path and os.path.exists(video.file_path):
                    try:
                        os.remove(video.file_path)
                    except OSError:
                        pass  # File may already be deleted or inaccessible
                
                # Delete video and its cascade relationships
                db.delete(video)
        
        # Delete the project - CASCADE will automatically handle:
        # - TestSessions (via cascade="all, delete-orphan")
        # - AnnotationSessions (via cascade="all, delete-orphan") 
        # - VideoProjectLinks (via cascade="all, delete-orphan")
        # - DetectionEvents (via TestSession cascade)
        # - TestResults (via TestSession cascade)
        # - DetectionComparisons (via TestSession cascade)
        db.delete(db_project)
        db.commit()
        
        return True
        
    except Exception as e:
        db.rollback()
        raise e

# Video Project Assignment Functions - NEW for Many-to-Many
def assign_video_to_project(db: Session, video_id: str, project_id: str, assignment_reason: str = None, confidence_score: float = None) -> VideoProjectLink:
    """Assign a video to a project via junction table"""
    # Check if assignment already exists
    existing = db.query(VideoProjectLink).filter(
        VideoProjectLink.video_id == video_id,
        VideoProjectLink.project_id == project_id
    ).first()
    
    if existing:
        return existing
    
    db_link = VideoProjectLink(
        video_id=video_id,
        project_id=project_id,
        assignment_reason=assignment_reason,
        confidence_score=confidence_score,
        intelligent_match=confidence_score is not None
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link

def remove_video_from_project(db: Session, video_id: str, project_id: str, user_id: str = "anonymous") -> bool:
    """Remove a video from a project (user security check included)"""
    # Security check: ensure user owns the project
    project = get_project(db, project_id, user_id)
    if not project:
        return False
    
    db_link = db.query(VideoProjectLink).filter(
        VideoProjectLink.video_id == video_id,
        VideoProjectLink.project_id == project_id
    ).first()
    
    if db_link:
        db.delete(db_link)
        db.commit()
        return True
    return False

def get_project_videos(db: Session, project_id: str, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[Video]:
    """Get all videos assigned to a specific project"""
    # Security check: ensure user owns the project
    project = get_project(db, project_id, user_id)
    if not project:
        return []
    
    return db.query(Video).join(VideoProjectLink).filter(
        VideoProjectLink.project_id == project_id
    ).offset(skip).limit(limit).all()

def get_video_projects(db: Session, video_id: str, user_id: str = "anonymous") -> List[Project]:
    """Get all projects that contain a specific video (user security check)"""
    return db.query(Project).join(VideoProjectLink).filter(
        VideoProjectLink.video_id == video_id,
        Project.owner_id == user_id
    ).all()

# Video CRUD - Updated for Many-to-Many Structure
def create_video(db: Session, filename: str, file_path: str = None, file_size: int = None, project_ids: List[str] = None) -> Video:
    """Create video with project assignment - project_id is required by database"""
    # Determine primary project_id (first in list or required for NOT NULL constraint)
    primary_project_id = project_ids[0] if project_ids else None
    if not primary_project_id:
        raise ValueError("At least one project_id is required for video creation")
    
    db_video = Video(
        filename=filename,
        file_path=file_path or f"/uploads/{filename}",
        file_size=file_size,
        project_id=primary_project_id  # Required by database NOT NULL constraint
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    
    # Assign to additional projects if provided (beyond the primary)
    if project_ids and len(project_ids) > 1:
        for project_id in project_ids[1:]:  # Skip first as it's already the primary
            assign_video_to_project(db, db_video.id, project_id)
    
    return db_video

# Legacy function for backward compatibility
def create_video_legacy(db: Session, project_id: str, filename: str, file_path: str = None, file_size: int = None) -> Video:
    """Legacy function - creates video and assigns to single project"""
    return create_video(db, filename, file_path, file_size, [project_id] if project_id else None)

def get_videos(db: Session, project_id: str = None, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[Video]:
    # SECURITY FIX: Join through VideoProjectLink to ensure user can only access their videos
    if project_id:
        # Get videos for specific project
        query = db.query(Video).join(VideoProjectLink).join(Project).filter(
            Project.owner_id == user_id,
            VideoProjectLink.project_id == project_id
        )
    else:
        # Get all videos accessible to user across all their projects
        query = db.query(Video).join(VideoProjectLink).join(Project).filter(
            Project.owner_id == user_id
        ).distinct()  # Prevent duplicates if video is in multiple projects
    
    return query.offset(skip).limit(limit).all()

def get_video(db: Session, video_id: str, user_id: str = "anonymous") -> Optional[Video]:
    # SECURITY FIX: Join through VideoProjectLink to ensure user can only access their videos
    return db.query(Video).join(VideoProjectLink).join(Project).filter(
        Video.id == video_id,
        Project.owner_id == user_id
    ).first()

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
                              class_label: str, x: float, y: float, width: float, height: float,
                              confidence: float, frame_number: int = None, validated: bool = True, 
                              difficult: bool = False, bounding_box: dict = None,
                              screenshot_path: str = None, screenshot_zoom_path: str = None) -> GroundTruthObject:
    # Create bounding_box dict for backward compatibility if not provided
    if bounding_box is None:
        bounding_box = {"x": x, "y": y, "width": width, "height": height}
    
    db_object = GroundTruthObject(
        video_id=video_id,
        frame_number=frame_number,
        timestamp=timestamp,
        class_label=class_label,
        x=x,
        y=y,
        width=width,
        height=height,
        bounding_box=bounding_box,  # Keep for backward compatibility
        confidence=confidence,
        validated=validated,
        difficult=difficult,
        screenshot_path=screenshot_path,
        screenshot_zoom_path=screenshot_zoom_path
    )
    db.add(db_object)
    db.commit()
    db.refresh(db_object)
    return db_object

def get_ground_truth_objects(db: Session, video_id: str, user_id: str = "anonymous") -> List[GroundTruthObject]:
    # SECURITY FIX: Join through Video, VideoProjectLink, and Project to ensure user can only access their ground truth objects
    return db.query(GroundTruthObject).join(Video).join(VideoProjectLink).join(Project).filter(
        GroundTruthObject.video_id == video_id,
        Project.owner_id == user_id
    ).all()

# Test Session CRUD
def create_test_session(db: Session, test_session: TestSessionCreate, user_id: str) -> TestSession:
    db_session = TestSession(**test_session.model_dump())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_test_sessions(db: Session, project_id: str = None, video_id: str = None, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[TestSession]:
    # SECURITY FIX: Join with Project to ensure user can only access their test sessions
    query = db.query(TestSession).join(Project).filter(Project.owner_id == user_id)
    if project_id:
        query = query.filter(TestSession.project_id == project_id)
    if video_id:
        # Ensure video belongs to user through VideoProjectLink
        video_subquery = db.query(Video.id).join(VideoProjectLink).join(Project).filter(
            Project.owner_id == user_id,
            Video.id == video_id
        ).subquery()
        query = query.filter(TestSession.video_id.in_(video_subquery))
    return query.offset(skip).limit(limit).all()

def get_test_session(db: Session, session_id: str, user_id: str = "anonymous") -> Optional[TestSession]:
    # SECURITY FIX: Join with Project to ensure user can only access their test sessions
    return db.query(TestSession).join(Project).filter(
        TestSession.id == session_id,
        Project.owner_id == user_id
    ).first()

# Detection Event CRUD
def create_detection_event(db: Session, detection: DetectionEventSchema) -> DetectionEvent:
    db_detection = DetectionEvent(**detection.model_dump())
    db.add(db_detection)
    db.commit()
    db.refresh(db_detection)
    return db_detection

def get_detection_events(db: Session, test_session_id: str, user_id: str = "anonymous") -> List[DetectionEvent]:
    # SECURITY FIX: Join through TestSession and Project to ensure user can only access their detection events
    return db.query(DetectionEvent).join(TestSession).join(Project).filter(
        DetectionEvent.test_session_id == test_session_id,
        Project.owner_id == user_id
    ).all()

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
    """Get dashboard statistics for a user - Updated for many-to-many structure"""
    from sqlalchemy import func
    
    project_count = db.query(func.count(Project.id)).filter(Project.owner_id == user_id).scalar() or 0
    
    # Get unique video count for user's projects through junction table
    video_count = db.query(func.count(Video.id.distinct())).join(VideoProjectLink).join(Project).filter(
        Project.owner_id == user_id
    ).scalar() or 0
    
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

# Bulk Operations for Many-to-Many Structure
def bulk_assign_videos_to_project(db: Session, project_id: str, video_ids: List[str], user_id: str = "anonymous") -> List[VideoProjectLink]:
    """Assign multiple videos to a project (with user security check)"""
    # Security check: ensure user owns the project
    project = get_project(db, project_id, user_id)
    if not project:
        return []
    
    links = []
    for video_id in video_ids:
        # Check if video exists and user has access
        video = get_video(db, video_id, user_id)
        if video:
            link = assign_video_to_project(db, video_id, project_id, "bulk_assignment")
            links.append(link)
    
    return links

def bulk_remove_videos_from_project(db: Session, project_id: str, video_ids: List[str], user_id: str = "anonymous") -> int:
    """Remove multiple videos from a project (with user security check)"""
    # Security check: ensure user owns the project
    project = get_project(db, project_id, user_id)
    if not project:
        return 0
    
    removed_count = 0
    for video_id in video_ids:
        if remove_video_from_project(db, video_id, project_id, user_id):
            removed_count += 1
    
    return removed_count

def get_orphaned_videos(db: Session, user_id: str = "anonymous") -> List[Video]:
    """Get videos that aren't assigned to any project for a user"""
    # Find videos not in any project link
    orphaned = []
    
    # Get all videos accessible to user
    user_videos_query = db.query(Video).join(VideoProjectLink).join(Project).filter(
        Project.owner_id == user_id
    )
    
    all_video_ids = {v.id for v in user_videos_query.all()}
    
    for video_id in all_video_ids:
        link_count = db.query(VideoProjectLink).filter(
            VideoProjectLink.video_id == video_id
        ).count()
        if link_count == 0:
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                orphaned.append(video)
    
    return orphaned

def cleanup_orphaned_videos(db: Session, user_id: str = "anonymous") -> int:
    """Delete videos that aren't assigned to any project"""
    import os
    
    orphaned_videos = get_orphaned_videos(db, user_id)
    deleted_count = 0
    
    for video in orphaned_videos:
        try:
            # Clean up physical file
            if video.file_path and os.path.exists(video.file_path):
                try:
                    os.remove(video.file_path)
                except OSError:
                    pass  # File may already be deleted or inaccessible
            
            # Delete video
            db.delete(video)
            deleted_count += 1
        except Exception:
            continue  # Skip problematic videos
    
    if deleted_count > 0:
        db.commit()
    
    return deleted_count

def migrate_legacy_video_relationships(db: Session) -> int:
    """Migrate videos with direct project_id to VideoProjectLink table"""
    # Find videos that still have direct project_id relationships
    legacy_videos = db.query(Video).filter(Video.project_id.isnot(None)).all()
    migrated_count = 0
    
    for video in legacy_videos:
        # Create VideoProjectLink entry
        existing_link = db.query(VideoProjectLink).filter(
            VideoProjectLink.video_id == video.id,
            VideoProjectLink.project_id == video.project_id
        ).first()
        
        if not existing_link:
            link = VideoProjectLink(
                video_id=video.id,
                project_id=video.project_id,
                assignment_reason="legacy_migration",
                intelligent_match=False
            )
            db.add(link)
            migrated_count += 1
        
        # Clear the direct relationship
        video.project_id = None
    
    if migrated_count > 0:
        db.commit()
    
    return migrated_count

def validate_project_video_relationships(db: Session, user_id: str = "anonymous") -> dict:
    """Validate integrity of project-video relationships for a user"""
    issues = {
        "orphaned_videos": 0,
        "invalid_links": 0,
        "legacy_relationships": 0,
        "duplicate_links": 0
    }
    
    # Count orphaned videos
    issues["orphaned_videos"] = len(get_orphaned_videos(db, user_id))
    
    # Count legacy relationships
    user_projects = get_projects(db, user_id, limit=1000)  # Get all projects
    project_ids = [p.id for p in user_projects]
    
    if project_ids:
        legacy_count = db.query(Video).join(VideoProjectLink).join(Project).filter(
            Project.owner_id == user_id,
            Video.project_id.isnot(None)
        ).count()
        issues["legacy_relationships"] = legacy_count
        
        # Count invalid links (links to non-existent projects/videos)
        from sqlalchemy import and_
        invalid_links = db.query(VideoProjectLink).outerjoin(
            Project, VideoProjectLink.project_id == Project.id
        ).outerjoin(
            Video, VideoProjectLink.video_id == Video.id
        ).filter(
            and_(
                VideoProjectLink.project_id.in_(project_ids),
                Project.id.is_(None)
            )
        ).count()
        issues["invalid_links"] = invalid_links
        
        # Count duplicate links
        from sqlalchemy import func
        duplicates = db.query(
            VideoProjectLink.video_id,
            VideoProjectLink.project_id,
            func.count().label('count')
        ).join(Project).filter(
            Project.owner_id == user_id
        ).group_by(
            VideoProjectLink.video_id,
            VideoProjectLink.project_id
        ).having(func.count() > 1).count()
        issues["duplicate_links"] = duplicates
    
    return issues
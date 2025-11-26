from sqlalchemy.orm import Session
from typing import List, Optional
import time
from sqlalchemy import func

from models import Project, Video, TestSession, DetectionEvent, GroundTruthObject, AuditLog, VideoProjectLink
from config.timing_config import MATCHING_TOLERANCE_MS
from schemas import (
    ProjectCreate, ProjectUpdate,
    TestSessionCreate,
    DetectionEvent as DetectionEventSchema,
    AuditLogCreate
)
import logging

logger = logging.getLogger(__name__)


# CRITICAL FIX: Ground Truth Single Source of Truth
def get_session_ground_truth_count(db: Session, session_id: str) -> int:
    """
    Single source of truth for ground truth event counts.

    This function eliminates discrepancies (0/242/514 mismatch) by querying
    the database directly instead of relying on cached session_metrics.

    Args:
        db: Database session
        session_id: Test session ID

    Returns:
        Total ground truth events for this session across all videos
    """
    try:
        # Get session to find associated video IDs
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return 0

        # Get video IDs from session (assuming session has video_ids field)
        # Adapt this based on your actual model structure
        video_ids = []
        if hasattr(session, 'video_ids') and session.video_ids:
            video_ids = session.video_ids
        elif hasattr(session, 'video_id') and session.video_id:
            video_ids = [session.video_id]

        if not video_ids:
            logger.warning(f"No videos associated with session: {session_id}")
            return 0

        # Count GT events across all videos
        gt_count = db.query(func.count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id.in_(video_ids)
        ).scalar() or 0

        logger.info(f"📊 GT count for session {session_id}: {gt_count} events across {len(video_ids)} videos")
        return gt_count

    except Exception as e:
        logger.error(f"❌ Error getting GT count for session {session_id}: {e}")
        return 0


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
    """Get all videos assigned to a specific project with eager loading to prevent N+1 queries"""
    from sqlalchemy.orm import selectinload, joinedload

    # Security check: ensure user owns the project
    project = get_project(db, project_id, user_id)
    if not project:
        return []

    # PERFORMANCE FIX: Eager load all relationships to prevent N+1 queries
    linked_videos = db.query(Video).join(VideoProjectLink).options(
        selectinload(Video.annotations),
        selectinload(Video.project_links),
        joinedload(Video.project)
    ).filter(
        VideoProjectLink.project_id == project_id
    ).offset(skip).limit(limit).all()

    linked_ids = {video.id for video in linked_videos}

    direct_query = db.query(Video).options(
        selectinload(Video.annotations),
        selectinload(Video.project_links),
        joinedload(Video.project)
    ).filter(
        Video.project_id == project_id
    )
    if linked_ids:
        direct_query = direct_query.filter(~Video.id.in_(linked_ids))

    direct_videos = direct_query.offset(skip).limit(max(0, limit - len(linked_videos))).all()

    return linked_videos + direct_videos

def get_video_projects(db: Session, video_id: str, user_id: str = "anonymous") -> List[Project]:
    """Get all projects that contain a specific video (user security check)"""
    return db.query(Project).join(VideoProjectLink).filter(
        VideoProjectLink.video_id == video_id,
        Project.owner_id == user_id
    ).all()

# Video CRUD - Updated for Many-to-Many Structure
def create_video(db: Session, filename: str, file_path: str = None, file_size: int = None, project_ids: List[str] = None) -> Video:
    """Create video as shared resource - can be linked to multiple projects"""
    # Create video as project-independent resource
    db_video = Video(
        filename=filename,
        file_path=file_path or f"/uploads/{filename}",
        file_size=file_size,
        project_id=None  # Videos are now shared resources
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    
    # Link to all provided projects via VideoProjectLink
    if project_ids:
        for project_id in project_ids:
            assign_video_to_project(db, db_video.id, project_id, "Initial upload assignment")
    
    return db_video

# Legacy function for backward compatibility
def create_video_legacy(db: Session, project_id: str, filename: str, file_path: str = None, file_size: int = None) -> Video:
    """Legacy function - creates video and assigns to single project"""
    return create_video(db, filename, file_path, file_size, [project_id] if project_id else None)

def get_videos(db: Session, project_id: str = None, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[Video]:
    """Get videos with eager loading to prevent N+1 queries"""
    from sqlalchemy.orm import selectinload, joinedload
    import time

    start_time = time.time()

    # SECURITY FIX: Join through VideoProjectLink to ensure user can only access their videos
    # PERFORMANCE FIX: Add eager loading for relationships
    if project_id:
        # Get videos for specific project
        query = db.query(Video).join(VideoProjectLink).join(Project).options(
            selectinload(Video.ground_truth_objects),
            selectinload(Video.project_links),
            joinedload(Video.project)
        ).filter(
            Project.owner_id == user_id,
            VideoProjectLink.project_id == project_id
        )
    else:
        # Get all videos accessible to user across all their projects
        query = db.query(Video).join(VideoProjectLink).join(Project).options(
            selectinload(Video.ground_truth_objects),
            selectinload(Video.project_links),
            joinedload(Video.project)
        ).filter(
            Project.owner_id == user_id
        ).distinct()  # Prevent duplicates if video is in multiple projects

    videos = query.offset(skip).limit(limit).all()

    query_time = (time.time() - start_time) * 1000
    logger.info(f"Retrieved {len(videos)} videos in {query_time:.2f}ms (with eager loading)")

    return videos

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
        difficult=difficult
        # Note: screenshot_path and screenshot_zoom_path are not model columns
    )
    db.add(db_object)
    db.commit()
    db.refresh(db_object)
    return db_object

def get_ground_truth_objects(db: Session, video_id: str, user_id: str = "anonymous") -> List[GroundTruthObject]:
    # SECURITY FIX: Join through Video, VideoProjectLink, and Project to ensure user can only access their ground truth objects
    # Issue #6: Exclude soft-deleted records
    return db.query(GroundTruthObject).join(Video).join(VideoProjectLink).join(Project).filter(
        GroundTruthObject.video_id == video_id,
        Project.owner_id == user_id,
        GroundTruthObject.deleted_at.is_(None)  # Only return active records
    ).all()

# Test Session CRUD
def create_test_session(db: Session, test_session: TestSessionCreate, user_id: str, session_id: Optional[str] = None) -> TestSession:
    """
    Create a new test session with optional pre-generated session ID.

    Args:
        db: Database session
        test_session: Test session creation data
        user_id: User creating the session
        session_id: Optional pre-generated session ID (for proactive WebSocket room join fix)

    Returns:
        Created TestSession instance

    Note:
        The session_id parameter enables the proactive room join fix that eliminates
        the 100-200ms race condition causing zero detections in HIL testing.
    """
    # Safely map only known fields to the ORM model
    data = test_session.model_dump(exclude_none=True)
    # Remove client-side config blob if present
    config_blob = data.pop('config', None)
    # Remove session_id from data if present (will be set separately)
    data.pop('session_id', None)
    # Filter to model columns to avoid unexpected kwargs
    allowed = {col.name for col in TestSession.__table__.columns}
    filtered = {k: v for k, v in data.items() if k in allowed}
    if config_blob is not None and 'test_configuration' in allowed:
        filtered['test_configuration'] = config_blob
    if not filtered.get("name"):
        filtered["name"] = "HIL Test Session"

    # FIX: Use pre-generated session_id if provided (enables proactive room join)
    if session_id:
        filtered['id'] = session_id
        logger.info(f"✅ Creating test session with pre-generated ID: {session_id}")
    else:
        logger.info(f"📝 Creating test session with auto-generated ID")

    filtered.setdefault("tolerance_ms", MATCHING_TOLERANCE_MS)

    db_session = TestSession(**filtered)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_test_sessions(db: Session, project_id: str = None, video_id: str = None, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[TestSession]:
    """Get test sessions with eager loading to prevent N+1 queries"""
    from sqlalchemy.orm import selectinload, joinedload
    import time

    start_time = time.time()

    # SECURITY FIX: Join with Project to ensure user can only access their test sessions
    # PERFORMANCE FIX: Add eager loading for relationships to prevent N+1 queries
    query = db.query(TestSession).join(Project).options(
        joinedload(TestSession.project),  # Join load project (1:1)
        joinedload(TestSession.video),  # Join load video (1:1)
        selectinload(TestSession.detection_events),  # Batch load detection events
        selectinload(TestSession.results),  # Batch load test results
        selectinload(TestSession.video_sequences)  # Batch load video sequences
    ).filter(Project.owner_id == user_id)

    if project_id:
        query = query.filter(TestSession.project_id == project_id)
    if video_id:
        # Ensure video belongs to user through VideoProjectLink
        video_subquery = db.query(Video.id).join(VideoProjectLink).join(Project).filter(
            Project.owner_id == user_id,
            Video.id == video_id
        ).subquery()
        query = query.filter(TestSession.video_id.in_(video_subquery))

    sessions = query.offset(skip).limit(limit).all()

    query_time = (time.time() - start_time) * 1000
    logger.info(f"Retrieved {len(sessions)} test sessions in {query_time:.2f}ms (with eager loading)")

    return sessions

def get_test_session(db: Session, session_id: str, user_id: str = "anonymous") -> Optional[TestSession]:
    # SECURITY FIX: Join with Project to ensure user can only access their test sessions
    return db.query(TestSession).join(Project).filter(
        TestSession.id == session_id,
        Project.owner_id == user_id
    ).first()

# Detection Event CRUD
def create_detection_event(db: Session, detection: DetectionEventSchema) -> DetectionEvent:
    data = detection.model_dump()
    # Ensure video_id is populated based on test_session_id if missing
    if not data.get('video_id') and data.get('test_session_id'):
        try:
            session = db.query(TestSession).filter(TestSession.id == data['test_session_id']).first()
            if session and session.video_id:
                data['video_id'] = session.video_id
        except Exception as e:
            logger.warning(f"Could not backfill detection.video_id from session: {e}")

    # FIXED: Ensure frame_number is always set
    if 'frame_number' not in data or data['frame_number'] is None:
        data['frame_number'] = 0
    if 'video_frame_number' not in data or data['video_frame_number'] is None:
        data['video_frame_number'] = 0

    db_detection = DetectionEvent(**data)
    db.add(db_detection)
    db.commit()
    db.refresh(db_detection)
    # Debug log with correlation details
    try:
        logger.info(
            "DetectionEvent created",
            extra={
                'extra_data': {
                    'event_type': 'detection_event',
                    'id': db_detection.id,
                    'session_id': db_detection.test_session_id,
                    'video_id': db_detection.video_id,
                    'timestamp': getattr(db_detection, 'timestamp', None),
                    'channel': getattr(db_detection, 'channel', None),
                    'voltage': getattr(db_detection, 'voltage', None),
                    'validation_result': getattr(db_detection, 'validation_result', None),
                }
            }
        )
    except Exception:
        pass
    return db_detection

def get_detection_events(db: Session, test_session_id: str, user_id: str = "anonymous") -> List[DetectionEvent]:
    """Get detection events for a test session with eager loading to prevent N+1 queries"""
    from sqlalchemy.orm import selectinload, joinedload

    # SECURITY FIX: Join through TestSession and Project to ensure user can only access their detection events
    # PERFORMANCE FIX: Eager load all relationships to prevent N+1 queries
    return db.query(DetectionEvent).join(TestSession).join(Project).options(
        joinedload(DetectionEvent.test_session),  # Join load test session (1:1)
        joinedload(DetectionEvent.video),  # Join load video (1:1)
        selectinload(DetectionEvent.ground_truth_match),  # Batch load ground truth matches
        selectinload(DetectionEvent.sequence_video_result)  # Batch load sequence results
    ).filter(
        DetectionEvent.test_session_id == test_session_id,
        Project.owner_id == user_id
    ).order_by(DetectionEvent.timestamp).all()

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
    """Get dashboard statistics for a user - Optimized with single query using subqueries"""
    from sqlalchemy import func, select
    import time

    start_time = time.time()

    # PERFORMANCE FIX: Use single query with multiple subqueries instead of 4 separate queries
    # This reduces database round trips from 4 to 1

    # Build subqueries for each stat
    project_subq = select(func.count(Project.id)).where(Project.owner_id == user_id).scalar_subquery()

    video_subq = select(func.count(Video.id.distinct())).select_from(
        Video.__table__.join(VideoProjectLink).join(Project)
    ).where(Project.owner_id == user_id).scalar_subquery()

    test_session_subq = select(func.count(TestSession.id)).select_from(
        TestSession.__table__.join(Project)
    ).where(Project.owner_id == user_id).scalar_subquery()

    detection_event_subq = select(func.count(DetectionEvent.id)).select_from(
        DetectionEvent.__table__.join(TestSession).join(Project)
    ).where(Project.owner_id == user_id).scalar_subquery()

    # Execute single query with all subqueries
    result = db.query(
        project_subq.label('project_count'),
        video_subq.label('video_count'),
        test_session_subq.label('test_session_count'),
        detection_event_subq.label('detection_event_count')
    ).first()

    query_time = (time.time() - start_time) * 1000
    logger.info(f"Dashboard stats retrieved in {query_time:.2f}ms (1 query with subqueries)")

    return {
        "project_count": result.project_count or 0,
        "video_count": result.video_count or 0,
        "test_session_count": result.test_session_count or 0,
        "detection_event_count": result.detection_event_count or 0
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
